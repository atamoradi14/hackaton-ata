# Offline hydraulic quality suite

Run from the project root in PowerShell, after installing and validating the environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/floodtwin.ps1 synthetic-quality run --root runs/quality-new
powershell -ExecutionPolicy Bypass -File scripts/floodtwin.ps1 synthetic-quality validate --root runs/quality-new
```

`run` requires a new directory and invokes the actual pinned SFINCS 2.4.0 Docker
launcher. No API keys, site data or rainfall account are required. The image must
already be pulled; solver containers have no network. Each case saves input hashes,
solver logs/exit status/wall time, output hashes, all-cell observations and volume
diagnostics. `validate` rejects changed input/output files, an unexpected solver
version, incomplete histories, nonfinite levels, negative depths and failed exits.
The full `scripts/validate.ps1` command also runs this suite in a new timestamped
directory. `overview.html`, `comparison.png` and `validation.json` are generated
only after all numerical acceptance checks pass.

## Explicit synthetic inputs

The grid is a closed 40 m × 10 m rectangle, with 2 m cells (1 m in the refinement
case), synthetic relative elevations, no rain, no infiltration, no drains and
assumed Manning roughness 0.03. The local-inertial option uses `advection=0`.
All-cell observations are sampled every 10 seconds for one hour. All cases are
initially wet; dry behaviour is independently checked in the original rain/dry
fixture. These closed outer boundaries intentionally isolate internal fluxes.
They are not proposed boundary conditions for the Auckland property.

| Fixture | Initial state and expected behaviour |
|---|---|
| Still water | Bed decreases at 0.01 m/m; level is uniformly 0.6 m. It remains stationary. |
| Slope | Same bed with uniform 0.2 m depth. Water moves downslope and approaches the storage-derived 0.4 m level. |
| Open | Flat bed; left/right levels 0.6/0.1 m. Redistribution approaches 0.35 m. |
| Finite weir | Same initial heads with a 0.4 m crest at x=20 m spanning the whole channel, coefficient 0.6. Water overtops while retaining a higher upstream level than the open case. |
| Below crest | Left/right levels 0.3/0.1 m with the same finite weir. No transfer is expected. |
| Infinite barrier | Same 0.6/0.1 m heads with an explicitly hypothetical infinitely high thin dam. No transfer is expected. |
| Cell refinement | Finite weir repeated at 1 m cells instead of 2 m. Compartment mean levels are compared at every sampled time. |
| Timestep sensitivity | Finite weir repeated with maximum timestep 0.25 s instead of 0.5 s. The actual adaptive timestep is recorded from the log. |

Finite structures use the installed HydroMT-SFINCS 1.2.2 geometry writer with
explicit crest/coefficient columns. The official [SFINCS structure documentation](https://sfincs.readthedocs.io/en/latest/input_structures.html)
describes finite crest overtopping and thin dams. Its current Python examples
include newer component APIs; this project uses the verified installed API.

## Acceptance and limits

Acceptance thresholds are declared in code before each run: maximum relative
storage drift over **all** saved times ≤0.5%; stationary level change ≤0.00001 m
and stationary observed speed ≤0.00001 m/s;
final open/slope equilibrium error ≤0.005 m at every cell; finite-weir net transfer
to the right >10 m³ and final upstream mean between 0.39/0.43 m; upstream mean
at least 0.03 m above the open baseline. Maximum compartment-mean difference
across cell/timestep repeats must be ≤0.02 m over the full time series.

The sudden initial head difference launches waves. Ten-minute runs did not
satisfy the open-case per-cell equilibrium check; a longer settling period is
used. The thresholds were not relaxed to hide the transient. Closed-case mass
balance is computed directly from all-cell depth × area; downstream storage
gain is net internal transfer, not a direct observation of instantaneous weir
discharge.

This suite checks conservation, still-water stability, qualitative overflow and
numerical sensitivity. It does not validate an analytical transient discharge
curve, wet/dry-front accuracy, measured roughness, building effects, real site
boundary/domain convergence or field calibration. Cell refinement of synthetic
geometry adds no new measured terrain information. Process wall time includes
Docker startup; container peak CPU/RAM are not separately instrumented.
Real site design-storm runs still require HIRDS rainfall and reviewed connected
domain, outlet, loss, roughness, barrier and drainage assumptions.
