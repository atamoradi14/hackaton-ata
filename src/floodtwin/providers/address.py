"""Exact official LINZ matching; secrets stay out of responses and provenance."""
import hashlib
import json
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape
import geopandas as gpd
import requests


def address_fields(address):
    """Parse a user-entered NZ street address without making it an official match."""
    if not isinstance(address, str):
        raise ValueError("Provide a street number and street name")
    parts = [" ".join(s.split()) for s in address.split(",") if s.strip()]
    match = re.fullmatch(r"(\d+[A-Za-z]?)\s+(.+)", parts[0] if parts else "")
    if not match:
        raise ValueError("Provide a street number and street name")
    number, road = match.groups()
    # LINZ keeps town/city separate from the optional NZ postcode in full_address.
    town = re.sub(r"\s+\d{4}$", "", parts[2]).strip() if len(parts) >= 3 else ""
    return dict(full_address_number=number, full_road_name=road,
                suburb_locality=parts[1] if len(parts) >= 2 else "", town_city=town)


def like_literal(value):
    """Escape user text for a FES PropertyIsLike pattern (wildcards are ours only)."""
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")


def suggest(address, limit=8):
    """Return bounded official address labels for type-ahead; never assigns coordinates."""
    if not isinstance(address, str) or not 3 <= len(address.strip()) <= 160:
        return []
    terms = [like_literal(term) for term in re.findall(r"[\w'-]+", address, flags=re.UNICODE)]
    if not terms:
        return []
    pattern = "*" + "*".join(terms) + "*"
    query_filter = ("<fes:Filter xmlns:fes=\"http://www.opengis.net/fes/2.0\">"
                    "<fes:PropertyIsLike wildCard=\"*\" singleChar=\"?\" escapeChar=\"&#92;\" matchCase=\"false\">"
                    "<fes:ValueReference>full_address</fes:ValueReference>"
                    f"<fes:Literal>{escape(pattern)}</fes:Literal>"
                    "</fes:PropertyIsLike></fes:Filter>")
    # LINZ does not guarantee relevance order. Fetch a bounded candidate window,
    # rank locally, then expose only the small type-ahead list.
    response, _ = wfs(dict(request="GetFeature", typeNames="layer-123113", count=max(80, limit * 12),
                           outputFormat="application/json", propertyName="address_id,full_address",
                           filter=query_filter), "address_suggestions.json")
    features = response.json().get("features", [])
    seen = set()
    results = []
    for feature in features:
        properties = feature.get("properties") or {}
        label = str(properties.get("full_address") or "").strip()
        address_id = properties.get("address_id")
        if label and address_id is not None and label.casefold() not in seen:
            seen.add(label.casefold())
            results.append(dict(address=label, address_id=int(address_id)))
    wanted = " ".join(terms).casefold()
    def relevance(item):
        value = item["address"].casefold()
        number = terms[0].casefold()
        return (0 if value.startswith(wanted) else 1,
                0 if value.startswith(number + " ") else 1,
                len(value), value)
    return sorted(results, key=relevance)[:limit]


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
    fields = address_fields(address)
    if not all(fields.values()):
        raise ValueError("Provide number and full street, suburb, city")
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
