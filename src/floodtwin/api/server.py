"""Explicit-origin app behind a private proxy, or loopback local development."""
import hmac
import json
import mimetypes
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

from .workspace import Workspaces, read_json, BusyError


EXPORTS = {"overview.html", "terrain-3d.png", "terrain-preview.png", "ground-dem-qc.png",
           "domain-screening.png", "terrain-cross-sections.csv", "dem_discovery.tif", "dsm_discovery.tif",
           "pointcloud_crop.laz", "terrain-qc.json", "pointcloud-manifest.json", "gis-discovery-manifest.json",
           "ground-dem-qc.json", "buildings-manifest.json", "site_manifest.json", "parcel.geojson",
           "domain-screening.json", "gis-discovery.png", "map-terrain.png", "address.geojson"}
EXPORTS.update({"scene-aerial.jpg", "scene-aerial.json", 'map-aerial.png','map-aerial.json'})


def make_server(root, port=8765, workspaces=None, bind="127.0.0.1", public_origin=None):
    root = Path(root).resolve()
    manager = workspaces or Workspaces(root)
    token = secrets.token_urlsafe(32)
    asset_cache = {}
    allowed_hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
    allowed_origins = {f"http://{host}" for host in allowed_hosts}
    if public_origin:
        origin = urlparse(public_origin)
        if origin.scheme not in {"http", "https"} or not origin.hostname or origin.username or origin.password or origin.path not in {"", "/"} or origin.query or origin.fragment:
            raise ValueError("FLOODTWIN_PUBLIC_ORIGIN must be an explicit HTTP(S) origin without credentials or path")
        allowed_hosts.add(origin.netloc)
        allowed_origins.add(f"{origin.scheme}://{origin.netloc}")

    class Handler(BaseHTTPRequestHandler):
        def json(self, value, status=200):
            import os
            body = json.dumps(value, allow_nan=False)
            for name in [key for key in os.environ if key.endswith("_KEY")]:
                if os.environ.get(name):
                    body = body.replace(os.environ[name], "REDACTED")
            self.send(body.encode(), "application/json", status)

        def send(self, body, kind, status=200):
            compressed = len(body)>32768 and 'gzip' in self.headers.get('Accept-Encoding','')
            if compressed:
                import gzip
                body=gzip.compress(body,compresslevel=1)
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header('Vary', 'Accept-Encoding')
            if compressed:
                self.send_header('Content-Encoding','gzip')
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tile.googleapis.com https://*.basemaps.cartocdn.com https://tile.openstreetmap.org; connect-src 'self' blob: https://tile.googleapis.com; worker-src 'self' blob:; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def host_valid(self):
            return self.headers.get("Host") in allowed_hosts

        def do_POST(self):
            origin = self.headers.get("Origin")
            valid_origin = origin is None or origin in allowed_origins
            if not self.host_valid() or not valid_origin or not hmac.compare_digest(self.headers.get("X-Floodtwin-Token", ""), token):
                self.json({"error": "Session verification failed. Reload the app."}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("A small JSON request is required")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("A JSON object is required")
                if self.path == "/api/search":
                    self.json(manager.search(data.get("address")))
                elif self.path == "/api/confirm":
                    job = manager.confirm(data.get("id"), data.get("address", ""), data.get("confirmed"))
                    self.json(manager.public(job), 202)
                elif self.path.startswith('/api/jobs/') and self.path.endswith('/comparison'):
                    self.json(manager.compare(self.path.split('/')[3], data.get('baseline'), data.get('modified')))
                elif self.path.startswith('/api/jobs/') and self.path.endswith('/source-check'):
                    identifier = self.path.split('/')[3]
                    manager.get(identifier)
                    from .freshness import status
                    self.json(status(manager.directory(identifier)/'data/processed/site', check=True))
                elif self.path.startswith('/api/jobs/') and self.path.endswith('/walls'):
                    self.json(manager.save_walls(self.path.split('/')[3], data.get('walls')))
                elif self.path.startswith('/api/jobs/') and self.path.endswith('/spatial'):
                    import math
                    import rasterio
                    from pyproj import Transformer
                    identifier = self.path.split('/')[3]
                    job = manager.get(identifier)
                    points = data.get('points')
                    if not isinstance(points,list) or not 1<=len(points)<=120:
                        raise ValueError('Bounded coordinate list required')
                    if any(not isinstance(p,list) or len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) for p in points):
                        raise ValueError('Finite coordinate pairs required')
                    x,y = job['site']['nztm']
                    to_nztm=Transformer.from_crs(4326,2193,always_xy=True)
                    to_wgs=Transformer.from_crs(2193,4326,always_xy=True)
                    samples=[]
                    with rasterio.open(manager.directory(identifier)/'data/processed/site/dem_discovery.tif') as dem:
                        if dem.crs.to_epsg()!=2193 or dem.tags().get('vertical_datum')!='NZVD2016':
                            raise ValueError('Verified terrain CRS/datum required')
                        for a,b in points:
                            east,north=to_nztm.transform(b,a) if data.get('mode')=='latlon' else (x+a,y+b)
                            if not (dem.bounds.left<=east<dem.bounds.right and dem.bounds.bottom<north<=dem.bounds.top):
                                raise ValueError('Point outside available terrain')
                            z=next(dem.sample([(east,north)],masked=True))[0]
                            if not math.isfinite(float(z)) or getattr(z,'mask',False):
                                raise ValueError('No ground sample available')
                            lon,lat=to_wgs.transform(east,north)
                            samples.append(dict(local=[east-x,north-y],ground_m=float(z),latlon=[lat,lon]))
                    self.json(dict(points=samples,datum='NZVD2016',source='nearest measured 1 m DEM sample'))
                elif self.path.startswith("/api/jobs/") and self.path.endswith("/hydraulics"):
                    identifier = self.path.split("/")[3]
                    self.json(manager.start_hydraulics(identifier, data), 202)
                else:
                    self.json({"error": "Route not found"}, 404)
            except ValueError as error:
                self.json({"error": str(error)}, 400)
            except BusyError:
                self.json({"error": "The processing slot is busy with preparation or simulation. Wait for that job to finish, then try again."}, 409)
            except Exception:
                self.json({"error": "The official address/parcel could not be resolved unambiguously. Check the full address and source access."}, 422)

        def do_GET(self):
            if not self.host_valid():
                self.json({"error": "The requested app host is not allowed"}, 403)
                return
            path = unquote(urlparse(self.path).path)
            try:
                if path == "/healthz":
                    self.json({"status": "ok"})
                    return
                if path == "/api/bootstrap":
                    site = read_json(root / "data/processed/site/site_manifest.json", {})
                    self.json(dict(csrf=token, default_address=site.get("address", ""), name="Auckland FlowLab",
                                   local=not bool(public_origin), solver="SFINCS 2.4.0", horizontal_crs="EPSG:2193", vertical_datum="NZVD2016"))
                    return
                if path == '/api/viewer-config':
                    # This key is deliberately public and must be HTTP-referrer/API restricted.
                    # Never expose LINZ credentials or a generic server GOOGLE_MAPS_API_KEY.
                    key = os.environ.get('GOOGLE_MAPS_BROWSER_KEY', '').strip()
                    self.send(json.dumps(dict(google=dict(enabled=bool(key), browser_key=key or None),
                        cesium_version='1.146.0', google_capture_date=None)).encode(), 'application/json')
                    return
                if path == "/api/lab":
                    from .assets import lab
                    if "lab" not in asset_cache:
                        asset_cache["lab"] = lab(root)
                    public = dict(asset_cache["lab"])
                    public.pop("report_directory", None)
                    self.json(public)
                    return
                if path.startswith("/api/jobs/"):
                    parts = path.split("/")
                    identifier = parts[3]
                    job = manager.get(identifier)  # Pending/unconfirmed candidates cannot pass this gate.
                    folder = manager.directory(identifier) / "data/processed/site"
                    if len(parts) == 4:
                        self.json(manager.public(job))
                    elif len(parts) == 5 and parts[4] == 'georeference':
                        from ..terrain.georeference import frame
                        scene = read_json(folder/'scene.json')
                        if not scene:
                            raise ValueError('Prepare the terrain scene first')
                        try:
                            self.json(dict(available=True, **frame(root, job['site'], scene['bounds_nztm'])))
                        except ValueError as error:
                            self.json(dict(available=False, reason=str(error)))
                    elif len(parts) == 5 and parts[4] == 'sources':
                        from .freshness import status
                        self.json(status(folder))
                    elif len(parts) == 5 and parts[4] == "scene":
                        from ..terrain.scene import build
                        cache = folder / "scene.json"
                        with manager.lock:
                            result = read_json(cache) if cache.exists() else build(folder)
                            if not result or result.get("version") != 6:
                                result = build(folder)
                        self.json(dict(result, address=job["site"]["address"]))
                    elif len(parts) == 5 and parts[4] == "points":
                        import laspy
                        import numpy as np
                        cloud = laspy.read(folder / "pointcloud_crop.laz")
                        stride = max(1, (len(cloud.points)+59999)//60000)
                        x,y = job["site"]["nztm"]
                        xyz = np.stack([np.asarray(cloud.x)[::stride]-x, np.asarray(cloud.y)[::stride]-y, np.asarray(cloud.z)[::stride]], axis=1)
                        self.json(dict(synthetic=False, points=np.round(xyz,3).tolist(), sampling_stride=stride,
                                       classification=np.asarray(cloud.classification)[::stride].tolist()))
                    elif len(parts) in {5,6} and parts[4] == "hydraulics":
                        self.json(manager.hydraulics(identifier, parts[5] if len(parts)==6 else None))
                    elif len(parts) == 5 and parts[4] == 'walls':
                        self.json(read_json(manager.directory(identifier)/'walls.json', dict(walls=[])))
                    elif len(parts) == 6 and parts[4] == "layers":
                        from .assets import layer
                        key = (identifier, parts[5])
                        if key not in asset_cache:
                            asset_cache[key] = layer(folder, parts[5])
                        self.json(asset_cache[key])
                    elif len(parts) == 5 and parts[4] == "terrain":
                        from .assets import terrain_overlay
                        self.json(terrain_overlay(folder))
                    elif len(parts) == 5 and parts[4] == 'aerial':
                        from .assets import aerial_overlay
                        with manager.lock:
                            self.json(aerial_overlay(folder))
                    elif len(parts) == 5 and parts[4] == "profiles":
                        from .assets import profiles
                        self.json(profiles(folder))
                    elif len(parts) == 6 and parts[4] == "files" and parts[5] in EXPORTS:
                        file = folder / parts[5]
                        self.send(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
                    else:
                        self.json({"error": "Artifact not available"}, 404)
                    return
                static = {"/": root / "web/index.html", "/app.js": root / "web/app.js", "/style.css": root / "web/style.css"}
                static.update({"/"+name: root/"web"/name for name in ["scene.html", "studio.css", "scene.bundle.js", "hydraulic.js", "workspace.js", "workspace.css", "hybrid.html", "hybrid.css", "hybrid.js", "hybrid-model.js", "hybrid.bundle.js", "google-maps-credit.png"]})
                vendor = root / "web/node_modules/leaflet/dist"
                if path.startswith('/vendor/cesium/'):
                    base = (root/'web/node_modules/cesium/Build/Cesium').resolve()
                    candidate = (base/path.removeprefix('/vendor/cesium/')).resolve()
                    file = candidate if candidate.is_relative_to(base) and candidate.is_file() else None
                elif path in {"/vendor/leaflet.js", "/vendor/leaflet.css"}:
                    file = vendor / path.rsplit("/", 1)[-1]
                elif path.startswith("/vendor/images/") and path.rsplit("/", 1)[-1] in {"marker-icon.png", "marker-icon-2x.png", "marker-shadow.png", "layers.png", "layers-2x.png"}:
                    file = vendor / "images" / path.rsplit("/", 1)[-1]
                else:
                    file = static.get(path)
                if file and file.exists():
                    kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                    self.send(file.read_bytes(), kind + ("; charset=utf-8" if file.suffix in {".html", ".css", ".js"} else ""))
                else:
                    self.json({"error": "Not found"}, 404)
            except (ValueError, FileNotFoundError, KeyError):
                self.json({"error": "This confirmed workspace or artifact is not available yet"}, 404)
            except Exception:
                self.json({"error": "The source artifact needs attention; no substitute data was generated"}, 422)

        def log_message(self, *args):
            pass  # Addresses and session tokens are not HTTP-log content.

    server = ThreadingHTTPServer((bind, port), Handler)
    allowed_hosts.update({f"localhost:{server.server_port}", f"127.0.0.1:{server.server_port}"})
    allowed_origins.update({f"http://localhost:{server.server_port}", f"http://127.0.0.1:{server.server_port}"})
    return server


def serve(port=8765):
    root = Path(__file__).resolve().parents[3]
    if not (root / "web/node_modules/leaflet/dist/leaflet.js").exists():
        raise RuntimeError("Run npm --prefix web ci --ignore-scripts first")
    bind = os.environ.get("FLOODTWIN_BIND", "127.0.0.1")
    origin = os.environ.get("FLOODTWIN_PUBLIC_ORIGIN")
    server = make_server(root, port, bind=bind, public_origin=origin)
    print(f"Auckland FlowLab app: {origin or f'http://localhost:{port}'}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
