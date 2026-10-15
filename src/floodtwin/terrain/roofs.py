"""Conservative roof QA. Rejected geometry is not repaired by invented detail."""
import numpy as np
from scipy.spatial import cKDTree, Delaunay, QhullError
from shapely import covers, polygons


def triangulate(points, footprint):
    points = np.asarray(points, dtype=float)
    if len(points)<20:
        return points, np.empty((0,3),dtype=int), dict(rejected_points=0, rejected_triangles=0)
    tree = cKDTree(points[:,:2])
    _, neighbours = tree.query(points[:,:2], k=min(9,len(points)))
    local = points[neighbours[:,1:],2]
    median = np.median(local,axis=1)
    mad = np.median(np.abs(local-median[:,None]),axis=1)
    keep = np.abs(points[:,2]-median)<=np.maximum(1.5,6*mad)
    rejected = int((~keep).sum())
    points = points[keep]
    if len(points)<20:
        return points, np.empty((0,3),dtype=int), dict(rejected_points=rejected,rejected_triangles=0)
    try:
        triangles = Delaunay(points[:,:2]).simplices
    except QhullError:
        return points, np.empty((0,3),dtype=int), dict(rejected_points=rejected, rejected_triangles=0)
    xyz = points[triangles]
    lengths = np.stack([np.linalg.norm(xyz[:,a,:2]-xyz[:,b,:2],axis=1) for a,b in [(0,1),(1,2),(2,0)]],axis=1)
    shapes = polygons(xyz[:,:,:2])
    # Entire triangle must lie within footprint, including concavities and holes.
    valid = covers(footprint, shapes)&(lengths.max(axis=1)<2)&(np.ptp(xyz[:,:,2],axis=1)<2)
    return points, triangles[valid], dict(rejected_points=rejected,rejected_triangles=int((~valid).sum()))
