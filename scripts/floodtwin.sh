#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec "$HOME/.local/bin/micromamba" run -r "$HOME/.local/share/mamba" -n floodtwin floodtwin "$@"
