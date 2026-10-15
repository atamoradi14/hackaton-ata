import importlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def doctor(online=False, external_solver=False):
    checks = []
    def check(name, operation, required=True):
        try:
            checks.append(dict(name=name, ok=True, detail=str(operation()), required=required))
        except Exception as error:
            checks.append(dict(name=name, ok=False, detail=str(error), required=required))
    check("python", lambda: sys.version if sys.version_info[:2] == (3, 11) else fail("Python 3.11 required"))
    for package in ["affine", "rasterio", "geopandas", "pdal", "laspy", "hydromt", "hydromt_sfincs", "netCDF4", "numpy", "pandas", "xarray", "pyflwdir"]:
        check(package, lambda p=package: importlib.import_module(p).__version__)
    check("GDAL", lambda: importlib.import_module("osgeo.gdal").VersionInfo("RELEASE_NAME"))
    check("released API compatibility", compatibility_check)
    check("EPSG:2193 roundtrip", crs_check)
    check("Rasterio GeoTIFF roundtrip", raster_check)
    check("PDAL execution", lambda: subprocess.check_output(["pdal", "--version"], text=True))
    check("LAS/LAZ and PDAL roundtrip", lidar_check)
    check("solver executable", lambda: shutil.which("sfincs") or fail("sfincs missing from PATH; standalone Compose solver required"), not external_solver)
    check("disk", lambda: str(round(shutil.disk_usage(".").free / 1024**3, 2)) + " GiB available")
    check("RAM", lambda: str(round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 2)) + " GiB OS-visible", False)
    check("LINZ_API_KEY", lambda: "present (not printed)" if os.environ.get("LINZ_API_KEY") else fail("needed for official address/parcel access"), False)
    check("OPENTOPOGRAPHY_API_KEY", lambda: "present; unused/unvalidated (public selected tiles do not require it)" if os.environ.get("OPENTOPOGRAPHY_API_KEY") else fail("optional and unused"), False)
    if online:
        from ..providers.council import metadata, LAYERS
        check("Council metadata", lambda: metadata(LAYERS["overland_flow"]) ["name"], False)
    return dict(timestamp=datetime.now(timezone.utc).isoformat(), validation_scope="tooling_only" if external_solver else "WSL_backend", passed=all(c["ok"] for c in checks if c["required"]), checks=checks,
                hydraulic_validation="Run scripts/validate.ps1 for the real solver numerical gate")


def fail(message):
    raise RuntimeError(message)


def compatibility_check():
    for distribution, expected in {"hydromt": "0.10.1", "hydromt-sfincs": "1.2.2", "affine": "2.4.0"}.items():
        actual = importlib.metadata.version(distribution)
        if actual != expected:
            fail(f"{distribution} {actual} is outside the verified combination {expected}")
    if importlib.import_module("numpy").__version__.split(".")[0] != "1":
        fail("NumPy 1.x required for this locked environment")
    if importlib.import_module("pandas").__version__.split(".")[0] != "2":
        fail("Pandas 2.x required by released HydroMT-SFINCS time aliases")
    return "released HydroMT pair, Affine 2.4 and NumPy/Pandas APIs verified"


def crs_check():
    from pyproj import Transformer
    # Synthetic CRS test coordinate; never used as the site location.
    x, y = Transformer.from_crs(4326, 2193, always_xy=True).transform(174, -37)
    lon, lat = Transformer.from_crs(2193, 4326, always_xy=True).transform(x, y)
    if abs(lon - 174) > 1e-8 or abs(lat + 37) > 1e-8:
        fail("coordinate roundtrip failed")
    return "metre units and lon/lat axis order verified"


def raster_check():
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    values = np.arange(4, dtype="float32").reshape(2, 2)
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", width=2, height=2, count=1, dtype="float32", crs="EPSG:2193", transform=from_origin(0, 20, 10, 10)) as ds:
            ds.write(values, 1)
        with mem.open() as ds:
            assert ds.crs.to_epsg() == 2193 and np.array_equal(ds.read(1), values)
    return "passed"


def lidar_check():
    import json
    import tempfile
    from pathlib import Path
    import laspy
    import numpy as np
    import pdal
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "synthetic.laz"
        cloud = laspy.create(point_format=3, file_version="1.2")
        cloud.x, cloud.y, cloud.z = [1, 2], [3, 4], [5, 6]
        cloud.write(path)
        readback = laspy.read(path)
        assert np.allclose(readback.z, [5, 6])
        pipeline = pdal.Pipeline(json.dumps([str(path), {"type": "filters.stats", "dimensions": "Z"}]))
        assert pipeline.execute() == 2
        assert np.allclose(pipeline.arrays[0]["Z"], [5, 6])
    return "2 synthetic LAZ points written/read and processed"
