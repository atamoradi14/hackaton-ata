"""Public metadata discovery and transfer-limit-safe bounded queries."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/"
LAYERS = {"overland_flow": "Overland_Flow_Paths", "flood_plains": "Flood_Plains",
          "flood_prone": "Flood_Prone_Areas", "pipes": "Stormwater_Pipe",
          "catchpits": "Stormwater_Catchpit", "manholes": "Stormwater_Manhole_And_Chamber",
          "connections": "Stormwater_Connection"}


def request(url, params):
    for attempt in range(4):
        response = requests.get(url, params=params, timeout=45)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 3:
                time.sleep(min(2 ** attempt, 8))
                continue
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"ArcGIS error {payload['error'].get('code')}: {payload['error'].get('message')}")
        return payload
    raise RuntimeError("retry budget exhausted")


def metadata(service):
    return request(BASE + service + "/FeatureServer/0", {"f": "pjson"})


def discover():
    folder = Path("data/raw/metadata")
    folder.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, service in LAYERS.items():
        try:
            payload = metadata(service)
            path = folder / (name + ".json")
            path.write_text(json.dumps(payload, indent=2))
            report[name] = dict(status="available", url=BASE + service + "/FeatureServer/0",
                                name=payload.get("name"), geometry=payload.get("geometryType"),
                                spatial_reference=payload.get("extent", {}).get("spatialReference"),
                                fields=payload.get("fields"), query_formats=payload.get("supportedQueryFormats"),
                                capabilities=payload.get("advancedQueryCapabilities"),
                                max_records=payload.get("maxRecordCount"),
                                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                coverage_at_target="not_assessed", vertical_datum="unverified")
        except Exception as error:
            report[name] = dict(status="blocked", reason=str(error))
    manifest = dict(timestamp=datetime.now(timezone.utc).isoformat(), actual_public_metadata=True, layers=report)
    Path("data/manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def fetch_bbox(service, bbox, session_request=request):
    if len(bbox) != 4 or not bbox[0] < bbox[2] or not bbox[1] < bbox[3]:
        raise ValueError("ordered NZTM metre bbox required")
    if (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) > 100_000_000:
        raise ValueError("bounded local query only (maximum 100 km²)")
    url = BASE + service + "/FeatureServer/0/query"
    common = dict(f="json", geometry=",".join(map(str, bbox)), geometryType="esriGeometryEnvelope",
                  inSR=2193, spatialRel="esriSpatialRelIntersects", where="1=1")
    ids = session_request(url, dict(common, returnIdsOnly="true")).get("objectIds")
    if ids is None:
        raise RuntimeError("Object-ID enumeration unavailable; refusing potentially truncated data")
    ids = sorted(set(ids))
    features = []
    for offset in range(0, len(ids), 200):
        batch = ids[offset:offset + 200]
        page = session_request(url, dict(f="json", objectIds=",".join(map(str, batch)), outFields="*", outSR=2193))
        if page.get("exceededTransferLimit") or len(page.get("features", [])) != len(batch):
            raise RuntimeError("incomplete object-ID batch")
        sr = page.get("spatialReference", {})
        if sr.get("latestWkid", sr.get("wkid")) != 2193:
            raise RuntimeError("response CRS was not EPSG:2193")
        features.extend(page["features"])
    return dict(spatialReference={"wkid": 2193}, features=features,
                zero_result_caveat="No features returned is not proof of no assets/flooding" if not ids else None)
