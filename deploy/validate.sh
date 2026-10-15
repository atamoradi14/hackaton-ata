#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
env_file="${AUCKLAND_FLOWLAB_ENV_FILE:-.env.production}"
env_path="$(realpath "$env_file")"
compose=(docker compose --env-file "$env_path" -f compose.production.yaml)
"${compose[@]}" config --quiet
# Mount the private env only into this disposable validation process.
"${compose[@]}" run --rm --no-deps -v "$env_path:/tmp/deploy.env:ro" --entrypoint /usr/local/bin/_entrypoint.sh app /opt/conda/bin/python /work/deploy/check-env.py --env-file /tmp/deploy.env
"${compose[@]}" exec -T app /opt/conda/bin/floodtwin doctor
"${compose[@]}" exec -T app /opt/conda/bin/floodtwin synthetic-quality run --root "/work/runs/quality-deployment-$(date -u +%Y%m%dT%H%M%SZ)"
read -r -p 'Public origin [https://daryajan.com]: ' origin
origin="${origin:-https://daryajan.com}"
status="$(curl --silent --output /dev/null --write-out '%{http_code}' "$origin/healthz")"
[[ "$status" == 200 ]] || { echo "Expected public HTTP 200; got $status"; exit 1; }
curl --fail --show-error "$origin/healthz"
echo; echo 'Deployment validation passed, including eight actual offline SFINCS cases.'
