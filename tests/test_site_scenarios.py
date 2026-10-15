import json
import pytest
from floodtwin.hydraulics.site import parameters
from floodtwin.providers.datahub import inspect_catalog


SPEC=dict(reviewed=True,rain_mm_h=50,duration_minutes=30,manning=.03,infiltration_mm_h=0,walls=[])


@pytest.mark.parametrize('update', [dict(reviewed=False),dict(rain_mm_h=-1),dict(rain_mm_h=float('nan')),dict(duration_minutes=True),dict(manning=.001),dict(infiltration_mm_h=100)])
def test_scenarios_require_reviewed_bounded_finite_units(update):
    with pytest.raises(ValueError):parameters(dict(SPEC,**update))


def test_wall_coordinates_cannot_escape_scene_or_claim_measurement():
    for wall in [dict(status='measured',points=[[0,0,50],[10,0,50]]),dict(status='hypothetical',points=[[0,0,50],[10000,0,50]])]:
        with pytest.raises(ValueError):parameters(dict(SPEC,walls=[wall]))
    assert parameters(dict(SPEC,walls=[dict(status='hypothetical',points=[[0,0,50],[10,0,50]])]))['walls']


def test_catalogue_is_not_storm_input(tmp_path):
    path=tmp_path/'catalog.csv'
    path.write_text('productRef,duration,ari,region\nhirds,60,100,Auckland\n')
    result=inspect_catalog(path)
    assert result['rainfall_ready'] is False
    assert result['kind']=='catalogue_metadata'
    assert result['durations_minutes']==[60]
