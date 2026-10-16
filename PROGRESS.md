# Progress

## WP0 in progress
Read AGENTS.md, CODEX_MASTER_PLAN.md, SOURCES.md and config.example.yaml in full.
Archive initially contains specifications only; no existing code or Git repository.
Verified Windows build 26200 (64-bit), WSL2 Ubuntu-24.04, Docker Desktop Linux engine
29.8.2. Native Python 3.14 is isolated from the scientific environment.
WSL has Python 3.12.3 and micromamba 2.9.0 installed in the user profile.

Task sequence: environment solve/install -> doctor -> real synthetic SFINCS
numerical checks -> public metadata discovery -> verified address/parcel gate ->
terrain, site hydraulics, scenarios and UI as inputs become available.

Selected released HydroMT-SFINCS 1.2.2 requires HydroMT >=0.10.1,<1.0;
the GitHub main branch has a different HydroMT >=1.3 API and must not be mixed.
Python 3.11 / conda-forge native libraries are the initial compatibility candidate,
pending dependency resolution and numerical validation.
## WP0 completed — 14 October 2026 (Pacific/Auckland)

Executed `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1`:
PASS, including six offline tests, CRS and GeoTIFF roundtrips, real LAZ/PDAL
processing, two SFINCS runs, QGIS CLI startup, CloudCompare CLI startup,
Playwright MCP initialize/tools/browser snapshot, GitHub MCP authenticated
read-only `get_me`, Docker tooling doctor and optional SWMM native import.
Logs: `reports/full-environment-validation.log`; `runs/synthetic/validation.json`.

Verified backend versions: Python 3.11.17; GDAL 3.10.3; Rasterio 1.4.3;
GeoPandas 1.1.4; Affine 2.4.0; PDAL core 2.8.4 / Python binding 3.4.5; laspy 2.6.1;
HydroMT 0.10.1; HydroMT-SFINCS 1.2.2; NumPy 1.26.4; Pandas 2.2.3;
xarray 2024.11.0. SFINCS 2.4.0 release pinned by digest. Native QGIS LTR
3.44.14 installed/started; CloudCompare 2.13.2 installer completed and CLI
started with exit 0. SWMM toolkit 0.16.2 / engine 5.2.4 installed separately.

Synthetic rain tank: 100 cells of 100 m² each, 36 mm/hr for 600 s;
analytical depth 0.006 m; observed maximum 0.006000000052154064 m;
stored volume 59.99999642372131 m³; relative error 5.960464465696684e-8
(acceptance <=0.01). Dry control: all 100 point histories zero; volume zero.
Both solvers exit 0. Solver map dry values are documented masked outputs,
not NaN instability: all-cell observation histories verify the dry case.
This fixture establishes conservation and dry control only, not site accuracy,
boundary convergence, calibration, barrier overflow or drainage coupling.

Reproducibility: `locks/conda-linux-64.lock` (230 exact builds) and
`locks/pip-linux-64.lock` (60 PyPI versions). Restored into an independent
`floodtwin-restored` environment; `pip check` and doctor passed.
Docker Compose tools image built and tested; solver and optional PostGIS images
pinned by digest. PostGIS configured but not initialized (private password gate).

Installation findings resolved: initial Conda Arrow/PDAL conflict, `lazrs-python`
package naming, Pandas 3 time alias incompatibility, explicit model index filename,
HydroMT observation catalogue lookup, dry-map wetting threshold and lock export
format. No hidden solver fallback. Scientific fixture is offline after image pull.

GitHub MCP reuses existing GitHub CLI keyring without saving/printing a token;
read-only server v2.0.2. Playwright MCP 0.0.83 uses a pinned alpha Playwright
runtime (1.64.0-alpha-1790635538000), verified by a synthetic browser roundtrip.
MCP project config needs host reload/project trust to appear in a new session.

Credential incident: LINZ schema embedded the supplied key in a URL and one tool
preview exposed it. Local caches are redacted; `.env` stays ignored. Rotate key.

## WP1 / preliminary WP2 in progress

Executed official LINZ WFS schema introspection and exact-address query.
One match: address ID 1030654, point-covering primary parcel 5180797.
Saved private GeoJSON, SHA256 provenance and local review plot. User visually
confirmed intended property on 14 October 2026. No elevations assigned to
address or parcel geometry. `configs/local_site.yaml` records confirmation.

All seven public Council layer metadata endpoints available; actual property
coverage was queried separately in a bounded 2 km × 2 km preliminary discovery
window; it is explicitly NOT a final hydraulic domain.

LINZ STAC capture-area polygons and published checksums inspected for all four
Auckland 2024 DEM/DSM collections: Part 1 covers official address; Part 2 does
not. Exact raster tile coverage is now checked below.

User has no HIRDS export yet. Real design-storm/site simulation is blocked until
site rainfall, selected connected domain, terrain datum/coverage and reviewed
parameter assumptions are available. Continue bounded GIS/terrain preparation.

## Bounded GIS / terrain preparation completed

Executed `floodtwin fetch-discovery`, `prepare-terrain-discovery`,
`fetch-pointcloud`, `screen-domain`, `scripts/fetch-buildings.py`,
`scripts/site-qc.py`, `scripts/terrain-3d.py` and `scripts/site-overview.py`.
Actual local artifacts and private HTML overview are in `data/processed/site/`.

Council counts: 830 overland-flow lines; 10 flood plains; 19 flood-prone areas;
1,786 pipes; 395 catchpits; 1,008 manholes/chambers; 223 connections.
All decoded CRS values verified as EPSG:2193. One invalid flood-prone polygon
is flagged/preserved for review. No unknown asset elevations or capacities used.
Official LINZ building query paginated to 3,464 footprints, no invalid geometries;
building height and entry thresholds remain unassigned/not assessed.

DEM and DSM: only HTTP range windows from spatially intersecting actual STAC
tiles BA31_10000_0304 and BA31_10000_0305. Aligned original 1 m grids, both
zero nodata within the 2001 × 2001 crop. Verified NZVD2016 using official LINZ
layer metadata (121990 DEM / 121992 DSM); no vertical conversion applied.
Full remote-tile checksum is recorded but not claimed verified for partial
downloads. Each local crop has its own SHA256. 419 cells with DSM-DEM < -0.2 m
remain QC flags; no automatic walls assigned. Official survey vertical accuracy
specification is ±0.2 m at 95%, not independently validated at this property.

Point cloud: official tile index 121993 selected BA31_1000_2541/2542. Only two
local source LAZ tiles acquired from OpenTopography's public unsigned endpoint
(21,568,123 and 46,816,299 bytes). Lossless 200 m crop has 526,437 points;
PDAL and laspy counts agree. LAS compound CRS verifies EPSG:2193 + 7839.
7,333 noise/withheld points and 2,834 overlap points preserved and flagged.
OpenTopography key is stored privately but unused/unvalidated for this pathway.
CloudCompare opened the real cropped LAZ successfully with automatic display
origin shift; the raw coordinates/inputs are unchanged.

Ground consistency QC used 120,510 class-2 non-withheld points. Median
point-minus-DEM = -0.0022503 m; 5th/95th percentiles = -0.1522494 / 0.1499992 m;
RMSE = 0.1028577 m. Same-survey comparison is NOT independent accuracy validation.
Cross-sections CSV, actual terrain-only 3D preview and QA figures saved and viewed.
The 3D view samples original 1 m data every 2 m for display, with labelled
visual vertical exaggeration; it contains no synthetic water surface.

D8 terrain screen: 4,839 m² possible contributing area, 74 downstream terrain
traces, no verified outlet and no final hydraulic domain. Local pits retained;
buildings, barriers, drains, dynamic overflow and receiving-water heads ignored
by this SCREENING ONLY calculation. It cannot establish storm continuity or risk.
Initial max_depth=0 stalled due to pyflwdir's self-neighbour comparison; own test
process terminated. Explicit 1e-6 m numerical tie tolerance resolves this without
changing source DEM. Affine 3 also failed the compiled metre-path API; pinned
Affine 2.4.0, regenerated exact locks, independently restored and rebuilt Docker.
Eight offline tests pass, including known synthetic 64 m² connectivity and
nodata rejection; the real site screening then ran successfully.

Real SFINCS binary SHA256:
`72b05c4922ef12c686ea6ea17654ccaf7dad292118d71126b22e5432d8c5cacf`.
Latest synthetic rain solver total runtime 0.525 s, average timestep 0.5 s;
peak per-process RAM/CPU not separately instrumented. Figures were inspected.

Final lock audit found duplicate Pandas prefix records after the earlier pip
downgrade/Conda reinstall: runtime was 2.2.3 but the export selected stale 3.0.6.
Quarantined the stale record into ignored diagnostics, force-reinstalled Conda
Pandas 2.2.3 and added duplicate-record rejection to the lock exporter. New lock
uses the actual 2.2.3 build. Removed/recreated only this task's disposable restore
environment; fresh restore now passes explicit Pandas/Affine API checks.

Windows Update installed WSL 3.0.3 during final checks (MSI success recorded;
temporary 1618 installer contention observed). Kernel changed to 6.18.54.1-1;
Ubuntu resumed and Docker Desktop restarted through its CLI. Final integrated
validation PASSED after rebuilding the corrected locked image: eight tests,
both real SFINCS runs, native tools, MCP authenticated/browser checks, Docker
tooling and optional SWMM. Docker's doctor now verifies Pandas 2.2.3 and Affine
2.4.0 explicitly; fresh restore passes the same API compatibility gate.
The staged-file audit also found a supplied OpenTopography key in `.env.example`;
cleared template values and reran the credential scan successfully. Actual keys
remain only in ignored `.env`; no secrets were committed.

## Next external/scientific gates

Official HIRDS endpoint now redirects to Earth Sciences NZ DataHub and requires
an account and declared purpose. User confirmed no account/credentials yet.
See `docs/HIRDS_ACCESS.md`; no account created, no terms/purpose submitted on
the user's behalf, and no rainfall values invented. User's LINZ/OpenTopography
keys remain Git-ignored in `.env` and cannot authenticate this separate service.

Next: obtain real DDF tables; choose/document hyetograph and durations; review
connected upstream/downstream hydraulic domain, receiving-water/outlet heads,
roughness/losses, building treatment, barrier measurements and drainage scenarios.
Only then construct/run a real site model and test domain/boundary convergence.
No site hydraulic baseline, reviewed wall scenarios, SWMM coupling, full UI or
property flood-risk verdict has been claimed. Current code repository is local
and private; no remote publishing or large raw data staging.

## WP10 offline hydraulic quality milestone — 14 October 2026

Continued from local environment/site-preparation commit `5fb91b0`. Re-read
AGENTS.md, master plan, SOURCES.md and example config before implementation.
HIRDS account/export remains missing; this milestone uses exclusively synthetic
terrain, initial water levels, wall geometry and roughness, with the real pinned
SFINCS 2.4.0 executable. No site rainfall or wall measurements were invented.

Implemented `floodtwin synthetic-quality run|validate --root <directory>` and
added the eight-case suite to `scripts/validate-wsl.sh` / `validate.ps1`.
Runs require a new directory, save input/output hashes, solver exits/logs/version,
wall time, adaptive timestep, all-cell histories, mass balances and a clearly
labelled synthetic HTML/PNG comparison. Validation rejects incomplete histories,
nonfinite/negative states, nonfinite velocities, changed files and failed exits.

Executed `scripts/floodtwin.ps1 synthetic-quality run --root runs/quality-20261014-c`
and independently revalidated saved outputs. All eight cases PASS: sloping-bed
hydrostatic still water; downslope redistribution; open head-driven channel;
finite weir overflow; below-crest finite-weir control; explicitly infinite barrier;
1 m vs 2 m cell refinement; 0.25 s vs 0.5 s maximum timestep sensitivity.
One-hour closed-tank runs, 10-second histories, 100 cells (400 in fine repeat).
Original rain/dry tests are retained separately. Thirteen offline tests pass,
including transient mass-drift detection, invalid states and equivalent initial
storage at both resolutions.

Quantitative evidence: maximum all-time relative volume error across cases
5.96e-8 against declared 0.005 tolerance. Finite-weir downstream storage gain
39.97755 m³; upstream/downstream final means 0.400112/0.299888 m; open case
0.348677/0.351323 m. Below-crest/infinite cases retain their initial heads.
Largest compartment-mean difference over the full sampled series: 0.00032967 m
for cell refinement, 0.00011465 m for timestep repeat (tolerance 0.02 m).
Recorded adaptive average timesteps 0.25 s / 0.249 s / 0.125 s; per-case process
wall time 8.1–11.9 s, including Docker startup. Peak CPU/RAM not instrumented.
Same 230-build Conda and 60-version pip locks used; Docker tooling rebuilt.

Initial trial issues retained in ignored run logs: a relative launch directory
failed on the second Docker invocation (getcwd/mount-source error); changed the
runner to resolve absolute paths before launching. Subsequent full eight-case
run succeeded. Sudden open-channel initial heads had residual waves at 600 s
and 1800 s; extended settling time to 3600 s instead of relaxing the predeclared
5 mm per-cell equilibrium tolerance. The one-hour case passes. This is a
local-inertial regression fixture, not analytical transient dam-break validation.

Inspected `runs/quality-20261014-c/comparison.png` and generated HTML report.
These closed boundaries isolate internal fluxes: no open-boundary outflow,
rainfall/loss/drainage coupling, real site domain convergence or calibration is
established by this suite. No engineering accuracy claim. Methods and thresholds:
`docs/HYDRAULIC_VALIDATION.md`.

Code/docs milestone commit: `fdac1f6`. Executed the updated
`powershell -ExecutionPolicy Bypass -File scripts/validate.ps1`, exit 0 / PASS.
Log: `reports/full-environment-validation.log`. Thirteen tests, original rain/dry
runs plus all eight quality runs, QGIS, real-LAZ CloudCompare, both MCP checks,
rebuilt Docker tooling and optional SWMM native engine all passed together.
Independent full-command quality run:
`runs/quality-20261013T125613-2235/validation.json` (UTC-named output folder).
API keys, actual `.env`, private site config and numerical outputs remain ignored;
staged credential scan passed. No remote push or account registration performed.
Next scientific gates remain real HIRDS inputs, connected domain/outlet review,
roughness/loss and building treatment, measured/reviewed barriers and drainage
assumptions. The actual property has not been hydraulically simulated.

## WP9 local interactive app milestone — 14 October 2026

Implementation commit: `34b8a67`. Final local HTTP readiness returned 200 after
the owned QA browser closed; the app service remains available to the user.

Implemented Tidewise, a private local browser app at `http://localhost:8765`,
with the Sites local-only workflow and Playwright CLI browser QA. No hosted
publication, remote repository, external account creation or private data upload.
Frontend Leaflet 1.9.4 is exact-pinned with npm integrity lock; Node 24.20.0 /
npm 11.19.0 verified. The loopback Python backend uses the existing scientific
environment and standard-library HTTP server; no new scientific dependency mix.

Implemented address input -> exact official point/parcel review -> explicit
confirmation -> automatic supported data preparation in isolated workspaces.
Searching performs only geocoding/parcel lookup. No data preparation job exists
until the backend verifies candidate ID, matching address and explicit approval.
Confirmation timestamp/request ID is recorded privately. Prior confirmation
does not authorize a newly searched candidate. Cached artifacts are reused only
for matching address AND parcel IDs, with visible `recorded` status. Changed
input clears visible metrics/layers/exports and requires a new confirmation.
No global process cwd changes; provider commands run with argument arrays in
separate per-site subprocess directories, inheriting keys privately.

Implemented actual interactive GIS layer toggles, pan/zoom/recenter, light/dark
OpenStreetMap display, parcel point, terrain overlay with actual percentile
legend, DEM profiles with inspection, real terrain-only 3D preview, provenance
JSON and GeoTIFF/LAZ/CSV/GeoJSON downloads. View derivatives use 0.25 m geometry
simplification and 512-pixel raster rendering only; originals retain source
resolution/datum. Mapped flood areas/flow paths are explicitly non-hydraulic.
The separate synthetic solver lab plays/scrubs actual SFINCS observation data
for open, finite-weir and infinite-barrier cases. History hashes must match the
existing passed quality validation before exposure; no fake site water overlay.

Executed `npm --prefix web run check`: PASS. Executed WSL `pytest -q`: **23 passed**,
including source dependency/native geospatial tests, confirmation enforcement,
address mismatch rejection, workspace isolation, idempotence, unconfirmed
export refusal, Host/Origin/session-token checks, private-file refusal,
truthful interrupted-job state and missing-terrain failure without borrowing
another site's artifacts. Numerical solver code/locks were unchanged; no new
site hydraulic run was claimed or performed in this web milestone.

Real Chrome browser QA through Playwright CLI: actual original address/parcel
search and confirmation; automatic recorded-data preparation (all eight steps),
7,735 mapped features / 526,437 points; map toggles, pipe layer and ground
overlay; actual east/north terrain profiles; 3D tab; provenance/export links
(profile CSV HTTP 200); missing-inputs dialog; refresh and restart/restore.
Lab timeline at 3600 s matches actual finite-weir 0.400/0.300 m and infinite
barrier 0.600/0.100 m; open case 0.349/0.351 m. Desktop 1440×1050 and mobile
390×844 inspected. Mobile charts reflow to readable axes; no horizontal overflow
in the measured viewport. Private screenshots: `output/playwright/`.

A live lookup of a second actual address returned distinct official address
and parcel IDs. The previous property's visible evidence cleared before the
lookup. That second property was not confirmed and no preparation job/data
download was triggered for it beyond address/parcel lookup. Invalid input
returns a clear error with no coordinate assignment. All test/site artifacts
remain ignored in `data/`, `reports/`, `output/` and `.playwright-cli/`.

Observed issues resolved: CARTO tiles returned an API-key-required image despite
HTTP 200, caught by screenshot inspection; switched to attributed, normal
interactive OpenStreetMap tiles. Native PowerShell readiness timed out while
the WSL service was running; replaced with proxy-bypassed loopback curl. Added
favicon, response integrity checks, restore race protection and truthful
interruption handling. Checkbox loading initially replaced focused DOM nodes;
kept the input nodes stable and retested successful check/uncheck interactions.
Source whitespace checks and tracked-source credential scan passed. `.env`,
actual keys, node_modules, site workspaces and browser screenshots are excluded.

Started/restarted/stopped only this workspace's app through tested hidden launch
and guarded stop scripts. Final production local app remains running for user
access; the owned QA browser is closed after checks. Instructions/support limits:
`docs/LOCAL_APP.md`. Backend is local-only, not a hosted multi-user service.

Current scientific gates stay visible in the app: HIRDS rainfall/account export,
connected hydraulic domain/outlet heads, reviewed losses/roughness/buildings,
barrier crests and drainage assumptions. Current registered terrain coverage is
Auckland 2024 Part 1; unknown/unsupported survey coverage is blocked, not silently
substituted. Site simulation, editable hydraulic barriers, scenario comparison
and SWMM coupling remain later milestones. Confirmation automatically prepares
supported evidence; it cannot replace missing scientific inputs or calibration.

## Own-node Caddy/Compose deployment — 14 Oct 2026

Implementation commit: `7462ec1`. Prepared `compose.production.yaml`, pinned
Caddy, HTTPS/bcrypt login, explicit public Host/Origin validation, unexposed
backend port, non-root/read-only app with writable named volumes, resource/job
limits, healthchecks and rotating container logs. Included exact locked
geospatial dependencies, packaged Leaflet and the official SFINCS 2.4 binary
with isolated released ELF libraries and binary checksum verification. No Docker
socket, nested Docker daemon or node-native Conda/Python installation is needed.
Added Linux launch/validation/backup scripts, names-only env checks, optional
PostGIS profile, existing-container-Caddy network override and deployment guide.
Preserved explicit per-address confirmation and scientific input gates.

Verification completed:
- Final image built: `sha256:cac628b513b23fc2b9fcd0cc520be9f4e22f4c84d6de92f1ce2ac31738334553`.
- WSL locked environment `pytest -q`: **31 passed**; Bash syntax and Git whitespace
  checks passed. Required/optional setting validation, hash quoting, secret-output
  exclusion, HTTPS origin and processing slot failure/release behavior covered.
- `python deploy/test-stack.py`: **14/14 passed**, including mounted env checker,
  Caddy config, actual geospatial doctor in the service, authenticated HTTPS,
  unauthenticated 401, packaged frontend/Leaflet, foreign-origin rejection,
  unconfirmed export gate, private `.env` denial, no backend host port, and data
  survival through container replacement. Local internal TLS CA/test-only login;
  no LINZ access or daryajan.com certificate issuance attempted. Test containers
  stopped and test env removed; test volumes retained for inspection.
- Final image, network disabled, read-only root, dropped capabilities, no new
  privileges, writable temporary cache/run volume: **eight actual SFINCS cases
  passed**. Max relative volume error `5.960464477539063e-08`; finite-crest transfer
  `39.97755229473114 m3`. Resolution/timestep checks passed. Artifacts/logs in
  ignored `reports/production-quality.json`, `reports/production-build.log`,
  `reports/deployment-test/result.json` and Docker validation volumes.
- Existing Caddy override Compose schema validation passed. Actual credential
  scan of tracked/new source passed; actual `.env` and all private outputs remain
  ignored and excluded from build contexts. No remote publishing/pushing occurred.

Resolved runtime differences: Numba and font caches need writable `/tmp` paths
under read-only mounts; Compose exec bypasses Mamba activation, so the final image
sets `/opt/conda/bin` on default PATH. Rechecked actual PDAL/geospatial APIs and
solver numerical outputs after the fix.

Node requirements and missing settings are in `docs/DEPLOYMENT.md`:
`ACME_EMAIL` and `CADDY_PASSWORD_HASH` are missing locally; `LINZ_API_KEY` exists
privately and must be transferred securely into the node's `.env.production`.
DOMAIN defaults to daryajan.com, login defaults to researcher; OpenTopography is
optional and PostGIS password only required if enabled. Node/DNS/firewall/admin
access was not provided; live domain/certificate validation remains a deployment
step for the node owner. This is a shared authenticated research workspace, not
a multi-tenant service. Jobs interrupted by restart require a new confirmation.
HIRDS export/account, site domain/outlet/parameter reviews, true site hydraulics
and SWMM coupling remain pending; synthetic validation is not site flood evidence.

## Live Helsinki Kubernetes deployment — 14 Oct 2026

Verified SSH alias and node UID against the user's `ravand` cluster. Remote
kubectl uses context `default`, with node `ravand-k3s-01` UID
`87614cb1-f141-4c35-92de-9926d0757108`, 2 CPU/4 GB, k3s 1.36.5. Existing
Traefik/ServiceLB were disabled and ports 80/443 free. Changed only dedicated
`tidewise` namespace resources and owned `/opt/tidewise-deploy` files.

Actual image transferred securely and imported into k3s containerd:
`docker.io/library/tidewise-app:k8s-7462ec1`, image index
`sha256:cac628b513b23fc2b9fcd0cc520be9f4e22f4c84d6de92f1ce2ac31738334553`.
Compressed archive SHA-256 matched locally/remotely:
`443391d98a450d00772c55e643f53059c0fdc6da0284a93cb848273906b6f1b1`.
Kubernetes server-side dry-run and live apply passed. App and separate Caddy
Deployments are 1/1 ready; both ClusterIP Services and two PVCs are present/bound.
Caddy host networking owns public 80/443 and proxies to the internal app service.
App limit 2 GiB/1.5 CPU/one worker; Caddy 256 MiB/0.25 CPU. Node stayed Ready.

User supplied certificate contact and confirmed DNS A/Cloudflare Full (strict).
Caddy completed real Let's Encrypt HTTP-01 validation through Cloudflare and
downloaded its trusted daryajan.com certificate. Both public and direct origin
unauthenticated HTTPS checks returned 401. Private provider keys from `.env`
are in namespace Secrets; staging env files were removed from the node. Generated
strong login is saved locally in ignored `reports/k8s-secrets/login.json`, with
only its bcrypt hash in the Caddy Secret. Filled private `.env.production` from
existing keys/user email/hash and node-appropriate limits. All mandatory variables
pass names-only validation; POSTGIS_PASSWORD remains optional/unset.

Live verification: geospatial doctor passed, all **eight real SFINCS synthetic
cases passed on this Kubernetes node**, maximum relative volume error
`5.960464477539063e-08`. Full-activation doctor passed cleanly; direct exec emitted
PROJ search-path warnings, so operator scripts now use the Mamba entrypoint.
**10/10 authenticated public smoke checks passed**: frontend/Leaflet, health,
public bootstrap, actual cached LINZ address 1030654 review, unconfirmed export
gate, foreign-origin rejection, private `.env` denial, 401 protection, and actual
synthetic laboratory outputs. No new site confirmation/preparation was triggered
by smoke tests. The verified private Pemberton cache was scanned for credential
values and transferred securely; each new address still needs confirmation.
Results are ignored `reports/k8s-{doctor,doctor-activated,quality,public-smoke}.json`.
Default Python urllib user agent received Cloudflare 403; a declared deployment
check user agent passed. Curl/public TLS and authenticated app routes passed.

Source credential scan (including both env keys, portal password and bcrypt hash),
shell syntax and whitespace checks passed. No secret/data/image publication or
public repository push occurred. Public outer repository currently has an app Git
link without submodule URL plus ZIP, so it is not a complete source checkout;
deployment uses the tested local image. Operations and requirements are documented
in `docs/KUBERNETES.md`. Node-local PVCs need off-node backups; this is one shared
research login and one node, not a multi-tenant/high-availability installation.
HIRDS export and site hydraulic domain/parameter reviews remain scientific gates.

## Interactive terrain and exploratory site hydraulics — 14 Oct 2026

Source implementation committed as `0ec89f7`. Added an interactive Three.js
terrain studio with orbit/pan/zoom, property/surroundings views, terrain sections,
LiDAR points, possible discontinuity bands, saved solver replay, finite hypothetical
wall drawing, PNG captions and terrain GLB export. Address preparation and scenario
execution remain gated by explicit confirmation/review. No generated imagery or
decorative water animation is presented as observed data or solver output.

Actual inputs: verified EPSG:2193/NZVD2016 1 m DEM/DSM, 113 official nearby building
footprints, native classified LiDAR roof triangulations (27 meshes, 26,710 vertices)
and a genuine bounded LINZ Auckland 2024–2025 urban aerial crop. Outer roofs use
DSM heights; facades are untextured approximations. Thirty-three terrain
discontinuity bands are candidates, not surveyed retaining walls. Practical
inspection, crest/opening measurement and Council review steps are documented in
`docs/TERRAIN_STUDIO.md`.

The user approved exploratory rain with explicit assumptions. The actual SFINCS
2.4 worker uses an 800 m square real-ground domain, 4 m computational grid and
1 m subgrid hypsometry. Building cells are solid/inactive; roof runoff and pipe
drainage are excluded. Uniform rain, roughness/losses, no external inflow and
free-outflow perimeter are assumed. Rain cessation is followed by 30 minutes
dry-down. The connected catchment/domain convergence remain unreviewed.

Local and live-node zero-rain, 50 mm/h for 30 minutes, and finite hypothetical-wall
runs completed with finite/nonnegative depths. Zero rain remains dry. Live rain
volume was 14,351.185333 m3; final storage was 4,779.389160 m3 without the wall and
4,779.506836 m3 with it; average actual solver timestep was 0.125 s. Stored volume
is bounded by supplied rainfall, but exact integrated open-boundary flux closure
is **unverified**, explicitly shown in UI/results. No calibrated site risk or
engineering recommendation follows from these runs.

Initial averaged-grid trials failed wet/dry QC and are not exposed. The 1 m
subgrid configuration passed. A model observation probe fixes released-solver
weir initialization failure; it is not a measured gauge. Local-only HydroMT
DataCatalog avoids read-only-home artifact cache failures. One OpenMP thread was
verified in a read-only, network-disabled container with the production 2 GiB/
1.5 CPU limits. Actual logs, NetCDF, source hashes and assumptions are retained
privately per run.

Validation: 41 automated tests passed, JavaScript syntax and reproducible bundle
build passed, whitespace/source credential checks passed. Real browser checks
covered desktop/mobile layout, geometry controls, point cloud, exports and actual
solver replay; authenticated public scene and rain/wall runs passed. Cloudflare's
injected analytics beacon is blocked by CSP; no app rendering failure was observed.
Screenshots and exported GLB remain ignored private artifacts.

Deployed `docker.io/library/tidewise-app:studio-v3-20261014` into the existing
isolated tidewise namespace. App/Caddy remain 1/1 Ready with zero restarts; existing
PVCs, credentials and routing were preserved. Confirmed demonstration workspace
`72c8fe1ec25341cc992773793393c7a9` has saved dry/rain/wall results. No public source,
image, data or credential upload/push was performed.

Saved user-provided DataHub credentials only in ignored private environment files
and the provider Secret. The official order-file API returned HTTP 404
`NO_ORDERS_FOUND`; no rainfall file was downloaded or order/license accepted.
The supplied hirds.csv is catalogue metadata (2,305 rows, 144 Auckland entries),
not site rainfall depths. Ordering a custom point HIRDS table and reviewing units,
duration, climate/ARI and temporal pattern remain the design-storm gate.
`docs/HIRDS_API.md` documents commands and the official ordering/API workflow.

Next scientific steps: approved site rainfall table, connected-domain sensitivity,
exact open-boundary budget, measured wall crests/openings and reviewed drainage.
This remains an exploratory research prototype with explicit missing inputs.

## Comprehensive README references — 14 Oct 2026

Added `README_METHODOLOGY.md` and `README_ARCHITECTURE.md` at the user's request.
Reconciled them against source, pinned environment/build files, manifests,
terrain/point-cloud/GIS QC and recorded local/live solver evidence. Documented
data accuracy versus resolution, same-survey comparison limits, local-inertial
equations, exact model configuration, HIRDS order gate, unverified site budget,
practical wall surveys and remaining scientific milestones. Architecture includes
four Mermaid diagrams, runtime/API/job/storage design, Compose/Kubernetes/Caddy,
credential names/status, resource/security boundaries and operational recovery.

Updated the main README's stale no-site-run/no-deployment/account statements and
linked both references. Recorded the existing Compose DataHub environment-binding
gap; documentation changes do not modify runtime configuration or deployed services.
Checks: local Markdown targets/section anchors and fence structure, whitespace,
recorded source figures and source credential scan. No solver rerun, deployment,
credential publication or public repository push was necessary for this docs task.

## Auckland FlowLab rename and live migration — 15 Oct 2026

The user selected **Auckland FlowLab**. Renamed current UI titles/wordmarks/footer,
accessible labels, avatar, API/runtime name, local scripts, session-storage key,
Compose project/image/network aliases, operator environment variable, backups,
Kubernetes namespace/Deployments/Services/Secrets/ConfigMap/PVC names and current
documentation. Adjusted the studio header for the longer name on narrow screens.
Earlier dated records above retain original operational aliases as audit evidence;
retired resources/immutable outputs are not silently rewritten as new executions.

Built/imported `docker.io/library/auckland-flowlab-app:rename-20261015`, OCI index
`sha256:6b321c3ffa70d841e329a1fcff00d9160525c4858b117c590d2c99a540b76d6a`.
SSH initially timed out; the user updated the firewall and access then passed.
Staged a dedicated namespace and copied existing provider/Caddy Secret values
privately without printing them. A preparation job caused the migration's idle
gate to defer changes until completion. The staged app passed internal health,
scene version and saved-run checks before cutover.

Final workspace copy: **748 files hash-verified**; certificate state: **7 files
hash-verified**. Preserved site confirmations, native inputs/outputs, rain/dry/wall
replays and the research login. New app and Caddy are 1/1 Ready with zero restarts.
Previous deployments are scaled to zero and original PVCs retained as inactive
rollback copies; no unrelated cluster workload or ingress was changed. The active
origin is now the renamed Caddy/service in namespace `auckland-flowlab`.

Checks: **41 tests passed**, JS syntax/bundle build, shell syntax, whitespace,
documentation links/anchors and source credential scans. **10/10 authenticated
public smoke checks passed**. Public bootstrap and both real saved rain/wall
results passed; Playwright inspected desktop/mobile naming and the public main/
studio pages. Live activated doctor passed. Local port 8765 was restarted under
the new name. Corrected the existing stop helper's DrvFS cwd-alias matching and
verified it stops only this workspace's owned server. Numerical inputs/results
were preserved; no unnecessary hydraulic rerun or public repository push occurred.

Private migration/check/browser evidence remains ignored under reports/output.
Temporary QA server and browser sessions were stopped; private browser credential
configuration was removed. Original actual environment values remain private.

## Public website access — 15 Oct 2026

The user explicitly requested removing website username/password authentication.
Removed BasicAuth from all current Caddy configurations, Compose requirements,
secret-generation and deployment validation/login prompts. Removed obsolete login
fields from the active Kubernetes Caddy Secret. Provider credentials remain in
their separate Secret; no API key or actual environment file was published.

Validated the new configuration in the running Caddy container, updated only the
active Caddy ConfigMap/settings and restarted Caddy. TLS/certificate storage,
application deployment, prepared data and hydraulic outputs were preserved.
Updated operator files on the node and current READMEs/deployment guides to state
that confirmed workspaces, exports and reviewed simulation controls are public.
There is no per-user job ownership. Host/origin/token checks, body limits, export
allowlists, address confirmation and scenario review remain in force.

Verification: **41 tests passed**, Python compile checks, shell syntax, Markdown
links/anchors, whitespace and credential scans passed. **9/9 public HTTPS smoke
checks passed without Authorization**, including frontend, health, address review,
synthetic laboratory, private-env denial, unconfirmed export denial and foreign
origin rejection. A fresh browser session opened the public app without login.
No new hydraulic run or application image rebuild was required for the proxy
change. Historical authentication evidence above remains dated history.


## Interactive simulation workspace — 15 Oct 2026

Implemented the map-first research journey without rebuilding the project:
confirmed property and evidence, saved native runs, actual georeferenced cell
layers, shared 2D/3D playback, hypothetical polyline wall editing/save/reload,
reviewed asynchronous SFINCS submission, compatible baseline comparisons and GIS
exports. Preparation is separate from simulation; long evidence is expandable.
Preserved specialist lab/studio and PNG/GLB exports. Pending wall edits are labelled
and do not mutate saved water. Parcel boundaries remain above hydraulic overlays.

Read-only public Playwright inspection captured before images. Desktop/mobile QA
used an isolated confirmed local Bayview workspace with matching prepared data
and copies of immutable demonstrations. A three-vertex map wall completed a fresh
native run; sfincs_his.nc records 10 snapped faces with finite interpolated crests.
Original runs, provider credentials, environment files and production were preserved.

Commands/checks completed:
- WSL `python -m pytest -q`: **50 passed**, one locked NumPy/netCDF4 ABI-size warning.
- Full application image `python -m pytest -q`: **50 passed**, same warning.
- `npm --prefix web run check`, `node --check web/workspace.js`, bundle build and
  full Docker build passed. Frontend stage now includes the shared module.
- Fresh actual SFINCS suite in `runs/quality-upgrade-20261015-v2`: **12/12 passed**;
  maximum closed-fixture mass error fraction 5.96046448e-8. Dry/rain, slope,
  stationary states, finite crest, overtopping, endpoint bypass, reversed wall,
  grid and time-step comparisons passed.
- Fresh Bayview repeat/domain/grid runs: repeat matches displayed depths exactly;
  1,200 m domain changes local depths by up to 0.525 m; 8 m grid differs by up to
  1.09 m after common-active block averaging. **Site convergence is not established.**
- Native solver-step maximum-depth wall changes: +0.038/-0.037 m; 5,056 m² at
  >=1 mm change in crop. Saved-frame maximum comparison is a different statistic.
- Native signed storage diagnostic: up to 6.55 m³ negative storage; exact external
  flux closure remains unavailable. No physical-accuracy claim is made.
- Playwright: scenario loading, same 1,800 s map/studio frame, draw/save/reload,
  actual run/status, comparison/before-after, desktop/mobile, exports and screenshots.
- GeoPandas/GDAL: wall and 5,541-cell comparison GeoJSON valid/non-empty WGS84.
  Crest profile also stored as JSON string for GIS readers that drop list fields.
  GLB version 2, 146 meshes and 291 finite VEC3 accessors; PNG exported.
- Review container under 1.5 CPU/2 GiB: health/static/aerial/native result and
  comparison passed; foreign origin/unknown workspace denied. Replay ~972 kB
  gzip, 3.01 s in this smoke check; sampled idle memory ~174 MiB, not peak solver use.
  Temporary review containers and earlier QA servers were stopped.

Corrected a native-job failure caused by inherited deleted cwd: workers now launch
with explicit repository cwd and the model lifecycle restores cwd. Failed outputs
are preserved. Comparison supports older manifests missing subgrid hashes by
verifying actual table bytes, while checking recorded input integrity. HDF5 reads
are serialised; caches/walls use atomic writes. Roof QA rejected 764 points and
3,102 triangles; 26 accepted native roofs remain, with labelled approximate
fallbacks. Terrain elevations were not arbitrarily smoothed. Recorded aerial
imagery is reprojected to Web Mercator for the homepage.

Private evidence: `reports/upgrade-*`, `output/playwright/`, new `runs/site-upgrade-*`
and the isolated workspace. Local review: port 8769, workspace
73cc00b4dc474fb99186ae5e882e6fa5. Production was not deployed, no public push or
commit was made, and Kubernetes resource settings were unchanged.

Updated architecture/methodology and `docs/INTERACTIVE_UPGRADE_REPORT.md` with exact
files, comparisons, screenshots, known failures, performance and rollback steps.
Remaining: connected catchment/boundary review, signed-storage diagnosis, exact
flux budget, calibrated HIRDS inputs, measured walls/drainage, field calibration,
further convergence, parcel/transect diagnostics,
scene LOD/camera transitions and per-user ownership. This is a useful exploratory
journey, not completion of all scientific/product roadmap items.

Same-time baseline/modified 2D swipe was added and checked with Playwright; two
separate native-value canvases are clipped at the movable divider.

## 15 October 2026 — authorized production release

Deployed the tested interactive upgrade to https://daryajan.com on the verified
Helsinki k3s node, namespace auckland-flowlab. App and prepare-volume now use
interactive-20261015-r1 (image ID ed573b3a361ba3403ff28a4516f8194dc2cacbec0dafc9e34d4772520c948e50).
The first SCP upload was interrupted; resumed SFTP completed and archive SHA256
was checked before import. Took a consistent 761 MB workspace backup while the
app was stopped; retained previous image/deployment and verified all 20 native
output/replay/manifest hashes were unchanged. Existing Caddy, TLS, provider
Secrets, PVCs and resource settings remain in place. The new pod is Ready with
zero restarts. No new production hydraulic job or saved-wall mutation was made.

Release image: 50 tests passed (one pre-existing NumPy/netCDF4 import warning).
Public API checks passed scene v6, imagery, saved dry/rain/wall results and actual
comparison +38/-37 mm, 5056 m² changed at >=1 mm; origin and unknown-job guards
passed. Live browser verified swipe, split real 3D, depth/velocity with shared
1200/1800 s timeline, 390×844 mobile without horizontal overflow, and evidence
modal. Existing Cloudflare beacon remains blocked by self-only script CSP.

Added root how-to-deploy.md with PowerShell/server commands, resumable verified
image transfer, idle checks, consistent backup, atomic app/init image patch,
public smoke script and previous-image rollback. Added reusable deployment
helpers under deploy/k8s and synchronized both tracked app-image references.
Private deployment evidence is in reports/interactive-production-* and
output/playwright/production-*. Scientific limitations remain as documented in
the interactive upgrade report.

## 15 October 2026 — Earth studio implementation, deployment blocked

Implemented optional CesiumJS 1.146 Earth studio while preserving Leaflet and the
original Three.js studio. Acquired terrain/roofs/aerial imagery form a resident
GLB; native SFINCS water, differences, opacity and sampled velocity arrows share
scenario/wall/timeline state. Added orbit/property/top/context cameras, compact
mobile controls, source dates and bounded public metadata checks. Google has
Hybrid/LiDAR/Neighbourhood modes, polygon clipping, restricted browser-key config,
visible attribution, bounded tile cache, retry/fallback and no Google extraction.
The user explicitly chose to enable Google later; no actual Google coverage or
independent Google/LiDAR alignment validation is claimed.

Pinned and verified LINZ NZGeoid2016 via PROJ-data. Independent bilinear sampling
tests confirm h=H+N and sign; local numerical display residual is 5.7 mm, geoid
separation +34.630 m. Epoch/deformation and Google photogrammetry offsets remain
unverified. Missing/modified grids fail closed. Acquired source snapshots and
solver inputs are never automatically replaced by a reachability check.

Validation: 55 Python tests pass, terrain GLB geometry test passes, npm syntax and
both bundles build. Playwright checked real local saved rainfall/wall replay,
signed comparison, shared 1200 s playback, velocity/72 sampled arrows, mobile
390×844 without horizontal overflow, source check UI and synthetic Google HTTP403
fallback. A viewer-close lifecycle error found by fault testing was fixed and
retested. Demand-driven rendering, 30 FPS cap, reduced mobile detail and hidden
viewer pause are implemented; sampled water-geometry construction was 9.7 ms on
this test machine, not a multi-device performance certification.

Prepared image auckland-flowlab-app:earth-20261015-r1,
sha256:c070767824173f4bf696b9d06478459f09baa3ac5240507df82e9f98e44c7adb.
The existing helsinki-server alias resolves to 2.29.10.235 but repeated SSH attempts
time out. Public production /healthz still returns ok. No production image,
configuration, secrets or native artifacts were changed for Earth studio. The
tracked Kubernetes image remains the previously deployed interactive release.
An asynchronous question about a changed SSH/VPN route is pending.

Review server: http://localhost:8772/?job=73cc00b4dc474fb99186ae5e882e6fa5.
Final-image read-only review container: localhost:8773, 1.5 CPU / 2 GiB, same saved
workspace. Evidence: reports/earth-*, output/playwright/earth-* and hybrid-*.
Updated how-to-deploy.md with the prepared release, secret-safe browser-key
configuration helper, backed-up restart and --earth public verification.
Remaining gates: working deployment SSH route, real Google key/coverage/clipping
and independent source alignment checks, representative-device sustained testing,
new-survey coverage/QC/rebuild before claiming newer terrain. Existing catchment,
drainage, calibration and hydraulic-budget limitations remain unchanged.

## 15 October 2026 — Earth studio deployed after firewall update

The user's firewall update restored helsinki-server access. Reverified the node
UID, retained existing resources, imported the tested earth-20261015-r1 image
after archive SHA256 verification, passed idle gates, and took a 1.1 GB consistent
workspace backup with the app stopped. Patched both app/init images; rollout is
Ready with zero restarts. All 28 native artifacts retained their SHA256.
Backup and previous interactive-20261015-r1 image references remain under
/opt/auckland-flowlab-deploy/releases/earth-20261015-r1/.

Public --earth verification passed health, native saved rainfall/wall comparison,
imagery, source metadata, georeferencing (5.7 mm numerical residual), bundle and
worker assets, foreign-origin denial and unknown-workspace rejection. Google is
confirmed disabled. Live Playwright checked Earth scene, shared 1200/1800 s
timeline, signed maximum-depth comparison (+38/-37 mm, 5056 m²), velocity layer,
source dates/provider-check dialog and mobile 390×844 without horizontal overflow.
Existing Cloudflare analytics beacon is still blocked by CSP; no app rendering
error was observed. No new solver job or wall mutation was used for deployment QA.

Updated how-to-deploy.md, tracked app/init image references and upgrade report to
the deployed release. Evidence is reports/earth-production-{release,validation}.json
and output/playwright/earth-production-*. Previous SSH blocker is resolved. Google
live coverage/alignment and the documented scientific validation gates remain.

## Address type-ahead and alphanumeric address fix — 15 October 2026

Fixed the interactive address entry path without changing the official-match, parcel
review, or explicit-confirmation gates. The exact resolver previously accepted only
numeric street numbers and compared a trailing postcode as if it were part of the
town/city, so `2A Toroa Terrace, Mount Albert, Auckland 1025` could fail before a
LINZ lookup. It now accepts an alphanumeric unit/house suffix and strips an optional
four-digit postcode before the exact official query.

Added a 250 ms debounced, bounded LINZ type-ahead endpoint and selection list. A
suggestion only fills the input; selecting it still executes the existing exact
official address + point-covering parcel lookup and requires explicit visual
confirmation before preparation. The local workspace subprocess now exposes this
checkout's `src` path to its CLI child process, preventing a local-only
`ModuleNotFoundError` during lookup.

Focused checks only (no full test run): WSL pinned environment ran 3 relevant tests
(`tests/test_address_input.py` plus the isolated workspace search guard), JavaScript
syntax and `git diff --check` passed. Live local API smoke: `2A Toroa` returned the
official `2A Toroa Terrace, Mount Albert, Auckland` suggestion; selected exact
address resolved with `official_exact_match=true` and remained unconfirmed. The
Playwright CLI could not launch because WSL has no Chromium distribution; no browser
installation was performed. No solver, terrain preparation, site simulation, or
production deployment was run.

## Terrain-and-evidence-only app surface — 15 October 2026

At the user's request, removed the app's hydraulic/simulation surface without
deleting source model code, saved native runs, inputs, or research data. The public
app no longer loads hydraulic/workspace scripts, solver lab, rainfall forms, wall
controls, saved-result layers, comparison/swipe controls, time playback, 3D/split
hydraulic views, or associated animation. The server no longer exposes the public
routes that start, list, read, compare, or save hydraulic runs/walls; it no longer
advertises a solver in bootstrap data. Address search, explicit parcel confirmation,
terrain profiles, and bounded GIS/evidence exports remain.

Focused checks completed: JavaScript syntax, Python API compilation and
`git diff --check` passed. A restarted local app returned bootstrap data without a
solver, its homepage contained no hydraulic assets/copy, and the former
`/hydraulic.js`, `/workspace.js`, `/scene.html`, and `/api/lab` entry points each
returned 404. No production deployment or full test run was requested or performed.

## Terrain-and-evidence-only production release — 15 October 2026

Deployed `terrain-evidence-20261015-r1` to `https://daryajan.com` after building
local image `sha256:bfc9910fde4044277e1dcf79b9a86565b31ebf503a2c57098549c240d3ff150a`.
The first resumable SFTP attempt produced a checksum mismatch and was not imported;
a clean retry completed with verified archive SHA256 before containerd import. The
server-side release helper enforced the idle gate, created a 1.2 GB consistent
workspace backup, preserved all recorded native artifact hashes, retained both
previous `earth-20261015-r1` image references for rollback, and rolled out the new
app pod Ready with zero restarts. Caddy, provider Secrets, TLS, PVCs and resource
limits were unchanged.

Focused public checks passed: health, homepage, Leaflet, public bootstrap without a
solver, exact address review, unconfirmed export denial, foreign-origin denial,
terrain-source access, unknown-workspace denial, no hydraulic page assets/copy, and
404 responses from former hydraulic/workspace/scene/lab endpoints. No full Python
suite, new preparation task, solver run, or saved-data mutation was performed.

## Terrain 3D correction production release — 15 October 2026

Restored the two terrain-only 3D entry points requested by the user: the native
LiDAR/property viewer (`terrain3d.html`) and the Earth/Google-context viewer
(`hybrid.html`). They load the existing terrain, building, parcel, point and imagery
evidence APIs only; the hydraulic UI, solver, rainfall/animation controls and former
hydraulic routes remain removed. The Earth viewer retains its explicit provider-state
handling. Google visual context is restored as a UI capability, but live Google
content remains unavailable until a valid browser key is configured.

Deployed `terrain-3d-20261015-r2` using image manifest
`sha256:28bd6a6a6b7b38b0894a8fc457933194d521333afb0fc377c2463b03c48c17eb`.
The release helper recorded the prior terrain-evidence image, retained the recorded
native artifact hashes, and the new pod is Ready with zero restarts. Focused public
verification passed: health, address review protections, `/terrain3d.html`,
`/terrain3d.bundle.js`, `/hybrid.html` and `/hybrid.bundle.js` all return 200;
`/hydraulic.js`, `/workspace.js`, `/scene.html` and `/api/lab` return 404. No full
test suite, new solver run, or saved-data mutation was performed.

## One-window 3D visual review — 15 October 2026

Paused the next production rollout after visual review found that the first
terrain-only correction was clean but not an adequate all-in-one presentation.
The local review container is running only on `127.0.0.1:8774`; production remains
on `terrain-3d-fix-20261015-r1`. It renders the actual orthophoto/1 m LiDAR terrain,
official building footprints as bounded DSM-median volumes, official parcel outline,
Council mapped overland-flow paths, LiDAR candidates and native point-cloud toggle in
one workspace. The former corrupt roof/facade triangulation is removed.

Focused local validation: image built, server health returned OK, scene rebuilt from
the selected workspace and browser review showed 113 LiDAR-derived building volumes
and 24 Council flow paths together. No full suite and no production deployment was
performed. Embedded Google 3D/Street View remains a provider-key/coverage gate; the
same workspace has direct Google Earth and Street View launch controls pending a
configured browser key for an in-app Google layer.

## Shared 3D renderer, alignment and visual review — 16 October 2026

Replaced the mirrored footprint extrusion with a shared coordinate contract
`east, elevation, -north` for both Three.js and Cesium. Both public 3D routes now
open one workspace with LiDAR, georeferenced Earth context and Street View tabs.
The homepage opens that workspace in the same tab. Removed hydraulic rendering
code from the Earth bundle; the previously removed hydraulic APIs remain removed.

Fixed the missing-imagery pipeline: preparation includes a bounded official LINZ
orthophoto crop and an existing-workspace preparation action. Acquired the actual
Kitenui crop locally and verified its bounds exactly match the scene. Correct sRGB
input/output and unlit imagery avoid the prior washed-out aerial material. Roofs
use quality-filtered class-6 native returns, not flat blocks or unsupported DSM
vegetation over building outlines. Kitenui has 53 supported roof meshes; Pemberton
has 27. Neutral display sides close roof boundaries to measured ground without
inventing facade detail. Wider context remains aerial/DEM where point coverage is
absent. Source point crops cover 200 m; ground/imagery context covers 320 m.

Classified points are bounded to 450000 displayed returns, excluding withheld/noise,
with actual source heights and orthophoto colours sampled in NZTM. Local browser
review loaded 397926 Kitenui and 259552 Pemberton returns. Trees, roofs, ground,
parcel and mapped Council flow paths have explicit layer controls. Flow paths are
clipped and sampled against terrain at 1 m spacing to avoid floating line chords.

Executed: frontend build, JS/Python syntax, `git diff --check`, asymmetric geometry
fixture (northing/UV/roof isolation/interpolation), 2 focused address tests, and the
focused roof outlier/footprint-hole test (1 passed). Local API type-ahead and exact
Kitenui lookup succeeded with private `.env` inherited by the container. Numerical
globe-frame residual for Kitenui was 5.478 mm; this is not independent source
alignment validation. Visually reviewed both renderers, top/property views,
vegetation toggling, and Street View's honest missing-provider state in Edge.
Evidence is in `output/visual-review/`. No full test suite or solver run was used.

Local review runs at `http://127.0.0.1:8774` in `floodtwin-3d-local-review`, with
source/web mounts for the reviewed changes. No cluster deployment was performed
for this correction. Google live tiles and embedded Street View remain blocked
by the missing browser-key configuration, so live Google coverage is unverified.
Official Three.js colour-management/glTF and Google Embed documentation informed
the shared-frame, colour-space and provider-state implementation.

## Local production environment and Lloyd recovery — 16 October 2026

Diagnosed the Lloyd preparation failure from its private worker log: a 60-second
read timeout fetching LINZ public elevation STAC item metadata. It was not an
address-match failure. Later steps were blocked by the terrain dependency.

Recreated only the loopback review container with `--env-file .env.production`;
kept source/web/data mounts and explicitly overrode the app origin to
`http://127.0.0.1:8774`. No secret values were printed, copied into source or served.
No cluster changes were performed. Added bounded transient GET retries, a shared
URL-keyed metadata cache, and reuse of recorded public STAC items only when their
SHA256 matches the collection's advertised checksum. No other site's geodata is
borrowed. Documented the current container configuration in `docs/LOCAL_APP.md`.

Added confirmed-workspace preparation retry, completed-artifact reuse, duplicate
worker prevention and slot release on failure. UI now offers Retry blocked data,
counts only ready steps for progress, and gates the 3D link on actual terrain and
point-cloud files. Resumed the existing confirmed Lloyd workspace: all 9 steps are
now done/cached with zero blocked. The real scene has aerial imagery, 57 supported
class-6 roof meshes and 36 mapped flow paths; browser loaded 417173 non-noise
classified returns. Visually verified the restored 9/9 homepage and 3D scene, with
no browser console errors. Screenshots: `output/visual-review/lloyd-*.jpg`.

Verification: 4 focused workspace failure/retry tests passed (14 deselected),
JavaScript/Python syntax and `git diff --check` passed. No full suite or solver run.

## Selected-property 3D boundary — 16 October 2026

Replaced the easily occluded one-pixel parcel line with a yellow, dark-cased,
fixed-pixel selection outline and light parcel shading. The LiDAR outline is
drawn over objects; Earth uses the same explicitly closed, DEM-sampled ring with
a depth-fail outline so trees/buildings cannot hide the selected extent. Both
remain controlled by Confirmed parcel. No cadastral coordinates, terrain or
building measurements changed. This is a display selection, not a fence/wall.

Verification: `node tests/web-geometry.mjs` passed the existing frame/roof checks
and added parcel closure, ground sampling, immutability and overlay checks.
`npm --prefix web run build`, targeted JS syntax checks and `git diff --check`
passed. Visually checked the real, prepared Lloyd workspace locally in both
LiDAR and georeferenced Earth views, including parcel on/off; no console errors.
Screenshots: `output/visual-review/lloyd-boundary.jpg` and
`output/visual-review/lloyd-earth-boundary.jpg`. Google live photorealistic tiles
remain unverified without a browser key. No full tests, hydraulics or deployment.
Next step: user review of the local selected-property presentation.

## Earth axis alignment and thin parcel boundary — 16 October 2026

Found an actual Earth model/overlay registration bug in the Cesium glTF loader's
default forward-axis correction. The shared mesh is (east, height, -north), but
default Y-up/Z-forward transformed a test point (17, 12, -83) to (-83, 17, 12),
while parcel/flow entities use (17, 83, 12). Explicit Y-up/X-forward now applies
only the necessary up-axis conversion. No source coordinates, survey heights or
geoid transform changed. Cesium's official Model axis documentation and the
installed 1.146.0 ModelUtility implementation were checked.

Reduced the boundary to a 2 px yellow line with a 0.5 px dark casing on each side
in both modes, with quieter 6% shading. The selection remains visible through
objects and is not a physical wall.

Checks: `node tests/web-geometry.mjs` passes, including three asymmetric points
through the installed Cesium axis-conversion implementation and explicit line
width assertions. `npm --prefix web run build`, `node --check web/hybrid.js`
and `git diff --check` passed. Visually checked the real Lloyd scene locally:
Earth oblique/top alignment and thin LiDAR boundary, no browser console errors.
Screenshot: `output/visual-review/lloyd-earth-aligned-thin.jpg`. No full tests,
solver run, data replacement or deployment. The local production-env container
still has no GOOGLE_MAPS_BROWSER_KEY, so Google photorealistic imagery remains
unavailable; the checked Earth scene is explicitly LINZ LiDAR/aerial data.
Next step: user review of the corrected local Earth workspace.

## Full-density LiDAR and raw-object inspection — 16 October 2026

Audited the actual Kitenui crop: 800288 source records, 795851 usable after
withheld/noise filtering. Previous presentation took every second usable point
(397926 loaded), and ground returns were off by default. This was real display
data loss, not a failed download. The existing crop is losslessly sourced within
200 x 200 m; the larger aerial terrain does not imply native point coverage.

Removed default stride decimation and bumped the points API cache version.
Expose original/usable/loaded counts, class counts, exclusions and crop bounds.
All usable classes including ground, unclassified and overlap returns are now
loaded at native density in both viewers. Ground is enabled by default and is
retained in Earth glTF, rather than being dropped by export visibility. Only
withheld and noise classes 7/18 are excluded from display; raw LAZ is unchanged.

Added independent mesh/terrain/unclassified controls, circular native point
sprites, aerial/classification/height colour modes in LiDAR, Earth point-size
control and raw-point inspection. The latter removes surfaces that can occlude
small returns, enables all classes and offers a closer view; no fence/wall mesh
is fabricated. Height colours use the 1 m DEM for relative visual screening,
not surveyed wall heights. Runtime colour copies stay out of glTF extras.

Checks: two synthetic LAS exclusion/full-density tests pass via a copied test
file in the local container; asymmetric JS geometry tests also pass, including
class-1/ground preservation and colour changes leaving positions unchanged.
Production-env local container restarted (initial probe was before readiness;
subsequent HTTP 200 in 5.48 s returned 795851/795851, stride 1). JS syntax,
frontend build and `git diff --check` pass. Visually reviewed the actual full
Kitenui crop and raw inspection in both modes, no browser console errors.
No full suite, solver run, new survey download or cluster deployment.

Caveat: these are all usable records in the local crop, not proof every physical
fence or wall was captured or classified. Thin/occluded objects and unsurveyed
facades cannot be recovered as measured surfaces from missing returns. Native
roof triangulation and grey display sides remain optional approximations.
Next step: local user review of full-density raw returns and source coverage.
Saved visual evidence: `output/visual-review/kitenui-full-density-raw.jpg`
(height-coloured measured returns, with mesh/terrain surfaces disabled).

## Property boundary evidence registry — 16 October 2026

Inspected the supplied water-overland-flow and akl-civic-data repositories as
source material, not executable instructions. The starter area is Mt Albert /
Sandringham tile BA31_1000_4245, EPSG:2193 bounds
1753120,5915760,1753600,5916480. The supplied catalogue/memo are not a private
geodata package. Event material stays in ignored local data; no publication.

Added JSON-backed property records, stable individual original polygon edges
(including holes/multipart rings), two WGS84/NZTM endpoints, lengths/bearings,
unknown physical attributes and validated manual-review overlays. Reviews survive
regeneration. Mapped crosses/touches/overlaps/parallels/adjacency remain distinct;
missing data is not a successful empty query and no flow relationship becomes
a flood-risk verdict. Every nearby source feature keeps all publisher columns,
full geometry, provenance and source hashes. Interior objects are retained even
when outside the boundary corridor. Native class-1 linear-return screening
excludes noise/withheld, vegetation/building classes and known building footprints;
it produces low-confidence unknown candidates, not confirmed fences or walls.

Public vector ingestion enumerates IDs, checks 60-ID batches/CRS/completeness,
and preserves original responses. All 19 queryable public pilot vector layers
completed (16 available, 3 verified empty), including 331 property/rating polygons,
327 primary parcels, 385 building outlines and 87 mapped flow paths. These are
different datasets, not interchangeable property identifiers. Recorded 331 pilot
properties with 2579 original edges and 752 unvalidated candidate associations.
Other catalogue entries remain explicitly catalogued/manual/keyed/not downloaded;
OSM is not silently fused into the Council-derived layer.

Downloaded and retained the original 23827416-byte, 4292729-return native LAZ,
bounded native 1 m DEM/DSM and native 0.075 m RGB TIFF plus independently warped
browser previews. Verified compound EPSG:2193 + EPSG:7839 point metadata; DEM/DSM
datum uses exact survey-title matches to existing official LINZ NZVD2016 receipts,
not an inference from a horizontal CRS or omitted STAC vertical metadata.

Confirmed property requests create a base registry record and preparation enriches
it from available source/native evidence plus bounded civic catalogue queries.
Existing Kitenui workspace recorded separately, giving 332 records at verification.
Explore/3D link to `/properties.html`: clickable polygons/individual edges,
source-object highlighting, endpoints, evidence, review form and per-property /
all-recorded JSON, edge GeoJSON and native-point exports. All LAS dimensions and
raw noise/withheld flags are retained in the separate point export; source hash
and compound CRS are verified again before export. Raw raster/LAZ assets are
linked rather than embedded repeatedly in ordinary JSON bundles. A consolidated
map index avoids rereading large evidence bundles during browsing (0.05 s local
HTTP map response after indexing).

Commands/checks: `import-civic-pilot --catalogue /work/data/civic-input/catalogue.json`,
`record-properties --workspace 7207322971a842a990174c3b93f5b4b5 --force`, targeted
`pytest /tmp/test_properties.py -q` (16 passed), and existing workspace confirmation/retry/
isolation selection (8 passed, 10 deselected). Added offline fixtures for eight
edges, stable IDs, holes, crossing distinctions, interior/nearby evidence,
candidate exclusions, review persistence, index refresh, CSRF, complete source
batches, verified-empty queries and lossless native-point export. No full suite.
Actual HTTP checks: all 332 records exported (138274876 bytes before interior-link
refresh), Kitenui point export 17884 returns / 18 LAS dimensions, pilot example
8202 returns / 18 dimensions and eight GeoJSON edges. Native and edge lengths/
attribute-array counts checked. JS syntax, Python compile, frontend build and
diff whitespace checks performed; local browser visual review covers selection,
aerial alignment, evidence and download controls. Downloaded and parsed the pilot
example's 19181-byte boundary GeoJSON with eight features through the browser.
Screenshot: `output/visual-review/property-boundary-evidence.png`.
No hydraulic run or deployment.

Limitations: no labelled reference set or field verification supplied; detection
precision/recall, physical material, permeability, depth and flood risk remain
unverified. No-return corridors do not prove no fence. The 1 m DEM supports only
screening relative heights, not measured wall dimensions. “All” exports mean all
recorded properties, not all Auckland or every restricted datasource. Storage is
JSON, not a newly provisioned Postgres database. Existing 3D modes are retained.
Next step: local review of boundary evidence and manually labelled validation.

## Inline 3D boundary editing + two assistant-authored samples — 16 October 2026

User clarified predictions should be made in-session for 3A Sadgrove Terrace and
23 Kitenui Avenue, with no model API/key provisioning. Preserved existing dirty
work and the newly supplied untracked check-BA31_1000_4245-team.csv. Its screen
labels were not treated as field measurements or used for an accuracy claim.

Fixed the UI gap: the 3D workspace previously only linked to the separate boundary
page. It now draws every original registry segment as a separate thin, numbered,
terrain-draped selection overlay in both Three/LiDAR and Cesium/Earth views.
Coordinates use exact absolute NZTM minus the same scene origin; no parcel/roof
geometry changes. Screen-space line picking ignores orbit drags. Same-origin,
job-scoped iframe messages synchronize Earth picks, visibility, labels and the
shared inline editor. Source-object outlines are clipped to scene extent, not
clamped onto its edges. Property camera framing now centres/fits the actual parcel
rather than its address point. Polygon/line graphics are not physical barriers.

Added inline source/inferred-object selection, original evidence, prediction
inspection, proposal-to-form copy (no auto-save), and manual type/material/
height/width/depth/continuity/permeability/influence/note edits. Reviews retain
CSRF/origin and property-membership checks. Existing map/context modes, native
full-density points and Street View remain available; no hydraulic UI re-added.

Prepared and visually inspected two analytical top-view aerial/native-return
figures. Offline evidence extracts original class counts and DEM-relative return
statistics per edge/footprint. Assistant-authored drafts are tied to image SHA256
and input revision; a local helper only validates/persists those already-authored
choices and attaches native statistics. This is NOT a deployed AI detector. No
OpenAI/model API, credential write, Google imagery scrape or remote image upload.
Google 3D/aerial/Street View were not used because no browser provider is configured.

Saved separate ignored JSON prediction bundles for property_5d45d76966ddf60027d0ce62
(Sadgrove, four edges) and property_f79838915f2b5477066e33b5 (Kitenui, five edges).
Every saved entity has an explicit result: 44 and 55 rows respectively, including
28 and 41 `not_applicable` context entries, and building-source aliases (not extra
physical buildings). There are 30 unreviewed proposal rows including aliases,
nine original edges and three newly delineated connected vegetation clusters.
Some hedge/fence types/heights are low-confidence visual hypotheses; obscured or
mixed full-edge heights remain unknown. Classified roof envelopes are only assigned
with >=100 building returns and >=80% footprint coverage. Height-range kinds
distinguish observed return spreads from subjective guesses; neither is a calibrated
confidence interval. Material/depth/permeability and flood risk are not fabricated.

Prediction bundles, inferred canopy geometry, drafts and evidence images live under
data/property-registry/{predictions,assistant-drafts,sample-evidence}; manual object
reviews have their own object-reviews folder. Registry read/export includes both
proposals and manual values without replacing original data. Source revision
changes (now including aerial JPG/metadata) flag proposals stale and disable
copying. The original AI draft never becomes field verified automatically.

Focused checks: 25 property/prediction tests passed; eight workspace confirmation/
retry/isolation checks passed (10 deselected, one dependency deprecation warning).
New JS boundary checks pass for asymmetric absolute/local coordinates, sampled
ground, hidden-line screen picking, bounding clips, point markers, camera framing
and non-mutating selection. Existing web-geometry checks pass. JS syntax, Python
compile, frontend build and git diff --check passed. One initial finite-value test
exposed normalization hiding Infinity; validation now runs before JSON cleaning,
and the regression passes. Synthetic CSRF/write/export tests cover object editing
without fabricating reviews on the real properties.

Local production-env review container restarted, loopback 8774 retained. Actual
HTTP per-property exports return 200, contain all edges + inferred objects and
non-stale predictions (398664 / 423108 bytes before any later user reviews).
The saved annotated evidence PNG route returns 200. Visually confirmed Sadgrove
canvas clicks select edge 2 in LiDAR and edge 4 in Earth, updating the same editor;
both modes show numbered lines, saved predictions and no browser errors. Kitenui
loads its five edges and sample proposals as well. Verified its tentative 1.5 m
fence proposal copies into the form without saving, and its main building's
5.33 m roof-envelope estimate selects/highlights the correct source geometry.
The saved aerial/native evidence opens in a modal on the same 3D page. Final
visual artifacts: `output/visual-review/kitenui-3d-boundary-prediction.png` and
`output/visual-review/sadgrove-earth-boundary-prediction.png`.
No full suite, solver run or
cluster deployment. No material/height edits were fabricated as real reviews.

Next step: user review/correction of the local sample proposals and field/reference
validation before any broader detection/accuracy claim.

## 2026-10-16 - Playwright browser corroboration of both sample properties

Inspected Google Earth top and photorealistic oblique views for 3A Sadgrove
Terrace and 23 Kitenui Avenue, comparing house/driveway/vegetation layout with
the original numbered LINZ parcel evidence. Top-view footers displayed
2024-03-18 (Google / Vexcel); 3D acquisition dates remain unverified. No Google
geometry was reconstructed, no tiles harvested and no AI/model API was called.
The CLI prerequisite/help check succeeded; browser review used the available
Playwright browser tools. Flutter accessibility needed keyboard activation;
some camera controls intercepted clicks, so no precise camera/height measurement
is claimed from those controls.

Street View failed for BOTH addresses in this session: Google metadata HTTP
500 and panorama tile HTTP 403, with the UI displaying no imagery. Kitenui's
coordinate retry and Earth Street View also failed. Failed sources are recorded
as attempted only, never counted as inspected imagery or confidence evidence.
This does not establish that these streets have no public Street View coverage.

Saved browser-review drafts and revised prediction JSON for all nine original
edges. Each edge has ten field assessments, individual qualitative confidence,
visibility/occlusion, rationale and linked view provenance. Successful screenshot
SHA256s are attached; old prediction JSON is archived by hash, original drafts
are preserved. Sadgrove street-front planting type moved low -> medium with
corroboration; heights remain low confidence, mixed-edge heights unknown.
Material/thickness/depth/permeability/risk stay unknown rather than fabricated.
Council GIS crossing flags and original endpoints remain unchanged. This is a
one-off assistant review, not a deployed detector, survey or hydraulic analysis.

The 3D editor now shows the field assessments, separates type from height
confidence, exposes source links/dates and detailed observations, and copies
continuity/permeability/influence into its edit form without auto-saving. Manual
reviews remain separate from predictions. No real-property manual review was
created during verification. Embedded Google 3D credentials remain unchanged;
public Earth browser access does not configure the app's Google API key.

Focused commands/checks: `python -m pytest -q /tmp/test_boundary_predictions.py`
inside the existing local container: 16 passed (including incomplete-field,
failed/foreign-source, false mapped-crossing and asserted-unknown rejection).
`node tests/web-boundaries.mjs`, JS syntax, frontend build and `git diff --check`
passed. Revalidated actual stored bundles against the current validator; all
nine rows contain ten assessments. An initial persistence attempt correctly
rejected absent screenshot artifacts in the container; copied the four specific
inspected screenshots into its output/playwright directory and saved successfully.
An initial diagnostic incorrectly validated the API metadata projection instead
of the full stored bundle; rerunning against prediction JSON passed.

Actual HTTP exports: both 200, 413256 bytes (Sadgrove) / 440860 (Kitenui),
predictions non-stale. Playwright selected every original edge and confirmed its
ten field rows and individual confidence. Sadgrove frontage proposal copied as
hedge / 1.2 m / discontinuous and explicitly remained unsaved. Both local 3D
pages rendered their numbered boundaries and had zero browser console errors.
Visual artifacts: output/playwright/{sadgrove,kitenui}-saved-google-review-3d.png;
Earth and failed Street View screenshots are in the same ignored QA folder.
Server remains local on 127.0.0.1:8774. No full suite, deployment or solver run.

Next: user/field review of obscured structure details. A usable street-level view
or survey is still needed before material, thickness, concealed fence continuity
or engineering heights can receive stronger confidence.

## 2026-10-16 - Independent multi-view boundary skill and supplied-image review

Created/validated `skills/property-boundary-review/SKILL.md`, field/persistence
reference and Codex UI metadata. Installed identical files at
`C:/Users/AtaMoradi/.codex/skills/property-boundary-review`. Skill-creator validation
passed for both copies; primary SKILL SHA256s match. Workflow requires a numbered
plan, four distinct Earth angles and street-level coverage (or explicit partial
status), property/camera-address reconciliation, original GIS IDs, multi-object
components, ten per-field assessments, explicit unknowns, local save/export and
visual QA. No model API, automatic credential provisioning or deployment implied.

Inspected the user's four distinct Kitenui Earth views and one distinct street
image (duplicate street upload counted once). Street footer shows Feb 2023;
caption says 25 Kitenui Ave while target Earth label is 23. Roof/chimney/drive/
garage/hedge arrangement visually matches the selected property; retain camera
caption and the non-surveyed identity limitation. This is NEW supplied street
evidence, not a claim that the earlier failed browser access was repaired.
Attachments retain conversation references, no fictional local image/hash.
Sadgrove was not newly reviewed from these Kitenui-specific attachments.

Saved a Kitenui multiview revision with five original edges, ten field assessments
per edge and ten component observation slots (includes a hidden/unresolved rear
base, not ten proven detected structures). Front clipped hedge and woody vegetation
supported; side boundary changed from a uniform fence to mixed possible fence/
planting, whole-edge 1.5 m guess withdrawn. Rear/corner canopy remains vegetation,
not a fence height; southwest side is mixed nearby paving/hedge/outbuilding.
Image-relative component positions have null geometry and no inherited crossing.
Material/thickness/depth/permeability/risk unresolved where evidence cannot show
them; no numerical foundation depth invented merely to fill an input.

Focused native check: within 0.5 m of front edge, 349 vegetation returns;
exploratory 0.4-3.5 m above-DEM filter retains 179, p10/median/p90 1.79/2.34/2.75 m.
Saved 2.34 m low-confidence candidate foliage envelope with explicit filter
assumption; not a calibrated hedge crest, may include other vegetation. Dates
differ between historical street view and native/recorded aerial sources.

Form no longer presents unknown manual values when fresh proposals exist:
auto-prefill type/material/dimensions/continuity/permeability/influence/note,
explicit UNSAVED IMAGE/LiDAR PROPOSAL label, manual review precedence and stale
guards. No actual user review created. Each source/component/field remains in
JSON. Prior bundles archived before replacement; original drafts untouched.

Focused verification: skill validator passes; 18 prediction tests pass in the
existing local container. New pure JS form checks pass for fresh proposal,
manual precedence, stale/context rejection and nonmutation. An initial boolean
test exposed undefined without a proposal; normalized to boolean and passed.
Existing JS geometry checks, syntax/build and git diff --check pass.
Actual HTTP property/export returns 200 with five fresh edge predictions.
Playwright selected all five edges and verified prefilled types/material/heights/
notes without saving. Screenshot inspected at
`output/playwright/kitenui-multiview-prefilled-form.png`. Local server retained
at 127.0.0.1:8774. No full suite, hydraulics or deployment.

Next: invoke the new skill on another confirmed property with its own adequate
views; unresolved concealed details still require better imagery/profiles or
field measurement rather than cross-property defaults.

## 2026-10-16 - Numeric type and height classification confidence

Added explicit type and height class labels with separately authored confidence
scores in [0,1], shown as 0-100% in the 3D summary, field rows, component notes and
boundary selector. Numeric judgments are subjective/uncalibrated, not measured
accuracy or probabilities. No automatic low/medium-to-number conversion.
Height classes are fixed metre bands, variable_height for mixed corridors, and
unresolved for an unsupported isolated component. Numeric estimates/ranges and
canopy-vs-fence methods are preserved; no height fabricated to fill a class.

Scored all nine original boundary edges of both confirmed samples, with explicit
component scores where reviewed. Kitenui frontage: hedge .90, 2-<3 m .55 with
the existing 2.34 m candidate foliage envelope. Mixed edges use variable_height
without pretending to have a uniform physical crest. Hidden observation slots
retain occluded/unresolved and zero physical-attribute confidence. Full source,
geometry, crossing and manual values unchanged. Prior prediction revisions are
archived; scoring drafts reference their exact SHA256.

Updated installed and portable property-boundary-review skill with numeric-score
semantics; both validate. Packaged the updated skill as
output/skills/property-boundary-review-numeric-confidence-20261016.zip.
Focused checks: 27 classification/prediction tests passed in the local container;
JS numeric-label and form-precedence checks passed; frontend build and diff check
passed. Invalid/nonfinite/out-of-range/boolean confidence and inconsistent labels
are rejected; classifier and field confidence must agree.

Playwright selected all five Kitenui edges and read the new class/score summaries.
Visually inspected output/playwright/kitenui-numeric-classification.png showing
hedge 90%, 2-<3 m / 2.34 m 55%. No manual review saved by this work. Local server
remains on 8774. No full suite, data acquisition, hydraulics or deployment.

Next: calibrate these subjective scores against independent labelled examples
before interpreting percentages as a statistical success rate.

## 2026-10-16 - Regional Mt Albert boundary/flow crossing-object JSON export

Added the Boundaries page's `Export Mt Albert crossings JSON` button and a link
from the inline 3D boundary editor. Read-only endpoint:
`GET /api/properties/mt-albert-flow-crossings`. It reads saved properties, source
asset candidates, LiDAR candidates, fresh predictions/components and manual
reviews; it does not acquire providers, run AI or simulate hydraulics.

Only properly crossing boundary edges enter `crossed_boundaries`; touching,
overlapping and nearby paths are excluded. `objects` contains the wider linked
candidate inventory. `crossing_object_ids` selects the narrower subset whose
geometry intersects a matched mapped flow and lies within the saved tolerance
of the boundary/path intersection. Per-association distances/intersections,
two GIS/NZTM endpoints, classifications/confidence, dimensions, raw attributes,
reviews and provenance are retained. Geometry-less image components never
inherit a parent's crossing. Stale or concealed labels are not asserted types.

Actual supplied `AC_OLFP_Obstructions.gdb` was inspected read-only: layer
`AC_OLFP_obstructions_20261016`, 1,443 MultiLineString features, EPSG:2193.
Four geometries intersect the pilot bounds; inspected type fields are null.
Normalised all supplied features into the private supplemental JSON, retaining
raw attributes, coordinates, layer identity and per-file hashes. This adds 11
property-linked candidate records across the saved coverage without rewriting
original property records. Missing physical types/dimensions remain unknown.
GDAL emitted an existing PROJ database-path diagnostic during inspection/import;
the reader returned explicit EPSG:2193 and no reprojection was performed.

Actual export: 334 recorded properties / 2,592 edges in the declared scope;
116 properties with 278 crossing boundary records. 266 linked object records:
177 classified, 89 unclassified. 104 are spatially near boundary intersections;
91 also intersect the mapped flow (47 kerbs, 12 buildings, 3 vegetation, 29
unclassified candidates). Nine image components have unresolved GIS positions.
Zero record-read errors. These are property-scoped records, not guaranteed unique
physical objects across neighbouring properties. No administrative suburb polygon
is verified: coverage is the available Mt Albert/Sandringham pilot plus confirmed
Mount Albert samples, NOT all Mt Albert properties or objects.

Focused verification: `python -m pytest /tmp/test_crossing_export.py -q` in the
existing local container: 9 passed. Fixtures check proper crossing vs touch/
overlap/proximity, GIS geometry, near-vs-far linked objects, source types without
invented confidence, deduplication within a property, unresolved image locations,
stale/manual precedence, supplied null-type features, scope exclusion, cache
invalidation and HTTP JSON. An initial preservation assertion compared in-memory
tuples with JSON lists; changed it to compare original property bytes, then passed.
`node --check web/properties.js`, `node --check web/boundary-editor.js`,
`npm --prefix web run build`, and `git diff --check` passed.

Restarted only `floodtwin-3d-local-review` to load the API route, retaining the
existing environment/mounts. Local HTTP 200, cached export about 0.2 s / 3.7 MB
compact JSON; cold generation reads raw bundles and can take several seconds.
Playwright verified the 3D link and actual website download, parsed the downloaded
JSON, checked counts/subset IDs, and saved
`output/playwright/mt-albert-flow-crossing-objects.json`. Screenshot visually
inspected: `output/playwright/mt-albert-crossing-export.png`.
Server remains at 127.0.0.1:8774. No full suite, remote deployment or hydraulics.

Next: acquire an authoritative suburb extent and additional property/source
coverage before calling this a whole-suburb inventory; independently review
unclassified candidates rather than inventing regional fence/wall labels.

## 2026-10-16 - Executed crossed-only pilot detection and dataset update

User requested actual processing, not another export-only change. Added and ran
`features.crossing_detection.prepare('/work')` in the existing local container.
Selected exactly the imported pilot's properly crossing records: 114 properties,
272 original boundary records, 131 distinct shared edges. No detection was run
for non-crossed edges or the three separate address-confirmed sample records.

Actual sources: the original 4,292,729-return LiDAR tile, verified EPSG:2193 /
NZVD2016 DEM and georeferenced LINZ 7.5 cm aerial. Source SHA256s, geometry,
selection IDs, raw property SHA256s, algorithm snapshot and per-edge native
support are recorded. Withheld and noise-class returns excluded; finite height
QC and outside-building screening applied. Classified vegetation and roof
returns stay separate from ambiguous low unclassified connected runs. Approximate
return envelopes are NOT surveyed physical geometry; point spread is NOT width.
No trained semantic model, model API, new provider imagery or hydraulics was run.

Prepared 11 rotated aerial/profile sheets. The initial square crops were too
small for thin-object review; replaced with edge-oriented strips, regenerated
and inspected all 131 cases on all 11 sheets. SHA256 checks proved the inspected
and final staged sheets byte-identical. Explicit hash-bound review records
partial/missing tile coverage, roadside gaps, canopy occlusion and roof context.
Five native vegetation clusters received authored hedge-like visual refinements;
two pale frontage barriers received provisional fence-like image observations
with low-wall/other alternatives, null object GIS geometry and null heights.
No hidden fabric, material, buried depth or fence crest was invented.

Published run `detection_51ed673cf50e4f33c6b8fb93` to private
`data/property-registry/crossing-detections/<property>.json`. This stores 402
property-linked native object candidate records (188 distinct edge clusters
before duplication across neighbouring properties), plus four property-linked
image-only fence-like components on two shared lines. Native object record types:
285 vegetation, 69 building, 16 visually refined hedge, 32 unresolved. Parent
record types: 133 vegetation, 63 mixed, 16 hedge, 4 provisional fence, 56 unresolved.
All ten field assessments are explicit; unknowns are completed assessments, not
fabricated dimensions. Scores are heuristic/subjective and NOT accuracy validated.
Four-angle Earth + Street View coverage was NOT acquired for 114 properties.

Registry read integration merges only crossed edges and their predicted objects.
Manual reviews still win and existing assistant samples are not rewritten.
Changed property inputs make the new proposals stale; previous detection files
are archived on replacement. Preservation audit: 272 target records checked,
all original property SHA256s match, all 990 non-crossed edges inside the 114
affected records match their originals, zero stale bundles. Other pilot properties
were not written. No original raw property, source or manual-review file changed.

Local map now shows selected-edge detection type/score, object return envelopes,
coverage and recorded evidence image. 3D editor supports the same records when
the property already has a confirmed 3D workspace; no bulk workspace confirmation
was invented. Atlas images use the existing read-only prediction-evidence route
with a validated edge query/path. Export cache invalidates on detection updates.

Focused verification: 34 tests passed in 2.62 s across only crossing detection,
crossing export and existing boundary prediction tests. Covers strict selection,
source class separation, no-return unknowns, native building exclusion, GIS
geometry, manual/stale precedence, exact publication review, archives and
image-only null crossing/geometry. One initial fixture assertion compared Shapely
tuples with JSON arrays; normalised the persisted fixture and reran successfully.
JS syntax checks, frontend build and git diff --check passed. No full suite.

Restarted only local `floodtwin-3d-local-review`; existing env and mounts retained.
HTTP property and correct edge-specific atlas image both return 200. Browser and
file SHA256s match for the E026 evidence image. Playwright selected an actual
hedge edge, enabled actual pilot aerial, displayed its native object support and
loaded the review sheet. Visually inspected screenshot:
`output/playwright/pilot-crossing-detection-hedge.png`.

Playwright downloaded and parsed the updated regional JSON: 278 total crossed
boundary records (272 new pilot assessments plus the prior samples), 672 total
linked objects, 551 classified / 121 unresolved, 278 spatially intersecting mapped
flows near boundary crossings. Object intersection is mapped screening, not
proof of water obstruction. Every new target row has all ten field assessments.
Zero export read errors. Saved refreshed QA download at
`output/playwright/mt-albert-flow-crossing-objects.json`.

Local server remains 127.0.0.1:8774. No remote deployment, training data upload,
hydraulic model or unsupported claim of accurate/complete fence-wall detection.
Next: targeted oblique/street/field review of the 56 unresolved boundary records,
thin image-only barriers and source-coverage gaps before accuracy can be claimed.

## 2026-10-16 - Groundtruth.gdb comparison: no assessed pilot overlap

Read the user-supplied `groundtruth.gdb` without editing it; copied it into the
existing local runtime at `/tmp/flowlab-groundtruth.gdb` for GDAL/pyogrio reads.
One layer: `AC_OLFP_obstructions_20261016`, 1,443 valid MultiLineStrings,
EPSG:2193. Across the GDB, 251 rows have any assessment information and 147 have
non-null Landscape_Structure text. Actual coded domains: Fence_Wall_Obstruction,
Contour and Building 0=None, 1=Low, 2=Medium, 3=High; these are not semantic
fence/wall IDs or measured heights. No dedicated height measurement field.

Only four reference lines intersect the pilot, and only those same four intersect
the 1 m corridors around our 131 distinct crossed lines. ALL four have null
structure, obstruction/contour/building assessment, comments and guidance fields.
Zero eligible assessed/type-labelled references overlap the 272-record prediction
scope. Nearest assessed reference is 1,981.97 m from the tile. Thus type accuracy,
detection precision/recall, height error and severity accuracy are null/not
evaluable, NOT zero percent. No empty reference value was treated as a negative.

Verified reference IDs/geometries: all 1,443 match the previously imported
supplemental source snapshot, and all non-length attributes match. The old
AC_OLFP_Obstructions.gdb folder is no longer present; an initial file-name hash
comparison therefore did not demonstrate changed contents. Used saved source
JSON instead and ignored Shape_Length float serialization differences.
Excluded imported source features from predicted detections to avoid scoring
copied reference context. Deduplicated 402 native object records to 188 distinct
geolocated clusters; two distinct image-only components have no spatial match.
Parent cadastral lines are not detected physical objects.

Spatial-only check: all four unassessed reference lines have 100% length coverage
within a 1 m buffer of the union of native detection envelopes. This is location
agreement only; broad vegetation/roof/unknown envelopes do NOT establish correct
fence/wall identification, validated precision/recall or a 100% accuracy claim.
Saved each line's attributes, geometry and 0.5/1/2 m sensitivity results.

Added an offline read-only coverage evaluator:
`python -m floodtwin.validation.groundtruth_check --root /work --groundtruth /tmp/flowlab-groundtruth.gdb`.
Ran it on actual data. Report:
`data/property-registry/evaluations/groundtruth-6163042496be396e/report.json`
and the human-readable `report.md`. Predictions, raw property records and runtime
reference copy hashes all unchanged. No dataset relabelling, source amendment,
confidence changes, model inference, app/API edits, server restart or deployment.
An existing PROJ-path diagnostic was emitted, but the reader returned EPSG:2193
and no coordinate/vertical transforms were made during matching.

Focused verification: `python -m pytest /tmp/test_groundtruth_check.py -q`:
4 passed in 0.49 s. Tests distinguish missing labels from explicit numeric zero,
verify spatial tolerance effects, prevent duplicate coverage inflation and leave
distance null without predictions. `git diff --check` passed. No full suite.

Next: obtain completed pilot reference labels and measured dimensions/assessed
positive-negative coverage, or ask the user to select an assessed area for a new,
separate prediction/evaluation run. Do not invent a numerical accuracy score from
the current zero-denominator overlap.

## 2026-10-16 - Exact four pilot objects: record and visual validation

User retained the current pilot and requested the exact four objects, not an
area change. Read-only OGR check confirmed OBJECTIDs 739/873/874/875 and their
GlobalIDs against the saved spatial report. All semantic/assessment fields on
these exact features are genuinely null, including assessment/obstruction IDs;
no related assessment table was found in the one-layer GDB.

Inspected sibling submission reference schemas and spatially compared its
allfences, detected, structures, v12 export, two manual-check GeoJSONs and
property-impact barrier-check snapshot. Those fence IDs are not our edge IDs.
No manual check overlaps the four GT objects: nearest manual geometries are
23.68/9.10/19.57/30.57 m away. Did not copy nearby fence labels. Sibling CV.md and
README explicitly identify Claude labels as unchecked AI development labels,
not independent truth; manual checks are visual, not field verified.

Using the property-boundary-review skill, rendered and visually inspected four
actual aerial/native LiDAR class/profile plots with exact GT geometry overlay.
Visible interpretations: 739 dense trees/shrubs; 873 tall trees/lower shrubs;
874 narrow clipped hedge; 875 L-shaped hedge around lawn. Authored subjective
type confidence .90/.95/.85/.90 in a separate diagnostic review only. No hidden
fence/wall or physical crest validated. Exact 1 m corridor p95 return heights
5.34/11.80/2.17/2.50 m are vegetation envelopes, not barrier heights. Existing
3.44/3.78 m clusters near 875 cover broader groups than the exact reference.
Saved broad vegetation classifications are plausible but do not certify fence
recognition. No independent semantic accuracy or height-error score available.

Artifacts: output/groundtruth-four/report.md, matches.json, visual-review.json,
four object-N.png evidence plots, inspect_four.py and render_evidence.py.
These remain local/ignored. No exactly matched Street View/oblique set acquired;
excluded a supplied local screenshot with filename 69 but visible house number
86 because its identity with these four reference objects was not established.

Commands: docker exec Python diagnostic and rendering scripts; targeted OGR
OBJECTID/GlobalID/null-field assertions; spatial non-match assertions; hashes of
all 114 saved predictions and the GDB matched the prior report. git diff --check
passed. Existing PROJ-path warning remains; comparisons used verified EPSG:2193
with explicit standard WGS84-to-NZTM transform for sibling GeoJSON. No raw source,
prediction, review or geometry relabelling, app edit, restart, deployment or full
test suite. Next useful validation is matched oblique/street/field evidence of
the concealed physical barriers, rather than treating these visual labels as GT.
