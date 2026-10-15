# Interactive terrain and exploratory hydraulics

Open a confirmed property, choose **Interactive 3D**, then **Open interactive
terrain studio**. Orbit by dragging, zoom with the wheel, pan with the right
button; touch devices support OrbitControls gestures. Focus the property or
surroundings, toggle buildings/parcel/discontinuity bands, inspect native LiDAR
points, take a terrain section and export a GLB for Blender or other viewers.
Blender is not required to run the browser viewer.

The site crop uses actual 1 m DEM/DSM and official building footprints. A bounded
LINZ 2024–2025 aerial crop is spatially matched and projected onto the ground and
roof mesh; it is a real photograph, not generated imagery. Source photography is
0.075 m, displayed at 0.2 m; this does not improve the 1 m height measurement.
Inside the native crop, building-classified (ASPRS class 6) LiDAR returns are
sampled by 0.35 m horizontal voxel, retaining an actual highest return, then
triangulated within official footprints. Long (>2 m) triangles and poorly covered
footprints are rejected. Other roofs retain coarser DSM samples. This captures
nearby gables and roof edges without inventing architectural geometry, while
remaining subject to classification and footprint errors. The native crop is
200 m wide; it does not cover all outer buildings in the 320 m scene.
DSM samples can contain canopy/overhangs. Roof edges and untextured vertical
facades are approximate; doors, windows, material finishes and hidden architecture
cannot be recovered accurately from these rasters. The native point cloud has
classification but no RGB. The viewer uses true scale, NZTM and NZVD2016, with
local coordinates to avoid WebGL precision loss. Exported GLB contains provenance
extras; exported PNG includes scientific captions and does not imply a risk grade.

## Practical Council wall-review workflow

1. Show **LiDAR discontinuity candidates**. The current filter identifies 0.8–4 m
   variation in a 3×3 DEM neighbourhood and excludes mapped buildings and high
   DSM vegetation. Bands are candidates for an elevation discontinuity, not
   automatic wall detections. A bank, kerb, sparse-ground interpolation or erosion
   edge can also trigger them; exclusion masks can miss walls under canopy.
2. Inspect the real aerial photograph and native points from several angles.
   Check classification and ground-density support; compare ground levels on
   both sides. Existing cross-section QC is available in the main workspace.
3. Council/site survey should establish the actual alignment, crest NZVD2016
   elevations, base levels, openings, fence porosity and adjacent drainage. Thin
   or hidden structures below the LiDAR resolution remain unmeasured. Photographs
   with consent and RTK/total-station measurements improve confidence.
4. For sensitivity exploration now, click **Draw hypothetical wall**, select two
   exposed ground points and supply an explicitly assumed crest offset. The
   solver receives a finite 3D crest with assumed weir coefficient 0.6, not an
   infinite parcel-boundary barrier. Walls near excluded building cells are
   rejected until obstacle geometry is refined. Keep surveyed and hypothetical
   alternatives separate in review records.
5. Compare saved no-wall/wall runs under the same storm, roughness, losses and
   domain. Check downstream effects as well as local ponding. This prototype
   replays individual results; it does not yet produce a certified scenario
   comparison or engineering design recommendation.

## What the water represents

The user authorized exploratory assumed-rain scenarios. Each run still requires
the UI review checkbox. The actual pinned SFINCS 2.4 solver runs asynchronously
on a bounded 800×800 m real-ground domain, a 4 m computational grid, and 1 m DEM
subgrid hypsometry. The initial state is dry. Rain lasts for the selected duration,
followed by 30 minutes without rain; retained water does not disappear when rain
stops. The zero-rain control is separately simulated. Water level/depth and
velocity arrows come from solver NetCDF, with 1 mm depth and 0.01 m/s browser
display quantization, not decorative flow-line animation.

Reviewed exploratory assumptions: uniform rain, constant Manning roughness,
optional constant infiltration, solid footprint obstacles, excluded roof runoff,
no pipe drainage, no external upstream inflow, and free outflow at the outer
perimeter. The domain is not a reviewed connected catchment. Building mask
resolution, unresolved doors/kerbs/drains, domain size and roughness/losses need
sensitivity and survey review. Inactive roof cells and outflow boundary cells
are not counted as active rainfall cells.

QC requires exact solver version, complete time history, finite raw levels and
velocities, nonnegative active depth, positive bounded timestep, dry zero-rain
control and stored volume not exceeding supplied rain. Expected dry fill values
in the released subgrid output are distinguished from raw NaN/Inf. The released
map output does not supply an exact integrated open-boundary flux budget here;
**mass-balance closure is unverified and clearly shown**. These outputs therefore
remain exploratory and uncalibrated, not a HIRDS design storm or flood-risk verdict.
The independently tested closed synthetic suite remains the conservation gate.

The first averaged-cell runs failed wet/dry QC and are not exposed as results.
The subgrid configuration passed. A model observation probe is included because
this released solver crashed during weir-output initialization without one; the
probe is a model sampling location, not a measured gauge. Logs, immutable inputs,
source hashes, NetCDF and execution records stay in each private workspace.
Only one data-preparation/hydraulic worker runs at a time. Interrupted jobs need
a fresh review/restart. Large domains may exceed the 2 GiB node allocation.
The worker uses an explicit local-only DataCatalog with fallback disabled; it
does not download HydroMT's default artifact catalogue or write under the
container's read-only home. OpenMP is limited to one thread on the 1.5 CPU pod.
