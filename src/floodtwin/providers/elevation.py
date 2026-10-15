"""Inspect actual LINZ STAC capture polygons without downloading raster tiles."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin
import requests
from shapely.geometry import shape, Point

ROOT = "https://nz-elevation.s3.ap-southeast-2.amazonaws.com/catalog.json"


def discover():
    site = json.loads(Path("data/processed/site/site_manifest.json").read_text())
    point = Point(site["lonlat"])
    folder = Path("data/raw/elevation-metadata")
    folder.mkdir(parents=True, exist_ok=True)
    def get(url, name):
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        path = folder / name
        path.write_bytes(response.content)
        return response.json(), hashlib.sha256(response.content).hexdigest()
    catalog, digest = get(ROOT, "catalog.json")
    results = []
    for link in catalog["links"]:
        if link["rel"] != "child" or "auckland-part-" not in link["href"] or "_2024" not in link["href"]:
            continue
        url = urljoin(ROOT, link["href"])
        label = link["href"].split("/")[2] + "-" + link["href"].split("/")[3]
        collection, collection_hash = get(url, label + "-collection.json")
        asset = collection["assets"]["capture_area"]
        capture, capture_hash = get(urljoin(url, asset["href"]), label + "-capture.geojson")
        advertised = asset.get("file:checksum", "")
        if advertised.startswith("1220") and capture_hash != advertised[4:]:
            raise RuntimeError("STAC capture checksum mismatch")
        features = capture["features"] if capture["type"] == "FeatureCollection" else [capture]
        intersects = any(shape(feature["geometry"]).covers(point) for feature in features)
        results.append(dict(title=link.get("title"), collection_url=url,
                            capture_area_covers_address=intersects,
                            collection_sha256=collection_hash, capture_sha256=capture_hash,
                            temporal_extent=collection["extent"]["temporal"], license=collection.get("license"),
                            raster_tile_downloaded=False, vertical_datum="must verify tile/survey metadata",
                            caveat="Simplified capture polygon; verify exact raster tile coverage/nodata before use"))
    output = dict(actual_public_metadata=True, root_sha256=digest, collections=results)
    Path("data/processed/site/elevation-discovery.json").write_text(json.dumps(output, indent=2))
    return output
