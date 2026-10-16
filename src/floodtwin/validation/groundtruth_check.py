"""Read-only coverage audit of saved crossed-edge predictions against a supplied GDB.

Unassessed reference lines are not positives or negatives. Spatial agreement with
such lines is reported separately, never as precision, recall or type accuracy.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

import pyogrio
from shapely.geometry import LineString, box, mapping, shape
from shapely.ops import unary_union

from ..properties import atomic, clean, read, stamp

ASSESSMENT_FIELDS=['Landscape_Structure','Fence_Wall_Obstruction','Contour','Building','Comments_Obstruction']
LAYER='AC_OLFP_obstructions_20261016'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def has_assessment(row):
    # Explicit numeric zero/"None" can be a recorded negative; missing != negative.
    return any(row.get(k) is not None and (not isinstance(row.get(k),str) or bool(row[k].strip()))
        for k in ASSESSMENT_FIELDS)


def spatial_agreement(reference,predictions,tolerance):
    geometry=unary_union(predictions)
    cover=geometry.buffer(tolerance)
    return dict(tolerance_m=tolerance,reference_length_covered_fraction=float(reference.intersection(cover).length/reference.length),
        nearest_prediction_distance_m=float(reference.distance(geometry)) if not geometry.is_empty else None,
        matches_at_least_half_reference=bool(reference.intersection(cover).length/reference.length>=.5))


def evaluate(root,gdb_path):
    from osgeo import gdal
    gdal.UseExceptions()
    root=Path(root);folder=root/'data/property-registry';gdb_path=Path(gdb_path)
    manifest=read(folder/'import-manifest.json');pilot=box(*manifest['bounds_nztm'])
    file_hashes={p.name:digest(p) for p in sorted(gdb_path.iterdir()) if p.is_file()}
    frame=pyogrio.read_dataframe(gdb_path,layer=LAYER)
    if frame.crs is None or frame.crs.to_epsg()!=2193: raise ValueError('Ground truth must be verified EPSG:2193')
    if frame.geometry.isna().any() or frame.geometry.is_empty.any() or not frame.geometry.is_valid.all():
        raise ValueError('Invalid/missing reference geometry; inspect before evaluation')
    source=gdal.OpenEx(str(gdb_path),gdal.OF_VECTOR)
    defn=source.GetLayer(0).GetLayerDefn();domains={}
    for i in range(defn.GetFieldCount()):
        field=defn.GetFieldDefn(i);name=field.GetDomainName()
        if name: domains[field.GetName()]=source.GetFieldDomain(name).GetEnumeration()
    reference=[dict(id=row['GlobalID'],attributes=clean(row.drop(labels=frame.geometry.name).to_dict()),geometry=row.geometry)
        for _,row in frame.iterrows()]
    for item in reference: item['assessed']=has_assessment(item['attributes'])
    prediction_paths=sorted((folder/'crossing-detections').glob('*.json'))
    before={p.name:digest(p) for p in prediction_paths}
    edges={};objects={};images={};bundles=[];property_hashes={}
    for path in prediction_paths:
        bundle=read(path)
        if bundle.get('pilot')!=manifest['pilot']: continue
        bundles.append(bundle);record_path=folder/'properties'/(bundle['property_id']+'.json')
        property_hashes[str(record_path)]=digest(record_path);record=read(record_path)
        expected=hashlib.sha256(json.dumps(record,sort_keys=True,default=str).encode()).hexdigest()
        if bundle.get('property_sha256')!=expected: raise ValueError('Stale prediction: '+bundle['property_id'])
        predicted={e['entity_id']:e for e in bundle['entities']}
        for edge in record['boundary_segments']:
            if edge['id'] not in predicted: continue
            if edge['flow_path'].get('crossed_by_flow_path') is not True: raise ValueError('Non-crossed edge in evaluation')
            edges[edge['id']]=LineString(edge['endpoints_nztm'])
            for comp in predicted[edge['id']].get('components',[]): images[comp['id']]=comp
        for obj in bundle['inferred_objects']:
            if obj.get('source_id')=='provided-olfp-obstructions': raise ValueError('Reference source cannot be counted as a detection')
            objects[obj['id']]=dict(obj,prediction=predicted[obj['id']])
    corridor=unary_union([e.buffer(1) for e in edges.values()])
    tile_rows=[r for r in reference if r['geometry'].intersects(pilot)]
    target_rows=[r for r in reference if r['geometry'].intersects(corridor)]
    assessed=[r for r in reference if r['assessed']]
    labelled=[r for r in target_rows if r['assessed']]
    types=[r for r in target_rows if r['attributes'].get('Landscape_Structure') not in (None,'')]
    original=read(folder/'raw/supplemental/olfp-obstructions.json',{})
    originals={r['source_feature_id']:r for r in original.get('objects',[])}
    geometry_reused=attributes_reused=0
    for row in reference:
        old=originals.get(row['id'])
        if old:
            geometry_reused+=int(shape(old['projected_geometry']).equals(row['geometry']))
            attributes_reused+=int(all(v==old['source_attributes'].get(k) for k,v in row['attributes'].items() if k!='Shape_Length'))
    native=[shape(o['projected_geometry']) for o in objects.values()]
    comparisons=[dict(id=r['id'],attributes=r['attributes'],assessed=r['assessed'],geometry=mapping(r['geometry']),
        spatial_agreement=[spatial_agreement(r['geometry'],native,t) for t in [.5,1.,2.]]) for r in target_rows]
    if labelled:
        raise ValueError('Assessed overlap is present; define explicit truth-label mapping before classification scoring')
    if before!={p.name:digest(p) for p in prediction_paths}: raise ValueError('Predictions changed during evaluation')
    if any(digest(Path(p))!=h for p,h in property_hashes.items()): raise ValueError('Properties changed during evaluation')
    if file_hashes!={p.name:digest(p) for p in sorted(gdb_path.iterdir()) if p.is_file()}:
        raise ValueError('Reference changed during evaluation')
    report=dict(created_at=stamp(),status='not_evaluable_no_assessed_overlap',hydraulic=False,
        reference=dict(layer=LAYER,crs='EPSG:2193',features=len(reference),bounds_nztm=frame.total_bounds.tolist(),file_sha256=file_hashes,
            non_null_counts={c:int(frame[c].notna().sum()) for c in ASSESSMENT_FIELDS},
            assessed_features=len(assessed),field_domains=domains,height_measurement_fields=[],
            nearest_assessed_distance_to_pilot_m=min(r['geometry'].distance(pilot) for r in assessed) if assessed else None),
        prediction=dict(run_ids=sorted({b['run_id'] for b in bundles}),properties=len(bundles),
            crossed_boundary_records=sum(sum(r['entity_kind']=='boundary_segment' for r in b['entities']) for b in bundles),
            distinct_crossed_edges=len(edges),native_object_records=sum(len(b['inferred_objects']) for b in bundles),
            distinct_geolocated_native_objects=len(objects),distinct_image_only_components=len(images),
            unique_native_object_types=dict(Counter(o['prediction']['type'] for o in objects.values())),file_sha256=before),
        overlap=dict(reference_in_pilot=len(tile_rows),assessed_in_pilot=sum(r['assessed'] for r in tile_rows),
            reference_in_crossed_edge_corridors=len(target_rows),assessed_in_crossed_edge_corridors=len(labelled),
            type_labelled_in_crossed_edge_corridors=len(types)),
        independence=dict(reference_geometries_already_in_imported_source=geometry_reused,
            reference_non_length_attributes_identical_to_imported_source=attributes_reused,
            imported_source_features_excluded_from_predictions=True,parent_cadastral_lines_not_counted_as_detected_objects=True,
            image_only_components_excluded_from_spatial_matching=True),
        metrics=dict(type_accuracy=None,detection_precision=None,detection_recall=None,height_mae_m=None,
            obstruction_severity_accuracy=None,eligible_assessed_reference_count=0,
            reason='No assessed reference overlaps this prediction scope. Unassessed features are not positives/negatives; severity codes are not semantic type labels; no dedicated measured-height field exists.'),
        unassessed_reference_geometry_comparison=comparisons,
        limitations=['Spatial envelope/line overlap is location agreement only, NOT detection or type accuracy',
            'No annotated negative coverage or complete object inventory established',
            'GT geometry and attributes were already supplied as source context; copied source records are excluded',
            'Numeric prediction confidence is not empirically validated by this dataset overlap'],
        preservation=dict(prediction_files_unchanged=True,property_files_unchanged=True,reference_files_unchanged=True))
    signature=hashlib.sha256(json.dumps([file_hashes,before],sort_keys=True).encode()).hexdigest()[:16]
    out=folder/'evaluations'/('groundtruth-'+signature);atomic(out/'report.json',report)
    return report,out


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--groundtruth',required=True)
    args=parser.parse_args();result,out=evaluate(args.root,args.groundtruth)
    print(json.dumps(dict(report=str(out/'report.json'),status=result['status'],reference=result['reference']['features'],
        assessed=result['reference']['assessed_features'],overlap=result['overlap'],metrics=result['metrics'],
        spatial_only=[dict(id=r['id'],coverage_at_1m=r['spatial_agreement'][1]['reference_length_covered_fraction'])
            for r in result['unassessed_reference_geometry_comparison']],preservation=result['preservation']),indent=2))
