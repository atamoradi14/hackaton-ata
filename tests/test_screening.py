import numpy as np
import pytest
from affine import Affine
from floodtwin.hydrology.screening import connectivity


def test_sloping_fixture_area_in_square_metres():
    row,col=np.indices((4,4))
    terrain=(6-row-col).astype("float32")
    target=np.zeros((4,4),dtype=bool); target[-1,-1]=True
    flow,mask,result=connectivity(terrain,Affine(2,0,0,0,-2,8),target)
    assert mask.all()
    assert result["contributing_area_m2"] == 64
    assert result["hydraulic"] is False
    assert result["upstream_reaches_discovery_boundary"] is True


def test_target_on_nodata_fails_closed():
    with pytest.raises(ValueError,match="missing terrain"):
        connectivity(np.full((2,2),-9999),Affine(1,0,0,0,-1,2),np.ones((2,2),dtype=bool))
