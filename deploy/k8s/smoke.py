"""Public HTTPS smoke check; no secrets printed or passed in arguments."""
import json
import urllib.error
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[2]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(path, body=None, headers=None):
    values = dict(headers or {})
    values["User-Agent"] = "Auckland-FlowLab-Deployment-Check/1.0"
    if body is not None:
        values["Content-Type"] = "application/json"
    req = urllib.request.Request("https://daryajan.com"+path,
                                 data=None if body is None else json.dumps(body).encode(), headers=values)
    try:
        with opener.open(req, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


checks = {}
checks["public_health"] = request("/healthz")[0] == 200
checks["frontend"] = request("/")[0] == 200
checks["leaflet"] = request("/vendor/leaflet.js")[0] == 200
checks["private_env_blocked"] = request("/.env")[0] == 404
status, raw = request("/api/bootstrap")
bootstrap = json.loads(raw)
checks["public_bootstrap"] = status == 200 and bootstrap["local"] is False
headers = {"Origin":"https://daryajan.com", "X-Floodtwin-Token": bootstrap["csrf"]}
status, raw = request("/api/search", {"address":"61 Pemberton Avenue, Bayview, Auckland"}, headers)
candidate = json.loads(raw)
checks["verified_address_review"] = status == 200 and candidate["site"]["address_id"] == 1030654 and not candidate["confirmed"]
checks["unconfirmed_exports_blocked"] = request(f"/api/jobs/{candidate['id']}/files/parcel.geojson")[0] == 404
headers["Origin"] = "https://evil.example"
checks["foreign_origin_blocked"] = request("/api/search", {"address":"bad"}, headers)[0] == 403
status, raw = request("/api/lab")
lab = json.loads(raw)
checks["real_synthetic_lab"] = status == 200 and lab["synthetic"] and lab["real_solver"]
(root / "reports/k8s-public-smoke.json").write_text(json.dumps(checks, indent=2))
print(json.dumps(checks, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
