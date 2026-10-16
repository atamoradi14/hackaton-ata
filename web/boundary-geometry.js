import * as THREE from 'three';
import {Line2} from 'three/addons/lines/Line2.js';
import {LineGeometry} from 'three/addons/lines/LineGeometry.js';
import {LineMaterial} from 'three/addons/lines/LineMaterial.js';
import {groundAt,localPosition} from './site-geometry.js';

export function propertyFrame(data){const vertices=(data.parcel||[]).flat();if(!vertices.length)return {east:0,north:0,span:50};const xs=vertices.map(p=>p[0]),ns=vertices.map(p=>p[1]);return {east:(Math.min(...xs)+Math.max(...xs))/2,north:(Math.min(...ns)+Math.max(...ns))/2,span:Math.max(20,Math.max(...xs)-Math.min(...xs),Math.max(...ns)-Math.min(...ns))};}

// Authoritative registry coordinates are absolute NZTM, unlike the scene's offsets.
export function sampleBoundary(endpoints,data,lift=.6){
  const origin=data.origin_nztm,g=data.grid,points=[];
  const a=endpoints[0].map((v,i)=>v-origin[i]),b=endpoints[1].map((v,i)=>v-origin[i]);
  const count=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/g.cell_m));
  for(let i=0;i<=count;i++){const t=i/count,x=a[0]+(b[0]-a[0])*t,n=a[1]+(b[1]-a[1])*t;
    if(x<g.west||x>g.west+g.cols*g.cell_m||n>g.north||n<g.north-g.rows*g.cell_m)continue;
    points.push([x,n,groundAt(data,x,n)+lift]);}
  return points;
}
export function objectPaths(geometry,data){
  if(!geometry)return [];
  if(geometry.type==='Point'||geometry.type==='MultiPoint'){const pts=geometry.type==='Point'?[geometry.coordinates]:geometry.coordinates;return pts.flatMap(([x,n])=>[sampleBoundary([[x-.7,n],[x+.7,n]],data,.8),sampleBoundary([[x,n-.7],[x,n+.7]],data,.8)]).filter(p=>p.length>1);}
  if(geometry.type==='GeometryCollection')return geometry.geometries.flatMap(g=>objectPaths(g,data));
  const raw=geometry.type==='LineString'?[geometry.coordinates]:geometry.type==='MultiLineString'||geometry.type==='Polygon'?geometry.coordinates:geometry.type==='MultiPolygon'?geometry.coordinates.flat():[];
  const paths=[];
  for(const ring of raw){let current=[];for(let i=1;i<ring.length;i++){
    // Clip each original segment to the scene rectangle before sampling. Never
    // clamp a distant catchment outline onto the edge of the local terrain.
    const a=ring[i-1],b=ring[i],o=data.origin_nztm,g=data.grid;
    let lo=0,hi=1;const dx=b[0]-a[0],dy=b[1]-a[1];let valid=true;
    for(const [p,q] of [[-dx,a[0]-o[0]-g.west],[dx,o[0]+g.west+g.cols*g.cell_m-a[0]],[-dy,a[1]-o[1]-(g.north-g.rows*g.cell_m)],[dy,o[1]+g.north-a[1]]]){
      if(p===0){if(q<0)valid=false;continue;}const r=q/p;if(p<0)lo=Math.max(lo,r);else hi=Math.min(hi,r);}
    if(!valid||lo>hi){if(current.length>1)paths.push(current);current=[];continue;}
    const samples=sampleBoundary([[a[0]+lo*dx,a[1]+lo*dy],[a[0]+hi*dx,a[1]+hi*dy]],data,.8);
    if(current.length&&samples.length&&Math.hypot(current.at(-1)[0]-samples[0][0],current.at(-1)[1]-samples[0][1])>.01){paths.push(current);current=[];}
    current.push(...samples);}
    if(current.length>1)paths.push(current);
  }return paths;
}
export function overlayLine(path,color,base,width=2){
  const geometry=new LineGeometry();geometry.setPositions(path.flatMap(([x,n,z])=>localPosition(x,n,z,base)));
  const line=new Line2(geometry,new LineMaterial({color,linewidth:width,depthTest:false,depthWrite:false,transparent:true}));line.renderOrder=1102;return line;
}
export function boundaryOverlay(record,data,base=0,labels=true){
  const group=new THREE.Group();group.name='Editable cadastral segments';group.userData.edges=[];
  record.boundary_segments.forEach((edge,i)=>{
    const path=sampleBoundary(edge.endpoints_nztm,data);if(path.length<2)return;
    const back=overlayLine(path,'#102630',base,3.5),line=overlayLine(path,'#f0f2ce',base,1.8);back.renderOrder=1101;
    line.userData={edgeId:edge.id,crossed:edge.flow_path.crossed_by_flow_path};group.add(back,line);
    let label;
    if(labels&&typeof document!=='undefined'){
      const canvas=document.createElement('canvas');canvas.width=64;canvas.height=64;const ctx=canvas.getContext('2d');
      ctx.fillStyle='#142f38';ctx.beginPath();ctx.roundRect(5,5,54,54,14);ctx.fill();ctx.strokeStyle='#f5e9aa';ctx.lineWidth=3;ctx.stroke();ctx.fillStyle='#fff4b7';ctx.font='bold 34px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(i+1),32,33);
      const texture=new THREE.CanvasTexture(canvas);label=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,depthWrite:false,transparent:true}));label.position.set(...localPosition(...path[Math.floor(path.length/2)],base));label.renderOrder=1103;group.add(label);
    }
    group.userData.edges.push({id:edge.id,path,line,back,label});
  });return group;
}
export function selectBoundary(group,id){for(const edge of group?.userData.edges||[]){const active=edge.id===id;edge.line.material.color.set(active?'#ffda45':edge.line.userData.crossed?'#f3a261':'#f0f2ce');edge.line.material.linewidth=active?3:1.8;edge.back.material.linewidth=active?4.5:3.5;}}
export function resizeBoundary(group,width,height){group?.traverse(o=>{if(o.material?.isLineMaterial)o.material.resolution.set(width,height);});}
export function disposeOverlay(group){group?.traverse(o=>{o.geometry?.dispose();o.material?.map?.dispose();o.material?.dispose();});}
export function pixelDistance(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);}
export function pickBoundary(group,camera,rect,clientX,clientY,base=0){
  if(!group?.visible)return null;let best=11,selected=null;
  for(const edge of group.userData.edges){let previous=null;for(const p of edge.path){const q=new THREE.Vector3(...localPosition(...p,base)).project(camera);
    if(q.z< -1||q.z>1){previous=null;continue;}const next=[(q.x+1)*rect.width/2,(1-q.y)*rect.height/2];
    if(previous){const d=pixelDistance([clientX-rect.left,clientY-rect.top],previous,next);if(d<best){best=d;selected=edge.id;}}previous=next;}
  }return selected;
}
