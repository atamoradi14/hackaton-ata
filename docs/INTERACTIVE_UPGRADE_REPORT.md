# Auckland FlowLab interactive upgrade — 15 October 2026

Implemented, validated and **deployed to https://daryajan.com** after explicit
deployment authorization. This is a working exploratory
property workflow, not a calibrated or converged flood-risk model.

**Earth studio follow-up:** deployed and verified on 15 October 2026 after the
user's firewall update restored SSH. Production runs `earth-20261015-r1`, image
`sha256:c070767824173f4bf696b9d06478459f09baa3ac5240507df82e9f98e44c7adb`.
The 1.1 GB stopped-app workspace backup and prior image references are retained
under `/opt/auckland-flowlab-deploy/releases/earth-20261015-r1/`; all 28 recorded
native artifacts retained their SHA256. Public APIs and browser checks passed
Earth rendering, shared 1200/1800 s playback, depth/velocity and signed comparison,
source dates/provider checks, and 390×844 mobile without horizontal overflow.
The release passed 55 Python tests plus GLB geometry checks. Google remains
intentionally disabled; actual Google coverage/clipping/alignment awaits a key.
Private evidence: `reports/earth-production-release.json`,
`reports/earth-production-validation.json` and `output/playwright/earth-production-*`.
See how-to-deploy.md for current release and Google enablement commands.

## Earlier interactive production deployment

The existing Helsinki k3s namespace `auckland-flowlab` now runs
`docker.io/library/auckland-flowlab-app:interactive-20261015-r1` in both `app`
and `prepare-volume`. Image ID/index digest:
`sha256:ed573b3a361ba3403ff28a4516f8194dc2cacbec0dafc9e34d4772520c948e50`.
The transferred archive SHA256 was verified before import. A stopped-app,
consistent full workspace backup and previous deployment/image references are
retained under `/opt/auckland-flowlab-deploy/releases/interactive-20261015-r1/`.
All 20 recorded native map/history/replay/manifest artifacts retained their SHA256.
The previous `rename-20261015` image remains available for rollback. Existing
provider Secrets, TLS/Caddy, PVCs and resource settings were preserved.

The release image passed 50 tests. Public verification passed health, scene v6,
recorded aerial PNG, all three saved demonstration runs, native rainfall/wall
replays and comparison (+0.038 m / −0.037 m; 5,056 m² changed by at least 1 mm),
foreign-origin POST rejection and unknown-workspace rejection. Production
Playwright checks passed same-time 2D swipe, split 2D/3D, shared 1200/1800 s
timeline, velocity layer, mobile 390×844 without horizontal overflow, and evidence
modal. The only browser console errors were the existing Cloudflare analytics
beacon blocked by the app's self-only script CSP; app scripts/rendering passed.

Private evidence: `reports/interactive-production-validation.json`,
`reports/interactive-production-release.json`, and screenshots
`output/playwright/production-{swipe,split,velocity,mobile,evidence}.png`.
No new production solver job or wall edit was used for deployment verification.
Step-by-step commands and rollback are in [how-to-deploy.md](../how-to-deploy.md).

## Original problems and findings

- The homepage was an evidence dashboard; actual site results, rainfall controls
  and hypothetical walls existed only in the separate studio. Preparation at
  100% did not indicate a hydraulic result, and the homepage always said not run.
- The 3D water mesh rebuilt geometry/materials every frame and joined triangles
  when any corner was wet, bridging predicted dry cells. The main map had no
  actual hydraulic overlay. Wall geometry was not restored when selecting runs.
- The roof pipeline retained the highest return per voxel and checked only a
  triangle centroid against a footprint. That admits isolated high returns and
  triangles spanning footprint holes or concave gaps. Unsupported DSM roofs
  could contain canopy/boundary artifacts.
- Terrain triangle winding and aerial UVs were already consistent with the
  NZTM crop; they did not need an arbitrary terrain smoothing rewrite. The new
  homepage aerial overlay additionally reprojects the NZTM image to Web Mercator,
  instead of stretching its geographic diagonal corners.
- Old input manifests matched `sfincs.*`, omitting `sfincs_subgrid.nc`. New runs
  hash that table too. Comparison checks actual input bytes, including older
  subgrid files, and allows only diagnostic observation-file differences and
  wall configuration differences.
- Site outputs expose cumulative precipitation, infiltration and signed subgrid
  storage, but no integrated external boundary budget. Negative signed subgrid
  storage exists. Connected domain, drainage and building runoff remain uncertain.

## Delivered journey and exact files

The existing address confirmation, file-backed workspaces, native solver,
evidence layers and full-screen studio are retained.

| Files | Change |
| --- | --- |
| `web/index.html`, `web/app.js` | Persistent workspace; 2D/3D/split selection; preparation event; URL/session restoration; evidence modal |
| `web/workspace.js`, `web/workspace.css` | Saved scenarios, actual map cell rendering, legends, playback, point inspection, rainfall review, async runs, wall editor/persistence, differences, before/after switch, same-time 2D swipe and GIS export |
| `web/hydraulic.js` | Shared depth palette and depth/surface/velocity/difference layer calculations |
| `web/scene.html`, `web/scene.js`, `web/studio.css` | Embedded shared state; restored scenario walls; independent wet-cell water quads and reusable GPU buffers; dry mask; retained PNG/GLB exports; approximate-roof labels |
| `src/floodtwin/api/server.py`, `workspace.py`, `assets.py` | Scoped spatial/wall/comparison/aerial APIs; gzip; serialised HDF5 reads; atomic saves; explicit worker cwd; georeferenced aerial derivative |
| `src/floodtwin/hydraulics/results.py` | Native hash and every-frame replay checks; physical grid coordinates/masks; native maxima; compatible comparisons; signed budget diagnostics |
| `src/floodtwin/hydraulics/site.py` | 2–12 vertex finite weirs; complete input hashes; restoration of cwd across the model lifecycle |
| `src/floodtwin/hydraulics/quality.py` | Dry, closed-rainfall, endpoint-bypass and reversed-orientation native fixtures |
| `src/floodtwin/terrain/scene.py`, `roofs.py` | Roof outlier/triangle/coverage QA; approximate fallback geometry; atomic version-6 cache |
| `tests/test_result_contract.py` | Native values, masks, comparisons, corruption, polylines, roof QA, imagery and cwd regressions |
| `Dockerfile` | Include shared hydraulic module in frontend build stage |
| `README_ARCHITECTURE.md`, `README_METHODOLOGY.md`, `README.md`, `PROGRESS.md`, this report | Contracts, evidence, scientific limits and operational handoff |

`web/style.css`, solver release, source terrain, Kubernetes limits, secrets and
production configuration were preserved. No private geodata, credentials, native
outputs or screenshots are committed. Source data and results remain ignored.

Wall points use east/north metres relative to the verified NZTM origin, with
absolute NZVD2016 crest elevations. Ground is sampled through pyproj/rasterio,
not screen-pixel guesses. Users draw 2–12 vertices, drag handles, review crests,
disable/delete walls, and save/reload them. Multiple separate polylines can
represent gaps. Pending edits are clearly distinct from immutable saved water.

## Hydraulic evidence

No parameters were altered to increase visual flooding. Added validation does
not establish increased field accuracy.

| Evidence | Result |
| --- | --- |
| Native synthetic suite | 12/12 cases passed |
| Maximum relative closed-fixture mass error | 5.960464477539063e-8, against 0.005 tolerance |
| Closed rain tank | 20 mm/h × 1 h × 400 m² = 8 m³; native final 7.99999982 m³ |
| Dry control | Zero depth and zero storage |
| Finite crest | Below-crest blocking and above-crest overtopping passed |
| Finite endpoint gaps | Approximately 20 m³ transferred around the ends in the below-crest fixture |
| Reversed wall orientation | Maximum compartment difference 1.19209290e-7 m |
| 1 m versus 2 m synthetic cells | Maximum compartment difference 0.000329673 m |
| 0.25 s versus 0.5 s maximum time step | Maximum compartment difference 0.000114650 m |
| Fresh Bayview repeat | Every displayed depth matches existing baseline at 1 mm precision |
| Bayview 1,200 m versus 800 m domain | Up to 0.525 m change; mean 0.000379792 m in the central crop |
| Bayview 8 m versus 4 m grid | Up to 1.09 m; mean 0.018722501 m after common-active block averaging |

The site domain/grid sensitivity tests fail any claim of convergence. The grid
comparison includes changed obstacle rasterisation and cell-bed definitions; it
is not a controlled wall comparison. Individual local changes can be large even
when a domain-wide average is small.

Native baseline precipitation is 14,349.8758 m³; infiltration is zero; final signed
storage is 4,779.3796 m³. Up to 6.5546 m³ of negative signed storage occurs. The
analytic rainfall estimate in the original report is slightly different because
of output integration/precision. Rainfall minus storage cannot be relabelled as
measured outflow. External inflow/outflow and exact closure remain unavailable.

## Baseline versus wall

The saved baseline and wall use the same rain (50 mm/h for 30 minutes, followed
by 30 minutes dry-down), roughness, losses, grid, terrain and subgrid tables.
Observation probes differ and do not affect the hydraulic model.

Native solver-step maximum depths change by **+0.038 m / -0.037 m** in the central
320 m crop. **5,056 m²** changes by at least 1 mm. Difference of maxima of saved
minute frames gives a different statistic: +0.056 / -0.053 m and 6,672 m². The
maximum absolute change in sampled peak speed is approximately **1.343 m/s**.
The application exposes actual same-timestamp depth changes separately.

A new wall drawn using three map clicks, saved, reloaded and submitted through
the homepage completed SFINCS successfully. The native history records **10
snapped structure faces**, eastings 1751726–1751762 m, northing 5928133 m, and
interpolated crests 10.59048–18.54187 m NZVD2016. Its peak-change metrics matched
the saved wall case. Native final signed storage is 4,779.5105 m³, only about
0.131 m³ above the baseline. Similar total storage plainly does not eliminate
local effects.

No selected wall is classified as a verified physical structure. Changes near
neighbouring land are visible; no legal or safety classification is inferred.
Dedicated upstream/downstream transect budgets, parcel statistics and robust
arrival-time diagnostics remain future work.

## End-to-end checks and screenshots

The Python suite passes 50 tests locally. A locked NumPy/netCDF4 import emits one
ABI-size warning; it remains documented rather than hidden. JS syntax and bundle
builds pass, and the full Docker image builds. Container checks are recorded in
`reports/upgrade-container-tests.log` and `reports/upgrade-container-smoke.json`.

An isolated confirmed local Bayview workspace reused matching real prepared data
and copies of the existing native runs. Original native outputs were not replaced.

- Desktop 1440 × 900 and mobile 390 × 844: map workspace, saved selections,
  collapsible panel, depth/maximum/surface/velocity controls, comparison and
  shared 2D/3D seeking were exercised with Playwright.
- Map and 3D show the same 1,800 s frame. Actual wet cells render at their native
  water-surface elevation; below-ground portions are occluded by measured terrain.
- Three-vertex wall drawing, saved reload and solver submission passed. Native
  output proves correct finite-weir encoding. The map swipe uses separate clipped native canvases for baseline and modified values,
with shared camera/time. Wall outlines are hidden during swipe to avoid applying
the proposal visually to the baseline. Before/after scenario switching
  preserves time and updates scenario walls.
- Wall and comparison GeoJSON downloads were read using GeoPandas/GDAL. WGS84
  horizontal coordinates and valid, non-empty geometries were confirmed.
  NZVD2016 crests are explicit properties, with a JSON string profile for GIS
  readers that do not support numeric-list fields. No incorrect ellipsoidal Z.
- Roof QA rejected 764 points and 3,102 triangles in this crop, retaining 26
  native roof meshes. Unsupported footprints use labelled approximate roofs.
  Some roof detail remains incomplete; aerial vegetation remains in the photo.
- One initial homepage run failed from an invalid inherited working directory;
  explicit worker cwd and lifecycle restoration fixed it. Failed artifacts were
  preserved, and the fresh rerun completed. Earlier test-harness timing/selector
  issues were corrected and did not create substitute results.

Private screenshots are in ignored `output/playwright/`:

| Before | After |
| --- | --- |
| [Homepage](../output/playwright/before-public-home.png) | [Main workspace](../output/playwright/after-home.png) |
| [Studio](../output/playwright/before-studio.png) | [Studio](../output/playwright/after-studio.png), [shared water view](../output/playwright/after-3d-water.png) |
| — | [Comparison](../output/playwright/after-comparison.png), [swipe](../output/playwright/after-swipe.png), [split view](../output/playwright/after-split.png) |
| — | [Mobile map](../output/playwright/after-mobile-map.png), [wall editing](../output/playwright/after-wall-edit.png) |

Logs and numerical evidence remain in ignored `reports/upgrade-*`,
`runs/quality-upgrade-20261015-v2/validation.json`, and fresh `runs/site-upgrade-*`.
PNG export passed. The 16 MB GLB is version 2 with 146 meshes and 291 finite VEC3 accessors.

The local review workspace is available at
http://localhost:8769/?job=73cc00b4dc474fb99186ae5e882e6fa5.

## Performance and security

No infrastructure was added. Solver jobs remain subprocesses with one processing
slot; saved outputs remain file-backed. Rain replay is roughly 4.7 MB uncompressed;
gzip reduced a real replay to about 972 kB in the container check. The map draws only 6,400 cropped computational cells.
The studio reuses position/colour/index buffers, omits inactive/dry cells, caps
pixel ratio at two, and caches comparison data. GPU water buffers are roughly
1 MB. Large native reads are serialised; geometry caches are reused. The 1,200 m
local domain run took about 179 s, the repeat about 87 s, and the 8 m run about
35 s. These are workstation timings, not measured k3s performance guarantees. A local container limited to 1.5 CPU and 2 GiB
served the native replay in 3.01 s, passed compatible comparison and origin/workspace
denial checks, and used about 174 MiB at the sampled idle point. This is not a peak
solver-memory measurement.

The app remains public without per-user ownership, as previously configured.
No cross-workspace result enumeration was added. Workspace/run grammar, exact
site IDs, host/origin/token checks, export allowlists and native hashes are
preserved. The existing 4 KiB POST limit can constrain large multi-wall submissions
before the nominal ten-wall/twelve-vertex maximum; it was not increased silently.
No keys or private provider responses are exposed by the new APIs.

## Deployment readiness and rollback

Production is unchanged. The image is built locally under
`auckland-flowlab-app:interactive-20261015-review`; test/build evidence is in
`reports/upgrade-image-build.log` and `reports/upgrade-container-tests.log`.
Do not treat image build or fixture passes as site-model certification.

Before an explicitly approved production deployment:

1. Wait for the existing processing slot to be idle. Record the current app image,
   active namespace/configuration and PVC references. Back up the workspace PVC
   and preserve the old image; do not delete or prune volumes.
2. Build/import the final reviewed image into the existing single-node k3s image
   store (manifests use `imagePullPolicy: Never`). Keep current limits, mounts,
   credentials, Caddy configuration and public routing unchanged.
3. Update only the app container and its `prepare-volume` init container image
   in `auckland-flowlab-app`, namespace `auckland-flowlab`. Validate locally first;
   do not substitute a registry tag that the node cannot resolve.
4. Check readiness, existing saved rain/wall loads, comparison, same-timestamp 3D,
   mobile layout, host/origin denial and exports. No fresh production hydraulic
   run is required merely to test saved-result rendering.
5. If checks fail, restore both app/init image references to the recorded previous
   image and wait for rollout readiness. Retain all native run directories and
   workspace/PVC contents. A compatible scene cache can regenerate; never replace
   native outputs as a rollback action.

## Remaining scientific/product work

Exact site boundary flux closure; diagnosis of signed storage artifacts; connected
catchment selection; further domain/grid convergence; approved time-varying HIRDS
storms; measured wall surveys/openings/porosity; verified roof runoff and drainage
inputs; qualified field calibration; parcel/transect summaries; progressive scene LOD and camera transitions;
additional device/GPU testing; per-user ownership if public multi-user isolation is
required. These are explicitly not claimed complete by this revision.
