"""Exact official LINZ matching; secrets stay out of responses and provenance."""
import hashlib
import json
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape
import geopandas as gpd
import requests


def wfs(parameters, filename):
    key = os.environ.get("LINZ_API_KEY")
    if not key:
        raise RuntimeError("LINZ_API_KEY missing; no coordinates assigned")
    try:
        response = requests.get("https://data.linz.govt.nz/services;key=" + key + "/wfs",
                                params=dict(service="WFS", version="2.0.0", **parameters), timeout=60)
    except requests.RequestException:
        raise RuntimeError("LINZ connection failed; URL/credential withheld") from None
    folder = Path("data/raw/linz")
    folder.mkdir(parents=True, exist_ok=True)
    redacted = response.text.replace(key, "REDACTED")
    digest = hashlib.sha256(redacted.encode()).hexdigest()
    name = Path(filename)
    path = folder / f"{name.stem}-{digest}{name.suffix}"
    if not path.exists():
        path.write_text(redacted)
    if response.status_code != 200 or "ExceptionReport" in response.text:
        raise RuntimeError(f"LINZ request failed (HTTP {response.status_code}); inspect redacted local response")
    return response, path


def resolve(address):
    parts = [s.strip() for s in address.split(",")]
    match = re.fullmatch(r"(\d+)\s+(.+)", parts[0])
    if not match or len(parts) < 3:
        raise ValueError("Provide number and full street, suburb, city")
    number, road = match.groups()
    fields = dict(full_address_number=number, full_road_name=road, suburb_locality=parts[1], town_city=parts[2])
    response, schema = wfs(dict(request="DescribeFeatureType", typeNames="layer-123113"), "addresses_schema.xml")
    if any(f'name="{field}"' not in response.text for field in fields):
        raise RuntimeError("Official address schema changed")
    clauses = "".join(f'<fes:PropertyIsEqualTo matchCase="false"><fes:ValueReference>{field}</fes:ValueReference><fes:Literal>{escape(value)}</fes:Literal></fes:PropertyIsEqualTo>' for field, value in fields.items())
    query_filter = f'<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:And>{clauses}</fes:And></fes:Filter>'
    response, raw = wfs(dict(request="GetFeature", typeNames="layer-123113", count=20,
                             outputFormat="application/json", srsName="EPSG:2193", filter=query_filter), "address_candidates.json")
    payload = response.json()
    if len(payload.get("features", [])) != 1:
        raise RuntimeError(f"Found {len(payload.get('features', []))} exact address candidates; selection required")
    if "2193" not in payload.get("crs", {}).get("properties", {}).get("name", ""):
        raise RuntimeError("Address CRS unverified")
    addresses = gpd.GeoDataFrame.from_features(payload["features"], crs=2193)
    for field, wanted in fields.items():
        if str(addresses.iloc[0][field]).strip().casefold() != wanted.casefold():
            raise RuntimeError("Returned address was not an exact match")
    point = addresses.geometry.iloc[0]
    x, y = point.x, point.y
    response, parcel_raw = wfs(dict(request="GetFeature", typeNames="layer-50772", count=100,
                                    outputFormat="application/json", srsName="EPSG:2193",
                                    bbox=f"{x-50},{y-50},{x+50},{y+50},EPSG:2193"), "parcel_candidates.json")
    parcels_json = response.json()
    if "2193" not in parcels_json.get("crs", {}).get("properties", {}).get("name", ""):
        raise RuntimeError("Parcel CRS unverified")
    if parcels_json.get("numberMatched", 0) > 100:
        raise RuntimeError("Parcel query exceeded local result cap")
    parcels = gpd.GeoDataFrame.from_features(parcels_json["features"], crs=2193)
    selected = parcels[parcels.geometry.covers(point)]
    if len(selected) != 1:
        raise RuntimeError(f"Parcel association ambiguous: {len(selected)} matches")
    local = Path("data/processed/site")
    local.mkdir(parents=True, exist_ok=True)
    addresses.to_crs(4326).to_file(local / "address.geojson", driver="GeoJSON")
    selected.to_crs(4326).to_file(local / "parcel.geojson", driver="GeoJSON")
    lonlat = addresses.to_crs(4326).geometry.iloc[0]
    result = dict(address=str(addresses.iloc[0]["full_address"]), address_id=int(addresses.iloc[0]["address_id"]),
                  parcel_id=str(selected.iloc[0].get("id", selected.index[0])), nztm=[x, y], lonlat=[lonlat.x, lonlat.y],
                  official_exact_match=True, user_visual_confirmation=False, hydraulic_domain="not_selected",
                  horizontal_crs="EPSG:2193", vertical_datum="2D geometry; no elevations assigned",
                  source="https://data.linz.govt.nz/layer/123113-nz-addresses/", license="CC-BY-4.0",
                  hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [schema, raw, parcel_raw]})
    (local / "site_manifest.json").write_text(json.dumps(result, indent=2))
    return result
