export default async ({project})=>{
const r='/home/user/e5-contact-v4';const p=await project({dir:r+'/contact-project',size:'320x180',fps:24,background:'#000'});
p.compose(<rect x={0} y={0} width={320} height={180} fill="#000"/>,{at:0,dur:5,name:'Contact stem'});
const a0=await p.add(r+'/contact-0.wav');p.cut(a0,{at:0.24500000000000002,from:0,dur:.24});
const a1=await p.add(r+'/contact-1.wav');p.cut(a1,{at:0.745,from:0,dur:.24});
const a2=await p.add(r+'/contact-2.wav');p.cut(a2,{at:1.2550000000000001,from:0,dur:.24});
const a3=await p.add(r+'/contact-3.wav');p.cut(a3,{at:1.8250000000000002,from:0,dur:.24});
const a4=await p.add(r+'/contact-4.wav');p.cut(a4,{at:2.3449999999999998,from:0,dur:.24});
const a5=await p.add(r+'/contact-5.wav');p.cut(a5,{at:2.935,from:0,dur:.24});
const a6=await p.add(r+'/contact-6.wav');p.cut(a6,{at:3.4949999999999997,from:0,dur:.24});
const a7=await p.add(r+'/contact-7.wav');p.cut(a7,{at:4.085,from:0,dur:.24});
await p.render(r+'/contact-stem.mp4',{draft:false,bitrate:200000});};