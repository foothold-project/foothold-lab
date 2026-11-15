'use strict';
// Execute unchanged retained worker JS with an offline-only fetch stub and known WASM.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const mode=process.argv[2];assert.ok(['points','mesh','image'].includes(mode));
const names={points:'three.worker-VAdOurOh.js',mesh:'three.worker-BhnsyeGz.js',image:'slam.worker-B9-NnJ09.js'};
const expected={points:'fb87c81e68b0958cfce39065cbf7764d298eb875769cfd65d4ea16a022967143',mesh:'2a2a87c04b03c51a02be39da4d282d585054cead6881e452a0cba3c9bcb23e96',image:'7be29eece06e43d4edbab276911f02e50c1134aa37d07dce4ec9731ead9066ef'};
const workerPath=path.join(root,'runtime-web/assets',names[mode]);
const source=fs.readFileSync(workerPath,'utf8');
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
assert.equal(sha(source),expected[mode]);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'evidence/runtime-web-manifest.json'),'utf8'));
const entry=manifest.find(x=>x.path==='assets/'+names[mode]);assert.ok(entry);assert.equal(entry.sha256,sha(source));assert.equal(entry.bytes,Buffer.byteLength(source));
const wasmFile=mode==='points'?'libvoxel-Bqa6xB-f.wasm':mode==='mesh'?'libvoxel-doIu-r8s.wasm':null;
const wasm=wasmFile?fs.readFileSync(path.join(root,'extracted/assets/dist/assets',wasmFile)):null;
if(wasm)assert.equal(sha(wasm),mode==='points'?'df28d833bc3045e58e110926dd87c312538a2e5b60a964a4fc5e99ff06d39b9c':'1ba27f065199954dc562b233aa38ea775ac687118cce77b5c71bc14e17e05542');
const record={mode,node:process.version,worker:names[mode],sha256:sha(source),manifest_matches:true,
  wasm:wasmFile,wasm_sha256:wasm?sha(wasm):null,source_changed:false,fetches:[],allocations:[],generate_calls:[],reset_calls:0,events:[],tests:[]};
let memory,ctx;
const listeners={},posted=[];
const self={location:{href:'https://offline.invalid/assets/'+names[mode]},addEventListener:(name,fn)=>{listeners[name]=fn;},postMessage:message=>{posted.push(message);if(message?.type)record.events.push(message.type);}};
const observedWebAssembly={RuntimeError:WebAssembly.RuntimeError,instantiate:async(bytes,imports)=>{
  assert.equal(sha(Buffer.from(bytes)),sha(wasm));
  const result=await WebAssembly.instantiate(bytes,imports);memory=Object.values(result.instance.exports).find(v=>v instanceof WebAssembly.Memory);
  assert.ok(memory && memory.buffer.byteLength<=1536*65536);record.memory_bytes=memory.buffer.byteLength;
  const exp={};for(const [key,value] of Object.entries(result.instance.exports))exp[key]=value;
  const alloc=exp.f;exp.f=n=>{const p=alloc(n);assert.ok(p>0&&p+n<=memory.buffer.byteLength);record.allocations.push({size:n,ptr:p});return p;};
  const generate=exp.e;exp.e=(...args)=>{record.generate_calls.push(args);return generate(...args);};
  if(mode==='points'){const reset=exp.d;exp.d=()=>{record.reset_calls++;return reset();};}
  return {module:result.module,instance:{exports:exp}};
}};
const fetch=async url=>{
  const asset=new URL(String(url)).pathname;
  assert.equal(asset,'/assets/'+wasmFile,'Offline fixture only permits the selected local WASM');record.fetches.push(asset);
  return {ok:true,arrayBuffer:async()=>wasm.buffer.slice(wasm.byteOffset,wasm.byteOffset+wasm.byteLength)};
};
ctx=vm.createContext({self,URL,WebAssembly:observedWebAssembly,fetch,
  console:{log:()=>{},error:()=>{}},atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64')});
function execute(code){return vm.runInContext(code,ctx,{timeout:2000});}
function send(data){ctx.fixtureCallback=listeners.message;ctx.fixtureEvent={data};execute('fixtureCallback(fixtureEvent)');delete ctx.fixtureCallback;delete ctx.fixtureEvent;}
function outputs(){const o=posted.splice(0);return o;}
function latest(type){const msgs=outputs();return msgs.findLast(x=>type?x.type===type:!x.type);}
function pointData(points,bounds=[0,64,0,64,0,64]){const buf=Buffer.alloc(points.length*6);points.flat().forEach((n,i)=>buf.writeUInt16LE(n,i*2));return {xmin:bounds[0],xmax:bounds[1],ymin:bounds[2],ymax:bounds[3],zmin:bounds[4],zmax:bounds[5],data:buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength)};}
function pointOutput(msg){const r=msg.data;return {directCount:r.directCount,directOutput:Array.from(r.directOutput),outputCount:r.outputCount,output:Array.from(r.output),addedCount:r.addedCount};}
function memoryState(){const a=record.allocations;assert.equal(a[4].size,67108864);assert.equal(a[5].size,4000000);const key=new DataView(memory.buffer).getUint32(a[5].ptr,true);const address=a[4].ptr+(key>>>3);return {dict_ptr:a[4].ptr,dict_intended_end:a[4].ptr+67108864,dict_actual_fill_end:67108864,indices_ptr:a[5].ptr,indices_intended_end:a[5].ptr+4000000,indices_actual_fill_end:4000000,key,key_byte_address:address,key_bit:new Uint8Array(memory.buffer)[address]&(1<<(key&7)),counters:Array.from(new Int32Array(memory.buffer,1028,2))};}
function add(name,data){record.tests.push({name,...data});}
function literalZeroTail(firstBytes){const literal=firstBytes.length,matchLength=61440-literal-5,a=[(literal<<4)|15,...firstBytes,1,0];let n=matchLength-19;while(n>=255){a.push(255);n-=255;}a.push(n,0x50,0,0,0,0,0);return Uint8Array.from(a).buffer;}
(async()=>{
  execute(source);
  // Await the worker's observable readiness, not an arbitrary event-loop count.
  const deadline=Date.now()+5000;
  let ready=mode==='image';
  while(!ready && Date.now()<deadline){
    await new Promise(resolve=>setTimeout(resolve,10));
    if(mode==='points' && listeners.message){send({type:'check'});ready=!!latest('check');}
    if(mode==='mesh')ready=record.events.includes('ready');
  }
  assert.ok(ready,'Worker did not finish WASM initialization within 5 seconds');
  assert.equal(typeof listeners.message,'function');
  if(mode==='points'){
    send({type:'check'});assert.equal(latest('check').type,'check');
    send('clear');outputs();
    send({type:'newMap',data:pointData([[1000,2000,0],[1000,2000,4000]])});
    let r=pointOutput(latest('newMap'));assert.equal(r.directCount,2);assert.equal(r.outputCount,1);assert.deepEqual(r.directOutput,[1,2,0,1,2,4]);
    add('actual-newMap-forwards-both-outputs',{input:[[1000,2000,0],[1000,2000,4000]],output:r});
    const normalBefore=memoryState();send('clear');outputs();const normalAfter=memoryState();assert.notEqual(normalBefore.key_bit,0);assert.equal(normalAfter.key_bit,0);assert.equal(normalAfter.key,normalBefore.key);
    add('actual-clear-normal-key',{before:normalBefore,after:normalAfter});
    send({type:'newMap',data:pointData([[51000,0,0]])});r=pointOutput(latest('newMap'));assert.equal(r.outputCount,1);
    const highBefore=memoryState();assert.ok(highBefore.key_byte_address>=67108864);assert.notEqual(highBefore.key_bit,0);
    send('clear');outputs();const highAfter=memoryState();assert.equal(highAfter.key_bit,highBefore.key_bit);assert.deepEqual(highAfter.counters,[0,0]);
    send({type:'newMap',data:pointData([[51000,0,0]])});r=pointOutput(latest('newMap'));assert.equal(r.directCount,1);assert.equal(r.outputCount,0);assert.equal(r.addedCount,0);assert.deepEqual(r.directOutput,[51,0,0]);
    add('actual-clear-leaves-high-key',{input:[[51000,0,0]],before:highBefore,after:highAfter,output_after_reinput:r});
    const bytes=Buffer.alloc(16);bytes.writeFloatLE(1.5,4);bytes.writeFloatLE(2.5,8);bytes.writeFloatLE(3.5,12);
    for(const type of ['preview','navigation-path']){
      const before=record.generate_calls.length;
      send({type,data:{width:1,height:1,fields:[{offset:4},{offset:8},{offset:12}],point_step:16,data:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}});
      const msg=latest(type);assert.deepEqual(Array.from(msg.data.points),[1.5,2.5,3.5]);assert.equal(record.generate_calls.length,before);
      add(type+'-bypasses-WASM',{output:Array.from(msg.data.points),additional_wasm_calls:0});
    }
  } else if(mode==='mesh'){
    assert.ok(record.events.includes('boot')&&record.events.includes('ready'));outputs();
    for(const [name,resolution,origin,width,expectedRes,zNorm] of [['numeric-string-resolution','.05',[1,2,.17],128,.05,3],['zero-resolution-fallback',0,[1,2,.17],999,.1,1]]){
      send({data:literalZeroTail([0x80,0]),resolution,origin,width});const r=latest();assert.ok(r?.geometryData);
      assert.equal(r.resolution,expectedRes);assert.equal(r.geometryData.face_count,6);assert.equal(r.geometryData.point_count,1);assert.equal(record.generate_calls.at(-1)[10],zNorm);
      add(name,{input_resolution:resolution,input_origin:origin,input_width:width,output_resolution:r.resolution,output_origin:r.origin,z_normalized:record.generate_calls.at(-1)[10],face_count:r.geometryData.face_count,point_count:r.geometryData.point_count,positions:Array.from(r.geometryData.positions),first_uvs:Array.from(r.geometryData.uvs).slice(0,8)});
    }
  }else{
    const inputBytes=[1,2,3,4,5,6];send({image_:{width_:2,height_:1,data_:Buffer.from(inputBytes).toString('base64')}});const r=latest();assert.ok(ArrayBuffer.isView(r));assert.equal(r.length,6);assert.deepEqual(Array.from(r),[0,0,0,0,0,0]);assert.equal(record.fetches.length,0);
    add('base64-decoded-result-discarded',{input_bytes:inputBytes,width:2,height:1,output:Array.from(r),wasm_calls:0});
  }
  record.assertions_passed=true;
  const anchors=mode==='points'?['m=new URL','clear(){','generate(l,t,i,c,y,A,a)','if(t=="newMap")','["preview","navigation-path"]']:
    mode==='mesh'?['f=new URL','generate(s,e)','Math.floor(s.origin[2]/s.resolution)','function G(r)']:['function $(t)','function q(t)'];
  record.snippets=anchors.map(anchor=>{const at=source.indexOf(anchor);assert.ok(at>=0);return {anchor,char_offset:at,text:source.slice(at,at+220)};});
  fs.writeFileSync(path.join(__dirname,`fixtures-wrappers-${mode}.json`),JSON.stringify(record,null,2)+'\n');
  console.log(JSON.stringify({worker:record.worker,sha256:record.sha256,tests:record.tests,assertions_passed:true}));
})().catch(e=>{console.error(e.name+': '+e.message);process.exitCode=1;});
