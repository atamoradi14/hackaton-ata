"""Export real Conda URLs and only PyPI-managed packages (no build-machine paths)."""
import json
from pathlib import Path
import subprocess
import sys
from collections import Counter

mm = Path.home() / ".local/bin/micromamba"
# Mixing pip replacement and Conda installs can leave duplicate prefix records.
# Refuse a lock rather than silently selecting an unused package version.
records = [json.loads(p.read_text()) for p in (Path(sys.prefix) / "conda-meta").glob("*.json")]
duplicates = [name for name,count in Counter(p["name"] for p in records).items() if count > 1]
if duplicates:
    raise RuntimeError(f"Duplicate Conda prefix records must be repaired before locking: {duplicates}")
packages = json.loads(subprocess.check_output([str(mm), "list", "-p", sys.prefix, "--json"], text=True))["packages"]
Path("locks").mkdir(exist_ok=True)
conda = [p["url"] + ("#" + p["md5"] if p.get("md5") else "") for p in packages if p["channel"] != "pypi" and p.get("url")]
pip = [p["name"] + "==" + p["version"] for p in packages if p["channel"] == "pypi" and p["name"] != "floodtwin"]
Path("locks/conda-linux-64.lock").write_text("# platform: linux-64\n@EXPLICIT\n" + "\n".join(sorted(conda)) + "\n")
Path("locks/pip-linux-64.lock").write_text("\n".join(sorted(pip)) + "\n")
print(f"Locked {len(conda)} Conda builds and {len(pip)} PyPI versions")
