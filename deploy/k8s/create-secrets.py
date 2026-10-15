"""Run with Linux Python 3.11/3.12; save credentials privately, never print them."""
import argparse
import json
import os
from pathlib import Path


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--email", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
folder = root / "reports/k8s-secrets"
folder.mkdir(parents=True, exist_ok=True, mode=0o700)
os.umask(0o077)
values = {}
for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
    if "=" in line and not line.startswith("#"):
        key, value = line.split("=", 1)
        if key.strip() in {"LINZ_API_KEY", "OPENTOPOGRAPHY_API_KEY", "DATAHUB_CUSTOMER_ID", "DATAHUB_API_KEY"}:
            values[key.strip()] = value.strip().strip("\"'")
if not values.get("LINZ_API_KEY"):
    raise RuntimeError("LINZ_API_KEY is required")
(folder / "provider.env").write_text("".join(f"{key}={value}\n" for key, value in values.items()))
(folder / "caddy.env").write_text(f"ACME_EMAIL={args.email}\n")
print("Private provider/Caddy settings saved under reports/k8s-secrets; values not printed.")
