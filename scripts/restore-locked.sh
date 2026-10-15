#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export MAMBA_ROOT_PREFIX="$HOME/.local/share/mamba"
MM="$HOME/.local/bin/micromamba"
"$MM" create -y -n floodtwin-restored --file locks/conda-linux-64.lock
"$MM" run -n floodtwin-restored pip install --no-deps -r locks/pip-linux-64.lock
"$MM" run -n floodtwin-restored pip install --no-deps -e .
install -m 755 scripts/sfincs "$MAMBA_ROOT_PREFIX/envs/floodtwin-restored/bin/sfincs"
"$MM" run -n floodtwin-restored pip check
"$MM" run -n floodtwin-restored floodtwin doctor --output reports/restored-doctor.json
