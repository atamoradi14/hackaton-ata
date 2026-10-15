# Auckland Property Flood Digital Twin — Codex Master Implementation Plan

**Target address:** 61 Pemberton Avenue, Bayview, Auckland, New Zealand  
**Purpose:** A reproducible, locally runnable, property-centred **research prototype** for rain-on-grid, overland hydraulic flow, physical barriers and drainage sensitivity.  
**Status:** Design specification only. No property geocoding, dataset download, calibrated modelling, or risk classification has yet been performed.  
**Do not use outputs for safety decisions, engineering design, resource consent, property sales, insurance or claims about an individual property's flood risk without qualified hydraulic-engineer review.**

## A. Non-negotiable scientific principles

1. **Actual water flow vs flow accumulation:** GIS D8/D-infinity flow direction, tracing and catchment accumulation are preliminary screening, not hydraulic simulation. Production hydraulic results must come from an actual 2D hydrodynamic solver with rainfall/inflows and time integration (prefer SFINCS). All images must distinguish screening from modelled depth/velocity.
2. **Hydrologic continuity:** Do not crop flow to the target cadastral parcel. Determine all relevant upstream contributing areas, potential downstream outlets, and linked drainage paths; extend model domain until the upstream/downstream boundaries cannot artificially dominate the target property. Provide sensitivity to domain size.
3. **Terrain:** Bare-earth DEM is the default elevation base. Do NOT directly simulate surface flow over the unfiltered DSM (trees/roofs will create spurious dams). Add buildings, walls, kerbs, other verified features with dedicated structure/breakline modifications. Preserve genuine embankments/terrain discontinuities.
4. **Data provenance:** Every elevation/rainfall/barrier/drain input must carry source URL, survey date, datum, accuracy, data license, preprocessing actions, uncertainty and status: `measured`, `official_map`, `inferred`, `assumed`, `missing`.
5. **Vertical datum:** Horizontal NZTM2000 EPSG:2193, vertical NZVD2016. Some Council legacy layer descriptions specify NZVD1946/local Auckland 1946 datum. Never mix absolute levels without converting using official LINZ relationship grids, checking actual asset-level datum, and recording the conversion; do not apply arbitrary 0.3 m constants. GIS geometries with no Z should never be assigned elevations implicitly.
6. **Asset incompleteness:** Open-data stormwater lines/pits are indicative, not a surveyed complete pipe network. Private drainage, culverts, inverts, outlets and blockage state may be missing. If essential information is missing, use explicitly labelled bounded *what-if* scenarios or mark the feature `unmodelled`; never silently invent pipe dimensions, wall heights or drain capacities.
7. **Porosity:** Solid retaining walls can behave as overflow structures (finite crest). Paling, open, chain-link and mesh fences differ; treat unverified fence porosity as uncertainty, not as a solid wall. SFINCS infinite `thin_dam` should only represent a deliberately hypothetical fully impermeable, non-overtoppable barrier; prefer finite-height weirs for real solid walls.
8. **Reproducibility:** Offline synthetic tests must pass without real data/API keys; no hardcoded fake Auckland data shall be presented as real. Model inputs and output hashes, solver version, parameters and logs should be saved.
9. **Security & privacy:** Keep API keys only in environment variables. Do not upload personally sensitive imagery, private council hackathon data, the target resident's identity or proprietary datasets to online AI tools or public repos. Public data licensing and Council hackathon rules must be respected. Default project local/private.
10. **No unsupported flood-risk verdict:** Reports may explain modelling results and assumptions; do not assert the property is safe/unsafe, definitively flood-prone/not flood-prone, or recommend structural changes without professional validation.

## B. Target user journeys

1. Enter an address; resolve a verified LINZ address point + associated cadastral parcel, show match provenance and ask user to select if ambiguous.
2. Display aerial background, parcel, building footprints, LiDAR-derived terrain, Council overland flow and flood layers, catchpits and stormwater network.
3. Select upstream contributing area and a model domain automatically, with manual adjustable extents. Display all outlet/boundary assumptions.
4. Build baseline hydraulic simulation for a named design rainfall scenario; run, inspect diagnostics, depth over time, maximum depth/velocity, flow paths and hydrographs.
5. Add/edit an **explicitly measured or hypothetical** retaining wall/fence with crest elevations and type, plus optional culvert or permeability assumption.
6. Compare baseline vs altered-wall or drainage case: maps of `delta_max_depth_m`, property-mask wetting, flow direction, peak depth, peak velocity, ponding duration, arrival time and upstream/downstream impacts.
7. Drill down into a parcel with 2D plan and 3D terrain/water visualisation; identify measurement uncertainty and missing inputs.
8. Export GeoJSON/GeoTIFF/CSV/NetCDF and a human-readable provenance+assumptions report.

## C. Reliable public source manifest

### Auckland Council ArcGIS FeatureServer layers
Base: `https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/`

- Overland flow paths: `Overland_Flow_Paths/FeatureServer/0`
  - public displayed layer is a **simplified** line service; do not assume it includes all upstream flow and TP108 attributes mentioned in the description. 2016/17 terrain used in 2019 remapping; not equivalent to 2024 LiDAR or a validated 2D model.
- Flood plains: `Flood_Plains/FeatureServer/0` (verify service availability during ingestion).
- Flood-prone areas: `Flood_Prone_Areas/FeatureServer/0` (verify).
- Stormwater pipes: `Stormwater_Pipe/FeatureServer/0` (verify the service resolves, support casing `ArcGIS/rest` too).
- Stormwater catchpits: `Stormwater_Catchpit/FeatureServer/0`.
- Stormwater manholes: `Stormwater_Manhole_And_Chamber/FeatureServer/0`.
- Stormwater connections: `Stormwater_Connection/FeatureServer/0` (verify).

**Acquisition algorithm:** HTTP GET layer metadata (`?f=pjson`); inspect fields, type, geometry, maxRecordCount, supportsGeoJSON and query abilities; query by `esriGeometryEnvelope` in EPSG:2193 with `spatialRel=esriSpatialRelIntersects`; request `outFields=*` but preserve unknown columns; paginate with `resultOffset` / `resultRecordCount` if supported or use `returnIdsOnly=true` + ID batches; check `exceededTransferLimit`; retry 429/5xx with backoff; cache raw responses and provenance. Use `outSR=2193`, output GeoJSON only if supported and cross-check CRS, otherwise convert EsriJSON with a validated converter. Sanity check zero-result queries without inferring nonexistence. Explicitly note date/time metadata and potential vertical datum heterogeneity.

### Toitū Te Whenua LINZ Data Service
- NZ Addresses — address-point matching; confirm official address including 61 Pemberton Avenue.
- NZ Primary Parcels (`https://data.linz.govt.nz/layer/50772-nz-primary-parcels/`) and/or Property Boundaries — different parcel types; do not treat as accurate surveyed fence location.
- NZ Building Outlines (`https://data.linz.govt.nz/layer/101290-nz-building-outlines/`).
- Auckland 2024 1 m DEM and DSM (Parts 1/2; **determine which covers the target via index tiles, do not guess**).
- Auckland 2024 point cloud LAS/LAZ tiles, through OpenTopography or LINZ tile index. Start with local crop only.
- NZ national 1 m DEM `https://data.linz.govt.nz/layer/121859-new-zealand-lidar-1m-dem/` and corresponding DSM; confirm newest source survey and capture date.
- Auckland urban aerial 0.075m imagery 2024–25 if the target lies inside coverage; aerial imagery may not show the ground beneath canopy.
- Online access: LINZ LDS web service usually needs a **user-created LINZ API key**; implement `.env` with `LINZ_API_KEY`, never check it in. Public NZ Elevation S3/STAC and OpenTopography offer alternatives. See `https://www.linz.govt.nz/guidance/data-service/linz-data-service-guide/web-services/creating-api-key`.
- Elevation: `https://nz-elevation.s3.ap-southeast-2.amazonaws.com/catalog.json`, `https://portal.opentopography.org/` and LINZ layers.
- Geodetic conversion resources: `https://www.linz.govt.nz/guidance/geodetic-system/understanding-coordinate-conversions/height-datum-conversions/vertical-datum-relationship-grids`.

### Rainfall, runoff, soils and local conditions
- Design rainfall from NIWA/Earth Sciences NZ HIRDS: `https://niwa.co.nz/climate-and-weather/high-intensity-rainfall-design-system-hirds` for site-specific depths/durations; must derive a documented hyetograph with a chosen temporal pattern, not invent HIRDS values. Check licence/access.
- Council 1% AEP floodplain extent and 2/10/100yr historical flow attributes if Ajay supplies them; **comparison is conditional** on consistent storm/assumptions.
- Impervious surfaces/land cover, infiltration/soil type, stream channels, bridge and road crossings, drainage/culvert details, tide/outfall levels if hydrologically connected: search legitimate public GIS catalogues; missing => assumptions with sensitivity, no invented data.
- Property-specific fence/retaining wall height and openings: site survey/user measurements/photos with consent, plus manual feature verification.

## D. Work packages and acceptance tests

### WP0 — Environment, provenance and fixture
- Native Windows frontend + WSL2 Linux backend (or Docker) on the existing workstation; Python versions compatible with current SFINCS/HydroMT release; do not assume any untested version combination.
- Structure: `src/floodtwin/{providers,geo,terrain,features,hydrology,hydraulics,scenarios,validation,api,visualization}`; `data/{raw,interim,processed}` `.gitignore` and `data/manifest.json`.
- CLI `floodtwin doctor`: check geospatial deps, solver executable (`sfincs`), optional PDAL, CRS handling, API keys, disk/RAM, endpoint status. Reports dependency blockers honestly.
- Deterministic synthetic **2x2 or sloping channel** fixture and tests bundled in Git.
- AC: `pytest` passes in offline fixture mode; no secret or large raw data staged for Git.

### WP1 — Verify address and select domain
- Resolve user address via LINZ NZ Addresses; normalize address and require exact street/suburb match. Store point `lonlat` EPSG:4326 and NZTM point EPSG:2193. Join to parcels using reliable spatial intersection/nearest and flag ambiguity; visual verification required.
- Build initially ~1–3km discovery window but compute hydrological upstream catchment and downstream outlet; adapt final model extents by connectivity, not a fixed radius or property polygon.
- Use stream/road/catchpit/outlet locations to identify possible artificial pathways and boundary complications.
- AC: actual address confirmation, a selected parcel polygon and a domain polygon are saved; if address not resolved, stop rather than assign a guessed coordinate.

### WP2 — Ingest, spatial QC and metadata
- Download only a bounded area including buffer and relevant tile intersections; Council ArcGIS pagination and LINZ clipping. Cache originals immutable with SHA256 and timestamp.
- Validate CRS of every layer; determine horizontal and **vertical** datum separately. Record any vertical transform and precise grid used.
- Geometry checks: valid, non-empty, projections, duplicates, invalid self-intersections, orphan network endpoints. Units metres, no mismatched degrees/metres.
- Raster checks: DEM and DSM coverage, nodata, same grid/resampling, source acquisition date, vertical outliers, tile edge effects, hole fill method; avoid interpolation across unsurveyed wall gaps.
- AC: layer status table `{available, missing, blocked, unsuitable}`, assets by source, a map with no silently substituted layers.

### WP3 — High-fidelity terrain model
- Ground elevations from **bare-earth DEM**, not direct DSM. Use DSM-DEM to flag above-ground heights. Process raw LAS/LAZ for selected candidate structures using PDAL/laspy and surface profiles; use labels such as `candidate`/`confirmed`.
- Buildings: model footprint blockage or raised no-flow cells, with optional entry/door openings only when supported by evidence; mesh treatment must maintain flow around structures.
- Roads/kerbs/driveways and retaining walls: model fine breaklines or terrain edits; choose resolution adaptively; 1 m DEM alone will not reliably resolve a 10-cm fence.
- Vegetation: do not automatically turn high DSM vegetation into a solid wall; reflect effect in roughness/uncertainty where appropriate.
- Explain original DEM may embed some earth structures: avoid double-adding an existing wall or embankment.
- AC: elevation cross-sections, 3D terrain preview, QA flags on anomalies, reproducible change layers.

### WP4 — Detect + register candidate obstacles
- Candidate process: aerial+DSM-DEM segmentation, straight/linear signatures, LiDAR point cross-sections, proximity to parcel boundaries, intersections with flow paths. Exclude buildings and obvious tall vegetation; use manual edits with provenance.
- **Do not assume every cadastral boundary has a fence.** Boundary positions are not the physical fence geometry.
- Feature schema: id, LineString EPSG:2193, category (solid_retaining_wall, solid_fence, permeable_fence, hedge, kerb, building_edge, unknown), base elevation, crest elevation, crest_source, length, thickness if measured, permeability category, gaps/openings, survey date, confidence, reviewer, source URLs, assumption flag.
- For finite-height solid walls: represent as SFINCS weir or carefully validated terrain/breakline with correct crest; not as an infinitely high thin dam unless clearly labelled extreme sensitivity case.
- AC: on-screen edit + confirm/reject. Unknowns cannot automatically become verified hydraulic structures.

### WP5 — Rainfall and catchment hydrology
- Read HIRDS depth-duration-frequency for exact geocoded location. Build documented design hyetograph (e.g., 10%, 1% AEP candidate, plus shorter high-intensity event; durations chosen after catchment travel-time analysis). Export CSV (timestamp, mm/hr) with source citation and units.
- Test storm duration sensitivity, antecedent wetness, runoff losses, rain spatial uniformity, imperviousness and infiltration (Green-Ampt/Curve Number/constant if supported; record parameter provenance).
- If catchment extends beyond local model, calculate time-dependent upstream inflows from watershed approach or extend domain; no unaccounted artificial rainfall losses.
- AC: rainfall mass totals analytically checked; runoff assumptions clearly labelled and tested.

### WP6 — Stormwater pipe network
- Geospatial network: catchpits/manholes connected by pipes/culverts; distinguish asset connection vs geometric near-neighbour. Extract dimensions, length, material, invert/cover/grate levels, status, outfall locations only where attributes exist and are reliable. Asset horizontal positions indicative.
- Three base drainage scenarios: `no_drainage_extreme`, `assumed_partial_drainage`, `verified_asset_drainage` (only if enough measurements). Add blocked inlet/catchpit sensitivity to each.
- Do not delete surface water at an inlet without routing it to a verified downstream outlet or explicitly accounting for a prescribed sink and missing downstream balances. Store transfer volumes and downstream surcharge/backflow assumptions.
- SFINCS latest documentation supports internal drainage/culvert structures; these are **simplified point-to-point transfers**, not a fully resolved 1D pressurised pipe network. Upgrade later to dynamic SWMM coupled 1D-2D **only after a tested coupling interface**, with mass-balance synchronization and consistent heads/datum. Do not label simplified drains as SWMM coupling.
- Coastal/tidal receiving water: assess whether the selected outlet or downstream domain is tide-controlled; add downstream time-dependent water level only with verified source and applicable datum.
- AC: topology plot, unresolved nodes table, conservation check of stormwater transfers, scenario provenance.

### WP7 — 2D hydraulics with SFINCS
- Prefer a known-compatible HydroMT-SFINCS version for input construction, plus separately installed compatible SFINCS executable; `hydromt_sfincs` **does not bundle** the solver itself. Pin package/executable versions and digest. Choose stable versions, or explicitly document pre-release use.
- Model continuous water motion under rain-on-grid and boundary inflows. Grid/resolution: evaluate 1–2m fine target zone and larger coarser contributing region via supported subgrid/quadtree approaches, constrained by data resolution, solver compatibility, timestep stability and resource budget. Do not simply upsample 1m raster and claim 0.25m new measurement resolution.
- Represent barriers using finite weirs and/or resolved elevation; include gaps or permeability assumptions as alternate scenarios. Use SFINCS `thin_dam` solely for a labelled infinitely blocking hypothetical sensitivity case.
- Scenarios: baseline (`as_observed` only for genuinely confirmed structures), add_wall, remove_wall, lower_wall, solid_vs_permeable_fence, inlet_blocked, drainage_partial, drainage_available, high_rainfall. Limit combinations for fast execution.
- Boundary: follow catchment extents, outlet levels, natural flow; no closed boundaries forcing spurious ponding at property.
- Track max depth, max velocity, duration above depth threshold, time of first wetting, water-level time series, flux over chosen transects, volume budgets.
- AC: solver starts/finishes with exit status 0, no NaN/negative depth beyond numerical tolerance, diagnostic mass-balance error below defined documented tolerance, stable timestep/checks; reproducible fixture.

### WP8 — Property metrics and explainability
- For target parcel and all affected downstream parcels, compute `max_depth_m`, `max_speed_mps`, `peak_time`, `wet_area_m2`, `wet_duration_min`, `delta_*` by scenario; do not report fabricated indoor flooding. Building entry thresholds unknown -> `not_assessed`.
- Surface velocity vector arrows based on solver output only. Flow lines from GIS always labelled `terrain-derived` not actual transient streamlines.
- Flag barrier candidate origin (`detected`, `reviewed`, `surveyed`), confidence, whether above LiDAR resolution or datum error, which storm scenario controls effect, and downstream tradeoffs.
- AC: comparison report has no unsupported flood-risk grade; every numeric result traceable to a particular solver run and inputs.

### WP9 — Frontend and 3D visualisation
- MVP Streamlit or FastAPI + MapLibre. Add PyVista/VTK for cross-sections/3D, or deck.gl terrain mesh if web view desired.
- UI: address search, data-source readiness dashboard, base aerial, parcel+flow+stormwater, LiDAR height profile, adjustable modelling domain, rainfall scenario, active barrier edits, run status, 2D water depth time slider, 3D water surface, before/after slider, flood-difference map, validation status and uncertainty list.
- All 3D visualizations must use actual terrain and hydraulic outputs; schematic demos must be WATERMARKED `synthetic demonstration`.
- AC: on clean machine read-only explore existing runs with no need to re-simulate, export reports, clear caveats.

### WP10 — Model quality and validation
- Synthetics: planar slope expected outflow, blocked channel raises upstream water with appropriately modelled overflow, hydrostatic still water, zero rainfall/zero inflow is dry (unless initial water), conserve injected rainfall minus infiltration/flow/sinks.
- Compare baseline Council-published floodplain only if scenario (AEP, rainfall pattern, drainage assumptions and datum) matches; disagreement explained, no unsupported accuracy score.
- Use historical flood observations, recorded marks, site photos, surveyed crest heights, LiDAR elevation cross-sections, Council experts for ground truth when accessible.
- Run sensitivities to: vertical LiDAR ± published accuracy envelope (where applicable), wall height uncertainty, drainage blocked/open/partially functioning, Manning roughness, infiltration, storm duration, boundary extent and timestep/cell size.
- Reports must show preliminary/not calibrated/not engineering certified if site observations and asset measurements absent.
- AC: QC HTML/Markdown/JSON summary with completeness score, limiting factors, quantitative conservation and convergence tests; label why each validation cannot be performed.

## E. CLI, API and acceptance expectations

Design executable commands (implement exact syntax in CLI rather than leaving mock flags):

```bash
floodtwin doctor
floodtwin resolve-address --address "61 Pemberton Avenue, Bayview, Auckland"
floodtwin fetch --config configs/local_site.yaml --layers all --bbox-from-domain
floodtwin qc --config configs/local_site.yaml
floodtwin build-domain --config configs/local_site.yaml
floodtwin detect-obstacles --config configs/local_site.yaml --interactive-review
floodtwin build-hydraulics --config configs/local_site.yaml --engine sfincs
floodtwin simulate --scenario baseline --config configs/local_site.yaml
floodtwin simulate --scenario wall_added --config configs/local_site.yaml
floodtwin compare --baseline baseline --alternate wall_added
floodtwin report --site 61-pemberton --format html
floodtwin serve
pytest -q
```

The commands are **target CLI requirements**, not commands that are currently implemented. Start with synthetic fixture to prove end-to-end works; integrate public live sources incrementally. Scripts must fail clearly with a documented reason when requisite inputs are unavailable.

### Model output contract

`runs/<run_id>/`:

- `run_manifest.json`: inputs SHA256, source, permissions, executable versions, dates, CRSs/datums, variable units, assumptions, solver config and environment.
- `inputs/`: immutable model inputs/links.
- `outputs/depth_max.tif`, `velocity_max.tif`, `depth_timeseries.nc`, `arrival_time.tif`, `delta_depth_max.tif`, `parcel_summary.geojson`, `barriers.geojson`, `stormwater_connections.geojson` (if modelled), `mass_balance.json`.
- `reports/overview.html`, `reports/validation.md`, `reports/uncertainty.json`.
- No fictional result values; all outputs generated only when actual model has run.

### Scenario schema (illustrative)

```yaml
site:
  address: "61 Pemberton Avenue, Bayview, Auckland"
  require_address_confirmation: true
  horizontal_crs: "EPSG:2193"
  vertical_datum: "NZVD2016"

model:
  hydraulic_engine: sfincs
  initial_resolution_m: 2.0  # pilot; evaluate against 1m source and 1-2m zone
  domain_mode: upstream_catchment_plus_downstream_outlet
  build_from_bare_earth_dem: true

rainfall:
  source: HIRDS
  aep_percent: 1
  event_duration_hours: null  # MUST be selected using HIRDS + catchment response, not invented
  hyetograph_file: null       # MANDATORY for a real run
  climate_scenario: current

drainage:
  mode: scenario
  default_unknown_asset: unmodelled
  options: [no_drainage_extreme, assumed_partial_drainage, verified_asset_drainage]

barriers:
  require_review_for_hydraulic_model: true
  unidentified_fence: unmodelled
  sources: [manual_survey, verified_aerial, lidar_candidate]

quality:
  require_source_manifest: true
  stop_if_vertical_datum_unknown: true
  output_not_certified_notice: true
```

## F. Prioritised milestone sequence

| Gate | Deliverable | Completion test | Time expectation |
|---|---|---|---|
| G0 | Repo + fixture + doctor | Offline test and CLI run | First 2-4h |
| G1 | Verified site address and public data | Coverage/data table + actual LINZ parcel | Day 1 |
| G2 | GIS terrain and 2D map | DEM/DSM aligned, flowpaths, drains, obstacle candidates | Days 1-2 |
| G3 | **Actual** 2D SFINCS synthetic run | Mass balance and solver outputs verified | Day 2 |
| G4 | Site-specific surface baseline | Real HIRDS inputs, catchment domain, scenario logs | Days 2-4 |
| G5 | Wall scenarios | Baseline-vs-change, verified/reviewed barrier geometry | Days 4-5 |
| G6 | Drainage sensitivity | Distinct assumptions; pipe detail limits shown | Days 5-7 |
| G7 | Visualisation, validation and report | 2D/3D comparative demo + QA report | Days 7-10 |
| G8 | Enhanced 1D-2D network coupling | Only after verified asset geometry, outlet heads, real solver tests | Later phase |

Estimates are planning targets for one experienced engineer plus AI coding support, **not guarantees**. If constrained to a one-day hackathon, ship G0-G3 and a limited G4/G5 example, and explicitly disclose missing rainfall/drainage details.

## G. Targeted Codex execution instructions

1. Read `AGENTS.md`, this plan, `SOURCES.md`, and `config.example.yaml`.
2. Create a tracked task plan and record each milestone's evidence. Only code/run one milestone at a time, using tests to validate.
3. First build a synthetic site and end-to-end hydraulics fixture. Confirm exact SFINCS, HydroMT API versions from installed packages and documentation. Do not invent callable methods/CLI args.
4. Implement public provider metadata discovery and robust layer pagination; do not immediately download regionwide data. No arbitrary sleeps/retries on auth failures.
5. Stop at external service access gates: show user required LINZ key, HIRDS hyetograph, permissions, missing property confirmation, required surveyed/assumed barrier information.
6. For each named process create unit tests for units, CRS, datum, clipping and conservation; include QA-generated plots.
7. Where data is not supplied, use synthetic explicitly labelled fixtures only; no fraudulent flood-risk result.
8. Document exactly what has been implemented, tested, skipped and blocked. Don't report success if unable to run solver or retrieve data.
9. Ensure site address and user-related details remain in local/private configs (not a public repo). When preparing public example substitute a fictional location with synthetic dataset.

## H. Sources and docs

- Council mapped OLFP: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Overland_Flow_Paths/FeatureServer/0
- Council pipes: https://services1.arcgis.com/n4yPwebTjJCmXB6W/ArcGIS/rest/services/Stormwater_Pipe/FeatureServer
- Council catchpits: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Stormwater_Catchpit/FeatureServer/0
- LINZ Auckland Part 2 DEM survey specs: https://data.linz.govt.nz/layer/122580-auckland-part-2-lidar-1m-dem-2024/
- LINZ elevation data: https://data.linz.govt.nz/layer/121859-new-zealand-lidar-1m-dem/
- SFINCS input: https://github.com/Deltares/SFINCS/blob/main/docs/input.rst
- SFINCS hydraulic and drainage structures: https://sfincs.readthedocs.io/en/latest/input_structures.html
- HydroMT-SFINCS: https://github.com/Deltares/hydromt_sfincs
- HEC-RAS 2D structures: https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.4/development-of-a-2d-or-combined-1d-2d-model/hydraulic-structures-inside-of-2d-flow-areas
- HIRDS: https://niwa.co.nz/climate-and-weather/high-intensity-rainfall-design-system-hirds
- LINZ vertical datum conversion: https://www.linz.govt.nz/guidance/geodetic-system/understanding-coordinate-conversions/height-datum-conversions/vertical-datum-relationship-grids

## I. Definition of done (at each stage)

Every milestone must record: code commit, input manifest, executed command, test and model output, known errors, explicit assumptions, screenshots, conservation/validation checks, time/CPU/memory use and a next-step list. No fabricated outputs or labels. Implement a reproducible workflow whose limitations are obvious to end-users.
