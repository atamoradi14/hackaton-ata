"""Local crossed-edge detection with native evidence and an explicit visual-QA gate.

This is conservative geometry/class screening, not a trained fence/wall model.
No network, model API, hydraulic inference or changes to raw property records.
"""
import copy
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from shapely import contains_xy, points
from shapely.geometry import LineString, MultiPoint, box, mapping, shape
from shapely.ops import unary_union

from ..properties import PointEvidence, Registry, atomic, gis, identifier, read, stamp
from .classifications import height_label
from .predictions import BOUNDARY_FIELDS

VERSION='native-crossing-corridors-v2'
LIMITATIONS=[
    'Unvalidated local LiDAR-class/geometry detector, not a trained semantic fence/wall model',
    'Native vegetation/roof heights are return envelopes above a 1 m DEM, not fence/wall crests',
    'Planting, shadows, airborne occlusion and source age differences hide small objects',
    'Fitted return envelopes are approximate GIS locations, not surveyed extents or physical thickness',
    'Aerial QA does not replace four oblique views, street-level evidence or field verification',
    'Material, buried depth, hydraulic permeability and risk remain unresolved without evidence']


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def crossed(record,pilot):
    if record.get('pilot')!=pilot: return []
    return [e for e in record['boundary_segments'] if e['flow_path'].get('crossed_by_flow_path') is True]


def classification(row,type_score,height_score,basis):
    row['classifications']=dict(version=1,confidence_scale='0_to_1',
        confidence_method='detector_evidence_heuristic_uncalibrated',calibrated=False,score_basis=basis,
        type=dict(label='occluded_or_unresolved' if row['type']=='unknown' else row['type'],confidence_score=type_score),
        height=dict(label=height_label(row),confidence_score=height_score,value_m=row['height_m'],
            range_m=row['height_range_m'],basis=row.get('height_basis')))
    return row


def fields(row):
    assessments={}
    for key in BOUNDARY_FIELDS:
        value=row[key]
        supported=value not in (None,'unknown','uncertain')
        basis={
            'type':row['rationale'],
            'height_m':row.get('height_basis') or 'No single defensible physical crest for this corridor.',
            'material':'Native classes/overhead imagery do not resolve construction material.',
            'width_m':'Observed point spread/envelope is not measured physical thickness.',
            'depth_m':'Buried/embedment depth cannot be observed.',
            'continuity':'Return gaps may be airborne occlusion; continuous physical fabric not established.',
            'permeability':'No measured hydraulic porosity or reliable exposed fabric.',
            'potential_influence':'No verified obstruction or hydraulic calculation.',
            'crossed_by_flow_path':'Original Council GIS relation; not inferred from images.',
            'risk_level':'Not assessed; no hydraulic risk calculation.'}[key]
        assessments[key]=dict(status='mapped_screening' if key=='crossed_by_flow_path' else 'estimated' if supported else 'unknown',
            confidence='medium' if supported else 'not_assessed',basis=basis,
            source_ids=['native_lidar','native/dem.tif'] if key in {'type','height_m'} and supported else
                ['ac-overland-flow-paths'] if key=='crossed_by_flow_path' else [])
    for field,key in [('type','type'),('height_m','height')]:
        assessments[field]['confidence_score']=row['classifications'][key]['confidence_score']
    row['field_assessments']=assessments
    return row


def proposal(entity_id,kind,type_,reason,height=None,spread=None,score=0,height_score=0):
    row=dict(entity_id=entity_id,entity_kind=kind,status='unreviewed_prediction',method='local_crossing_detection',
        confidence='low',type=type_,material=None,height_m=height,height_range_m=spread,width_m=None,depth_m=None,
        continuity='unknown',permeability='unknown',potential_influence='uncertain',crossed_by_flow_path=None,
        risk_level=None,rationale=reason,not_for_hydraulics=True,height_range_kind='observed_return_spread_not_confidence_interval')
    if height is not None:
        row['height_basis']='p95 of selected native '+type_+' returns minus co-located verified NZVD2016 1 m DEM; local observed envelope, not a surveyed fence, wall, eave or whole-object height'
    return fields(classification(row,score,height_score,reason+' Scores are uncalibrated evidence-rule judgments, not measured accuracy.'))


def detect(cloud,edge):
    """Separate classified roofs/vegetation from ambiguous low linear returns."""
    coords=sorted(edge['endpoints_nztm']);line=LineString(coords);a,b=np.asarray(coords)
    direction=(b-a)/line.length;normal=np.array([-direction[1],direction[0]])
    ids=cloud.near(line,1.0);ids=ids[cloud.valid[ids]&np.isfinite(cloud.heights[ids])]
    h=cloud.heights[ids];xy=np.column_stack([cloud.x[ids],cloud.y[ids]])
    along=(xy-a)@direction;across=(xy-a)@normal
    bounded=(along>=0)&(along<=line.length)&(h>=-.5)&(h<=40)
    classes=cloud.cls[ids]
    vegetation=bounded&np.isin(classes,[3,4,5])&(h>=.3)
    building=bounded&(classes==6)&(h>=.5)
    low=bounded&np.isin(classes,[0,1])&(h>=.25)&(h<=4)
    if cloud.building_mask is not None and low.any():
        low &= ~contains_xy(cloud.building_mask,xy[:,0],xy[:,1])
    objects=[];rows=[]
    for kind,mask in [('vegetation',vegetation),('building',building),('unknown',low)]:
        selected=np.flatnonzero(mask)
        if len(selected)<12: continue
        bins=np.floor(along[selected]/.5).astype(int)
        occupied=np.unique(bins)
        for run in np.split(occupied,np.where(np.diff(occupied)>2)[0]+1):
            group=selected[np.isin(bins,run)]
            start,end=float(along[group].min()),float(along[group].max())
            if len(group)<12 or end-start<(.75 if kind!='unknown' else 1.5): continue
            span=float(np.percentile(across[group],95)-np.percentile(across[group],5))
            occupancy=len(run)/(int(run[-1]-run[0])+1)
            if kind=='unknown' and (span>1.0 or occupancy<.65): continue
            geometry=MultiPoint(xy[group]).convex_hull.intersection(line.buffer(1))
            if geometry.is_empty: continue
            key=identifier('detected',[VERSION,edge['id'],kind,int(run[0]),int(run[-1])])
            intervals=np.round(np.percentile(h[group],[10,50,95]),2).tolist()
            reason=('Native classified '+kind+' returns occupy this boundary corridor; exact boundary coincidence/ownership and hidden fabric are not established.' if kind!='unknown' else
                'Narrow connected low unclassified returns outside mapped buildings: possible small structure, vegetation, vehicle or clutter. Fence versus wall is unresolved.')
            score=.8 if kind=='building' else .75 if kind=='vegetation' else 0
            row=proposal(key,'object',kind,reason,intervals[2],[intervals[0],intervals[2]],score,.45 if len(group)>=30 else .3)
            stats=dict(usable_return_count=len(group),class_counts=dict(Counter(map(str,classes[group].tolist()))),
                height_p10_p50_p95_m=intervals,along_start_m=start,along_end_m=end,
                observed_lateral_spread_m=span,occupied_half_m_bin_fraction=occupancy)
            row['native_evidence']=stats;rows.append(row)
            objects.append(dict(id=key,parent_edge_id=edge['id'],source_id='native_lidar',
                candidate_kind='classified_return_cluster' if kind!='unknown' else 'linear_above_ground_returns',
                evidence_status='local_detection_unverified',position_status='native_return_envelope_not_surveyed_object',
                geometry=gis(geometry),projected_geometry=mapping(geometry),type=kind,native_semantic_class=kind,
                limitations=LIMITATIONS,native_evidence=stats))
    kinds={r['type'] for r in rows};resolved=kinds-{'unknown'}
    type_='mixed' if len(kinds)>1 else next(iter(resolved)) if resolved else 'unknown'
    reason=('Corridor contains '+', '.join(sorted(kinds))+'. Types describe detected adjacent return groups, not one continuous barrier.' if rows else
        'No supported above-ground object cluster resolved in the sampled corridor; not proof of no fence, wall or gate.')
    parent=proposal(edge['id'],'boundary_segment',type_,reason,score=.65 if type_=='mixed' else .75 if type_!='unknown' else 0,
        height_score=.5 if type_=='mixed' else 0)
    parent['crossed_by_flow_path']=True;parent['flow_relation']=edge['flow_path']['relation']
    parent['detected_object_ids']=[o['id'] for o in objects]
    parent['native_evidence']=dict(usable_return_count=len(ids),outside_height_qc_count=int((~bounded).sum()),
        coverage_fraction=float(line.intersection(cloud.bounds).length/line.length),
        classes=dict(Counter(map(str,classes.tolist()))),height_qc_m=[-.5,40],corridor_half_width_m=1,
        excluded_noise_classes=[7,18],withheld_excluded=True)
    parent['coverage']='partial_aerial_and_native_only';fields(parent)
    return dict(edge_id=edge['id'],edge=edge,parent=parent,objects=objects,entities=rows),dict(
        xy=xy,along=along,height=h,classes=classes)


def prepare(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import rasterio
    from rasterio.windows import from_bounds
    root=Path(root);registry=Registry(root);manifest=read(registry.folder/'import-manifest.json')
    records=[read(p) for p in sorted((registry.folder/'properties').glob('property_*.json'))]
    selected=[r for r in records if crossed(r,manifest['pilot'])]
    unique={e['id']:e for r in selected for e in crossed(r,manifest['pilot'])}
    native=registry.folder/'raw/native'
    source_hashes={n:digest(native/n) for n in ['pointcloud.laz','dem.tif','aerial.tif']}
    algorithm_sha256=digest(Path(__file__))
    run_id=identifier('detection',[VERSION,algorithm_sha256,manifest['pilot'],source_hashes,sorted(unique)])
    out=registry.folder/'crossing-detection-runs'/run_id;out.mkdir(parents=True,exist_ok=True)
    # Preserve the exact detector implementation alongside the run for reproducibility.
    import shutil
    shutil.copyfile(__file__,out/'detector.py')
    cloud=PointEvidence(native/'pointcloud.laz',native/'dem.tif')
    buildings={o['id']:shape(o['projected_geometry']) for r in selected for o in r['objects']
        if o['source_id'] in {'linz-building-outlines','buildings'}}
    cloud.building_mask=unary_union(list(buildings.values())).buffer(.25)
    cases=[];evidence=[];edge_items=sorted(unique.items());atlas=[]
    with rasterio.open(native/'aerial.tif') as aerial:
        if aerial.crs.to_epsg()!=2193: raise ValueError('Verified EPSG:2193 aerial required')
        for offset in range(0,len(edge_items),12):
            fig=plt.figure(figsize=(20,17));grid=fig.add_gridspec(8,3,hspace=.6,wspace=.15)
            page=offset//12+1
            for local,(eid,edge) in enumerate(edge_items[offset:offset+12]):
                case,raw=detect(cloud,edge);code='E'+str(offset+local+1).zfill(3);case['code']=code
                case['atlas_page']=page;case['atlas_file']=f'atlas-{page:02d}.png'
                col=local%3;row=(local//3)*2
                ax=fig.add_subplot(grid[row,col]);profile=fig.add_subplot(grid[row+1,col])
                line=LineString(edge['endpoints_nztm']);bounds=line.bounds
                # Orient each aerial corridor along the edge, at native 7.5 cm sampling.
                # This exposes thin details instead of shrinking a long diagonal into a tiny square.
                from scipy.ndimage import map_coordinates
                a,b=np.asarray(sorted(edge['endpoints_nztm']));direction=(b-a)/line.length
                normal=np.array([-direction[1],direction[0]])
                u,v=np.meshgrid(np.arange(-2,line.length+2,.075),np.arange(4,-4,-.075))
                wx=a[0]+u*direction[0]+v*normal[0];wy=a[1]+u*direction[1]+v*normal[1]
                bounds=(float(wx.min())-.1,float(wy.min())-.1,float(wx.max())+.1,float(wy.max())+.1)
                window=from_bounds(*bounds,aerial.transform).round_offsets().round_lengths()
                image=aerial.read([1,2,3],window=window,boundless=True,fill_value=0)
                transform=aerial.window_transform(window)
                cols=(wx-transform.c)/transform.a-.5;rows=(wy-transform.f)/transform.e-.5
                strip=np.stack([map_coordinates(band,[rows,cols],order=1,mode='constant',cval=0) for band in image],axis=-1)
                ax.imshow(strip,extent=[-2,line.length+2,-4,4],aspect='auto')
                ax.plot([0,line.length],[0,0],color='#ffda36',lw=.65,alpha=.8)
                for match in edge['flow_path'].get('matches',[]):
                    if match.get('relation')=='crosses' and match.get('intersection'):
                        from .crossing_export import projected
                        p=projected(dict(geometry=match['intersection']))
                        if p.geom_type=='Point': ax.plot((np.array([p.x,p.y])-a)@direction,0,'o',mfc='none',mec='#00ffff',ms=7)
                ax.set_xticks([]);ax.set_yticks([])
                ax.set_title(code+' | '+case['parent']['type']+' | '+str(round(line.length,1))+' m',fontsize=10)
                for cls,color,label in [([2],'#927044','ground'),([6],'#a74be0','building'),([3,4,5],'#187443','vegetation'),([0,1],'#777777','other')]:
                    mask=np.isin(raw['classes'],cls)&(raw['height']>=-.5)&(raw['height']<35)
                    profile.scatter(raw['along'][mask],raw['height'][mask],s=1,c=color,label=label,rasterized=True)
                profile.set_xlim(0,line.length);profile.set_ylim(-.5,max(4,min(25,float(np.nanpercentile(raw['height'],99))+1)) if len(raw['height']) else 4)
                profile.tick_params(labelsize=7);profile.set_xlabel('Along edge (m)',fontsize=8);profile.set_ylabel('Above DEM (m)',fontsize=8)
                cases.append(case)
            fig.suptitle(f'Crossed pilot boundaries | page {page} | aerial + native class profiles | not verified fences/walls\nYellow cadastral line; cyan mapped crossing; ground brown, roof purple, vegetation green, unclassified grey',fontsize=12)
            path=out/f'atlas-{page:02d}.png';fig.savefig(path,dpi=110,bbox_inches='tight');plt.close(fig)
            atlas.append(dict(page=page,file=path.name,sha256=digest(path),edge_codes=[c['code'] for c in cases if c['atlas_page']==page]))
            print(f'Prepared page {page}: {len(cases)}/{len(unique)} distinct crossed edges',flush=True)
    report=dict(run_id=run_id,version=VERSION,algorithm_sha256=algorithm_sha256,pilot=manifest['pilot'],created_at=stamp(),source_hashes=source_hashes,
        source_assets=selected[0]['raw_assets'],coordinate_systems=dict(horizontal='EPSG:2193',vertical='NZVD2016'),
        properties=[dict(id=r['id'],property_sha256=digest(registry._path(r['id'])),input_revision=r.get('input_revision'),
            crossing_edge_ids=[e['id'] for e in crossed(r,manifest['pilot'])]) for r in selected],
        scope='crossed_boundaries_only',properties_count=len(selected),crossed_boundary_records=sum(len(crossed(r,manifest['pilot'])) for r in selected),
        distinct_crossed_edges=len(unique),atlas=atlas,cases=cases,limitations=LIMITATIONS,
        google_views_acquired=False,accuracy_validated=False)
    atomic(out/'evidence.json',report)
    return dict(run_id=run_id,properties=len(selected),crossed_boundary_records=report['crossed_boundary_records'],
        distinct_edges=len(unique),objects=sum(len(c['objects']) for c in cases),
        types=dict(Counter(c['parent']['type'] for c in cases)),atlas_pages=len(atlas))


def validate(record,bundle):
    if bundle.get('method')!='local_crossing_detection' or bundle.get('scope')!='crossed_boundaries_only':
        raise ValueError('Crossed-only local detector contract required')
    if bundle.get('property_id')!=record['id'] or bundle.get('property_sha256')!=hashlib.sha256(
        json.dumps(record,sort_keys=True,default=str).encode()).hexdigest():
        raise ValueError('Detector property snapshot mismatch')
    eligible={e['id'] for e in crossed(record,bundle['pilot'])}
    rows=bundle['entities'];edge_rows=[r for r in rows if r['entity_kind']=='boundary_segment']
    if {r['entity_id'] for r in edge_rows}!=eligible or len(edge_rows)!=len(eligible):
        raise ValueError('Every crossed pilot boundary, and no non-crossed boundary, must be assessed')
    objects={o['id']:o for o in bundle['inferred_objects']}
    if len(objects)!=len(bundle['inferred_objects']) or {r['entity_id'] for r in rows}!=eligible|objects.keys() or len(rows)!=len(eligible)+len(objects):
        raise ValueError('Detection entity IDs must be exact and unique')
    for obj in objects.values():
        if obj['parent_edge_id'] not in eligible: raise ValueError('Object attached to non-crossed boundary')
        geometry=shape(obj['projected_geometry']);parent=next(e for e in record['boundary_segments'] if e['id']==obj['parent_edge_id'])
        if not geometry.is_valid or geometry.is_empty or not LineString(parent['endpoints_nztm']).buffer(1.01).covers(geometry):
            raise ValueError('Detected geometry must lie in its observed boundary corridor')
        if shape(gis(geometry)).hausdorff_distance(shape(obj['geometry']))>1e-7:
            raise ValueError('Detected object GIS coordinates disagree')
    for row in rows:
        if set(row.get('field_assessments',{}))!=BOUNDARY_FIELDS or row.get('risk_level') is not None or row.get('depth_m') is not None:
            raise ValueError('All fields assessed; unsupported buried depth/risk prohibited')
        for field in ['type','height']:
            score=row['classifications'][field]['confidence_score']
            if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=1:
                raise ValueError('Invalid numeric evidence confidence')
        if row['classifications']['height']['label']!=height_label(row): raise ValueError('Height class mismatch')
    return bundle


def publish(root,run_id,review_path):
    """Publish only after the atlas is actually inspected and hash-bound reviewed."""
    root=Path(root);registry=Registry(root);out=registry.folder/'crossing-detection-runs'/run_id
    evidence=read(out/'evidence.json');review=read(review_path)
    if review.get('run_id')!=run_id or review.get('evidence_sha256')!=digest(out/'evidence.json'):
        raise ValueError('Review must match the exact evidence run')
    if set(review.get('reviewed_atlas_sha256',[]))!={p['sha256'] for p in evidence['atlas']} or not review.get('limitations'):
        raise ValueError('Every atlas page needs an explicit hash-bound review')
    cases={c['edge_id']:c for c in evidence['cases']};pending=[]
    for source in evidence['properties']:
        pid=source['id'];path=registry._path(pid)
        if digest(path)!=source['property_sha256']: raise ValueError('Property changed since detection: '+pid)
        record=read(path);entities=[];objects=[]
        for eid in source['crossing_edge_ids']:
            case=copy.deepcopy(cases[eid]);parent=case['parent']
            parent['evidence_image']=dict(path=str((out/case['atlas_file']).relative_to(root)),atlas_page=case['atlas_page'],edge_code=case['code'])
            if case['code'] in review.get('edge_notes',{}): parent['atlas_review_note']=review['edge_notes'][case['code']]
            semantic=review.get('visual_type_reviews',{}).get(case['code'])
            if semantic:
                # Explicitly authored local-image judgments, not automatic fence labels.
                matches=[r for r in case['entities'] if r['type']==semantic['native_type']]
                if len(matches)!=1 or semantic['type']!='hedge' or not semantic.get('reason'):
                    raise ValueError('Visual type refinement requires one identified native vegetation cluster')
                row=matches[0];row['type']='hedge';row['material']='vegetation'
                row['rationale']=semantic['reason'];row['visual_semantic_review']=semantic
                row['classifications']['type'].update(label='hedge',confidence_score=semantic['confidence_score'],
                    confidence_method='assistant_subjective_uncalibrated',basis=semantic['reason'])
                fields(row);row['field_assessments']['type']['source_ids'].append('native/aerial.tif')
                row['field_assessments']['material'].update(status='estimated',confidence='medium',
                    basis='Visible foliage and vegetation-classified returns; underlying hard fence/material remains unknown.',source_ids=['native/aerial.tif','native_lidar'])
                next(o for o in case['objects'] if o['id']==row['entity_id'])['type']='hedge'
                if parent['type']=='vegetation':
                    parent['type']='hedge';parent['rationale']=semantic['reason']+' The detected planting is not proof of a continuous barrier on the cadastral line.'
                    parent['classifications']['type'].update(label='hedge',confidence_score=semantic['confidence_score'],
                        confidence_method='assistant_subjective_uncalibrated',basis=semantic['reason'])
                    fields(parent)
            visual=review.get('image_only_components',{}).get(case['code'])
            if visual:
                if visual['type']!='fence' or not visual.get('reason'): raise ValueError('Authored visual component required')
                cid=identifier('image_component',[run_id,eid,visual['type']])
                component=proposal(cid,'object','fence',visual['reason'],score=visual['confidence_score'])
                component.update(id=cid,parent_edge_id=eid,geometry=None,projected_geometry=None,
                    position_status='relative_image_position_only',position_note=visual['position_note'],
                    alternatives=visual['alternatives'],source_ids=['native/aerial.tif',case['atlas_file']],
                    image_only=True,not_for_hydraulics=True)
                parent['components']=[component]
                parent['type']='fence' if parent['type']=='unknown' else 'mixed'
                parent['rationale']=visual['reason']+' Native corridor statistics do not establish this barrier height or exact GIS alignment.'
                classification(parent,visual['confidence_score'],.5 if parent['type']=='mixed' else 0,parent['rationale'])
                fields(parent)
            entities.append(parent);entities.extend(case['entities']);objects.extend(case['objects'])
        bundle=dict(method='local_crossing_detection',scope='crossed_boundaries_only',api_used=False,pilot=evidence['pilot'],
            property_id=pid,property_sha256=hashlib.sha256(json.dumps(record,sort_keys=True,default=str).encode()).hexdigest(),
            input_revision=record.get('input_revision'),created_at=stamp(),run_id=run_id,version=VERSION,
            independently_verified=False,hydraulic=False,confidence_calibrated=False,accuracy_validated=False,
            atlas_review=review,source_hashes=evidence['source_hashes'],sources_used=evidence['source_assets'],
            limitations=evidence['limitations'],entities=entities,inferred_objects=objects)
        validate(record,bundle);pending.append((pid,bundle))
    for pid,bundle in pending:
        path=registry.folder/'crossing-detections'/(pid+'.json')
        if path.exists():
            archive=registry.folder/'prediction-history'/pid/('detection-'+digest(path)+'.json')
            if not archive.exists(): atomic(archive,read(path))
        atomic(path,bundle)
    summary=dict(run_id=run_id,published_at=stamp(),properties=len(pending),
        crossed_boundary_records=sum(len(p['crossing_edge_ids']) for p in evidence['properties']),
        distinct_crossed_edges=len(cases),detected_object_records=sum(len(b['inferred_objects']) for p,b in pending),
        parent_types=dict(Counter(r['type'] for p,b in pending for r in b['entities'] if r['entity_kind']=='boundary_segment')),
        object_types=dict(Counter(r['type'] for p,b in pending for r in b['entities'] if r['entity_kind']=='object')),
        non_crossed_boundaries_modified=0,raw_property_records_modified=0,manual_reviews_modified=0,accuracy_validated=False)
    atomic(out/'published.json',summary)
    return summary
