# Agent instructions for Codex — Auckland Flood Digital Twin

You are the lead geospatial software engineer and hydraulic model developer. Read CODEX_MASTER_PLAN.md, SOURCES.md, config.example.yaml before coding.

## Primary objective
Implement a real, reproducible, private/local research prototype to simulate surface flooding near a verified property using Auckland Council GIS data, 2024 LiDAR DEM/DSM/point cloud, drainage scenarios, actual rain-on-grid 2D hydraulics and reviewed barriers.

## First response expected from you
- State current repository status, intended first milestone, available runtime/solver/data access, and blocker questions.
- List exact files and small commands you will implement/run first.
- Do NOT pretend to have downloaded data, confirmed the address location, simulated water, validated outputs or executed software when you haven't.

## Operating rules
- Work incrementally: synthetic physics fixture -> address/site GIS -> terrain -> SFINCS site model -> obstacle scenarios -> drainage scenarios -> UI.
- Prefer SFINCS via a version-compatible HydroMT-SFINCS stack. The HydroMT plugin is not the SFINCS executable. Verify versions, binary install and documented APIs before coding.
- Never substitute a D8 runoff line trace, image animation, or LLM-generated coloured overlay for a 2D mass-conserving hydraulic run. Mark screening outputs as non-hydraulic.
- Never silently assume: terrain datum, valid rainfall intensity, wall height, fence porosity, pipe diameter, pipe invert, inlet/outlet connectivity, drainage capacity, flooding at target property, or real source data.
- Check datum and units on all geodata. Use NZTM2000 EPSG:2193 and NZVD2016 for all model elevations. Convert only with authoritative relationship grid and recorded method.
- For walls, use measured or reviewed finite-height weir structures. Thin dam is an explicitly infinite-barrier scenario only. Don't block every parcel boundary.
- Provide provenance and assumption status for each layer, feature, parameter and output.
- Secure LINZ credentials and data; keep address-specific local configs out of public repos and respect any Auckland Council hackathon data-use restrictions.
- Test numerical and integration logic, make fixtures offline and synthetic; ensure mass balance, domain convergence and model stability diagnostics.
- Present uncertainties prominently. No engineering signoff, no definite property flood-risk claim.
- Ask user only for indispensable things and keep working on offline tasks otherwise.

## Milestone contract
At end of each task update `PROGRESS.md`: completed commands/tests, blockers, actual vs synthetic data, caveats, next step. Then proceed to next testable task.

## Start now
Create the project structure, .gitignore, `floodtwin doctor` and synthetic hydrology/hydraulics test, package/version choices, and provider metadata introspection. Do not attempt the entire project as a single untested code generation.
