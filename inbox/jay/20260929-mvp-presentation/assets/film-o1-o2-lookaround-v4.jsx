export default async ({project})=>{
const r='/home/user/o1join-v4';const p=await project({dir:r+'/project',size:'854x480',fps:24,background:'#000'});
const a=await p.add(r+'/o1.mp4');const b=await p.add(r+'/o2.mp4');
p.cut(a,{from:0,at:0,dur:8});p.cut(b,{from:0,at:8,dur:2.25});
await p.render(r+'/film-o1-o2-lookaround-v4.mp4',{draft:false,bitrate:3500000});
};
