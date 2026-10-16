import pytest
from floodtwin.features.classifications import annotate,validate,height_label


def test_numeric_classes_preserve_estimate_and_keep_scores_separate():
    row=dict(type='hedge',height_m=2.34,height_range_m=[1.79,2.75],height_basis='Synthetic native envelope')
    annotate(row,.9,.55,'Synthetic subjective fixture')
    assert row['classifications']['type']['label']=='hedge'
    assert row['classifications']['height']['label']=='2_to_3_m'
    assert row['classifications']['height']['value_m']==2.34
    assert row['classifications']['height']['confidence_score']==.55
    assert row['classifications']['calibrated'] is False


def test_variable_and_occlusion_are_classes_not_fabricated_heights():
    mixed=annotate(dict(type='mixed',height_m=None),.75,.65,'Synthetic mixed corridor')
    assert mixed['classifications']['height']['label']=='variable_height'
    assert mixed['height_m'] is None
    hidden=annotate(dict(type='unknown',height_m=None),0,0,'Synthetic occluded slot')
    assert hidden['classifications']['type']['label']=='occluded_or_unresolved'
    with pytest.raises(ValueError): annotate(dict(type='unknown'),.8,0,'Synthetic unsupported physical type')


@pytest.mark.parametrize('score',[True,-.1,1.1,float('nan'),float('inf'),'90'])
def test_bad_numeric_confidence_rejected(score):
    with pytest.raises(ValueError): annotate(dict(type='hedge',height_m=2),score,.5,'Synthetic fixture')


def test_inconsistent_class_and_exact_boundaries():
    assert height_label(dict(height_m=2))=='2_to_3_m'
    assert height_label(dict(height_m=3))=='3_to_5_m'
    assert height_label(dict(height_m=10))=='10_m_or_more'
    row=annotate(dict(type='hedge',height_m=2),.9,.5,'Synthetic fixture')
    row['classifications']['height']['label']='5_to_10_m'
    with pytest.raises(ValueError,match='contradicts'): validate(row)
