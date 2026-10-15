"""Bounded preliminary GIS acquisition, explicitly not a hydraulic domain."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .council import LAYERS, BASE, metadata, fetch_bbox


def fetch_discovery():
    site_path = Path("data/processed/site/site_manifest.json")
    site = json.loads(site_path.read_text())
    if not site.get("user_visual_confirmation"):
        raise RuntimeError("Property visual confirmation required")
    x, y = site["nztm"]
    bbox = [x-1000, y-1000, x+1000, y+1000]
    folder = Path("data/raw/council-discovery")
    folder.mkdir(parents=True, exist_ok=True)
    processed = Path("data/processed/site")
    reports = {}
    fig, ax = plt.subplots(figsize=(9, 9))
    styles = {"overland_flow": "#087f8c", "pipes": "#4b579e", "catchpits": "#c18b13"}
    for name, service in LAYERS.items():
        try:
            meta = metadata(service)
            payload = fetch_bbox(service, bbox)
            payload.update(geometryType=meta["geometryType"], fields=meta["fields"])
            encoded = json.dumps(payload).encode()
            digest = hashlib.sha256(encoded).hexdigest()
            raw = folder / (name + "-" + digest + ".json")
            if not raw.exists():
                raw.write_bytes(encoded)
            count = len(payload["features"])
            report = dict(status="available" if count else "available_empty", count=count,
                          source=BASE + service + "/FeatureServer/0", horizontal_crs="EPSG:2193",
                          vertical_datum="unverified; no asset levels used in hydraulics",
                          provenance_status="official_map", copyright=meta.get("copyrightText"),
                          license="check provider terms before redistribution", editing_info=meta.get("editingInfo"),
                          raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                          zero_result_caveat=payload.get("zero_result_caveat"))
            if count:
                frame = gpd.read_file(raw, driver="ESRIJSON")
                if frame.crs is None or frame.crs.to_epsg() != 2193:
                    raise ValueError("Decoded GIS CRS mismatch")
                report.update(invalid_geometries=int((~frame.geometry.is_valid).sum()),
                              empty_geometries=int(frame.geometry.is_empty.sum()),
                              duplicate_geometries=int(frame.geometry.to_wkb().duplicated().sum()))
                frame.to_file(processed / (name + ".gpkg"), driver="GPKG", layer=name)
                if name in styles:
                    frame.plot(ax=ax, color=styles[name], linewidth=0.7, markersize=5, label=name)
            reports[name] = report
        except Exception as error:
            reports[name] = dict(status="blocked", reason=str(error))
    parcel = gpd.read_file(processed / "parcel.geojson").to_crs(2193)
    parcel.boundary.plot(ax=ax, color="#c4322b", linewidth=2)
    ax.scatter([x], [y], color="#c4322b", s=30)
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.set_title("Official GIS discovery window — not a hydraulic simulation\nCouncil flow paths are mapped screening lines; domain not selected")
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.set_xlabel("NZTM easting (m)"); ax.set_ylabel("NZTM northing (m)")
    fig.tight_layout(); fig.savefig(processed / "gis-discovery.png", dpi=150); plt.close(fig)
    result = dict(timestamp=datetime.now(timezone.utc).isoformat(), discovery_bbox_nztm=bbox,
                  final_hydraulic_domain=False, actual_public_data=True, layers=reports,
                  caveats=["Discovery window only; upstream/downstream continuity not yet assessed",
                           "Asset geometry is indicative; pipe connectivity/inverts not verified",
                           "No flood-risk inference from mapped lines or zero query results"])
    (processed / "gis-discovery-manifest.json").write_text(json.dumps(result, indent=2))
    return result
