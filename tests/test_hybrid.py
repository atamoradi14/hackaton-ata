import json
import threading
from pathlib import Path

import numpy as np
import pytest
import requests
from floodtwin.api.server import make_server
from floodtwin.api import freshness
from floodtwin.terrain import georeference as geo


def test_grid_missing_or_changed_never_silently_uses_orthometric_height(tmp_path, monkeypatch):
    monkeypatch.setenv('FLOODTWIN_GEOID_GRID', str(tmp_path/'missing.tif'))
    with pytest.raises(ValueError, match='Install'):
        geo.grid_path(tmp_path)
    (tmp_path/'changed.tif').write_bytes(b'changed')
    monkeypatch.setenv('FLOODTWIN_GEOID_GRID', str(tmp_path/'changed.tif'))
    with pytest.raises(ValueError, match='checksum'):
        geo.grid_path(tmp_path)


def test_geoid_sign_and_ecef_frame_against_independent_grid_sampling():
    import rasterio
    root = Path(__file__).resolve().parents[1]
    try:
        grid = geo.grid_path(root)
    except ValueError:
        pytest.skip('Authoritative grid is required in the release image; optional for source-only offline tests')
    x,y=1751744.2,5928101.3
    result=geo.frame(root,dict(nztm=[x,y]),[x-160,y-160,x+160,y+160])
    lon,lat=result['origin_lonlat']
    # An independent Rasterio bilinear read verifies h=H+N, including the sign.
    with rasterio.open(grid) as src:
        col,row=(~src.transform)*(lon,lat)
        col-=.5;row-=.5;c,r=int(np.floor(col)),int(np.floor(row))
        v=src.read(1,window=rasterio.windows.Window(c,r,2,2))
        dx,dy=col-c,row-r
        n=(1-dy)*((1-dx)*v[0,0]+dx*v[0,1])+dy*((1-dx)*v[1,0]+dx*v[1,1])
    assert result['geoid_separation_m']==pytest.approx(float(n),abs=.002)
    assert 30<result['geoid_separation_m']<40
    matrix=np.array(result['model_matrix']).reshape(4,4).T
    assert np.linalg.det(matrix[:3,:3])>0
    assert np.linalg.norm(matrix[:3,2])==pytest.approx(1,abs=1e-6)
    assert result['numerical_residual_max_m']<.01
    with pytest.raises(ValueError,match='tolerance'):
        geo.frame(root,dict(nztm=[x,y]),[x-3000,y-3000,x+3000,y+3000])


def test_provider_check_cannot_fetch_arbitrary_or_redirected_sources(monkeypatch):
    calls=[]
    monkeypatch.setattr(freshness.requests,'get',lambda *a,**k:calls.append(a))
    for url in ('http://127.0.0.1/','https://evil.invalid/collection.json','https://nz-elevation.s3.ap-southeast-2.amazonaws.com.evil.invalid/a/collection.json'):
        assert freshness.probe(dict(url=url))['state']=='unavailable'
    assert not calls


def test_live_provider_status_is_cached_and_input_records_are_preserved(tmp_path,monkeypatch):
    freshness.CACHE.clear()
    url='https://nz-elevation.s3.ap-southeast-2.amazonaws.com/test/collection.json'
    payload=b'{"title":"Synthetic catalogue"}'
    class Response:
        status_code=200
        headers={'Last-Modified':'fixture'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,*args):yield payload
    calls=[]
    def get(*args,**kwargs):
        calls.append(kwargs)
        return Response()
    monkeypatch.setattr(freshness.requests,'get',get)
    first=freshness.probe(dict(url=url,recorded_sha256='different snapshot'))
    second=freshness.probe(dict(url=url,recorded_sha256='different snapshot'))
    assert first['state']=='reachable' and first['recorded_metadata_matches'] is False
    assert second['cached'] and len(calls)==1
    assert calls[0]['allow_redirects'] is False
    assert not list(tmp_path.iterdir())


def test_public_viewer_config_exposes_only_explicit_browser_key(tmp_path,monkeypatch):
    monkeypatch.setenv('GOOGLE_MAPS_BROWSER_KEY','synthetic-browser-key')
    monkeypatch.setenv('GOOGLE_MAPS_API_KEY','private-server-key')
    monkeypatch.setenv('LINZ_API_KEY','private-linz-key')
    server=make_server(tmp_path,port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}'
        response=requests.get(url+'/api/viewer-config')
        assert response.json()['google']==dict(enabled=True,browser_key='synthetic-browser-key')
        assert 'private-server-key' not in response.text and 'private-linz-key' not in response.text
        assert requests.get(url+'/vendor/cesium/../../pyproject.toml').status_code==404
    finally:
        server.shutdown();server.server_close();thread.join()
