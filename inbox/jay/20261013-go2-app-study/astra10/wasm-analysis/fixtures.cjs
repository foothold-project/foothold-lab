'use strict';
// Offline fixtures. No WASI, network, process or filesystem imports reach WASM.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const mode = process.argv[2];
assert.ok(mode==='points'||mode==='mesh','mode must be points or mesh');
const file = mode === 'points' ? 'libvoxel-Bqa6xB-f.wasm' : 'libvoxel-doIu-r8s.wasm';
const bytes = fs.readFileSync(path.join(root,'extracted/assets/dist/assets',file));
const expectedHash = mode==='points' ? 'df28d833bc3045e58e110926dd87c312538a2e5b60a964a4fc5e99ff06d39b9c' : '1ba27f065199954dc562b233aa38ea775ac687118cce77b5c71bc14e17e05542';
assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),expectedHash,'Target differs from inspected WASM');
const moduleObj = new WebAssembly.Module(bytes);
const evidence = {node:process.version, mode, file, sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
  imports:WebAssembly.Module.imports(moduleObj),exports:WebAssembly.Module.exports(moduleObj),tests:[]};
let memory;
const instance = new WebAssembly.Instance(moduleObj,{a:{a:()=>0,b:(dst,src,n)=>{
  assert.ok(dst>=0 && src>=0 && n>=0 && dst+n<=memory.buffer.byteLength && src+n<=memory.buffer.byteLength);
  new Uint8Array(memory.buffer).copyWithin(dst,src,src+n);
}}});
const e = instance.exports;
memory = e.b instanceof WebAssembly.Memory ? e.b : e.c;
assert.ok(memory.buffer.byteLength <= 1536*65536);
evidence.memory_bytes = memory.buffer.byteLength;
evidence.function_arities = Object.fromEntries(Object.entries(e).filter(([,v])=>typeof v==='function').map(([k,v])=>[k,v.length]));
function call(fn,args) { return vm.runInNewContext('fn(...args)',{fn,args},{timeout:2000}); }
function malloc(n) { const p=call(e.f,[n]); assert.ok(p>0 && p+n<=memory.buffer.byteLength); return p; }
function i32(p) { return new DataView(memory.buffer).getInt32(p,true); }
function clear(p,n) {new Uint8Array(memory.buffer).fill(0,p,p+n);}
function digest(data) {return crypto.createHash('sha256').update(Buffer.from(data.buffer,data.byteOffset,data.byteLength)).digest('hex');}
function closeEnough(actual,expected) {
  assert.equal(actual.length,expected.length);
  for(let i=0;i<actual.length;i++)assert.ok(Math.abs(actual[i]-expected[i])<1e-5,`${actual[i]} != ${expected[i]}`);
}
if(mode==='points') {
  assert.equal(e.e.length,15); call(e.c,[]);
  const capacity=4, dictSize=67108864;
  const p={input:malloc(1024),dict:malloc(dictSize),indices:malloc(capacity*4),direct:malloc(1024),out:malloc(capacity*12),added:malloc(4),count:malloc(4)};
  function reset(full=true) {call(e.d,[]);if(full){clear(p.dict,dictSize);clear(p.indices,capacity*4);clear(p.out,capacity*12);}clear(p.direct,1024);}
  function run(name,points,bounds=[0,1,0,1,0,1]) {
    assert.ok(points.length<=100);
    const v=new DataView(memory.buffer);
    points.flat().forEach((x,i)=>{assert.ok(Number.isInteger(x)&&x>=0&&x<=65535);v.setUint16(p.input+i*2,x,true);});
    const ret=call(e.e,[...bounds,points.length,p.input,capacity,p.dict,p.indices,p.direct,p.out,p.added,p.count]);
    const count=i32(p.count),added=i32(p.added); assert.ok(count>=0&&count<=capacity);
    const row={name,input_u16:points,bounds,return:ret,added,count,
      direct:Array.from(new Float32Array(memory.buffer,p.direct,points.length*3)),
      output:Array.from(new Float32Array(memory.buffer,p.out,count*3)),
      stored_keys:Array.from(new Uint32Array(memory.buffer,p.indices,capacity)),
      counters_at_1028_1032:Array.from(new Int32Array(memory.buffer,1028,2))};
    evidence.tests.push(row);return row;
  }
  reset();let r=run('known-origin-single',[[1000,2000,3000]],[10,11,20,21,30,31]);
  closeEnough(r.direct,[11,22,33]);assert.equal(r.count,1);assert.equal(r.added,1);
  reset();let a=run('max-bounds-a',[[1000,2000,3000]],[10,11,20,21,30,31]);
  reset();let b=run('max-bounds-b',[[1000,2000,3000]],[10,-500,20,800,30,-900]);
  assert.deepEqual(a.direct,b.direct);assert.deepEqual(a.stored_keys,b.stored_keys);
  reset();r=run('duplicate-in-frame',[[1000,2000,3000],[1000,2000,3000]]);assert.equal(r.added,1);assert.equal(r.count,1);
  r=run('duplicate-next-frame',[[1000,2000,3000]]);assert.equal(r.added,0);assert.equal(r.count,1);
  reset();r=run('z-only-change',[[1000,2000,0],[1000,2000,4000]]);assert.equal(r.added,1);assert.equal(r.count,1);
  closeEnough(r.direct,[1,2,0,1,2,4]);closeEnough(r.output,[1,2,0]);
  reset();r=run('y-separation-200mm',[[1000,2000,0],[1000,2200,0]]);assert.equal(r.count,2);
  reset();r=run('x-separation-200mm',[[1000,2000,0],[1200,2000,0]]);assert.equal(r.count,2);
  reset();r=run('dense-nearby-points',[[1000,2000,0],[1010,2010,100],[1020,2020,200]]);assert.equal(r.count,1);
  reset();r=run('isolated-point',[[1000,2000,0]]);assert.equal(r.count,1);
  reset(false);r=run('reset-function-only',[[1000,2000,0]]);assert.equal(r.count,0);assert.equal(r.added,0);
  reset(true);r=run('reset-plus-clear',[[1000,2000,0]]);assert.equal(r.count,1);
  reset();r=run('ring-capacity-four',[[0,0,0],[200,0,0],[400,0,0],[600,0,0],[800,0,0]]);assert.equal(r.count,4);assert.equal(r.added,5);
  closeEnough(r.output,[.8,0,0,.2,0,0,.4,0,0,.6,0,0]);
  r=run('ring-reaccept-evicted',[[0,0,0]]);assert.equal(r.added,1);assert.equal(r.count,4);
  r=run('empty-input',[]);assert.equal(r.count,4);assert.equal(r.added,0);
} else if(mode==='mesh') {
  assert.equal(e.e.length,11);call(e.d,[]);
  const p={input:malloc(70000),decoded:malloc(80000),size:malloc(4),pos:malloc(100000),uv:malloc(100000),idx:malloc(300000),faces:malloc(4),points:malloc(4)};
  function bitmap(points) {
    const b=Buffer.alloc(61440);
    for(const [x,y,z] of points) {
      assert.ok(x>=0&&x<128&&y>=0&&y<128&&z>=0&&z<30);
      const n=x+128*y+16384*z;b[n>>3]|=0x80>>(n&7);
    }return b;
  }
  function literal(data) {
    const head=[Math.min(data.length,15)<<4];
    if(data.length>=15){let n=data.length-15;while(n>=255){head.push(255);n-=255;}head.push(n);}
    return Buffer.concat([Buffer.from(head),data]);
  }
  function zeroMatch(){let n=61434-19;const a=[0x1f,0,1,0];while(n>=255){a.push(255);n-=255;}a.push(n,0x50,0,0,0,0,0);return Buffer.from(a);}
  function run(name,points,zNorm=0,input=null) {
    const raw=bitmap(points), data=input||literal(raw);assert.ok(data.length<70000);
    clear(p.decoded,80000);clear(p.pos,100000);clear(p.uv,100000);clear(p.idx,300000);
    new Uint8Array(memory.buffer).set(data,p.input);
    const ret=call(e.e,[p.input,data.length,80000,p.decoded,p.size,p.pos,p.uv,p.idx,p.faces,p.points,zNorm]);
    const faces=i32(p.faces),count=i32(p.points),size=i32(p.size);
    assert.ok(faces>=0&&faces<=1000);assert.ok(count>=0&&count<=1000);
    const positions=new Uint8Array(memory.buffer,p.pos,faces*12),uvs=new Uint8Array(memory.buffer,p.uv,faces*8),indices=new Uint32Array(memory.buffer,p.idx,faces*6);
    const bbox=[[255,255,255],[-1,-1,-1]];
    for(let i=0;i<positions.length;i++){let a=i%3;bbox[0][a]=Math.min(bbox[0][a],positions[i]);bbox[1][a]=Math.max(bbox[1][a],positions[i]);}
    const row={name,input_points:points,z_normalized:zNorm,compressed_bytes:data.length,compressed_sha256:digest(data),input_prefix_hex:data.subarray(0,24).toString('hex'),
      return:ret,decompressed_size:size,decoded_matches_expected:size===raw.length&&Buffer.from(memory.buffer,p.decoded,size).equals(raw),
      points:count,faces,vertices:positions.length/3,triangles:indices.length/3,bbox:faces?bbox:null,
      positions:Array.from(positions),uvs:Array.from(uvs),indices:Array.from(indices)};
    evidence.tests.push(row);return row;
  }
  let r=run('empty-volume',[]);assert.equal(r.faces,0);assert.equal(r.points,0);assert.ok(r.decoded_matches_expected);
  r=run('known-lz4-offset-match',[],0,zeroMatch());assert.equal(r.faces,0);assert.ok(r.decoded_matches_expected);
  r=run('isolated-interior',[[3,4,5]]);assert.equal(r.faces,6);assert.equal(r.points,1);assert.deepEqual(r.bbox,[[3,4,5],[4,5,6]]);assert.ok(r.decoded_matches_expected);
  const baseline=r;
  r=run('same-point-color-shift',[[3,4,5]],10);assert.deepEqual(r.positions,baseline.positions);assert.notDeepEqual(r.uvs,baseline.uvs);
  r=run('adjacent-x',[[3,4,5],[4,4,5]]);assert.equal(r.faces,10);assert.equal(r.points,2);
  r=run('adjacent-y',[[3,4,5],[3,5,5]]);assert.equal(r.faces,10);
  r=run('adjacent-z',[[3,4,5],[3,4,6]]);assert.equal(r.faces,10);
  r=run('separated',[[3,4,5],[5,4,5]]);assert.equal(r.faces,12);
  r=run('bit-order-extremes',[[0,0,0],[7,0,0]]);assert.equal(r.faces,12);assert.deepEqual(r.bbox,[[0,0,0],[8,1,1]]);
  r=run('volume-upper-corner',[[127,127,29]]);assert.equal(r.faces,6);assert.deepEqual(r.bbox,[[127,127,29],[128,128,30]]);
  for(const side of [2,3]){const pts=[];for(let z=5;z<5+side;z++)for(let y=4;y<4+side;y++)for(let x=3;x<3+side;x++)pts.push([x,y,z]);
    r=run(`solid-cube-${side}`,pts);assert.equal(r.points,side**3);assert.equal(r.faces,6*side**2);}
  r=run('independent-frame-empty',[]);assert.equal(r.points,0);assert.equal(r.faces,0);
} else throw new Error('mode must be points or mesh');
evidence.assertions_passed=true;
fs.writeFileSync(path.join(__dirname,`fixtures-${mode}.json`),JSON.stringify(evidence,null,2)+'\n');
console.log(JSON.stringify({file,memory_bytes:evidence.memory_bytes,tests:evidence.tests.map(x=>({name:x.name,added:x.added,count:x.count,points:x.points,faces:x.faces,decompressed_size:x.decompressed_size})),assertions_passed:true}));
