"""Saved-data-only Mt Albert boundary/OLFP object inventory; not hydraulics."""
import re
import hashlib
import threading
from collections import Counter
from pathlib import Path

from shapely.geometry import LineString, box, shape, mapping
from shapely.ops import transform, unary_union

from ..properties import read,stamp,identifier,TO_NZTM,gis,atomic,clean

SOURCE_TYPES={
    'buildings':'building','linz-building-outlines':'building','ac-stormwater-fence':'fence',
    'fences':'fence','ac-kerblines':'kerb','ac-stormwater-pipe':'pipe','pipes':'pipe',
    'ac-stormwater-catchpit':'catchpit','catchpits':'catchpit',
    'ac-stormwater-manhole':'manhole','manholes':'manhole','ac-stormwater-inlet-outlet':'inlet_outlet'}
FLOW_SOURCES={'ac-overland-flow-paths','overland_flow'}
_CACHE={}
_CACHE_LOCK=threading.Lock()


def import_obstructions(registry,path):
    """Retain supplied obstruction geometry/attributes without inventing a type."""
    import pyogrio
    path=Path(path);layer='AC_OLFP_obstructions_20261016'
    frame=pyogrio.read_dataframe(path,layer=layer)
    if frame.crs is None or frame.crs.to_epsg()!=2193:
        raise ValueError('Expected supplied obstruction data in EPSG:2193')
    fingerprints={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.iterdir()) if p.is_file()}
    source=dict(id='provided-olfp-obstructions',title=layer,source_file=path.name,
        file_sha256=fingerprints,crs='EPSG:2193',capture_date=None,license='Supplied project data; restrictions not independently verified',
        status='locally_available',imported_at=stamp(),feature_count=len(frame))
    objects=[]
    for index,row in frame.iterrows():
        geometry=row.geometry
        if geometry is None or geometry.is_empty or not geometry.is_valid:
            raise ValueError('Invalid supplied obstruction geometry at row '+str(index))
        attrs=clean(row.drop(labels=frame.geometry.name).to_dict())
        key=attrs.get('GlobalID') or str(index)
        objects.append(dict(id=identifier('feature',[source['id'],key]),source_id=source['id'],
            source_feature_id=key,source_attributes=attrs,source=source,
            candidate_kind='mapped_obstruction',evidence_status='source_feature_not_physically_verified',
            geometry=gis(geometry),projected_geometry=mapping(geometry)))
    value=dict(source=source,objects=objects)
    atomic(registry.folder/'raw/supplemental/olfp-obstructions.json',value)
    return dict(features=len(objects),source_id=source['id'])


def cached_export(registry):
    """Reuse a snapshot only while all atomic registry/review inputs are unchanged."""
    folder=registry.folder
    paths=[folder/name for name in ['properties','reviews','object-reviews','predictions','crossing-detections','import-manifest.json',
        'raw/supplemental/olfp-obstructions.json']]
    signature=tuple((str(p),p.stat().st_mtime_ns if p.exists() else None) for p in paths)
    with _CACHE_LOCK:
        if _CACHE.get('signature')!=signature:
            value=export_crossings(registry)
            _CACHE.update(signature=signature,value=value)
        return _CACHE['value']


def attributes(entity):
    """Manual review wins; stale assistant labels never become effective values."""
    prediction=entity.get('prediction') or {};structure=entity.get('structure') or {}
    fresh=prediction and not prediction.get('stale') and prediction.get('status')!='not_applicable'
    if entity.get('review'):
        value=structure;kind='manual_review';label=value.get('type','unknown');score=None
    elif fresh:
        value=prediction;kind='local_detector_prediction' if prediction.get('method')=='local_crossing_detection' else 'assistant_prediction';label=value.get('type','unknown')
        score=(value.get('classifications') or {}).get('type',{}).get('confidence_score')
    elif entity.get('source_id') in SOURCE_TYPES:
        value={};kind='source_layer_type';label=SOURCE_TYPES[entity['source_id']];score=None
    else:
        value={};kind='unclassified';label='unknown';score=None
    if label in {'unknown','mapped_context','concealed_possible_fence','occluded'}:
        kind='unclassified';score=None;label='unknown'
    height_class=(value.get('classifications') or {}).get('height',{})
    return dict(type=label,type_status=kind,type_confidence=score,
        height_m=value.get('height_m'),height_class=height_class.get('label'),
        height_confidence=height_class.get('confidence_score'),
        material=value.get('material'),width_m=value.get('width_m'),depth_m=value.get('depth_m'),
        continuity=value.get('continuity'),permeability=value.get('permeability'),
        potential_influence=value.get('potential_influence'),risk=entity.get('risk'),
        classifications=value.get('classifications'),prediction_stale=bool(prediction.get('stale')),
        confidence_calibrated=False,review=entity.get('review'),structure=entity.get('structure'),
        prediction=entity.get('prediction'))


def projected(entity):
    if entity.get('projected_geometry'): return shape(entity['projected_geometry'])
    if entity.get('geometry'): return transform(TO_NZTM,shape(entity['geometry']))
    return None


def in_scope(record,manifest):
    if manifest.get('pilot') and record.get('pilot')==manifest['pilot']: return True
    if re.search(r'\bmount\s+albert\b',record.get('address') or '',re.I): return True
    bounds=manifest.get('bounds_nztm')
    geometry=projected(record)
    return bool(bounds and geometry is not None and geometry.intersects(box(*bounds)))


def export_crossings(registry):
    manifest=read(registry.folder/'import-manifest.json',{})
    boundaries=[];objects={};properties=[];errors=[];skipped=0;context_links=0
    coverage=Counter();types=Counter();sources={};areas={}
    supplemental=read(registry.folder/'raw/supplemental/olfp-obstructions.json',{})
    extra_objects=supplemental.get('objects',[])
    extra_geometry=[projected(o) for o in extra_objects]
    from shapely.strtree import STRtree
    extra_index=STRtree(extra_geometry)
    paths=sorted((registry.folder/'properties').glob('property_*.json'))
    for path in paths:
        try:
            record=registry.get(path.stem)
            if not in_scope(record,manifest): skipped+=1;continue
        except (ValueError,KeyError,TypeError) as error:
            errors.append(dict(property_id=path.stem,error=str(error)));continue
        pid=record['id'];edges=record['boundary_segments'];tolerance=record['proximity_tolerance_m']
        crossing_edges=[e for e in edges if e['flow_path'].get('crossed_by_flow_path') is True]
        coverage['properties_in_scope']+=1;coverage['boundary_edges_in_scope']+=len(edges)
        coverage['flow_unknown_edges']+=sum(e['flow_path'].get('crossed_by_flow_path') is None for e in edges)
        properties.append(dict(id=pid,address=record.get('address'),workspace_id=record.get('workspace_id'),
            source_id=record['source_id'],source_feature_id=record['source_feature_id'],
            geometry=record['geometry'],crossing_boundary_count=len(crossing_edges),
            boundary_count=len(edges),proximity_tolerance_m=tolerance,
            input_revision=record.get('input_revision'),updated_at=record.get('updated_at')))
        if not crossing_edges: continue
        coverage['properties_with_crossings']+=1
        for name,source in record.get('sources',{}).items():
            sources.setdefault(name,dict(id=name,url=source.get('url'),title=source.get('title'),
                capture_date=source.get('capture_date'),license=source.get('license'),status=source.get('status')))
            if source.get('bounds_nztm'):
                key=tuple(source['bounds_nztm']);areas.setdefault(key,set()).add(name)
        originals={o['id']:o for o in record['objects']}
        inferred={o['id']:o for o in record.get('prediction_objects',[])}
        flows=[o for o in originals.values() if o.get('source_id') in FLOW_SOURCES]
        for number,edge in enumerate(edges,1):
            if edge['flow_path'].get('crossed_by_flow_path') is not True: continue
            line=LineString(edge['endpoints_nztm']);flow=edge['flow_path']
            matches=[m for m in flow.get('matches',[]) if m.get('relation')=='crosses']
            intersections=[transform(TO_NZTM,shape(m['intersection'])) for m in matches if m.get('intersection')]
            crossing=unary_union(intersections) if intersections else None
            matched_flows=[projected(o) for o in flows if any(o.get('source_id')==m.get('source_id') and o.get('source_attributes')==m.get('source_attributes') for m in matches)]
            flow_geometry=unary_union(matched_flows) if matched_flows else None
            refs={r['object_id']:r for r in edge.get('nearby_objects',[])}
            for index in extra_index.query(line.buffer(tolerance),predicate='intersects'):
                obj=extra_objects[index];originals[obj['id']]=obj;refs[obj['id']]=dict(object_id=obj['id'])
                source=supplemental['source'];sources.setdefault(source['id'],source)
            for oid,obj in inferred.items():
                geometry=projected(obj)
                if geometry is not None and geometry.distance(line)<=tolerance: refs[oid]=dict(object_id=oid)
            linked=[]

            def add(obj,origin,object_key):
                oid=identifier('crossing_object',[pid,origin,object_key])
                if oid not in objects:
                    objects[oid]=dict(id=oid,object_id=object_key,property_id=pid,
                        address=record.get('address'),kind=origin,source_id=obj.get('source_id'),
                        source_feature_id=obj.get('source_feature_id'),source_attributes=obj.get('source_attributes'),
                        source=obj.get('source'),geometry=obj.get('geometry'),projected_geometry=obj.get('projected_geometry'),
                        position_status=obj.get('position_status'),position_note=obj.get('position_note'),
                        candidate_kind=obj.get('candidate_kind'),evidence_status=obj.get('evidence_status'),
                        limitations=obj.get('limitations'),notes=obj.get('notes'),associations=[],**attributes(obj))
                geometry=projected(obj)
                relation=dict(boundary_id=edge['id'],boundary_number=number,parent_boundary_crossed_by_flow=True,
                    crossing_distance_m=float(geometry.distance(crossing)) if geometry is not None and crossing is not None else None,
                    proximity_tolerance_m=tolerance,
                    near_boundary_crossing=bool(geometry.distance(crossing)<=tolerance) if geometry is not None and crossing is not None else None,
                    object_intersects_mapped_flow=bool(geometry.intersects(flow_geometry)) if geometry is not None and flow_geometry is not None else None,
                    object_properly_crosses_mapped_flow=bool(geometry.crosses(flow_geometry)) if geometry is not None and flow_geometry is not None else None,
                    relation_status='geometry_checked' if geometry is not None and flow_geometry is not None else 'linked_to_crossing_boundary_only')
                objects[oid]['associations'].append(relation);linked.append(oid)

            for oid in sorted(refs):
                obj=originals.get(oid) or inferred.get(oid)
                if obj is None: continue
                pred=obj.get('prediction') or {}
                physical=obj.get('candidate_kind') or obj.get('source_id') in SOURCE_TYPES or (pred.get('status')=='unreviewed_prediction' and pred.get('type') not in {'unknown','mapped_context'}) or obj.get('review')
                if obj.get('source_id') in FLOW_SOURCES or not physical:
                    context_links+=1;continue
                add(obj,'recorded_object',oid)
            for index,component in enumerate((edge.get('prediction') or {}).get('components',[]),1):
                # Components have relative positions; no geometry/crossing is invented.
                obj=dict(component,source_id='assistant_image_component',prediction=dict(component,
                    status='unreviewed_prediction',stale=edge['prediction'].get('stale',False)))
                add(obj,'boundary_component',component.get('id') or edge['id']+':component:'+str(index))
            values=attributes(edge)
            boundaries.append(dict(property_id=pid,address=record.get('address'),boundary_id=edge['id'],
                boundary_number=number,geometry=edge['geometry'],endpoints_nztm=edge['endpoints_nztm'],
                length_m=edge['length_m'],is_hole=edge.get('is_hole',False),
                flow_path=flow,crossing_geometry=gis(crossing) if crossing is not None else None,
                crossing_geometry_nztm=mapping(crossing) if crossing is not None else None,
                object_ids=linked,**values))
            coverage['classified_crossing_boundaries' if values['type_status']!='unclassified' else 'unclassified_crossing_boundaries']+=1
    for obj in objects.values(): types[obj['type']]+=1
    rows=list(objects.values())
    crossing_object_ids=[o['id'] for o in rows if any(a['near_boundary_crossing'] is True and
        a['object_intersects_mapped_flow'] is True for a in o['associations'])]
    return dict(schema_version=1,created_at=stamp(),region='mt-albert',hydraulic=False,
        scope=dict(label='Available Mt Albert / Sandringham pilot and confirmed Mount Albert properties',
            complete_suburb_inventory=False,administrative_suburb_boundary_verified=False,
            membership='Recorded project pilot, confirmed address containing Mount Albert, or parcel intersecting pilot bounds',
            pilot=manifest.get('pilot'),pilot_bounds_nztm=manifest.get('bounds_nztm'),
            recorded_properties_total=len(paths),excluded_outside_scope=skipped,
            supplemental_obstruction_source=supplemental.get('source'),
            source_coverage_areas=[dict(bounds_nztm=list(b),source_ids=sorted(names)) for b,names in sorted(areas.items())]),
        coordinate_systems=dict(geometry='OGC:CRS84 longitude/latitude',projected_geometry='EPSG:2193 metres',
            elevation='No new Z or height measurements generated'),
        selection=dict(boundaries='proper crosses only; touching, overlapping and nearby paths excluded',
            objects='Physical/source asset candidates and image components linked to crossing boundaries',
            object_identity='Property-scoped object records; same source feature may occur at adjacent properties',
            crossing_object_ids='Objects whose saved geometry intersects a matched mapped flow AND is within the boundary-crossing tolerance',
            near_crossing='Distance to boundary/flow intersection <= recorded proximity tolerance; not proof of physical obstruction'),
        summary=dict(coverage,crossing_boundaries=len(boundaries),objects=len(rows),object_types=dict(sorted(types.items())),
            classified_objects=sum(o['type_status']!='unclassified' for o in rows),
            unclassified_objects=sum(o['type_status']=='unclassified' for o in rows),
            objects_near_crossing=sum(any(a['near_boundary_crossing'] is True for a in o['associations']) for o in rows),
            objects_intersecting_flow_at_crossing=len(crossing_object_ids),
            objects_with_unresolved_location=sum(o['geometry'] is None for o in rows),
            nonphysical_context_links_excluded=context_links,read_errors=len(errors)),
        properties=properties,crossed_boundaries=boundaries,objects=rows,crossing_object_ids=crossing_object_ids,
        sources=list(sources.values()),errors=errors,
        limitations=['Available recorded data, not a complete inventory of every Mt Albert property or object',
            'A crossing cadastral boundary is not a measured fence or wall',
            'Parent boundary crossing does not establish that each linked object is crossed by water',
            'Unknown/stale classifications remain explicit; no regionwide AI classifications were generated',
            'Council mapped paths and 2D asset intersections are screening evidence, not actual water motion or flood risk'])
