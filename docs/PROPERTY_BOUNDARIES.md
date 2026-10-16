# Property boundary evidence registry

Open `http://127.0.0.1:8774/properties.html`. The Explore and 3D workspaces also
link to this view for their confirmed property. JSON storage requires no new
database or Postgres credentials. This feature does not run hydraulics.

## Inline 3D editing and two locally authored prediction samples

The **3D page itself** now has `Property lines & objects`. Every original edge is
a separate terrain-draped, numbered line. Click a line in LiDAR or Earth mode, or
choose an edge/object from the selector. Selection and the editor are shared
between both modes; orbiting does not select lines accidentally. Lines are thin
screen-space selection graphics visible behind occluders, not fence/wall meshes.
Orange indicates a mapped flow crossing, yellow the selected edge. Source-object
outlines are clipped to the scene extent rather than clamped onto its border.

Expand `Edit selected entity` to save type, material, dimensions and an evidence
note directly without leaving 3D. Original cadastral coordinates and publisher
attributes are not overwritten. Both existing mapped objects and inferred sample
canopy objects can be reviewed. Writes retain the existing origin/CSRF checks.

At the user's request, **assistant-in-session proposals** were authored for
3A Sadgrove Terrace and 23 Kitenui Avenue after inspecting the saved LINZ aerial
and native-return height plots. No OpenAI or other model API was used; this is not
a new automated detection service. The sample covers every original boundary and
recorded entity. Nonphysical map/context features explicitly say `not_applicable`,
not guessed building/fence types. Duplicate building-source aliases are retained
in JSON but not counted as distinct physical objects in the selector.

Building heights use p95 classified roof-return Z minus the co-located bare-earth
DEM, only with adequate property-footprint coverage and return count. These are
roof envelopes, not surveyed wall/eave heights. Vegetation groups are connected
canopy clusters, not individual trees. Boundary hedge/fence hypotheses are based
on the inspected imagery and separately retained native corridor statistics;
mixed/obscured edges can have unknown overall height. `height_range_kind` separates
observed return-height spreads from qualitative guesses: neither is a calibrated
statistical confidence interval. Material, depth, permeability and flood risk are
not manufactured. Google aerial, photorealistic 3D and Street View were **not** used:
the local Google provider is not configured.

Predictions stay separate from `structure` and manual reviews. `Copy proposal
into edit form` does not save or verify it. Check/correct it before saving. Source
revision changes mark proposals `stale` and disable copying. The ordinary property
JSON/GeoJSON exports include the proposal and review evidence where applicable.
The user-provided untracked `check-BA31_1000_4245-team.csv` is preserved; its
screen-review labels were not treated as field verification or used to claim
prediction accuracy.

Ignored local storage:

```
data/property-registry/predictions/property_<id>.json
data/property-registry/assistant-drafts/property_<id>.json
data/property-registry/sample-evidence/property_<id>/{evidence.json,top-evidence.png}
data/property-registry/object-reviews/property_<id>.json
```

`floodtwin.features.sample_evidence.prepare(root, workspace_id)` creates analytical
evidence, not predictions. `save_sample(root, property_id, draft_path)` validates
and saves an already-authored draft tied to the inspected image hash and source
revision. There is deliberately no remote AI call or automatic new-address
prediction. All ordinary records, inferred samples and reviews remain exportable.

Additional routes:

- `GET /api/properties/{id}/prediction-evidence`: saved annotated evidence PNG.
- `POST /api/properties/{id}/objects/{object}/review`: reviewed attributes for an
  existing source or saved inferred object, without changing source geometry.

## Contract

Each property retains its original polygon (including interior rings and
multipart polygons), original publisher attributes, source IDs, metadata and
raw-asset hashes. Every nonzero straight edge between consecutive original
vertices is a separate object. No simplifying, artificial densifying or clipping
of cadastral rings is applied. A polygon with eight edges produces eight records.

Boundary IDs hash canonical, millimetre-rounded endpoint pairs, so reversing a
ring or changing its start vertex does not rename an edge. Identical edge pairs
across properties share an edge ID; this does not establish physical ownership
or solve unmatched T-junction topology. Property IDs include their source dataset
and source key. Rating-unit/property polygons and primary parcels are distinct
datasets, not silently interchangeable identifiers.

Each `boundary_segments[]` item includes:

- `id`, part/ring/edge index, `is_hole`, length and bearing.
- `geometry`: RFC 7946-style GeoJSON LineString, two longitude/latitude endpoints.
- `endpoints_nztm`: the same two positions in EPSG:2193 metres. No fabricated Z.
- `structure`: type, material, height/width/depth in metres, continuity,
  permeability, potential influence, confidence and review status. Unknown
  values stay unknown/null. Source features do not automatically become a fence
  on the boundary.
- `flow_path`: crosses/touches/overlaps/parallels/adjacent/outside/unknown,
  intersections, original flow attributes and explicit mapped-data status.
  `crossed_by_flow_path` is null for unavailable data and false for a successful
  empty query. Touching at endpoints and collinear overlap are not proper crosses.
- `nearby_objects`: references and metric distances to original mapped features
  within the recorded tolerance (default 1 m). Full geometries and all original
  attributes are retained in `objects[]`; raw publisher responses are also saved.
- `property_object_ids` on the parent record separately links every mapped feature
  intersecting the polygon, even objects well inside it and far from all edges.
- `lidar`: native corridor-return counts/classes, crop coverage and relative
  height statistics. Missing returns do not prove absence of a structure.
- `risk`: unassessed by default. Optional manual concern labels are explicitly
  user-supplied and unvalidated, not a calculated property flood-risk assessment.

The source point cloud is never reduced to a raster for candidate screening.
The detector finds contiguous, narrow runs of unclassified returns 0.3–3 m
above the verified ground DEM in a boundary corridor. It excludes classified
buildings and vegetation, and returns inside known building footprints, from
built-object candidates. These are low-confidence,
unvalidated **linear-return candidates**, not automatically named fences/walls.
Some fences may be classified as vegetation or have no aerial returns; no recall
or accuracy claim is made. Observed lateral point spread is not wall thickness.
Material, permeability and below-ground depth cannot be measured by this rule.

## Storage and review

All address-specific and event-catalogue material is ignored by Git:

```
data/property-registry/
  properties/property_<hash>.json
  reviews/property_<hash>.json
  index/property_<hash>.json
  map-index.json
  raw/water-source-catalogue.json
  raw/<dataset-id>/{features,metadata,source}.json
  raw/areas/area_<hash>/<dataset-id>/...
  raw/native/{pointcloud.laz,dem.tif,dsm.tif,aerial.tif,...}
  import-manifest.json
```

Reviews are stored separately and survive evidence regeneration. The form
requires an evidence note. Numeric values must be finite nonnegative metres;
no automated result becomes `field_verified`. Existing public-app origin and
CSRF checks also apply to review writes. This is the existing shared local
research app, not a new per-user authorization system.

Confirmed requests create a base edge record, then preparation enriches it from
the available GIS/native data. Once the local civic catalogue is provisioned,
new properties also receive bounded queries of its public vector sources, cached
by area. Inaccessible sources remain explicitly blocked; empty is not missing.
Property/rating references can be kept without requesting owner identities.

## Import and refresh

The supplied organiser repository names starter tile BA31_1000_4245, Mt Albert /
Sandringham, NZTM bounds `[1753120,5915760,1753600,5916480]` (480 x 720 m).
It supplies a catalogue and memo, not a private geodata package. The importer
downloads public source responses and a bounded native tile/window only.

```powershell
docker cp C:/path/to/akl-civic-data/catalogue.json floodtwin-3d-local-review:/work/data/civic-input/catalogue.json
docker exec floodtwin-3d-local-review python -m floodtwin.cli import-civic-pilot --catalogue /work/data/civic-input/catalogue.json
docker exec floodtwin-3d-local-review python -m floodtwin.cli record-properties --workspace CONFIRMED_WORKSPACE_ID --enrich
```

The import enumerates ArcGIS object IDs, checks every batch and keeps all
publisher columns, with short GET batches to avoid server URL-length limits.
Public non-vector, manual/keyed, academic and software catalogue entries remain
catalogued rather than falsely marked downloaded. Current 2024 native data and
RGB windows are handled separately. OSM is not fused into the Council-derived
layer; its ODbL licensing/validation role requires separate handling. No private
Council drives, login bypasses or gated imagery are used. The event catalogue
and memo stay local; no publication/deployment is performed by this workflow.

Native heights require compound EPSG:2193 + EPSG:7839 LAS metadata and a matching
recorded official LINZ survey-datum receipt for DEM/DSM. STAC collection titles
are checked against that receipt because collection metadata alone omits the
vertical datum. Browser preview imagery is a separately warped display asset;
the native-resolution RGB window is retained as a TIFF.

## API and exports

| Route | Result |
|---|---|
| `GET /api/jobs/{job}/property` | Record/refresh confirmed property's available evidence |
| `GET /api/properties` | All recorded property polygons and source-coverage summary |
| `GET /api/properties/{id}` | Polygon, individual edges, linked objects and review overlay |
| `GET /api/properties/{id}/boundaries` | GIS-ready GeoJSON boundary features |
| `GET /api/properties/{id}/export` | JSON bundle for one property |
| `GET /api/properties/export` | JSON bundle for every recorded property |
| `GET /api/properties/{id}/points` | Every native point and original LAS dimension in property + tolerance |
| `POST /api/properties/{id}/segments/{edge}/review` | Validated manual attributes + mandatory note |
| `GET /api/property-sources/{source}` | Original pilot publisher feature JSON |
| `GET /api/property-sources/{area}/{source}` | Original per-request area feature JSON |
| `GET /api/property-assets/{allowed-name}` | Whitelisted pilot native asset or browser preview |

The ordinary JSON bundles include raw source-asset references/hashes rather than
base64-encoding rasters or duplicating an entire LAZ in every property. Native
points have their own lossless attribute export, including noise/withheld flags;
this differs deliberately from the filtered display. “Export all” means all
**recorded** properties, not all Auckland. Large sources are never silently
treated as completely fetched based on one truncated feature page.

## Validation limits

Focused synthetic tests cover topology, IDs, two-endpoint geometries, proximity,
proper crossing vs touching/overlap, missing/empty distinction, review durability,
native candidate screening, CSRF and exports. Real pilot counts and screenshots
are recorded in `PROGRESS.md`. No manually labelled fence validation set was
supplied; detection precision/recall and hydraulic significance remain unverified.

## Two-property browser review (16 October 2026)

The saved sample proposals for 3A Sadgrove Terrace and 23 Kitenui Avenue now
include manually inspected Google Earth top and photorealistic oblique views
through Playwright, in addition to the recorded LINZ aerial/native LiDAR.
The top-view footer displayed 18 March 2024; the 3D acquisition date was not
verified. Sources may be from different dates. Cadastral endpoints are unchanged.

All nine original edges carry ten explicit field assessments: type, material,
height, width, depth, continuity, permeability, potential influence, mapped flow
crossing and risk. Each has a status, qualitative confidence and evidence/reason.
Unknown dimensions/materials remain null, not zero. Vegetation height describes
canopy/foliage, not a measured fence crest. Obscured long mixed boundaries have
no single assigned height. Google screenshots/notes are local review artifacts,
not a Google data-download, model-training or cadastral-reconstruction pipeline.

Street View was attempted for both properties, but Google returned metadata
HTTP 500 / panorama HTTP 403 and displayed no imagery. Kitenui's Earth Street
View attempt also displayed no data. These are session failures, not claims
that the street has no public coverage. Failed views are recorded separately
and cannot be used to raise confidence. Google Earth browser availability does
not configure the app's embedded Google 3D API key.

Original assistant drafts remain unchanged. Hash-bound browser-review drafts
create revised sample bundles; previous prediction JSON is archived under
`data/property-registry/prediction-history`. Each successful view is attributed,
linked and screenshot-hashed. The 3D sidebar shows field-by-field assessments,
occlusion notes and source links, and the JSON exports retain them. Copying a
proposal fills all supported edit fields but never saves a manual review.
No proposal becomes field verified, no automatic risk inference and no hydraulic
barrier is created from a parcel edge.

## Reusable multi-view review skill and supplied-image review

`skills/property-boundary-review/SKILL.md` and its field/storage reference describe
the independent workflow: numbered parcel plan, four genuinely distinct oblique
angles, street-level coverage, source/date/property matching, per-edge components,
all ten field assessments, local save and visual/form/export verification. The
same skill is installed in the user's Codex skills directory. Missing views are
reported as partial coverage, not silently counted as successful captures.

Kitenui's later review uses four distinct user-supplied Earth screenshots and one
deduplicated February 2023 street image, plus the previously reviewed aerial and
native data. The street caption is 25, while the intended target is 23; the
house/roof/chimney/drive/garage/hedge arrangement visually matches, but is not
cadastral control. Supplied images have conversation references and null hashes
where local original bytes are unavailable. No original image file was invented.

The edit form now seeds fresh unreviewed proposal values automatically when no
manual review exists, with an explicit unsaved label. Manual reviews always win;
stale or context-only proposals do not prefill. Unobservable numbers remain null,
with a reason/placeholder, not false zeros. Component observations include relative
positions, source IDs and explicit unknowns; image-only positions are not fabricated
GIS features. Parent crossings are not inherited by ungeoreferenced components.

## Explicit classes and numeric confidence

Reviewed boundaries now have `classifications.type` and `classifications.height`:
each contains a class label and separately authored confidence_score in [0,1].
The UI displays these as percentages. Height labels use <0.5, 0.5-<1, 1-<2,
2-<3, 3-<5, 5-<10 and >=10 m, or variable_height for a mixed corridor without
one meaningful crest. Original estimates, ranges and height methods remain separate.
Occluded/unresolved values carry zero physical-attribute confidence, not invented
heights. Numbers are subjective evidence judgments, not calibrated probability,
accuracy or engineering reliability. Legacy words remain for compatibility.

`features.classifications.save_scores` checks the exact prior prediction SHA256,
requires a score/rationale for every original edge, archives and validates before
replacement. Component scores are separate. The two sample properties' nine
edges are scored. Field-assessment scores must match classification scores.
Original GIS geometry/crossings, source heights and manual reviews are unchanged.

## Mt Albert crossing-object export

Open **Boundaries** from the main navigation, then **Export Mt Albert crossings
JSON**. The 3D boundary editor also links to this control. The read-only endpoint
is `GET /api/properties/mt-albert-flow-crossings`. It uses saved evidence only;
no network providers, new AI reviews or hydraulic models are invoked.

The file includes `crossed_boundaries` (proper line crossings, excluding touches,
overlaps and nearby paths), each property's IDs, two NZTM endpoints, GIS geometry,
crossing points, linked object IDs, source attributes, effective types, available
height classifications/confidence, manual reviews and original predictions.
`objects` is the broader property-scoped list of candidates linked to those edges;
one source object can have multiple boundary associations. Across properties the
same physical source feature can recur, preserving distinct property reviews.

For the narrower spatial list use `crossing_object_ids` to select entries from
`objects`. An entry qualifies only if its geometry intersects a matched Council
flow line AND is within the property's saved tolerance of the boundary/path
intersection. Each association retains the distance, tolerance, intersects and
proper-crosses flags. This is 2D mapped screening, not observed flowing water,
hydraulic obstruction, ownership or a risk assessment. Image-only components
without GIS geometry have null relationship flags and cannot enter this subset.

Effective precedence is manual review, fresh assistant prediction, known source
asset-layer type, unknown. Stale/concealed predictions do not become asserted
physical types. Source asset-layer names have no invented numeric confidence.
Unknown type/material/dimensions remain explicit and original attributes remain
available. No automatic regionwide AI labels are generated by this export.

Coverage is the recorded project pilot, address-confirmed Mount Albert properties,
or parcels intersecting pilot bounds. There is no verified administrative suburb
polygon and this is NOT complete Mt Albert coverage. Scope, coverage bounds,
unclassified totals and record read errors are included in JSON. The provided
`AC_OLFP_Obstructions.gdb` can be normalised using
`features.crossing_export.import_obstructions(Registry(root), path)`. Original
attributes, EPSG:2193 geometry, layer name and per-file hashes are saved under
`data/property-registry/raw/supplemental/olfp-obstructions.json`; missing type
fields do not become fences. The regional export spatially joins these supplied
features to crossed boundaries without modifying original property records.

The API reuses an in-memory snapshot until property/prediction/review directories,
the import manifest or supplemental evidence change. The first export can take
several seconds to read the raw evidence; repeated downloads reuse that snapshot.

## Crossed-only pilot detection and local visual review

`features.crossing_detection.prepare(root)` stages a reproducible offline run for
the imported pilot's properly crossing boundaries ONLY. It hashes the original
LAZ, DEM and aerial assets, checks native horizontal/vertical CRS, normalises
native Z against the verified DEM, excludes withheld/noise/invalid heights,
separates vegetation/building classes and screens low unclassified connected
returns outside mapped buildings. It keeps native support, approximate GIS
return envelopes and object-specific height spreads. It does not classify every
linear point run as a fence or wall. Heights are local return envelopes, not
physical fence crests. No trained detector, remote model API or hydraulic run is
implied. Evidence-rule scores are uncalibrated, not accuracy probabilities.

Preparation produces rotated aerial corridor/profile sheets and an evidence
manifest in private `data/property-registry/crossing-detection-runs/<run>/`.
`publish(root, run_id, review_path)` requires an exact evidence hash and explicit
review of every atlas sheet before saving. Authored visual refinements stay
separate from native evidence, including alternatives and unresolved dimensions.
An overhead fence-like observation without traced GIS geometry remains an
image-only component, with null object crossing and no invented height.

Published per-property bundles live in `crossing-detections/`; previous revisions
are archived in `prediction-history/`. Registry reads merge ONLY the assessed
crossing edges and their objects. Non-crossed edges, original property JSON,
existing assistant samples and manual reviews are not rewritten. Manual decisions
still win. Changed property inputs make detections stale. The regional download
automatically includes the merged candidates; its cache watches this folder.
The map's selected-edge panel shows type scores, local object envelopes, missing
coverage and the evidence image. The 3D editor understands the same records when
that property has a confirmed 3D workspace. Pilot cadastral imports do not silently
create 114 new confirmed workspaces.

The 2026-10-16 run `detection_51ed673cf50e4f33c6b8fb93` covers 272 crossed
boundary records / 131 distinct shared lines across 114 pilot properties. All 11
sheets were inspected. It saved 402 property-linked native object candidates
(188 distinct edge-based clusters before adjacent-property duplication), plus
image-only fence-like observations on two shared lines. Five hedge-like planting
clusters received explicit local-image refinements. 56 boundary records remain
unresolved. Missing tile portions, roadside gaps and concealed fabric are NOT
zero-height walls or proof of an unobstructed path. No batch-wide Google Earth
four-angle or Street View verification, complete object recall or accuracy claim.
