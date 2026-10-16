"""Offline synthetic crossed-only detector contracts, not accuracy validation."""
import copy
import hashlib
import json
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Polygon, box

from floodtwin.features.crossing_detection import crossed, detect, proposal, validate, digest, publish
from floodtwin.features.crossing_export import attributes, export_crossings
from floodtwin.properties import Evidence, Registry, atomic, build_record

X,Y=1753200,5916000


def fixture(tmp_path):
    polygon=Polygon([(X,Y),(X+10,Y),(X+10,Y+10),(X,Y+10)])
    flows=gpd.GeoDataFrame({'OBJECTID':[1]},geometry=[LineString([(X+5,Y-2),(X+5,Y+2)])],crs=2193)
    record=build_record(polygon,'synthetic',1,evidence=Evidence({'overland_flow':flows}))
    record['pilot']='synthetic';registry=Registry(tmp_path);registry.save(record)
    record=json.loads(registry._path(record['id']).read_text())
    return registry,record


def fake_cloud():
    count=80
    x=np.r_[np.linspace(.1,4.9,count),np.linspace(5.1,9.9,count)]
    y=np.r_[np.full(count,.2),np.full(count,.1)]
    return SimpleNamespace(x=x+X,y=y+Y,heights=np.r_[np.full(count,2),np.full(count,1)],
        cls=np.r_[np.full(count,5),np.full(count,1)],valid=np.ones(2*count,dtype=bool),
        near=lambda *a:np.arange(2*count),bounds=box(X,Y-1,X+10,Y+1),building_mask=None)


def bundle(record,case):
    return dict(property_id=record['id'],pilot='synthetic',method='local_crossing_detection',scope='crossed_boundaries_only',
        property_sha256=hashlib.sha256(json.dumps(record,sort_keys=True,default=str).encode()).hexdigest(),
        entities=[case['parent'],*case['entities']],inferred_objects=case['objects'],
        sources_used=[dict(source='synthetic fixture')],limitations=['Synthetic contract fixture'])


def test_native_groups_are_not_invented_fences_or_walls(tmp_path):
    _,record=fixture(tmp_path);case,_=detect(fake_cloud(),crossed(record,'synthetic')[0])
    assert case['parent']['type']=='mixed'
    assert {r['type'] for r in case['entities']}=={'vegetation','unknown'}
    vegetation=next(r for r in case['entities'] if r['type']=='vegetation')
    unknown=next(r for r in case['entities'] if r['type']=='unknown')
    assert vegetation['height_m']==2 and 'local observed envelope' in vegetation['height_basis']
    assert unknown['classifications']['type']['confidence_score']==0
    assert all(r['risk_level'] is None and r['depth_m'] is None for r in case['entities'])
    assert not any(r['type'] in {'fence','wall','retaining_wall'} for r in case['entities'])
    validate(record,bundle(record,case))


def test_no_usable_returns_is_unknown_not_open_or_no_objects(tmp_path):
    _,record=fixture(tmp_path);cloud=fake_cloud();cloud.valid[:]=False
    case,_=detect(cloud,crossed(record,'synthetic')[0])
    assert case['objects']==[] and case['parent']['type']=='unknown'
    assert case['parent']['height_m'] is None
    assert case['parent']['classifications']['type']['confidence_score']==0
    assert 'not proof' in case['parent']['rationale']


def test_building_mask_excludes_ambiguous_low_points(tmp_path):
    _,record=fixture(tmp_path);cloud=fake_cloud();cloud.building_mask=box(X+5,Y-1,X+10,Y+1)
    case,_=detect(cloud,crossed(record,'synthetic')[0])
    assert {r['type'] for r in case['entities']}=={'vegetation'}


def test_validator_rejects_non_crossed_edges_and_bad_scores(tmp_path):
    _,record=fixture(tmp_path);case,_=detect(fake_cloud(),crossed(record,'synthetic')[0]);value=bundle(record,case)
    noncrossed=next(e for e in record['boundary_segments'] if not e['flow_path']['crossed_by_flow_path'])
    bad=copy.deepcopy(value);bad['entities'].append(proposal(noncrossed['id'],'boundary_segment','unknown','Synthetic'))
    with pytest.raises(ValueError,match='no non-crossed'): validate(record,bad)
    bad=copy.deepcopy(value);bad['entities'][0]['classifications']['type']['confidence_score']=float('nan')
    with pytest.raises(ValueError,match='confidence'): validate(record,bad)
    assert crossed(record,'another-pilot')==[]


def test_registry_merges_only_crossed_edges_and_preserves_raw_manual_and_staleness(tmp_path):
    registry,record=fixture(tmp_path);original=registry._path(record['id']).read_bytes()
    case,_=detect(fake_cloud(),crossed(record,'synthetic')[0]);value=validate(record,bundle(record,case))
    atomic(registry.folder/'crossing-detections'/(record['id']+'.json'),value)
    updated=registry.get(record['id']);eligible={e['id'] for e in crossed(record,'synthetic')}
    assert {e['id'] for e in updated['boundary_segments'] if e.get('prediction')}==eligible
    assert len(updated['prediction_objects'])==2
    for edge in updated['boundary_segments']:
        if edge['id'] not in eligible: assert edge==next(e for e in record['boundary_segments'] if e['id']==edge['id'])
    assert updated['detection_bundle']['stale'] is False
    registry.review(record['id'],case['parent']['entity_id'],dict(type='wall',notes='Synthetic manual review'))
    reviewed=registry.get(record['id'])['boundary_segments'][0]
    assert attributes(reviewed)['type']=='wall' and reviewed['prediction']['type']=='mixed'
    assert registry._path(record['id']).read_bytes()==original
    raw=copy.deepcopy(record);raw['input_revision']='changed';atomic(registry._path(raw['id']),raw)
    stale=registry.get(raw['id'])['boundary_segments'][0]
    assert stale['prediction']['stale'] is True


def test_export_includes_new_objects_but_not_false_water_claims(tmp_path):
    registry,record=fixture(tmp_path);case,_=detect(fake_cloud(),crossed(record,'synthetic')[0])
    atomic(registry.folder/'crossing-detections'/(record['id']+'.json'),validate(record,bundle(record,case)))
    atomic(registry.folder/'import-manifest.json',dict(pilot='synthetic',bounds_nztm=[X,Y,X+10,Y+10]))
    result=export_crossings(registry)
    assert result['summary']['crossing_boundaries']==1 and result['summary']['objects']==2
    assert result['crossed_boundaries'][0]['type_status']=='local_detector_prediction'
    assert all(o['prediction']['method']=='local_crossing_detection' for o in result['objects'])
    assert result['hydraulic'] is False


def test_publication_requires_exact_review_and_keeps_image_only_objects_unlocated(tmp_path):
    from PIL import Image
    registry,record=fixture(tmp_path);original=registry._path(record['id']).read_bytes()
    case,_=detect(fake_cloud(),crossed(record,'synthetic')[0]);case.update(code='E001',atlas_file='atlas-01.png',atlas_page=1)
    run_id='detection_'+'a'*24;out=registry.folder/'crossing-detection-runs'/run_id;out.mkdir(parents=True)
    Image.new('RGB',(12,12),'white').save(out/'atlas-01.png')
    report=dict(run_id=run_id,pilot='synthetic',properties=[dict(id=record['id'],property_sha256=digest(registry._path(record['id'])),
        crossing_edge_ids=[case['edge_id']])],atlas=[dict(sha256=digest(out/'atlas-01.png'))],cases=[case],
        source_hashes={'synthetic':'fixture'},source_assets=[{'source':'synthetic'}],limitations=['Offline fixture'])
    atomic(out/'evidence.json',report)
    review=dict(run_id=run_id,evidence_sha256=digest(out/'evidence.json'),reviewed_atlas_sha256=[],limitations=['Synthetic'])
    atomic(out/'review.json',review)
    with pytest.raises(ValueError,match='Every atlas'): publish(tmp_path,run_id,out/'review.json')
    assert not (registry.folder/'crossing-detections').exists()
    review['reviewed_atlas_sha256']=[digest(out/'atlas-01.png')]
    review['visual_type_reviews']={'E001':dict(native_type='vegetation',type='hedge',confidence_score=.7,reason='Synthetic hedge annotation, not actual imagery')}
    review['image_only_components']={'E001':dict(type='fence',confidence_score=.5,reason='Synthetic ambiguous fence-like fixture',
        position_note='Relative position only',alternatives=['wall'])}
    atomic(out/'review.json',review)
    summary=publish(tmp_path,run_id,out/'review.json')
    assert summary['crossed_boundary_records']==1 and summary['properties']==1
    live=registry.get(record['id']);parent=next(e for e in live['boundary_segments'] if e.get('detection'))
    assert parent['prediction']['components'][0]['geometry'] is None
    assert parent['prediction']['components'][0]['crossed_by_flow_path'] is None
    assert next(o for o in live['prediction_objects'] if o['prediction']['type']=='hedge')['prediction']['material']=='vegetation'
    assert registry._path(record['id']).read_bytes()==original
    publish(tmp_path,run_id,out/'review.json')
    assert len(list((registry.folder/'prediction-history'/record['id']).glob('detection-*.json')))==1
