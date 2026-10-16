import json
import threading

import geopandas as gpd
import numpy as np
import pytest
import requests
from shapely.geometry import LineString, Polygon, MultiPolygon

from floodtwin.properties import Evidence, PointEvidence, Registry, build_record, flow_relationship, segments
from floodtwin.api.server import make_server


POLYGON=Polygon([(0,0),(4,0),(4,1),(3,1),(3,3),(1,3),(1,1),(0,1)])


def test_eight_original_edges_stable_ids_and_two_endpoints():
    edges=list(segments(POLYGON))
    assert len(edges)==8
    assert all(len(e['endpoints_nztm'])==len(e['geometry']['coordinates'])==2 for e in edges)
    reversed_polygon=Polygon(list(POLYGON.exterior.coords)[::-1])
    assert {e['id'] for e in edges}=={e['id'] for e in segments(reversed_polygon)}
    assert sum(e['length_m'] for e in edges)==pytest.approx(POLYGON.length)


def test_holes_multipart_and_invalid_geometry():
    p=Polygon([(0,0),(8,0),(8,8),(0,8)],holes=[[(2,2),(3,2),(3,3),(2,3)]])
    multi=MultiPolygon([p,Polygon([(10,0),(11,0),(11,1),(10,1)])])
    edges=list(segments(multi))
    assert len(edges)==12 and sum(e['is_hole'] for e in edges)==4
    with pytest.raises(ValueError,match='valid Polygon'):
        list(segments(Polygon([(0,0),(1,1),(0,1),(1,0)])))


@pytest.mark.parametrize('coordinates,expected,crossed',[
    ([(2,-1),(2,1)],'crosses',True),([(-1,0),(0,0)],'touches',False),
    ([(1,0),(3,0)],'overlaps',False),([(0,-.5),(4,-.5)],'parallels',False),
    ([(0,-3),(4,-3)],'outside',False)])
def test_flow_relationship_not_a_risk_score(coordinates,expected,crossed):
    frame=gpd.GeoDataFrame({'OBJECTID':[42],'unknown_publisher_field':['preserved']},geometry=[LineString(coordinates)],crs=2193)
    result=flow_relationship(LineString([(0,0),(4,0)]),Evidence({'overland_flow':frame}),1)
    assert result['relation']==expected and result['crossed_by_flow_path'] is crossed
    if result['matches']: assert result['matches'][0]['source_attributes']['unknown_publisher_field']=='preserved'


def test_missing_is_not_empty_and_proximity_not_structure_type():
    line=LineString([(0,0),(4,0)])
    assert flow_relationship(line,Evidence(),1)['crossed_by_flow_path'] is None
    empty=gpd.GeoDataFrame(geometry=[],crs=2193)
    assert flow_relationship(line,Evidence({'overland_flow':empty}),1)['crossed_by_flow_path'] is False
    object_frame=gpd.GeoDataFrame({'OBJECTID':[1,2],'material':['stone','steel'],'extra':['kept','too far']},
        geometry=[LineString([(1,.5),(3,.5)]),LineString([(1,5),(3,5)])],crs=2193)
    record=build_record(POLYGON,'synthetic',7,{'extra':'raw'},Evidence({'fences':object_frame}))
    first=record['boundary_segments'][0]
    assert len(first['nearby_objects'])==1
    assert record['objects'][0]['source_attributes']['extra']=='kept'
    assert first['structure']['type']=='unknown' and first['structure']['material'] is None
    assert first['risk']['level'] is None


def test_property_keeps_interior_objects_not_just_boundary_corridors():
    polygon=Polygon([(0,0),(20,0),(20,20),(0,20)])
    frame=gpd.GeoDataFrame({'OBJECTID':[1],'all_raw_fields':['preserved']},
        geometry=[Polygon([(8,8),(12,8),(12,12),(8,12)])],crs=2193)
    record=build_record(polygon,'synthetic',9,evidence=Evidence({'buildings':frame}))
    assert len(record['objects'])==len(record['property_object_ids'])==1
    assert record['objects'][0]['source_attributes']['all_raw_fields']=='preserved'
    assert all(not e['nearby_objects'] for e in record['boundary_segments'])


def test_review_survives_rebuild_and_validation(tmp_path):
    registry=Registry(tmp_path); record=build_record(POLYGON,'synthetic',7)
    registry.save(record); edge=record['boundary_segments'][0]['id']
    registry.review(record['id'],edge,dict(type='fence',height_m=1.8,notes='Synthetic offline measured-example note'))
    registry.save(build_record(POLYGON,'synthetic',7))
    updated=registry.get(record['id'])['boundary_segments'][0]
    assert updated['structure']['height_m']==1.8 and updated['structure']['review_status']=='manually_reviewed'
    assert updated['review']['independently_verified'] is False
    for value in [-1,float('nan'),True]:
        with pytest.raises(ValueError): registry.review(record['id'],edge,dict(height_m=value,notes='Invalid synthetic example'))
    assert len(registry.export()['properties'])==1
    assert len(registry.geojson(record['id'])['features'])==8


def test_map_index_does_not_load_raw_bundles_and_refreshes_on_save(tmp_path,monkeypatch):
    registry=Registry(tmp_path); record=registry.save(build_record(POLYGON,'synthetic',7))
    assert len(registry.collection()['features'])==1
    with monkeypatch.context() as patch:
        patch.setattr(registry,'_index',lambda *a:pytest.fail('Unchanged map must not reread evidence'))
        assert registry.collection()['features'][0]['properties']['segment_count']==8
    registry.save(build_record(POLYGON,'synthetic',8))
    assert len(registry.collection()['features'])==2


def test_native_candidate_is_unknown_not_fence_and_keeps_ground(tmp_path):
    import laspy
    import rasterio
    from pyproj import CRS
    from rasterio.transform import from_origin
    header=laspy.LasHeader(point_format=6,version='1.4'); header.add_crs(CRS.from_user_input('EPSG:2193+7839'))
    cloud=laspy.LasData(header)
    cloud.x=np.r_[np.linspace(0,3,31),-1,6];cloud.y=np.r_[np.zeros(31),-1,6]
    cloud.z=np.r_[np.full(31,1.5),0,0];cloud.classification=np.r_[np.ones(31),2,2].astype('uint8')
    path=tmp_path/'points.laz'; cloud.write(path)
    dem=tmp_path/'dem.tif'
    with rasterio.open(dem,'w',driver='GTiff',height=10,width=10,count=1,dtype='float32',crs=2193,transform=from_origin(-2,8,1,1)) as dst:
        dst.write(np.zeros((10,10),dtype='float32'),1);dst.update_tags(vertical_datum='NZVD2016')
    evidence=PointEvidence(path,dem); stats,candidates=evidence.evidence(LineString([(0,0),(4,0)]),1,'test')
    assert stats['usable_return_count']==31
    assert len(candidates)==1 and candidates[0]['type']=='unknown'
    assert candidates[0]['height_estimate_p95_m']==pytest.approx(1.5)
    building=gpd.GeoDataFrame(geometry=[Polygon([(-1,-1),(4,-1),(4,1),(-1,1)])],crs=2193)
    Evidence({'buildings':building},cloud=evidence)
    assert evidence.evidence(LineString([(0,0),(4,0)]),1,'test')[1]==[]
    cloud.classification=np.r_[np.full(31,5),2,2].astype('uint8');cloud.write(path)
    assert PointEvidence(path,dem).evidence(LineString([(0,0),(4,0)]),1,'test')[1]==[]


def test_registry_http_csrf_geometry_and_exports(tmp_path):
    registry=Registry(tmp_path); record=registry.save(build_record(POLYGON,'synthetic',7))
    server=make_server(tmp_path,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port)
    try:
        assert len(requests.get(url+'/api/properties',timeout=5).json()['features'])==1
        assert len(requests.get(url+'/api/properties/'+record['id']+'/boundaries',timeout=5).json()['features'])==8
        endpoint=url+'/api/properties/'+record['id']+'/segments/'+record['boundary_segments'][0]['id']+'/review'
        payload=dict(type='wall',notes='Offline synthetic API fixture, not an actual wall')
        assert requests.post(endpoint,json=payload,timeout=5).status_code==403
        token=requests.get(url+'/api/bootstrap',timeout=5).json()['csrf']
        response=requests.post(endpoint,json=payload,headers={'X-Floodtwin-Token':token},timeout=5)
        assert response.status_code==200
        assert requests.get(url+'/api/properties/export',timeout=5).json()['properties'][0]['boundary_segments'][0]['structure']['type']=='wall'
    finally: server.shutdown();server.server_close();thread.join(timeout=3)


def test_native_export_preserves_noise_flags_and_all_dimensions(tmp_path):
    import hashlib
    import laspy
    from pyproj import CRS
    registry=Registry(tmp_path); path=registry.folder/'raw/native/pointcloud.laz'
    path.parent.mkdir(parents=True)
    header=laspy.LasHeader(point_format=6,version='1.4');header.add_crs(CRS.from_user_input('EPSG:2193+7839'))
    cloud=laspy.LasData(header);cloud.x=[.1,1.1,10.1];cloud.y=[.1,1.1,10.1];cloud.z=[1,2,3]
    cloud.classification=[2,7,1];cloud.withheld=[0,1,0];cloud.intensity=[11,22,33];cloud.write(path)
    record=build_record(Polygon([(0,0),(2,0),(2,2),(0,2)]),'synthetic',8,
        evidence=Evidence(assets=[dict(name='native/pointcloud.laz',sha256=hashlib.sha256(path.read_bytes()).hexdigest())]))
    registry.save(record); result=registry.point_export(record['id'])
    assert result['count']==2 and result['point_attributes']['classification']==[2,7]
    assert result['point_attributes']['withheld']==[0,1]
    assert result['point_attributes']['intensity']==[11,22]
    assert set(result['point_attributes'])==set(header.point_format.dimension_names)
    assert all(len(v)==2 for v in result['point_attributes'].values())
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='source changed'): registry.point_export(record['id'])


@pytest.mark.parametrize('empty',[False,True])
def test_source_batches_are_complete_and_empty_is_verified(tmp_path,monkeypatch,empty):
    from floodtwin.providers import civic
    calls=[]
    def query(url,params=None):
        calls.append(params)
        if not url.endswith('/query'):
            return dict(type='Feature Layer',geometryType='esriGeometryPolyline',maxRecordCount=2000,
                        objectIdField='OBJECTID',fields=[dict(name='OBJECTID',type='esriFieldTypeOID')])
        if params.get('returnIdsOnly'): return dict(objectIds=None if empty else list(range(125)))
        if params.get('returnCountOnly'): return dict(count=0)
        ids=[int(v) for v in params['objectIds'].split(',')]
        assert len(ids)<=60
        return dict(spatialReference={'wkid':2193},features=[dict(attributes=dict(OBJECTID=v),geometry=dict(paths=[[[0,0],[1,1]]])) for v in ids])
    monkeypatch.setattr(civic,'get',query)
    report=civic.fetch_vector(dict(id='test',title='Synthetic',url='https://example.test/0',queryUrl='https://example.test/0/query'),[0,0,1,1],tmp_path)
    assert report['status']==('available_empty' if empty else 'available')
    assert report['count']==(0 if empty else 125)
    assert len([c for c in calls if c.get('objectIds')])==(0 if empty else 3)
