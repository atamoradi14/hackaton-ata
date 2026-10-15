"""Offline hydraulic regression fixtures; all geometry/levels are synthetic.

Closed boundaries isolate internal flux conservation, not site outlet behaviour.
This is not an analytical validation of transient weir discharge or calibration.
"""
import importlib.metadata
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import xarray as xr
from hydromt_sfincs import SfincsModel
from shapely.geometry import LineString, Point

from .synthetic import sha


CASES = {
    "dry": {"bed": "flat", "initial": "dry", "dx": 2.0},
    "rain_closed": {"bed": "flat", "initial": "dry", "dx": 2.0, "rain_mm_h":20},
    "still_water": {"bed": "slope", "initial": "level", "dx": 2.0},
    "slope": {"bed": "slope", "initial": "depth", "dx": 2.0},
    "open": {"bed": "flat", "initial": "step", "dx": 2.0},
    "weir": {"bed": "flat", "initial": "step", "dx": 2.0, "structure": "weir"},
    "weir_fine": {"bed": "flat", "initial": "step", "dx": 1.0, "structure": "weir"},
    "weir_timestep": {"bed": "flat", "initial": "step", "dx": 2.0, "structure": "weir", "dtmax": 0.25},
    "weir_below_crest": {"bed": "flat", "initial": "below", "dx": 2.0, "structure": "weir"},
    "weir_bypass": {"bed": "flat", "initial": "below", "dx": 2.0, "structure": "weir", "endpoints":[[20,2],[20,8]]},
    "weir_reversed": {"bed": "flat", "initial": "step", "dx": 2.0, "structure": "weir", "endpoints":[[20,10],[20,0]]},
    "infinite_barrier": {"bed": "flat", "initial": "step", "dx": 2.0, "structure": "thd"},
}
SOLVER_IMAGE = "deltares/sfincs-cpu@sha256:4301bffc74f3cb3f334be5d21aa75dfe5742a16c9838942cdfc2f870859fb404"
DURATION = 3600


def fixture_arrays(case):
    """Cell-centred arrays and explicit initial levels; no geodata required."""
    dx = case["dx"]
    x, y = np.meshgrid(np.arange(dx / 2, 40, dx), np.arange(dx / 2, 10, dx))
    bed = 0.01 * (40 - x) if case["bed"] == "slope" else np.zeros_like(x)
    initial = case["initial"]
    if initial == 'dry':
        zs = bed.copy()
    elif initial == "level":
        zs = np.full_like(bed, 0.6)
    elif initial == "depth":
        zs = bed + 0.2
    else:
        zs = np.where(x < 20, 0.3 if initial == "below" else 0.6, 0.1)
    return x, y, bed, zs


def build(root):
    root = Path(root)
    # Never mix fresh inputs with stale output from an earlier solver invocation.
    root.mkdir(parents=True, exist_ok=False)
    for name, case in CASES.items():
        folder = root / name
        folder.mkdir()
        x, y, bed, zs = fixture_arrays(case)
        dx = case["dx"]
        model = SfincsModel(root=str(folder), mode="w+")
        model.setup_grid(x0=0, y0=0, dx=dx, dy=dx, nmax=bed.shape[0], mmax=bed.shape[1], rotation=0, epsg=2193)
        template = model.reggrid.empty_mask.astype("float32")
        dep = template.copy(data=bed.astype("float32"))
        dep.raster.set_nodata(-9999)
        model.set_grid(dep, name="dep")
        model.set_grid(xr.full_like(template, 1, dtype="uint8"), name="msk")
        model.set_states(template.copy(data=zs.astype("float32")), name="zsini")
        for key, value in dict(indexfile="sfincs.ind", tref="20200101 000000", tstart="20200101 000000",
                               tstop="20200101 010000", dtout=10, dtmaxout=10, dthisout=10,
                               dtmax=case.get("dtmax", 0.5), manning=0.03,
                               advection=0, storevel=1, huthresh=1e-6).items():
            model.set_config(key, value)
        model.set_geoms(gpd.GeoDataFrame(
            {"name": [f"cell_{i}" for i in range(x.size)]},
            geometry=[Point(a, b) for a, b in zip(x.ravel(), y.ravel())], crs=2193), name="obs")
        if case.get('rain_mm_h'):
            import pandas as pd
            rain=pd.Series([case['rain_mm_h']]*2,index=pd.to_datetime(['2020-01-01 00:00:00','2020-01-01 01:00:00']),name='precip')
            rain.index.name='time'
            model.set_forcing(rain.to_xarray(),name='precip')
        if "structure" in case:
            kind = case["structure"]
            attrs = {"name": ["SYNTHETIC finite weir" if kind == "weir" else "SYNTHETIC infinite barrier"]}
            if kind == "weir":
                attrs.update(z=[0.4], par1=[0.6])
            model.set_geoms(gpd.GeoDataFrame(attrs, geometry=[LineString(case.get('endpoints',[(20, 0), (20, 10)]))], crs=2193), name=kind)
        model.write()
        inputs = {p.name: sha(p) for p in folder.glob("sfincs.*") if p.is_file()}
        manifest = dict(synthetic=True, case=name, parameters=case, duration_s=DURATION,
                        horizontal_crs="EPSG:2193", vertical_datum="synthetic relative zero; not a surveyed datum",
                        grid_extent_m=[0, 0, 40, 10], cell_area_m2=dx ** 2,
                        initial_volume_m3=float(((zs - bed) * dx ** 2).sum()),
                        rainfall_volume_m3=case.get('rain_mm_h',0)/1000*400, losses_volume_m3=0, external_flux_volume_m3=0,
                        weir_crest_m=0.4 if case.get("structure") == "weir" else None,
                        assumptions=["synthetic cell-centred terrain and levels", "closed rectangular tank",
                                     "assumed uniform rain where specified; no infiltration or drainage", "Manning 0.03 assumed for fixture",
                                     "local-inertial solver (advection=0)", "finite crest 0.4 m; coefficient 0.6 where weir present"],
                        hydromt_sfincs=importlib.metadata.version("hydromt-sfincs"),
                        solver_image=SOLVER_IMAGE, inputs=inputs)
        (folder / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return {"built": str(root), "synthetic": True, "cases": list(CASES)}


def verify_inputs(folder, manifest):
    for filename, digest in manifest["inputs"].items():
        if sha(folder / filename) != digest:
            raise ValueError(f"Input changed: {folder.name}/{filename}")


def run(root):
    """Launch actual pinned solver wrapper; preserve exits/logs/output hashes."""
    solver = shutil.which("sfincs")
    if not solver:
        raise RuntimeError("SFINCS executable missing; run setup/doctor before hydraulic quality suite")
    root = Path(root).resolve()
    build(root)
    for name in CASES:
        folder = root / name
        manifest = json.loads((folder / "run_manifest.json").read_text())
        verify_inputs(folder, manifest)
        started = time.time()
        with (folder / "solver.log").open("w") as log:
            result = subprocess.run([solver], cwd=folder, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        record = {"exit_code": result.returncode, "wall_time_s": time.time() - started,
                  "launcher_sha256": sha(Path(solver)), "solver_image": SOLVER_IMAGE,
                  "inputs": manifest["inputs"],
                  "outputs": {p.name: sha(p) for p in folder.glob("sfincs_*.nc")},
                  "log_sha256": sha(folder / "solver.log")}
        (folder / "execution.json").write_text(json.dumps(record, indent=2))
        if result.returncode != 0:
            raise RuntimeError(f"Solver exit {result.returncode} for {name}; inspect {folder}/solver.log")
    return validate(root)


def check_history(levels, bed, initial_volume, cell_area):
    """All-cell histories make negative/NaN/missing states and mass drift explicit."""
    levels = np.asarray(levels)
    bed = np.asarray(bed).ravel()
    if levels.ndim != 2 or levels.shape[1] != bed.size or not np.isfinite(levels).all():
        raise ValueError("Missing/nonfinite cell water levels")
    depth = levels - bed[None, :]
    if depth.min() < -1e-6:
        raise ValueError("Negative water depth")
    volumes = depth.sum(axis=1) * cell_area
    error = float(np.max(np.abs(volumes - initial_volume)) / max(float(np.max(initial_volume)),1e-10))
    if error > 0.005:
        raise ValueError(f"Closed tank volume drift exceeds 0.5%: {error}")
    return volumes, error


def validate(root):
    root = Path(root)
    records, histories = {}, {}
    for name, case in CASES.items():
        folder = root / name
        manifest = json.loads((folder / "run_manifest.json").read_text())
        execution = json.loads((folder / "execution.json").read_text())
        verify_inputs(folder, manifest)
        if manifest["parameters"] != case or manifest["duration_s"] != DURATION:
            raise ValueError(f"Fixture definition differs from this validator: {name}")
        if execution["exit_code"] != 0 or execution["inputs"] != manifest["inputs"]:
            raise ValueError(f"Unsuccessful or mismatched solver execution: {name}")
        if not {"sfincs_his.nc", "sfincs_map.nc"} <= execution["outputs"].keys():
            raise ValueError(f"Missing solver output hashes: {name}")
        for filename, digest in execution["outputs"].items():
            if sha(folder / filename) != digest:
                raise ValueError(f"Solver output changed: {name}/{filename}")
        log = (folder / "solver.log").read_text()
        if sha(folder / "solver.log") != execution["log_sha256"] or "Simulation finished" not in log:
            raise ValueError(f"Missing/mismatched successful solver log: {name}")
        timestep = re.search(r"Average time step \(s\)\s*:\s*([\d.]+)", log)
        if not timestep or float(timestep[1]) <= 0:
            raise ValueError(f"Missing/invalid timestep diagnostics: {name}")
        x, y, bed, initial = fixture_arrays(case)
        with xr.open_dataset(folder / "sfincs_his.nc") as ds:
            levels = ds["point_zs"].transpose("time", "stations").values
            speed = np.hypot(ds["point_u"].values, ds["point_v"].values)
            if not np.isfinite(speed).all():
                raise ValueError(f"Nonfinite velocity: {name}")
            seconds = (ds.time.values - ds.time.values[0]) / np.timedelta64(1, "s")
            if "v2.4.0 Galibier Release" not in ds.attrs.get("Build-Revision", ""):
                raise ValueError(f"Unexpected solver version: {name}")
            if len(seconds) != DURATION // 10 + 1 or not np.array_equal(seconds, np.arange(0, DURATION + 1, 10)):
                raise ValueError(f"Incomplete simulation history: {name}")
            # Ensure spatial ordering is the all-cell observation order used above.
            if not np.allclose(ds["station_x"].values, x.ravel()) or not np.allclose(ds["station_y"].values, y.ravel()):
                raise ValueError(f"Observation ordering mismatch: {name}")
        if np.max(np.abs(levels[0] - initial.ravel())) > 1e-6:
            raise ValueError(f"Initial state not honoured: {name}")
        expected=manifest['initial_volume_m3']+case.get('rain_mm_h',0)/1000*400*seconds/3600
        volumes, error = check_history(levels, bed, expected, case["dx"] ** 2)
        left = x.ravel() < 20
        left_mean, right_mean = levels[:, left].mean(axis=1), levels[:, ~left].mean(axis=1)
        transfer = float(((levels[-1, ~left] - initial.ravel()[~left]) * case["dx"] ** 2).sum())
        records[name] = dict(passed=True, initial_volume_m3=manifest["initial_volume_m3"],
                             final_volume_m3=float(volumes[-1]), max_relative_volume_error=error,
                             max_abs_level_change_m=float(np.max(np.abs(levels - initial.ravel()))),
                             left_final_mean_level_m=float(left_mean[-1]), right_final_mean_level_m=float(right_mean[-1]),
                             net_transfer_to_right_m3=transfer, observation_cells=x.size,
                             duration_s=DURATION, solver_wall_time_s=execution["wall_time_s"],
                             solver_average_timestep_s=float(timestep[1]),
                             max_observed_speed_m_s=float(speed.max()),
                             outputs=execution["outputs"])
        histories[name] = (seconds, left_mean, right_mean)
        if name in {"dry", "still_water", "weir_below_crest", "infinite_barrier"}:
            if records[name]["max_abs_level_change_m"] > 1e-5 or speed.max() > 1e-5:
                raise ValueError(f"Expected stationary water changed: {name}")
        if name in {"slope", "open"}:
            target = 0.4 if name == "slope" else 0.35
            if np.max(np.abs(levels[-1] - target)) > 0.005:
                raise ValueError(f"Redistribution did not approach analytical equilibrium: {name}")
            if transfer < 5:
                raise ValueError(f"Expected downslope/head-driven transfer missing: {name}")
        if name=='rain_closed' and abs(float(levels[-1].mean())-.02)>.0001:
            raise ValueError('Closed rainfall tank does not accumulate the analytical rain depth')
        if name=='weir_bypass' and (transfer<10 or np.max(np.abs(levels[-1]-.2))>.005):
            raise ValueError('Finite barrier endpoint bypass missing')
        if case.get("structure") == "weir" and name not in {"weir_below_crest",'weir_bypass'}:
            if transfer < 10 or not 0.39 < left_mean[-1] < 0.43:
                raise ValueError(f"Finite wall did not overflow/retain water correctly: {name}")
        (folder / "mass_balance.json").write_text(json.dumps(records[name], indent=2))
    if records["weir"]["left_final_mean_level_m"] <= records["open"]["left_final_mean_level_m"] + 0.03:
        raise ValueError("Finite wall did not raise upstream water relative to open baseline")
    sensitivity = {}
    for alternate in ["weir_fine", "weir_timestep", 'weir_reversed']:
        difference = float(max(np.max(np.abs(histories["weir"][i] - histories[alternate][i])) for i in [1, 2]))
        if difference > 0.02:
            raise ValueError(f"Resolution/timestep mean-level sensitivity exceeds 2 cm: {alternate}, {difference}")
        sensitivity[alternate] = {"max_compartment_mean_level_difference_m": difference, "tolerance_m": 0.02}
    summary = dict(passed=True, synthetic=True, root=str(root), cases=records, sensitivities=sensitivity,
                   tolerances={"mass_balance_fraction": 0.005, "stationary_level_m": 1e-5,
                               "stationary_speed_m_s": 1e-5,
                               "equilibrium_level_m": 0.005, "sensitivity_level_m": 0.02},
                   limitations=["closed fixtures do not establish site boundary/domain convergence",
                                "no analytical transient discharge comparison or observed site calibration",
                                "rainfall tested in closed tank only; no infiltration, drainage or SWMM coupling",
                                "all levels, crest heights and roughness are synthetic assumptions"])
    (root / "validation.json").write_text(json.dumps(summary, indent=2))
    write_report(root, summary, histories)
    return summary


def write_report(root, summary, histories):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for name in ["open", "weir", "infinite_barrier"]:
        seconds, left, right = histories[name]
        axes[0].plot(seconds, left, label=name)
        axes[1].plot(seconds, right, label=name)
    for ax, title in zip(axes, ["Upstream compartment", "Downstream compartment"]):
        ax.set(xlabel="Time (s)", ylabel="Mean water level (m)", title=title)
        ax.axhline(0.4, color="gray", linestyle="--", label="Synthetic finite crest")
        ax.legend()
    fig.suptitle("SYNTHETIC DEMONSTRATION — real SFINCS closed-tank hydraulics")
    fig.tight_layout()
    fig.savefig(root / "comparison.png", dpi=150)
    plt.close(fig)
    rows = "".join(f"<tr><td>{name}</td><td>{r['max_relative_volume_error']:.3g}</td>"
                   f"<td>{r['left_final_mean_level_m']:.5f}</td><td>{r['right_final_mean_level_m']:.5f}</td>"
                   f"<td>{r['net_transfer_to_right_m3']:.3f}</td></tr>" for name, r in summary["cases"].items())
    text = f"""<!doctype html><meta charset="utf-8"><title>Synthetic hydraulic validation</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:40px auto}}td,th{{padding:8px;text-align:left}}img{{width:100%}}</style>
<h1>Synthetic hydraulic validation: PASS</h1><p>All geometry, levels and wall heights are synthetic.
Actual SFINCS solver outputs; no Auckland site result or property risk claim.</p>
<img src="comparison.png" alt="Synthetic upstream and downstream compartment levels">
<table><tr><th>Fixture</th><th>Max volume error fraction</th><th>Upstream level (m)</th><th>Downstream level (m)</th><th>Net transfer right (m³)</th></tr>{rows}</table>
<p>Finite wall crest: 0.4 m, discharge coefficient: 0.6. Infinite barrier is a deliberate extreme scenario.
Closed outer boundaries isolate internal mass conservation. No drains or rain.</p>
<p>1 m vs 2 m cells and 0.25 s vs 0.5 s maximum timesteps are compared over all sampled times.
These tests do not establish connected site domain convergence, transient discharge accuracy or field calibration.</p>
<p><a href="validation.json">Quantitative validation and tolerances</a></p>"""
    (root / "overview.html").write_text(text, encoding="utf-8")
