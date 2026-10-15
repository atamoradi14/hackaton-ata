"""Acquire small, grid-aligned COG windows from spatially intersecting STAC tiles."""
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin
import numpy as np
import requests
import rasterio
from rasterio.merge import merge
from pyproj import Transformer
from shapely.geometry import box, shape


def prepare():
    site_dir = Path("data/processed/site")
    site = json.loads((site_dir / "site_manifest.json").read_text())
    if not site.get("user_visual_confirmation"):
        raise RuntimeError("Property confirmation required")
    discovery = json.loads((site_dir / "elevation-discovery.json").read_text())
    gis = json.loads((site_dir / "gis-discovery-manifest.json").read_text())
    xmin, ymin, xmax, ymax = gis["discovery_bbox_nztm"]
    bounds = (math.floor(xmin), math.floor(ymin), math.ceil(xmax), math.ceil(ymax))
    tr = Transformer.from_crs(2193, 4326, always_xy=True)
    lonmin, latmin = tr.transform(bounds[0], bounds[1]); lonmax, latmax = tr.transform(bounds[2], bounds[3])
    query_box = box(min(lonmin, lonmax), min(latmin, latmax), max(lonmin, lonmax), max(latmin, latmax))
    folder = Path("data/raw/terrain-metadata")
    folder.mkdir(parents=True, exist_ok=True)
    def get(url, filename):
        path = folder / filename
        if path.exists():
            return json.loads(path.read_text())
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
        return response.json()
    reports = {}
    arrays = {}
    for product in ["dem", "dsm"]:
        candidates = [c for c in discovery["collections"] if c["capture_area_covers_address"] and f"/{product}_1m/" in c["collection_url"]]
        if len(candidates) != 1:
            raise RuntimeError("Survey coverage ambiguous; manual selection needed")
        selected = candidates[0]
        url = selected["collection_url"]
        if "auckland-part-1_2024" not in url:
            raise RuntimeError("Survey metadata must be registered before adding a new source")
        layer_id = 121990 if product == "dem" else 121992
        official_url = f"https://data.linz.govt.nz/layer/{layer_id}-auckland-part-1-lidar-1m-{product}-2024/"
        page = requests.get(official_url, timeout=60)
        page.raise_for_status()
        (folder / (product + "-official-metadata.html")).write_bytes(page.content)
        # The LDS site serves a JS shell to plain HTTP. Use the explicit,
        # independently verified official source registry, never infer a datum.
        registry = json.loads(Path("docs/verified-surveys.json").read_text())
        evidence = registry["surveys"].get(str(layer_id))
        if not evidence or evidence["url"] != official_url or evidence["vertical_datum"] != "NZVD2016":
            raise RuntimeError("Official vertical datum evidence unavailable")
        collection = get(url, product + "-collection.json")
        links = [l for l in collection["links"] if l["rel"] == "item"]
        def item(link):
            item_url = urljoin(url, link["href"])
            return item_url, get(item_url, product + "-" + link["href"].split("/")[-1])
        with ThreadPoolExecutor(max_workers=6) as pool:
            indexed = list(pool.map(item, links))
        intersecting = [(item_url, payload) for item_url, payload in indexed if shape(payload["geometry"]).intersects(query_box)]
        if not intersecting or len(intersecting) > 12:
            raise RuntimeError("Unexpected bounded tile count")
        sources = []
        records = []
        try:
            for item_url, payload in intersecting:
                asset = payload["assets"]["visual"]
                raster_url = urljoin(item_url, asset["href"])
                response = requests.get(raster_url, headers={"Range": "bytes=0-255"}, timeout=60)
                if response.status_code != 206:
                    raise RuntimeError("COG server does not honor bounded range requests")
                src = rasterio.open(raster_url)
                if src.crs.to_epsg() != 2193 or src.res != (1.0, 1.0):
                    src.close()
                    raise RuntimeError("Source raster CRS/resolution mismatch")
                sources.append(src)
                records.append(dict(stac_item=item_url, raster_url=raster_url, item_id=payload["id"],
                                    properties=payload["properties"], source_checksum=asset.get("file:checksum"),
                                    full_source_checksum_verified=False, acquisition="HTTP range window; not full tile download",
                                    source_raster_bounds=list(src.bounds), source_crs=src.crs.to_string(), resolution_m=src.res))
            values, transform = merge(sources, bounds=bounds, res=1, nodata=-9999, dtype="float32")
        finally:
            for src in sources:
                src.close()
        path = site_dir / (product + "_discovery.tif")
        with rasterio.open(path, "w", driver="GTiff", width=values.shape[2], height=values.shape[1], count=1,
                           dtype="float32", crs=2193, transform=transform, nodata=-9999,
                           compress="deflate", tiled=True) as dst:
            dst.write(values)
            dst.update_tags(vertical_datum="NZVD2016", units="m", source=official_url,
                            usage="discovery crop only; not selected hydraulic domain")
        masked = np.ma.masked_equal(values[0], -9999)
        arrays[product] = (masked, transform)
        reports[product] = dict(source=official_url, source_metadata_sha256=hashlib.sha256(page.content).hexdigest(),
                               license="CC-BY-4.0", producer="Woolpert", horizontal_crs="EPSG:2193",
                               vertical_datum="NZVD2016", datum_evidence=evidence, datum_evidence_checked_on=registry["checked_on"],
                               vertical_conversion="none; source is already NZVD2016", units="m",
                               vertical_accuracy_specification="±0.2 m at 95% (survey specification, not local validation)",
                               output_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                               nodata_fraction=float(np.ma.getmaskarray(masked).mean()),
                               min_m=float(masked.min()), max_m=float(masked.max()),
                               shape=list(masked.shape), transform=list(transform), tiles=records)
    if arrays["dem"][1] != arrays["dsm"][1] or arrays["dem"][0].shape != arrays["dsm"][0].shape:
        raise RuntimeError("DEM/DSM grids not aligned")
    height = arrays["dsm"][0] - arrays["dem"][0]
    reports["height_flags"] = dict(negative_height_cells=int((height < -0.2).sum()),
                                   candidate_status="above-ground height only; buildings/trees/walls not classified")
    report = dict(actual_data=True, synthetic=False, bounds_nztm=bounds, final_hydraulic_domain=False,
                  layers=reports, caveats=["Discovery crop is not guaranteed to include upstream contributors/downstream outlets",
                                         "No interpolation across nodata; datum conversions not applied",
                                         "DSM is not used as the hydraulic bed; structure review still needed"])
    (site_dir / "terrain-qc.json").write_text(json.dumps(report, indent=2))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    a = axes[0].imshow(arrays["dem"][0], cmap="terrain"); fig.colorbar(a, ax=axes[0], label="Elevation (m NZVD2016)")
    b = axes[1].imshow(height, cmap="viridis", vmin=0, vmax=15); fig.colorbar(b, ax=axes[1], label="DSM minus DEM (m)")
    axes[0].set_title("Actual bare-earth DEM discovery crop")
    axes[1].set_title("Above-ground heights — not wall classification")
    for ax in axes: ax.set_axis_off()
    fig.suptitle("LINZ Auckland Part 1 2024 — no hydraulic/flood-risk result")
    fig.tight_layout(); fig.savefig(site_dir / "terrain-preview.png", dpi=150); plt.close(fig)
    return report
