"""Validate locally authored assistant proposals; no remote model or API calls."""
import math
from urllib.parse import urlparse
from shapely.geometry import shape


BOUNDARY_FIELDS={'type','material','height_m','width_m','depth_m','continuity',
                 'permeability','potential_influence','crossed_by_flow_path','risk_level'}


def validate_visual_review(review,results):
    """Browser observations remain predictions, never measured/field verified data."""
    if not isinstance(review,dict) or review.get('method') not in {'playwright_visual_review','assistant_multiview_review'} or not review.get('reviewed_at'):
        raise ValueError('Dated Playwright visual review required')
    sources=review.get('sources',[])
    ids={s.get('id') for s in sources}
    if not sources or None in ids or len(ids)!=len(sources): raise ValueError('Unique visual sources required')
    for source in sources:
        if source.get('source_kind')=='user_attachment':
            index=source.get('attachment_index')
            if isinstance(index,bool) or not isinstance(index,int) or index<1 or not source.get('conversation_reference') or not source.get('attribution') or source.get('status')!='viewed':
                raise ValueError('Viewed user attachment requires an index, conversation reference and attribution')
            continue
        url=urlparse(source.get('url',''))
        if url.scheme!='https' or url.hostname not in {'earth.google.com','www.google.com','maps.google.com'}:
            raise ValueError('Expected an attributed Google browser view URL')
        if source.get('status')!='viewed' or not source.get('artifact') or not source.get('attribution'):
            raise ValueError('Only successfully viewed attributed sources may support predictions')
    for row in results:
        if row.get('entity_kind')!='boundary_segment': continue
        visual=row.get('visual_review',{})
        if not visual.get('visibility') or not visual.get('observation') or not visual.get('source_ids') or not set(visual['source_ids'])<=ids:
            raise ValueError('Every boundary needs visibility and linked visual evidence')
        fields=row.get('field_assessments',{})
        if set(fields)!=BOUNDARY_FIELDS: raise ValueError('Every boundary field needs an explicit assessment')
        for key,assessment in fields.items():
            if key not in row or not assessment.get('basis') or not set(assessment.get('source_ids',[]))<=ids:
                raise ValueError('Prediction field value, basis and valid sources required')
            if assessment.get('confidence') not in {'low','medium','not_assessed'} or assessment.get('status') not in {'estimated','unknown','mapped_screening'}:
                raise ValueError('Uncalibrated field confidence and explicit status required')
            if assessment['status']=='unknown' and row[key] not in (None,'unknown','uncertain'):
                raise ValueError('Unknown attributes cannot contain asserted physical values')
            if assessment['status']=='mapped_screening' and key!='crossed_by_flow_path':
                raise ValueError('Only mapped flow relationship is a screening field')


def validate(record,bundle):
    if not isinstance(bundle,dict) or bundle.get('property_id')!=record['id']:
        raise ValueError('Prediction property does not match')
    if bundle.get('method')!='assistant_in_session' or bundle.get('api_used') is not False:
        raise ValueError('Only locally authored assistant samples without model API calls accepted here')
    if bundle.get('input_revision')!=record.get('input_revision'):
        raise ValueError('Prediction input revision does not match available evidence')
    ids={e['id'] for e in record['boundary_segments']}|{o['id'] for o in record['objects']}
    original_ids=set(ids)
    polygon=shape(record['projected_geometry']).buffer(2)
    for obj in bundle.get('inferred_objects',[]):
        if obj.get('id') in ids or not isinstance(obj.get('id'),str): raise ValueError('Duplicate prediction object')
        geometry=shape(obj['projected_geometry'])
        if not geometry.is_valid or geometry.is_empty or not polygon.covers(geometry):
            raise ValueError('Inferred sample object outside the property evidence envelope')
        if not obj.get('geometry') or not obj.get('limitations'): raise ValueError('Prediction geometry/provenance required')
        from ..properties import gis
        if shape(gis(geometry)).hausdorff_distance(shape(obj['geometry']))>1e-7:
            raise ValueError('Prediction WGS84 and NZTM geometries disagree')
        ids.add(obj['id'])
    results=bundle.get('entities',[])
    if len({r['entity_id'] for r in results})!=len(results): raise ValueError('Duplicate entity prediction')
    if {r['entity_id'] for r in results}!=ids: raise ValueError('Every recorded/sample entity needs an explicit prediction or not-applicable result')
    for item in results:
        from .classifications import validate as validate_classification
        validate_classification(item)
        for component in item.get('components',[]): validate_classification(component)
        if item.get('status') not in {'unreviewed_prediction','not_applicable'} or not item.get('rationale'):
            raise ValueError('Explicit prediction status and evidence rationale required')
        if item.get('confidence') not in {'low','medium','not_assessed'}:
            raise ValueError('Sample confidences are qualitative and uncalibrated')
        for key in ['height_m','width_m','depth_m']:
            value=item.get(key)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100):
                raise ValueError('Prediction dimensions must be finite nonnegative metres or null')
        interval=item.get('height_range_m')
        if interval is not None and (not isinstance(interval,list) or len(interval)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=100 for v in interval) or interval[0]>interval[1]):
            raise ValueError('Invalid prediction height range')
        if item.get('height_m') is not None and (interval is None or not interval[0]<=item['height_m']<=interval[1] or not item.get('height_basis')):
            raise ValueError('Height estimates require a supporting range and method')
        if item.get('risk_level') is not None: raise ValueError('No unvalidated property flood-risk prediction')
    if not bundle.get('sources_used') or not bundle.get('limitations'):
        raise ValueError('Prediction evidence and limitations required')
    if bundle.get('visual_review'):
        validate_visual_review(bundle['visual_review'],results)
        original_edges={e['id']:e for e in record['boundary_segments']}
        for row in results:
            expected='boundary_segment' if row['entity_id'] in original_edges else 'object'
            if row.get('entity_kind')!=expected: raise ValueError('Visual review entity kind does not match original record')
            if expected=='boundary_segment':
                flow=original_edges[row['entity_id']]['flow_path']
                if row.get('crossed_by_flow_path')!=flow.get('crossed_by_flow_path') or row.get('flow_relation')!=flow['relation']:
                    raise ValueError('Visual predictions must not override the mapped flow relationship')
    return dict(bundle,coverage=dict(recorded_entities=len(original_ids),inferred_objects=len(ids-original_ids),results=len(results)),
                independently_verified=False,hydraulic=False,confidence_calibrated=False)
