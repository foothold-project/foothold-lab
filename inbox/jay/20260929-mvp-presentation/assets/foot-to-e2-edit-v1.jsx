export default async ({project}) => {
 const p=await project({dir:"/home/user/foot-e2/project",size:"854x480",fps:24,background:"#000"});
 const f=await p.add("/home/user/foot-e2/foot.mp4");
 const e=await p.add("/home/user/foot-e2/e2.mp4");
 p.cut(f,{from:0,dur:5,at:0,fit:"contain"});
 p.cut(e,{from:0,dur:3.75,at:5,fit:"contain"});
 p.compose(<rect x={0} y={0} width={854} height={480} fill="#000" animate={[{property:"offsetX",from:-854,to:0,at:0,duration:0.3333333333,easing:"smooth"},{property:"opacity",from:1,to:0,at:0.625,duration:0.375,easing:"smooth"}]}/>,{at:4.625,dur:1.0416666667,name:"Left-to-right black wipe, hold, reveal"});
 await p.render("renders/foot-to-e2-v1.mp4",{draft:false});
};
