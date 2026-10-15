"""Build a private local report from actual recorded artifacts only."""
import html
import json
from pathlib import Path

folder = Path("data/processed/site")
site = json.loads((folder / "site_manifest.json").read_text())
gis = json.loads((folder / "gis-discovery-manifest.json").read_text())
terrain = json.loads((folder / "terrain-qc.json").read_text())
cloud = json.loads((folder / "pointcloud-manifest.json").read_text())
ground = json.loads((folder / "ground-dem-qc.json").read_text())
screen = json.loads((folder / "domain-screening.json").read_text()) if (folder / "domain-screening.json").exists() else None
rows = "".join(f"<tr><td>{html.escape(name)}</td><td>{layer.get('count','—')}</td><td>{layer.get('invalid_geometries','—')}</td><td>{html.escape(layer['status'])}</td></tr>" for name,layer in gis["layers"].items())
body = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Private site preparation report</title>
<style>body{{font:16px system-ui;line-height:1.6;max-width:1100px;margin:40px auto;padding:0 20px;color:#203441}}h1,h2{{line-height:1.25}}img{{max-width:100%}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;text-align:left;border-bottom:1px solid #ccd6dd}}.notice{{background:#fff1cd;padding:18px;border-left:5px solid #b98b16}}a{{color:#006875}}</style>
<h1>{html.escape(site['address'])}</h1><p>Private research preparation report. Official LINZ address {site['address_id']}, parcel {site['parcel_id']}; user-confirmed.</p>
<div class="notice"><b>Site hydraulics have not been run.</b> HIRDS rainfall is unavailable. A connected model domain, verified outlet/boundary assumptions, loss/roughness scenarios and reviewed structures are still needed. These maps and profiles do not establish property flood risk.</div>
<h2>Development environment</h2><p>The full validation command passed: WSL geospatial roundtrips, real SFINCS rain-tank/dry controls, QGIS, CloudCompare, read-only GitHub and Playwright MCP, Docker tooling and optional SWMM import. See PROGRESS.md and reports/full-environment-validation.log.</p>
<h2>Official GIS discovery</h2><p>2 km × 2 km preliminary data window; it is not the final model domain. Invalid geometries remain flagged and require review.</p>
<table><tr><th>Layer</th><th>Features</th><th>Invalid geometry flags</th><th>Status</th></tr>{rows}</table><img src="gis-discovery.png" alt="Actual mapped Council assets and flow-path screening lines">
<h2>Actual 2024 Part 1 terrain</h2><p>Aligned 1 m DEM/DSM in EPSG:2193 and NZVD2016. Both crops have {terrain['layers']['dem']['nodata_fraction']:.2%} and {terrain['layers']['dsm']['nodata_fraction']:.2%} nodata respectively.
{terrain['layers']['height_flags']['negative_height_cells']} cells have DSM minus DEM below −0.2 m and remain QC flags. No wall/fence geometry or crest height is assigned automatically.</p>
<img src="terrain-preview.png" alt="Actual DEM and above-ground heights"><img src="terrain-3d.png" alt="Actual ground-only 3D DEM preview, with declared visual decimation">
<h2>Point-cloud and profile QC</h2><p>{cloud['crop_point_count']:,} points cropped to a 200 m square. Compound CRS verified from LAS headers; source noise/withheld/overlap flags are preserved. {cloud['noise_points']:,} classified noise points and {cloud['withheld_points']:,} withheld points are flagged.
Ground/DEM comparison used {ground['compared_ground_points']:,} non-withheld class-2 points from the same survey. This is a consistency check, not independent accuracy validation.</p>
<img src="ground-dem-qc.png" alt="Ground-minus-DEM comparison and real terrain profiles">
<p><a href="terrain-cross-sections.csv">Download real terrain profile CSV</a> · <a href="terrain-qc.json">Terrain provenance and QC</a> · <a href="pointcloud-manifest.json">Point-cloud provenance</a></p>
<h2>Domain screening</h2>'''
if screen:
    body += '<p>D8 topographic connectivity only, with preserved local pits. No verified outlet or final hydraulic domain.</p><img src="domain-screening.png" alt="Non-hydraulic D8 terrain screening"><p><a href="domain-screening.json">Screening assumptions and boundary flags</a></p>'
else:
    body += '<p>Screening still pending; no domain assigned.</p>'
body += '<h2>Source acknowledgements</h2><p>LINZ, Woolpert and Regional Software Holdings Limited (CC-BY-4.0); OpenTopography, DOI <a href="https://doi.org/10.5069/G9HH6H8T">10.5069/G9HH6H8T</a>. Auckland Council mapped layers remain subject to provider terms. No private inputs or credentials were published.</p></html>'
(folder / "overview.html").write_text(body,encoding="utf-8")
print("Private overview saved to data/processed/site/overview.html")
