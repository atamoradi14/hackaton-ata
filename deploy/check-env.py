"""Check deployment configuration without displaying credential values."""
import argparse
import re
from pathlib import Path


def check(path, postgis=False):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    defaults = {"DOMAIN": "daryajan.com"}
    missing = []
    for key in ["DOMAIN", "ACME_EMAIL", "LINZ_API_KEY"]:
        value = values.get(key, defaults.get(key, ""))
        valid = bool(value)
        if key == "DOMAIN":
            valid = bool(re.fullmatch(r"[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", value))
        elif key == "ACME_EMAIL":
            valid = bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))
        print(f"{key}: {'configured' if valid else 'MISSING or invalid'}")
        if not valid:
            missing.append(key)
    for key in ["OPENTOPOGRAPHY_API_KEY", "POSTGIS_PASSWORD"]:
        print(f"{key}: {'configured' if values.get(key) else 'optional, unset'}")
    if postgis and not values.get("POSTGIS_PASSWORD"):
        missing.append("POSTGIS_PASSWORD")
    for key in ["MAX_ACTIVE_JOBS", "OMP_NUM_THREADS"]:
        value = values.get(key, "1")
        if not value.isdigit() or int(value) < 1:
            print(f"{key}: invalid; use a positive integer")
            missing.append(key)
    return not missing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--postgis", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if check(args.env_file, args.postgis) else 1)
