"""Explicitly exploratory site runs: real terrain + actual solver, assumed storm.

No claim of calibrated domain, roof drainage, building entry or measured walls.
"""
import json
import math
import shutil
import subprocess
import time
import re
import os
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import xarray as xr
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from shapely.geometry import LineString, Point, box
from hydromt_sfincs import SfincsModel
from hydromt import DataCatalog
from ..terrain.scene import sha


def parameters(spec):
    if not isinstance(spec, dict) or spec.get("reviewed") is not True:
        raise ValueError("Explicit review of exploratory assumptions is required")
    result = {}
    for key, low, high in [("rain_mm_h",0,100),("duration_minutes",10,60),("manning",.015,.08),("infiltration_mm_h",0,20)]:
        value = spec.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"Invalid {key}")
        result[key] = float(value)
    walls = spec.get("walls", [])
    if not isinstance(walls,list) or len(walls)>10:
        raise ValueError("At most ten hypothetical finite walls")
    for wall in walls:
        if not isinstance(wall,dict) or wall.get("status")!="hypothetical" or not isinstance(wall.get('points'),list) or not 2<=len(wall['points'])<=12:
            raise ValueError("Wall must have 2 to 12 reviewed hypothetical vertices")
        for point in wall["points"]:
            if not isinstance(point,list) or len(point)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in point):
                raise ValueError("Invalid wall coordinates")
            if abs(point[0])>160 or abs(point[1])>160 or not -10<=point[2]<=150:
                raise ValueError("Wall outside the bounded scene or valid elevation range")
        for a,b in zip(wall['points'],wall['points'][1:]):
            if np.linalg.norm(np.subtract(a[:2],b[:2]))<1:
                raise ValueError("Wall segments must be at least one metre long")
    result["walls"] = walls
    result["reviewed"] = True
    return result


def run(folder, root, spec, radius=400, resolution=4):
    # HydroMT helpers can leave cwd in a removed temporary folder. Restore it
    # across the whole model lifecycle, including exceptions and destruction.
    try:
        previous_cwd=Path.cwd()
    except FileNotFoundError:
        previous_cwd=Path(__file__).resolve().parents[3]
        os.chdir(previous_cwd)
    try:
        return _run(folder,root,spec,radius,resolution)
    finally:
        os.chdir(previous_cwd)


def _run(folder, root, spec, radius=400, resolution=4):
    folder,root=Path(folder).resolve(),Path(root).resolve()
    spec=parameters(spec)
    root.mkdir(parents=True,exist_ok=True)
    if (root/"sfincs.inp").exists():
        raise ValueError("Never reuse prior model inputs/output directory")
    site=json.loads((folder/"site_manifest.json").read_text())
    if not site.get("user_visual_confirmation"):
        raise ValueError("Confirmed property required")
    qc=json.loads((folder/"terrain-qc.json").read_text())
    if qc["layers"]["dem"]["vertical_datum"]!="NZVD2016":
        raise ValueError("Verified vertical datum required")
    x,y=site["nztm"]
    west,south=int(x)-radius,int(y)-radius
    bounds=[west,south,west+radius*2,south+radius*2]
    n=radius*2//resolution
    with rasterio.open(folder/"dem_discovery.tif") as source:
        if source.crs.to_epsg()!=2193:
            raise ValueError("NZTM terrain required")
        window=from_bounds(*bounds,source.transform)
        heights=source.read(1,window=window,out_shape=(n,n),resampling=Resampling.average,masked=True)
        transform=source.window_transform(window)*source.transform.scale(window.width/n,window.height/n)
        if heights.shape!=(n,n) or np.ma.getmaskarray(heights).any():
            raise ValueError("Missing DEM coverage in exploratory domain")
    buildings=gpd.read_file(folder/"buildings.gpkg",bbox=tuple(bounds)).to_crs(2193)
    footprint=rasterize([(g,1) for g in buildings.geometry if g.intersects(box(*bounds))],out_shape=(n,n),transform=transform,fill=0,dtype="uint8")
    bed=np.flipud(np.asarray(heights,dtype="float32"))
    mask=np.where(np.flipud(footprint),0,1).astype("uint8")
    mask[0,:]=np.where(mask[0,:],3,0);mask[-1,:]=np.where(mask[-1,:],3,0)
    mask[:,0]=np.where(mask[:,0],3,0);mask[:,-1]=np.where(mask[:,-1],3,0)
    model=SfincsModel(root=str(root),mode="w+")
    # Local explicit inputs only; HydroMT's default artifact fallback is neither
    # needed nor permitted to create a catalogue in a read-only user home.
    model.data_catalog=DataCatalog(fallback_lib=None)
    model.setup_grid(x0=west,y0=south,dx=resolution,dy=resolution,nmax=n,mmax=n,rotation=0,epsg=2193)
    template=model.reggrid.empty_mask.astype("float32")
    dep=template.copy(data=bed);dep.raster.set_nodata(-9999)
    model.set_grid(dep,name="dep");model.set_grid(template.copy(data=mask),name="msk")
    # 1 m measured hypsometry inside the 4 m computational cells, rather than
    # treating an averaged steep cell as a flat tank.
    model.setup_subgrid(datasets_dep=[{"elevtn":str(folder/"dem_discovery.tif")}],
                       nr_subgrid_pixels=resolution,nlevels=12,huthresh=.01,
                       manning_land=spec["manning"],manning_sea=spec["manning"])
    model.set_states(model.subgrid["z_zmin"].fillna(0).astype("float32"),name="zsini")
    cells=np.argwhere(mask==1)
    r,c=cells[np.argmin(((cells-n/2)**2).sum(axis=1))]
    probe=[west+(int(c)+.5)*resolution,south+(int(r)+.5)*resolution]
    model.set_geoms(gpd.GeoDataFrame({"name":["Exploratory model probe; not a measured gauge"]},
                                    geometry=[Point(*probe)],crs=2193),name="obs")
    rain_seconds=spec["duration_minutes"]*60
    stop_seconds=rain_seconds+1800
    start=pd.Timestamp("2020-01-01")
    stop=start+pd.Timedelta(seconds=stop_seconds)
    for key,value in dict(indexfile="sfincs.ind",tref="20200101 000000",tstart="20200101 000000",
        tstop=stop.strftime("%Y%m%d %H%M%S"),dtout=60,dtmaxout=60,dthisout=60,dtmax=.25,
        manning=spec["manning"],advection=0,storevel=1,huthresh=.01,storecumprcp=1,storezvolume=1).items():
        model.set_config(key,value)
    ticks=pd.to_datetime([start,start+pd.Timedelta(seconds=rain_seconds),start+pd.Timedelta(seconds=rain_seconds+1),stop])
    forcing=pd.Series([spec["rain_mm_h"],spec["rain_mm_h"],0,0],index=ticks,name="precip")
    forcing.index.name="time"
    model.set_forcing(forcing.to_xarray(),name="precip")
    if spec["infiltration_mm_h"]:
        model.set_grid(xr.full_like(template,spec["infiltration_mm_h"]),name="qinf")
    if spec["walls"]:
        geoms=[]
        for wall in spec["walls"]:
            line=LineString([(x+p[0],y+p[1]) for p in wall['points']])
            if buildings.geometry.intersects(line.buffer(resolution)).any():
                raise ValueError("Wall crosses or is too close to a solid building footprint; choose exposed ground or refine obstacle geometry")
            # Absolute endpoints derived from reviewed clicks; per-vertex finite crests.
            geoms.append(LineString([(x+p[0],y+p[1],p[2]) for p in wall['points']]))
        model.set_geoms(gpd.GeoDataFrame({"name":["Hypothetical finite wall"]*len(geoms),"par1":[.6]*len(geoms)},geometry=geoms,crs=2193),name="weir")
    model.write()
    manifest=dict(exploratory=True,synthetic=False,actual_terrain=True,assumed_rainfall=True,
        site_ids=dict(address=site["address_id"],parcel=site["parcel_id"]),parameters=spec,
        horizontal_crs="EPSG:2193",vertical_datum="NZVD2016",bounds_nztm=bounds,cell_size_m=resolution,
        source_sha256=sha(folder/"dem_discovery.tif"),active_cells=int((mask>0).sum()),
        buildings="Official footprint cells excluded as solid obstacles; roof runoff excluded",
        boundaries="Free outflow on outer perimeter only; no upstream external inflow; not a reviewed catchment",
        probe_nztm=probe,
        inputs={p.name:sha(p) for p in root.glob("sfincs*") if p.is_file()})
    (root/"run_manifest.json").write_text(json.dumps(manifest,indent=2))
    solver=shutil.which("sfincs")
    if not solver:raise ValueError("Actual SFINCS executable unavailable")
    begun=time.time()
    with (root/"solver.log").open("w") as log:
        execution=subprocess.run([solver],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    (root/"execution.json").write_text(json.dumps(dict(exit_code=execution.returncode,
        launcher_sha256=sha(solver),wall_time_s=time.time()-begun,log_sha256=sha(root/"solver.log")),indent=2))
    if execution.returncode:raise ValueError("Actual solver failed; inspect private log")
    with xr.open_dataset(root/"sfincs_map.nc") as ds:
        display_bed=np.asarray(ds["zb"].values)
        # This release masks subgrid water levels for dry cells. Only its exact
        # declared fill value is a dry marker; raw NaN/inf remain failures.
        with xr.open_dataset(root/"sfincs_map.nc",mask_and_scale=False) as raw:
            levels=np.asarray(raw["zs"].values)
            fill=raw["zs"].attrs.get("_FillValue")
            if not np.isfinite(levels).all():raise ValueError("Nonfinite raw solver water level")
            for variable in ["u","v"]:
                if not np.isfinite(raw[variable].values).all():raise ValueError("Nonfinite raw solver velocity")
            levels=np.where(levels==fill,display_bed,levels)
        h=levels-display_bed
        if h.shape[1:]!=(n,n):raise ValueError("Unexpected solver grid layout")
        active=mask==1
        valid=h[:,active]
        if not np.isfinite(valid).all() or valid.min() < -1e-5:raise ValueError("Nonfinite or negative solver depth")
        if "v2.4.0 Galibier Release" not in ds.attrs.get("Build-Revision",""):raise ValueError("Unexpected solver version")
        seconds=((ds.time.values-ds.time.values[0])/np.timedelta64(1,"s")).astype(float)
        if abs(seconds[-1]-stop_seconds)>1:raise ValueError("Incomplete solver history")
        rain_volume=spec["rain_mm_h"]/1000*(rain_seconds+.5)/3600*active.sum()*resolution**2
        if "subgrid_volume" not in ds:
            raise ValueError("Subgrid storage volume output required for budget checks")
        volumes=np.nan_to_num(ds["subgrid_volume"].values[:,active]).sum(axis=1)
        if rain_volume and volumes.max()>rain_volume*1.02:raise ValueError("Stored volume exceeds available rain")
        if not rain_volume and valid.max()>1e-5:raise ValueError("Zero-rain control is not dry")
        timestep=re.search(r"Average time step \(s\)\s*:\s*([\d.]+)",(root/"solver.log").read_text())
        average_dt=float(timestep[1]) if timestep else 0
        if not 0<average_dt<=.251:raise ValueError("Invalid timestep diagnostics")
        # Browser crop preserves model cell values, no invented interpolation detail.
        half=160//resolution;middle=n//2
        region=(slice(middle-half,middle+half),slice(middle-half,middle+half))
        frames=[]
        for i,elapsed in enumerate(seconds):
            crop=np.flipud(np.nan_to_num(h[i][region],nan=0))
            frames.append(dict(seconds=float(elapsed),rain_mm_h=spec["rain_mm_h"] if elapsed<=rain_seconds else 0,
                               depth_mm=np.rint(np.maximum(crop,0)*1000).astype("int32").ravel().tolist(),
                               u_cm_s=np.rint(np.flipud(np.nan_to_num(ds["u"].values[i][region]))*100).astype("int32").ravel().tolist(),
                               v_cm_s=np.rint(np.flipud(np.nan_to_num(ds["v"].values[i][region]))*100).astype("int32").ravel().tolist()))
        report=dict(status="done",exploratory=True,real_solver=True,frames=frames,
            grid=dict(rows=half*2,cols=half*2,cell_m=resolution,west=int(x)-160-x,north=int(y)+160-y,
                      bed=np.flipud(np.where(np.isfinite(display_bed[region]),display_bed[region],bed[region])).ravel().tolist()),
            validation=dict(finite_nonnegative=True,completed=True,average_dt_s=average_dt,
                            rainfall_volume_m3=float(rain_volume),final_storage_m3=float(volumes[-1]),
                            mass_balance_verified=False,relative_mass_error=None,
                            reason="Stored-volume upper bound checked; exact open-boundary flux budget not available in this released output"),
            limitations=["Exploratory uncalibrated local domain; domain convergence and external inflows unreviewed.",
                         "Rain and roughness/losses assumed, not HIRDS. Roof runoff and pipe drainage excluded.",
                         "Exact open-boundary mass budget not verified. No flood-risk verdict."],
            wall_time_s=time.time()-begun,parameters=spec,outputs={p.name:sha(p) for p in root.glob("sfincs_*.nc")})
    (root/"results.json").write_text(json.dumps(report,separators=(",",":"),allow_nan=False))
    return report


if __name__ == "__main__":
    import sys
    root=Path(sys.argv[2])
    specification=json.loads((root/"request.json").read_text())
    run(Path(sys.argv[1]),root,specification)
