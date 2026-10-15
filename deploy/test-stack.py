"""Disposable offline Caddy/Compose integration test. No real provider keys."""
import json
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "reports/deployment-test"
CADDY = "caddy:2-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f"


def command(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True, **kwargs).stdout


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    env = FOLDER / "test.env"
    env.write_text("DOMAIN=daryajan.com\nPUBLIC_ORIGIN=https://localhost:18443\nACME_EMAIL=offline@example.invalid\nLINZ_API_KEY=offline-fixture-unused\n")
    config = FOLDER / "Caddyfile"
    config.write_text((ROOT / "deploy/Caddyfile").read_text().replace("    email {$ACME_EMAIL}", "    email {$ACME_EMAIL}\n    auto_https disable_redirects").replace("{$DOMAIN} {", "{$DOMAIN} {\n    tls internal"))
    override = FOLDER / "override.yaml"
    override.write_text('services:\n  caddy:\n    environment:\n      DOMAIN: localhost\n    ports: !override ["127.0.0.1:18443:443"]\n    volumes: !override\n      - ./reports/deployment-test/Caddyfile:/etc/caddy/Caddyfile:ro\n      - caddy_data:/data\n      - caddy_config:/config\n')
    compose = ["docker", "compose", "--project-name", "auckland-flowlab-integration", "--env-file", str(env), "-f", "compose.production.yaml", "-f", str(override)]
    checks = {}
    try:
        command([*compose, "config", "--quiet"])
        command([*compose, "run", "--rm", "--no-deps", "-v", f"{env}:/tmp/deploy.env:ro", "--entrypoint", "/usr/local/bin/_entrypoint.sh", "app", "/opt/conda/bin/python", "/work/deploy/check-env.py", "--env-file", "/tmp/deploy.env"])
        checks["env_checker_in_container"] = True
        command([*compose, "run", "--rm", "--no-deps", "caddy", "caddy", "validate", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"])
        checks["caddy_config_valid"] = True
        command([*compose, "up", "-d", "--wait", "--wait-timeout", "180", "app", "caddy"])
        command([*compose, "exec", "-T", "app", "/opt/conda/bin/floodtwin", "doctor"])
        checks["locked_geospatial_runtime"] = True
        context = ssl._create_unverified_context()  # Disposable internal CA only.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
        def request(path, body=None, headers=None):
            values = dict(headers or {})
            if body is not None:
                values["Content-Type"] = "application/json"
            req = urllib.request.Request("https://localhost:18443"+path, data=None if body is None else json.dumps(body).encode(), headers=values)
            try:
                with opener.open(req, timeout=5) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as error:
                return error.code, error.read()
        for _ in range(30):
            try:
                if request("/healthz")[0] == 200:
                    break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        checks["public_health"] = request("/healthz")[0] == 200
        checks["frontend"] = request("/")[0] == 200
        checks["leaflet_packaged"] = request("/vendor/leaflet.js")[0] == 200
        checks["private_env_blocked"] = request("/.env")[0] == 404
        status, raw = request("/api/bootstrap")
        boot = json.loads(raw)
        checks["public_mode"] = status == 200 and boot["local"] is False
        headers = {"X-Floodtwin-Token": boot["csrf"], "Origin": "https://localhost:18443"}
        # Invalid address reaches input validation without accessing any provider.
        checks["https_origin_accepted"] = request("/api/search", body={"address":"bad"}, headers=headers)[0] == 400
        headers["Origin"] = "https://evil.example"
        checks["foreign_origin_blocked"] = request("/api/search", body={"address":"bad"}, headers=headers)[0] == 403
        checks["unconfirmed_export_blocked"] = request("/api/jobs/"+"a"*32+"/files/parcel.geojson")[0] == 404
        identifier = command([*compose, "ps", "-q", "app"]).strip()
        ports = json.loads(command(["docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", identifier]))
        checks["backend_not_published"] = not any(ports.values())
        command([*compose, "exec", "-T", "app", "/opt/conda/bin/python", "-c", "from pathlib import Path; Path('/work/reports/persistence-check').write_text('offline test')"])
        command([*compose, "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180", "app"])
        command([*compose, "exec", "-T", "app", "/opt/conda/bin/python", "-c", "from pathlib import Path; assert Path('/work/reports/persistence-check').read_text()=='offline test'"])
        checks["data_survives_recreate"] = True
        (FOLDER / "result.json").write_text(json.dumps(checks, indent=2))
        print(json.dumps(checks, indent=2))
        if not all(checks.values()):
            raise RuntimeError("Deployment integration checks failed")
    finally:
        # Keep volumes for inspection. Never delete persistent data automatically.
        command([*compose, "down"])
        env.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
