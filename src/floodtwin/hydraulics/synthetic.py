"""Closed synthetic rain tank and zero-forcing control, using the real solver.

Closed boundaries are intentional ONLY for this analytical conservation test.
No site location, actual terrain or design rainfall is implied.
"""
import hashlib
import json
import importlib.metadata
from pathlib import Path
import numpy as np
import xarray as xr
import geopandas as gpd
from shapely.geometry import Point
from hydromt_sfincs import SfincsModel


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root):
    for name, rain in [("rain", 36.0), ("dry", 0.0)]:
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        model = SfincsModel(root=str(folder), mode="w+")
        model.setup_grid(x0=0, y0=0, dx=10, dy=10, nmax=10, mmax=10, rotation=0, epsg=2193)
        template = model.reggrid.empty_mask.astype("float32")
        dep = xr.full_like(template, 0.0)
        dep.raster.set_nodata(-9999)
        model.set_grid(dep, name="dep")
        model.set_grid(xr.full_like(template, 1, dtype="uint8"), name="msk")
        for key, value in dict(indexfile="sfincs.ind", tref="20200101 000000", tstart="20200101 000000", tstop="20200101 001000",
                               dtout=60, dtmaxout=60, dthisout=60, dtmax=1, manning=0.03,
                               zsini=0, advection=0, storevel=1, huthresh=0.000001).items():
            model.set_config(key, value)
        model.setup_precip_forcing(magnitude=rain)
        model.set_geoms(gpd.GeoDataFrame(
            {"name": [f"cell_{n}_{m}" for n in range(10) for m in range(10)]},
            geometry=[Point(5 + 10*m, 5 + 10*n) for n in range(10) for m in range(10)], crs=2193), name="obs")
        model.set_config("obsfile", "sfincs.obs")
        model.write()
        manifest = dict(synthetic=True, horizontal_crs="EPSG:2193", vertical_datum="synthetic relative zero; not NZVD2016 survey",
                        assumptions=["flat bed", "closed tank", "no infiltration", "no drains", "uniform synthetic rain"],
                        rainfall_mm_hr=rain, duration_s=600, area_m2=10000,
                        expected_depth_m=rain / 1000 * 600 / 3600,
                        hydromt_sfincs=importlib.metadata.version("hydromt-sfincs"),
                        solver_image="deltares/sfincs-cpu@sha256:4301bffc74f3cb3f334be5d21aa75dfe5742a16c9838942cdfc2f870859fb404",
                        inputs={p.name: sha(p) for p in folder.iterdir() if p.suffix in {".inp", ".ind", ".dep", ".msk", ".precip", ".obs"}})
        (folder / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return dict(built=str(root), synthetic=True)


def validate(root):
    results = {}
    for name in ["rain", "dry"]:
        folder = root / name
        manifest = json.loads((folder / "run_manifest.json").read_text())
        for filename, digest in manifest["inputs"].items():
            if sha(folder / filename) != digest:
                raise ValueError(f"Input changed: {filename}")
        model = SfincsModel(root=str(folder), mode="r")
        model.read()
        model.read_results()
        peak = model.results["hmax"]
        if "timemax" in peak.dims:
            peak = peak.max("timemax")
        depth = peak.values
        # SFINCS deliberately masks maps at/below huthresh. Dry cells must
        # instead be verified through all 100 unmasked observation histories.
        history = xr.open_dataset(folder / "sfincs_his.nc")
        observed = history["point_zs"].values
        if not np.isfinite(observed).all():
            raise ValueError("Nonfinite observation water levels")
        elapsed = (history["time"].values - history["time"].values[0]) / np.timedelta64(1, "s")
        analytic = manifest["rainfall_mm_hr"] / 1000 * elapsed / 3600
        time_error = float(np.max(np.abs(observed - analytic[:, None])))
        if time_error > max(1e-6, manifest["expected_depth_m"] * 0.01):
            raise ValueError(f"Observation time-series differs from analytical rain tank: {time_error}")
        if name == "dry":
            if observed.shape[-1] != 100 or np.max(np.abs(observed)) > 1e-6:
                raise ValueError("Dry control has water or missing observations")
            peak = xr.zeros_like(model.grid["dep"])
            depth = peak.values
        valid = np.isfinite(depth)
        if valid.sum() != 100:
            raise ValueError(f"Missing/nonfinite depths: {valid.sum()} valid cells")
        expected = manifest["expected_depth_m"]
        final_zs = model.results["zs"].isel(time=-1).values
        final_depth = final_zs - model.grid["dep"].values
        if name == "dry":
            final_depth = np.zeros_like(depth)
        if not np.isfinite(final_depth).all() or np.min(final_depth) < -1e-6:
            raise ValueError("Nonfinite or negative final depth")
        volume = float(np.sum(final_depth) * 100)
        target = expected * 10000
        error = abs(volume - target) / target if target else abs(volume)
        if (target and error > 0.01) or (not target and np.max(np.abs(final_depth)) > 1e-6):
            raise ValueError(f"Conservation/control failure: {error}")
        if abs(float(depth.max()) - expected) > max(1e-6, expected * 0.01):
            raise ValueError("Peak depth differs from analytical solution")
        record = dict(passed=True, synthetic=True, expected_depth_m=expected, max_depth_m=float(depth.max()),
                      stored_volume_m3=volume, rainfall_volume_m3=target, relative_volume_error=error,
                      tolerance_fraction=0.01, max_timeseries_error_m=time_error,
                      observation_cells=100, output_sha256=sha(folder / "sfincs_map.nc"))
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(elapsed, observed.mean(axis=1), "o", label="SFINCS mean of 100 cells")
        ax.plot(elapsed, analytic, "-", label="Analytical rainfall storage")
        ax.set(xlabel="Elapsed time (s)", ylabel="Depth (m)", title=f"SYNTHETIC {name} tank — numerical conservation check")
        ax.legend(); fig.tight_layout(); fig.savefig(folder / "validation.png", dpi=150); plt.close(fig)
        peak.raster.to_raster(str(folder / "depth_max.tif"))
        (folder / "mass_balance.json").write_text(json.dumps(record, indent=2))
        results[name] = record
    (root / "validation.json").write_text(json.dumps(results, indent=2))
    return results
