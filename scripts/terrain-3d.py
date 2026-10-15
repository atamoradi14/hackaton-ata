"""Actual DEM-only terrain preview; no invented water or added structures."""
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder = Path("data/processed/site")
site = json.loads((folder / "site_manifest.json").read_text())
x,y=site["nztm"]
with rasterio.open(folder / "dem_discovery.tif") as source:
    window=from_bounds(x-100,y-100,x+100,y+100,source.transform).round_offsets().round_lengths()
    values=source.read(1,window=window,masked=True)
    transform=source.window_transform(window)
    row,col=np.indices(values.shape)
    east=transform.c+(col+0.5)*transform.a
    north=transform.f+(row+0.5)*transform.e
    point_z=float(next(source.sample([(x,y)]))[0])
fig=plt.figure(figsize=(10,7))
ax=fig.add_subplot(111,projection="3d")
ax.plot_surface((east-x)[::2,::2],(north-y)[::2,::2],values[::2,::2],cmap="terrain",linewidth=0,antialiased=False)
ax.scatter([0],[0],[point_z],c="#b52927",s=60,label="Official address point on DEM")
ax.set(xlabel="Easting offset (m)",ylabel="Northing offset (m)",zlabel="Ground elevation (m NZVD2016)")
ax.view_init(elev=38,azim=-65); ax.legend(loc="upper left")
ax.set_title("Actual bare-earth DEM — 200 m discovery preview\nOriginal 1 m samples drawn every 2 m; vertical scale exaggerated for visibility\nNo water surface or verified structures modelled")
fig.tight_layout(); fig.savefig(folder / "terrain-3d.png",dpi=150); plt.close(fig)
print("Actual terrain-only 3D preview saved")
