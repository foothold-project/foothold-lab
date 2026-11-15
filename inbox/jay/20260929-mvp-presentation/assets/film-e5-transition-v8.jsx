export default async ({project})=>{
const r='/home/user/e5-transition-v8';const p=await project({dir:r+'/comparison-project',size:'854x480',fps:24,background:'#000'});
for(const [label,file,at] of [['BEFORE','master-v7.mp4',0],['AFTER','film-master-v8.mp4',6.5]]){
const m=await p.add(r+'/'+file);p.compose(<media file={m} trimStart={47.504} x={0} y={0} width={854} height={480} muted={true}/>,{at,dur:6,name:label});
p.compose(<group><rect x={12} y={12} width={130} height={34} fill="#06131d" opacity={.85}/><text x={22} y={19} width={114} height={22} fontFamily="Metropolis" fontSize={18} color="#fff">{label}</text></group>,{at,dur:6,name:label+' title'});
}await p.render(r+'/compare-picture.mp4',{draft:false,bitrate:3500000});};