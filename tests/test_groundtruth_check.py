"""Synthetic evaluation guardrails; these do not establish detector accuracy."""
import pytest
from shapely.geometry import LineString

from floodtwin.validation.groundtruth_check import has_assessment, spatial_agreement


def test_missing_assessment_is_not_a_negative():
    assert not has_assessment({})
    assert not has_assessment(dict(Landscape_Structure=None,Fence_Wall_Obstruction=None))
    assert not has_assessment(dict(Landscape_Structure='  '))
    assert has_assessment(dict(Fence_Wall_Obstruction=0))  # Explicit recorded None severity.
    assert has_assessment(dict(Landscape_Structure='None'))


def test_spatial_agreement_is_tolerance_sensitive_and_not_a_class_score():
    line=LineString([(0,0),(10,0)])
    parallel=LineString([(0,1),(10,1)])
    assert spatial_agreement(line,[parallel],.5)['reference_length_covered_fraction']==0
    assert spatial_agreement(line,[parallel],1.1)['reference_length_covered_fraction']==pytest.approx(1)
    assert spatial_agreement(line,[parallel],1.1)['nearest_prediction_distance_m']==1


def test_duplicate_objects_cannot_inflate_spatial_coverage():
    line=LineString([(0,0),(10,0)]);prediction=LineString([(0,0),(4,0)])
    single=spatial_agreement(line,[prediction],.1)
    assert spatial_agreement(line,[prediction,prediction],.1)==single
    assert single['reference_length_covered_fraction']==pytest.approx(.41)
    assert single['matches_at_least_half_reference'] is False


def test_no_geolocated_predictions_does_not_invent_a_distance():
    result=spatial_agreement(LineString([(0,0),(10,0)]),[],1)
    assert result['nearest_prediction_distance_m'] is None
    assert result['reference_length_covered_fraction']==0
