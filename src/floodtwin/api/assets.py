"""Display derivatives from actual source files, never hydraulic substitutes."""
import csv
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds, reproject, Resampling
from PIL import Image

LAYERS = {name: name + ".gpkg" for name in
          ["overland_flow", "pipes", "catchpits", "manholes", "connections", "flood_plains", "flood_prone", "buildings"]}


def aerial_overlay(folder):
    """Warp the recorded NZTM crop into Leaflet's actual Web Mercator plane."""
    output,meta=folder/'map-aerial.png',folder/'map-aerial.json'
    if output.exists() and meta.exists():
        return json.loads(meta.read_text())
    source_meta=json.loads((folder/'scene-aerial.json').read_text())
    source=np.asarray(Image.open(folder/'scene-aerial.jpg').convert('RGBA'))
    height,width=source.shape[:2]
    bounds=source_meta['bounds_nztm']
    target_bounds=transform_bounds(2193,3857,*bounds,densify_pts=21)
    target=np.zeros((4,height,width),dtype='uint8')
    reproject(source=np.moveaxis(source,-1,0),destination=target,
              src_transform=from_bounds(*bounds,width,height),src_crs=2193,
              dst_transform=from_bounds(*target_bounds,width,height),dst_crs=3857,
              resampling=Resampling.bilinear,dst_nodata=0)
    Image.fromarray(np.moveaxis(target,0,-1)).save(output)
    west,south,east,north=transform_bounds(3857,4326,*target_bounds)
    result=dict(bounds=[[south,west],[north,east]],source_crs='EPSG:2193',display_crs='EPSG:3857',
                source=source_meta['title'],source_sha256=source_meta['sha256'],
                provenance='/files/scene-aerial.json',resampling='bilinear; transparent outside source crop')
    meta.write_text(json.dumps(result))
    return result


def layer(folder, name):
    if name == "parcel":
        return json.loads((folder / "parcel.geojson").read_text())
    if name not in LAYERS or not (folder / LAYERS[name]).exists():
        raise ValueError("This layer is not available for the confirmed property")
    frame = gpd.read_file(folder / LAYERS[name])
    if frame.crs is None or frame.crs.to_epsg() != 2193:
        raise ValueError("Source layer CRS not verified")
    # Display geometries are simplified in metres; original GIS stays untouched.
    frame = frame[["geometry"]].copy()
    frame.geometry = frame.geometry.simplify(0.25, preserve_topology=True)
    frame["source_layer"] = name
    frame["status"] = "official_map; not a hydraulic result"
    return json.loads(frame.to_crs(4326).to_json(drop_id=True))


def terrain_overlay(folder):
    output = folder / "map-terrain.png"
    meta = folder / "map-terrain.json"
    if output.exists() and meta.exists():
        return json.loads(meta.read_text())
    with rasterio.open(folder / "dem_discovery.tif") as source:
        if source.crs.to_epsg() != 2193 or source.tags().get("vertical_datum") != "NZVD2016":
            raise ValueError("Terrain CRS/datum not verified")
        west, south, east, north = transform_bounds(source.crs, "EPSG:4326", *source.bounds)
        values = np.full((512, 512), np.nan, dtype="float32")
        reproject(source=rasterio.band(source, 1), destination=values, src_nodata=source.nodata,
                  dst_nodata=np.nan, src_transform=source.transform, src_crs=source.crs,
                  dst_transform=from_bounds(west, south, east, north, 512, 512), dst_crs="EPSG:4326",
                  resampling=Resampling.bilinear)
    valid = np.isfinite(values)
    if not valid.any():
        raise ValueError("Terrain preview has no valid elevations")
    low, high = np.nanpercentile(values, [2, 98])
    normal = np.clip((np.nan_to_num(values, nan=low) - low) / max(high - low, 1), 0, 1)
    palette = np.array([[33, 92, 92], [108, 153, 120], [203, 194, 136], [235, 219, 177]])
    rgb = np.stack([np.interp(normal, np.linspace(0, 1, 4), palette[:, i]) for i in range(3)], axis=-1)
    dy, dx = np.gradient(np.nan_to_num(values, nan=low))
    shade = np.clip(0.85 + 0.1 * (-dx + dy), 0.60, 1.08)
    rgba = np.concatenate([np.clip(rgb * shade[..., None], 0, 255).astype("uint8"),
                           (valid * 210).astype("uint8")[..., None]], axis=-1)
    Image.fromarray(rgba).save(output)
    result = dict(bounds=[[south, west], [north, east]], low_m=float(low), high_m=float(high),
                  description="Actual ground elevation, NZVD2016. 512-pixel display derivative; source remains 1 m.",
                  synthetic=False, hydraulic=False)
    meta.write_text(json.dumps(result))
    return result


def profiles(folder):
    with (folder / "terrain-cross-sections.csv").open() as source:
        rows = list(csv.DictReader(source))
    return dict(offset_m=[float(r["offset_m"]) for r in rows],
                east_m=[float(r["east_west_dem_m_NZVD2016"]) for r in rows],
                north_m=[float(r["north_south_dem_m_NZVD2016"]) for r in rows],
                datum="NZVD2016", synthetic=False)


def lab(root):
    import xarray as xr
    runs = sorted((root / "runs").glob("quality-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for run in runs:
        manifest = run / "validation.json"
        if manifest.exists() and json.loads(manifest.read_text()).get("passed"):
            validation = json.loads(manifest.read_text())
            cases = {}
            for name in ["open", "weir", "infinite_barrier"]:
                expected = validation["cases"][name]["outputs"]["sfincs_his.nc"]
                if hashlib.sha256((run / name / "sfincs_his.nc").read_bytes()).hexdigest() != expected:
                    raise ValueError("Synthetic output changed since validation; rerun the numerical checks")
                with xr.open_dataset(run / name / "sfincs_his.nc") as ds:
                    left = ds.station_x.values < 20
                    cases[name] = dict(upstream_m=ds.point_zs.values[:, left].mean(axis=1).tolist(),
                                       downstream_m=ds.point_zs.values[:, ~left].mean(axis=1).tolist())
                    seconds = ((ds.time.values - ds.time.values[0]) / np.timedelta64(1, "s")).tolist()
            return dict(synthetic=True, real_solver=True, seconds=seconds, cases=cases,
                        validation=validation, report_directory=str(run))
    raise ValueError("No validated synthetic solver run is available")
