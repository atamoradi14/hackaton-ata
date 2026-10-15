#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
env_file="${AUCKLAND_FLOWLAB_ENV_FILE:-.env.production}"
if [[ ! -f "$env_file" ]]; then
  cp .env.production.example "$env_file"
  chmod 600 "$env_file"
  echo "Created $env_file. Fill ACME_EMAIL and LINZ_API_KEY, then run again."
  exit 1
fi
[[ "$(uname -m)" == x86_64 ]] || { echo 'This pinned solver stack requires an x86_64 Linux node.'; exit 1; }
docker info --format '{{.OSType}}' | grep -qx linux
docker compose version
env_path="$(realpath "$env_file")"
compose=(docker compose --env-file "$env_path" -f compose.production.yaml)
"${compose[@]}" config --quiet
# Checker runs inside the image; the node needs neither Python nor Conda.
"${compose[@]}" build app
"${compose[@]}" run --rm --no-deps -v "$env_path:/tmp/deploy.env:ro" --entrypoint /usr/local/bin/_entrypoint.sh app /opt/conda/bin/python /work/deploy/check-env.py --env-file /tmp/deploy.env
"${compose[@]}" run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
"${compose[@]}" up -d --wait --wait-timeout 180 app caddy
"${compose[@]}" ps
echo 'Run bash deploy/validate.sh to verify the numerical solver and public HTTPS access.'
