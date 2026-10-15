#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec "$HOME/.local/bin/micromamba" run -r "$HOME/.local/share/mamba" -n floodtwin python - <<'PY'
import os
import signal
from pathlib import Path

root = Path.cwd().resolve()
root_aliases = {str(root), str(root).removeprefix('/mnt/c')}
stopped = 0
for process in Path('/proc').glob('[0-9]*'):
    try:
        args = (process / 'cmdline').read_bytes().split(b'\0')
        ours = any(Path(arg.decode()).name == 'floodtwin' and args[i+1:i+4] == [b'serve', b'--port', b'8765']
                   for i, arg in enumerate(args) if arg)
        cwd = os.readlink(process / 'cwd').removesuffix(' (deleted)')
        if ours and cwd in root_aliases and process.stat().st_uid == os.getuid():
            os.kill(int(process.name), signal.SIGTERM)
            stopped += 1
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
print(f'Stopped {stopped} Auckland FlowLab server(s) belonging to this workspace.')
PY
