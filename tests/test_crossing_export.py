"""Offline synthetic export fixtures; no real walls, addresses or flood claims."""
import json
import threading

import geopandas as gpd
import pytest
import requests
from shapely.geometry import LineString, Polygon, shape

from floodtwin.api.server import make_server
from floodtwin.properties import Evidence, Registry, atomic, build_record
from floodtwin.features.crossing_export import attributes, cached_export, export_crossings, import_obstructions

X,Y=1753200,5916000


def line(coords):
    return LineString([(X+x,Y+y) for x,y in coords])


def fixture(tmp_path,objects=True):
    flows=gpd.GeoDataFrame({'OBJECTID':[42]},geometry=[line([(5,-2),(5,12)])],crs=2193)
    layers={'overland_flow':flows}
    if objects:
        layers['fences']=gpd.GeoDataFrame({'OBJECTID':[1,2,3],'source_note':['retained']*3},geometry=[
            line([(4.5,.2),(5.5,.2)]),line([(1,-.2),(1,.2)]),line([(5,-.5),(5,10.5)])],crs=2193)
    record=build_record(Polygon([(X,Y),(X+10,Y),(X+10,Y+10),(X,Y+10)]),
        'synthetic',1,evidence=Evidence(layers),address='Synthetic property, Mount Albert')
    record['input_revision']='v1'
    registry=Registry(tmp_path);registry.save(record)
    atomic(registry.folder/'import-manifest.json',dict(pilot='synthetic',bounds_nztm=[X-1,Y-1,X+11,Y+11]))
    return registry,record


def test_crossings_keep_positions_types_and_separate_object_intersection(tmp_path):
    registry,record=fixture(tmp_path)
    result=export_crossings(registry)
    assert result['summary']['crossing_boundaries']==2
    assert result['summary']['objects']==3
    by_id={o['source_feature_id']:o for o in result['objects']}
    close=by_id['1'];far=by_id['2'];shared=by_id['3']
    assert close['type']=='fence' and close['type_status']=='source_layer_type'
    assert close['type_confidence'] is None  # Not an invented AI confidence for an official layer name.
    assert close['source_attributes']['source_note']=='retained'
    assert close['associations'][0]['object_properly_crosses_mapped_flow'] is True
    assert close['associations'][0]['near_boundary_crossing'] is True
    assert far['associations'][0]['near_boundary_crossing'] is False
    assert far['associations'][0]['object_intersects_mapped_flow'] is False
    assert close['id'] in result['crossing_object_ids'] and far['id'] not in result['crossing_object_ids']
    assert len(shared['associations'])==2  # One object, linked to two edges.
    assert shared['associations'][0]['object_properly_crosses_mapped_flow'] is False  # Overlap != crosses.
    assert len(result['crossed_boundaries'][0]['endpoints_nztm'])==2
    assert shape(result['crossed_boundaries'][0]['crossing_geometry_nztm']).x==pytest.approx(X+5)
    assert result['hydraulic'] is False and not result['scope']['complete_suburb_inventory']
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize('coords',[[(-2,0),(0,0)],[(2,0),(8,0)],[(0,-.5),(10,-.5)]])
def test_touch_overlap_and_nearby_are_not_crossings(tmp_path,coords):
    registry,record=fixture(tmp_path,False)
    record=build_record(shape(record['projected_geometry']),'synthetic',1,
        evidence=Evidence({'overland_flow':gpd.GeoDataFrame(geometry=[line(coords)],crs=2193)}),
        address='Synthetic property, Mount Albert')
    registry.save(record)
    result=export_crossings(registry)
    assert result['summary']['crossing_boundaries']==0 and result['objects']==[]


def test_unknown_edges_retained_and_outside_scope_excluded(tmp_path):
    registry,record=fixture(tmp_path,False)
    outside=build_record(Polygon([(X+100,Y),(X+110,Y),(X+110,Y+10),(X+100,Y+10)]),'synthetic',2)
    registry.save(outside)
    result=export_crossings(registry)
    assert result['summary']['unclassified_crossing_boundaries']==2
    assert result['summary']['objects']==0 and len(result['properties'])==1
    assert result['scope']['excluded_outside_scope']==1


def test_image_component_does_not_inherit_parent_crossing(tmp_path):
    registry,record=fixture(tmp_path,False)
    edge=record['boundary_segments'][0]
    component=dict(id='image-only',type='hedge',height_m=2,classifications=dict(
        type=dict(label='hedge',confidence_score=.7),height=dict(label='2_to_3_m',confidence_score=.4)))
    atomic(registry.folder/'predictions'/(record['id']+'.json'),dict(input_revision='v1',entities=[dict(
        entity_id=edge['id'],type='mixed',status='unreviewed_prediction',components=[component])]))
    result=export_crossings(registry);obj=result['objects'][0]
    assert obj['type']=='hedge' and obj['type_confidence']==.7 and obj['height_confidence']==.4
    assert obj['geometry'] is None and obj['associations'][0]['near_boundary_crossing'] is None
    assert obj['associations'][0]['object_intersects_mapped_flow'] is None
    assert obj['id'] not in result['crossing_object_ids']


def test_manual_review_wins_and_stale_or_concealed_is_not_effective_type():
    prediction=dict(type='wall',height_m=3,stale=False,status='unreviewed_prediction')
    entity=dict(prediction=prediction,structure=dict(type='fence',height_m=1.5),review=dict(notes='Synthetic'))
    result=attributes(entity)
    assert result['type']=='fence' and result['height_m']==1.5 and result['type_confidence'] is None
    assert attributes(dict(prediction=dict(prediction,stale=True)))['type']=='unknown'
    assert attributes(dict(prediction=dict(prediction,type='concealed_possible_fence')))['type_status']=='unclassified'


def test_supplied_obstruction_import_retains_null_types_and_joins_edges(tmp_path,monkeypatch):
    import pyogrio
    registry,record=fixture(tmp_path,False)
    before=registry._path(record['id']).read_bytes()
    path=tmp_path/'AC_OLFP_Obstructions.gdb';path.mkdir();(path/'fixture').touch()
    frame=gpd.GeoDataFrame({'GlobalID':['synthetic-guid'],'Fence_Wall_Obstruction':[None]},
        geometry=[line([(4.5,.2),(5.5,.2)])],crs=2193)
    monkeypatch.setattr(pyogrio,'read_dataframe',lambda *a,**k:frame)
    assert import_obstructions(registry,path)['features']==1
    result=export_crossings(registry);obj=result['objects'][0]
    assert obj['source_id']=='provided-olfp-obstructions' and obj['type']=='unknown'
    assert obj['source_attributes']['Fence_Wall_Obstruction'] is None
    assert obj['associations'][0]['object_intersects_mapped_flow'] is True
    assert result['scope']['supplemental_obstruction_source']['file_sha256']
    assert registry._path(record['id']).read_bytes()==before  # No existing records rewritten.


def test_http_download_and_cache_invalidates_after_review(tmp_path):
    registry,record=fixture(tmp_path,False)
    first=cached_export(registry)
    assert cached_export(registry) is first
    registry.review(record['id'],record['boundary_segments'][0]['id'],dict(type='wall',notes='Synthetic review'))
    assert cached_export(registry)['crossed_boundaries'][0]['type']=='wall'
    server=make_server(tmp_path,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url='http://127.0.0.1:'+str(server.server_port)+'/api/properties/mt-albert-flow-crossings'
        response=requests.get(url,timeout=10)
        assert response.status_code==200 and response.json()['summary']['crossing_boundaries']==2
        assert response.headers['Content-Type'].startswith('application/json')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
