#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"$HOME/.local/bin/micromamba" run -r "$HOME/.local/share/mamba" -n floodtwin-swmm python scripts/validate-swmm.py
