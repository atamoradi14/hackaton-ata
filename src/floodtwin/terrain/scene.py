"""Bounded, real-data browser mesh. No inferred architectural ornament."""
import hashlib
import json
from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely.geometry import box, shape, MultiPoint
from shapely import contains_xy
from scipy.ndimage import maximum_filter, minimum_filter, binary_dilation
from scipy.spatial import Delaunay, cKDTree
from scipy.interpolate import LinearNDInterpolator
from .roofs import triangulate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(folder, radius=160):
    folder = Path(folder)
    site = json.loads((folder / "site_manifest.json").read_text())
    qc = json.loads((folder / "terrain-qc.json").read_text())
    if any(qc['layers'][name]['vertical_datum'] != 'NZVD2016' for name in ['dem','dsm']):
        raise ValueError("Verified NZVD2016 terrain required")
    x, y = site["nztm"]
    bounds = [int(x)-radius, int(y)-radius, int(x)+radius, int(y)+radius]
    with rasterio.open(folder / "dem_discovery.tif") as dem, rasterio.open(folder / "dsm_discovery.tif") as dsm:
        if dem.crs.to_epsg() != 2193 or dsm.crs != dem.crs or dem.transform != dsm.transform:
            raise ValueError("Aligned NZTM DEM/DSM required")
        window = from_bounds(*bounds, dem.transform).round_offsets().round_lengths()
        ground = dem.read(1, window=window, masked=True)
        surface = dsm.read(1, window=window, masked=True)
        transform = dem.window_transform(window)
        if np.ma.getmaskarray(ground).any() or np.ma.getmaskarray(surface).any():
            raise ValueError("Scene has missing terrain coverage")
    ground, surface = np.asarray(ground), np.asarray(surface)
    buildings = gpd.read_file(folder / "buildings.gpkg", bbox=tuple(bounds)).to_crs(2193)
    buildings = buildings[buildings.geometry.intersects(box(*bounds))].copy()
    polygons = [g.intersection(box(*bounds)) for g in buildings.geometry]
    mask = rasterize([(g, 1) for g in polygons], out_shape=ground.shape, transform=transform, fill=0, dtype="uint8")
    # DSM values are observed surfaces, not an architectural roof reconstruction.
    roof = np.where(mask, np.maximum(ground, surface), ground)
    import laspy
    cloud=laspy.read(folder/"pointcloud_crop.laz")
    selected=(np.asarray(cloud.classification)==6)&~np.asarray(cloud.withheld,dtype=bool)
    native=np.stack([np.asarray(cloud.x)[selected],np.asarray(cloud.y)[selected],np.asarray(cloud.z)[selected]],axis=1)
    roof_meshes=[]
    roof_polygons=[]
    roof_trees=[]
    roof_quality=[]
    for geometry in polygons:
        candidates=native[contains_xy(geometry.buffer(.3),native[:,0],native[:,1])]
        if len(candidates)<50:
            roof_trees.append(None);continue
        # Keep an actual highest classified return per 0.35m horizontal voxel.
        order=np.argsort(-candidates[:,2]);candidates=candidates[order]
        _,indices=np.unique(np.floor(candidates[:,:2]/.35).astype("int64"),axis=0,return_index=True)
        candidates=candidates[indices]
        if len(candidates)<20:
            roof_trees.append(None);continue
        if geometry.area<=0 or MultiPoint(candidates[:,:2]).convex_hull.intersection(geometry).area/geometry.area<.7:
            roof_trees.append(None);continue
        candidates,triangles,quality=triangulate(candidates,geometry)
        xyz=candidates[triangles,:2]
        area=np.abs((xyz[:,1,0]-xyz[:,0,0])*(xyz[:,2,1]-xyz[:,0,1])-(xyz[:,1,1]-xyz[:,0,1])*(xyz[:,2,0]-xyz[:,0,0])).sum()/2
        quality['coverage_fraction']=float(area/geometry.area)
        quality['approximate_fallback']=bool(len(triangles)<10 or area/geometry.area<.7)
        roof_quality.append(quality)
        if quality['approximate_fallback']:
            roof_trees.append(None);continue
        tree=cKDTree(candidates[:,:2])
        roof_trees.append((tree,candidates,LinearNDInterpolator(candidates[:,:2],candidates[:,2])))
        roof_polygons.append(geometry)
        shifted=candidates.copy();shifted[:,0]-=x;shifted[:,1]-=y
        roof_meshes.append(dict(vertices=np.round(shifted,3).ravel().tolist(),triangles=triangles.ravel().tolist(),
                                provenance="Class 6 measured returns; 0.35m voxel; local outliers, footprint-crossing and long/high triangles rejected"))
    native_mask=rasterize([(g,1) for g in roof_polygons],out_shape=ground.shape,transform=transform,fill=0,dtype="uint8") if roof_polygons else np.zeros_like(mask)
    fallback_levels=[]
    for index,geometry in enumerate(polygons):
        local_mask=rasterize([(geometry,1)],out_shape=ground.shape,transform=transform,fill=0,dtype='uint8').astype(bool)
        level=float(np.median(surface[local_mask])) if local_mask.any() else float(ground.min())
        fallback_levels.append(level)
        if roof_trees[index] is None:
            roof[local_mask]=np.maximum(ground[local_mask],level)
    facade_rings = []
    for index,geometry in enumerate(polygons):
        for polygon in ([geometry] if geometry.geom_type=="Polygon" else geometry.geoms if geometry.geom_type=="MultiPolygon" else []):
            anchor=polygon.representative_point()
            ring=[]
            for east,north in polygon.exterior.coords:
                delta=np.array([anchor.x-east,anchor.y-north]);delta*=min(1,.8/max(np.linalg.norm(delta),.01))
                r,c=rasterio.transform.rowcol(transform,east,north)
                rr,cc=rasterio.transform.rowcol(transform,east+delta[0],north+delta[1])
                r,c=int(np.clip(r,0,ground.shape[0]-1)),int(np.clip(c,0,ground.shape[1]-1))
                rr,cc=int(np.clip(rr,0,ground.shape[0]-1)),int(np.clip(cc,0,ground.shape[1]-1))
                top=float(max(fallback_levels[index],ground[r,c]))
                if roof_trees[index] is not None:
                    tree,vertices,interpolate=roof_trees[index]
                    roof_elevation=float(interpolate(east,north))
                    if np.isfinite(roof_elevation):
                        top=max(roof_elevation,float(ground[r,c]))
                    else:
                        distance,point=tree.query([east,north])
                        if distance<3:top=max(float(vertices[point,2]),float(ground[r,c]))
                ring.append([round(east-x,3),round(north-y,3),round(float(ground[r,c]),3),round(top,3)])
            facade_rings.append(ring)
    step = maximum_filter(ground, 3)-minimum_filter(ground, 3)
    candidates = (step > 0.8) & (step < 4.0) & ~binary_dilation(mask.astype(bool), iterations=3)
    vegetation = (surface-ground) > 1.0
    candidates &= ~binary_dilation(vegetation, iterations=1)
    lines = []
    for geo, value in shapes(candidates.astype("uint8"), transform=transform):
        if not value:
            continue
        polygon = shape(geo)
        if polygon.area < 4 or polygon.area > 500:
            continue
        ring = list(polygon.exterior.coords)
        # Boundary of a discontinuity band, not a claimed wall centreline.
        lines.append([[round(a-x,2), round(b-y,2)] for a,b in ring])
    parcel = gpd.read_file(folder / "parcel.geojson").to_crs(2193)
    rings = []
    for geometry in parcel.geometry:
        for polygon in ([geometry] if geometry.geom_type == "Polygon" else geometry.geoms):
            rings.append([[round(a-x,2),round(b-y,2)] for a,b in polygon.exterior.coords])
    from pyproj import Transformer
    projector=Transformer.from_crs(2193,4326,always_xy=True)
    lon,lat=projector.transform([bounds[0],bounds[2]],[bounds[1],bounds[3]])
    data = dict(version=6, synthetic=False, hydraulic=False, origin_nztm=[x,y], bounds_nztm=bounds, wgs84=site["lonlat"],
        bounds_latlon=[[lat[0],lon[0]],[lat[1],lon[1]]], roof_quality=roof_quality,
        grid=dict(rows=ground.shape[0], cols=ground.shape[1], cell_m=dem.res[0], west=transform.c-x,
                  north=transform.f-y, elevations=np.round(ground,3).ravel().tolist(),
                  surfaces=np.round(roof,3).ravel().tolist(), buildings=mask.ravel().tolist(), native_roofs=native_mask.ravel().tolist()),
        parcel=rings, candidate_bands=lines[:300], building_count=len(buildings), facade_rings=facade_rings, roof_meshes=roof_meshes,
        candidate_status="LiDAR elevation discontinuity; wall/bank interpretation and crest unverified",
        roof_status="QA-filtered classified LiDAR roofs; unsupported footprints use approximate flat DSM-median roofs; facades approximate; not architectural surveys",
        datum="NZVD2016", horizontal_crs="EPSG:2193", source_resolution_m=1,
        accuracy="Survey specification ±0.2m at 95%; not local independent validation",
        sources=dict(dem_sha256=sha(folder/"dem_discovery.tif"), dsm_sha256=sha(folder/"dsm_discovery.tif"),
                     outlines_sha256=sha(folder/"buildings.gpkg")),
        imagery=json.loads((folder/"scene-aerial.json").read_text()) if (folder/"scene-aerial.json").exists() else None)
    temporary=folder/'scene.tmp'
    temporary.write_text(json.dumps(data, separators=(",",":"), allow_nan=False))
    temporary.replace(folder/'scene.json')
    return data
