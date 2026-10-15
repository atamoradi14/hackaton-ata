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
