import assert from 'node:assert/strict';
import {localPosition,rasterGeometry,groundAt,parcelPaths,propertyHighlight,EARTH_GLTF_AXES,classifiedCloud,colorCloud} from '../web/site-geometry.js';
import ModelUtility from '../web/node_modules/@cesium/engine/Source/Scene/Model/ModelUtility.js';
import Axis from '../web/node_modules/@cesium/engine/Source/Scene/Axis.js';
import {Matrix4,Cartesian3} from '../web/node_modules/@cesium/core/index.js';
// Asymmetric fixture catches mirrored northing, wrong grid origin, roof bridging,
// upside-down texture UV and inconsistent local/global display geometry.
assert.deepEqual(localPosition(17,83,12,4),[17,8,-83]);
// Use the installed renderer's actual axis correction, not an assumed matrix.
const correction=ModelUtility.getAxisCorrectionMatrix(Axis[EARTH_GLTF_AXES.upAxis],Axis[EARTH_GLTF_AXES.forwardAxis]);
for(const [east,north,z] of [[17,83,12],[-49,21,34],[0,-15,7]]){
  const actual=Matrix4.multiplyByPoint(correction,new Cartesian3(...localPosition(east,north,z)),new Cartesian3());
  assert.deepEqual([actual.x,actual.y,actual.z],[east,north,z]);
}
console.log('PASS: Cesium model east/north/height agrees with parcel and flow coordinates');
const data={grid:{rows:2,cols:3,cell_m:1,west:10,north:84,elevations:[1,2,3,4,5,6],surfaces:[8,9,30,8,9,30],building_ids:[1,1,2,1,1,2]}};
const mesh=rasterGeometry(data,0,true),positions=mesh.getAttribute('position');
assert.equal(positions.getX(0),10.5);assert.equal(positions.getZ(0),-83.5);
assert.equal(mesh.getAttribute('uv').getY(0),.75);
assert.equal(mesh.index.count,6);
for(const v of positions.array)assert.ok(Number.isFinite(v));
assert.equal(groundAt(data,10.5,83.5),1);
assert.equal(groundAt(data,11,83),3);
console.log('PASS: asymmetric NZTM frame, raster centres, roof isolation, texture north and ground interpolation');
data.parcel=[[[10.5,83.5],[12.5,83.5],[12.5,82.5],[10.5,82.5]]];
const paths=parcelPaths(data),highlight=propertyHighlight(data,4);
assert.deepEqual(paths[0][0],paths[0].at(-1));
assert.equal(paths[0][0][2],1.4);
assert.equal(data.parcel[0].length,4); // Never mutate the recorded parcel.
assert.equal(highlight.children.filter(o=>o.isLine2).length,2);
assert.deepEqual(highlight.children.filter(o=>o.isLine2).map(o=>o.material.linewidth),[3,2]);
for(const o of highlight.children){assert.equal(o.material.depthWrite,false);assert.equal(o.material.depthTest,false);}
const fill=highlight.children.find(o=>o.isMesh&&!o.isLine2);
assert.ok(fill.geometry.index.count>0);
console.log('PASS: closed terrain-sampled parcel, non-mutating selection, high-contrast non-physical overlay');
const source={points:[[10.5,83.5,1],[11,83,4],[12,83,9],[12,83,7]],classification:[2,1,6,5],colors:[[10,20,30],[40,50,60],[70,80,90],[100,110,120]]};
const cloud=classifiedCloud(source),groups=Object.fromEntries(cloud.children.map(o=>[o.name,o]));
assert.equal(cloud.children.reduce((n,o)=>n+o.geometry.getAttribute('position').count,0),4);
assert.equal(groups.other.geometry.getAttribute('position').count,1);
assert.equal(groups.ground.visible,true);
const original=groups.other.geometry.getAttribute('color').array.slice();
colorCloud(cloud,'height',data);colorCloud(cloud,'classification',data);colorCloud(cloud,'aerial',data);
assert.deepEqual(groups.other.geometry.getAttribute('color').array,original);
assert.deepEqual(Array.from(groups.other.geometry.getAttribute('position').array),[11,4,-83]);
console.log('PASS: unclassified structures and ground retained; colour modes never change measured positions');
