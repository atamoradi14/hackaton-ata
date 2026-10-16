"""Explicit type/height labels with separately authored numeric confidence."""
import math

HEIGHT_BINS=((.5,'under_0_5_m'),(1,'0_5_to_1_m'),(2,'1_to_2_m'),
             (3,'2_to_3_m'),(5,'3_to_5_m'),(10,'5_to_10_m'),(math.inf,'10_m_or_more'))


def height_label(row):
    value=row.get('height_m')
    if value is not None:
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100:
            raise ValueError('Height must be finite nonnegative metres')
        return next(label for limit,label in HEIGHT_BINS if value<limit)
    if row.get('type')=='mixed': return 'variable_height'
    if row.get('type')=='mapped_context': return 'not_applicable'
    return 'unresolved'


def annotate(row,type_score,height_score,basis):
    """Label existing evidence; never manufacture a numeric height or map words to scores."""
    if not basis: raise ValueError('Numeric confidence requires an authored rationale')
    type_label=row.get('type') or 'unknown'
    if type_label=='unknown': type_label='occluded_or_unresolved'
    if type_label=='mapped_context': type_label='not_applicable'
    values=dict(type=dict(label=type_label,confidence_score=type_score),
        height=dict(label=height_label(row),confidence_score=height_score,value_m=row.get('height_m'),
                    range_m=row.get('height_range_m'),basis=row.get('height_basis')))
    row['classifications']=dict(version=1,confidence_scale='0_to_1',
        confidence_method='assistant_subjective_uncalibrated',calibrated=False,score_basis=basis,**values)
    for key,label in [('type','type'),('height_m','height')]:
        if key in row.get('field_assessments',{}):
            row['field_assessments'][key]['confidence_score']=values[label]['confidence_score']
    validate(row)
    return row


def validate(row):
    value=row.get('classifications')
    if value is None: return  # earlier stored proposals remain readable
    if value.get('confidence_method')!='assistant_subjective_uncalibrated' or value.get('calibrated') is not False or not value.get('score_basis'):
        raise ValueError('Numeric scores must be attributed, subjective and uncalibrated')
    expected=row.get('type') or 'unknown'
    expected={'unknown':'occluded_or_unresolved','mapped_context':'not_applicable'}.get(expected,expected)
    for key in ['type','height']:
        item=value.get(key,{})
        score=item.get('confidence_score')
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=1:
            raise ValueError('Numeric confidence must be finite between 0 and 1')
        if item.get('label')!=(expected if key=='type' else height_label(row)):
            raise ValueError('Classification label contradicts the evidence value')
        if item['label'] in {'unresolved','occluded_or_unresolved','not_applicable'} and score!=0:
            raise ValueError('Unresolved physical attributes have no positive confidence score')
    if value['height'].get('value_m')!=row.get('height_m') or value['height'].get('range_m')!=row.get('height_range_m'):
        raise ValueError('Height classification must preserve the original numeric estimate/range')
    for field,key in [('type','type'),('height_m','height')]:
        assessment=row.get('field_assessments',{}).get(field)
        if assessment is not None and assessment.get('confidence_score')!=value[key]['confidence_score']:
            raise ValueError('Field and classification confidence scores disagree')


def save_scores(root,pid,review_path):
    """Version-check and archive an explicitly authored scoring review."""
    import hashlib
    from pathlib import Path
    from ..properties import Registry,read,atomic,stamp
    registry=Registry(Path(root));path=registry.folder/'predictions'/(pid+'.json')
    review=read(review_path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if review.get('property_id')!=pid or review.get('prediction_sha256')!=digest:
        raise ValueError('Score review must match this exact saved prediction revision')
    bundle=read(path);edges=[r for r in bundle['entities'] if r['entity_kind']=='boundary_segment']
    if set(review['edges'])!={r['entity_id'] for r in edges}: raise ValueError('Score every original edge exactly')
    for row in edges:
        scores=review['edges'][row['entity_id']]
        annotate(row,scores['type'],scores['height'],scores['basis'])
        for index,component in enumerate(row.get('components',[])):
            key=component.get('id') or 'component_'+str(index+1)
            if key in scores.get('components',{}):
                item=scores['components'][key];annotate(component,item['type'],item['height'],item['basis'])
    bundle['classification_review']=dict(created_at=stamp(),method='assistant_subjective_uncalibrated',
        previous_prediction_sha256=digest,review_sha256=hashlib.sha256(Path(review_path).read_bytes()).hexdigest(),calibrated=False)
    archive=registry.folder/'prediction-history'/pid/(digest+'.json')
    if not archive.exists(): atomic(archive,read(path))
    return registry.save_predictions(pid,bundle)
