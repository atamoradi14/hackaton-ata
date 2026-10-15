# Local development environment

Run from Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
```

Backend: WSL2 Ubuntu-24.04, isolated micromamba environment `floodtwin`.
Existing Windows Python installations are untouched. Solver: official Deltares
SFINCS CPU 2.4.0 image pinned by digest; the WSL `sfincs` executable is a Docker
launcher. It mounts only the current run directory and disables networking.
HydroMT-SFINCS 1.2.2 and HydroMT 0.10.1 use the released pre-1.0 API.
Affine is pinned to 2.4.0: Affine 3 breaks PyFlwDir's compiled metre-path API.
PDAL core is installed without optional Arrow/TileDB plugins, avoiding unrelated
native-library constraints. GeoTIFF, CRS and real solver tests are mandatory.

`locks/conda-linux-64.lock` records exact Conda builds/URLs; the pip lock records
only PyPI-managed versions, excluding unportable Conda build paths. Run
`bash scripts/restore-locked.sh` in WSL to restore a second environment; this
was tested successfully. Do not silently upgrade the solver or HydroMT family.
The YAML is the compatibility specification; locks represent tested versions.

## External access and manual gates

- Windows application installers may require UAC administrator consent. WSL
  installation/virtualization or Docker Desktop installation also needs admin
  rights when absent. Current WSL2 and Docker engine have been tested.
- `.env` and `configs/local_site.yaml` stay private and Git-ignored. Credentials
  are not included in reproducibility files or Docker build contexts.
- A LINZ key supplied in chat was saved privately. A schema response embedded
  it in a URL exposed by a tool preview; rotate that key and replace it in `.env`.
  Cached schemas now redact credential URLs. Do not paste replacement keys.
- Official address candidates require visual user confirmation and parcel join;
  the current target was confirmed by the user on 14 October 2026.
- Site-specific HIRDS export, temporal storm pattern, datum evidence, hydrologic
  domain, reviewed barriers and drainage measurements are required before site
  hydraulics; synthetic rainfall is never used as site design rainfall.
  HIRDS now requires a separate Earth Sciences NZ DataHub account/purpose;
  see [HIRDS_ACCESS.md](HIRDS_ACCESS.md). The user has no account yet.
- Project-scoped `.codex/config.toml` configures Playwright MCP and read-only
  GitHub MCP. GitHub reuses the existing `gh` authenticated keyring at launch;
  if unavailable, run `gh auth login` interactively. No token is persisted.
  Both servers passed real initialize/tool tests; Playwright also passed a
  synthetic browser page/snapshot test, GitHub an authenticated `get_me` read.
  Playwright MCP 0.0.83 depends on a pinned alpha browser runtime
  `1.64.0-alpha-1790635538000`; this is disclosed and tested.
  Restart/reload the host and trust this project if required;
  the current conversation cannot hot-load newly configured servers.
- No remote repository is created and no private site data is published.
- OpenTopography key is stored privately but not used/validated: selected local
  point-cloud tiles are available through its public unsigned bulk endpoint.

## Optional later components

PostGIS: set a private `POSTGIS_PASSWORD`, then `docker compose --profile postgis
up -d postgis`. Only localhost:55432 is exposed. Empty passwords deliberately
cannot initialize the database; existing database volumes must be preserved.

SWMM: `micromamba create -f optional-swmm.yml`; validate the toolkit separately.
The separate optional environment was installed; engine 5.2.4 import verified.
This provides an engine interface for later work, **not** SFINCS/SWMM coupling.
Coupling needs explicit timestep/head exchange and volume conservation tests.

Docker Compose provides the tooling build and pinned standalone solver profile.
`scripts/validate.ps1` is the full integrated validation command. The Docker
tooling service validates dependencies with `--external-solver`; numerical
hydraulics are checked through the separately pinned solver container. No Docker
socket is exposed to the tooling service. PostGIS remains uninitialized.
