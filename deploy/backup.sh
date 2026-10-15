#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
chmod 700 backups
env_file="${AUCKLAND_FLOWLAB_ENV_FILE:-.env.production}"
compose=(docker compose --env-file "$env_file" -f compose.production.yaml)
echo 'Run when property preparation is idle; files are private, encrypt before transferring.'
archive="backups/auckland-flowlab-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
umask 077
"${compose[@]}" exec -T app tar -czf - -C /work data runs configs reports > "$archive.partial"
mv "$archive.partial" "$archive"
echo "Saved $archive. Caddy certificates and optional PostGIS require separate backups; see deployment guide."
