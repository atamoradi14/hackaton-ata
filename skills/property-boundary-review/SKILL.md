---
name: property-boundary-review
description: Review property-boundary objects from multiple Google Earth 3D angles, Street View or supplied photos, aerial imagery and LiDAR; save per-edge GIS-linked predictions with complete field assessments and populate the local map editor. Use for fences, walls, hedges, gates, openings and adjacent objects, not cadastral surveying or hydraulic risk certification.
---

# Multi-view property boundary review

Produce an image-supported inventory for every original parcel edge, not a generic
description of the house. Work independently through acquisition, interpretation,
local persistence and visual verification. A skill guides Codex; it is not an
unattended detector/service and cannot guarantee access to Google or see hidden
foundations. Do not add a model API or change credentials unless requested.

## Scope and prerequisites

Use the user's selected properties and repository, not addresses copied from an
old example. Read the repository's AGENTS.md and required source/schema guidance.
Keep existing changes, manual reviews and native data. No deployment, hydraulic
modelling or full test suite unless requested. Never expose environment secrets.

For browser acquisition, use the installed Playwright skill if available and a
real headed browser. Check `npx`/the available Playwright connector first. Use
the user's authorized working browser session when the tool supports it; do not
assume an isolated session can access the same imagery. Supplied images are valid
evidence even when an automated browser failed. Read them directly and identify
duplicates. Do not generate replacement evidence images.

Before constructing saved records read [references/fields-and-persistence.md](references/fields-and-persistence.md).
It defines field semantics and the FlowLab adapter. Other repositories may use a
different storage interface; preserve the same evidence/unknown distinctions.

## 1. Establish the property and edge key

Load the confirmed parcel, address point and every original edge ID with its two
endpoints. Retain exact topology, including tiny corner edges, holes/multiparts
and separate parcels where applicable. Use the authoritative parcel source for
geometry; do not redraw cadastral positions from Google images.

For FlowLab retain WGS84 `[longitude, latitude]`, projected EPSG:2193 metres and
verified NZVD2016 elevation data. A 2D endpoint has no invented Z. Number edges
on the recorded aerial/top view; calculate their bearings from the endpoints so
that 'front/left/rear' cannot silently change with the camera. Locate the road
frontage and shared drive; a neighbouring driveway need not lie on this parcel.

Match imagery by at least the roof/chimney, driveway/outbuilding and adjacent
house/street arrangement. A Street View caption is often the camera's nearest
address, NOT proof of the house being inspected. Record both displayed and target
addresses, the matching evidence and any ambiguity. Ambiguous imagery cannot
support a definite property-specific claim.

## 2. Acquire a coverage-complete evidence set

For each property seek:

- a numbered plan/aerial showing the entire parcel;
- four distinct close oblique 3D views: front-left, front-right, rear-left and
  rear-right, or equivalent headings distributed around the property;
- street-level frontage and both frontage corners; use additional viewpoints
  where side gates, fences or retaining walls need them;
- available original LiDAR/DEM evidence, not just a textured rendered mesh.

This is a **view coverage target**, not permission to invent missing views.
Inspect each image at sufficient scale to see the boundary corridor; four
screenshots of nearly the same angle do not satisfy it. Rotate to expose each
side, stop orbiting, wait for geometry/imagery to settle and capture again.
Inspect thin objects close up; foliage and neutral mesh sides can hide returns.

With Playwright, snapshot before element references and refresh after changes.
Google Earth's canvas may require its 'Enable accessibility' button to receive
keyboard Enter. Prefer accessible heading/tilt controls; if intercepted, inspect
the dialog and dismiss its tip, use keyboard interaction or another supported
browser mechanism. Do not keep clicking the same blocked control. A changed URL
or slider does not prove the rendered camera moved: compare the actual image.
Record observed heading when available; otherwise use descriptive view labels,
not fabricated bearings. Do not claim a north-facing capture after reset failed.

Use normal provider UI only. Preserve attribution/dates. Store local QA screenshots
under `output/playwright/<property-id>/`; no bulk tile scraping, access-control
bypass, public imagery redistribution or training dataset extraction. Existing
provider/user restrictions still apply.

Record ID, provider, source kind, URL if known, capture/review date, imagery date
(or unknown), view label, property match, attribution and limitations per view.
Hash local originals. For conversation-only images record attachment index and
conversation reference; leave artifact/hash null if original bytes are not on
disk. Do not invent files, hashes, URLs, acquisition dates or successful access.

If Street View fails, try one normal alternative such as Earth's Street View or
a nearby road point. If it still fails, record the actual error, use supplied
street images where available and finish a clearly **partial** review. Do not
claim completed multi-view acquisition or repeatedly retry authorization errors.

## 3. Build the edge-by-view observation matrix

For every original edge record which views expose its corridor, base, crest and
ends, and what remains occluded. Distinguish:

- directly visible object;
- reasonable semantic/material/dimension estimate;
- LiDAR-only candidate;
- hidden/unresolvable feature;
- positive observation of an open area (not simply 'nothing visible').

Identify ALL supported components beside an edge: hedge + underlying possible
fence, masonry retaining wall + fence above, gate/opening, building edge, kerb,
driveway/paving and overhead trees. An adjacent object is not automatically on
the cadastral line or owned by the selected property. Record setback/proximity
only if spatially supported. Expose mapping ambiguity instead of snapping the
object onto the cadastral edge.

Use one parent record per original edge and separate component objects. Split
the **physical observations**, not the original parcel topology. Each component
needs its own stable ID, parent edge, type, position/extent description, attributes,
sources, alternatives and confidence. Where georeferencing is insufficient use
`geometry: null` and `position_status: relative_image_position_only`; do not turn
an image bounding box into fabricated GIS endpoints. Original edge endpoints
remain the GIS anchor. Mark coverage fractions unresolved unless actually mapped.

## 4. Fill every field responsibly

Return an explicit assessment for type, material, height, width, depth,
continuity, permeability, potential influence, mapped flow crossing and risk.
Never omit a field. Populate supported values rather than defaulting everything
to unknown, but a hidden foundation depth cannot be 'filled' with a real numeric
measurement from photos. Use null plus a concrete reason and required follow-up.

Keep confidence **per field**, with source IDs and method. Confidence in 'hedge'
does not transfer to a hedge height, fence material, boundary coincidence or
hydraulic porosity. Prefer broad, labelled visual ranges over false precision.
Record separately authored numeric type and height confidence scores in [0,1],
displayed as 0-100%. Use explicit classification labels for both, including height
bands and variable_height for mixed objects. The score is a subjective evidence
judgment, NOT a calibrated probability/accuracy rate. Do not mechanically convert
low/medium words into numbers. Never call a range a calibrated confidence interval.
Use unresolved/occluded labels with a zero physical-attribute score when no
defensible assignment exists; a low score does not justify inventing a height.
Conflicts across dates remain documented; do not silently merge a removed fence
and a newer hedge into one current structure.

Estimate heights from native profiles only where object association and local
ground are credible. A corridor's p95 canopy height is NOT its fence height.
Visual scale estimates require an explicit reference and perspective uncertainty;
if no defensible reference exists, leave the numeric dimension unresolved. Never
use camera altitude, nominal car/door sizes or assumed fence standards as exact
measurement. Separate canopy envelope, fence crest, wall crest and roof height.

Distinguish visible slats/gaps from hydraulic permeability; do not assign numeric
porosity from foliage. Derive mapped flow crossing from original GIS intersection,
not an apparent gutter, photo or AI water trace. Potential influence may be a
labelled screening hypothesis; no validated flood-risk level from these images.

## 5. Save, populate and verify

Save locally using the repo's prediction schema, original input revision and
evidence references. Archive the previous prediction bundle before replacement;
retain raw sources and any manual reviews. Do not store image inference as a
survey or automatically field-verified human review. Property JSON and edge
GeoJSON should include the component observations and field assessments.

On the 3D page select every edge. The form should prefill fresh supported
prediction values when no manual review exists, with an **unsaved/unverified**
label. Existing manual decisions win; stale/context-only predictions do not
prefill. An unknown numeric dimension remains blank/null with its reason shown,
not zero or a made-up plausible number. Evidence notes must explain unknowns.
Support correction and explicit Save without auto-accepting the assistant.

Run focused schema/geometry/form checks and verify real HTTP exports. Inspect
the rendered 3D lines, correct selected edge, values, component inventory and
source notes. Do not mark a browser click or successful file write as visual QA.
Update PROGRESS.md when required by the repo.

## Completion criteria and handoff

Report separately: properties/edges reviewed; view coverage acquired versus
missing; fields populated versus unresolved; inferred objects versus GIS context;
local save/export paths and visual/test evidence. Use a short edge/type/component
table when it makes the mapping clearer. Include unknowns needing better images,
LiDAR profiles or a field measurement. Do not say 'all fields measured', 'all
objects detected' or 'same quality for every property' without supporting coverage.

Recommended invocation: `$property-boundary-review Review the selected properties
independently using four distinct Earth 3D angles, Street View, aerial and native
LiDAR. Identify components along every original boundary, assess every field,
save local JSON, prefill the 3D editor and verify it visually. No deployment or
full tests.`
