"""Isolated workspaces: geocoding is read-only preparation, not site analysis."""
import copy
import json
import os
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text()) if path.exists() else fallback
    except (OSError, json.JSONDecodeError):
        return fallback


def canonical(address):
    parts = [" ".join(p.split()).casefold() for p in address.split(",")]
    return ",".join(parts[:3])


STEPS = [
    ("gis", "Council GIS", "Mapped flow paths, flood areas and drainage assets", ["fetch-discovery"], "gis-discovery-manifest.json", []),
    ("buildings", "Building outlines", "Official footprints; no assumed entry heights", "fetch-buildings.py", "buildings-manifest.json", ["gis"]),
    ("coverage", "Survey coverage", "Intersect the actual 2024 capture areas", ["discover-elevation"], "elevation-discovery.json", []),
    ("terrain", "Ground & surface", "Aligned 1 m DEM / DSM with verified datum", ["prepare-terrain-discovery"], "terrain-qc.json", ["gis", "coverage"]),
    ("lidar", "LiDAR crop", "Bounded native point cloud and classification QC", ["fetch-pointcloud"], "pointcloud-manifest.json", ["terrain"]),
    ("aerial", "Aerial imagery", "Recorded LINZ orthophoto crop", ["prepare-aerial"], "scene-aerial.json", ["lidar"]),
    ("profiles", "Terrain checks", "Ground consistency and two cross-sections", "site-qc.py", "ground-dem-qc.json", ["lidar", "terrain"]),
    ("screening", "Connectivity screen", "Terrain-derived only; no hydraulic water motion", ["screen-domain"], "domain-screening.json", ["terrain"]),
    ("preview", "Evidence report", "Terrain preview and source provenance", "terrain-3d.py", "terrain-3d.png", ["profiles", "screening", "buildings"]),
]


class BusyError(RuntimeError):
    """No processing slot is available; approval has not been consumed."""


class Workspaces:
    def __init__(self, root, execute=None):
        self.root = Path(root).resolve()
        self.folder = self.root / "data/web-sites"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.candidates = {}
        self.jobs = {}
        self.execute = execute or self.command
        capacity = int(os.environ.get("FLOODTWIN_MAX_ACTIVE_JOBS", "1"))
        if capacity < 1:
            raise ValueError("FLOODTWIN_MAX_ACTIVE_JOBS must be positive")
        self.slots = threading.BoundedSemaphore(capacity)
        for path in self.folder.glob("*/runs/property/*/status.json"):
            record=read_json(path,{})
            if record.get("status")=="running":
                record.update(status="interrupted",message="Server restarted; this exploratory run must be reviewed and started again.")
                path.write_text(json.dumps(record))

    def command(self, workspace, command, timeout=1800):
        args = ([sys.executable, "-m", "floodtwin.cli", *command] if isinstance(command, list)
                else [sys.executable, str(self.root / "scripts" / command)])
        # No shell interpolation of addresses; credentials inherit privately.
        environment = os.environ.copy()
        source = str(self.root / "src")
        environment["PYTHONPATH"] = source + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
        result = subprocess.run(args, cwd=workspace, env=environment, capture_output=True,
                                text=True, timeout=timeout)
        output = result.stdout + result.stderr
        for name in [key for key in os.environ if key.endswith("_KEY")]:
            key = os.environ.get(name)
            if key:
                output = output.replace(key, "REDACTED")
        logs = workspace / "logs"
        logs.mkdir(exist_ok=True)
        (logs / (str(command[0] if isinstance(command, list) else command) + ".log")).write_text(output)
        if result.returncode:
            if 'ReadTimeout' in output or 'ConnectTimeout' in output:
                raise TimeoutError('The source server timed out. Retry preparation to continue from recorded data.')
            # Fixed public message: provider exception URLs never cross into UI.
            raise RuntimeError("Provider or processing check failed. See private job logs for details.")

    def directory(self, identifier):
        if not isinstance(identifier, str) or len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
            raise ValueError("Invalid workspace identifier")
        return self.folder / identifier

    def suggestions(self, address):
        """Suggestions are discovery only; they never create a workspace or assign a parcel."""
        from floodtwin.providers.address import suggest
        return suggest(address)

    def search(self, address):
        if not isinstance(address, str) or not 5 <= len(address) <= 240 or len(address.split(",")) < 3:
            raise ValueError("Enter street number and full street, suburb, city")
        identifier = uuid.uuid4().hex
        directory = self.directory(identifier)
        site_folder = directory / "data/processed/site"
        site_folder.mkdir(parents=True)
        known = self.root / "data/processed/site"
        known_manifest = read_json(known / "site_manifest.json", {})
        if canonical(address) == canonical(known_manifest.get("address", "")):
            for name in ["address.geojson", "parcel.geojson", "site_manifest.json"]:
                shutil.copy2(known / name, site_folder / name)
        else:
            self.execute(directory, ["resolve-address", "--address", address], timeout=180)
        manifest = read_json(site_folder / "site_manifest.json")
        if not manifest or not manifest.get("official_exact_match"):
            raise RuntimeError("An unambiguous official address and parcel match is required")
        # The cached site's previous confirmation does not authorize a new job.
        manifest["user_visual_confirmation"] = False
        (site_folder / "site_manifest.json").write_text(json.dumps(manifest, indent=2))
        candidate = dict(id=identifier, requested_address=address, site=manifest, created_at=stamp(), confirmed=False,
                         parcel=read_json(site_folder / "parcel.geojson"), point=read_json(site_folder / "address.geojson"))
        with self.lock:
            self.candidates[identifier] = candidate
        return copy.deepcopy(candidate)

    def confirm(self, identifier, address, confirmed, launch=True):
        with self.lock:
            candidate = self.candidates.get(identifier)
            if not candidate:
                raise ValueError("Search again before confirming this address")
            if confirmed is not True or canonical(address) != canonical(candidate["requested_address"]):
                raise ValueError("Explicit confirmation must match the reviewed address")
            if candidate["confirmed"]:
                return copy.deepcopy(self.jobs[identifier])
            if launch and not self.slots.acquire(blocking=False):
                raise BusyError("Processing capacity reached")
            site = copy.deepcopy(candidate["site"])
            site.update(user_visual_confirmation=True, user_confirmation_timestamp=stamp(), confirmation_request_id=identifier)
            directory = self.directory(identifier)
            job = dict(id=identifier, site=site, status="preparing", created_at=stamp(),
                       steps=[dict(id=s[0], name=s[1], description=s[2], status="queued") for s in STEPS],
                       events=[dict(time=stamp(), message="Property confirmed. Isolated preparation started.")],
                       blockers=[], hydraulic_results_available=False)
            try:
                (directory / "data/processed/site/site_manifest.json").write_text(json.dumps(site, indent=2))
                self.save(job)
                self.jobs[identifier] = job
                candidate["confirmed"] = True
                if launch:
                    threading.Thread(target=self.prepare_managed, args=(identifier,), daemon=True).start()
            except Exception:
                self.jobs.pop(identifier, None)
                candidate["confirmed"] = False
                if launch:
                    self.slots.release()
                raise
            return copy.deepcopy(job)

    def retry_preparation(self, identifier):
        with self.lock:
            job=self.get(identifier)
            if not job['site'].get('user_visual_confirmation'):
                raise ValueError('Confirm the property first')
            if job['status']=='preparing':
                return self.public(job)
            if not self.slots.acquire(blocking=False):
                raise BusyError('Processing capacity reached')
            try:
                job['status']='preparing'
                previous={step['id']:step for step in job['steps']}
                job['steps']=[dict(previous.get(s[0],dict(id=s[0],name=s[1],description=s[2])),status='queued') for s in STEPS]
                job['events'].append(dict(time=stamp(),message='Retry requested; recorded artifacts will be reused.'))
                self.save(job)
                self.jobs[identifier]=job
                threading.Thread(target=self.prepare_managed,args=(identifier,True),daemon=True).start()
                return self.public(job)
            except Exception:
                self.slots.release()
                raise

    def prepare_managed(self, identifier, reuse_existing=False):
        try:
            self.prepare(identifier,reuse_existing=reuse_existing)
        finally:
            self.slots.release()

    def save(self, job):
        directory = self.directory(job["id"])
        temporary = directory / "job.tmp"
        temporary.write_text(json.dumps(job, indent=2))
        temporary.replace(directory / "job.json")

    def get(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            if job is None:
                job = read_json(self.directory(identifier) / "job.json")
                if job and job["status"] == "preparing":
                    job["status"] = "interrupted"
                    for step in job["steps"]:
                        if step["status"] in {"queued", "running"}:
                            step.update(status="blocked", detail="Preparation interrupted by a server restart.")
                    job["events"].append(dict(time=stamp(), message="Server restarted before preparation finished. Retry blocked data to resume this confirmed workspace."))
                    self.save(job)
            if not job:
                raise ValueError("Confirmed workspace not found")
            return copy.deepcopy(job)

    def update(self, identifier, step, status, detail):
        with self.lock:
            job = self.jobs[identifier]
            record = next(s for s in job["steps"] if s["id"] == step)
            record.update(status=status, detail=detail)
            job["events"].append(dict(time=stamp(), message=f"{record['name']}: {detail}"))
            self.save(job)

    def prepare(self, identifier, reuse_existing=False):
        directory = self.directory(identifier)
        local = directory / "data/processed/site"
        try:
            # Reuse prior verified data only for the exact same address AND parcel.
            original = self.root / "data/processed/site"
            known = read_json(original / "site_manifest.json", {})
            site = self.get(identifier)["site"]
            cached = (known.get("address_id") == site["address_id"] and str(known.get("parcel_id")) == str(site["parcel_id"]))
            if cached:
                for file in original.iterdir():
                    if file.is_file() and file.name not in {"address.geojson", "parcel.geojson", "site_manifest.json"}:
                        shutil.copy2(file, local / file.name)
            (directory / "docs").mkdir(exist_ok=True)
            shutil.copy2(self.root / "docs/verified-surveys.json", directory / "docs/verified-surveys.json")
            statuses = {}
            for step, name, description, command, artifact, dependencies in STEPS:
                if any(statuses.get(dep) not in {"done", "cached", "partial"} for dep in dependencies):
                    statuses[step] = "blocked"
                    self.update(identifier, step, "blocked", "Waiting for a required data preparation step.")
                    continue
                self.update(identifier, step, "running", "Checking source coverage and recorded artifacts…")
                try:
                    if (cached or reuse_existing) and (local / artifact).exists():
                        status, detail = "cached", "Reused recorded data for this exact address and parcel."
                    else:
                        self.execute(directory, command)
                        if not (local / artifact).exists():
                            raise RuntimeError("Expected data artifact not produced")
                        status, detail = "done", "Prepared from actual provider data."
                    if step == "gis":
                        report = read_json(local / artifact)
                        if any(layer.get("status") == "blocked" for layer in report["layers"].values()):
                            status, detail = "partial", "Some Council sources are unavailable; coverage is incomplete."
                    if step == "preview" and status == "done":
                        self.execute(directory, "site-overview.py")
                    statuses[step] = status
                    self.update(identifier, step, status, detail)
                except (TimeoutError,subprocess.TimeoutExpired):
                    statuses[step] = 'blocked'
                    self.update(identifier,step,'blocked','Source request timed out. Retry to continue from recorded data.')
                except Exception:
                    statuses[step] = "blocked"
                    self.update(identifier, step, "blocked", "Source access, verified coverage or processing needs attention. See private logs.")
            with self.lock:
                job = self.jobs[identifier]
                job["status"] = "needs_inputs"
                job["blockers"] = [
                    dict(id="rainfall", title="Site-specific rainfall", detail="Import a HIRDS export and review its storm duration and temporal pattern."),
                    dict(id="domain", title="Connected domain & outlets", detail="Review upstream coverage, downstream outlets and boundary water levels."),
                    dict(id="parameters", title="Surface & structure assumptions", detail="Review roughness, losses, buildings, finite barrier crests and drainage scenarios."),
                ]
                job["events"].append(dict(time=stamp(), message="Preparation finished. Hydraulic simulation awaits reviewed scientific inputs."))
                self.save(job)
        except Exception:
            with self.lock:
                job = self.jobs[identifier]
                job["status"] = "failed"
                job["events"].append(dict(time=stamp(), message="Preparation interrupted; private source files are preserved."))
                self.save(job)

    def start_hydraulics(self, identifier, specification):
        from ..hydraulics.site import parameters
        specification = parameters(specification)
        job = self.get(identifier)
        if job["status"] == "preparing":
            raise ValueError("Wait for evidence preparation to finish")
        folder = self.directory(identifier)/"data/processed/site"
        if not all((folder/name).exists() for name in ["dem_discovery.tif", "terrain-qc.json", "buildings.gpkg"]):
            raise ValueError("Verified ground and building data required")
        if not self.slots.acquire(blocking=False):
            raise BusyError("Processing capacity reached")
        run_id = uuid.uuid4().hex
        root = self.directory(identifier)/"runs/property"/run_id
        try:
            root.mkdir(parents=True)
            name = f"{specification['rain_mm_h']:g} mm/h · {len(specification['walls'])} hypothetical walls"
            record = dict(id=run_id, name=name, status="running", message="Actual terrain model queued for SFINCS", created_at=stamp())
            (root/"status.json").write_text(json.dumps(record))
            (root/"request.json").write_text(json.dumps(specification))
            def execute():
                try:
                    # Separate process bounds modelling memory lifetime and keeps HTTP responsive.
                    result = subprocess.run([sys.executable,"-m","floodtwin.hydraulics.site",str(folder),str(root)],
                                            cwd=self.root,capture_output=True,text=True,timeout=1500)
                    (root/"worker.log").write_text(result.stdout+result.stderr)
                    if result.returncode:
                        if "Wall crosses or is too close" in result.stderr:
                            raise ValueError("Wall crosses or is too close to a building footprint; draw on exposed ground or refine the obstacle geometry.")
                        raise RuntimeError("Hydraulic worker failed")
                    record.update(status="done", message="Actual exploratory solver outputs ready; scientific limits remain")
                except ValueError as error:
                    record.update(status="failed",message=str(error))
                except Exception:
                    record.update(status="failed",message="Solver or quality check failed. Inspect private model logs; no substitute water generated.")
                finally:
                    (root/"status.json").write_text(json.dumps(record))
                    self.slots.release()
            threading.Thread(target=execute,daemon=True).start()
            return copy.deepcopy(record)
        except Exception:
            self.slots.release()
            raise

    def hydraulics(self, identifier, run_id=None):
        self.get(identifier)
        directory = self.directory(identifier)/"runs/property"
        if not run_id:
            return dict(runs=[read_json(path) for path in sorted(directory.glob("*/status.json"))])
        self.directory(run_id)  # Validate identifier grammar, not a filesystem path.
        root = directory/run_id
        record = read_json(root/"status.json")
        if not record:
            raise ValueError("Hydraulic run not found")
        if record["status"] == "done":
            from ..hydraulics.results import presentation
            return dict(presentation(root, self.get(identifier)['site']),id=run_id,name=record["name"])
        if record["status"]=="running" and (root/"solver.log").exists():
            import re
            with (root/"solver.log").open("rb") as source:
                source.seek(max(0,(root/"solver.log").stat().st_size-8192))
                tail=source.read().decode(errors="replace")
            progress=re.findall(r"(\d+)% complete",tail)
            if progress:
                record=dict(record,message=f"Actual SFINCS solving: {progress[-1]}% complete")
        return record

    def compare(self, identifier, baseline, modified):
        self.directory(baseline); self.directory(modified)
        job = self.get(identifier)
        directory = self.directory(identifier)/'runs/property'
        for run_id in [baseline, modified]:
            if read_json(directory/run_id/'status.json', {}).get('status') != 'done':
                raise ValueError('Two completed runs in this workspace are required')
        from ..hydraulics.results import comparison
        return comparison(directory/baseline, directory/modified, job['site'])

    def save_walls(self, identifier, walls):
        from ..hydraulics.site import parameters
        self.get(identifier)
        # Same contract and bounds as actual solver requests.
        checked = parameters(dict(reviewed=True,rain_mm_h=0,duration_minutes=30,
                                  manning=.03,infiltration_mm_h=0,walls=walls))['walls']
        directory = self.directory(identifier)
        with self.lock:
            temp = directory/'walls.tmp'
            temp.write_text(json.dumps(dict(walls=checked, updated_at=stamp())))
            temp.replace(directory/'walls.json')
        return dict(walls=checked)

    def public(self, job):
        directory = self.directory(job["id"]) / "data/processed/site"
        result = copy.deepcopy(job)
        result["terrain"] = read_json(directory / "terrain-qc.json")
        result["pointcloud"] = read_json(directory / "pointcloud-manifest.json")
        result["gis"] = read_json(directory / "gis-discovery-manifest.json")
        result["ground"] = read_json(directory / "ground-dem-qc.json")
        result["buildings"] = read_json(directory / "buildings-manifest.json")
        runs=[read_json(p,{}) or {} for p in (self.directory(job['id'])/'runs/property').glob('*/status.json')]
        result['hydraulic_results_available']=any(r.get('status')=='done' for r in runs)
        result['hydraulic_status']='running' if any(r.get('status')=='running' for r in runs) else 'results_ready' if result['hydraulic_results_available'] else 'requires_review'
        result["available_files"] = [p.name for p in directory.iterdir() if p.is_file()]
        return result
