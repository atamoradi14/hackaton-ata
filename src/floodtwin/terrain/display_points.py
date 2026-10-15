"""Bounded classified LiDAR display; source elevations remain unchanged."""
import json
import laspy
import numpy as np
from PIL import Image


def presentation(folder,site,limit=None):
    cloud=laspy.read(folder/'pointcloud_crop.laz')
    cls=np.asarray(cloud.classification)
    valid=~np.asarray(cloud.withheld,dtype=bool)&~np.isin(cls,[7,18])
    indices=np.flatnonzero(valid)
    # The bounded local crop is lossless by default. Global every-Nth sampling
    # can erase sparse fences/low structures while leaving dense trees intact.
    stride=max(1,int(np.ceil(len(indices)/limit))) if limit else 1
    indices=indices[::stride]
    east=np.asarray(cloud.x)[indices];north=np.asarray(cloud.y)[indices]
    z=np.asarray(cloud.z)[indices];classes=cls[indices]
    x,y=site['nztm']
    # Classification palette is the honest fallback when no orthophoto is present.
    palette=np.array([[169,180,183]]*256,dtype='uint8')
    palette[2]=[164,155,126];palette[3:6]=[68,121,78];palette[6]=[186,194,201]
    colors=palette[classes].copy()
    aerial=folder/'scene-aerial.json'
    color_source='LAS classification'
    if aerial.exists() and (folder/'scene-aerial.jpg').exists():
        meta=json.loads(aerial.read_text());west,south,east_edge,north_edge=meta['bounds_nztm']
        image=np.asarray(Image.open(folder/'scene-aerial.jpg').convert('RGB'))
        rows=np.floor((north_edge-north)/(north_edge-south)*image.shape[0]).astype(int)
        cols=np.floor((east-west)/(east_edge-west)*image.shape[1]).astype(int)
        inside=(rows>=0)&(rows<image.shape[0])&(cols>=0)&(cols<image.shape[1])
        colors[inside]=image[rows[inside],cols[inside]]
        color_source='Recorded LINZ orthophoto sampled by NZTM coordinates; acquisition dates may differ from LiDAR'
    if not len(indices):
        raise ValueError('No usable LiDAR returns in the local crop')
    manifest=folder/'pointcloud-manifest.json'
    crop_bounds=json.loads(manifest.read_text()).get('bounds_nztm') if manifest.exists() else None
    counts,numbers=np.unique(cls[valid],return_counts=True)
    return dict(points=np.round(np.column_stack([east-x,north-y,z]),3).tolist(),
                classification=classes.tolist(),colors=colors.tolist(),sampling_stride=stride,
                source_count=int(valid.sum()),display_count=len(indices),color_source=color_source,
                raw_count=len(cls),excluded_count=int((~valid).sum()),
                excluded_reason='Withheld or LAS noise classes 7/18 only; overlap and unclassified returns retained',
                class_counts={str(int(c)):int(n) for c,n in zip(counts,numbers)},
                crop_bounds_nztm=crop_bounds,full_density=stride==1,
                bounds_local=[float(east.min()-x),float(north.min()-y),float(east.max()-x),float(north.max()-y)],
                synthetic=False,datum='NZVD2016')
