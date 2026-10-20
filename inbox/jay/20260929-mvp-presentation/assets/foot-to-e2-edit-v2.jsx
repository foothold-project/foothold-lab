export default async ({project}) => {
 const p=await project({dir:"/home/user/foot-e2-v2/project",size:"854x480",fps:24,background:"#000"});
 const f=await p.add("/home/user/foot-e2-v2/foot.mp4"), e=await p.add("/home/user/foot-e2-v2/e2.mp4"), a=await p.add("/home/user/foot-e2-v2/mix.wav");
 p.cut(a,{at:0,from:0,dur:9});
 p.compose(<media file={f} x={0} y={0} width={854} height={480} fit="contain" muted={true}/>,{at:0,dur:5,name:"Approved foot, unchanged speed"});
 p.compose(<media file={e} x={0} y={0} width={854} height={480} fit="contain" muted={true}/>,{at:5.25,dur:3.75,name:"Approved E2, unchanged speed"});
 p.compose(<rect x={0} y={0} width={854} height={480} fill={{kind:"linear",angle:0,stops:[{offset:0,color:"#000",opacity:1},{offset:0.32,color:"#000",opacity:0.85},{offset:0.72,color:"#000",opacity:0.12},{offset:1,color:"#000",opacity:0}]}} animate={[{property:"opacity",from:0,to:1,at:0,duration:0.65,easing:"smooth"}]}/>,{at:4.0,dur:1,name:"Soft loss of light on left; retain right landing lip"});
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000" animate={[{property:"opacity",keyframes:[{at:0,value:0},{at:0.5,value:1},{at:0.75,value:1},{at:0.875,value:0}],easing:"smooth"}]}/>,{at:4.5,dur:0.916666667,name:"Final light decay, black hold, short E2 reveal"});
 await p.render("renders/foot-to-e2-v2.mp4",{draft:false});
};
