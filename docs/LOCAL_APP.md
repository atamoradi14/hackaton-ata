# Auckland FlowLab local web app

Start from the project root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-app.ps1
```

Open **http://localhost:8765**. The launcher installs the exact Leaflet dependency
from `web/package-lock.json` if missing, starts the WSL scientific backend in a
hidden process and checks readiness through a proxy-bypassed loopback request.
It reuses an already-running Auckland FlowLab instance. It does not change execution
policy globally, install a public service or publish site data.

To stop only this project's app:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-app.ps1
```

The stop script checks Linux process arguments, owning user and resolved project
working directory. To run in the foreground instead, use
`scripts/floodtwin.ps1 serve --port 8765`.

## Address → review → confirm → prepare

Enter the **street number and full street, suburb, city**. The current resolver
requires an unambiguous official LINZ match and a single point-covering primary
parcel; it does not guess coordinates for partial or ambiguous addresses.
Search reads/geocodes only the address and parcel. The existing official match
can be read from recorded local artifacts. The highlighted parcel and point are
displayed for review before a preparation job exists.

**Confirm & prepare** authorizes that exact reviewed address. The backend checks
the candidate identifier, address and explicit confirmation. It saves the audit
timestamp and starts an isolated `data/web-sites/<id>/` workspace. Neither edits
to the input nor another tab can replace its site manifest. Changing the input
clears the previous visible result and requires another search/confirmation.
Refreshing the same tab restores its previously confirmed workspace.

After confirmation the app automatically prepares supported, bounded data:
Council GIS; official building footprints; spatial survey coverage; aligned
bare-earth DEM/DSM; native LiDAR crop; ground/DEM consistency and profiles;
terrain-derived connectivity screening; terrain preview and evidence report.
Previously prepared data are reused only when **both address ID and parcel ID**
match, with a visible `recorded` status. Other inputs use actual provider
requests in separate subprocess workspaces. No global process working directory
is changed. Logs are private, with supplied provider keys redacted.

The registered elevation/point-cloud workflow currently supports the verified
2024 Auckland Part 1 survey. Other coverage or changed metadata is reported as
blocked for review. Provider failures remain visible; independent available
data can still be prepared. An interrupted server marks incomplete work as
interrupted, rather than continuing a fictitious progress indicator.

## Explore and export

Pan/zoom/recenter, switch light/dark basemap rendering and toggle official
buildings, mapped flow paths, drainage assets, Council flood areas and ground
elevation. The OpenStreetMap basemap needs internet, proper attribution and normal
interactive tile access; no bulk tile downloading occurs. Parcel/GIS rendering
uses actual local geometry. Map geometry is simplified by 0.25 m for display;
the ground overlay is a 512-pixel display derivative. Neither creates new
measured resolution or changes the 1 m source terrain.

Terrain cross-sections are interactive; the 3D terrain tab shows the actual
ground-only preview with its documented display sampling/exaggeration. The
source tab exposes provenance JSON and actual GeoTIFF, LAZ, CSV and GeoJSON
downloads. The source layers and terrain screening are not hydraulic water
motion, and cadastral outlines are not measured fences.

The **Solver lab** is a separate, clearly labelled synthetic demonstration using
the existing validated SFINCS NetCDF histories. Choose open, finite-weir or
infinite-barrier cases, then play/scrub actual sampled times and inspect upstream
and downstream levels. History hashes must match numerical validation before
the lab loads. The diagram represents synthetic compartment means, not the
selected property, a measured wall or a direct transient-discharge validation.

## Real site model gate

Confirmation starts data preparation, not an unsupported design-storm run.
The app visibly records `Site hydraulics: Not run`, and the simulation-input
panel lists real HIRDS rainfall, connected domain/outlet conditions and reviewed
roughness/loss/building/barrier/drainage assumptions. No rainfall or asset
capacity is invented. Site `simulate`, hydraulic comparisons and a full editable
barrier/network model remain later milestones. The HIRDS link is an external
access guide; the app does not create an account or submit terms/purpose.

The service binds only loopback, rejects unexpected Host/Origin values, checks
a per-process session token for POSTs and exposes an explicit artifact allowlist.
Actual `.env`, raw credentials, arbitrary filesystem paths and unconfirmed job
exports cannot be served. Keys remain in the inherited backend environment;
the browser receives no LINZ/OpenTopography API key. Data and screenshots stay
Git-ignored. This is a private local research app, not a public multi-user service.

## Verification

```powershell
npm --prefix web ci --ignore-scripts
npm --prefix web run check
```

Backend tests run with `micromamba run -n floodtwin pytest -q` in WSL.
Browser QA uses the Playwright CLI and stores private screenshots under
`output/playwright/`. See `PROGRESS.md` for executed checks and coverage limits.
