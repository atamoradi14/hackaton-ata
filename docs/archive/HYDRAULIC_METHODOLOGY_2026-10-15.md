> Historical snapshot (14–15 October 2026), retained for reproducibility only.
> Current product documentation: [README](../../README.md) and [METHODOLOGY](../../METHODOLOGY.md).
> Hydraulic scenarios and their old UI descriptions below are not the current boundary-review workflow.

# Auckland FlowLab: data, accuracy and hydraulic methodology

Technical reference for the Auckland property flood research prototype. Implementation
and recorded validation snapshot: **14 October 2026**. Read alongside
[README_ARCHITECTURE.md](../../README_ARCHITECTURE.md) and [PROGRESS.md](../../PROGRESS.md).
The master plan is a specification; this document describes the implemented state.

## Contents

- [Purpose and current scope](#purpose-and-current-scope)
- [Data inventory](#data-inventory)
- [Accuracy and uncertainty](#accuracy-and-uncertainty)
- [Acquisition and preprocessing](#acquisition-and-preprocessing)
- [Terrain and building reconstruction](#terrain-and-building-reconstruction)
- [Finding and reviewing walls](#finding-and-reviewing-walls)
- [Hydraulic formulation](#hydraulic-formulation)
- [Implemented simulation configuration](#implemented-simulation-configuration)
- [Rainfall and HIRDS](#rainfall-and-hirds)
- [Validation and recorded results](#validation-and-recorded-results)
- [Outputs and reproducibility](#outputs-and-reproducibility)
- [Client demonstration and Council workflow](#client-demonstration-and-council-workflow)
- [Remaining scientific work](#remaining-scientific-work)

## Purpose and current scope

Auckland FlowLab connects an official address and cadastral parcel to real survey terrain,
public GIS context and an actual time-dependent hydraulic solver. A user confirms
the property before preparation, then separately reviews assumptions before a
simulation. The demonstrated site is 61 Pemberton Avenue, Bayview, Auckland.
Its official address and parcel match were visually confirmed by the user.

Implemented: address review, bounded GIS/elevation/point-cloud acquisition, terrain
QC, screening, interactive 2D/3D inspection, assumed-rain and zero-rain SFINCS runs,
finite hypothetical-wall scenarios, saved replay and provenance/artifact exports.

Not yet established: a calibrated catchment model, reviewed design storm, surveyed
wall inventory, functioning pipe-network coupling, exact site open-boundary mass
closure, validated property metrics or an engineering flood-risk classification.
Use the current output to inspect evidence and explore assumptions. Qualified
hydraulic review is required before safety, consent, insurance or design decisions.

Four different extents serve different purposes:

| Extent | Size | Purpose |
|---|---:|---|
| GIS/DEM/DSM discovery | Approximately 2 km square | Context and acquisition; aligned raster is 2,001 × 2,001 pixels |
| Native point-cloud crop | 200 × 200 m | Ground QC and nearby roof/structure inspection |
| Exploratory hydraulic domain | 800 × 800 m | Actual 200 × 200 computational grid at 4 m spacing |
| Interactive scene/replay crop | 320 × 320 m | Central terrain display and 80 × 80 hydraulic cells |

None of these fixed extents proves that the full contributing catchment and all
downstream controls are represented. Discovery coverage is not domain convergence.

## Data inventory

Counts below come from the private prepared demonstration cache, not a promise
about another address or a continuously refreshed service.

| Dataset | Source, date and current contents | Role and provenance status |
|---|---|---|
| Address point | LINZ NZ Addresses | Official match; coordinates/identifier and user confirmation retained |
| Parcel | LINZ NZ Primary Parcels, layer 50772 | Official cadastral context; not a surveyed fence/wall line |
| Building footprints | LINZ NZ Building Outlines, layer 101290; 113 intersect the scene | Official map geometry; rasterized as solid obstacles; entry heights missing |
| Ground DEM | Auckland **Part 1** LiDAR 1 m DEM (2024), LINZ layer 121990; Woolpert; capture 30 April–27 June 2024 | Official survey-derived bare-earth hydraulic terrain |
| Surface DSM | Auckland Part 1 LiDAR 1 m DSM (2024), layer 121992; same survey | Above-ground visual surfaces, not the hydraulic bed |
| Classified LAS/LAZ | OpenTopography Auckland 2024 bulk tiles; 526,437 cropped returns | Actual survey returns; class/flags retained; class 2 ground and class 6 buildings used selectively |
| Aerial imagery | LINZ Auckland 0.075 m Urban Aerial Photos (2024–2025) | Actual orthophotography for visual context; 0.2 m display crop |
| Overland flow paths | Council `Overland_Flow_Paths`, 830 features in discovery window | Official mapped context, not transient hydraulic output |
| Flood plains | Council `Flood_Plains`, 10 features | Official mapped context; scenario equivalence not established |
| Flood-prone areas | Council `Flood_Prone_Areas`, 19 features | Official mapped context; not a calibrated comparison target yet |
| Stormwater pipes | Council `Stormwater_Pipe`, 1,786 features | Indicative asset map; no hydraulic pipe network constructed |
| Catchpits | Council `Stormwater_Catchpit`, 395 features | Context; inlet capacity and connectivity unverified |
| Manholes/chambers | Council `Stormwater_Manhole_And_Chamber`, 1,008 features | Context; levels/datum/connectivity unverified |
| Connections | Council `Stormwater_Connection`, 223 features | Context; no assumed private drainage model |
| HIRDS CSV supplied by user | 2,305 catalogue rows, including 144 Auckland regional entries | Metadata only; no usable site rainfall depths downloaded |
| Scenario rain | User-reviewed editable constant intensity | Assumed forcing, not observed rainfall or HIRDS design rainfall |
| Scenario walls | Two clicked endpoints and assumed crest offsets | Hypothetical finite structures, not survey measurements |
| Roughness/infiltration | Editable constant parameters | Assumed; no fitted soil/land-cover parameterization |

The seven Council layers are stored as GeoPackages with availability and geometry
QC in `gis-discovery-manifest.json`. All seven were available in this snapshot.
Their asset elevations were not imported into the hydraulic model. A feature
service editing timestamp is not necessarily its survey or modelling date.
The overland-flow product has older terrain/mapping lineage than the 2024 LiDAR;
do not interpret recent service edits as a complete terrain refresh.

Source references:

- [LINZ DEM metadata](https://data.linz.govt.nz/layer/121990-auckland-part-1-lidar-1m-dem-2024/)
  and [DSM metadata](https://data.linz.govt.nz/layer/121992-auckland-part-1-lidar-1m-dsm-2024/).
- [OpenTopography dataset](https://portal.opentopography.org/lidarDataset?opentopoID=OTLAS.042025.2193.1),
  [dataset DOI](https://doi.org/10.5069/G9HH6H8T).
- [LINZ imagery collection](https://nz-imagery.s3-ap-southeast-2.amazonaws.com/auckland/auckland_2024_0.075m/rgb/2193/collection.json).
- [SOURCES.md](../../SOURCES.md) lists exact Council endpoints and provider starting points.

DEM/DSM, selected point cloud and imagery manifests record CC-BY-4.0. Preserve
Woolpert, Regional Software Holdings Limited, LINZ and OpenTopography attribution
as applicable. Council redistribution terms need review per provider; public
read access is not a blanket licence for redistribution. HIRDS order terms must
be reviewed independently. Private site data stays outside the source repository.

## Accuracy and uncertainty

**Resolution, numerical precision and measurement accuracy are different.** A 1 m
DEM cell is an elevation sample/support area, not ±1 m accuracy. A millimetre in a
JSON value or replay slider is display precision, not millimetre terrain accuracy.

| Component | Supported statement | Practical limit |
|---|---|---|
| DEM/DSM vertical accuracy | Recorded survey specification ±0.2 m at 95% | Specification is not independent validation at this property; steep edges, canopy and interpolation matter |
| Raster spacing | 1 m source/output grid | Thin fences, small kerbs, narrow openings and local crest changes can be unresolved |
| Aerial pixels | 0.075 m source, resampled to 0.2 m display | Pixel size does not establish horizontal positional accuracy; canopy and acquisition mismatch hide features |
| Raw points | Classified survey returns, with noise/withheld flags | Point density is irregular; occlusion/classification errors remain |
| Building meshes | Native classified roofs where coverage passes; DSM elsewhere | Not architectural BIM; untextured facades, no verified doors/thresholds/interior |
| Parcel | Official cadastral polygon | Cannot locate the physical wall/fence without survey |
| Water display | 4 m cells, 1 mm depth and 0.01 m/s velocity quantization | Display is coarser than the terrain; subgrid does not recover observed street-scale detail |
| Scenario prediction | Finite/nonnegative/completed checks pass | Model uncertainty is not quantified by these QC checks; no calibrated prediction interval |

### Same-survey ground consistency check

Class 2, non-withheld LiDAR returns were compared with nearest DEM cells:

| Metric | Recorded result |
|---|---:|
| Compared points | 120,510 |
| Median point minus DEM elevation | −0.002250 m |
| 5th/95th percentiles | −0.152249 / +0.149999 m |
| RMSE | 0.102858 m |
| Absolute difference above 0.4 m | 0.785% |

This compares products derived from the same survey. It checks internal consistency,
not independent ground truth. Nearest-cell sampling on slopes introduces additional
differences. RTK/total-station checks, surveyed wall crests and benchmark control
would provide stronger site evidence.

QC also records 419 DSM-minus-DEM negative-height cells in the discovery window.
These remain flags, not evidence of subsurface structures. Raw LAZ contains noise
and withheld returns, including implausible negative elevations; these are preserved
in raw evidence and must not be used to build the hydraulic bed.

### Coordinate reference systems

All modelling horizontal coordinates use NZTM2000 **EPSG:2193**, in metres.
Heights use **NZVD2016**, associated with vertical EPSG:7839 in point-cloud metadata.
Source metadata and actual tile evidence established the selected terrain datum;
no vertical conversion was applied. WGS84 is used for address/HIRDS location and
browser map interchange. Longitude/latitude axis ordering is checked.

Legacy Council asset levels may use another datum. No arbitrary offset is applied.
If later imported, conversion needs authoritative LINZ relationship grids, a known
source datum, benchmark checks and recorded transformations. A two-dimensional
asset line alone carries no verified invert or crest elevation.

## Acquisition and preprocessing

1. Resolve the full address through LINZ, join a defensible parcel and show a review
   map. Ambiguous matches fail or require selection; no guessed location is used.
2. Obtain Council metadata before queries. Inspect schema, geometry type, pagination,
   feature limits and CRS; query a bounded EPSG:2193 envelope. Save raw responses,
   hashes, counts and invalid/empty/duplicate geometry diagnostics.
3. Intersect actual LiDAR capture polygons and tile indexes. The demonstration uses
   Part 1; Part 2 is not selected merely because a plan mentioned it.
4. Discover intersecting STAC raster items. Read bounded Cloud Optimized GeoTIFF
   windows, merge onto aligned 1 m DEM/DSM grids and verify nodata/CRS/datum.
5. Select two official-index point-cloud tiles, preserve full LAZ source hashes and
   crop locally. The chosen public bulk endpoint needs no OpenTopography key.
6. Prepare ground consistency checks, profiles, above-ground flags and D8 screening.
7. Fetch bounded genuine aerial windows through STAC geometry intersection, resample
   the 320 m square display crop, record source resolution/licence and JPEG hash.
8. Construct the scene from explicit source files; reject missing terrain coverage
   rather than fabricate a replacement.

Raster/aerial range reads do **not** verify full remote-tile checksums. Manifests
record that limitation, source metadata/checksums where supplied and local output
SHA-256 hashes. Full downloaded LAZ tile hashes and cropped-output hashes are
recorded separately. A hash establishes file identity, not physical correctness.

Implementation: `providers/`, `terrain/aerial.py`, `terrain/scene.py`,
`scripts/site-qc.py` and preparation steps in `api/workspace.py`.

## Terrain and building reconstruction

The scene uses the central 1 m DEM at true vertical scale and genuine orthophoto
texture. It also contains the confirmed parcel, building surfaces, approximate
facades and inspection overlays. It is a browser Three.js model, not a rendered
video. Orbit, pan, zoom, top/property/surroundings views and terrain sectioning
allow inspection from multiple positions.

Nearby roofs are reconstructed from non-withheld ASPRS class 6 returns:

1. Select points within footprint geometry with a 0.3 m allowance.
2. Keep the highest actual classified return per 0.35 m horizontal voxel.
3. Require sufficient points and at least 70% footprint convex-hull coverage.
4. Delaunay-triangulate horizontal positions; retain triangles centred inside the
   footprint and omit triangles with any horizontal edge of 2 m or more.
5. Use accepted native elevations for nearby roof/facade tops, with DSM fallback
   outside native roof coverage. Do not invent architectural details.

The demonstration has 27 native roof meshes and 26,710 vertices. Other buildings
use 1 m DSM surfaces. Vegetation/classification errors can contaminate roofs, and
the convex-hull coverage criterion does not prove complete roof geometry.
The point view is display-decimated to at most 60,000 points; original cropped
returns remain private. No source RGB channels were available in the native LAZ;
the aerial texture is a separate observation.

Buildings have two representations: visual roof/facade meshes and **hydraulic
footprint masks**. The solver does not run over the visual DSM or through rendered
walls. Official footprint-intersecting cells are inactive/solid. This excludes
roof rainfall/runoff and does not model doors, overhangs, basements or indoor water.

## Finding and reviewing walls

The current detector finds **terrain discontinuity bands**, not confirmed walls:
3 × 3 DEM-window relief between 0.8 and 4 m, excluding dilated building masks and
areas with DSM-minus-DEM above 1 m, with connected polygon areas 4–500 m². The
demonstration produced 33 bands. Their boundaries are drawn as inspection cues;
they are not wall centrelines. Slopes/banks can trigger them; hidden or narrow walls
can be missed. No precision/recall evaluation against a surveyed wall inventory exists.

Practical review: inspect the aerial image, raw ground/structure returns and terrain
cross-sections; distinguish a retaining wall from a bank/hedge/roof edge. Obtain
site-access consent and measure line position, ground on both sides, crest along
the line, openings, culverts, porosity and source/date/datum. Check whether the DEM
already includes an embankment before adding another barrier.

For exploration, the UI accepts two exposed-ground clicks and an assumed offset
of 0.1–3 m. Their absolute crest endpoints become a finite SFINCS weir with assumed
coefficient 0.6. Server validation requires hypothetical status, finite values,
endpoints within ±160 m of the site origin, crest −10 to 150 m, length at least 1 m
and at most ten walls. Lines near/crossing footprint buffers of 4 m are rejected.
This protects the current coarse obstacle representation; it is not a physical
setback rule. Gaps, permeability and measured wall ingestion need further work.

Finite crests allow overtopping. Infinite thin dams appear only in the explicitly
labelled synthetic sensitivity suite. Parcel boundaries are not automatic dams.
See [SFINCS structures](https://sfincs.readthedocs.io/en/latest/input_structures.html)
for the released solver's structure formulation.

## Hydraulic formulation

The engine is the actual Deltares **SFINCS 2.4.0 Galibier** CPU executable.
HydroMT-SFINCS writes model inputs; it is not the solver itself. The deployed
configuration uses `advection=0`, the local-inertial approximation, rather than
claiming a complete advective shallow-water solution. SFINCS uses an explicit
time-stepping scheme; the [official overview](https://sfincs.readthedocs.io/en/latest/overview.html)
describes the reduced-complexity formulation and when advection matters.

Conceptually, continuity on an active area is:

```text
change in stored water = rainfall − infiltration + inflows − outflows
```

For a flat cell notation, `∂h/∂t + ∂qx/∂x + ∂qy/∂y = R − I + S`, where h is
depth, q is discharge per unit width, R/I are rainfall/loss rates and S represents
other sources/sinks. Local-inertial momentum retains local acceleration,
water-surface gradient and friction while omitting advective acceleration.
Manning friction depends on roughness, flow and effective depth.

These are explanatory equations, not a reimplementation of SFINCS. Its staggered
fluxes, wet/dry rules and subgrid storage/conveyance tables determine the discrete
solution. In the site model, 1 m terrain samples produce 12-level hypsometric
tables within each 4 m computational cell. This improves storage/conveyance
representation relative to flat averaged cells, but does not create a 1 m
independent velocity solution or resolve unmeasured features. Steep, rapidly
varying or supercritical flow needs specific assessment of the chosen approximation.

D8 screening follows terrain-derived directions without solving time-dependent
momentum, storage, overtopping or backwater. It is labelled non-hydraulic and is
never substituted for SFINCS water depth/velocity.

## Implemented simulation configuration

Source of truth: [site.py](../../src/floodtwin/hydraulics/site.py).

| Setting | Implemented value/meaning |
|---|---|
| Domain | 800 m square around integer-aligned site origin; not reviewed catchment |
| Grid | Regular 200 × 200 cells, 4 m; EPSG:2193; rotation 0 |
| Subgrid | 1 m DEM samples, 12 elevation levels |
| Mask | 0 inactive footprint, 1 active interior, 3 free-outflow outer perimeter |
| Initial state | Dry, based on subgrid minimum elevations |
| Rain | Constant reviewed intensity, then one-second linear ramp to zero |
| Duration | 10–60 min rainfall plus 30 min dry-down |
| Roughness | Constant Manning 0.015–0.08; example 0.03 |
| Loss | Optional constant infiltration 0–20 mm/h; example zero |
| Rain bounds | 0–100 mm/h, finite numeric values |
| Momentum | `advection=0` |
| Maximum timestep | 0.25 s; adaptive actual timestep read from log |
| Wet/dry threshold | `huthresh=0.01` m |
| Output sampling | Maps/history/max-output configuration at 60 s |
| Stored diagnostics | Velocity, cumulative rain and subgrid volume enabled |
| External inflow/drainage | None; no pipe drainage, roof routing or tidal forcing |
| Model clock | Arbitrary 1 January 2020 reference, not a historical event |
| Structure | Finite per-endpoint crest, coefficient 0.6, hypothetical |

Only the outer domain perimeter has free-outflow flags; internal building edges
are not outlets. Free outflow can artificially reduce ponding or miss downstream
backwater; absent upstream inflows can miss incoming water. Excluded roof runoff
can underestimate supply, while no drains can increase surface storage. These
competing effects mean this is **not automatically a conservative upper bound**.

The released solver needed an observation point to avoid weir-output initialization
failure. A nearby active model cell provides that probe; it is not a measured gauge.
The data catalogue is explicitly local-only and OpenMP is restricted to one thread
on the Kubernetes pod. Fresh directories prevent reuse of stale solver outputs.

## Rainfall and HIRDS

The supplied CSV describes products rather than site DDF/IDF values. Its regional
entries include 2,000 m grids, durations and recurrence intervals, but these are
not a reviewed point-table storm. Credentials are private; the tested order-file
API returned HTTP 404 `NO_ORDERS_FOUND`.

Order a custom point dataset through the [official HIRDS workflow](https://data.niwa.co.nz/blogs/how-to/articles/get-hirds-tables),
using the confirmed WGS84 location shown by the studio. Review purpose, licence,
price if any, current/future climate and ARI/AEP. The [documented DataHub API](https://data.niwa.co.nz/pages/datahub-api-information)
lists/downloads approved order files; no point-generation endpoint was established.

```text
floodtwin hirds-inspect --csv hirds.csv
floodtwin hirds-files
floodtwin hirds-download --id YOUR_APPROVED_ORDER_FILE_ID
```

After obtaining depths, derive a justified time-varying hyetograph, review units,
duration, temporal pattern, climate uplift and any areal adjustment. A DDF/IDF
table is not itself a rainfall time series. The current uniform UI storm is an
explicit assumption and cannot be labelled a 1% AEP or other HIRDS event.
Details: [docs/HIRDS_API.md](../../docs/HIRDS_API.md).

## Validation and recorded results

### Three levels of evidence

1. **Environment/integration:** real GDAL/CRS/raster/point-cloud interfaces, exact
   dependency family, executable and Docker/Kubernetes runtime checks.
2. **Synthetic numerical fixtures:** actual solver on deliberately fabricated
   geometry/forcing, independent of site data or keys.
3. **Exploratory site QC:** actual survey terrain and solver with assumed forcing;
   checks completion/stability, not field calibration or full site conservation.

The offline eight-case suite covers still water, downslope equilibration, open
redistribution, finite overtopping, below-crest blocking, an infinite barrier,
1 m/2 m cell sensitivity and 0.25 s/0.5 s maximum-timestep sensitivity. Closed-case
all-cell storage drift must be ≤0.5%; still-water level/speed changes ≤0.00001 in
their respective units; open/slope equilibrium error ≤0.005 m; sensitivity in
compartment-mean levels ≤0.02 m. Full acceptance details are in
[docs/HYDRAULIC_VALIDATION.md](../../docs/HYDRAULIC_VALIDATION.md).

Recorded node suite: eight cases passed; maximum relative volume error
`5.960464477539063e-08`; finite-weir net transfer about 39.977552 m³. This establishes
the tested fixture behavior, not accuracy of a real wall's transient discharge.
The application test suite recorded 41 passes; browser checks covered desktop,
mobile, controls, exports and live solver replay.

### Live site controls, 14 October 2026

| Case | Forcing | Final stored volume | Recorded checks |
|---|---|---:|---|
| Dry control | 0 mm/h | 0 m³ | Completed, dry, finite/nonnegative |
| Rain baseline | 50 mm/h × 30 min + 30 min dry-down | 4,779.389160 m³ | Completed, finite/nonnegative |
| Hypothetical finite wall | Same rain, one assumed wall | 4,779.506836 m³ | Completed, finite/nonnegative |

Rain cases supplied 14,351.185333 m³ to interior active cells, including the
one-second ramp; average logged timestep was 0.125 s. The small global storage
difference is not a demonstrated local mitigation benefit. Scenario difference
maps, per-parcel impact analysis and controlled domain sensitivity remain pending.

Site QC rejects failed exit status, incorrect solver revision, incomplete history,
raw nonfinite water levels/velocities, active depths below −0.00001 m, invalid
logged timestep, wet zero-rain control, and storage exceeding available rainfall
by more than 2%. Released dry-cell fill markers are handled explicitly.

**Exact site mass-balance closure is not verified.** The stored-volume upper-bound
check cannot account for all integrated open-boundary discharge/losses. Results
therefore carry `mass_balance_verified: false` and `relative_mass_error: null`.
A successful exit or bounded storage is not a full conservation certificate.
Initial averaged-cell trials failed wet/dry QC; their results are not exposed as
successful simulations. Subgrid runs passed the stated checks.

## Outputs and reproducibility

| Artifact | Meaning |
|---|---|
| `site_manifest.json` | Official match, coordinates, confirmation and provenance |
| `terrain-qc.json` | CRS/datum, source metadata, aligned grid, nodata and hashes |
| `pointcloud-manifest.json` | Source tiles/hashes, crop, classification/flags and caveats |
| `ground-dem-qc.json` / cross-section CSV | Same-survey comparison and profile evidence |
| `gis-discovery-manifest.json` | Layer status/counts/geometry checks and source references |
| `scene-aerial.json` / `scene.json` | Image provenance, scene grid/geometry and accuracy statements |
| `request.json` | Reviewed scenario parameters |
| `sfincs.*` model files | Executable inputs, grid/mask/subgrid, forcing and structures |
| `run_manifest.json` | Terrain/input hashes, bounds, datum and assumptions |
| `solver.log`, `worker.log`, `execution.json` | Exit status, runtime, version/log identity and errors |
| `sfincs_map.nc`, `sfincs_his.nc` | Native solver outputs/history |
| `results.json`, `status.json` | QC summary, replay frames, parameters and persisted state |

Replay derives displayed depth from solver level minus output bed, with expected
dry fill handled separately, and uses solver u/v for arrows. The central crop is
quantized to integer millimetres and centimetres/second at saved times. Playback
speed and arrow layout are visual controls, not new numerical integration.
Residual water after rain stops is retained. The maximum depth label is a
coarse-cell quantity, not predicted indoor depth.

PNG exports include assumptions/captions. GLB exports contain terrain geometry,
not a coupled hydraulic model or complete architectural survey. Other allowlisted
exports include DEM/DSM, LAZ, maps, profiles and provenance. Native hydraulic files
remain in private workspace storage; no general public filesystem endpoint exists.

Preserve fresh run directories, exact lockfiles and executable image digest.
Re-run numerical validation after changing the solver, HydroMT pair, subgrid,
mask/structure logic or forcing. Never overwrite failed evidence with a successful
run or remove caveats from client exports.

## Client demonstration and Council workflow

1. Enter and confirm an official address/parcel; inspect source readiness.
2. Open Interactive 3D. Orbit the real terrain, compare roofs/points and inspect
   profiles/candidate bands. Explain survey and rendering limits.
3. Replay the dry control, then the assumed-rain baseline. Show rain cessation,
   residual storage, depth/velocity and QC caveats.
4. Draw a hypothetical wall on exposed terrain, state its assumed crest, review
   all scenario settings, run and replay it alongside the baseline.
5. Collect a measured wall/drainage inventory and obtain an approved HIRDS table.
6. Have Council/hydraulic reviewers agree catchment boundaries/outlets, losses,
   runoff routing and validation targets before interpreting intervention effects.
7. Preserve input/run identity and inspect upstream/downstream impacts, not only
   the target parcel. Do not recommend construction from the exploratory replay.

No Blender step is required for the current WebGL interaction. A measured
architectural/photogrammetry model could improve appearance, but would not by
itself improve hydraulic boundary conditions, wall crests or rainfall evidence.

## Remaining scientific work

- Approved point HIRDS values and documented design hyetographs.
- Connected upstream/downstream domain and outlet/backwater review; domain-size,
  grid, timestep and local-inertial approximation sensitivity.
- Exact rainfall/infiltration/storage/boundary-flux budget and convergence checks.
- Measured wall crests, gaps/porosity, kerbs and building thresholds.
- Roof runoff routing, land-cover roughness and soil/antecedent-loss evidence.
- Verified inlet/pipe/outfall network with consistent datum and capacity.
- Tested SWMM head/timestep/volume exchange before claiming 1D–2D coupling.
- Calibration against consented observations and independent survey checks.
- Scenario difference maps, arrival/wet-duration metrics and reviewed parcel
  impacts with quantified uncertainty. These master-plan capabilities are future work.

For installation, APIs, persistence, deployment and operations, continue with
[README_ARCHITECTURE.md](../../README_ARCHITECTURE.md).


## Interactive revision evidence — 15 October 2026

This revision improves display correctness and validation coverage, not site
calibration. Native frames are checked against their hashed NetCDF source.
Maximum depths use solver-step `zsmax - zb` where `hmax` is absent. Maximum of
saved minute frames is a different statistic; velocity peaks and inundation
inspection remain sampled at those saved intervals. Display depth is rounded to
1 mm and velocity components to 0.01 m/s. Values describe computational cells;
water within a steep 1 m terrain subgrid is not separately solved at 1 m.

The 12-case native suite adds dry terrain, a closed rainfall tank, finite endpoint
bypass and reversed wall orientation. Maximum closed-fixture relative mass error
was 5.960464477539063e-8 (0.00000596%). The rainfall tank accumulated 8 m³ under
20 mm/h for one hour over 400 m². These fixtures do not validate field boundaries.

The saved 50 mm/h, 30-minute baseline/wall pair has native maximum-depth changes
of +0.038 / -0.037 m in the central 320 m crop, with 5,056 m² changing by at least
1 mm. The difference of maxima of saved frames instead gives +0.056 / -0.053 m
and 6,672 m². Neither is a simultaneous difference field; the UI provides actual
same-timestamp depth differences separately. Final signed storage differs by
approximately 0.13 m³. A new three-vertex wall drawn in the homepage produced
10 native snapped structure faces and reproduced those peak-change metrics.

Fresh sensitivity checks against the existing baseline:

| Check | Maximum absolute displayed depth change | Mean absolute change |
| --- | ---: | ---: |
| Same 800 m domain / 4 m cells, fresh run | 0 m at 1 mm display precision | 0 m |
| 1,200 m domain / 4 m cells | 0.525 m | 0.000380 m |
| 800 m domain / 8 m cells | 1.09 m | 0.018723 m |

Domain comparisons use aligned cells in the central crop. The 8 m comparison
averages 4 m depths to 8 m blocks and includes only common all-active blocks;
obstacle rasterisation and cell-minimum bed definitions change. It is a diagnostic
of sensitivity, not a convergence proof or a comparison of identical models.
The large local changes mean the original site model must not be called converged.

Native precipitation is approximately 14,349.88 m³ and final signed subgrid
storage approximately 4,779.38 m³ in the baseline interior. Infiltration is zero.
Up to 6.55 m³ of negative signed subgrid storage occurs. This is exposed as a
numerical diagnostic; it is not silently clipped out of the budget. Integrated
external fluxes are unavailable in these saved outputs. Rainfall minus storage
is not a measured outflow budget, so exact closure remains unverified.

Walls retain finite absolute NZVD2016 crests, now with 2–12 vertices per wall.
Multiple separated walls can represent explicit gaps; no automatic culvert or
porosity is invented. Review wall placement and grid snapping. The released solver
interpolates per-vertex crests and snaps structures to cell faces; see the
[official SFINCS structures documentation](https://sfincs.readthedocs.io/en/latest/input_structures.html).
Geometry exports use WGS84 horizontal coordinates, with NZVD2016 crest arrays in
properties rather than falsely labelling those heights as ellipsoidal GeoJSON Z.

Roof QA rejects isolated class-6 elevation outliers, triangles crossing footprint
holes/edges, edges at least 2 m long and triangle elevation spans at least 2 m.
Coverage below 70% uses approximate flat DSM-median roofs. This conservative
rejection can omit genuine roof detail; it is not architectural reconstruction.
Real terrain elevations are not smoothed. QA counts remain in scene metadata.

HIRDS storm import, surveyed barriers, upstream catchment review, downstream
boundary budgets and coupled drainage remain required scientific work. No pipe
capacities, inverts, rainfall frequencies or absolute property safety labels were
invented. A future drainage interface must require verified node/edge IDs, CRS,
vertical datum, inverts, diameters, connectivity, outfall heads and time-resolved
surface/network exchange budgets before a SWMM coupling can be claimed.

The optional Earth studio is a visualization layer over the same native results.
Google is surrounding visual context only; its surface is clipped from the local
simulation patch and is not used to derive terrain or hydraulic parameters.
NZGeoid2016 converts normal-orthometric elevations to ellipsoidal display heights.
Numerical transform residuals do not establish physical alignment with Google.
Maximum-depth display uses native maxima; difference colours use actual signed
deltas on the union of wet cells' display envelope. No dry-cell bridges or
invented temporal water interpolation are introduced. Online source checks retain
acquisition dates and do not imply real-time terrain, newest coverage or calibration.
