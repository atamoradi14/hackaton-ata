"""Bounded, real-data browser mesh. No inferred architectural ornament."""
import hashlib
import json
from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely.geometry import box, shape
from scipy.ndimage import maximum_filter, minimum_filter, binary_dilation, median_filter
from shapely import contains_xy
from .roofs import triangulate

SCENE_VERSION = 11


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
    # Keep separate footprint IDs: adjacent buildings must never be triangulated
    # together. Use the measured DSM rather than arbitrary flat height extrusions.
    building_outlines=[]
    building_ids=np.zeros(ground.shape,dtype='int32')
    roofs=ground.copy()
    building_index=0
    import laspy
    cloud=laspy.read(folder/'pointcloud_crop.laz')
    keep=(np.asarray(cloud.classification)==6)&~np.asarray(cloud.withheld,dtype=bool)
    native=np.column_stack([np.asarray(cloud.x)[keep],np.asarray(cloud.y)[keep],np.asarray(cloud.z)[keep]])
    roof_meshes=[]
    native_roofs=np.zeros(ground.shape,dtype='uint8')
    for geometry in polygons:
        for polygon in ([geometry] if geometry.geom_type == "Polygon" else geometry.geoms if geometry.geom_type == "MultiPolygon" else []):
            ring=[[round(east-x,2), round(north-y,2)] for east,north in polygon.exterior.coords]
            building_outlines.append(ring)
            local_mask=rasterize([(polygon,1)],out_shape=ground.shape,transform=transform,fill=0,dtype='uint8').astype(bool)
            if not local_mask.any():
                continue
            building_index+=1
            building_ids[local_mask]=building_index
            # Suppress isolated single-pixel DSM spikes, retaining source elevations
            # and recording this display-only operation. No invented architectural detail.
            filtered=median_filter(surface,size=3)
            interior=minimum_filter(local_mask.astype('uint8'),size=3).astype(bool)
            roofs[local_mask]=np.maximum(ground[local_mask],np.where(interior[local_mask],filtered[local_mask],surface[local_mask]))
            selected=native[contains_xy(polygon,native[:,0],native[:,1])]
            if len(selected)>=30:
                # Uniform sub-metre display sampling of actual classified returns.
                _,indices=np.unique(np.floor(selected[:,:2]/.25).astype('int64'),axis=0,return_index=True)
                vertices,triangles,quality=triangulate(selected[indices],polygon)
                if len(triangles):
                    xyz=vertices[triangles,:2]
                    area=np.abs((xyz[:,1,0]-xyz[:,0,0])*(xyz[:,2,1]-xyz[:,0,1])-(xyz[:,1,1]-xyz[:,0,1])*(xyz[:,2,0]-xyz[:,0,0])).sum()/2
                    if area/polygon.area>=.6:
                        native_roofs[local_mask]=1
                        shifted=vertices.copy();shifted[:,0]-=x;shifted[:,1]-=y
                        roof_meshes.append(dict(vertices=np.round(shifted,3).ravel().tolist(),triangles=triangles.ravel().tolist(),quality=quality))
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
    overland_paths=[]
    overland_file=folder/'overland_flow.gpkg'
    if overland_file.exists():
        flow=gpd.read_file(overland_file, bbox=tuple(bounds)).to_crs(2193)
        for geometry in flow.geometry:
            members=[geometry] if geometry.geom_type == 'LineString' else geometry.geoms if geometry.geom_type == 'MultiLineString' else []
            for member in members:
                clipped=member.intersection(box(*bounds))
                for line in ([clipped] if clipped.geom_type=='LineString' else clipped.geoms if clipped.geom_type=='MultiLineString' else []):
                    # Densify to the actual ground grid so mapped lines follow terrain
                    # instead of joining distant vertices with floating straight chords.
                    line=line.segmentize(1.0)
                    if len(line.coords)>=2:
                        overland_paths.append([[round(east-x,2),round(north-y,2)] for east,north,*_ in line.coords])
    from pyproj import Transformer
    projector=Transformer.from_crs(2193,4326,always_xy=True)
    lon,lat=projector.transform([bounds[0],bounds[2]],[bounds[1],bounds[3]])
    data = dict(version=SCENE_VERSION, synthetic=False, hydraulic=False, origin_nztm=[x,y], bounds_nztm=bounds, wgs84=site["lonlat"],
        bounds_latlon=[[lat[0],lon[0]],[lat[1],lon[1]]],
        grid=dict(rows=ground.shape[0], cols=ground.shape[1], cell_m=dem.res[0], west=transform.c-x,
                  north=transform.f-y, elevations=np.round(ground,3).ravel().tolist(),
                  surfaces=np.round(roofs,3).ravel().tolist(),building_ids=building_ids.ravel().tolist(),native_roofs=native_roofs.ravel().tolist(),buildings=mask.ravel().tolist()),
        parcel=rings, building_outlines=building_outlines, roof_meshes=roof_meshes, overland_paths=overland_paths,
        candidate_bands=lines[:300], building_count=len(buildings),
        candidate_status="LiDAR elevation discontinuity; wall/bank interpretation and crest unverified",
        roof_status="Class 6 measured roof triangulation where >=60% footprint coverage; elsewhere only aerial/ground context. Long/steep/cross-footprint triangles rejected. Display sides close roofs down to measured ground; facade detail unmeasured.",
        datum="NZVD2016", horizontal_crs="EPSG:2193", source_resolution_m=1,
        accuracy="Survey specification ±0.2m at 95%; not local independent validation",
        sources=dict(dem_sha256=sha(folder/"dem_discovery.tif"), dsm_sha256=sha(folder/"dsm_discovery.tif"),
                     outlines_sha256=sha(folder/"buildings.gpkg")),
        imagery=json.loads((folder/"scene-aerial.json").read_text()) if (folder/"scene-aerial.json").exists() else None)
    temporary=folder/'scene.tmp'
    temporary.write_text(json.dumps(data, separators=(",",":"), allow_nan=False))
    temporary.replace(folder/'scene.json')
    return data
