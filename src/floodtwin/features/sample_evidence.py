"""Offline evidence for assistant-authored samples; this is NOT an AI detector."""
import hashlib
import json
from pathlib import Path

import numpy as np
from shapely import contains_xy, points, covers
from shapely.geometry import LineString, shape, mapping

from ..properties import Registry, PointEvidence, atomic, gis, identifier, read, stamp, record_workspace


def prepare(root, workspace):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    root=Path(root); folder=root/'data/web-sites'/workspace/'data/processed/site'
    registry=Registry(root); site=read(folder/'site_manifest.json')
    record=record_workspace(root,folder,site,workspace)
    polygon=shape(record['projected_geometry'])
    cloud=PointEvidence(folder/'pointcloud_crop.laz',folder/'dem_discovery.tif')
    buildings=[shape(o['projected_geometry']) for o in record['objects'] if o['source_id'] in {'buildings','linz-building-outlines'}]
    building_mask=np.zeros(len(cloud.x),dtype=bool)
    for building in buildings: building_mask |= contains_xy(building,cloud.x,cloud.y)
    def stats(ids):
        ids=np.asarray(ids,dtype=int); good=ids[cloud.valid[ids]]
        result=dict(count=len(good),classes={str(c):int((cloud.cls[good]==c).sum()) for c in np.unique(cloud.cls[good])})
        for name,selected in [('building',good[cloud.cls[good]==6]),('vegetation',good[np.isin(cloud.cls[good],[3,4,5])]),
                              ('low_unclassified_outside_buildings',good[(cloud.cls[good]==1)&~building_mask[good]&(cloud.heights[good]>=.3)&(cloud.heights[good]<=3)])]:
            h=cloud.heights[selected]; h=h[np.isfinite(h)]
            result[name]=dict(count=len(h),height_p10_p50_p95_m=np.round(np.percentile(h,[10,50,95]),2).tolist() if len(h) else None)
        return result
    report=dict(property_id=record['id'],workspace_id=workspace,address=record['address'],created_at=stamp(),
        input_revision=record['input_revision'],method='Evidence extraction, not an AI prediction',
        assets=[a for a in record['raw_assets'] if a['name'] in {'pointcloud_crop.laz','dem_discovery.tif','scene-aerial.jpg','scene-aerial.json','buildings.gpkg'}],
        limitations=['Percentiles of returns are not automatically physical fence heights','Aerial image cannot identify concealed structures/material/depth'],
        google_sources_used=False,edges=[],objects=[])
    for index,edge in enumerate(record['boundary_segments']):
        ids=cloud.near(LineString(edge['endpoints_nztm']),1)
        report['edges'].append(dict(id=edge['id'],index=index+1,endpoints_nztm=edge['endpoints_nztm'],length_m=round(edge['length_m'],2),
            flow_relation=edge['flow_path']['relation'],point_evidence=stats(ids)))
    native_ids=np.flatnonzero(covers(polygon.buffer(1),points(cloud.x,cloud.y)))
    for obj in record['objects']:
        if obj['source_id'] not in {'buildings','linz-building-outlines','native_lidar'}: continue
        geometry=shape(obj['projected_geometry'])
        ids=native_ids[covers(geometry.buffer(.2),points(cloud.x[native_ids],cloud.y[native_ids]))]
        coverage=geometry.intersection(polygon.buffer(1)).area/geometry.area if geometry.area else None
        report['objects'].append(dict(id=obj['id'],source_id=obj['source_id'],source_feature_id=obj.get('source_feature_id'),footprint_coverage_fraction=coverage,point_evidence=stats(ids)))
    # Connected vegetation returns are canopy clusters, NOT individual trees.
    from scipy.ndimage import label
    veg=native_ids[cloud.valid[native_ids]&np.isin(cloud.cls[native_ids],[3,4,5])&(cloud.heights[native_ids]>.5)]
    report['vegetation_clusters']=[]
    if len(veg):
        from shapely.geometry import MultiPoint
        bins=np.floor(np.column_stack([cloud.x[veg],cloud.y[veg]])).astype(int); origin=bins.min(axis=0); local=bins-origin
        cells=np.zeros(tuple(local.max(axis=0)+1),dtype=bool);cells[local[:,0],local[:,1]]=True
        labels,_=label(cells,structure=np.ones((3,3)));groups=labels[local[:,0],local[:,1]]
        for key in np.unique(groups):
            ids=veg[groups==key]
            if len(ids)<30: continue
            hull=MultiPoint(np.column_stack([cloud.x[ids],cloud.y[ids]])).convex_hull
            if hull.geom_type!='Polygon' or hull.area<1: continue
            h=cloud.heights[ids]
            report['vegetation_clusters'].append(dict(id=identifier('vegetation',[record['id'],int(key)]),
                geometry=gis(hull),projected_geometry=mapping(hull),point_count=len(ids),
                height_p10_p50_p95_m=np.round(np.percentile(h,[10,50,95]),2).tolist(),
                area_m2=round(hull.area,2),source_id='native_lidar',
                limitations=['Connected canopy returns may contain several trees/hedges; not an individual-tree inventory']))
    out=registry.folder/'sample-evidence'/record['id'];out.mkdir(parents=True,exist_ok=True)
    meta=read(folder/'scene-aerial.json'); image=np.asarray(Image.open(folder/'scene-aerial.jpg').convert('RGB'))
    extent=meta.get('bounds_nztm')
    if extent is None: raise ValueError('Recorded aerial extent required')
    west,south,east,north=extent
    b=polygon.bounds; margin=12
    limits=[b[0]-margin,b[2]+margin,b[1]-margin,b[3]+margin]
    fig,axes=plt.subplots(1,2,figsize=(16,10),layout='constrained')
    axes[0].imshow(image,extent=[west,east,south,north],origin='upper')
    ids=native_ids[cloud.valid[native_ids]&np.isfinite(cloud.heights[native_ids])]
    axes[1].scatter(cloud.x[ids],cloud.y[ids],c=cloud.heights[ids],s=1,cmap='turbo',vmin=0,vmax=15,rasterized=True)
    for ax in axes:
        for index,edge in enumerate(record['boundary_segments']):
            a,b=np.array(edge['endpoints_nztm']);ax.plot([a[0],b[0]],[a[1],b[1]],color='#ffec56',lw=1.5)
            centre=(a+b)/2;ax.text(*centre,str(index+1),color='black',fontsize=11,weight='bold',ha='center',va='center',bbox=dict(facecolor='#ffec56',edgecolor='black',pad=2))
        ax.set_xlim(limits[:2]);ax.set_ylim(limits[2:]);ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(axis='x',rotation=35)
        ax.set_xlabel('Easting EPSG:2193 (m)');ax.set_ylabel('Northing EPSG:2193 (m)')
    axes[0].set_title('Recorded LINZ aerial + original numbered parcel edges')
    axes[1].set_title('Native returns coloured by height above 1 m DEM (0–15 m)')
    fig.suptitle(record['address']+'\nEvidence for unverified assistant predictions; not a survey')
    figure=out/'top-evidence.png';fig.savefig(figure,dpi=145);plt.close(fig)
    report['evidence_image']=dict(path=str(figure.relative_to(root)),sha256=hashlib.sha256(figure.read_bytes()).hexdigest())
    atomic(out/'evidence.json',report)
    return report


def save_sample(root,pid,draft_path):
    """Persist in-session visual judgements, attaching reproducible native statistics.

    This does not run a model or predict new properties. The draft must already
    have been authored after examining the recorded evidence image.
    """
    root=Path(root);registry=Registry(root);record=registry.get(pid)
    path=registry.folder/'sample-evidence'/pid/'evidence.json';evidence=read(path);draft=read(draft_path)
    if draft.get('property_id')!=pid or draft.get('evidence_image_sha256')!=evidence['evidence_image']['sha256']:
        raise ValueError('Assistant draft must reference the inspected evidence image')
    if evidence['input_revision']!=record.get('input_revision'): raise ValueError('Sample evidence is outdated')
    def proposal(entity_id,kind,**values):
        return dict(entity_id=entity_id,entity_kind=kind,status='unreviewed_prediction',confidence='low',
                    type='unknown',material=None,height_m=None,height_range_m=None,width_m=None,depth_m=None,
                    risk_level=None,not_for_hydraulics=True,**values)
    # dict unpacking here deliberately allows authored values to override defaults.
    def item(entity_id,kind,values):
        base=proposal(entity_id,kind);base.update(values);return base
    edges={p['entity_id']:p for p in draft['edges']}
    if set(edges)!={e['id'] for e in record['boundary_segments']}: raise ValueError('Assistant must cover every original edge')
    results=[]
    for edge in record['boundary_segments']:
        authored=dict(edges[edge['id']]);authored.pop('entity_id')
        row=item(edge['id'],'boundary_segment',authored)
        row['lidar_evidence']=next(e['point_evidence'] for e in evidence['edges'] if e['id']==edge['id'])
        row['crossed_by_flow_path']=edge['flow_path'].get('crossed_by_flow_path')
        row['flow_relation']=edge['flow_path']['relation']
        results.append(row)
    measurements={o['id']:o for o in evidence['objects']}
    canonical=[]
    for obj in sorted(record['objects'],key=lambda o:0 if o['source_id']=='linz-building-outlines' else 1):
        source=obj['source_id'];values={}
        if source in {'linz-building-outlines','buildings'}:
            geometry=shape(obj['projected_geometry']);alias=next((i for i,g in canonical if geometry.equals(g)),None)
            if alias: values['alias_of']=alias
            else: canonical.append((obj['id'],geometry))
            sample=measurements.get(obj['id'],{});stats=sample.get('point_evidence',{}).get('building',{});h=stats.get('height_p10_p50_p95_m')
            complete=(sample.get('footprint_coverage_fraction') or 0)>=.8
            values.update(type='building',confidence='medium',rationale='Official building footprint with classified building returns. Type supported by the inspected roof imagery; no facade/material claim.',lidar_evidence=sample)
            if complete and stats.get('count',0)>=100 and h:
                values.update(height_m=h[2],height_range_m=[h[0],h[2]],height_range_kind='observed_return_spread_not_confidence_interval',
                    height_basis='p95 classified roof-return z minus the co-located 1 m bare-earth DEM; roof envelope, not wall/eave height or a field measurement')
            else: values['rationale']+=' Only a small/partial footprint is inside the property crop; whole-building height left unknown.'
        elif obj.get('candidate_kind'):
            sample=measurements.get(obj['id'],{});values.update(draft.get('object_overrides',{}).get(obj['id'],{}))
            values.setdefault('rationale','Narrow low unclassified returns could be a fence, low branches or clutter. No reliable semantic type or physical height can be assigned from this evidence alone.')
            values['lidar_evidence']=sample
        else:
            values.update(type='mapped_context',status='not_applicable',confidence='not_assessed',
                rationale='Retained '+source+' map/context feature, not a visually identified above-ground structure. Height/material/depth are not inferred from cadastral, flow, zoning or indicative network geometry.')
        results.append(item(obj['id'],'object',values))
    inferred=[]
    for cluster in evidence['vegetation_clusters']:
        obj=dict(cluster,source_id='native_lidar',type='vegetation',evidence_status='inferred_canopy_cluster',review_status='unreviewed_prediction')
        inferred.append(obj);h=cluster['height_p10_p50_p95_m']
        results.append(item(obj['id'],'object',dict(type='vegetation',confidence='medium',height_m=h[2],height_range_m=[h[0],h[2]],
            height_range_kind='observed_return_spread_not_confidence_interval',
            height_basis='p95 vegetation-classified native returns above the local 1 m DEM within this connected canopy cluster',
            rationale='Inspected aerial vegetation and classified native returns support a mixed canopy/shrub cluster. Connected returns are not individual trees and do not prove a hedge/fence at the cadastral edge.',point_count=cluster['point_count'])))
    visual=draft.get('visual_review')
    visual_sources=[]
    if visual:
        from .predictions import validate_visual_review
        validate_visual_review(visual,results)
        for source in visual['sources']:
            if source.get('source_kind')=='user_attachment' and not source.get('artifact'):
                visual_sources.append(dict(source,sha256=None,hash_status='original_attachment_bytes_not_available_in_local_workspace'))
                continue
            artifact=(root/source['artifact']).resolve()
            if not artifact.is_relative_to((root/'output/playwright').resolve()) or not artifact.is_file():
                raise ValueError('Visual evidence artifact must exist inside output/playwright')
            visual_sources.append(dict(source,sha256=hashlib.sha256(artifact.read_bytes()).hexdigest()))
        visual=dict(visual,sources=visual_sources)
    bundle=dict(property_id=pid,address=record['address'],workspace_id=record['workspace_id'],method='assistant_in_session',api_used=False,
        model_id=None,created_at=stamp(),input_revision=record['input_revision'],draft_sha256=hashlib.sha256(Path(draft_path).read_bytes()).hexdigest(),
        evidence_image=evidence['evidence_image'],evidence_json_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        sources_used=evidence['assets']+visual_sources,
        sources_not_used=visual['sources_not_used'] if visual else ['Google photorealistic 3D','Google aerial','Google Street View'],
        source_limitation=visual['limitation'] if visual else 'Google provider is not configured locally; no Google imagery was used for these proposals.',
        visual_review=visual,
        limitations=['Assistant-authored two-property sample, not an automated/trained detection service or validated inventory',
                     'Qualitative confidence is uncalibrated; height ranges are explicitly labelled observed spreads or subjective estimates',
                     'Aerial occlusion, vegetation, source age mismatch and 1 m ground DEM limit physical barrier identification',
                     'Unknown material/width/depth/permeability and flood risk are not invented; manual/field review required'],
        entities=results,inferred_objects=inferred)
    return registry.save_predictions(pid,bundle)


def save_visual_sample(root,pid,review_path):
    """Apply an already-authored per-edge browser review to an existing sample.

    No detector, scraping, geometry inference or confidence boost is performed.
    Unknown fields stay explicit; original drafts/predictions are archived first.
    """
    from copy import deepcopy
    root=Path(root);registry=Registry(root)
    base_path=registry.folder/'assistant-drafts'/(pid+'.json')
    base=read(base_path);review=read(review_path)
    if review.get('property_id')!=pid or review.get('base_draft_sha256')!=hashlib.sha256(base_path.read_bytes()).hexdigest():
        raise ValueError('Visual review must match the original property draft hash')
    draft=deepcopy(base);updates={e['entity_id']:e for e in review['edge_reviews']}
    if len(updates)!=len(review['edge_reviews']) or set(updates)!={e['entity_id'] for e in draft['edges']}:
        raise ValueError('Visual review must cover each original edge exactly once')
    for edge in draft['edges']:
        update=deepcopy(updates[edge['entity_id']]);previous=edge['confidence']
        authored_fields=update.pop('field_assessments');visual=update.pop('visual_review')
        unknown_reasons=dict(material='Surface material cannot be resolved reliably in the reviewed views.',
            width_m='No calibrated cross-section or clear thickness measurement.',
            depth_m='Buried depth cannot be observed in aerial, 3D imagery or airborne returns.',
            permeability='Visible planting/openings do not measure hydraulic permeability or concealed fence solidity.',
            continuity='The entire original cadastral line is not exposed in the reviewed views.',
            potential_influence='No validated structure geometry or hydraulic modelling; mapped crossings alone are insufficient.',
            risk_level='Not assessed: no validated hydraulic risk calculation or engineering review.')
        fields={k:dict(status='unknown',confidence='not_assessed',basis=reason,source_ids=[]) for k,reason in unknown_reasons.items()}
        fields['crossed_by_flow_path']=dict(status='mapped_screening',confidence='medium',source_ids=[],
            basis='Original Council GIS line/polygon intersection only; unchanged by visual review. Not observed water or a risk classification.')
        fields.update(authored_fields)
        edge.update(update,field_assessments=fields,visual_review=visual)
        edge['confidence_change']=dict(previous=previous,current=edge['confidence'],
            reason=visual['confidence_reason'])
        for key in ['material','width_m','depth_m','risk_level']: edge.setdefault(key,None)
        for key in ['continuity','permeability']: edge.setdefault(key,'unknown')
        edge.setdefault('potential_influence','uncertain')
        edge.setdefault('height_m',None);edge.setdefault('height_range_m',None)
        # Authored image components remain relative observations until georeferenced.
        for component in edge.get('components',[]):
            if not component.get('id'): continue  # preserve older, coarse component notes
            component.setdefault('parent_edge_id',edge['entity_id'])
            component.setdefault('geometry',None)
            component.setdefault('position_status','relative_image_position_only')
            for key in ['material','height_m','width_m','depth_m','crossed_by_flow_path','risk_level']: component.setdefault(key,None)
            for key in ['continuity','permeability']: component.setdefault(key,'unknown')
            component.setdefault('potential_influence','uncertain')
            assessments={k:dict(status='unknown',confidence='not_assessed',basis=reason,source_ids=[]) for k,reason in unknown_reasons.items()}
            assessments['height_m']=dict(status='unknown',confidence='not_assessed',basis='No isolated component height profile or calibrated visual scale.',source_ids=[])
            assessments['crossed_by_flow_path']=dict(status='unknown',confidence='not_assessed',basis='Component has no measured/georeferenced geometry; parent edge crossing is not a component crossing.',source_ids=[])
            assessments['type']=dict(status='estimated',confidence=component.get('confidence','low'),basis=component.get('notes','Authored visual component hypothesis'),source_ids=component.get('source_ids',[]))
            assessments.update(component.get('field_assessments',{}));component['field_assessments']=assessments
    draft['visual_review']=review['visual_review']
    draft['visual_review_draft_sha256']=hashlib.sha256(Path(review_path).read_bytes()).hexdigest()
    # Archive immutable inputs/results before replacing a saved sample bundle.
    previous=registry.folder/'predictions'/(pid+'.json')
    if previous.is_file():
        digest=hashlib.sha256(previous.read_bytes()).hexdigest()
        archive=registry.folder/'prediction-history'/pid/(digest+'.json')
        if not archive.exists(): atomic(archive,read(previous))
    revised=registry.folder/'assistant-drafts'/(pid+'-visual.json')
    atomic(revised,draft)
    return save_sample(root,pid,revised)
