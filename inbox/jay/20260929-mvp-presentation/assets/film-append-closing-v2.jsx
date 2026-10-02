export default async ({project})=>{
 const root='/home/user/append-brand';
 const p=await project({dir:root+'/project',size:'854x480',fps:24,background:'#000'});
 const master=await p.add(root+'/master.mp4'),closing=await p.add(root+'/closing.mp4');
 p.compose(<media file={master} x={0} y={0} width={854} height={480} fit="contain" muted={true}/>,{at:0,dur:69.5,name:'Existing review master unchanged'});
 p.compose(<media file={closing} x={0} y={0} width={854} height={480} fit="contain" muted={true}/>,{at:69.5,dur:281/24,name:'User supplied FOOTHOLD closing'});
 await p.render(root+'/picture.mp4',{draft:false,bitrate:4000000});
};
