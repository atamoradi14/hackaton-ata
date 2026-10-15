"""Official order-file API. Catalogue metadata is not a rainfall hyetograph."""
import csv
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE = "https://d17fc0a885.execute-api.ap-southeast-2.amazonaws.com/dev/api/data-files"


def api(identifier=None, page=1):
    customer, key = os.environ.get("DATAHUB_CUSTOMER_ID"), os.environ.get("DATAHUB_API_KEY")
    if not customer or not key:
        raise ValueError("Set private DATAHUB_CUSTOMER_ID and DATAHUB_API_KEY")
    if identifier and not re.fullmatch(r"[a-f0-9]{24}", identifier):
        raise ValueError("Select an order file ID returned by DataHub")
    try:
        response = requests.get(BASE + ("/"+identifier if identifier else ""),
            headers={"X-Customer-ID": customer, "Authorization": "Bearer " + key, "Accept": "application/json"},
            params={"includeMetadata": "true", **({"page": page, "limit": 50} if not identifier else {})}, timeout=40)
    except requests.RequestException:
        raise ValueError("DataHub connection failed; private headers are not displayed") from None
    if not response.ok:
        raise ValueError(f"DataHub returned HTTP {response.status_code}; check account credentials and approved orders. No credentials or response body displayed.")
    result = response.json()
    if identifier:
        return result
    # Only metadata; never expose signed download URLs or credentials.
    return {"files": [{"id": f.get("id"), "name": f.get("fileName"), "metadata": f.get("metaData", {})} for f in result.get("data", [])],
            "pagination": result.get("pagination", {})}


def download(identifier, root=Path("data/raw/rainfall")):
    record = api(identifier)
    url = record.get("presignedUrl", "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".amazonaws.com"):
        raise ValueError("DataHub did not return a supported HTTPS S3 download URL")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    name = Path(record.get("fileName", identifier)).name
    if name in {"", ".", ".."}:
        raise ValueError("Invalid file name")
    destination = root / (identifier + "-" + name)
    with requests.get(url, stream=True, timeout=60) as response:
        if not response.ok:
            raise ValueError(f"Private file download failed with HTTP {response.status_code}")
        with destination.open("wb") as output:
            size = 0
            for part in response.iter_content(1024*1024):
                size += len(part)
                if size > 100*1024*1024:
                    raise ValueError("Download exceeds the bounded 100 MiB limit")
                output.write(part)
    import hashlib
    provenance = dict(id=identifier, file=destination.name, bytes=size, sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                      source="ESNZ DataHub approved order file API", rainfall_ready=False,
                      next_step="Inspect site, units, scenario and durations; choose and review a temporal pattern.")
    destination.with_suffix(destination.suffix+".json").write_text(json.dumps(provenance, indent=2))
    return provenance


def inspect_catalog(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if not {"productRef", "duration", "ari", "region"}.issubset(fields):
            raise ValueError("Not a HIRDS catalogue export; a site rainfall table needs a different parser")
        rows = list(reader)
    selected = [row for row in rows if row["region"].casefold() == "auckland"]
    return dict(kind="catalogue_metadata", rainfall_ready=False, total_rows=len(rows), auckland_rows=len(selected),
                durations_minutes=sorted({float(row["duration"]) for row in selected if row["duration"]}),
                ari_years=sorted({float(row["ari"]) for row in selected if row["ari"]}),
                reason="No site rainfall depth/intensity values. Grid catalogue describes 2000 m regional products.")
