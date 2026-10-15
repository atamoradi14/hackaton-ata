#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export MAMBA_ROOT_PREFIX="$HOME/.local/share/mamba"
MM="$HOME/.local/bin/micromamba"
"$MM" run -n floodtwin floodtwin doctor
"$MM" run -n floodtwin pytest -q
"$MM" run -n floodtwin floodtwin synthetic build
for case in rain dry; do
  (cd "runs/synthetic/$case"; "$MM" run -n floodtwin sfincs > solver.log 2>&1)
done
"$MM" run -n floodtwin floodtwin synthetic validate
quality_root="runs/quality-$(date -u +%Y%m%dT%H%M%S)-$$"
"$MM" run -n floodtwin floodtwin synthetic-quality run --root "$quality_root"
