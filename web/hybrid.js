import {terrainGLB} from './hybrid-model.js';
import {CesiumWidget,Cesium3DTileset,ClippingPolygonCollection,ClippingPolygon,Model,PerInstanceColorAppearance,Primitive,DirectionalLight,Resource,Credit,ScreenSpaceEventType,RequestScheduler,PolylineArrowMaterialProperty} from '@cesium/engine';
import {Matrix4,Cartesian3,Math as CesiumMath,BoundingSphere,HeadingPitchRange,Geometry,GeometryAttribute,ComponentDatatype,PrimitiveType,GeometryInstance,Color} from '@cesium/core';
const C={CesiumWidget,Cesium3DTileset,ClippingPolygonCollection,ClippingPolygon,Model,PerInstanceColorAppearance,Primitive,DirectionalLight,Matrix4,Cartesian3,Math:CesiumMath,BoundingSphere,HeadingPitchRange,Resource,Credit,Geometry,GeometryAttribute,ComponentDatatype,PrimitiveType,GeometryInstance,Color,ScreenSpaceEventType,RequestScheduler};
const H=globalThis.FlowHydraulics,$=id=>document.getElementById(id);
const query=new URLSearchParams(location.search),job=query.get('job'),embedded=query.has('embed');
let viewer,data,geo,config,csrf,localModel,google,water,wallKey='',walls=[],mode='hybrid',tour=false,tourRemove=null;
let latest=null,processing=false,renderKey='',googleAttempt=0,googleWarning='',sourceData;
const runs=new Map(),comparisons=new Map(),wallEntities=[],parcelEntities=[],arrowEntities=[];
let arrowKey='';
const api=async(path,body)=>{const r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Floodtwin-Token':csrf}:{},body:body?JSON.stringify(body):undefined});const v=await r.json();if(!r.ok)throw Error(v.error||'Data unavailable');return v;};
function parentMessage(type,extra={}){if(embedded)parent.postMessage({type,job,...extra},location.origin);}
function notice(){const parts=[];if(!config?.google.enabled)parts.push('LiDAR + acquired aerial imagery · Google surroundings not enabled.');if(googleWarning)parts.push(googleWarning);if(mode==='neighbourhood')parts.push('Visual context only. Select Hybrid or LiDAR for the simulation.');$('notice').textContent=parts.join(' ');}
function point(x,n,z){return C.Matrix4.multiplyByPoint(C.Matrix4.fromArray(geo.model_matrix),new C.Cartesian3(x,n,z),new C.Cartesian3());}
function ground(x,n){const g=data.grid,c=Math.max(0,Math.min(g.cols-1,Math.floor((x-g.west)/g.cell_m))),r=Math.max(0,Math.min(g.rows-1,Math.floor((g.north-n)/g.cell_m)));return g.elevations[r*g.cols+c];}
function camera(kind){stopTour();const height=ground(0,0),target=point(0,0,height+3);viewer.camera.flyToBoundingSphere(new C.BoundingSphere(target,kind==='context'?210:55),{duration:1.2,offset:new C.HeadingPitchRange(C.Math.toRadians(28),C.Math.toRadians(kind==='top'?-89:-38),kind==='context'?650:kind==='top'?390:155)});}
function stopTour(){tour=false;if(tourRemove){tourRemove();tourRemove=null;}if(viewer&&!viewer.isDestroyed())viewer.camera.lookAtTransform(C.Matrix4.IDENTITY);$('tour').textContent='Orbit';}
function orbit(){if(tour){stopTour();return;}tour=true;$('tour').textContent='Stop orbit';const center=point(0,0,ground(0,0)+3);let heading=viewer.camera.heading,last=performance.now();tourRemove=viewer.clock.onTick.addEventListener(()=>{const now=performance.now();if(now-last<32)return;heading+=(now-last)*.000035;last=now;viewer.camera.lookAt(center,new C.HeadingPitchRange(heading,-.55,190));viewer.scene.requestRender();});}
function presentation(value){
  mode=value;
  document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
  if(localModel)localModel.show=mode!=='neighbourhood';
  if(water)water.show=mode!=='neighbourhood';
  for(const entity of [...wallEntities,...parcelEntities,...arrowEntities])entity.show=mode!=='neighbourhood';
  if(google){google.show=mode!=='simulation';google.clippingPolygons.enabled=mode==='hybrid';}
  notice();viewer.scene.requestRender();parentMessage('flowlab-google-context',{active:!!google&&mode!=='simulation'});
}
async function loadGoogle(){
  if(!config.google.enabled)return;
  if(!C.ClippingPolygonCollection.isSupported(viewer.scene)){googleWarning='This device cannot clip 3D tiles safely. LiDAR mode remains available.';notice();return;}
  if(google){presentation(mode);return;}
  const attempt=++googleAttempt;$('load-state').textContent='Connecting Google context…';$('retry').hidden=true;
  try{
    const tile=await C.Cesium3DTileset.fromUrl(new C.Resource({url:'https://tile.googleapis.com/v1/3dtiles/root.json',queryParameters:{key:config.google.browser_key},credits:[new C.Credit('<img src="/google-maps-credit.png" alt="Google Maps" height="19">',true)]}),{
      showCreditsOnScreen:true,maximumScreenSpaceError:matchMedia('(max-width:650px)').matches?24:12,
      cacheBytes:128*1024*1024,maximumCacheOverflowBytes:32*1024*1024,preloadWhenHidden:false,
      cullRequestsWhileMoving:true,skipLevelOfDetail:true,show:false});
    if(attempt!==googleAttempt){tile.destroy();return;}
    // Clip exactly to the model's sampled edge centres to avoid a ground seam.
    const g=data.grid,ring=[[g.west+.5*g.cell_m,g.north-.5*g.cell_m],[g.west+(g.cols-.5)*g.cell_m,g.north-.5*g.cell_m],[g.west+(g.cols-.5)*g.cell_m,g.north-(g.rows-.5)*g.cell_m],[g.west+.5*g.cell_m,g.north-(g.rows-.5)*g.cell_m]];
    tile.clippingPolygons=new C.ClippingPolygonCollection({polygons:[new C.ClippingPolygon({positions:ring.map(([x,n])=>point(x,n,0))})]});
    tile.tileFailed.addEventListener(()=>{googleWarning='Some Google tiles are unavailable. The local measured terrain remains usable.';notice();$('retry').hidden=false;});
    tile.loadProgress.addEventListener((pending,processing)=>{$('load-state').textContent=pending||processing?`Streaming context · ${pending} pending`:' ';});
    google=viewer.scene.primitives.add(tile);googleWarning='';presentation(mode);
  }catch{googleWarning='Google context could not load. Check billing, coverage, key restrictions or connectivity.';$('retry').hidden=false;notice();}
  finally{$('load-state').textContent='';}
}
function cache(map,key,value,max=2){map.set(key,value);while(map.size>max)map.delete(map.keys().next().value);return value;}
async function run(id){if(!runs.has(id))cache(runs,id,api(`/api/jobs/${job}/hydraulics/${id}`));try{return await runs.get(id);}catch(e){runs.delete(id);throw e;}}
function renderWater(result,state,comparison,baseline){
  const key=JSON.stringify([result.id,state.frame,state.layer,state.comparison,state.editedWalls,state.opacity]);if(key===renderKey)return;renderKey=key;
  const begin=performance.now(),index=Math.max(0,Math.min(result.frames.length-1,Number(state.frame)||0)),f=result.frames[index],g=result.grid;
  const difference=['difference','max-difference','velocity-change'].includes(state.layer),layer=difference&&!comparison?'depth':state.layer;
  const values=H.values(result,index,layer,comparison),positions=[],colors=[],indices=[];
  let low=0,high=['difference','max-difference'].includes(layer)?.1:1;
  if(layer==='surface'){low=Infinity;high=-Infinity;g.bed.forEach((z,i)=>{if(g.active[i]){low=Math.min(low,z);high=Math.max(high,z);}});}
  const matrix=geo.model_matrix;
  for(let i=0;i<g.rows*g.cols;i++){
    const depth=layer==='maximum'?result.maximum_depth_mm[i]:difference&&baseline?Math.max(f.depth_mm[i],baseline.frames[index].depth_mm[i]):f.depth_mm[i];
    if(!g.active[i]||depth<1)continue;
    const r=Math.floor(i/g.cols),c=i%g.cols,x=g.west+c*g.cell_m,n=g.north-r*g.cell_m,z=g.bed[i]+depth/1000,a=positions.length/3;
    const color=H.color(values[i],difference?'difference':'depth',low,high);
    for(const [xx,nn] of [[x,n],[x+g.cell_m,n],[x,n-g.cell_m],[x+g.cell_m,n-g.cell_m]]){positions.push(matrix[0]*xx+matrix[4]*nn+matrix[8]*z+matrix[12],matrix[1]*xx+matrix[5]*nn+matrix[9]*z+matrix[13],matrix[2]*xx+matrix[6]*nn+matrix[10]*z+matrix[14]);colors.push(...color,Math.round(255*Math.max(.1,Math.min(.9,Number(state.opacity)||.6))));}
    indices.push(a,a+2,a+1,a+1,a+2,a+3);
  }
  if(water){viewer.scene.primitives.remove(water);water=null;}
  if(indices.length){const p=new Float64Array(positions),geometry=new C.Geometry({attributes:{position:new C.GeometryAttribute({componentDatatype:C.ComponentDatatype.DOUBLE,componentsPerAttribute:3,values:p}),color:new C.GeometryAttribute({componentDatatype:C.ComponentDatatype.UNSIGNED_BYTE,componentsPerAttribute:4,normalize:true,values:new Uint8Array(colors)})},indices:new Uint32Array(indices),primitiveType:C.PrimitiveType.TRIANGLES,boundingSphere:C.BoundingSphere.fromVertices(p)});
    water=viewer.scene.primitives.add(new C.Primitive({geometryInstances:new C.GeometryInstance({geometry}),appearance:new C.PerInstanceColorAppearance({flat:true,translucent:true,renderState:{depthTest:{enabled:true},depthMask:false}}),asynchronous:false,allowPicking:false,show:mode!=='neighbourhood'}));}
  $('water-state').textContent=`ACTUAL SFINCS · ${f.seconds} s · ${layer}${state.editedWalls?' · wall edits not solved':''}`;
  $('legend').textContent=difference?'Modified − baseline · comparison on wet-cell envelope':layer==='velocity'?'Velocity · 0 → 1 m/s':layer==='surface'?`Surface · ${low.toFixed(1)} → ${high.toFixed(1)} m NZVD2016`:'Depth · 0 → 1 m · dry cells omitted';
  document.body.dataset.frame=String(index);document.body.dataset.run=result.id;document.body.dataset.waterBuildMs=(performance.now()-begin).toFixed(1);
  viewer.scene.requestRender();
}
function renderWalls(value){
  const key=JSON.stringify(value);if(key===wallKey)return;wallKey=key;for(const entity of wallEntities)viewer.entities.remove(entity);wallEntities.length=0;
  walls=structuredClone(value||[]);
  for(const wall of walls){if(wall.enabled===false)continue;const p=wall.points;for(let i=1;i<p.length;i++){const a=p[i-1],b=p[i],vertices=[point(a[0],a[1],ground(a[0],a[1])),point(a[0],a[1],a[2]),point(b[0],b[1],b[2]),point(b[0],b[1],ground(b[0],b[1]))];wallEntities.push(viewer.entities.add({name:'Hypothetical finite crest',show:mode!=='neighbourhood',polygon:{hierarchy:vertices,perPositionHeight:true,material:C.Color.fromCssColorString('#efbb64').withAlpha(.9)}}));}}
  viewer.scene.requestRender();
}
async function applyState(state){
  renderWalls(state.walls||[]);
  if(!state.runId){if(water)viewer.scene.primitives.remove(water);water=null;renderKey='';for(const e of arrowEntities)viewer.entities.remove(e);arrowEntities.length=0;arrowKey='';$('water-state').textContent='No hydraulic scenario selected';return;}
  const selected=await run(state.runId);let baseline=null,comparison=null,result=selected;
  if(state!==latest)return;
  if(state.comparison){const {baseline:a,modified:b,before}=state.comparison,key=a+':'+b;baseline=await run(a);if(!comparisons.has(key))cache(comparisons,key,api(`/api/jobs/${job}/comparison`,{baseline:a,modified:b}),1);comparison=await comparisons.get(key);if(before)result=baseline;}
  if(state!==latest)return;
  if(result.status!=='done')throw Error('Select a completed native simulation');
  const akey=JSON.stringify([result.id,state.frame,state.arrows]);
  if(akey!==arrowKey){arrowKey=akey;for(const e of arrowEntities)viewer.entities.remove(e);arrowEntities.length=0;
    if(state.arrows){const g=result.grid,f=result.frames[Math.max(0,Math.min(result.frames.length-1,Number(state.frame)||0))],stride=Math.max(1,Math.ceil(Math.sqrt(g.rows*g.cols/128)));
      for(let r=0;r<g.rows;r+=stride)for(let c=0;c<g.cols;c+=stride){const i=r*g.cols+c,u=f.u_cm_s[i]/100,v=f.v_cm_s[i]/100,speed=Math.hypot(u,v);if(!g.active[i]||f.depth_mm[i]<1||speed<.01)continue;const x=g.west+(c+.5)*g.cell_m,n=g.north-(r+.5)*g.cell_m,z=g.bed[i]+f.depth_mm[i]/1000+.07,scale=Math.min(8,2+speed*4)/speed;arrowEntities.push(viewer.entities.add({show:mode!=='neighbourhood',polyline:{positions:[point(x,n,z),point(x+u*scale,n+v*scale,z)],width:5,material:new PolylineArrowMaterialProperty(C.Color.fromCssColorString('#123f59'))}}));}
    }document.body.dataset.arrows=String(arrowEntities.length);
  }
  renderWater(result,state,comparison,baseline);
}
async function drain(){if(processing||!viewer||!localModel)return;processing=true;try{let handled;do{handled=latest;if(handled)await applyState(handled);}while(handled!==latest);}catch{$('water-state').textContent='Saved results could not be verified. Select the scenario again.';}finally{processing=false;}}
window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==parent||event.data?.job!==job)return;if(event.data.type==='flowlab-state'){latest=event.data;drain();}if(event.data.type==='flowlab-visibility'){if(!event.data.visible)stopTour();if(viewer)viewer.useDefaultRenderLoop=!!event.data.visible;parentMessage('flowlab-google-context',{active:!!event.data.visible&&!!google&&mode!=='simulation'});}});
function sourceRows(value){sourceData=value;$('source-rows').replaceChildren();for(const source of value.layers){const row=document.createElement('div');row.className='source-row';const title=document.createElement('strong');title.textContent=source.title;row.append(title);const dates=document.createElement('span');dates.textContent='Captured: '+(source.capture_dates?.length?source.capture_dates.map(v=>v.slice(0,10)).join(' → '):'date not verified');row.append(dates);const check=document.createElement('small');const live=source.live_check;check.textContent=live?`${live.state} · checked ${new Date(live.checked_at).toLocaleString()}${live.cached?' · cached up to 1 hour':''}${live.recorded_metadata_matches===false?' · metadata changed; review needed':''}`:source.status;row.append(check);if(source.source){const link=document.createElement('a');link.href=source.source;link.rel='noopener';link.target='_blank';link.textContent='Source metadata';row.append(link);}$('source-rows').append(row);}}
async function start(){
  if(!job||!/^[a-f0-9]{32}$/.test(job))throw Error('Open Earth studio from a confirmed property workspace.');
  const boot=await api('/api/bootstrap');csrf=boot.csrf;
  [data,config]=await Promise.all([api(`/api/jobs/${job}/scene`),api('/api/viewer-config')]);
  geo=await api(`/api/jobs/${job}/georeference`);if(!geo.available)throw Error(geo.reason);
  $('place').textContent=data.address;$('fallback').href=`/scene.html?job=${job}`;
  C.RequestScheduler.maximumRequests=12;C.RequestScheduler.maximumRequestsPerServer=6;
  viewer=new C.CesiumWidget('earth',{globe:false,baseLayer:false,requestRenderMode:true,maximumRenderTimeChange:Infinity,contextOptions:{webgl:{alpha:false,preserveDrawingBuffer:false}}});
  viewer.resolutionScale=Math.min(devicePixelRatio,1.5)/devicePixelRatio;viewer.scene.backgroundColor=C.Color.fromCssColorString('#829e9e');viewer.scene.fog.enabled=false;viewer.scene.sun.show=false;viewer.scene.moon.show=false;viewer.scene.skyBox.show=false;viewer.targetFrameRate=30;
  viewer.scene.renderError.addEventListener(()=>{$('notice').textContent='This device could not render Earth studio reliably. Use the measured terrain studio.';$('fatal').hidden=false;$('fatal-message').textContent='The existing 3D studio remains available.';stopTour();});
  const sunlight=C.Cartesian3.subtract(point(-100,-150,300),point(0,0,0),new C.Cartesian3());C.Cartesian3.normalize(sunlight,sunlight);C.Cartesian3.negate(sunlight,sunlight);viewer.scene.light=new C.DirectionalLight({direction:sunlight,intensity:2});
  viewer.screenSpaceEventHandler.setInputAction(()=>stopTour(),C.ScreenSpaceEventType.LEFT_DOWN);
  const url=URL.createObjectURL(terrainGLB(data,new URL(`/api/jobs/${job}/files/scene-aerial.jpg`,location.origin).href));
  try{localModel=await C.Model.fromGltfAsync({url,modelMatrix:C.Matrix4.fromArray(geo.model_matrix),minimumPixelSize:0,allowPicking:true,credit:'Local patch: LINZ / Auckland Council · CC BY 4.0',showCreditsOnScreen:true});viewer.scene.primitives.add(localModel);}finally{URL.revokeObjectURL(url);}
  for(const ring of data.parcel)parcelEntities.push(viewer.entities.add({polyline:{positions:ring.map(([x,n])=>point(x,n,ground(x,n)+.15)),width:2,material:C.Color.fromCssColorString('#dbfa9d')}}));
  viewer.screenSpaceEventHandler.setInputAction(click=>{if(!viewer.scene.pickPositionSupported)return;const p=viewer.scene.pickPosition(click.position);if(!p)return;const inv=C.Matrix4.inverse(C.Matrix4.fromArray(geo.model_matrix),new C.Matrix4()),local=C.Matrix4.multiplyByPoint(inv,p,new C.Cartesian3());const g=data.grid;if(local.x<g.west||local.x>g.west+g.cols*g.cell_m||local.y>g.north||local.y<g.north-g.rows*g.cell_m){$('inspect').textContent='Outside measured patch · Google context is visual only';return;}$('inspect').textContent=`DEM ground ${ground(local.x,local.y).toFixed(2)} m NZVD2016 · E ${local.x.toFixed(1)} / N ${local.y.toFixed(1)} m`;},C.ScreenSpaceEventType.LEFT_CLICK);
  $('alignment').textContent=`NZGeoid2016 applied · N=${geo.geoid_separation_m.toFixed(3)} m · numerical frame residual ${(geo.numerical_residual_max_m*1000).toFixed(1)} mm. ${geo.limitations}`;
  camera('property');notice();document.body.dataset.ready='true';parentMessage('flowlab-ready');drain();
  sourceRows(await api(`/api/jobs/${job}/sources`));
  if(config.google.enabled)loadGoogle();
}
document.querySelectorAll('[data-mode]').forEach(button=>button.onclick=()=>{if(button.dataset.mode==='neighbourhood'&&!google){$('notice').textContent=config.google.enabled?'Google context is not ready. LiDAR and Hybrid remain available.':'Neighbourhood view needs the optional Google connection. LiDAR and Hybrid show the acquired local scene.';return;}presentation(button.dataset.mode);});
$('focus').onclick=()=>camera('property');$('context').onclick=()=>camera('context');$('top').onclick=()=>camera('top');$('tour').onclick=orbit;
$('sources').onclick=()=>$('source-dialog').showModal();$('close-sources').onclick=()=>$('source-dialog').close();
$('check-providers').onclick=async()=>{$('check-providers').disabled=true;$('source-check-status').textContent='Checking official metadata endpoints…';try{sourceRows(await api(`/api/jobs/${job}/source-check`,{}));$('source-check-status').textContent='Check complete. Existing terrain and saved simulations were preserved.';}catch{$('source-check-status').textContent='Online check unavailable. Acquired source records remain available.';}finally{$('check-providers').disabled=false;}};
$('retry').onclick=()=>{if(google){viewer.scene.primitives.remove(google);google=null;}loadGoogle();};
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopTour();if(viewer)viewer.useDefaultRenderLoop=!document.hidden;});
window.addEventListener('pagehide',()=>{stopTour();if(viewer&&!viewer.isDestroyed())viewer.destroy();viewer=null;parentMessage('flowlab-google-context',{active:false});});
start().catch(error=>{$('fatal').hidden=false;$('fatal-message').textContent=error.message;$('notice').textContent='';$('fallback').href=`/scene.html?job=${encodeURIComponent(job||'')}`;parentMessage('flowlab-hybrid-unavailable');});
