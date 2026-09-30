// E7 approved-image animation. Native Higgsedit, not generated footage.
export default async ({project})=>{
 const root='/home/user/foothold-e7';
 const p=await project({dir:root+'/project',size:'854x480',fps:24,background:'#000'});
 const tx=await p.add(root+'/transfer.png'),done=await p.add(root+'/complete.png'),audio=await p.add(root+'/mix.wav');
 p.cut(audio,{at:0,from:0,dur:5});
 p.compose(<media file={tx} x={0} y={0} width={854} height={480} fit="contain"/>,{at:0,dur:2.8,name:'Approved transfer'});
 p.compose(<rect x={181} y={217} width={86} height={39} radius={2} fill="#0b211c"/>,{at:0,dur:2.8,name:'Percentage field'});
 for(let k=0;k<=32;k++){
  const at=k*2.5/32,dur=k===32?.3:2.5/32;
  p.compose(<group><rect x={181} y={217} width={86} height={39} radius={2} fill="#0b211c"/><text x={181} y={217} width={86} height={39} fontFamily="JetBrains Mono" fontSize={k===32?33:36} color="#c7ffea" align="center">{(68+k)+'%'}</text></group>,{at,dur,name:'Transfer '+(68+k)});
 }
 // Existing lit segments are retained; fill only the remaining 32 percent.
 for(let k=0;k<19;k++)p.compose(<rect x={570+k*12.8} y={410} width={7} height={13} fill="#c7ffea"/>,{at:(k+1)*2.5/19,dur:2.8-(k+1)*2.5/19,name:'Progress segment '+k});
 p.compose(<media file={done} x={0} y={0} width={854} height={480} fit="contain" animate={[{property:'opacity',from:0,to:1,at:0,duration:.125}]}/>,{at:2.675,dur:1.575,name:'Receipt confirmed red'});
 // Brief horizontal disturbances affect the entire feed and then terminate.
 for(const [at,dur,x] of [[4.25,.083,-9],[4.333,.084,0],[4.417,.083,6],[4.5,.15,0]]){
  p.compose(<media file={done} x={x} y={0} width={854} height={480} fit="contain"/>,{at,dur,name:'Signal disturbance '+at});
 }
 for(const [at,y,h] of [[4.25,168,5],[4.417,298,3],[4.5,226,2]])p.compose(<rect x={0} y={y} width={854} height={h} fill="#9fa5a3" opacity={.3}/>,{at,dur:.042,name:'Interference stripe '+at});
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000"/>,{at:4.65,dur:.35,name:'Complete black tail'});
 await p.render(root+'/e7.mp4',{draft:false,bitrate:3000000});
};
