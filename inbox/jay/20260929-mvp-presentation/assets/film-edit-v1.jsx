// Native Higgsedit. Source clips retain speed. Reviewed stills are used only for E7.
import fs from 'node:fs';
export default async ({project}) => {
 const root='/home/user/foothold-film';
 const plan=JSON.parse(fs.readFileSync(root+'/timeline.json','utf8'));
 if(plan.clips.some(c=>c.file==='opening-o5-seedance25-v2.mp4'))throw new Error('Rejected O5 v2: human-like boot/limb enters robot sensor POV. Do not render.');
 if(plan.clips.some(c=>c.file==='ending-e5pre-kling30-v1.mp4'))throw new Error('Rejected E5pre: external robot appears in onboard POV. Do not render.');
 const p=await project({dir:root+'/project',size:'854x480',fps:24,background:'#000'});
 const mix=await p.add(root+'/mix.wav');p.cut(mix,{at:0,from:0,dur:plan.total});
 for(const c of plan.clips){
  const media=await p.add(root+'/media/'+c.file);
  p.compose(<media file={media} trimStart={c.from} x={0} y={0} width={854} height={480} fit="contain" muted={true}/>,{at:c.at,dur:c.dur,name:c.shot});
 }
 // Opening begins in black with exactly two tiny beacon pulses.
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000" animate={[{property:'opacity',keyframes:[{at:0,value:1},{at:.85,value:1},{at:1.1,value:0}]}]}/>,{at:0,dur:1.1,name:'Black intro, controlled reveal'});
 for(const at of [.16,.62])p.compose(<rect x={474} y={141} width={3} height={3} radius={1.5} fill="#ed3434" animate={[{property:'opacity',keyframes:[{at:0,value:0},{at:.06,value:.8},{at:.13,value:.8},{at:.2,value:0}]}]}/>,{at,dur:.2,name:'Distant beacon pulse'});
 // O5: preserve generated terrain animation, replace only the two velocity readouts.
 const obs=plan.clips.find(x=>x.shot==='O5');
 p.compose(<rect x={741} y={127} width={78} height={16} fill="#001c14"/>,{at:obs.at,dur:obs.dur,name:'O5 numeric backing'});
 for(let k=0;k<24;k++){
  const at=k*obs.dur/24, u=at/obs.dur;
  const cmd=Math.max(0,.30*(1-u/.70));const state=Math.max(0,.28*(1-Math.max(0,u-.09)/.76));
  p.compose(<group><text x={747} y={129} width={30} height={14} fontFamily="JetBrains Mono" fontSize={10} color="#baeee1">{cmd.toFixed(2)}</text><text x={787} y={129} width={30} height={14} fontFamily="JetBrains Mono" fontSize={10} color="#baeee1">{state.toFixed(2)}</text></group>,{at:obs.at+at,dur:obs.dur/24,name:'O5 illustrative velocity '+k});
 }
 // Preserve the soft broad fall-off and debris tail of the existing foot transition.
 const foot=plan.clips.find(x=>x.shot==='O7');
 p.compose(<rect x={0} y={0} width={854} height={480} fill={{kind:'linear',angle:0,stops:[{offset:0,color:'#000',opacity:1},{offset:.32,color:'#000',opacity:.85},{offset:.72,color:'#000',opacity:.12},{offset:1,color:'#000',opacity:0}]}} animate={[{property:'opacity',from:0,to:1,at:0,duration:.65,easing:'smooth'}]}/>,{at:foot.at+4,dur:1,name:'Broad soft left-to-right loss of light'});
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000" animate={[{property:'opacity',keyframes:[{at:0,value:0},{at:.5,value:1},{at:.75,value:1},{at:.875,value:0}],easing:'smooth'}]}/>,{at:foot.at+4.5,dur:.916666667,name:'Debris tail and black split'});
 // Native E7 fallback after provider IP-detection rejection, not an AI-generated clip.
 const tx=await p.add(root+'/media/transfer.png'), done=await p.add(root+'/media/complete.png');
 p.compose(<media file={tx} x={0} y={0} width={854} height={480} fit="contain"/>,{at:plan.e7,dur:3.25,name:'E7 approved transfer design'});
 p.compose(<rect x={179} y={215} width={90} height={42} fill="#082016"/>,{at:plan.e7,dur:3.25,name:'Transfer changing percentage backing'});
 p.compose(<rect x={44} y={408} width={752} height={17} fill="#09251c"/>,{at:plan.e7,dur:3.25,name:'Progress track'});
 for(let k=0;k<32;k++){
  const n=68+k, at=plan.e7+k*.09375;
  p.compose(<text x={182} y={217} width={84} height={40} fontFamily="JetBrains Mono" fontSize={38} align="center" color="#c8ffea">{n+'%'}</text>,{at,dur:.09375,name:'Transfer '+n});
 }
 p.compose(<text x={180} y={217} width={91} height={40} fontFamily="JetBrains Mono" fontSize={34} align="center" color="#c8ffea">100%</text>,{at:plan.e7+3,dur:.25,name:'Transfer 100 before receipt'});
 p.compose(<rect x={45} y={411} width={748} height={9} fill="#a7edd4" animate={[{property:'scaleX',from:.68,to:1,at:0,duration:3,easing:'linear'}]}/>,{at:plan.e7,dur:3.25,name:'Transfer progression'});
 p.compose(<media file={done} x={0} y={0} width={854} height={480} fit="contain" animate={[{property:'opacity',from:0,to:1,at:0,duration:.15}]}/>,{at:plan.e7+3.15,dur:1.85,name:'Red receipt confirmed'});
 // Short horizontal signal interruption, then genuine black before Q&A.
 for(const [dt,h,y] of [[0,5,164],[.08,2,308],[.16,4,241]])p.compose(<rect x={0} y={y} width={854} height={h} fill="#87908b" opacity={.25}/>,{at:plan.e7+4.65+dt,dur:.042,name:'Signal interference'});
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000" animate={[{property:'opacity',from:0,to:1,at:0,duration:.15}]}/>,{at:plan.e7+4.85,dur:.65,name:'Signal off, final black'});
 await p.render(root+'/master-picture.mp4',{draft:false,bitrate:3000000});
};
