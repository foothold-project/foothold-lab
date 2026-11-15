'use strict';
// Exact method bodies from recovered official APK, invoked with isolated spies.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=__dirname;
const source=fs.readFileSync(path.join(root,'runtime-web/assets/main-LIOZh9o1.js'),'utf8');
function method(name) {
  const start=source.indexOf('    '+name+'('); assert(start>=0);
  let open=source.indexOf('{',start),n=1,q=null,esc=false,end=open+1;
  for(;end<source.length&&n;end++) {const c=source[end];if(q){if(esc)esc=false;else if(c==='\\')esc=true;else if(c===q)q=null;}else if(c==='"'||c==="'"||c==='`')q=c;else if(c==='{')n++;else if(c==='}')n--;}
  return {code:source.slice(start,end).trim(),line:source.slice(0,start).split('\n').length};
}
const rows=[];
{
 const m=method('loadPointCloud');const ctx={Kg:()=>{}};
 const fn=vm.runInNewContext('({'+m.code+'}).loadPointCloud',ctx,{timeout:1000});
 const state={pointVoxelWorld:{},pointUpdated:false};
 const full={geometryData:{point_count:1,positions:new Uint8Array([0,0,0])}};
 fn.call(state,full);assert.equal(state.pointUpdated,true);assert.equal(state.pointVoxelWorld.currCellDataInfo,full);
 state.pointUpdated=false;fn.call(state,{geometryData:{point_count:0,positions:new Uint8Array(0)}});
 assert.equal(state.pointUpdated,false);assert.equal(state.pointVoxelWorld.currCellDataInfo,full);
 rows.push({test:'live-renderer-empty-frame-keeps-previous',line:m.line,result:'pass',scope:'exact method body with geometry holder spy, not pixel output'});
}
{
 const m=method('updatePointCloud');const ctx={xI:class {constructor(buffer,size){this.buffer=buffer;this.itemSize=size;}}};
 const fn=vm.runInNewContext('({'+m.code+'}).updatePointCloud',ctx,{timeout:1000});
 const filtered=new Float32Array([1,2,0]),direct=new Float32Array([1,2,0,1,2,4]);const captured={};
 const state={filteredBufferGeometry:{setAttribute:(k,v)=>captured.filtered=v},laserBufferGeometry:{setAttribute:(k,v)=>captured.direct=v}};
 fn.call(state,filtered,direct);assert.equal(captured.filtered.buffer,filtered.buffer);assert.equal(captured.direct.buffer,direct.buffer);
 rows.push({test:'accumulated-and-direct-both-forwarded-to-renderer',line:m.line,result:'pass',filtered_points:1,direct_points:2});
}
const report={node:process.version,tests:rows,scope:'isolated exact JavaScript methods, no network/filesystem imports in VM'};
fs.writeFileSync(path.join(root,'evidence/renderer-fixtures.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
