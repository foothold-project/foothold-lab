export default async ({project})=>{
const r='/home/user/e5-out-v5';const src=r+'/master-v4.mp4';
const p=await project({dir:r+'/master-project',size:'854x480',fps:24,background:'#000'});const m=await p.add(src);
p.compose(<media file={m} trimStart={0} x={0} y={0} width={854} height={480} muted={true}/>,{at:0,dur:1205/24,name:'Before shortened POV out'});
p.compose(<media file={m} trimStart={1207/24+.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:1205/24,dur:(1949-1207)/24,name:'E5 and remaining ending'});
await p.render(r+'/picture-v5.mp4',{draft:false,bitrate:4500000});
const q=await project({dir:r+'/comparison-project',size:'854x480',fps:24,background:'#000'});const a=await q.add(src);
for(const [i,n] of [0,1,2].entries()){
const at=i*7.5,begin=47.5,tail=1207/24-n/24;
q.compose(<media file={a} trimStart={begin+.004} x={0} y={0} width={854} height={480} muted={true}/>,{at,dur:tail-begin,name:'POV '+n});
q.compose(<media file={a} trimStart={1207/24+.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:at+tail-begin,dur:7-(tail-begin),name:'Climb '+n});
q.compose(<group><rect x={12} y={12} width={255} height={34} fill="#06131d" opacity={.85}/><text x={22} y={19} width={240} height={22} fontFamily="Metropolis" fontSize={18} color="#fff">{['ORIGINAL','POV OUT -1 FRAME','POV OUT -2 FRAMES'][i]}</text></group>,{at,dur:7,name:'Label '+n});
}
await q.render(r+'/compare-picture.mp4',{draft:false,bitrate:3500000});
};