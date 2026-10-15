"""Local plot of the actual official parcel and address point, no hydraulic overlay."""
from pathlib import Path
import json
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path("data/processed/site")
manifest = json.loads((root / "site_manifest.json").read_text())
confirmation = "User confirmed intended property" if manifest.get("user_visual_confirmation") else "User visual confirmation pending"
parcel = gpd.read_file(root / "parcel.geojson").to_crs(2193)
point = gpd.read_file(root / "address.geojson").to_crs(2193)
fig, ax = plt.subplots(figsize=(8, 7))
parcel.plot(ax=ax, facecolor="#dceaf0", edgecolor="#244b63", linewidth=2)
point.plot(ax=ax, color="#c4322b", markersize=60)
ax.set_title(f"Official LINZ address point and primary parcel\n{confirmation}; no flood result")
ax.set_xlabel("NZTM2000 easting (m)")
ax.set_ylabel("NZTM2000 northing (m)")
ax.ticklabel_format(style="plain", useOffset=False)
fig.tight_layout()
fig.savefig(root / "parcel-review.png", dpi=150)
lon, lat = manifest["lonlat"]
html = f'''<!doctype html><html><meta charset="utf-8"><title>Local site review</title>
<body style="font:17px system-ui;max-width:950px;margin:40px auto"><h1>{manifest['address']}</h1>
<p>Exact official address ID {manifest['address_id']}; point-covering parcel {manifest['parcel_id']}.
{confirmation}. No terrain elevation, hydraulic domain or flood-risk assessment is implied.</p>
<img src="parcel-review.png" style="width:100%" alt="LINZ parcel with official address point">
<p>LINZ CC-BY-4.0. Coordinates: latitude {lat:.8f}, longitude {lon:.8f}.</p>
<p><a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}">Review location on OpenStreetMap</a></p>
<p>Parcel boundaries are not surveyed fence locations. The red point identifies the official address location.</p></body></html>'''
(root / "review.html").write_text(html)
print("Local site review saved to data/processed/site/review.html")
