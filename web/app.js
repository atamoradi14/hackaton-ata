'use strict';
const $ = id => document.getElementById(id);
const icons = {
  map:'<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/>',
  waves:'<path d="M2 6c3-5 5 5 8 0s5 5 8 0 4 0 4 0M2 12c3-5 5 5 8 0s5 5 8 0 4 0 4 0M2 18c3-5 5 5 8 0s5 5 8 0 4 0 4 0"/>',
  layers:'<path d="m12 3 10 5-10 5L2 8l10-5Zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
  search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  target:'<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 1v4m0 14v4M1 12h4m14 0h4"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M20 4l-2 2M6 18l-2 2"/>',
  pin:'<path d="M19 10c0 5-7 12-7 12S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
  check:'<path d="m5 12 4 4 10-10"/>',
  compass:'<circle cx="12" cy="12" r="10"/><path d="m16 8-3 5-5 3 3-5 5-3Z"/>',
  terrain:'<path d="m2 20 7-13 4 7 3-5 6 11H2ZM7 11l2 3 2-3"/>',
  points:'<circle cx="6" cy="6" r="1"/><circle cx="12" cy="4" r="1"/><circle cx="18" cy="7" r="1"/><circle cx="4" cy="13" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="20" cy="14" r="1"/><circle cx="7" cy="20" r="1"/><circle cx="15" cy="19" r="1"/>',
  sliders:'<path d="M5 3v7m0 4v7M12 3v12m0 4v2M19 3v3m0 4v11"/><path d="M2 10h6M9 15h6M16 6h6"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  play:'<path d="m8 4 12 8-12 8V4Z"/>',
  pause:'<path d="M8 5v14M16 5v14"/>'
};
function icon(name) {return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.layers}</svg>`;}
function decorate(root=document) {root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
const esc = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
decorate();
let csrf='', candidate=null, job=null, generation=0, pollTimer=null, currentProfile=null, profileDirection='east';
const map = L.map('map',{zoomControl:true,preferCanvas:true,minZoom:5,maxZoom:20}).setView([-36.83,174.75],11);
map.createPane('parcelEvidence');map.getPane('parcelEvidence').style.zIndex=450;
let dark=false, tiles, tileErrors=0;
function setBasemap() {
  if(tiles) map.removeLayer(tiles);
  tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxNativeZoom:19,maxZoom:20,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}).addTo(map);
  map.getPane('tilePane').style.filter=dark?'invert(.88) hue-rotate(145deg) saturate(.45) brightness(.8)':'saturate(.45) contrast(.92)';
  tiles.on('tileerror',()=>{if(++tileErrors>4)$('tile-notice').hidden=false;});
  tiles.on('tileload',()=>{$('tile-notice').hidden=true;tileErrors=0;});
}
setBasemap(); L.control.scale({imperial:false,position:'bottomright'}).addTo(map);
let parcelLayer, marker; const overlays={}, pendingLayers=new Set();
const layerSpecs=[
  ['buildings','Building footprints','#859881',true],['overland_flow','Mapped flow paths','#399da1',true],
  ['pipes','Stormwater pipes','#9471ac',false],['catchpits','Catchpits','#bca264',false],
  ['manholes','Manholes / chambers','#b29262',false],['connections','Stormwater connections','#9c81b3',false],
  ['flood_plains','Council flood plains','#5e94ae',false],['flood_prone','Council flood-prone areas','#c08078',false],
  ['terrain','Ground elevation','#88a876',false]
];
let enabledLayers=new Set(), availableLayers=new Set(), terrainDisplay=null;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,4500);}
async function api(path, data){
  const options=data?{method:'POST',headers:{'Content-Type':'application/json','X-Floodtwin-Token':csrf},body:JSON.stringify(data)}:{};
  const response=await fetch(path,options);const result=await response.json();
  if(!response.ok)throw new Error(result.error || 'The request could not be completed.');
  return result;
}
function resetStudy(){
  sessionStorage.removeItem('auckland-flowlab-workspace');
  clearTimeout(pollTimer);job=null;candidate=null;currentProfile=null;terrainDisplay=null;enabledLayers.clear();availableLayers.clear();
  for(const key of Object.keys(overlays)){map.removeLayer(overlays[key]);delete overlays[key];}
  if(parcelLayer){map.removeLayer(parcelLayer);parcelLayer=null;}if(marker){map.removeLayer(marker);marker=null;}
  ['confirmation-panel','job-panel','detail-card','map-legend'].forEach(id=>$(id).hidden=true);
  $('welcome-panel').hidden=false;$('map-title').textContent='Choose your study area';
  $('map-status').innerHTML='<span></span> Awaiting address';$('map-caption').innerHTML='<span class="caption-dot"></span>Auckland / Tāmaki Makaurau';
  $('layer-count').textContent='—';$('resolution').textContent='—';$('point-count').textContent='—';
  $('coordinate-label').textContent='Drag to explore · Scroll to zoom';
  renderLayerMenu();
}
function showParcel(data){
  if(parcelLayer)map.removeLayer(parcelLayer);if(marker)map.removeLayer(marker);
  parcelLayer=L.geoJSON(data.parcel,{pane:'parcelEvidence',style:{color:'#416c47',weight:2.5,fillColor:'#b4d384',fillOpacity:.4}}).addTo(map);
  parcelLayer.bindTooltip('Official primary parcel · not a surveyed fence');
  const [lon,lat]=data.site.lonlat;
  marker=L.marker([lat,lon],{icon:L.divIcon({className:'parcel-marker',html:'',iconSize:[16,16],iconAnchor:[8,8]})}).addTo(map);
  marker.bindTooltip(esc(data.site.address));
  map.fitBounds(parcelLayer.getBounds(),{padding:[65,65],maxZoom:19});
  $('coordinate-label').textContent=`${Math.abs(lat).toFixed(5)}° S · ${lon.toFixed(5)}° E`;
  $('map-caption').innerHTML='<span class="caption-dot"></span>Official address & parcel <span class="caption-small">LINZ / CC-BY-4.0</span>';
  $('map-title').textContent=data.site.address.split(',')[0];
}
let suggestionTimer=null,suggestionRequest=0;
function hideSuggestions(){$('address-suggestions').hidden=true;$('address-suggestions').replaceChildren();}
async function loadSuggestions(){
  const address=$('address').value.trim(),request=++suggestionRequest;
  if(address.length<3){hideSuggestions();return;}
  try{
    const result=await api('/api/address-suggestions',{address});if(request!==suggestionRequest)return;
    const choices=result.suggestions||[];if(!choices.length){hideSuggestions();return;}
    $('address-suggestions').replaceChildren(...choices.map(choice=>{const button=document.createElement('button');button.type='button';button.role='option';button.textContent=choice.address;button.onclick=()=>{$('address').value=choice.address;hideSuggestions();$('search-form').requestSubmit();};return button;}));
    $('address-suggestions').hidden=false;
  }catch(error){if(request===suggestionRequest){hideSuggestions();$('search-help').textContent='Address suggestions are unavailable. Check the local provider connection or enter the full address.';}}
}
$('address').addEventListener('input',()=>{generation++;resetStudy();$('search-help').classList.remove('error');$('search-help').textContent='Choose an official suggestion, then review and confirm the parcel.';clearTimeout(suggestionTimer);suggestionTimer=setTimeout(loadSuggestions,250);});
$('address').addEventListener('blur',()=>setTimeout(hideSuggestions,150));
$('search-form').addEventListener('submit',async event=>{
  event.preventDefault();hideSuggestions();const address=$('address').value.trim(), request=++generation;resetStudy();
  $('search-button').disabled=true;$('search-button').innerHTML='Locating…';$('search-help').classList.remove('error');
  $('search-help').textContent='Checking the official LINZ address and point-covering parcel…';
  try{
    const result=await api('/api/search',{address});if(request!==generation)return;
    candidate=result;showParcel(result);$('welcome-panel').hidden=true;$('confirmation-panel').hidden=false;
    $('candidate-address').textContent=result.site.address;$('candidate-address-id').textContent=result.site.address_id;$('candidate-parcel-id').textContent=result.site.parcel_id;
    $('map-status').innerHTML='<span></span> Review property';$('search-help').textContent='Exact official match found. Confirm the highlighted parcel to start preparation.';
    if(innerWidth<820)$('confirmation-panel').scrollIntoView({behavior:'smooth',block:'center'});
  }catch(error){if(request===generation){$('search-help').textContent=error.message;$('search-help').classList.add('error');}}
  finally{$('search-button').disabled=false;$('search-button').innerHTML='Find address '+icon('arrow');}
});
$('change-address').onclick=()=>{$('address').focus();$('address').select();};
$('confirm-button').onclick=async()=>{
  if(!candidate)return;const request=generation, id=candidate.id;$('confirm-button').disabled=true;
  try{
    const result=await api('/api/confirm',{id,address:$('address').value.trim(),confirmed:true});
    if(request!==generation)return;job=result;sessionStorage.setItem('auckland-flowlab-workspace',result.id);$('confirmation-panel').hidden=true;$('job-panel').hidden=false;
    $('map-legend').hidden=false;$('map-status').innerHTML='<span></span> Confirmed';
    $('search-help').textContent='This property is confirmed. Preparation runs automatically in its own workspace.';
    renderJob(result);poll(id,request);
  }catch(error){toast(error.message);}finally{$('confirm-button').disabled=false;}
};
async function poll(id,request){
  if(request!==generation)return;
  try{const result=await api(`/api/jobs/${id}`);if(request!==generation)return;job=result;renderJob(result);
    if(result.status==='preparing')pollTimer=setTimeout(()=>poll(id,request),1200);
  }catch(error){if(request===generation){toast(error.message);pollTimer=setTimeout(()=>poll(id,request),3000);}}
}
function renderJob(data){
  $('job-address').textContent=data.site.address;
  const ready=data.steps.filter(s=>['done','cached'].includes(s.status)).length;
  const percent=Math.round(ready/data.steps.length*100);
  $('progress-percent').textContent=percent+'%';$('progress-fill').style.width=percent+'%';
  $('progress-label').textContent=data.status==='preparing'?'Preparing your evidence':ready===data.steps.length?'Evidence prepared':'Preparation needs attention';
  $('steps').innerHTML=data.steps.map(s=>`<div class="step ${esc(s.status)}" title="${esc(s.detail || s.description)}"><span class="step-dot">${['done','cached'].includes(s.status)?icon('check'):s.status==='blocked'?'!':''}</span><span>${esc(s.name)}</span><span class="step-status">${({cached:'recorded',done:'ready',queued:'queued',running:'working',blocked:'blocked',partial:'partial'})[s.status]}</span></div>`).join('');
  $('map-status').innerHTML='<span></span> '+(data.status==='preparing'?'Preparing evidence':'GIS evidence');
  $('map-caption').innerHTML='<span class="caption-dot"></span>Confirmed study area <span class="caption-small">GIS and terrain evidence</span>';
  const layers=data.gis?.layers || {};
  $('layer-count').textContent=(Object.values(layers).reduce((n,l)=>n+(l.count||0),0)+(data.buildings?.count||0)).toLocaleString();
  if(data.terrain)$('resolution').textContent='1 m';
  if(data.pointcloud)$('point-count').textContent=data.pointcloud.crop_point_count.toLocaleString();
  const previous=[...availableLayers].join();
  availableLayers=new Set(layerSpecs.filter(([name])=>name==='terrain'?data.available_files.includes('dem_discovery.tif'):data.available_files.includes(name+'.gpkg')).map(s=>s[0]));
  if(previous!==[...availableLayers].join()){
    renderLayerMenu();
    for(const [name,,,defaultOn] of layerSpecs)if(defaultOn&&availableLayers.has(name)&&!overlays[name]){enabledLayers.add(name);loadLayer(name);}
  }
  if(data.available_files.includes('terrain-cross-sections.csv')){
    $('detail-card').hidden=false;
    if(!currentProfile)loadProfiles(data.id,generation);
  }
  $('open-lidar-3d').href=`/terrain3d.html?job=${data.id}`;
  $('open-earth-3d').href=`/hybrid.html?job=${data.id}`;
  let boundaries=$('boundary-records');if(!boundaries){boundaries=document.createElement('a');boundaries.id='boundary-records';boundaries.textContent='Boundary lines & nearby objects →';$('job-panel').append(boundaries);}boundaries.href=`/properties.html?job=${data.id}`;
  const sceneReady=['dem_discovery.tif','dsm_discovery.tif','pointcloud_crop.laz','buildings.gpkg'].every(file=>data.available_files.includes(file));
  $('open-lidar-3d').textContent=sceneReady?'Open 3D workspace →':'3D awaits terrain & LiDAR';
  if(!sceneReady)$('open-lidar-3d').removeAttribute('href');
  let retry=$('retry-preparation');
  if(!retry){retry=document.createElement('button');retry.id='retry-preparation';retry.className='primary';retry.textContent='Retry blocked data';$('job-panel').append(retry);retry.onclick=async()=>{if(!job)return;const id=job.id,request=generation;retry.disabled=true;try{const resumed=await api(`/api/jobs/${id}/retry-preparation`,{});if(request!==generation)return;job=resumed;renderJob(resumed);poll(id,request);}catch(error){toast(error.message);}finally{retry.disabled=false;}};}
  retry.hidden=data.status==='preparing'||!data.steps.some(step=>['blocked','partial'].includes(step.status));
  renderSources(data);
}
function renderLayerMenu(){
  $('map-legend').hidden=!job;
  $('map-legend').innerHTML='<i></i> Confirmed parcel'+(enabledLayers.has('overland_flow')&&overlays.overland_flow?'<span class="flow-line"></span> Mapped flow paths':'');
  $('terrain-legend').hidden=!(job&&terrainDisplay&&enabledLayers.has('terrain')&&overlays.terrain);
  if(terrainDisplay){$('terrain-low').textContent=terrainDisplay.low_m.toFixed(1);$('terrain-high').textContent=terrainDisplay.high_m.toFixed(1);}
  if(!$('layer-options').childElementCount)$('layer-options').innerHTML=layerSpecs.map(([name,label,color])=>`<label class="layer-option"><input type="checkbox" data-layer="${name}"><span style="color:${color}">●</span>${label}<small>pending</small></label>`).join('');
  $('layer-options').querySelectorAll('input').forEach(input=>{
    input.disabled=!availableLayers.has(input.dataset.layer);input.checked=enabledLayers.has(input.dataset.layer);
    input.parentElement.querySelector('small').textContent=availableLayers.has(input.dataset.layer)?'real data':'pending';
  });
  $('layer-options').querySelectorAll('input').forEach(input=>input.onchange=()=>{
    if(input.checked){enabledLayers.add(input.dataset.layer);loadLayer(input.dataset.layer);}
    else{enabledLayers.delete(input.dataset.layer);if(overlays[input.dataset.layer])map.removeLayer(overlays[input.dataset.layer]);}
    renderLayerMenu();
  });
}
renderLayerMenu();
async function loadLayer(name){
  if(!job)return;const id=job.id, request=generation, key=id+name;
  if(overlays[name]){if(enabledLayers.has(name))overlays[name].addTo(map);return;}
  if(pendingLayers.has(key))return;pendingLayers.add(key);
  try{
    let overlay,terrainInfo;
    if(name==='terrain'){
      const data=await api(`/api/jobs/${id}/terrain`);
      terrainInfo=data;
      overlay=L.imageOverlay(`/api/jobs/${id}/files/map-terrain.png`,data.bounds,{opacity:.75});
    }else{
      const data=await api(`/api/jobs/${id}/layers/${name}`), color=layerSpecs.find(s=>s[0]===name)[2];
      overlay=L.geoJSON(data,{style:{color,weight:name==='overland_flow'?1.6:.9,fillOpacity:name==='buildings'?.20:.14},
        pointToLayer:(feature,latlng)=>L.circleMarker(latlng,{radius:3,color,fillColor:color,fillOpacity:.8,weight:.8}),
        onEachFeature:(feature,layer)=>layer.bindTooltip(esc(layerSpecs.find(s=>s[0]===name)[1])+' · official map; not solver output')});
    }
    if(request!==generation||job?.id!==id)return;overlays[name]=overlay;
    if(terrainInfo)terrainDisplay=terrainInfo;
    if(enabledLayers.has(name))overlay.addTo(map);if(parcelLayer)parcelLayer.bringToFront();renderLayerMenu();
  }catch(error){if(request===generation){enabledLayers.delete(name);renderLayerMenu();toast(error.message);}}
  finally{pendingLayers.delete(key);}
}
$('layers-button').onclick=()=>{$('layer-menu').hidden=!$('layer-menu').hidden;$('layers-button').setAttribute('aria-expanded',String(!$('layer-menu').hidden));};
$('basemap').onclick=()=>{dark=!dark;setBasemap();};
$('recenter').onclick=()=>{if(parcelLayer)map.fitBounds(parcelLayer.getBounds(),{padding:[65,65],maxZoom:18});else map.setView([-36.83,174.75],11);};
map.on('moveend',()=>{if(!candidate&&!job){const center=map.getCenter();$('coordinate-label').textContent=`${Math.abs(center.lat).toFixed(4)}° S · ${center.lng.toFixed(4)}° E · zoom ${map.getZoom()}`;}});
function selectTab(name){
  for(const tab of ['profile','sources']){$(tab+'-content').hidden=tab!==name;$(tab+'-tab').classList.toggle('active',tab===name);$(tab+'-tab').setAttribute('aria-selected',String(tab===name));}
}
for(const name of ['profile','sources'])$(name+'-tab').onclick=()=>selectTab(name);
function renderSources(data){
  const sources=[['Recorded aerial crop','Survey dates, original imagery resolution, display resampling and clipped coverage','scene-aerial.json'],
    ['Official site match','LINZ address '+data.site.address_id+' · parcel '+data.site.parcel_id,'site_manifest.json'],
    ['Council GIS','Mapped assets and flood layers; capacity, inverts and connectivity unverified','gis-discovery-manifest.json'],
    ['Ground / surface survey','1 m source grid · EPSG:2193 · NZVD2016 · source metadata and QC','terrain-qc.json'],
    ['Native LiDAR crop','Classifications preserved; no automatic fence or wall assignment','pointcloud-manifest.json'],
    ['Ground consistency','Same-survey comparison, not independent accuracy validation','ground-dem-qc.json']];
  $('sources-content').innerHTML=sources.filter(s=>data.available_files.includes(s[2])).map(([name,detail,file])=>`<div class="source-row"><div>${name}<small>${esc(detail)}</small></div><a href="/api/jobs/${data.id}/files/${file}" target="_blank" rel="noopener">View provenance ↗</a></div>`).join('')+
    '<div class="source-actions">'+[['dem_discovery.tif','DEM GeoTIFF'],['dsm_discovery.tif','DSM GeoTIFF'],['pointcloud_crop.laz','LiDAR LAZ'],['terrain-cross-sections.csv','Profiles CSV'],['parcel.geojson','Parcel GeoJSON'],['overview.html','Evidence report']].filter(s=>data.available_files.includes(s[0])).map(([file,label])=>`<a href="/api/jobs/${data.id}/files/${file}" ${file.endsWith('.html')?'target="_blank" rel="noopener"':'download'}>${label} ↗</a>`).join('')+'</div><p class="small-muted">Source acknowledgements: LINZ, Woolpert, Regional Software Holdings Limited, OpenTopography and Auckland Council. Source permissions and uncertainties are recorded in each manifest.</p>';
}
async function loadProfiles(id,request){
  try{const result=await api(`/api/jobs/${id}/profiles`);if(request!==generation)return;currentProfile=result;drawProfile();}
  catch(error){if(request===generation)toast(error.message);}
}
function chart(x, series, limits, markerIndex){
  const small=innerWidth<820,width=small?450:900,font=small?12:9;
  const x0=small?35:45,x1=width-25,y0=22,y1=176,minX=x[0],maxX=x.at(-1),[minY,maxY]=limits;
  const px=value=>x0+(value-minX)/(maxX-minX)*(x1-x0),py=value=>y1-(value-minY)/(maxY-minY)*(y1-y0);
  let result='';
  for(let i=0;i<5;i++){const v=minY+(maxY-minY)*i/4,y=py(v);result+=`<path d="M${x0} ${y}H${x1}" stroke="#e6ecdf"/><text x="${x0-10}" y="${y+3}" text-anchor="end" fill="#829779" font-size="${font}">${v.toFixed(1)}</text>`;}
  for(let i=0;i<5;i++){const v=minX+(maxX-minX)*i/4;result+=`<text x="${px(v)}" y="198" text-anchor="middle" fill="#829779" font-size="${font}">${Math.round(v)}</text>`;}
  for(const s of series){const d=x.map((v,i)=>(i?'L':'M')+px(v).toFixed(2)+' '+py(s.values[i]).toFixed(2)).join(' ');result+=`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.2"/>`;
    if(markerIndex!=null)result+=`<circle cx="${px(x[markerIndex])}" cy="${py(s.values[markerIndex])}" r="4" fill="${s.color}" stroke="white" stroke-width="2"/>`;
  }
  if(markerIndex!=null)result+=`<path d="M${px(x[markerIndex])} ${y0}V${y1}" stroke="#709361" stroke-dasharray="3 4" opacity=".5"/>`;
  return result;
}
function drawProfile(index){if(!currentProfile)return;const values=currentProfile[profileDirection+'_m'],lo=Math.floor(Math.min(...values)),hi=Math.ceil(Math.max(...values))+1;
  $('profile-chart').setAttribute('viewBox',`0 0 ${innerWidth<820?450:900} 210`);
  $('profile-chart').innerHTML=chart(currentProfile.offset_m,[{values,color:'#698e64'}],[lo,hi],index);
  if(index!=null)$('profile-readout').textContent=`${currentProfile.offset_m[index]} m offset · ${values[index].toFixed(3)} m NZVD2016`;
}
for(const direction of ['east','north'])$(direction+'-profile').onclick=()=>{profileDirection=direction;for(const d of ['east','north'])$(d+'-profile').classList.toggle('active',d===direction);drawProfile();};
$('profile-chart').addEventListener('pointermove',event=>{if(!currentProfile)return;const width=innerWidth<820?450:900,x0=width===450?35:45,rect=$('profile-chart').getBoundingClientRect(),local=(event.clientX-rect.left)/rect.width*width;const index=Math.max(0,Math.min(currentProfile.offset_m.length-1,Math.round((local-x0)/(width-25-x0)*(currentProfile.offset_m.length-1))));drawProfile(index);});
document.querySelectorAll('.close-dialog').forEach(button=>button.onclick=()=>button.closest('dialog').close());
$('evidence-nav').onclick=()=>{if(!job||!currentProfile){toast('Confirm a property and prepare its data to explore site evidence.');return;}selectTab('sources');$('evidence-dialog').showModal();};
$('workspace-nav').onclick=()=>{window.scrollTo({top:0,behavior:'smooth'});};
window.addEventListener('resize',drawProfile);
api('/api/bootstrap').then(async data=>{
  csrf=data.csrf;if(generation!==0)return;
  const restoreGeneration=generation;$('address').value=data.default_address;
  const previous=new URLSearchParams(location.search).get('job')||sessionStorage.getItem('auckland-flowlab-workspace');
  if(previous){try{
    const restored=await api(`/api/jobs/${previous}`), parcel=await api(`/api/jobs/${previous}/layers/parcel`);
    if(restoreGeneration!==generation)return;
    job=restored;$('address').value=restored.site.address;showParcel({site:restored.site,parcel});
    $('welcome-panel').hidden=true;$('job-panel').hidden=false;$('map-legend').hidden=false;
    $('search-help').textContent='Restored this previously confirmed workspace.';renderJob(restored);
    if(restored.status==='preparing')poll(restored.id,generation);
  }catch{sessionStorage.removeItem('auckland-flowlab-workspace');}}
}).catch(error=>{$('search-help').textContent=error.message;$('search-help').classList.add('error');});
