import {test} from 'node:test';
import assert from 'node:assert/strict';
import {terrainGLB} from './hybrid-model.js';

test('GLB preserves measured elevations, finite normals and upward terrain winding',async()=>{
  const data={datum:'NZVD2016',sources:{fixture:'synthetic'},imagery:null,grid:{rows:2,cols:2,cell_m:1,west:-1,north:1,elevations:[1,2,3,4],surfaces:[1,2,3,4],buildings:[0,0,0,0],native_roofs:[0,0,0,0]},roof_meshes:[],facade_rings:[]};
  const buffer=await terrainGLB(data,'',1).arrayBuffer(),view=new DataView(buffer);
  assert.equal(view.getUint32(0,true),0x46546c67);assert.equal(view.getUint32(8,true),buffer.byteLength);
  const jsonLength=view.getUint32(12,true),json=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,20,jsonLength))),offset=28+jsonLength;
  assert.equal(json.images,undefined);
  const primitive=json.meshes[0].primitives[0];
  const get=(id,Type)=>{const a=json.accessors[id],v=json.bufferViews[a.bufferView];return new Type(buffer,offset+v.byteOffset,v.byteLength/Type.BYTES_PER_ELEMENT);};
  const positions=get(primitive.attributes.POSITION,Float32Array),normals=get(primitive.attributes.NORMAL,Float32Array),indices=get(primitive.indices,Uint32Array);
  assert.deepEqual([positions[1],positions[4],positions[7],positions[10]],[1,2,3,4]);
  assert(normals.every(Number.isFinite));assert(indices.every(i=>i<4));
  const [a,b,c]=[...indices.slice(0,3)].map(i=>i*3),ux=positions[b]-positions[a],uz=positions[b+2]-positions[a+2],vx=positions[c]-positions[a],vz=positions[c+2]-positions[a+2];
  assert(uz*vx-ux*vz>0,'ground faces upward');
});
