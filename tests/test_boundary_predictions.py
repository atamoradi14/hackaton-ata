import pytest
from shapely.geometry import Polygon, mapping

from floodtwin.properties import Registry, build_record, gis


def fixture(tmp_path):
    registry=Registry(tmp_path)
    record=build_record(Polygon([(1750000,5910000),(1750010,5910000),(1750010,5910010),(1750000,5910010)]),'synthetic',1)
    record['input_revision']='revision_1';registry.save(record)
    rows=[dict(entity_id=e['id'],type='hedge',height_m=1.5,height_range_m=[1,2],height_basis='Synthetic fixture only',
          confidence='low',status='unreviewed_prediction',rationale='Offline synthetic fixture, not real Auckland evidence',risk_level=None) for e in record['boundary_segments']]
    bundle=dict(property_id=record['id'],input_revision='revision_1',method='assistant_in_session',api_used=False,
                entities=rows,inferred_objects=[],sources_used=['Synthetic fixture'],limitations=['Not real data'])
    return registry,record,bundle


def test_predictions_separate_from_reviews_survive_rebuild_and_flag_stale(tmp_path):
    registry,record,bundle=fixture(tmp_path);pid=record['id'];edge=record['boundary_segments'][0]['id']
    value=registry.save_predictions(pid,bundle)
    assert value['boundary_segments'][0]['structure']['height_m'] is None
    assert value['boundary_segments'][0]['prediction']['height_m']==1.5
    value=registry.review(pid,edge,dict(type='fence',height_m=1.8,notes='Offline synthetic reviewed evidence'))
    assert value['boundary_segments'][0]['structure']['height_m']==1.8
    assert value['boundary_segments'][0]['prediction']['type']=='hedge'
    registry.save(record)
    assert registry.get(pid)['boundary_segments'][0]['structure']['type']=='fence'
    record['input_revision']='revision_2';registry.save(record)
    assert registry.get(pid)['prediction_bundle']['stale']
    assert registry.get(pid)['boundary_segments'][0]['prediction']['stale']


@pytest.mark.parametrize('change', ['missing_entity','bad_height','risk','wrong_revision','remote'])
def test_prediction_validation_rejects_unsupported_values(tmp_path,change):
    registry,record,bundle=fixture(tmp_path)
    if change=='missing_entity': bundle['entities'].pop()
    elif change=='bad_height': bundle['entities'][0]['height_m']=float('inf')
    elif change=='risk': bundle['entities'][0]['risk_level']='high'
    elif change=='wrong_revision': bundle['input_revision']='other'
    elif change=='remote': bundle['api_used']=True
    with pytest.raises(ValueError): registry.save_predictions(record['id'],bundle)


def test_inferred_object_can_be_reviewed_without_altering_prediction_or_geometry(tmp_path):
    registry,record,bundle=fixture(tmp_path);pid=record['id']
    geometry=Polygon([(1750001,5910001),(1750003,5910001),(1750003,5910003),(1750001,5910003)])
    bundle['inferred_objects']=[dict(id='canopy_synthetic',geometry=gis(geometry),projected_geometry=mapping(geometry),limitations=['Synthetic'])]
    bundle['entities'].append(dict(entity_id='canopy_synthetic',type='vegetation',height_m=None,height_range_m=None,
        confidence='medium',status='unreviewed_prediction',rationale='Synthetic vegetation fixture'))
    value=registry.save_predictions(pid,bundle)
    value=registry.review(pid,'canopy_synthetic',dict(type='vegetation',height_m=3,notes='Synthetic reviewed canopy height'),kind='object')
    obj=value['prediction_objects'][0]
    assert obj['prediction']['height_m'] is None and obj['structure']['height_m']==3
    assert obj['projected_geometry']==mapping(geometry) or obj['projected_geometry']=={'type':'Polygon','coordinates':[[list(v) for v in geometry.exterior.coords]]}
    assert registry.export(pid)['properties'][0]['prediction_bundle']['coverage']['results']==5
    with pytest.raises(ValueError): registry.review(pid,'not-an-object',dict(notes='Synthetic invalid owner'),kind='object')


def test_proposal_outside_property_rejected(tmp_path):
    registry,record,bundle=fixture(tmp_path)
    polygon=Polygon([(0,0),(1,0),(1,1),(0,1)])
    bundle['inferred_objects']=[dict(id='outside',projected_geometry=mapping(polygon),geometry=mapping(polygon),limitations=['Synthetic'])]
    with pytest.raises(ValueError,match='outside'): registry.save_predictions(record['id'],bundle)


def visual_fixture(tmp_path):
    registry,record,bundle=fixture(tmp_path)
    source=dict(id='earth_synthetic',url='https://earth.google.com/web/',status='viewed',
        artifact='output/playwright/synthetic.png',attribution='Synthetic test, no real Google pixels')
    bundle['visual_review']=dict(method='playwright_visual_review',reviewed_at='2026-10-16T00:00:00Z',sources=[source])
    from floodtwin.features.predictions import BOUNDARY_FIELDS
    for row,edge in zip(bundle['entities'],record['boundary_segments']):
        row.update(entity_kind='boundary_segment',material=None,width_m=None,depth_m=None,continuity='unknown',
            permeability='unknown',potential_influence='uncertain',risk_level=None,
            crossed_by_flow_path=edge['flow_path'].get('crossed_by_flow_path'),flow_relation=edge['flow_path']['relation'],
            visual_review=dict(visibility='synthetic_partial',observation='Synthetic only',source_ids=['earth_synthetic']))
        row['field_assessments']={key:dict(status='unknown',confidence='not_assessed',basis='Synthetic unknown field',source_ids=[]) for key in BOUNDARY_FIELDS}
        for key in ['type','height_m']: row['field_assessments'][key].update(status='estimated',confidence='low')
        row['field_assessments']['crossed_by_flow_path'].update(status='mapped_screening',confidence='medium')
    return registry,record,bundle


def test_visual_review_persists_field_confidence_without_changing_original_data(tmp_path):
    registry,record,bundle=visual_fixture(tmp_path)
    saved=registry.save_predictions(record['id'],bundle)
    edge=saved['boundary_segments'][0]
    assert edge['structure']['type']=='unknown'
    assert len(edge['prediction']['field_assessments'])==10
    assert edge['prediction']['material'] is None
    assert not saved['prediction_bundle']['independently_verified']


def test_user_attachment_can_support_review_without_inventing_local_file_or_hash(tmp_path):
    registry,record,bundle=visual_fixture(tmp_path)
    bundle['visual_review']['method']='assistant_multiview_review'
    bundle['visual_review']['sources']=[dict(id='earth_synthetic',source_kind='user_attachment',attachment_index=1,
        conversation_reference='synthetic_test_image_1',attribution='Synthetic fixture, not actual imagery',status='viewed')]
    result=registry.save_predictions(record['id'],bundle)
    assert result['prediction_bundle']['visual_review']['sources'][0].get('sha256') is None
    bundle['visual_review']['sources'][0]['attachment_index']=True
    with pytest.raises(ValueError,match='attachment'): registry.save_predictions(record['id'],bundle)


def test_multiview_revision_preserves_reviews_and_gives_components_explicit_unknowns(tmp_path):
    import hashlib
    from floodtwin.properties import atomic
    from floodtwin.features.sample_evidence import save_visual_sample
    registry,record,bundle=visual_fixture(tmp_path);pid=record['id']
    source=dict(id='earth_synthetic',source_kind='user_attachment',attachment_index=1,
        conversation_reference='synthetic_test_image_1',attribution='Synthetic test only',status='viewed')
    base=registry.folder/'assistant-drafts'/(pid+'.json')
    atomic(base,dict(property_id=pid,evidence_image_sha256='synthetic',edges=bundle['entities']))
    atomic(registry.folder/'sample-evidence'/pid/'evidence.json',dict(input_revision='revision_1',
        evidence_image=dict(sha256='synthetic'),assets=['Synthetic evidence'],
        edges=[dict(id=e['id'],point_evidence={}) for e in record['boundary_segments']],objects=[],vegetation_clusters=[]))
    rows=[]
    for row in bundle['entities']:
        rows.append(dict(row,visual_review=dict(row['visual_review'],confidence_reason='Synthetic corroboration'),
            components=[dict(id=row['entity_id']+'_hedge',type='hedge',confidence='low',source_ids=['earth_synthetic'],notes='Synthetic hedge component')]))
    draft=tmp_path/'synthetic-review.json'
    atomic(draft,dict(property_id=pid,base_draft_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),edge_reviews=rows,
        visual_review=dict(method='assistant_multiview_review',reviewed_at='2026-10-16T00:00:00Z',sources=[source],sources_not_used=[],limitation='Synthetic test only')))
    registry.save_predictions(pid,bundle)
    registry.review(pid,record['boundary_segments'][0]['id'],dict(type='fence',notes='Existing synthetic user decision'))
    value=save_visual_sample(tmp_path,pid,draft)
    assert value['boundary_segments'][0]['structure']['type']=='fence'
    component=value['boundary_segments'][0]['prediction']['components'][0]
    assert component['geometry'] is None and component['depth_m'] is None
    assert component['crossed_by_flow_path'] is None and len(component['field_assessments'])==10
    assert len(list((registry.folder/'prediction-history'/pid).glob('*.json')))==1


@pytest.mark.parametrize('change',['missing_field','failed_source','foreign_source','invented_flow','wrong_kind','asserted_unknown'])
def test_visual_review_rejects_false_evidence_and_incomplete_fields(tmp_path,change):
    registry,record,bundle=visual_fixture(tmp_path);row=bundle['entities'][0]
    if change=='missing_field': row['field_assessments'].pop('material')
    elif change=='failed_source': bundle['visual_review']['sources'][0]['status']='failed'
    elif change=='foreign_source': row['visual_review']['source_ids']=['other_property']
    elif change=='invented_flow': row['crossed_by_flow_path']=True
    elif change=='wrong_kind': row['entity_kind']='object'
    elif change=='asserted_unknown': row['material']='concrete'
    with pytest.raises(ValueError): registry.save_predictions(record['id'],bundle)


def test_object_review_http_requires_csrf_and_preserves_predictions(tmp_path):
    import threading
    import requests
    from floodtwin.api.server import make_server
    registry,record,bundle=fixture(tmp_path);pid=record['id']
    geometry=Polygon([(1750001,5910001),(1750003,5910001),(1750003,5910003),(1750001,5910003)])
    bundle['inferred_objects']=[dict(id='canopy_http',geometry=gis(geometry),projected_geometry=mapping(geometry),limitations=['Synthetic'])]
    bundle['entities'].append(dict(entity_id='canopy_http',type='vegetation',confidence='medium',status='unreviewed_prediction',rationale='Synthetic HTTP fixture'))
    registry.save_predictions(pid,bundle)
    server=make_server(tmp_path,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port);endpoint=url+'/api/properties/'+pid+'/objects/canopy_http/review'
    try:
        payload=dict(type='vegetation',height_m=3,notes='Synthetic API verification only')
        assert requests.post(endpoint,json=payload,timeout=5).status_code==403
        token=requests.get(url+'/api/bootstrap',timeout=5).json()['csrf']
        response=requests.post(endpoint,json=payload,headers={'X-Floodtwin-Token':token},timeout=5)
        assert response.status_code==200
        obj=response.json()['prediction_objects'][0]
        assert obj['structure']['height_m']==3 and obj['prediction'].get('height_m') is None
        result=requests.get(url+'/api/properties/'+pid+'/export',timeout=5).json()['properties'][0]
        assert result['prediction_objects'][0]['structure']['height_m']==3
    finally: server.shutdown();server.server_close();thread.join(timeout=3)
