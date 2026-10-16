"""Private catalogue ingestion; public, bounded, cached publisher data only."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import requests
from urllib.parse import urljoin

from ..properties import Evidence, PointEvidence, Registry, atomic, build_record, read, stamp

PILOT_BOUNDS=[1753120,5915760,1753600,5916480]
TILE='CL2_BA31_2024_1000_4245'
POINT_BASE='https://opentopography.s3.sdsc.edu/pc-bulk/NZ24_Auckland/'


def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def get(url,params=None):
    response=requests.get(url,params=params,timeout=(12,35),headers={'User-Agent':'AucklandFlowLab-local-research/1.0'})
    response.raise_for_status(); value=response.json()
    if 'error' in value: raise ValueError('Publisher query error: '+str(value['error'].get('code','unknown')))
    return value


def fetch_vector(record,bounds,raw):
    name=record['id']; folder=raw/name; folder.mkdir(parents=True,exist_ok=True)
    saved=read(folder/'source.json')
    if saved and (folder/'features.json').exists(): return saved
    source=dict(id=name,title=record['title'],url=record['url'],access='open',bounds_nztm=bounds,
                retrieved_at=stamp(),capture_date=None,license=record.get('license','Check publisher copyright metadata'),
                vertical_datum='unverified; no absolute asset levels combined',status='pending')
    try:
        metadata=get(record['queryUrl'].removesuffix('/query'),{'f':'json'})
        atomic(folder/'metadata.json',metadata)
        if metadata.get('type') not in {'Feature Layer','Table'} or not metadata.get('geometryType'):
            raise ValueError('Not a spatial feature layer')
        source['copyright']=metadata.get('copyrightText')
        source['editing_info']=metadata.get('editingInfo')  # Update timestamp is not a survey date.
        common=dict(f='json',geometry=','.join(map(str,bounds)),geometryType='esriGeometryEnvelope',inSR=2193,
                    spatialRel='esriSpatialRelIntersects',where='1=1')
        enumeration=get(record['queryUrl'],dict(common,returnIdsOnly='true'))
        ids=enumeration.get('objectIds')
        if ids is None:
            if 'objectIds' in enumeration and get(record['queryUrl'],dict(common,returnCountOnly='true')).get('count')==0:
                ids=[]
            else: raise ValueError('Publisher did not enumerate IDs; refusing possible truncation')
        if len(ids)>100000: raise ValueError('Too many features for a local pilot')
        ids=sorted(set(ids)); features=[]
        oid=metadata.get('objectIdField') or next((f['name'] for f in metadata['fields'] if f.get('type')=='esriFieldTypeOID'),None)
        if not oid: raise ValueError('Publisher omitted object ID field')
        # Keep encoded GET URLs below common IIS query-string limits.
        step=min(60,int(metadata.get('maxRecordCount') or 60))
        for start in range(0,len(ids),step):
            batch=ids[start:start+step]
            page=get(record['queryUrl'],dict(f='json',objectIds=','.join(map(str,batch)),outFields='*',outSR=2193,
                                              returnGeometry='true'))
            sr=page.get('spatialReference',{})
            if sr.get('latestWkid',sr.get('wkid'))!=2193: raise ValueError('Response CRS was not NZTM2000')
            if page.get('exceededTransferLimit') or len(page.get('features',[]))!=len(batch):
                raise ValueError('Incomplete publisher ID batch')
            if {f['attributes'].get(oid) for f in page['features']}!=set(batch):
                raise ValueError('Publisher returned different object IDs')
            features.extend(page['features'])
        value=dict(spatialReference={'wkid':2193},geometryType=metadata['geometryType'],fields=metadata['fields'],features=features)
        atomic(folder/'features.json',value)
        source.update(status='available' if ids else 'available_empty',count=len(features),sha256=digest(folder/'features.json'),
                      raw_file=name+'/features.json',metadata_file=name+'/metadata.json',geometry_type=metadata['geometryType'])
    except Exception as error:
        source.update(status='blocked',reason=str(error)[:200])
    atomic(folder/'source.json',source)
    return source


def enrich_workspace(root,folder):
    """Reuse the privately provisioned catalogue for any later confirmed property."""
    from ..properties import identifier
    root=Path(root); folder=Path(folder); registry=Registry(root)
    catalogue=read(registry.folder/'raw/water-source-catalogue.json')
    if not catalogue: return None
    frame=gpd.read_file(folder/'parcel.geojson').to_crs(2193)
    b=frame.total_bounds; bounds=[float(b[0]-20),float(b[1]-20),float(b[2]+20),float(b[3]+20)]
    area=identifier('area',[round(v,2) for v in bounds]); raw=registry.folder/'raw/areas'/area
    raw.mkdir(parents=True,exist_ok=True)
    records=[r for r in catalogue['datasets'] if r.get('access')=='open' and r.get('linkType')=='arcgis_rest' and r.get('queryUrl')]
    with ThreadPoolExecutor(max_workers=3) as pool:
        reports=list(pool.map(lambda r:fetch_vector(r,bounds,raw),records))
    report=dict(area_id=area,bounds_nztm=bounds,sources={r['id']:r for r in reports},updated_at=stamp())
    atomic(raw/'manifest.json',report); atomic(folder/'civic-evidence.json',report)
    return report


def native_assets(raw):
    """One verified native tile, plus authoritative raster windows, not whole-region downloads."""
    import laspy
    import rasterio
    from rasterio.windows import from_bounds
    folder=raw/'native'; folder.mkdir(exist_ok=True)
    metadata=get(POINT_BASE+TILE+'.json'); atomic(folder/'pointcloud-source.json',metadata)
    native=metadata['metadata']
    if 'NZVD2016' not in native['comp_spatialreference'] or '"2193"' not in native['comp_spatialreference']:
        raise ValueError('Pilot tile compound datum not verified')
    if any(abs(a-b)>1 for a,b in zip([native['minx'],native['miny'],native['maxx'],native['maxy']],PILOT_BOUNDS)):
        raise ValueError('Starter tile native bounds changed')
    target=folder/'pointcloud.laz'; size=int(metadata['file_size'])
    if size>80000000: raise ValueError('Pilot point tile exceeds download limit')
    if not target.exists():
        with requests.get(POINT_BASE+TILE+'.laz',stream=True,timeout=(15,90)) as response:
            response.raise_for_status(); total=0
            with target.with_suffix('.partial').open('wb') as stream:
                for chunk in response.iter_content(1024*1024):
                    total+=len(chunk)
                    if total>size: raise ValueError('Point tile larger than publisher size')
                    stream.write(chunk)
            if total!=size: raise ValueError('Incomplete native point download')
        target.with_suffix('.partial').replace(target)
    with laspy.open(target) as cloud:
        crs=cloud.header.parse_crs()
        if not crs or not crs.is_compound or [c.to_epsg() for c in crs.sub_crs_list]!=[2193,7839] or cloud.header.point_count!=int(native['count']):
            raise ValueError('Native point header/count differs from metadata')
    assets=[dict(name='native/pointcloud.laz',sha256=digest(target),bytes=size,source=POINT_BASE+TILE+'.laz',
                 capture_dates=['2024-04-30','2024-06-27'],horizontal_crs='EPSG:2193',vertical_datum='NZVD2016')]
    for kind in ['dem','dsm']:
        url=f'https://nz-elevation.s3.ap-southeast-2.amazonaws.com/auckland/auckland-part-1_2024/{kind}_1m/2193/BA31_10000_0505.tiff'
        collection=url.rsplit('/',1)[0]+'/collection.json'
        meta=get(collection); atomic(folder/(kind+'-collection.json'),meta)
        # STAC's collection omits a vertical datum. Match the exact survey to the
        # independently recorded official LINZ-layer datum receipt; never infer
        # it from EPSG:2193 or apply an arbitrary vertical offset.
        receipt=read(raw.parents[2]/'docs/verified-surveys.json',{}).get('surveys',{}).get('121990' if kind=='dem' else '121992',{})
        if receipt.get('title')!=meta.get('title') or receipt.get('vertical_datum')!='NZVD2016':
            raise ValueError('A matching authoritative survey-datum receipt is required for '+kind)
        atomic(folder/(kind+'-datum-evidence.json'),receipt)
        output=folder/(kind+'.tif')
        if not output.exists():
            with rasterio.Env(GDAL_HTTP_TIMEOUT='40',GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
                with rasterio.open(url) as src:
                    if src.crs.to_epsg()!=2193: raise ValueError('Pilot raster CRS mismatch')
                    win=from_bounds(*PILOT_BOUNDS,src.transform).round_offsets().round_lengths()
                    values=src.read(1,window=win,masked=True)
                    if values.mask.any(): raise ValueError('Pilot raster has nodata; do not fill silently')
                    profile=src.profile.copy(); profile.update(width=values.shape[1],height=values.shape[0],transform=src.window_transform(win),driver='GTiff')
                    with rasterio.open(output,'w',**profile) as dst:
                        dst.write(values.filled(src.nodata or -9999),1)
                        dst.update_tags(vertical_datum='NZVD2016',datum_source=receipt['url'])
        assets.append(dict(name='native/'+output.name,sha256=digest(output),bytes=output.stat().st_size,source=url,
                           horizontal_crs='EPSG:2193',vertical_datum='NZVD2016',resolution_m=1))
    # Keep a native-resolution RGB window as an original-data asset, and a
    # separate lighter, correctly warped browser preview. Imagery is not a DEM.
    image_status=dict(status='pending')
    try:
        import numpy as np
        from PIL import Image
        from ..api.assets import aerial_overlay
        collection='https://nz-imagery.s3.ap-southeast-2.amazonaws.com/auckland/auckland_2024_0.075m/rgb/2193/collection.json'
        item_url=urljoin(collection,'BA31_1000_4245.json'); item=get(item_url)
        atomic(folder/'aerial-item.json',item)
        image_url=urljoin(item_url,item['assets']['visual']['href'])
        image_file=folder/'aerial.tif'
        if not image_file.exists():
            with rasterio.Env(GDAL_HTTP_TIMEOUT='40',GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
                with rasterio.open(image_url) as src:
                    if src.crs.to_epsg()!=2193: raise ValueError('Aerial CRS mismatch')
                    win=from_bounds(*PILOT_BOUNDS,src.transform).round_offsets().round_lengths()
                    pixels=src.read([1,2,3],window=win,masked=True)
                    if np.ma.getmaskarray(pixels).any(): raise ValueError('Aerial window has nodata')
                    profile=src.profile.copy();profile.update(driver='GTiff',count=3,width=pixels.shape[2],height=pixels.shape[1],transform=src.window_transform(win),compress='deflate')
                    with rasterio.open(image_file,'w',**profile) as dst: dst.write(np.asarray(pixels))
        with rasterio.open(image_file) as src:
            pixels=src.read([1,2,3],out_shape=(3,3600,2400))
            resolution=list(src.res)
        Image.fromarray(np.moveaxis(pixels,0,-1)).save(folder/'scene-aerial.jpg',quality=94)
        atomic(folder/'scene-aerial.json',dict(bounds_nztm=PILOT_BOUNDS,title='LINZ Auckland 2024–2025 7.5 cm aerial',
            sha256=digest(folder/'scene-aerial.jpg'),source_resolution_m=resolution,display_resolution_m=.2,
            source=image_url,source_properties=item['properties'],license='CC-BY-4.0'))
        aerial_overlay(folder)
        for path in [image_file,folder/'scene-aerial.jpg',folder/'map-aerial.png']:
            assets.append(dict(name='native/'+path.name,sha256=digest(path),bytes=path.stat().st_size,
                source=image_url,source_properties=item['properties'],download_url='/api/property-assets/'+path.name))
        image_status=dict(status='available',source=image_url,capture_properties=item['properties'],license='CC-BY-4.0')
    except Exception as error:
        image_status=dict(status='blocked',reason=str(error)[:200])
    atomic(folder/'aerial-status.json',image_status)
    for asset in assets:
        asset.setdefault('download_url','/api/property-assets/'+asset['name'].split('/')[-1])
    return assets


def import_pilot(root,catalogue_path,include_lidar=True):
    root=Path(root); registry=Registry(root); raw=registry.folder/'raw'; raw.mkdir(parents=True,exist_ok=True)
    catalogue=read(catalogue_path)
    records=[r for r in catalogue['datasets'] if 'water-overland-flow' in r.get('problemStatements',[])]
    atomic(raw/'water-source-catalogue.json',dict(problem=catalogue['problemStatements']['water-overland-flow'],datasets=records,
        catalogue_sha256=digest(catalogue_path),private_event_catalogue=True))
    vectors=[r for r in records if r.get('access')=='open' and r.get('linkType')=='arcgis_rest' and r.get('queryUrl')]
    with ThreadPoolExecutor(max_workers=3) as pool:
        reports=list(pool.map(lambda r:fetch_vector(r,PILOT_BOUNDS,raw),vectors))
    print('Pilot vector sources cached: '+str(len(reports)),flush=True)
    sources={r['id']:r for r in reports}; layers={}
    for source in reports:
        if source['status']=='available':
            frame=gpd.read_file(raw/source['raw_file'])
            if frame.crs is None or frame.crs.to_epsg()!=2193: raise ValueError('Decoded source CRS mismatch')
            layers[source['id']]=frame
        elif source['status']=='available_empty': layers[source['id']]=gpd.GeoDataFrame(geometry=[],crs=2193)
    asset_status={}; assets=[]; cloud=None
    if include_lidar:
        try:
            assets=native_assets(raw)
            cloud=PointEvidence(raw/'native/pointcloud.laz',raw/'native/dem.tif')
            asset_status['native_lidar']='available'
        except Exception as error:
            asset_status['native_lidar']='blocked: '+str(error)[:180]
            # A downloaded, verified LAZ may still be usable without height data.
            if (raw/'native/pointcloud.laz').exists():
                cloud=PointEvidence(raw/'native/pointcloud.laz')
        print('Pilot native evidence: '+asset_status['native_lidar'],flush=True)
    for source in reports:
        if source.get('raw_file'):
            path=raw/source['raw_file']
            assets.append(dict(name=source['raw_file'],sha256=source['sha256'],bytes=path.stat().st_size,
                               download_url='/api/property-sources/'+source['id'],source=source['url']))
    context=Evidence(layers,sources,cloud,assets)
    sources['native_lidar']=dict(status='available' if cloud else 'missing',source=POINT_BASE+TILE+'.laz',
        capture_dates=['2024-04-30','2024-06-27'],horizontal_crs='EPSG:2193',vertical_datum='NZVD2016',license='CC-BY-4.0')
    property_source='linz-property-boundaries'
    properties=layers.get(property_source)
    if properties is None or properties.empty:
        property_source='linz-primary-parcels'; properties=layers.get(property_source)
    if properties is None or properties.empty: raise ValueError('No pilot property polygons acquired; inspect source manifest')
    count=0; edge_count=0; candidates=0
    for index,row in properties.iterrows():
        if row.geometry is None or row.geometry.is_empty or not row.geometry.is_valid: continue
        attrs=row.drop(labels=['geometry']).to_dict()
        reference=next((attrs[k] for k in ['valuation_reference','id','OBJECTID','objectid'] if attrs.get(k) is not None),index)
        record=build_record(row.geometry,property_source,reference,attrs,context)
        record['pilot']='BA31_1000_4245'; registry.save(record)
        count+=1; edge_count+=len(record['boundary_segments']); candidates+=sum(o.get('candidate_kind') is not None for o in record['objects'])
        if count%25==0: print('Properties recorded: '+str(count),flush=True)
    for r in records:
        if r['id'] not in sources:
            sources[r['id']]=dict(id=r['id'],title=r['title'],url=r['url'],status='catalogued_not_downloaded',
                reason='Non-vector/manual/keyed source; native sources handled separately. OSM remains a separate ODbL validation source.')
    report=dict(updated_at=stamp(),pilot='BA31_1000_4245',bounds_nztm=PILOT_BOUNDS,properties=count,
                segments=edge_count,automated_candidates=candidates,sources=sources,native_assets=asset_status,
                caveats=['All means all recorded properties, not whole Auckland',
                         'Private organiser material retained locally only; original public licences still apply',
                         'No detection accuracy claim without labelled validation'])
    atomic(registry.folder/'import-manifest.json',report)
    return report
