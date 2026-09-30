// Unified picture edit. Soundtrack is made only after this picture render exists.
import fs from 'node:fs';
export default async ({project})=>{
 const root='/home/user/foothold-master',plan=JSON.parse(fs.readFileSync(root+'/plan.json','utf8'));
 const p=await project({dir:root+'/project',size:'854x480',fps:24,background:'#000'});
 for(const c of plan.clips){
  const m=await p.add(root+'/media/'+c.file);
  if(c.shot==='E5pre'){
   const contacts=[.28,.78,1.29,1.86,2.38,2.97,3.53,4.12];
   const y=[{at:0,value:0}],roll=[{at:0,value:0}];
   contacts.forEach((t,i)=>{const a=i%2?1:-1;for(const [dt,v] of [[-.10,-3],[0,9],[.055,-5],[.14,2],[.26,0]])y.push({at:t+dt,value:v});for(const [dt,v] of [[-.10,a*.4],[0,a*1.0],[.13,-a*.45],[.26,0]])roll.push({at:t+dt,value:v});});
   y.push({at:4.65,value:0},{at:5,value:0});roll.push({at:4.65,value:0},{at:5,value:0});
   p.compose(<media file={m} trimStart={c.from} x={-26} y={-15} width={906} height={510} fit="cover" muted={true} animate={[{property:'offsetY',keyframes:y,easing:'linear'},{property:'rotation',keyframes:roll,easing:'linear'}]}/>,{at:c.at,dur:c.dur,name:'E5pre contact-linked camera motion'});
  }else p.compose(<media file={m} trimStart={c.from} x={0} y={0} width={854} height={480} fit="cover" muted={true}/>,{at:c.at,dur:c.dur,name:c.shot});
 }
 // Camera-origin light reveal: no overall ambient fade-up outside the moving pool.
 p.compose(<rect x={-1000} y={-400} width={2400} height={1400} fill={{kind:'radial',stops:[{offset:0,color:'#000',opacity:.08},{offset:.07,color:'#000',opacity:.12},{offset:.16,color:'#000',opacity:.72},{offset:.27,color:'#000',opacity:1},{offset:1,color:'#000',opacity:1}]}} animate={[{property:'offsetX',keyframes:[{at:0,value:500},{at:1.8,value:500},{at:3.1,value:160},{at:4.4,value:240},{at:5.4,value:220},{at:6.5,value:180},{at:7.2,value:220},{at:8,value:220}],easing:'smooth'},{property:'offsetY',keyframes:[{at:0,value:-30},{at:2,value:-30},{at:3.4,value:20},{at:4.5,value:50},{at:5.8,value:70},{at:7.2,value:-30},{at:8,value:-30}],easing:'smooth'}]}/>,{at:0,dur:8,name:'Camera light pool, surroundings remain black'});
 const obs=plan.clips.find(x=>x.shot==='O5');
 for(let frame=0;frame<Math.round(obs.dur*24);frame+=3){
  const t=frame/24,u=Math.min(1,t/3.5),vx=Math.max(0,.30*(1-u)),state=Math.max(0,.28*(1-Math.max(0,u-.1)/.9));
  const vals=[[vx,state],[0,.01*(1-u)],[0,.02*(1-u)]];
  p.compose(<group><rect x={744} y={126} width={77} height={61} fill="#06251f"/>{vals.map((v,i)=><group><text x={746} y={127+i*23} width={33} height={13} fontFamily="JetBrains Mono" fontSize={10} color="#c0efdf">{v[0].toFixed(2)}</text><text x={787} y={127+i*23} width={33} height={13} fontFamily="JetBrains Mono" fontSize={10} color="#c0efdf">{v[1].toFixed(2)}</text></group>)}</group>,{at:obs.at+t,dur:Math.min(3/24,obs.dur-t),name:'O5 illustrative values '+frame});
 }
 // Full black is guaranteed at start; underlying generated light reveal begins after it.
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000" animate={[{property:'opacity',keyframes:[{at:0,value:1},{at:.95,value:1},{at:1.2,value:0}]}]}/>,{at:0,dur:1.2,name:'Black opening'});
 for(const at of [.22,.72])p.compose(<rect x={plan.beacon[0]} y={plan.beacon[1]} width={3} height={3} radius={1.5} fill="#df2529" animate={[{property:'opacity',keyframes:[{at:0,value:0},{at:.05,value:.8},{at:.12,value:.8},{at:.19,value:0}]}]}/>,{at,dur:.20,name:'Distant red pulse'});
 const foot=plan.clips.find(x=>x.shot==='O7');
 p.compose(<rect x={0} y={0} width={854} height={480} fill={{kind:'linear',angle:0,stops:[{offset:0,color:'#000',opacity:1},{offset:.32,color:'#000',opacity:.85},{offset:.72,color:'#000',opacity:.12},{offset:1,color:'#000',opacity:0}]}} animate={[{property:'opacity',from:0,to:1,at:0,duration:.65,easing:'smooth'}]}/>,{at:foot.at+4,dur:1,name:'Debris tail soft wipe'});
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000" animate={[{property:'opacity',keyframes:[{at:0,value:0},{at:.5,value:1},{at:.75,value:1},{at:.875,value:0}],easing:'smooth'}]}/>,{at:foot.at+4.5,dur:1,name:'Black division with E2 fade-in'});
 const tx=await p.add(root+'/media/transfer.png'),done=await p.add(root+'/media/complete.png'),e=plan.e7;
 p.compose(<media file={tx} x={0} y={0} width={854} height={480} fit="contain"/>,{at:e,dur:2.8,name:'E7 transfer'});
 for(let k=0;k<=32;k++){const dt=k*2.5/32;p.compose(<group><rect x={180} y={217} width={88} height={39} radius={2} fill="#0b211c"/><text x={181} y={217} width={86} height={39} fontFamily="JetBrains Mono" fontSize={k===32?33:36} color="#c7ffea" align="center">{(68+k)+'%'}</text></group>,{at:e+dt,dur:k===32?.3:2.5/32,name:'E7 progress '+k});}
 for(let k=0;k<19;k++)p.compose(<rect x={570+k*12.8} y={410} width={7} height={13} fill="#c7ffea"/>,{at:e+(k+1)*2.5/19,dur:2.8-(k+1)*2.5/19,name:'Transfer segment '+k});
 p.compose(<media file={done} x={0} y={0} width={854} height={480} fit="contain" animate={[{property:'opacity',from:0,to:1,at:0,duration:.125}]}/>,{at:e+2.675,dur:1.575,name:'E7 red receipt'});
 for(const [at,dur,x] of [[4.25,.083,-9],[4.333,.084,0],[4.417,.083,6],[4.5,.15,0]])p.compose(<media file={done} x={x} y={0} width={854} height={480} fit="contain"/>,{at:e+at,dur,name:'Feed tear '+at});
 for(const [at,y,h] of [[4.25,168,5],[4.417,298,3],[4.5,226,2]])p.compose(<rect x={0} y={y} width={854} height={h} fill="#9fa5a3" opacity={.3}/>,{at:e+at,dur:1/24,name:'Signal stripe'});
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000"/>,{at:e+4.65,dur:.35,name:'Final black'});
 await p.render(root+'/picture.mp4',{draft:false,bitrate:3000000});
 await p.frame(obs.at+2,root+'/qa-hud.png');
 await p.frame(e+2.5,root+'/qa-transfer.png');
 await p.frame(e+4.85,root+'/qa-black.png');
};
