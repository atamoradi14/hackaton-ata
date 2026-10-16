"""Persistent property/edge evidence. Cadastral lines are NOT physical barriers."""
import copy
import hashlib
import json
import math
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import transform
from shapely import distance, points, contains_xy, prepare

TO_WGS = Transformer.from_crs(2193, 4326, always_xy=True).transform
TO_NZTM = Transformer.from_crs(4326, 2193, always_xy=True).transform
LOCK = threading.RLock()
VERSION = 1


def stamp():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    """Keep original attributes JSON-safe, including unknown publisher columns."""
    return json.loads(json.dumps(value, default=lambda x: x.item() if hasattr(x, 'item') else str(x)),
                      parse_constant=lambda _: None)


def identifier(prefix, value):
    return prefix + '_' + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:24]


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(clean(value), allow_nan=False, separators=(',', ':')), encoding='utf-8')
    temporary.replace(path)


def read(path, fallback=None):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else fallback


def gis(geometry):
    return mapping(transform(TO_WGS, geometry))


def unknown_structure():
    return dict(type='unknown', material=None, height_m=None, width_m=None, depth_m=None,
                continuity='unknown', permeability='unknown', potential_influence='uncertain',
                confidence=None, review_status='unreviewed', provenance='No verified physical structure assigned')


def segments(polygon):
    """Every original ring edge, including holes; no clipping/simplification/densification."""
    if polygon.geom_type not in {'Polygon', 'MultiPolygon'} or not polygon.is_valid:
        raise ValueError('A valid Polygon/MultiPolygon is required; geometry repair must be reviewed')
    for part, poly in enumerate([polygon] if polygon.geom_type == 'Polygon' else polygon.geoms):
        for ring_index, ring in enumerate([poly.exterior, *poly.interiors]):
            coords = list(ring.coords)
            for index, (a, b) in enumerate(zip(coords, coords[1:])):
                a, b = list(a[:2]), list(b[:2])
                if a == b:
                    continue
                line = LineString([a, b])
                key = identifier('edge', sorted([[round(v, 3) for v in a], [round(v, 3) for v in b]]))
                yield dict(id=key, part=part, ring=ring_index, is_hole=ring_index > 0, edge_index=index,
                           geometry=gis(line), endpoints_nztm=[a, b], length_m=line.length,
                           bearing_deg=(math.degrees(math.atan2(b[0]-a[0], b[1]-a[1]))+360)%360)


class PointEvidence:
    """Lossless local returns, queried in a metric corridor, never a wall mesh."""
    def __init__(self, cloud_path, dem_path=None):
        import laspy
        from scipy.spatial import cKDTree
        cloud = laspy.read(cloud_path)
        crs = cloud.header.parse_crs()
        if not crs or not crs.is_compound or [c.to_epsg() for c in crs.sub_crs_list] != [2193, 7839]:
            raise ValueError('Native point cloud EPSG:2193 + NZVD2016 required')
        self.path = Path(cloud_path)
        self.x = np.asarray(cloud.x); self.y = np.asarray(cloud.y); self.z = np.asarray(cloud.z)
        self.cls = np.asarray(cloud.classification)
        self.valid = ~np.asarray(cloud.withheld, dtype=bool) & ~np.isin(self.cls, [7, 18])
        self.tree = cKDTree(np.column_stack([self.x, self.y]))
        self.bounds = box(*[float(v) for v in [self.x.min(), self.y.min(), self.x.max(), self.y.max()]])
        self.heights = np.full(len(self.x), np.nan)
        self.building_mask = None
        if dem_path and Path(dem_path).exists():
            import rasterio
            with rasterio.open(dem_path) as dem:
                if dem.crs.to_epsg() != 2193 or dem.tags().get('vertical_datum') != 'NZVD2016':
                    raise ValueError('Verified NZTM/NZVD2016 DEM required for relative heights')
                ground = dem.read(1, masked=True)
                rows, cols = rasterio.transform.rowcol(dem.transform, self.x, self.y)
                rows, cols = np.asarray(rows), np.asarray(cols)
                inside = (rows>=0)&(rows<dem.height)&(cols>=0)&(cols<dem.width)
                indices = np.flatnonzero(inside)
                values = ground[rows[indices], cols[indices]]
                good = ~np.ma.getmaskarray(values)
                self.heights[indices[good]] = self.z[indices[good]] - np.asarray(values)[good]

    def near(self, line, tolerance):
        centre = line.interpolate(.5, normalized=True)
        selected = np.asarray(self.tree.query_ball_point([centre.x, centre.y], line.length/2+tolerance), dtype=int)
        if len(selected):
            selected = selected[distance(line, points(self.x[selected], self.y[selected])) <= tolerance]
        return selected

    def evidence(self, line, tolerance, edge_id):
        selected = self.near(line, tolerance)
        valid = selected[self.valid[selected]]
        heights = self.heights[valid]
        classes, counts = np.unique(self.cls[valid], return_counts=True)
        coverage = line.intersection(self.bounds).length/line.length
        result = dict(status='available' if coverage>.999 else 'partial' if coverage>0 else 'outside_crop',
                      coverage_fraction=round(coverage, 4), raw_return_count=len(selected), usable_return_count=len(valid),
                      class_counts=dict(zip(map(str, classes.tolist()), counts.tolist())),
                      height_above_dem_p95_m=float(np.nanpercentile(heights,95)) if np.isfinite(heights).any() else None,
                      height_method='Native z minus nearest 1 m DEM cell; screening only',
                      absence_is_not_proof_of_no_structure=True)
        # Deliberately conservative, unvalidated candidate screening. Never turn
        # vegetation/building returns or a parcel edge into a confirmed fence.
        low = valid[(self.cls[valid]==1)&(heights>=.3)&(heights<=3)]
        if self.building_mask is not None and len(low):
            low=low[~contains_xy(self.building_mask,self.x[low],self.y[low])]
        candidates = []
        if len(low)>=8:
            a, b = np.array(line.coords[0]), np.array(line.coords[-1]); direction=(b-a)/line.length
            xy = np.column_stack([self.x[low], self.y[low]])-a
            along = xy@direction; across = xy@np.array([-direction[1], direction[0]])
            bins = np.floor(along/.5).astype(int)
            unique = np.unique(bins)
            for run in np.split(unique, np.where(np.diff(unique)>2)[0]+1):
                keep = np.isin(bins, run)
                if len(run)<4 or keep.sum()<8:
                    continue
                start, end = float(along[keep].min()), float(along[keep].max())
                continuity = len(run)/(int(run[-1]-run[0])+1)
                spread = float(np.percentile(across[keep],95)-np.percentile(across[keep],5))
                if end-start<1.5 or continuity<.5 or spread>1.2:
                    continue
                offset = float(np.median(across[keep])); normal=np.array([-direction[1], direction[0]])
                geometry=LineString([a+direction*start+normal*offset, a+direction*end+normal*offset])
                candidates.append(dict(id=identifier('candidate',[edge_id,round(start,1),round(end,1)]),
                    geometry=gis(geometry), projected_geometry=mapping(geometry), type='unknown',
                    candidate_kind='linear_above_ground_returns', confidence='low; heuristic not validated',
                    review_status='automated_candidate', point_count=int(keep.sum()), source_class=1,
                    height_estimate_p95_m=float(np.percentile(self.heights[low[keep]],95)),
                    observed_lateral_spread_m=spread, occupied_bin_fraction=continuity,
                    material=None, width_m=None, depth_m=None,
                    limitations=['Could be clutter; needs imagery/field review',
                                 'Point spread is not physical wall thickness',
                                 'Vegetation-classified fences may be missed']))
        return result, candidates


class Evidence:
    def __init__(self, layers=None, sources=None, cloud=None, assets=None):
        self.layers = layers or {}; self.sources = sources or {}; self.cloud = cloud; self.assets = assets or []
        if cloud:
            name=next((n for n in ['linz-building-outlines','buildings'] if n in self.layers),None)
            if name:
                frame=self.layers[name]
                cloud.building_mask=frame.loc[frame.geometry.is_valid & ~frame.geometry.is_empty].geometry.union_all()
                prepare(cloud.building_mask)

    def nearby(self, line, tolerance):
        found = []
        for name, frame in self.layers.items():
            if frame.empty:
                continue
            for index in frame.sindex.query(line.buffer(tolerance), predicate='intersects'):
                row = frame.iloc[int(index)]; geometry = row.geometry
                attributes = clean(row.drop(labels=['geometry']).to_dict())
                object_id = next((attributes[k] for k in ['OBJECTID','objectid','id','FID','osm_id'] if attributes.get(k) is not None),
                                 hashlib.sha256(geometry.wkb).hexdigest()[:20])
                source = self.sources.get(name, {})
                fid = identifier('feature',[name,str(object_id)])
                found.append(dict(id=fid, source_id=name, source_feature_id=str(object_id),
                                  distance_m=float(line.distance(geometry)), geometry=gis(geometry),
                                  projected_geometry=mapping(geometry), source_attributes=attributes,
                                  source=source, evidence_status='official_map' if not name.startswith('osm') else 'community_map',
                                  limitations=['Proximity is not proof this feature is the boundary structure']))
        return found


def flow_relationship(line, evidence, tolerance):
    names=[n for n in ['ac-overland-flow-paths','overland_flow'] if n in evidence.layers][:1]
    if not names:
        return dict(status='missing', crossed_by_flow_path=None, relation='unknown', matches=[])
    matches=[]
    for name in names:
        frame=evidence.layers[name]
        for index in frame.sindex.query(line.buffer(tolerance), predicate='intersects'):
            row=frame.iloc[int(index)]; flow=row.geometry
            if line.crosses(flow): relation='crosses'
            elif line.intersects(flow): relation='overlaps' if line.intersection(flow).length>1e-7 else 'touches'
            else:
                # Compare the local flow tangent, not a long feature's end-to-end heading.
                members=list(flow.geoms) if flow.geom_type=='MultiLineString' else [flow]
                nearest=min(members,key=lambda g:line.distance(g))
                at=nearest.project(line.interpolate(.5,normalized=True))
                p,q=nearest.interpolate(max(0,at-1)),nearest.interpolate(min(nearest.length,at+1))
                a,b=np.array(line.coords[0]),np.array(line.coords[-1]); d=b-a; f=np.array([q.x-p.x,q.y-p.y])
                cosine=abs(float(d@f))/(float(np.linalg.norm(d)*np.linalg.norm(f)) or 1)
                relation='parallels' if cosine>=math.cos(math.radians(15)) else 'adjacent'
            attributes=clean(row.drop(labels=['geometry']).to_dict())
            matches.append(dict(source_id=name, source_attributes=attributes, relation=relation,
                distance_m=float(line.distance(flow)), intersection=gis(line.intersection(flow)) if line.intersects(flow) else None))
    relations={m['relation'] for m in matches}
    relation=next((r for r in ['crosses','overlaps','touches','parallels','adjacent'] if r in relations),'outside')
    return dict(status='mapped_screening_only', crossed_by_flow_path='crosses' in relations,
                intersects_mapped_path=bool(relations&{'crosses','overlaps','touches'}), relation=relation,matches=matches,
                limitation='Mapped GIS relationship, not observed water motion or hydraulic risk')


def build_record(geometry, source_id, source_feature_id, attributes=None, evidence=None, address=None,
                 tolerance=1.0, workspace_id=None):
    if not .1<=tolerance<=5:
        raise ValueError('Proximity tolerance must be 0.1–5 metres')
    evidence=evidence or Evidence(); pid=identifier('property',[source_id,str(source_feature_id)])
    interior=evidence.nearby(geometry,0)
    objects={o['id']:o for o in interior}; edges=[]
    for edge in segments(geometry):
        line=LineString(edge['endpoints_nztm']); nearby=evidence.nearby(line,tolerance)
        for item in nearby: objects[item['id']]=item
        cloud, candidates = evidence.cloud.evidence(line,tolerance,edge['id']) if evidence.cloud else (
            dict(status='missing',usable_return_count=None,absence_is_not_proof_of_no_structure=True),[])
        for item in candidates: objects[item['id']]=dict(item,source_id='native_lidar',source=evidence.sources.get('native_lidar',{}),evidence_status='inferred_candidate')
        flow=flow_relationship(line,evidence,tolerance)
        edges.append(dict(edge, structure=unknown_structure(), flow_path=flow,
            nearby_objects=[dict(object_id=o['id'], distance_m=o['distance_m']) for o in nearby]+
                           [dict(object_id=o['id'],distance_m=None) for o in candidates],
            lidar=cloud, risk=dict(level=None,status='not_assessed',reason='No validated property/structure risk assessment'),
            review_priority='inspect_crossing' if flow.get('crossed_by_flow_path') else 'unranked'))
    return dict(schema_version=VERSION,id=pid,source_id=source_id,source_feature_id=str(source_feature_id),
        address=address,workspace_id=workspace_id,geometry=gis(geometry),projected_geometry=mapping(geometry),
        coordinate_systems=dict(geometry='OGC:CRS84 longitude/latitude',endpoints_nztm='EPSG:2193 metres',
                                elevations='NZVD2016 only where source verified; 2D endpoints have no invented z'),
        source_attributes=clean(attributes or {}),source_provenance=evidence.sources.get(source_id,dict(capture_date=None,status='source_date_unverified')),
        boundary_segments=edges, objects=list(objects.values()),property_object_ids=[o['id'] for o in interior],
        raw_assets=evidence.assets, sources=evidence.sources, proximity_tolerance_m=tolerance, updated_at=stamp(),
        limitations=['Cadastral boundaries do not establish fences, ownership of structures or surveyed fence locations',
                     'Automated candidates are not verified fences; material, depth and risk are unknown unless reviewed',
                     'Missing/empty data is not proof no structures or flood exposure exist'])


class Registry:
    def __init__(self, root):
        self.root=Path(root); self.folder=self.root/'data/property-registry'

    def _path(self, pid):
        if not re.fullmatch(r'property_[0-9a-f]{24}',str(pid)):
            raise ValueError('Invalid property identifier')
        return self.folder/'properties'/(pid+'.json')

    def save(self, record):
        with LOCK:
            atomic(self._path(record['id']),record)
            self._index(record['id'],record)
        return self.get(record['id'])

    def get(self,pid):
        value=read(self._path(pid))
        if value is None: raise ValueError('Property not recorded')
        detection=read(self.folder/'crossing-detections'/(pid+'.json'))
        detection_stale=bool(detection and detection.get('property_sha256')!=hashlib.sha256(
            json.dumps(value,sort_keys=True,default=str).encode()).hexdigest())
        reviews=read(self.folder/'reviews'/(pid+'.json'),{})
        for edge in value['boundary_segments']:
            if edge['id'] in reviews:
                edge['structure'].update(reviews[edge['id']]['structure'])
                edge['review']=reviews[edge['id']]['review']
                edge['risk']=reviews[edge['id']]['risk']
        bundle=read(self.folder/'predictions'/(pid+'.json'))
        value['prediction_objects']=[]
        if bundle:
            stale=bundle.get('input_revision')!=value.get('input_revision')
            value['prediction_bundle']={k:v for k,v in bundle.items() if k not in {'entities','inferred_objects'}}
            value['prediction_bundle']['stale']=stale
            predicted={r['entity_id']:dict(r,stale=stale) for r in bundle['entities']}
            value['prediction_objects']=bundle.get('inferred_objects',[])
            for entity in [*value['boundary_segments'],*value['objects'],*value['prediction_objects']]:
                if entity['id'] in predicted: entity['prediction']=predicted[entity['id']]
        if detection:
            value['detection_bundle']={k:v for k,v in detection.items() if k not in {'entities','inferred_objects'}}
            value['detection_bundle']['stale']=detection_stale
            value.setdefault('prediction_bundle',value['detection_bundle'])
            detected={r['entity_id']:dict(r,stale=detection_stale) for r in detection['entities']}
            original_ids={o['id'] for o in value['objects']+value['prediction_objects']}
            value['prediction_objects'].extend(copy.deepcopy(o) for o in detection['inferred_objects'] if o['id'] not in original_ids)
            for entity in [*value['boundary_segments'],*value['prediction_objects']]:
                if entity['id'] not in detected: continue
                row=detected[entity['id']];entity['detection']=row
                if not entity.get('prediction') or entity['prediction'].get('stale'): entity['prediction']=row
                if entity.get('flow_path',{}).get('crossed_by_flow_path') is True:
                    ids={r['object_id'] for r in entity['nearby_objects']}
                    entity['nearby_objects'].extend(dict(object_id=oid,distance_m=None) for oid in row.get('detected_object_ids',[]) if oid not in ids)
        object_reviews=read(self.folder/'object-reviews'/(pid+'.json'),{})
        for obj in [*value['objects'],*value['prediction_objects']]:
            if obj['id'] in object_reviews:
                saved=object_reviews[obj['id']];obj['structure']=saved['structure'];obj['review']=saved['review'];obj['risk']=saved['risk']
        return value

    def save_predictions(self,pid,bundle):
        from .features.predictions import validate
        value=validate(self.get(pid),bundle)
        with LOCK: atomic(self.folder/'predictions'/(pid+'.json'),value)
        return self.get(pid)

    def _index(self,pid,record=None):
        """Keep browsing independent of potentially large raw-evidence bundles."""
        source=self._path(pid); stat=source.stat(); signature=[stat.st_size,stat.st_mtime_ns]
        path=self.folder/'index'/(pid+'.json'); cached=read(path,{})
        if record is None and cached.get('source_signature')==signature: return cached['feature']
        r=record if record is not None else self.get(pid)
        feature=dict(type='Feature',id=r['id'],geometry=r['geometry'],properties=dict(
            id=r['id'],address=r['address'],source_id=r['source_id'],source_feature_id=r['source_feature_id'],
            segment_count=len(r['boundary_segments']),crossing_count=sum(e['flow_path'].get('crossed_by_flow_path') is True for e in r['boundary_segments']),
            candidate_count=sum(o.get('candidate_kind') is not None for o in r['objects'])))
        with LOCK: atomic(path,dict(source_signature=signature,feature=feature))
        return feature

    def collection(self):
        folder=self.folder/'properties'
        # All registry writes atomically replace a file, changing directory mtime.
        # One consolidated browse index avoids hundreds of Docker bind-mount reads.
        signature=folder.stat().st_mtime_ns if folder.exists() else 0
        path=self.folder/'map-index.json'; cached=read(path,{})
        if cached.get('source_directory_revision')==signature:
            features=cached['features']
        else:
            features=[self._index(p.stem) for p in sorted(folder.glob('property_*.json'))]
            with LOCK: atomic(path,dict(source_directory_revision=signature,features=features))
        return dict(type='FeatureCollection',features=features,storage='JSON',hydraulic=False,
                    source_import=read(self.folder/'import-manifest.json',{}))

    def export(self,pid=None):
        records=[self.get(pid)] if pid else [self.get(p.stem) for p in sorted((self.folder/'properties').glob('property_*.json'))]
        return dict(schema_version=VERSION,created_at=stamp(),properties=records,
                    export_scope='all recorded properties; not all Auckland',hydraulic=False)

    def point_export(self,pid):
        """Every original LAS dimension in/next to this polygon, including raw flags."""
        import laspy
        from shapely import covers
        value=self.get(pid); source=None
        for asset in value['raw_assets']:
            if asset['name'].endswith('.laz'):
                source=(self.root/'data/web-sites'/value['workspace_id']/'data/processed/site'/asset['name']) if value.get('workspace_id') else self.folder/'raw'/asset['name']
                break
        if source is None or not source.exists(): raise ValueError('No native point source for this property')
        if not source.resolve().is_relative_to((self.root/'data').resolve()): raise ValueError('Invalid point source')
        with source.open('rb') as stream: actual_hash=hashlib.file_digest(stream,'sha256').hexdigest()
        if asset.get('sha256') and asset['sha256']!=actual_hash:
            raise ValueError('Native point source changed; refresh the recorded evidence')
        polygon=shape(value['projected_geometry']).buffer(value['proximity_tolerance_m'])
        rows=[]; dimensions={}
        with laspy.open(source) as reader:
            crs=reader.header.parse_crs()
            if not crs or not crs.is_compound or [c.to_epsg() for c in crs.sub_crs_list]!=[2193,7839]:
                raise ValueError('Native point export requires verified NZTM/NZVD2016 metadata')
            scales=reader.header.scales.tolist(); offsets=reader.header.offsets.tolist()
            for chunk in reader.chunk_iterator(500000):
                x,y=np.asarray(chunk.x),np.asarray(chunk.y); bounds=polygon.bounds
                ids=np.flatnonzero((x>=bounds[0])&(y>=bounds[1])&(x<=bounds[2])&(y<=bounds[3]))
                ids=ids[covers(polygon,points(x[ids],y[ids]))]
                if not len(ids): continue
                rows.extend(np.column_stack([x[ids],y[ids],np.asarray(chunk.z)[ids]]).tolist())
                for name in reader.header.point_format.dimension_names:
                    dimensions.setdefault(name,[]).extend(np.asarray(chunk[name])[ids].tolist())
        return dict(property_id=pid,count=len(rows),points_nztm=rows,point_attributes=dimensions,
                    horizontal_crs='EPSG:2193',vertical_datum='NZVD2016',raw_las_scales=scales,raw_las_offsets=offsets,
                    includes_noise_and_withheld=True,scope='Property polygon plus recorded proximity tolerance',
                    source_sha256=actual_hash,synthetic=False)

    def geojson(self,pid):
        value=self.get(pid)
        return dict(type='FeatureCollection',features=[dict(type='Feature',id=e['id'],geometry=e['geometry'],
                    properties={k:v for k,v in e.items() if k!='geometry'}) for e in value['boundary_segments']])

    def review(self,pid,edge_id,data,kind='segment'):
        if not isinstance(data,dict): raise ValueError('Review must be an object')
        record=self.get(pid)
        entities=record['boundary_segments'] if kind=='segment' else record['objects']+record['prediction_objects'] if kind=='object' else []
        if edge_id not in {e['id'] for e in entities}:
            raise ValueError('Entity not part of this property')
        allowed={'type','material','height_m','width_m','depth_m','continuity','permeability','potential_influence','notes','risk_level'}
        if set(data)-allowed: raise ValueError('Unknown review field')
        enums=dict(type={'building','fence','wall','retaining_wall','gate','hedge','bund','kerb','vegetation','mixed','other','unknown'},
                   continuity={'continuous','discontinuous','unknown'},permeability={'solid','partly_permeable','permeable','unknown'},
                   potential_influence={'block','divert','constrict','channel','uncertain','negligible'})
        checked={k:v for k,v in data.items() if k not in {'notes','risk_level'}}
        for key, choices in enums.items():
            if key in checked and checked[key] not in choices: raise ValueError('Invalid '+key)
        for key in ['height_m','width_m','depth_m']:
            if key in checked and checked[key] is not None:
                v=checked[key]
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=100:
                    raise ValueError('Dimensions must be finite metres between 0 and 100, or null')
        if 'material' in checked and checked['material'] is not None and (not isinstance(checked['material'],str) or len(checked['material'])>100):
            raise ValueError('Material must be a short description or null')
        notes=data.get('notes','')
        if not isinstance(notes,str) or not 5<=len(notes.strip())<=1200:
            raise ValueError('Record an evidence/review note (5–1200 characters)')
        level=data.get('risk_level')
        if level not in {None,'low','medium','high'}: raise ValueError('Invalid user-supplied risk level')
        checked.update(review_status='manually_reviewed',provenance='User supplied; not independently verified')
        with LOCK:
            path=self.folder/('reviews' if kind=='segment' else 'object-reviews')/(pid+'.json'); reviews=read(path,{})
            previous=reviews.get(edge_id,{}).get('structure',unknown_structure())
            reviews[edge_id]=dict(structure=dict(previous,**checked),
                review=dict(notes=notes.strip(),updated_at=stamp(),method='user_input',independently_verified=False),
                risk=dict(level=level,status='user_supplied_unvalidated' if level else 'not_assessed',
                          reason='Manual concern label, not an engineering flood-risk verdict'))
            atomic(path,reviews)
        return self.get(pid)


def workspace_evidence(folder, include_cloud=True, root=None):
    folder=Path(folder); layers={}; sources={}; assets=[]
    manifest=read(folder/'gis-discovery-manifest.json',{}).get('layers',{})
    for path in sorted(folder.glob('*.gpkg')):
        frame=gpd.read_file(path)
        if frame.crs is None: continue
        layers[path.stem]=frame.to_crs(2193)
        sources[path.stem]=manifest.get(path.stem,dict(status='available',source_file=path.name,capture_date=None))
    for name,source in manifest.items():
        if source.get('status')=='available_empty' and name not in layers:
            layers[name]=gpd.GeoDataFrame(geometry=[],crs=2193); sources[name]=source
    civic=read(folder/'civic-evidence.json',{})
    if root and civic.get('area_id'):
        base=Registry(root).folder/'raw/areas'/civic['area_id']
        for name,source in civic.get('sources',{}).items():
            sources[name]=source
            if source.get('status')=='available':
                layers[name]=gpd.read_file(base/source['raw_file']).to_crs(2193)
            elif source.get('status')=='available_empty': layers[name]=gpd.GeoDataFrame(geometry=[],crs=2193)
            if source.get('raw_file'):
                assets.append(dict(name=source['raw_file'],sha256=source.get('sha256'),format='EsriJSON',
                    download_url=f"/api/property-sources/{civic['area_id']}/{name}"))
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix in {'.gpkg','.geojson','.tif','.laz','.json','.jpg'}:
            with path.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
            assets.append(dict(name=path.name,sha256=digest,
                               bytes=path.stat().st_size,format=path.suffix))
    cloud=PointEvidence(folder/'pointcloud_crop.laz',folder/'dem_discovery.tif') if include_cloud and (folder/'pointcloud_crop.laz').exists() else None
    sources['native_lidar']=read(folder/'pointcloud-manifest.json',dict(status='missing'))
    sources['linz-primary-parcels']=dict(source='https://data.linz.govt.nz/layer/50772-nz-primary-parcels/',
                                       capture_date=None,license='CC-BY-4.0',status='official_map')
    return Evidence(layers,sources,cloud,assets)


def record_workspace(root,folder,site,workspace_id=None,force=False):
    registry=Registry(root); folder=Path(folder)
    if not site.get('user_visual_confirmation'): raise ValueError('Confirmed property required')
    pid=identifier('property',['linz-primary-parcels',str(site['parcel_id'])])
    # Fingerprint source revisions, not just their existence. Never overwrite manual reviews.
    inputs=[p for p in folder.iterdir() if p.suffix in {'.gpkg','.laz','.tif','.jpg'} or p.name in {'parcel.geojson','civic-evidence.json','scene-aerial.json'}]
    fingerprint=identifier('revision',sorted((p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in inputs))
    old=read(registry._path(pid))
    if not force and old and old.get('input_revision')==fingerprint: return registry.get(pid)
    parcel=gpd.read_file(folder/'parcel.geojson').to_crs(2193)
    if len(parcel)!=1: raise ValueError('One selected property feature required')
    context=workspace_evidence(folder,root=root)
    result=build_record(parcel.geometry.iloc[0],'linz-primary-parcels',site['parcel_id'],
                        parcel.iloc[0].drop(labels=['geometry']).to_dict(),context,site.get('address'),workspace_id=workspace_id)
    result['input_revision']=fingerprint
    for asset in result['raw_assets']:
        asset['workspace_id']=workspace_id
        if not asset.get('download_url'): asset['download_url']=f'/api/jobs/{workspace_id}/files/'+asset['name'] if workspace_id else None
    return registry.save(result)
