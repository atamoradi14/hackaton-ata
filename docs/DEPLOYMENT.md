# Auckland FlowLab on daryajan.com

This deploys the address/map/evidence app as a public research workspace on your
own Linux node. Website login was removed at the user's request. Every new address
still requires map confirmation, and every hydraulic run requires an assumptions
review. Existing confirmed workspaces/exports and simulation controls are public;
there is no tenant isolation. Design-storm modelling still requires actual HIRDS
rainfall and scientific domain/parameter review.

## Requirements and current missing settings

| Requirement | Current local status | Action on the node |
|---|---|---|
| `DOMAIN` | Default `daryajan.com` | Point DNS A to the node; publish AAAA only if IPv6 also works |
| `ACME_EMAIL` | Configured privately for the deployed node | Set your contact email for a new node |
| `LINZ_API_KEY` | Present in private local `.env` | Copy securely to the node's `.env.production` |
| `OPENTOPOGRAPHY_API_KEY` | Present locally, optional | Only needed for a future API route requiring it |
| `POSTGIS_PASSWORD` | Unset, optional | Set only before enabling the `postgis` profile |
| HIRDS rainfall export | **Unavailable** | Obtain an Earth Sciences NZ DataHub account/export; not an environment variable |

Use an x86_64 Linux node with Docker Engine and Docker Compose v2.24.4 or newer.
Install standard Bash, curl and tar for the helper scripts. Start with 4 vCPU,
8 GiB RAM and at least 60 GiB free SSD space; large terrain jobs
may need more. The default app ceiling is 6 GiB/4 CPUs and one active preparation.
Monitor disk usage: downloaded crops and model output accumulate in named volumes.
Inbound TCP 80/443 is required for the bundled Caddy HTTPS setup; UDP 443 enables
HTTP/3. Allow outbound HTTPS for image/package downloads and GIS providers. DNS,
firewall changes and Docker installation may require your node administrator.
Native Python, Node, Conda, GDAL, QGIS and CloudCompare are not needed on the node;
the geospatial runtime and pinned SFINCS binary are inside the application image.
Do not expose port 8765 or a Docker socket publicly/to the app.

## First launch on Linux

Transfer the source securely to the node, excluding `.env`, data, reports and
private configurations from public repositories. In the project directory:

```bash
test -f .env.production || cp .env.production.example .env.production
chmod 600 .env.production
```

Edit `.env.production` with the certificate email and private provider settings.
No website username/password or bcrypt hash is required. Then:

```bash
bash deploy/up.sh
bash deploy/validate.sh
```

`up.sh` checks Compose, builds the exact locked dependencies, validates settings
without displaying secret values, validates Caddy, and starts healthy services.
`validate.sh` checks dependencies, runs eight real offline SFINCS cases with saved
NetCDF diagnostics, and checks public HTTPS access without credentials.
It must run against your working DNS/HTTPS endpoint; no insecure TLS flag is used.
For a names-only checklist before building, where Python is available:

```bash
python deploy/check-env.py --env-file .env.production
```

Never print `docker compose config` in logs: it includes expanded keys. Use
`docker compose --env-file .env.production -f compose.production.yaml config --quiet`.
Docker administrators can inspect container environment variables: restrict node
access and protect the private env file. Images/build contexts omit private data.

## If your node already runs Caddy

Do not start the bundled Caddy on occupied ports. Fill the same environment file,
set `CADDY_NETWORK` to the existing Caddy container's Docker network, and use:

```bash
docker compose --env-file .env.production -f compose.production.yaml -f deploy/compose.existing-caddy.yaml up -d --build --wait app
```

Add the block from `deploy/Caddyfile.existing` to the existing Caddy configuration,
and supply DOMAIN to **that** Caddy process.
The global ACME contact stays in your existing configuration. Validate and reload
it using your established administration procedure. The app is reached through
network alias `auckland-flowlab-app:8765`. The base Compose file still requires
its certificate email during parsing even though
its bundled Caddy is not started. A native host Caddy needs a separate deliberate
loopback-only port mapping; the external-network override is for container Caddy.

## Data, solver and maintenance

The app mounts persistent `site_data`, `model_runs`, `site_configs` and `reports`
volumes; Caddy persists certificate state in `caddy_data` and `caddy_config`.
There is no public data in the image. A fresh node fetches supported site evidence
after address confirmation. To seed your already prepared private cache before
first use, copy it over SSH and stream it into the running app as its own user:

```bash
tar -C /secure/local/project -cf - data/processed/site | docker compose --env-file .env.production -f compose.production.yaml exec -T app tar --no-same-owner -xf - -C /work
```

Only import into an empty destination. Copying a cache does not authorize a new
address: the app still verifies exact address/parcel IDs and requires confirmation.
Run `bash deploy/backup.sh` when preparation is idle; encrypt its private archive
before moving off-node. Also back up the private env separately, Caddy volumes,
and use `pg_dump` for optional PostGIS. Restore only into an empty stopped workspace,
then extract as the app user using the same tar approach. Existing unfinished jobs
are marked interrupted on restart rather than reported as complete. No automatic
job retry/resumption or durable queue exists; search and confirm again to retry.

Updates: rerun `bash deploy/up.sh`, then validation. Roll back using your previous
source checkout/image tag and the same volumes. `docker compose ... down` stops
containers without deleting volumes. Never use `down -v` or volume pruning for
maintenance. The image bundles the pinned official SFINCS 2.4 solver and its own
ELF loader/libraries; it requires no nested Docker permissions. Synthetic quality
tests are physics validation only, not a Pemberton flood-risk calculation.

PostGIS is opt-in and not yet used by the app:
`docker compose --env-file .env.production -f compose.production.yaml --profile postgis up -d postgis`.
Set POSTGIS_PASSWORD first; there is no host database port. SWMM coupling remains
a later milestone; the optional local environment is not a production dependency.
QGIS/CloudCompare are desktop inspection tools. GitHub/Playwright MCP belong to
development and are not exposed as production services.

## Offline deployment regression check

For developers with Python and Docker:
`python deploy/test-stack.py`. This launches an isolated Compose project, uses a
test-only internal TLS CA, tests public access, origin/CSRF behavior, assets,
private-file gates and data persistence through container replacement, then stops
its containers while preserving test volumes. It does not contact LINZ or attempt
certificate issuance for daryajan.com. Results are in ignored
`reports/deployment-test/result.json`. This is distinct from live domain validation.

References: [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[Docker Compose services](https://docs.docker.com/reference/compose-file/services/).
