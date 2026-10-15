/* Our acquired terrain only. Google content never enters this asset or an export. */
export function terrainGLB(data, imageURL, stride=2) {
  const g=data.grid, chunks=[], views=[], accessors=[], meshes=[], nodes=[];
  let bytes=0;
  const gltf={asset:{version:'2.0',generator:'Auckland FlowLab · measured terrain',extras:{datum:data.datum,sources:data.sources,display_sampling_m:stride*g.cell_m}},
    scene:0,scenes:[{nodes}],nodes:[],meshes,extensionsUsed:['KHR_materials_unlit'],materials:[
      {name:'LINZ acquired aerial',extensions:{KHR_materials_unlit:{}},pbrMetallicRoughness:{baseColorTexture:{index:0},metallicFactor:0,roughnessFactor:1},doubleSided:true},
      {name:'Approximate facades',pbrMetallicRoughness:{baseColorFactor:[.76,.74,.68,1],metallicFactor:0,roughnessFactor:1},doubleSided:true}],
    textures:[{source:0,sampler:0}],samplers:[{magFilter:9729,minFilter:9729,wrapS:33071,wrapT:33071}],images:[{uri:imageURL}],
    buffers:[{byteLength:0}],bufferViews:views,accessors};
  function array(value,type,components,target){
    const offset=bytes, raw=new Uint8Array(value.buffer,value.byteOffset,value.byteLength),padding=(4-raw.length%4)%4;
    chunks.push(raw,new Uint8Array(padding));bytes+=raw.length+padding;
    const view=views.push({buffer:0,byteOffset:offset,byteLength:raw.length,target})-1;
    const accessor={bufferView:view,componentType:type,count:value.length/components,type:components===3?'VEC3':components===2?'VEC2':'SCALAR'};
    if(components===3){accessor.min=[Infinity,Infinity,Infinity];accessor.max=[-Infinity,-Infinity,-Infinity];for(let i=0;i<value.length;i++) {const k=i%3;accessor.min[k]=Math.min(accessor.min[k],value[i]);accessor.max[k]=Math.max(accessor.max[k],value[i]);}}
    return accessors.push(accessor)-1;
  }
  function mesh(name,p,uv,index,material=0){
    if(!index.length)return;
    const positions=new Float32Array(p), indices=new Uint32Array(index), normals=new Float32Array(p.length);
    for(let i=0;i<index.length;i+=3){const a=index[i]*3,b=index[i+1]*3,c=index[i+2]*3,ux=p[b]-p[a],uy=p[b+1]-p[a+1],uz=p[b+2]-p[a+2],vx=p[c]-p[a],vy=p[c+1]-p[a+1],vz=p[c+2]-p[a+2];const n=[uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx];for(const q of [a,b,c])for(let k=0;k<3;k++)normals[q+k]+=n[k];}
    for(let i=0;i<normals.length;i+=3){const n=Math.hypot(...normals.subarray(i,i+3))||1;for(let k=0;k<3;k++)normals[i+k]/=n;}
    const attributes={POSITION:array(positions,5126,3,34962),NORMAL:array(normals,5126,3,34962)};
    if(uv.length)attributes.TEXCOORD_0=array(new Float32Array(uv),5126,2,34962);
    const id=meshes.push({name,primitives:[{attributes,indices:array(indices,5125,1,34963),material}]})-1;
    nodes.push(gltf.nodes.length);gltf.nodes.push({name,mesh:id});
  }
  // Preserve the measured edge centres and sample true source values; no height smoothing.
  const rows=[],cols=[];for(let r=0;r<g.rows;r+=stride)rows.push(r);if(rows.at(-1)!==g.rows-1)rows.push(g.rows-1);
  for(let c=0;c<g.cols;c+=stride)cols.push(c);if(cols.at(-1)!==g.cols-1)cols.push(g.cols-1);
  const p=[],uv=[],indices=[];
  for(const r of rows)for(const c of cols){p.push(g.west+(c+.5)*g.cell_m,g.elevations[r*g.cols+c],-g.north+(r+.5)*g.cell_m);uv.push((c+.5)/g.cols,(r+.5)/g.rows);}
  for(let r=0;r<rows.length-1;r++)for(let c=0;c<cols.length-1;c++){const a=r*cols.length+c,b=a+1,d=a+cols.length,e=d+1;indices.push(a,d,b,b,d,e);}
  mesh('Measured bare earth · display sampling '+stride+' m',p,uv,indices);
  const fallbackP=[],fallbackUV=[],fallbackI=[];
  for(let r=0;r<g.rows-1;r++)for(let c=0;c<g.cols-1;c++){
    const a=r*g.cols+c,b=a+1,d=a+g.cols,e=d+1;
    if(![a,b,d,e].every(i=>g.buildings[i])||[a,b,d,e].some(i=>g.native_roofs[i]))continue;
    const start=fallbackP.length/3;for(const i of [a,b,d,e]){const rr=Math.floor(i/g.cols),cc=i%g.cols;fallbackP.push(g.west+(cc+.5)*g.cell_m,g.surfaces[i],-g.north+(rr+.5)*g.cell_m);fallbackUV.push((cc+.5)/g.cols,(rr+.5)/g.rows);}fallbackI.push(start,start+2,start+1,start+1,start+2,start+3);
  }
  mesh('Approximate DSM roof fallbacks',fallbackP,fallbackUV,fallbackI);
  const rp=[],ru=[],ri=[];
  for(const roof of data.roof_meshes){const start=rp.length/3;for(let i=0;i<roof.vertices.length;i+=3){const [x,n,z]=roof.vertices.slice(i,i+3);rp.push(x,z,-n);ru.push((x-g.west)/(g.cols*g.cell_m),(g.north-n)/(g.rows*g.cell_m));}for(const i of roof.triangles)ri.push(start+i);}
  mesh('QA-filtered classified LiDAR roofs',rp,ru,ri);
  const fp=[],fi=[];for(const ring of data.facade_rings){const start=fp.length/3;for(const [x,n,b,t] of ring)fp.push(x,b,-n,x,t,-n);for(let i=0;i<ring.length-1;i++){const a=start+i*2;fi.push(a,a+1,a+2,a+2,a+1,a+3);}}
  mesh('Approximate building facades',fp,[],fi,1);
  if(!data.imagery){delete gltf.images;delete gltf.textures;delete gltf.samplers;delete gltf.materials[0].pbrMetallicRoughness.baseColorTexture;gltf.materials[0].pbrMetallicRoughness.baseColorFactor=[.44,.57,.42,1];}
  gltf.buffers[0].byteLength=bytes;
  const json=new TextEncoder().encode(JSON.stringify(gltf)),jsonSize=Math.ceil(json.length/4)*4,total=12+8+jsonSize+8+bytes;
  const buffer=new ArrayBuffer(total), view=new DataView(buffer), out=new Uint8Array(buffer);
  view.setUint32(0,0x46546c67,true);view.setUint32(4,2,true);view.setUint32(8,total,true);
  view.setUint32(12,jsonSize,true);view.setUint32(16,0x4e4f534a,true);out.fill(32,20,20+jsonSize);out.set(json,20);
  const at=20+jsonSize;view.setUint32(at,bytes,true);view.setUint32(at+4,0x004e4942,true);let cursor=at+8;for(const chunk of chunks){out.set(chunk,cursor);cursor+=chunk.length;}
  return new Blob([buffer],{type:'model/gltf-binary'});
}
