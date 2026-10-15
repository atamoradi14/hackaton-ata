"""Verify the public terrain-and-evidence app without starting model work."""
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

base = "https://daryajan.com"
job = "72c8fe1ec25341cc992773793393c7a9"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
checks = {}


def call(path, body=None, origin=base, expected=200, binary=False):
    headers = {"User-Agent": "Auckland-FlowLab-Deployment-Check/1.0", "Accept-Encoding": "gzip"}
    if body is not None:
        headers.update({"Content-Type": "application/json", "X-Floodtwin-Token": token, "Origin": origin})
    request = urllib.request.Request(base + path, headers=headers, data=json.dumps(body).encode() if body else None)
    start = time.monotonic()
    try:
        response = opener.open(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.code == expected, (path, response.code)
        data = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
    key = path + (" [foreign origin]" if origin != base else "")
    checks[key] = {"status": expected, "seconds": round(time.monotonic() - start, 3)}
    return data if binary else json.loads(data)


assert call("/healthz")["status"] == "ok"
boot = call("/api/bootstrap")
assert boot["name"] == "Auckland FlowLab" and not boot["local"] and "solver" not in boot
token = boot["csrf"]
page = call("/", binary=True)
assert all(item not in page for item in (b"hydraulic.js", b"workspace.js", b"scene.html"))
for path in ("/hydraulic.js", "/workspace.js", "/scene.html", "/api/lab"):
    call(path, expected=404)
for path in ("/terrain3d.html", "/terrain3d.bundle.js", "/hybrid.html", "/hybrid.bundle.js"):
    call(path, binary=True)
call("/api/jobs/" + job + "/sources")
call("/api/jobs/" + "0" * 32, expected=404)
call("/api/address-suggestions", {"address": "2A Toroa"})
call("/api/address-suggestions", {"address": "2A Toroa"}, origin="https://foreign.invalid", expected=403)
record = {"site": base, "checks": checks, "mode": "terrain_and_evidence_only"}
Path("reports").mkdir(exist_ok=True)
Path("reports/terrain-evidence-production-validation.json").write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))
