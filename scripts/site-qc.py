"""Measured terrain QA only. No rainfall, flood simulation or wall assignment."""
import json
from pathlib import Path
import numpy as np
import geopandas as gpd
import laspy
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder = Path("data/processed/site")
cloud = laspy.read(folder / "pointcloud_crop.laz")
valid_ground = (cloud.classification == 2) & (cloud.withheld == 0)
if not valid_ground.any():
    raise RuntimeError("No non-withheld classified ground points")
x, y, z = np.asarray(cloud.x)[valid_ground], np.asarray(cloud.y)[valid_ground], np.asarray(cloud.z)[valid_ground]
with rasterio.open(folder / "dem_discovery.tif") as dem:
    sampled = np.array([v[0] for v in dem.sample(zip(x, y))])
    if np.any(sampled == dem.nodata) or not np.isfinite(sampled).all():
        raise RuntimeError("Ground comparison crosses DEM nodata")
    difference = z - sampled
    site = json.loads((folder / "site_manifest.json").read_text())
    sx, sy = site["nztm"]
    distance = np.arange(-100, 101, dtype=float)
    east_profile = np.array([v[0] for v in dem.sample(zip(sx+distance, np.full_like(distance, sy)))])
    north_profile = np.array([v[0] for v in dem.sample(zip(np.full_like(distance, sx), sy+distance))])
result = dict(actual_data=True, synthetic=False, compared_ground_points=int(valid_ground.sum()),
              comparison="Class 2 non-withheld point elevations minus nearest DEM cell (same survey; not independent validation)",
              median_difference_m=float(np.median(difference)), p05_p95_difference_m=np.percentile(difference,[5,95]).tolist(),
              rmse_m=float(np.sqrt(np.mean(difference**2))),
              percent_abs_difference_above_0_4m=float(np.mean(np.abs(difference)>0.4)*100),
              limitations=["Same-survey comparison does not establish independent accuracy",
                           "Nearest raster-cell sampling is affected by slopes/terrain discontinuities",
                           "Profiles do not identify walls or their crest heights",
                           "Rainfall, connected domain, roughness, barriers and drainage remain unverified"])
(folder / "ground-dem-qc.json").write_text(json.dumps(result, indent=2))
np.savetxt(folder / "terrain-cross-sections.csv", np.column_stack([distance,east_profile,north_profile]),
           delimiter=",", header="offset_m,east_west_dem_m_NZVD2016,north_south_dem_m_NZVD2016", comments="")
fig, axes = plt.subplots(1,2,figsize=(12,4.5))
axes[0].hist(difference,bins=np.linspace(-1,1,101),color="#39798c")
axes[0].set(xlabel="Ground point minus DEM cell (m); display limited to ±1 m",ylabel="Point count",title="Same-survey consistency (not independent accuracy)")
axes[1].plot(distance,east_profile,label="East–west DEM transect")
axes[1].plot(distance,north_profile,label="North–south DEM transect")
axes[1].axvline(0,color="#c4322b",linestyle="--",label="Official address point")
axes[1].set(xlabel="Offset from official address point (m)",ylabel="Elevation (m NZVD2016)",title="Actual ground profiles — no barrier crest assignment")
axes[1].legend(); fig.suptitle("Research terrain QC — no hydraulic/flood-risk result")
fig.tight_layout(); fig.savefig(folder / "ground-dem-qc.png",dpi=150); plt.close(fig)
print(json.dumps(result,indent=2))
