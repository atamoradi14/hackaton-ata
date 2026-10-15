"""Bounded official building footprints, preserving source attributes."""
import hashlib
import json
from pathlib import Path
import os
import geopandas as gpd
from floodtwin.providers.address import wfs

for line in (Path(".env").read_text(encoding="utf-8-sig").splitlines() if Path(".env").exists() else []):
    if line.startswith("LINZ_API_KEY="):
        os.environ.setdefault("LINZ_API_KEY", line.split("=", 1)[1])
folder = Path("data/processed/site")
query = json.loads((folder / "gis-discovery-manifest.json").read_text())
bbox = ",".join(map(str, query["discovery_bbox_nztm"])) + ",EPSG:2193"
features = []
hashes = {}
seen = set()
for offset in range(0, 10000, 1000):
    response, raw = wfs(dict(request="GetFeature", typeNames="layer-101290", count=1000, startIndex=offset,
                             outputFormat="application/json", srsName="EPSG:2193", bbox=bbox), f"buildings-{offset}.json")
    payload = response.json()
    if "2193" not in payload.get("crs", {}).get("properties", {}).get("name", ""):
        raise RuntimeError("Building response CRS unverified")
    hashes[raw.name] = hashlib.sha256(raw.read_bytes()).hexdigest()
    for feature in payload.get("features", []):
        identifier = feature.get("id")
        if identifier is None or identifier in seen:
            raise RuntimeError("Missing/duplicate building identifier across pages")
        seen.add(identifier); features.append(feature)
    if len(payload.get("features", [])) < 1000:
        break
else:
    raise RuntimeError("Local building query exceeded cap")
frame = gpd.GeoDataFrame.from_features(features, crs=2193)
frame.to_file(folder / "buildings.gpkg", layer="buildings", driver="GPKG")
result = dict(actual_public_data=True, source="https://data.linz.govt.nz/layer/101290-nz-building-outlines/",
              count=len(frame), invalid_geometries=int((~frame.geometry.is_valid).sum()),
              provenance_status="official_map", license="CC-BY-4.0", horizontal_crs="EPSG:2193",
              building_heights="not_assigned", entry_thresholds="not_assessed", hashes=hashes)
(folder / "buildings-manifest.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
