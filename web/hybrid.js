import * as THREE from 'three';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {siteMeshes,classifiedCloud,groundAt,parcelPaths,EARTH_GLTF_AXES} from './site-geometry.js';
import {CesiumWidget,Model,Cesium3DTileset,Resource,Credit,ClippingPolygon,ClippingPolygonCollection,PolylineOutlineMaterialProperty,Axis} from '@cesium/engine';
import {Matrix4,Cartesian3,Math as CMath,BoundingSphere,HeadingPitchRange,Color,PolygonHierarchy,ArcType} from '@cesium/core';
const $=id=>document.getElementById(id),job=new URLSearchParams(location.search).get('job');
let viewer,data,geo,config,localModel,google,mode='simulation',state={parcel:true,flow:true,buildings:true,points:true,vegetation:true};
const parcelEntities=[],flowEntities=[];
async function api(path){const r=await fetch(path);const v=await r.json();if(!r.ok)throw Error(v.error||'Source unavailable');return v;}
function point(x,n,z){return Matrix4.multiplyByPoint(Matrix4.fromArray(geo.model_matrix),new Cartesian3(x,n,z),new Cartesian3());}
function camera(kind){const z=groundAt(data,0,0);viewer.camera.flyToBoundingSphere(new BoundingSphere(point(0,0,z+2),55),{duration:.6,offset:new HeadingPitchRange(CMath.toRadians(28),CMath.toRadians(kind==='top'?-89:-35),kind==='context'?550:kind==='top'?360:160)});}
function notice(){ $('notice').textContent=config.google.enabled?'Measured LiDAR patch · Google 3D visual context available':'Measured LiDAR / aerial scene · Google 3D tiles are not configured';}
function sync(){if(localModel){localModel.show=mode!=='neighbourhood';for(const [name,show] of [['Measured DSM roofs',state.buildings],['Display building sides',state.buildings],['buildings',state.points&&state.buildings],['vegetation',state.points&&state.vegetation],['other',state.points]]){try{localModel.getNode(name).show=show;}catch{}}}parcelEntities.forEach(e=>e.show=state.parcel&&mode!=='neighbourhood');flowEntities.forEach(e=>e.show=state.flow&&mode!=='neighbourhood');if(google){google.show=mode!=='simulation';google.clippingPolygons.enabled=mode==='hybrid';}viewer.scene.requestRender();}
async function loadGoogle(){
  if(!config.google.enabled)return;
  try{google=await Cesium3DTileset.fromUrl(new Resource({url:'https://tile.googleapis.com/v1/3dtiles/root.json',queryParameters:{key:config.google.browser_key},credits:[new Credit('<img src="/google-maps-credit.png" height="19" alt="Google Maps">',true)]}),{maximumScreenSpaceError:12,cacheBytes:128*1024*1024,maximumCacheOverflowBytes:32*1024*1024,showCreditsOnScreen:true});
    if(ClippingPolygonCollection.isSupported(viewer.scene)){const g=data.grid;google.clippingPolygons=new ClippingPolygonCollection({polygons:[new ClippingPolygon({positions:[[g.west,g.north],[g.west+g.cols*g.cell_m,g.north],[g.west+g.cols*g.cell_m,g.north-g.rows*g.cell_m],[g.west,g.north-g.rows*g.cell_m]].map(([x,n])=>point(x,n,0))})]});viewer.scene.primitives.add(google);mode='hybrid';sync();}
    else{$('notice').textContent='Google clipping is unsupported on this device; measured LiDAR remains available.';google.destroy();google=null;}
  }catch{$('notice').textContent='Google tiles unavailable. Check browser-key access, billing and coverage.';}
}
async function start(){
  [data,config]=await Promise.all([api(`/api/jobs/${job}/scene`),api('/api/viewer-config')]);geo=await api(`/api/jobs/${job}/georeference`);if(!geo.available)throw Error(geo.reason);
  $('place').textContent=data.address;const [lon,lat]=data.wgs84;$('earth-link').href=`https://earth.google.com/web/@${lat},${lon},180a,500d,35y,0h,0t,0r`;$('street-link').href=`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`;
  viewer=new CesiumWidget('earth',{globe:false,baseLayer:false,requestRenderMode:true,maximumRenderTimeChange:Infinity,contextOptions:{webgl:{alpha:false}}});viewer.scene.backgroundColor=Color.fromCssColorString('#d8e3e7');viewer.scene.sun.show=false;viewer.scene.moon.show=false;viewer.scene.skyBox.show=false;viewer.resolutionScale=Math.min(devicePixelRatio,1.5)/devicePixelRatio;
  let texture;if(data.imagery){texture=await new THREE.TextureLoader().loadAsync(`/api/jobs/${job}/files/scene-aerial.jpg`);texture.colorSpace=THREE.SRGBColorSpace;}
  const meshes=siteMeshes(data,texture);const cloud=await api(`/api/jobs/${job}/points`);const points=classifiedCloud(cloud);
  // glTF POINTS use unlit vertex colours; PointsMaterial display sizing is handled
  // by Cesium, while the same measured vertices and linear colours are retained.
  for(const object of points.children)object.material=new THREE.MeshBasicMaterial({vertexColors:true});meshes.group.add(points);
  const binary=await new GLTFExporter().parseAsync(meshes.group,{binary:true,onlyVisible:true});const url=URL.createObjectURL(new Blob([binary],{type:'model/gltf-binary'}));
  try{localModel=await Model.fromGltfAsync({url,modelMatrix:Matrix4.fromArray(geo.model_matrix),upAxis:Axis[EARTH_GLTF_AXES.upAxis],forwardAxis:Axis[EARTH_GLTF_AXES.forwardAxis],allowPicking:true,credit:'LINZ LiDAR & aerial · CC BY 4.0',showCreditsOnScreen:true});viewer.scene.primitives.add(localModel);}finally{URL.revokeObjectURL(url);}
  const addLine=(path,color,width)=>{const positions=[];for(let i=1;i<path.length;i++){const a=path[i-1],b=path[i],steps=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])));for(let j=0;j<=steps;j++){const t=j/steps,x=a[0]+(b[0]-a[0])*t,n=a[1]+(b[1]-a[1])*t;positions.push(point(x,n,groundAt(data,x,n)+.35));}}return viewer.entities.add({polyline:{positions,width,material:Color.fromCssColorString(color)}});};
  for(const path of parcelPaths(data)){
    const positions=path.map(([x,n,z])=>point(x,n,z));
    const material=new PolylineOutlineMaterialProperty({color:Color.fromCssColorString('#ffda45'),outlineColor:Color.fromCssColorString('#152f38'),outlineWidth:.5});
    parcelEntities.push(viewer.entities.add({name:'Selected property boundary',polyline:{positions,width:3,arcType:ArcType.NONE,material,depthFailMaterial:material}}));
    parcelEntities.push(viewer.entities.add({name:'Selected property area',polygon:{hierarchy:new PolygonHierarchy(positions.slice(0,-1)),perPositionHeight:true,arcType:ArcType.NONE,material:Color.fromCssColorString('#ffda45').withAlpha(.06)}}));
  }
  for(const path of data.overland_paths)flowEntities.push(addLine(path,'#00cde4',3));
  localModel.readyEvent.addEventListener(()=>{sync();camera('property');document.body.dataset.ready='true';parent.postMessage({type:'earth-ready',job},location.origin);});
  notice();document.body.classList.toggle('embedded',new URLSearchParams(location.search).has('embed'));camera('property');$('load-state').textContent='';sync();await loadGoogle();
}
window.addEventListener('message',e=>{if(e.origin!==location.origin||e.data?.job!==job||e.data.type!=='terrain-layers')return;state=e.data;if(viewer)sync();});
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{if(b.dataset.mode!=='simulation'&&!google){$('notice').textContent='Google 3D requires a configured browser key. The measured scene remains available.';return;}mode=b.dataset.mode;sync();});
$('focus').onclick=()=>camera('property');$('context').onclick=()=>camera('context');$('top').onclick=()=>camera('top');$('tour').hidden=true;
$('sources').onclick=async()=>{$('source-dialog').showModal();$('source-rows').textContent='Loading recorded source metadata…';try{const report=await api(`/api/jobs/${job}/sources`);$('source-rows').replaceChildren();for(const source of report.layers){const row=document.createElement('div');row.className='source-row';const title=document.createElement('strong');title.textContent=source.title;const dates=document.createElement('small');dates.textContent=source.capture_dates?.length?source.capture_dates.map(v=>v.slice(0,10)).join(' → '):'Capture date not verified';row.append(title,dates);$('source-rows').append(row);}$('alignment').textContent=`NZTM2000 / NZVD2016 → geocentric display. Numerical frame residual ${(geo.numerical_residual_max_m*1000).toFixed(1)} mm. ${geo.limitations}`;}catch(e){$('source-rows').textContent=e.message;}};
$('close-sources').onclick=()=>$('source-dialog').close();$('check-providers').hidden=true;
start().catch(e=>{$('fatal').hidden=false;$('fatal-message').textContent=e.message;$('fallback').href=`/terrain3d.html?job=${job}`;});
