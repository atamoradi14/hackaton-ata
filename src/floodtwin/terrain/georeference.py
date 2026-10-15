"""Auditable local NZTM/NZVD2016 -> geocentric display frame. No network fallback."""
import hashlib
import os
from pathlib import Path

import numpy as np
from pyproj import Transformer

GRID_NAME = 'nz_linz_nzgeoid2016.tif'
GRID_SHA256 = 'b986261d778e30b52b7d9ae24280c704c280c13bb02e51f3dca65fa862d1f027'
GRID_URL = 'https://cdn.proj.org/' + GRID_NAME


def grid_path(root):
    candidates = [Path(os.environ['FLOODTWIN_GEOID_GRID'])] if os.environ.get('FLOODTWIN_GEOID_GRID') else [
        Path('/opt/conda/share/proj') / GRID_NAME, Path(root) / 'data/geodesy' / GRID_NAME]
    for path in candidates:
        if path.is_file():
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != GRID_SHA256:
                    raise ValueError('NZGeoid2016 checksum mismatch; globe alignment disabled')
            return path.resolve()
    raise ValueError('Install the verified NZGeoid2016 grid to enable globe alignment')


def frame(root, site, bounds):
    path = grid_path(root)
    xy = Transformer.from_crs(2193, 4167, always_xy=True, allow_ballpark=False)
    # h = H + N. Explicit positive grid shift; never permit a silent no-op CRS transform.
    height = Transformer.from_pipeline('+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad '
        '+step +proj=vgridshift +grids=' + path.as_posix() + ' +multiplier=1 '
        '+step +proj=unitconvert +xy_in=rad +xy_out=deg')
    cart = Transformer.from_pipeline('+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad '
        '+step +proj=cart +ellps=GRS80')
    def exact(east, north, z):
        lon, lat = xy.transform(east, north, errcheck=True)
        lon, lat, ellipsoid = height.transform(lon, lat, z, errcheck=True)
        return np.asarray(cart.transform(lon, lat, ellipsoid, errcheck=True))
    x, y = site['nztm']
    origin = exact(x, y, 0)
    east = (exact(x + 1, y, 0) - exact(x - 1, y, 0)) / 2
    north = (exact(x, y + 1, 0) - exact(x, y - 1, 0)) / 2
    up = exact(x, y, 1) - origin
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack([east, north, up])
    matrix[:3, 3] = origin
    residuals = []
    for xx in np.linspace(bounds[0], bounds[2], 5):
        for yy in np.linspace(bounds[1], bounds[3], 5):
            for z in (0, 100):
                residuals.append(float(np.linalg.norm(exact(xx, yy, z) - (origin + east*(xx-x) + north*(yy-y) + up*z))))
    error = max(residuals)
    if not np.isfinite(error) or error > .03:
        raise ValueError('Display frame exceeds the 3 cm numerical approximation tolerance')
    lon, lat = xy.transform(x, y)
    offset = height.transform(lon, lat, 0)[2]
    return dict(model_matrix=matrix.T.ravel().tolist(), origin_lonlat=[lon, lat],
        geoid_separation_m=offset, numerical_residual_max_m=error,
        source_horizontal_crs='EPSG:2193', source_vertical_datum='NZVD2016',
        display_frame='NZGD2000 / GRS80 geocentric, used as WGS84 display approximation',
        method='NZTM inverse projection; h=H+NZGeoid2016; local first-order projected frame',
        limitations='Numerical residual is not Google alignment accuracy. No epoch/deformation or photogrammetry bias correction; source alignment requires independent control.',
        grid=dict(name=GRID_NAME, sha256=GRID_SHA256, source=GRID_URL, license='CC-BY-4.0; LINZ via PROJ-data'))
