#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"$HOME/.local/bin/micromamba" create -y -r "$HOME/.local/share/mamba" -f optional-swmm.yml
