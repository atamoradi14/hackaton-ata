#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/.local/bin"
if ! test -x "$HOME/.local/bin/micromamba"; then
  curl --fail -Ls https://micro.mamba.pm/api/micromamba/linux-64/2.9.0 | tar -xj -C "$HOME/.local" bin/micromamba
fi
export MAMBA_ROOT_PREFIX="$HOME/.local/share/mamba"
"$HOME/.local/bin/micromamba" create -y -f environment.yml
"$HOME/.local/bin/micromamba" run -n floodtwin python -m pip install -e . --no-deps
install -m 755 scripts/sfincs "$HOME/.local/share/mamba/envs/floodtwin/bin/sfincs"
docker pull deltares/sfincs-cpu@sha256:4301bffc74f3cb3f334be5d21aa75dfe5742a16c9838942cdfc2f870859fb404
mkdir -p locks reports configs
"$HOME/.local/bin/micromamba" run -n floodtwin python scripts/lock-env.py
test -f configs/local_site.yaml || cp config.example.yaml configs/local_site.yaml
echo 'Run scripts/validate.ps1 from Windows or bash scripts/validate-wsl.sh.'
