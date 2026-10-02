export default async ({project})=>{
const r='/home/user/e5-contact-v4';const p=await project({dir:r+'/comparison-project',size:'854x480',fps:24,background:'#000'});
for(const [name,file,at] of [['BEFORE','master-v3.mp4',0],['AFTER','film-master-v4.mp4',15.25]]){
const m=await p.add(r+'/'+file);
p.compose(<media file={m} trimStart={40.25} x={0} y={0} width={854} height={480} muted={true}/>,{at,dur:14.75,name});
p.compose(<group><rect x={12} y={12} width={130} height={34} fill="#06131d" opacity={.85}/><text x={22} y={19} width={114} height={22} fontFamily="Metropolis" fontSize={18} color="#ffffff">{name}</text></group>,{at,dur:14.75,name:name+' label'});
}await p.render(r+'/comparison-picture.mp4',{draft:false,bitrate:2500000});};