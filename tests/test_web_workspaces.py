import json
import threading

import pytest
import requests

from floodtwin.api.workspace import Workspaces
from floodtwin.api.server import make_server

ADDRESS = "1 Synthetic Road, Offline, Auckland"


@pytest.fixture
def manager(tmp_path):
    folder = tmp_path / "data/processed/site"
    folder.mkdir(parents=True)
    manifest = dict(address=ADDRESS, address_id=100, parcel_id="200", official_exact_match=True,
                    user_visual_confirmation=True, nztm=[0, 0], lonlat=[174, -36])
    (folder / "site_manifest.json").write_text(json.dumps(manifest))
    for name in ["address", "parcel"]:
        (folder / (name + ".geojson")).write_text(json.dumps(dict(type="FeatureCollection", features=[])))
    def never_execute(*args, **kwargs):
        raise AssertionError("No preparation or network operation is authorized in a search")
    return Workspaces(tmp_path, execute=never_execute)


def test_search_does_not_authorize_preparation_or_copy_prior_confirmation(manager):
    candidate = manager.search(ADDRESS)
    assert not candidate["confirmed"]
    assert not candidate["site"]["user_visual_confirmation"]
    with pytest.raises(ValueError, match="not found"):
        manager.get(candidate["id"])
    assert not (manager.directory(candidate["id"]) / "job.json").exists()


def test_confirmation_must_match_reviewed_address(manager):
    candidate = manager.search(ADDRESS)
    with pytest.raises(ValueError, match="Explicit confirmation"):
        manager.confirm(candidate["id"], "2 Other Road, Offline, Auckland", True, launch=False)
    with pytest.raises(ValueError, match="Explicit confirmation"):
        manager.confirm(candidate["id"], ADDRESS, False, launch=False)


def test_confirmed_jobs_are_isolated_and_confirmation_is_idempotent(manager):
    first, second = manager.search(ADDRESS), manager.search(ADDRESS)
    one = manager.confirm(first["id"], ADDRESS, True, launch=False)
    two = manager.confirm(second["id"], ADDRESS, True, launch=False)
    assert one["id"] != two["id"]
    assert one["site"]["confirmation_request_id"] == first["id"]
    assert manager.confirm(first["id"], ADDRESS, True, launch=False) == one
    assert manager.directory(one["id"]) != manager.directory(two["id"])
    assert not one["hydraulic_results_available"]


def test_restart_reports_interrupted_work_instead_of_phantom_progress(manager):
    candidate = manager.search(ADDRESS)
    job = manager.confirm(candidate["id"], ADDRESS, True, launch=False)
    restarted = Workspaces(manager.root, execute=manager.execute)
    recovered = restarted.get(job["id"])
    assert recovered["status"] == "interrupted"
    assert all(step["status"] == "blocked" for step in recovered["steps"])
    assert not recovered["hydraulic_results_available"]


def test_new_site_failure_does_not_borrow_another_sites_terrain(manager):
    old = manager.root / "data/processed/site"
    (old / "terrain-qc.json").write_text('{"belongs_to": "old_site"}')
    calls = []
    def execute(directory, command, **kwargs):
        calls.append(command)
        folder = directory / "data/processed/site"
        if isinstance(command, list) and command[0] == "resolve-address":
            manifest = dict(address="2 Synthetic Road, Offline, Auckland", address_id=101, parcel_id="201",
                            official_exact_match=True, user_visual_confirmation=False, nztm=[0,0], lonlat=[174,-36])
            (folder / "site_manifest.json").write_text(json.dumps(manifest))
            for name in ["address", "parcel"]:
                (folder / (name+".geojson")).write_text('{"type":"FeatureCollection","features":[]}')
        elif command == ["fetch-discovery"]:
            (folder / "gis-discovery-manifest.json").write_text('{"layers":{"pipes":{"status":"available_empty"}}}')
        elif command == "fetch-buildings.py":
            (folder / "buildings-manifest.json").write_text('{"count":0}')
        elif command == ["discover-elevation"]:
            (folder / "elevation-discovery.json").write_text('{"collections":[]}')
        elif command == ["prepare-terrain-discovery"]:
            assert not (folder / "terrain-qc.json").exists()
            raise RuntimeError("No registered terrain coverage")
        else:
            raise AssertionError("Dependent work must not run after missing terrain")
    (manager.root / "docs").mkdir()
    (manager.root / "docs/verified-surveys.json").write_text('{}')
    manager.execute = execute
    candidate = manager.search("2 Synthetic Road, Offline, Auckland")
    assert len(calls) == 1  # Only geocoding before confirmation.
    job = manager.confirm(candidate["id"], candidate["requested_address"], True, launch=False)
    manager.prepare(job["id"])
    result = manager.get(job["id"])
    statuses = {step["id"]: step["status"] for step in result["steps"]}
    assert statuses["gis"] == "done"
    assert all(statuses[key] == "blocked" for key in ["terrain","lidar","profiles","screening","preview"])
    assert not (manager.directory(job["id"]) / "data/processed/site/terrain-qc.json").exists()
    assert result["status"] == "needs_inputs"
    assert not result["hydraulic_results_available"]


@pytest.mark.parametrize("identifier", ["../secrets", "a/"*16, "", None])
def test_workspace_paths_are_not_user_paths(manager, identifier):
    with pytest.raises(ValueError):
        manager.directory(identifier)


def test_http_gate_and_private_file_access(manager):
    server = make_server(manager.root, port=0, workspaces=manager)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        csrf = requests.get(url+"/api/bootstrap").json()["csrf"]
        assert requests.post(url+"/api/search", json={"address":ADDRESS}).status_code == 403
        assert requests.get(url+"/.env").status_code == 404
        assert requests.get(url+"/api/bootstrap", headers={"Host":"evil.example"}).status_code == 403
        assert requests.post(url+"/api/search", json={"address":ADDRESS}, headers={"X-Floodtwin-Token":csrf,"Origin":"https://evil.example"}).status_code == 403
        candidate = requests.post(url+"/api/search", json={"address":ADDRESS}, headers={"X-Floodtwin-Token":csrf}).json()
        assert requests.get(url+f"/api/jobs/{candidate['id']}/files/parcel.geojson").status_code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_https_origin_through_proxy(manager):
    server = make_server(manager.root, port=0, workspaces=manager, public_origin="https://daryajan.com")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        headers = {"Host": "daryajan.com", "Origin": "https://daryajan.com"}
        bootstrap = requests.get(url+"/api/bootstrap", headers=headers).json()
        assert bootstrap["local"] is False
        headers["X-Floodtwin-Token"] = bootstrap["csrf"]
        candidate = requests.post(url+"/api/search", json={"address": ADDRESS}, headers=headers)
        assert candidate.status_code == 200
        assert not candidate.json()["confirmed"]
        headers["Origin"] = "https://evil.example"
        assert requests.post(url+"/api/search", json={"address": ADDRESS}, headers=headers).status_code == 403
        assert requests.get(url+"/healthz").status_code == 200
    finally:
        server.shutdown()
        server.server_close()


def test_busy_slot_keeps_confirmation_pending(manager):
    from floodtwin.api.workspace import BusyError
    candidate = manager.search(ADDRESS)
    assert manager.slots.acquire(blocking=False)
    try:
        with pytest.raises(BusyError):
            manager.confirm(candidate["id"], ADDRESS, True)
        assert not manager.candidates[candidate["id"]]["confirmed"]
        assert not (manager.directory(candidate["id"]) / "job.json").exists()
    finally:
        manager.slots.release()


def test_failed_save_releases_processing_slot(manager, monkeypatch):
    candidate = manager.search(ADDRESS)
    def failed(job):
        raise OSError("Synthetic disk failure")
    monkeypatch.setattr(manager, "save", failed)
    with pytest.raises(OSError):
        manager.confirm(candidate["id"], ADDRESS, True)
    assert not manager.candidates[candidate["id"]]["confirmed"]
    assert manager.slots.acquire(blocking=False)
    manager.slots.release()


def test_worker_releases_processing_slot_on_failure(manager, monkeypatch):
    assert manager.slots.acquire(blocking=False)
    def failed(identifier):
        raise RuntimeError("Synthetic interruption")
    monkeypatch.setattr(manager, "prepare", failed)
    with pytest.raises(RuntimeError):
        manager.prepare_managed("unused")
    assert manager.slots.acquire(blocking=False)
    manager.slots.release()


def test_hydraulics_cannot_bypass_property_confirmation(manager):
    candidate=manager.search(ADDRESS)
    spec=dict(reviewed=True,rain_mm_h=50,duration_minutes=30,manning=.03,infiltration_mm_h=0,walls=[])
    with pytest.raises(ValueError):
        manager.start_hydraulics(candidate['id'],spec)
    assert not (manager.directory(candidate['id'])/'runs/property').exists()


def test_restart_marks_exploratory_worker_interrupted(manager):
    candidate=manager.search(ADDRESS)
    manager.confirm(candidate['id'],ADDRESS,True,launch=False)
    path=manager.directory(candidate['id'])/'runs/property'/('b'*32)/'status.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(id='b'*32,status='running')))
    Workspaces(manager.root,execute=manager.execute)
    assert json.loads(path.read_text())['status']=='interrupted'
