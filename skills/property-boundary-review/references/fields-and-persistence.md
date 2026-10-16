# Field contract and FlowLab adapter

## Canonical edge/component output

Every field needs `status`, `confidence`, `basis` and `source_ids`. Use
`estimated`, `unknown` or `mapped_screening`; confidence `low`, `medium` or
`not_assessed` in the current FlowLab schema. Do not silently raise these enums.
Unknown is a completed assessment, not a missing field. Numeric values are metres.
For new reviewed labels also require `classifications.type` and
`classifications.height`, each with `label` and `confidence_score` in [0,1].
Use `confidence_method: assistant_subjective_uncalibrated`, `calibrated: false`
and an authored `score_basis`. The UI displays percentages, not validated
probabilities. Legacy confidence words remain only for compatibility.

Height bands are <0.5, 0.5-<1, 1-<2, 2-<3, 3-<5, 5-<10 and >=10 metres;
mixed edges can use variable_height without inventing a single numeric height.
Retain actual estimate/range/height method separately. Confidence in a variable
class is not confidence in a numeric crest. Occluded/unresolved/not-applicable
physical values receive zero, not a fabricated certain label.
See `src/floodtwin/features/classifications.py`: `annotate` attaches an explicitly
authored score pair; `save_scores(root,pid,review_path)` requires a property ID,
SHA256 of the exact current prediction JSON and every edge's numeric type/height
score plus rationale. Optional component scores are keyed by component ID (or
component_1 etc. for older coarse notes). It archives before saving; never reuse
a scoring review after the underlying prediction revision changes.

| Field | Interpretation |
|---|---|
| type | fence, wall, retaining_wall, hedge, vegetation, gate, building, kerb, bund, mixed, other or unknown; parent mixed if components differ |
| material | visible/estimated construction or vegetation material; null if concealed; do not call a green surface timber/concrete |
| height_m | object-specific above-local-ground estimate; requires range + height_basis; never treat canopy/roof heights as fence height |
| width_m | cross-boundary thickness/spread, not edge length; null unless supported, with width basis/range if estimated |
| depth_m | buried/embedment depth; normally null/not observable, not the same as hedge spread or wall height |
| continuity | continuous/discontinuous only over the stated observed extent; otherwise unknown |
| permeability | solid/partly_permeable/permeable only when evidence supports physical fabric; hydraulic numeric porosity remains unknown |
| potential_influence | block/divert/constrict/channel/negligible/uncertain, explicitly screening only; default uncertain without defensible structure/path evidence |
| crossed_by_flow_path | true/false/null from original GIS, including separate relation crosses/touches/overlaps; never changed by image interpretation |
| risk_level | null/not assessed absent a validated assessment; don't manufacture a flood-risk rating |

Every component should carry the same field keys/assessments where relevant,
plus `id`, `parent_edge_id`, `position_note`, `position_status`, `geometry`,
`source_ids`, `confidence`, `notes` and alternatives/occlusions. A parent may
have null height even if two of its components have different known heights.
Flow crossing of the parent must not be inherited as a component crossing unless
that component's actual geometry was intersected. Use null for unresolved
component geometry/crossing. Components are predicted observations, not extra
surveyed polygons. Preserve original edge endpoints in the exported parent.

## Source records

Browser source: `id`, `provider`, `view`, `view_direction_label`, `status:viewed`,
`url`, `artifact`, `sha256`, `attribution`, `imagery_date`, identity and limitations.
The URL must be an actual observed or clearly labelled navigation URL; a camera
URL need not reproduce the frozen screenshot heading after Earth auto-orbits.

Supplied image: `source_kind:user_attachment`, `attachment_index` (one-based),
`conversation_reference`, `status:viewed`, `provider`, `view`, view label,
attribution, identity and dates. If unavailable locally use artifact/sha256 null
and say why. Duplicate uploads are one evidence view, not extra coverage.
Store failed attempts separately; they cannot be referenced as viewed evidence.

Use `view_coverage` to report target counts, actual distinct view IDs, numbered
plan reference, per-edge visibility and `complete` or `partial_with_gaps`.
Four oblique images do not resolve every object if trees hide the bases.

## FlowLab live paths (verify before use)

Detect the active repository/root and container instead of assuming paths from
an older checkout. The local review has used `127.0.0.1:8774` and container
`floodtwin-3d-local-review`; check them. Keep production keys server-side and do
not print env files. No Google browser key is needed to inspect public Earth,
but browsing does not configure embedded Google tiles in the app.

Read these current implementation files before adapting data:

- `src/floodtwin/properties.py`: Registry, persistent JSON and review separation.
- `src/floodtwin/features/sample_evidence.py`: native evidence and sample saver.
- `src/floodtwin/features/predictions.py`: current validation contract.
- `web/boundary-form.js`, `web/boundary-editor.js`: display/edit precedence.

1. Obtain a confirmed workspace through the existing address/parcel workflow.
   `GET /api/jobs/{job}/property` returns the property ID and original edges.
   `GET /api/properties/{id}` returns current source and prediction data.
2. Run `prepare(root, workspace)` in the project's compatible Python runtime
   to inspect the original numbered aerial/native evidence. It records image
   hash, input revision, per-edge return statistics and connected canopy clusters.
   It is evidence extraction, not an AI detector.
3. Author an initial local draft with property_id, evidence_image_sha256 and
   `edges` containing EVERY original entity_id. Include all physical attributes,
   rationale, components, field_assessments and per-edge visual_review. For a
   browser-backed review include the top-level visual_review/source metadata.
   Use existing raw object results/candidates, not imaginary detections.
4. `save_sample(root, pid, draft_path)` attaches original GIS crossing facts,
   native evidence and explicit object/context predictions, validates then saves.
   It does not invoke a remote model. Archive any old prediction first.
5. For the two existing samples, `save_visual_sample(root, pid, review_path)`
   accepts property_id, SHA256 of the original assistant draft, edge_reviews and
   visual_review. It requires every original edge once, archives the prior bundle
   and makes a revised draft. Edge reviews can carry material/height/components
   and field_assessment overrides. Its conservative defaults fill unresolved
   material/width/depth/permeability/risk; override them only with actual evidence.

Actual import pattern (run only in the detected project runtime; paths are inputs):

```python
from pathlib import Path
from floodtwin.features.sample_evidence import prepare, save_sample, save_visual_sample
root = Path('/work')  # replace with verified runtime repo root
# prepare(root, confirmed_workspace_id)
# save_sample(root, property_id, reviewed_draft_path)
# save_visual_sample(root, property_id, reviewed_revision_path)
```

In the current Docker review, src/web/data are bind-mounted; output/playwright
may NOT be mounted. Before saving browser sources, copy just the inspected QA
screenshots into matching `/work/output/playwright/...` paths if necessary.
Attachment-only sources need no invented screenshot file or hash.

Persistent files are under ignored `data/property-registry/`: assistant-drafts,
sample-evidence, predictions, prediction-history, reviews and object-reviews.
Do not change confirmed structures merely to make a prediction visible.

Verify `GET /api/properties/{id}/export` (JSON), `/boundaries` (GeoJSON), and
`terrain3d.html?job={job}`. Select each edge in LiDAR and Earth modes; verify
prediction/field notes, prefill and unchanged manual reviews. JSON `.prediction`
is separate from `.structure`; a draft form is not a persisted user decision.

Focused checks where present: `node tests/web-boundary-form.mjs`,
`node tests/web-boundaries.mjs`, selected `tests/test_boundary_predictions.py`,
JS syntax, frontend build and `git diff --check`. Do not run hydraulics, all
provider acquisition or a full test suite merely to assess images.
