"""Read-only, georeferenced presentation of persisted native SFINCS outputs.

No resampling of hydraulic values. Browser precision: 1 mm / 0.01 m/s.
"""
import json
import threading
from pathlib import Path
import numpy as np
import xarray as xr
from pyproj import Transformer
from ..terrain.scene import sha
_native_lock=threading.RLock()  # netCDF4/HDF5 readers are not thread safe.


def presentation(root, site):
    root = Path(root).resolve()
    result = json.loads((root / 'results.json').read_text())
    manifest = json.loads((root / 'run_manifest.json').read_text())
    for filename,digest in manifest['inputs'].items():
        if Path(filename).name!=filename or sha(root/filename)!=digest:
            raise ValueError('Model input changed since native execution')
    if manifest['site_ids'] != dict(address=site['address_id'], parcel=site['parcel_id']):
        raise ValueError('Run belongs to a different property')
    native = root / 'sfincs_map.nc'
    if sha(native) != result['outputs']['sfincs_map.nc']:
        raise ValueError('Native output changed since validation')
    grid = result['grid']
    rows, cols, cell = grid['rows'], grid['cols'], grid['cell_m']
    x, y = site['nztm']
    transform = Transformer.from_crs(2193, 4326, always_xy=True)
    east, north = np.meshgrid(x + grid['west'] + np.arange(cols + 1)*cell,
                             y + grid['north'] - np.arange(rows + 1)*cell)
    lon, lat = transform.transform(east, north)
    grid['corners_latlon'] = np.stack([lat, lon], axis=-1).reshape(-1, 2).tolist()
    grid['origin_nztm'] = [x, y]
    grid['horizontal_crs'] = 'EPSG:2193'
    grid['vertical_datum'] = 'NZVD2016'
    with _native_lock, xr.open_dataset(native) as ds:
        active=ds.msk.values==1
        storage=np.asarray(ds.subgrid_volume.values[:,active],dtype='float64') if 'subgrid_volume' in ds else None
        result['native_budget']=dict(
            precipitation_m3=float(np.nansum(ds.cumprcp.values[-1][active],dtype='float64')*cell**2) if 'cumprcp' in ds else None,
            infiltration_m3=float(np.nansum(ds.cuminf.values[-1][active],dtype='float64')*cell**2) if 'cuminf' in ds else None,
            initial_signed_storage_m3=float(np.nansum(storage[0])) if storage is not None else None,
            final_signed_storage_m3=float(np.nansum(storage[-1])) if storage is not None else None,
            maximum_negative_storage_m3=float(np.nanmax(np.nansum(np.maximum(-storage,0),axis=1))) if storage is not None else None,
            external_inflow_m3=None, external_outflow_m3=None, exact_closure_verified=False,
            note='Native cumulative rain/losses and signed subgrid storage on mask=1 cells. Negative storage is retained as a diagnostic, not silently corrected. Boundary fluxes unavailable; rainfall minus storage is not measured outflow.')
        middle_r, middle_c = ds.sizes['n']//2, ds.sizes['m']//2
        region = (slice(middle_r-rows//2, middle_r+rows//2), slice(middle_c-cols//2, middle_c+cols//2))
        grid['active'] = np.flipud(ds.msk.values[region] == 1).ravel().astype(int).tolist()
        # Older exporters used different bed fill values in inactive buildings.
        # No hydraulic value is meaningful there; canonicalise only those cells.
        grid['bed'] = np.where(grid['active'], grid['bed'], 0).tolist()
        times=((ds.time.values-ds.time.values[0])/np.timedelta64(1,'s')).astype(float)
        if list(times)!=[f['seconds'] for f in result['frames']]:
            raise ValueError('Replay timestamps differ from native output')
        mask=np.asarray(grid['active'],dtype=bool)
        crop=dict(n=region[0],m=region[1])
        levels_crop=ds.zs.isel(**crop).values
        bed_crop=ds.zb.isel(**crop).values
        velocity_crop={var:ds[var].isel(**crop).values for var in ['u','v']}
        for index,frame in enumerate(result['frames']):
            levels=levels_crop[index]
            bed=bed_crop
            native_depth=np.rint(np.flipud(np.maximum(np.nan_to_num(levels-bed,nan=0),0))*1000).astype(int).ravel()
            if not np.array_equal(native_depth[mask],np.asarray(frame['depth_mm'])[mask]):
                raise ValueError('Replay depth differs from native output')
            for var,key in [('u','u_cm_s'),('v','v_cm_s')]:
                native_velocity=np.rint(np.flipud(np.nan_to_num(velocity_crop[var][index]))*100).astype(int).ravel()
                if not np.array_equal(native_velocity[mask],np.asarray(frame[key])[mask]):
                    raise ValueError('Replay velocity differs from native output')
        # Native hmax is computed at solver steps, unlike a maximum of minute frames.
        if 'hmax' in ds or 'zsmax' in ds:
            variable='hmax' if 'hmax' in ds else 'zsmax'
            peak = ds[variable].values
            while peak.ndim > 2:
                peak = np.max(np.where(np.isfinite(peak),peak,-np.inf),axis=0)
            if variable=='zsmax':
                peak=peak-ds.zb.values
            result['maximum_depth_mm'] = np.rint(np.maximum(np.nan_to_num(np.flipud(peak[region])), 0)*1000).astype(int).ravel().tolist()
            result['maximum_depth_source'] = f'native {variable} (solver-step maximum)'
        else:
            result['maximum_depth_mm'] = np.max([f['depth_mm'] for f in result['frames']], axis=0).tolist()
            result['maximum_depth_source'] = 'maximum of saved frames; may miss inter-frame peaks'
        result['maximum_depth_mm'] = np.where(grid['active'], result['maximum_depth_mm'], 0).tolist()
    result['provenance'] = manifest
    return result


def compatible(a, b):
    """Fail closed: comparisons must isolate walls, not storms or input artifacts."""
    for key in ['site_ids', 'horizontal_crs', 'vertical_datum', 'bounds_nztm', 'cell_size_m',
                'source_sha256', 'buildings', 'boundaries']:
        if a.get(key) != b.get(key) or key not in a:
            raise ValueError(f'Incompatible comparison: {key}')
    for key in ['rain_mm_h', 'duration_minutes', 'manning', 'infiltration_mm_h']:
        if a['parameters'].get(key) != b['parameters'].get(key):
            raise ValueError(f'Incompatible comparison: {key}')
    # Input hashes, including subgrid, forcing, grid masks and initial conditions.
    # sfincs.inp legitimately adds weirfile only; compare its content separately.
    ignored = {'sfincs.inp', 'sfincs.weir', 'sfincs.obs'}
    ai = {k:v for k,v in a['inputs'].items() if k not in ignored}
    bi = {k:v for k,v in b['inputs'].items() if k not in ignored}
    if any(ai[k]!=bi[k] for k in ai.keys() & bi.keys()):
        raise ValueError('Incompatible numerical input hashes')


def comparison(root_a, root_b, site):
    root_a, root_b = Path(root_a), Path(root_b)
    a, b = presentation(root_a, site), presentation(root_b, site)
    compatible(a['provenance'], b['provenance'])
    def configuration(root):
        return [line.strip() for line in (root/'sfincs.inp').read_text().splitlines()
                if line.strip() and not line.strip().lower().startswith(('weirfile', 'obsfile'))]
    if configuration(root_a) != configuration(root_b):
        raise ValueError('Incompatible solver configuration')
    names=set(a['provenance']['inputs'])|set(b['provenance']['inputs'])
    names-= {'sfincs.inp','sfincs.obs','sfincs.weir'}
    names.update(['sfincs_subgrid.nc', 'sfincs.dep', 'sfincs.msk', 'sfincs.ind', 'sfincs.zsini', 'sfincs.precip'])
    for name in names:
        if Path(name).name!=name:
            raise ValueError('Invalid input manifest filename')
        if not (root_a/name).exists() and not (root_b/name).exists():
            if name == 'sfincs.dep':
                continue  # Subgrid models need no separate averaged bed file.
            raise ValueError(f'Missing native input: {name}')
        if sha(root_a/name) != sha(root_b/name):
            raise ValueError(f'Incompatible native model input: {name}')
    if a['grid'] != b['grid'] or [f['seconds'] for f in a['frames']] != [f['seconds'] for f in b['frames']]:
        raise ValueError('Incompatible output grids or timestamps')
    delta = np.asarray(b['maximum_depth_mm'])-np.asarray(a['maximum_depth_mm'])
    active = np.asarray(a['grid']['active'], dtype=bool)
    valid = delta[active]/1000
    speeds = lambda r: np.max([np.hypot(f['u_cm_s'], f['v_cm_s'])/100 for f in r['frames']], axis=0)
    dv = speeds(b)-speeds(a)
    frames = [dict(seconds=fa['seconds'], delta_depth_mm=(np.asarray(fb['depth_mm'])-np.asarray(fa['depth_mm'])).tolist())
              for fa,fb in zip(a['frames'], b['frames'])]
    return dict(compatible=True, convention='modified minus baseline', grid=a['grid'], frames=frames,
                delta_maximum_depth_mm=delta.tolist(), delta_peak_sampled_speed_m_s=dv.tolist(),
                metrics=dict(maximum_increase_m=float(valid.max()), maximum_decrease_m=float(valid.min()),
                             changed_area_m2=int(np.count_nonzero(np.abs(valid)>=.001))*a['grid']['cell_m']**2,
                             max_abs_sampled_speed_change_m_s=float(np.max(np.abs(dv[active])))),
                limitations=['Velocity peaks and inundation timing sampled at saved frame intervals.',
                             'Differences quantised to 1 mm. Zero means no resolved difference at that precision.',
                             'Site boundary budget and connected-domain convergence remain unverified.'])
