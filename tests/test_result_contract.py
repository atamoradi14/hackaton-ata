import json
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Polygon, box
from floodtwin.hydraulics.results import presentation, comparison, compatible
from floodtwin.hydraulics.site import parameters
from floodtwin.terrain.scene import sha
from floodtwin.terrain.roofs import triangulate


SITE=dict(address_id=1,parcel_id='2',nztm=[1751744.2,5928101.3])


def fixture(root,modified=False):
    root.mkdir()
    bed=np.ones((2,2))*10
    ds=xr.Dataset(dict(msk=(('n','m'),[[1,0],[1,1]]),zb=(('n','m'),bed),
                       zsmax=(('timemax','n','m'),[bed+(.012 if modified else .01)]),
                       zs=(('time','n','m'),[bed]),u=(('time','n','m'),[bed*0]),v=(('time','n','m'),[bed*0])),
                  coords={'time':np.array(['2020-01-01'],dtype='datetime64[ns]')})
    ds.to_netcdf(root/'sfincs_map.nc')
    for name in ['sfincs_subgrid.nc','sfincs.msk','sfincs.ind','sfincs.zsini','sfincs.precip']:
        (root/name).write_bytes(b'fixed numerical input')
    (root/'sfincs.inp').write_text('dx = 4\n'+('weirfile = sfincs.weir\n' if modified else ''))
    manifest=dict(site_ids=dict(address=1,parcel='2'),horizontal_crs='EPSG:2193',vertical_datum='NZVD2016',
                  bounds_nztm=[0,0,8,8],cell_size_m=4,source_sha256='terrain',buildings='inactive',boundaries='closed',
                  parameters=dict(rain_mm_h=50,duration_minutes=30,manning=.03,infiltration_mm_h=0,walls=[]),inputs={'sfincs.msk':sha(root/'sfincs.msk')})
    (root/'run_manifest.json').write_text(json.dumps(manifest))
    result=dict(grid=dict(rows=2,cols=2,cell_m=4,west=-4,north=4,bed=[10]*4),
                frames=[dict(seconds=0,depth_mm=[0]*4,u_cm_s=[0]*4,v_cm_s=[0]*4)],
                outputs={'sfincs_map.nc':sha(root/'sfincs_map.nc')})
    (root/'results.json').write_text(json.dumps(result))
    return root


def test_georeferencing_masks_and_native_peak_not_frame_maximum(tmp_path):
    root=fixture(tmp_path/'a');r=presentation(root,SITE)
    assert len(r['grid']['corners_latlon'])==9
    assert r['grid']['active']==[1,1,1,0]  # native south-up → browser north-down
    assert r['maximum_depth_mm']==[10,10,10,0]
    assert r['grid']['bed']==[10,10,10,0]
    assert 'zsmax' in r['maximum_depth_source']
    with pytest.raises(ValueError,match='different property'):
        presentation(root,dict(SITE,address_id=3))
    (root/'sfincs_map.nc').write_bytes(b'corrupted output')
    with pytest.raises(ValueError,match='changed'):
        presentation(root,SITE)


def test_comparison_is_quantitative_and_rejects_changed_native_inputs(tmp_path):
    a=fixture(tmp_path/'a');b=fixture(tmp_path/'b',True)
    c=comparison(a,b,SITE)
    assert c['delta_maximum_depth_mm']==[2,2,2,0]
    assert c['metrics']['changed_area_m2']==48
    assert c['frames'][0]['delta_depth_mm']==[0]*4
    (b/'sfincs_subgrid.nc').write_bytes(b'different terrain tables')
    with pytest.raises(ValueError,match='native model input'):
        comparison(a,b,SITE)


def test_storm_mismatch_rejected(tmp_path):
    a=fixture(tmp_path/'a');b=fixture(tmp_path/'b',True)
    ma=json.loads((a/'run_manifest.json').read_text());mb=json.loads((b/'run_manifest.json').read_text())
    mb['parameters']['rain_mm_h']=40
    with pytest.raises(ValueError,match='rain_mm_h'):
        compatible(ma,mb)


def test_replay_cannot_substitute_invented_depth(tmp_path):
    root=fixture(tmp_path/'a')
    r=json.loads((root/'results.json').read_text())
    r['frames'][0]['depth_mm'][0]=50
    (root/'results.json').write_text(json.dumps(r))
    with pytest.raises(ValueError,match='Replay depth'):
        presentation(root,SITE)


def test_changed_input_does_not_relabel_saved_native_execution(tmp_path):
    root=fixture(tmp_path/'a')
    (root/'sfincs.msk').write_bytes(b'changed obstacle mask')
    with pytest.raises(ValueError,match='Model input changed'):
        presentation(root,SITE)


def test_model_lifecycle_restores_cwd_on_worker_failure(tmp_path,monkeypatch):
    import os
    from pathlib import Path
    from floodtwin.hydraulics import site
    previous=Path.cwd()
    def fail(*args):
        os.chdir(tmp_path)
        raise ValueError('Native helper failure')
    monkeypatch.setattr(site,'_run',fail)
    with pytest.raises(ValueError,match='Native helper failure'):
        site.run(tmp_path,tmp_path,{})
    assert Path.cwd()==previous


def test_polyline_vertices_and_segment_lengths():
    spec=dict(reviewed=True,rain_mm_h=50,duration_minutes=30,manning=.03,infiltration_mm_h=0,
              walls=[dict(status='hypothetical',points=[[0,0,10],[4,0,10.2],[4,4,10.3]])])
    assert len(parameters(spec)['walls'][0]['points'])==3
    spec['walls'][0]['points'][2]=[4,.1,10.3]
    with pytest.raises(ValueError,match='segments'):
        parameters(spec)


def test_roof_outlier_removed_and_no_triangle_crosses_footprint_hole():
    x,y=np.meshgrid(np.arange(0,6,.4),np.arange(0,6,.4))
    points=np.column_stack([x.ravel(),y.ravel(),np.ones(x.size)*12])
    points[50,2]=50
    footprint=Polygon([(0,0),(6,0),(6,6),(0,6)],holes=[[(2,2),(4,2),(4,4),(2,4)]])
    vertices,triangles,qa=triangulate(points,footprint)
    assert qa['rejected_points']>=1
    assert vertices[:,2].max()==12
    assert len(triangles)>0
    assert all(footprint.covers(Polygon(vertices[t,:2])) for t in triangles)


def test_recorded_aerial_is_reprojected_for_leaflet_not_bbox_stretched(tmp_path):
    from PIL import Image
    from floodtwin.api.assets import aerial_overlay
    p=tmp_path/'scene-aerial.jpg'
    Image.fromarray(np.full((20,20,3),180,dtype='uint8')).save(p)
    (tmp_path/'scene-aerial.json').write_text(json.dumps(dict(
        title='Synthetic offline imagery fixture',sha256=sha(p),
        bounds_nztm=[1751700,5928100,1751720,5928120])))
    result=aerial_overlay(tmp_path)
    assert result['display_crs']=='EPSG:3857'
    assert result['bounds'][0][0]<result['bounds'][1][0]
    assert result['bounds'][0][1]<result['bounds'][1][1]
    pixels=np.asarray(Image.open(tmp_path/'map-aerial.png'))
    assert pixels.shape==(20,20,4)
    assert pixels[10,10,3]==255
    assert aerial_overlay(tmp_path)==result
