export default async ({project})=>{
const r='/home/user/continuity-v7';const p=await project({dir:r+'/project',size:'854x480',fps:24,background:'#000'});
const a=await p.add(r+'/o1.mp4'), b=await p.add(r+'/o2-matched.mp4');
p.compose(<media file={a} trimStart={.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:0,dur:8,name:'O1 left-right-down'});
p.compose(<media file={b} trimStart={.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:8,dur:55/24,name:'O2 registered light continuity'});
await p.render(r+'/native-join.mp4',{draft:false,bitrate:4000000});};