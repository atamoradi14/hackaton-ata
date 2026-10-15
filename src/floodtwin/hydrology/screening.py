"""D8 terrain connectivity screening only; never hydraulic water motion."""
import json
from pathlib import Path
import numpy as np
import pyflwdir
import rasterio
from rasterio.features import geometry_mask
import geopandas as gpd
from shapely.geometry import LineString


def connectivity(data, transform, target, nodata=-9999):
    if data.ndim != 2 or target.shape != data.shape or not target.any():
        raise ValueError("Nonempty target mask matching a 2D terrain grid required")
    if transform.a <= 0 or transform.e >= 0 or transform.b != 0 or transform.d != 0:
        raise ValueError("North-up positive metre grid required")
    if np.any(data[target] == nodata) or not np.isfinite(data[target]).all():
        raise ValueError("Target crosses missing terrain")
    # A strict zero max_depth loops on self-neighbours in pyflwdir 0.5.12.
    # Use a declared 1 micrometre numerical tolerance; do not modify source DEM.
    flow = pyflwdir.from_dem(data, nodata=nodata, transform=transform, latlon=False, max_depth=1e-6)
    # Retain depressions deeper than the numerical tie tolerance as pits.
    upstream = flow.basins(idxs=np.flatnonzero(target)) > 0
    touches_edge = bool(upstream[0].any() or upstream[-1].any() or upstream[:,0].any() or upstream[:,-1].any())
    cell_area = abs(transform.a * transform.e)
    return flow, upstream, dict(screening_only=True, hydraulic=False, contributing_area_m2=float(upstream.sum()*cell_area),
                                upstream_reaches_discovery_boundary=touches_edge,
                                dem_depression_filling="only <=1e-6 m numerical ties; deeper pits retained; source DEM unchanged")


def screen_site():
    folder = Path("data/processed/site")
    parcel = gpd.read_file(folder / "parcel.geojson").to_crs(2193)
    with rasterio.open(folder / "dem_discovery.tif") as dem:
        if dem.crs.to_epsg() != 2193:
            raise ValueError("NZTM metre CRS required")
        data = dem.read(1); profile = dem.profile.copy(); transform = dem.transform
        target = geometry_mask(parcel.geometry, out_shape=data.shape, transform=transform, invert=True, all_touched=True)
        flow, upstream, result = connectivity(data, transform, target, dem.nodata)
    mask_profile = dict(profile, dtype="uint8", nodata=0)
    with rasterio.open(folder / "terrain_upstream_screening.tif", "w", **mask_profile) as dst:
        dst.write(upstream.astype("uint8"),1)
        dst.update_tags(usage="D8 terrain screening only; not hydraulic depth or a final model domain")
    downstream = flow.idxs_ds
    indices = np.flatnonzero(target)
    exits = indices[~target.ravel()[downstream[indices]]]
    paths, distances = flow.path(idxs=exits, max_length=3000, unit="m")
    records = []; geometry = []
    for sequence, length in zip(paths, distances):
        if len(sequence) < 2:
            continue
        rows, cols = np.unravel_index(sequence, data.shape)
        xs, ys = rasterio.transform.xy(transform, rows, cols)
        records.append(dict(status="inferred_terrain_screening", length_m=float(length), endpoint_verified=False,
                            reached_discovery_boundary=bool(rows[-1] in [0,data.shape[0]-1] or cols[-1] in [0,data.shape[1]-1])))
        geometry.append(LineString(zip(xs,ys)))
    if geometry:
        traces = gpd.GeoDataFrame(records,geometry=geometry,crs=2193)
        traces.to_crs(4326).to_file(folder / "terrain_downstream_screening.geojson",driver="GeoJSON")
    result.update(parcel_cells=int(target.sum()), downstream_trace_count=len(records), final_hydraulic_domain=False,
                  max_trace_length_m=3000, verified_outlet_count=0,
                  limitations=["Bare-earth D8 ignores building blockage, finite walls, drainage transfers and dynamic overtopping",
                               "Local terrain pits terminate traces; hydraulic overflow may connect additional areas",
                               "Receiving-water levels, boundary conditions and domain convergence require review",
                               "Do not interpret contributing-area or line traces as a property flood-risk result"])
    (folder / "domain-screening.json").write_text(json.dumps(result,indent=2))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8,8))
    extent=(profile["transform"].c, profile["transform"].c+data.shape[1]*transform.a,
            transform.f+data.shape[0]*transform.e, transform.f)
    ax.imshow(data,cmap="Greys",extent=extent,alpha=0.6)
    ax.imshow(np.ma.masked_where(~upstream,upstream),cmap="Greens",vmin=0,vmax=1,extent=extent,alpha=0.6)
    if geometry: traces.plot(ax=ax,color="#12658b",linewidth=0.8)
    parcel.boundary.plot(ax=ax,color="#b72e2e",linewidth=1.8)
    ax.set_title("SCREENING ONLY — D8 terrain connectivity\nGreen: possible contributors; blue: terrain traces; no hydraulic result")
    ax.ticklabel_format(style="plain",useOffset=False); ax.set_xlabel("NZTM easting (m)"); ax.set_ylabel("NZTM northing (m)")
    fig.tight_layout(); fig.savefig(folder / "domain-screening.png",dpi=150); plt.close(fig)
    return result
