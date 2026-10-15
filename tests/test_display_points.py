"""Small synthetic point crop: all usable classes survive native display."""
import inspect

import laspy
import numpy as np

from floodtwin.terrain.display_points import presentation


def test_full_density_preserves_sparse_objects_and_ground(tmp_path):
    cloud=laspy.LasData(laspy.LasHeader(point_format=6,version='1.4'))
    cloud.x=np.arange(9,dtype=float)
    cloud.y=np.arange(9,dtype=float)+10
    cloud.z=np.arange(9,dtype=float)+20
    cloud.classification=np.array([1,2,3,4,5,6,7,18,1],dtype='uint8')
    cloud.withheld=np.array([0,0,0,0,0,0,0,0,1],dtype='uint8')
    cloud.overlap=np.array([1,0,0,0,0,0,0,0,0],dtype='uint8')
    cloud.write(tmp_path/'pointcloud_crop.laz')
    value=presentation(tmp_path,{'nztm':[0,10]})
    assert inspect.signature(presentation).parameters['limit'].default is None
    assert value['sampling_stride']==1 and value['full_density']
    assert value['raw_count']==9 and value['source_count']==value['display_count']==6
    assert value['classification']==[1,2,3,4,5,6]
    assert value['excluded_count']==3
    assert value['points'][0]==[0,0,20]  # unclassified overlap return retained
    assert value['points'][1]==[1,1,21]  # actual ground preserved, not DEM replacement
    assert value['class_counts']=={str(c):1 for c in range(1,7)}


def test_no_usable_returns_fail_clearly(tmp_path):
    cloud=laspy.LasData(laspy.LasHeader(point_format=6,version='1.4'))
    cloud.x=[0];cloud.y=[0];cloud.z=[0];cloud.classification=[7]
    cloud.write(tmp_path/'pointcloud_crop.laz')
    import pytest
    with pytest.raises(ValueError,match='No usable LiDAR'):
        presentation(tmp_path,{'nztm':[0,0]})
