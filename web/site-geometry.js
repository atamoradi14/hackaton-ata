import * as THREE from 'three';
import {Line2} from 'three/addons/lines/Line2.js';
import {LineGeometry} from 'three/addons/lines/LineGeometry.js';
import {LineMaterial} from 'three/addons/lines/LineMaterial.js';
const aerialColors=new WeakMap(); // Runtime-only; do not inflate exported glTF extras.

// Both viewers use the same local frame: east, elevation, minus north.
export const localPosition=(x,n,z,base=0)=>[x,z-base,-n];
// Cesium must only convert Y-up to Z-up. Its default Z-forward correction
// adds another quarter turn, putting this geospatial mesh at (-north,east,z).
export const EARTH_GLTF_AXES=Object.freeze({upAxis:'Y',forwardAxis:'X'});
export function groundAt(data,x,n){
  const g=data.grid,c=Math.max(0,Math.min(g.cols-1,(x-g.west)/g.cell_m-.5)),r=Math.max(0,Math.min(g.rows-1,(g.north-n)/g.cell_m-.5));
  const c0=Math.floor(c),r0=Math.floor(r),c1=Math.min(c0+1,g.cols-1),r1=Math.min(r0+1,g.rows-1),tx=c-c0,ty=r-r0;
  return (g.elevations[r0*g.cols+c0]*(1-tx)+g.elevations[r0*g.cols+c1]*tx)*(1-ty)+(g.elevations[r1*g.cols+c0]*(1-tx)+g.elevations[r1*g.cols+c1]*tx)*ty;
}
export function rasterGeometry(data,base=0,roof=false){
  const g=data.grid,p=[],uv=[],indices=[],values=roof?g.surfaces:g.elevations;
  for(let r=0;r<g.rows;r++)for(let c=0;c<g.cols;c++){p.push(...localPosition(g.west+(c+.5)*g.cell_m,g.north-(r+.5)*g.cell_m,values[r*g.cols+c],base));uv.push((c+.5)/g.cols,1-(r+.5)/g.rows);}
  for(let r=0;r<g.rows-1;r++)for(let c=0;c<g.cols-1;c++){
    const a=r*g.cols+c,b=a+1,d=a+g.cols,e=d+1;
    for(const triangle of [[a,d,b],[b,d,e]]){
      // Real-data scenes provide classified roofs. Outside their measured point
      // coverage, DSM vegetation over old footprints must not become buildings.
      if(roof&&Array.isArray(data.roof_meshes))continue;
      if(roof){const id=g.building_ids[triangle[0]];if(!id||triangle.some(k=>g.building_ids[k]!==id||g.native_roofs?.[k]))continue;const zs=triangle.map(k=>values[k]);if(Math.max(...zs)-Math.min(...zs)>2)continue;}
      indices.push(...triangle);
    }
  }
  if(roof)for(const mesh of data.roof_meshes||[]){const start=p.length/3;for(let j=0;j<mesh.vertices.length;j+=3){const [x,n,z]=mesh.vertices.slice(j,j+3);p.push(...localPosition(x,n,z,base));uv.push((x-g.west)/(g.cols*g.cell_m),1-(g.north-n)/(g.rows*g.cell_m));}for(const k of mesh.triangles)indices.push(start+k);}
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(p,3));geo.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));geo.setIndex(indices);geo.computeVertexNormals();
  const normals=geo.getAttribute('normal');for(let i=0;i<normals.count;i++)if(Math.hypot(normals.getX(i),normals.getY(i),normals.getZ(i))<.5)normals.setXYZ(i,0,1,0);
  return geo;
}
export function mappedLines(data,paths,color,base=0,lift=.2){
  const p=[];for(const path of paths)for(let i=1;i<path.length;i++){
    const a=path[i-1],b=path[i],steps=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/data.grid.cell_m));
    for(let j=0;j<steps;j++)for(const t of [j/steps,(j+1)/steps]){const x=a[0]+(b[0]-a[0])*t,n=a[1]+(b[1]-a[1])*t;p.push(...localPosition(x,n,groundAt(data,x,n)+lift,base));}
  }
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(p,3));return new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color,transparent:true,opacity:.95}));
}
// Selection graphics only: never turn cadastral boundaries into physical walls.
// Close each ring explicitly and sample the DEM so the highlight follows slopes.
export function parcelPaths(data){
  return (data.parcel||[]).filter(r=>r.length>=3).map(r=>{
    const ring=r.map(([x,n])=>[x,n]);
    if(ring[0][0]!==ring.at(-1)[0]||ring[0][1]!==ring.at(-1)[1])ring.push([...ring[0]]);
    const points=[];
    for(let i=1;i<ring.length;i++){
      const a=ring[i-1],b=ring[i],steps=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/data.grid.cell_m));
      for(let j=0;j<steps;j++){const t=j/steps,x=a[0]+(b[0]-a[0])*t,n=a[1]+(b[1]-a[1])*t;points.push([x,n,groundAt(data,x,n)+.4]);}
    }
    points.push([...points[0]]);return points;
  });
}
export function propertyHighlight(data,base=0){
  const group=new THREE.Group();group.name='Selected property boundary';
  for(const path of parcelPaths(data)){
    const geometry=new LineGeometry();geometry.setPositions(path.flatMap(([x,n,z])=>localPosition(x,n,z,base)));
    // Fixed pixel widths remain legible at both property and neighbourhood scales.
    for(const [color,width,order] of [['#152f38',3,1001],['#ffda45',2,1002]]){
      const line=new Line2(geometry,new LineMaterial({color,linewidth:width,depthTest:false,depthWrite:false,transparent:true}));line.renderOrder=order;group.add(line);
    }
    const ring=path.slice(0,-1).map(([x,n])=>new THREE.Vector2(x,n));
    const triangles=THREE.ShapeUtils.triangulateShape(ring,[]),positions=path.slice(0,-1).flatMap(([x,n,z])=>localPosition(x,n,z,base));
    const fillGeometry=new THREE.BufferGeometry();fillGeometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));fillGeometry.setIndex(triangles.flat());
    const fill=new THREE.Mesh(fillGeometry,new THREE.MeshBasicMaterial({color:'#ffda45',opacity:.06,transparent:true,depthTest:false,depthWrite:false,side:THREE.DoubleSide}));fill.renderOrder=1000;group.add(fill);
  }
  return group;
}
export function siteMeshes(data,texture,base=0){
  const group=new THREE.Group();group.name='Measured site';
  const material=()=>texture?new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide}):new THREE.MeshStandardMaterial({color:0x607b76,roughness:1,side:THREE.DoubleSide});
  const terrain=new THREE.Mesh(rasterGeometry(data,base),material());terrain.name='LINZ bare earth';const roofs=new THREE.Mesh(rasterGeometry(data,base,true),material());roofs.name='Measured DSM roofs';roofs.material.polygonOffset=true;roofs.material.polygonOffsetFactor=-1;roofs.material.polygonOffsetUnits=-1;
  // Close the sampled roof perimeter down to the measured ground at that exact
  // edge. These neutral display sides have no invented facade imagery or details.
  const edges=new Map(),index=roofs.geometry.index.array,top=roofs.geometry.getAttribute('position');
  for(let i=0;i<index.length;i+=3)for(const [a,b] of [[index[i],index[i+1]],[index[i+1],index[i+2]],[index[i+2],index[i]]]){const key=Math.min(a,b)+':'+Math.max(a,b);if(edges.has(key))edges.delete(key);else edges.set(key,[a,b]);}
  const sidePositions=[];
  for(const [a,b] of edges.values()){
    const pa=[top.getX(a),top.getY(a),top.getZ(a)],pb=[top.getX(b),top.getY(b),top.getZ(b)];const ga=[pa[0],groundAt(data,pa[0],-pa[2])-base,pa[2]],gb=[pb[0],groundAt(data,pb[0],-pb[2])-base,pb[2]];
    if(Math.max(pa[1]-ga[1],pb[1]-gb[1])<.5)continue;for(const p of [pa,ga,pb,pb,ga,gb])sidePositions.push(...p);
  }
  const sidesGeo=new THREE.BufferGeometry();sidesGeo.setAttribute('position',new THREE.Float32BufferAttribute(sidePositions,3));sidesGeo.computeVertexNormals();
  const sides=new THREE.Mesh(sidesGeo,new THREE.MeshStandardMaterial({color:0x899591,roughness:1,side:THREE.DoubleSide}));sides.name='Display building sides';
  group.add(terrain,roofs,sides);return {group,terrain,roofs,sides};
}
export function classifiedCloud(cloud,base=0){
  const group=new THREE.Group();group.name='Classified LiDAR';
  for(const [name,select] of [['buildings',c=>c===6],['vegetation',c=>c>=3&&c<=5],['other',c=>c!==6&&!(c>=3&&c<=5)&&c!==2],['ground',c=>c===2]]){
    const positions=[],colors=[],color=new THREE.Color();cloud.points.forEach(([x,n,z],i)=>{if(!select(cloud.classification[i]))return;positions.push(...localPosition(x,n,z,base));const rgb=cloud.colors[i];color.setRGB(rgb[0]/255,rgb[1]/255,rgb[2]/255,THREE.SRGBColorSpace);colors.push(color.r,color.g,color.b);});
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geo.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));geo.computeBoundingSphere();
    const material=new THREE.PointsMaterial({vertexColors:true,size:2,sizeAttenuation:false});
    material.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace('#include <clipping_planes_fragment>','#include <clipping_planes_fragment>\nif (distance(gl_PointCoord, vec2(0.5)) > 0.5) discard;');};
    const points=new THREE.Points(geo,material);points.name=name;aerialColors.set(points,geo.getAttribute('color').array);group.add(points);
  }return group;
}
export function colorCloud(group,mode,data,base=0){
  const palette={buildings:'#a4b7d2',vegetation:'#5fbd77',other:'#ffb849',ground:'#b4af9c'},color=new THREE.Color();
  for(const object of group.children){
    const geometry=object.geometry;
    if(mode==='aerial'){geometry.setAttribute('color',new THREE.BufferAttribute(aerialColors.get(object),3));continue;}
    const positions=geometry.getAttribute('position'),colors=new Float32Array(positions.count*3);
    for(let i=0;i<positions.count;i++){
      if(mode==='classification')color.set(palette[object.name]);
      else{const h=positions.getY(i)+base-groundAt(data,positions.getX(i),-positions.getZ(i));color.set(h<.3?'#6b91ab':h<1?'#48dcca':h<3?'#ffca55':h<6?'#ee884d':'#b88ee6');}
      colors.set([color.r,color.g,color.b],i*3);
    }
    geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));
  }
}
