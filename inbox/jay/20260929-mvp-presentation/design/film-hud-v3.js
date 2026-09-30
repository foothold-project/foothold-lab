/* Procedural concept geometry and example telemetry. Not a live sensor display. */
function tx(x,y,v,z=18,c=''){return `<text x="${x}" y="${y}" font-size="${z}" class="${c}">${v}</text>`}
function ln(x,y,a,b,c=''){return `<path d="M${x} ${y}L${a} ${b}" class="stroke ${c}"/>`}
function circle(x,y,r,c='',extra=''){return `<circle cx="${x}" cy="${y}" r="${r}" class="stroke ${c}" ${extra}/>`}
function polar(x,y,r,a){a*=Math.PI/180;return [x+r*Math.cos(a),y+r*Math.sin(a)]}
function arc(x,y,r,a,b,c='',width=2){const p=polar(x,y,r,a),q=polar(x,y,r,b);return `<path class="stroke ${c}" style="stroke-width:${width}px" d="M${p}A${r} ${r} 0 ${b-a>180?1:0} 1 ${q}"/>`}
function ticks(x,y,r,n=100){return `<g class="stroke tick">${Array.from({length:n},(_,i)=>{const p=polar(x,y,r,i*360/n),q=polar(x,y,r+(i%5?6:14),i*360/n);return `<path d="M${p}L${q}"/>`}).join('')}</g>`}
function ring(x,y,r,pct=68){if(r<60)return circle(x,y,r,'faint')+circle(x,y,r-8,'soft','stroke-dasharray="2 4"')+ticks(x,y,r+8,36)+arc(x,y,r,-90,240,'lit',3);let s=circle(x,y,r,'faint')+circle(x,y,r-11,'soft','stroke-dasharray="2 8"')+ticks(x,y,r+18,90);for(let i=0;i<12;i++)s+=arc(x,y,r,i*30+2,i*30+25,i<Math.round(pct*.12)?'lit':'faint',6);return s+arc(x,y,r-27,-140,60,'soft',2)+arc(x,y,r-39,75,242,'lit',1)}
function cutFrame(x,y,w,h,label){return `<path class="stroke frame-line" fill="#00160d35" d="M${x+18} ${y}H${x+w-40}l40 32V${y+h-18}l-18 18H${x+30}l-30-25V${y+18}z"/>${tx(x+20,y+30,label,15,'soft')}`}
function wave(x,y,w,h,phase=0){let pts=[];for(let i=0;i<=64;i++){let v=Math.sin(i*.49+phase)*.15+Math.sin(i*1.43+phase)*.11+Math.sin(i*.13)*.17;pts.push(`${x+i*w/64},${y+h/2+v*h}`)}return `<g class="stroke grid faint">${[0,.25,.5,.75,1].map(v=>ln(x,y+v*h,x+w,y+v*h)).join('')}</g><polyline class="stroke lit" points="${pts.join(' ')}"/>`}
function bars(x,y,w,h,n=35){return Array.from({length:n},(_,i)=>{let v=.16+.75*Math.abs(Math.sin(i*.36)*Math.cos(i*.17));return `<rect x="${x+i*w/n}" y="${y+h-v*h}" width="${w/n-3}" height="${v*h}" class="bar-fill"/>`}).join('')}
function contour(x,y,w,h){let s='';for(let j=0;j<17;j++){let pts=[];for(let i=0;i<=55;i++){let t=i/55;let z=Math.sin(t*6.6+j*.10)*.19+Math.cos(t*13.1+j*.22)*.07;pts.push(`${x+t*w},${y+h*(j/20+.08+z*.4)}`)}s+=`<polyline class="stroke ${j%4?'faint':'soft'}" points="${pts.join(' ')}"/>`}return s}
function mesh(x,y,w,h){function point(i,j){let u=i/20,v=j/14;let bump=Math.exp(-((u-.38)**2+(v-.52)**2)*23)*.43+Math.sin(u*12+v*5)*.06;return `${x+u*w+(v-.5)*w*.11},${y+v*h-bump*h}`};let s='';for(let j=0;j<=14;j++)s+=`<polyline class="stroke ${j%4?'faint':'soft'}" points="${Array.from({length:21},(_,i)=>point(i,j)).join(' ')}"/>`;for(let i=0;i<=20;i++)s+=`<polyline class="stroke faint" points="${Array.from({length:15},(_,j)=>point(i,j)).join(' ')}"/>`;return s}
function header(label){return `<g class="stroke"><path d="M38 172V60l26-24h461l20 18h510l20-18h461l26 24v112M38 728v112l26 24h461l20-18h510l20 18h461l26-24V728"/><path class="faint" d="M49 200v500M1551 200v500M60 47h432M1108 47h432M60 853h432M1108 853h432"/></g>${tx(74,93,'FOOTHOLD / FIELD SYSTEM',19)}${tx(1140,93,label,19)}${tx(74,126,'GO2 / SENSOR INTERFACE',13,'soft')}${tx(1290,126,'WLAN : ACTIVE',13,'soft')}<path class="stroke lit" stroke-width="3" d="M596 54h120m168 0h120"/>${tx(771,60,'FH',17)}${Array.from({length:17},(_,i)=>ln(520+i*35,78,520+i*35,85+(i%4?0:5),'faint')).join('')}`}
function bottom(){return tx(74,830,'VISUAL FEED / LOCAL TERRAIN',13,'soft')+tx(1170,830,'LINK / RECORD / TRANSFER',13,'soft')+`<g class="stroke faint">${Array.from({length:36},(_,i)=>ln(492+i*17,825,492+i*17,833+(i%5?0:7))).join('')}</g>`}
function attitude(x,y,r){return ring(x,y,r,100)+`<g class="stroke lit"><path d="M${x-r+18} ${y}h55m${r*2-146} 0h55"/><g transform="rotate(0 ${x} ${y})"><path d="M${x-48} ${y}h96m-76-26h56m-45-23h34m-45 75h56"/></g><path d="M${x-24} ${y-2}l24 12 24-12"/></g>`}
function svg(s){return `<div class="hud"><svg class="hud-vector" viewBox="0 0 1600 900" aria-hidden="true"><defs><linearGradient id="hudShade" x1="0" x2="1"><stop stop-color="#00110ae8"/><stop offset=".28" stop-color="#00110a00"/><stop offset=".72" stop-color="#00110a00"/><stop offset="1" stop-color="#00110ae8"/></linearGradient></defs><rect width="1600" height="900" fill="url(#hudShade)"/>${s}</svg><div class="crt"></div></div>`}
function hud(type){if(!type)return '';if(type==='brand')return '<div class="qa-slide"><div class="qa-word">Q&amp;A</div></div>';let s=header(type==='mission'?'MISSION CONTROL':type==='observe'?'TERRAIN ANALYSIS':type==='record'?'FIELD CAPTURE':'DATA TRANSFER')+bottom();
 if(type==='mission'){
 s+=cutFrame(76,166,665,537,'TERRAIN / TOPOGRAPHIC VIEW')+ring(407,429,187,75)+circle(407,429,150,'faint')+`<g opacity=".8">${mesh(219,365,372,172)}</g>`+tx(373,449,'GO2',28)+tx(344,482,'FIELD UNIT',14,'soft')+`<path class="stroke lit" d="M390 326l17-24 17 24-17-8z"/>`+ln(407,290,407,272)+tx(300,664,'ENVIRONMENT / UNMAPPED',15,'soft');
 s+=tx(816,220,'INCOMING ASSIGNMENT',18,'soft spaced')+tx(811,305,'MISSION',76,'title')+ln(816,338,1517,338)+tx(818,400,'01',17,'accent')+tx(875,401,'REACH THE TARGET',29)+tx(818,463,'02',17,'accent')+tx(875,464,'CAPTURE SITE STATUS',29)+cutFrame(817,515,700,187,'EXECUTION SEQUENCE');
 [925,1165,1405].forEach((x,i)=>{s+=ring(x,615,30,100)+tx(x-21,622,['GO','REC','TX'][i],17)+tx(x-45,669,['APPROACH','CAPTURE','TRANSFER'][i],14,'soft');if(i<2)s+=ln(x+52,615,x+182,615,'faint')});
 s+=tx(91,759,'INPUT / BODY STATE',17,'soft')+tx(91,791,'INPUT / TERRAIN HEIGHT',17,'soft')+tx(818,759,'VISUAL FEED : STANDBY',17)+tx(818,791,'AWAITING TERRAIN SCAN_',16,'soft');
 }
 if(type==='observe'){
 s+=cutFrame(72,174,300,385,'BODY / ATTITUDE')+attitude(222,349,82)+tx(94,497,'ROLL   --°',21)+tx(94,533,'PITCH  --°',21);
 s+=cutFrame(1230,174,300,284,'VELOCITY / TRACKING')+tx(1250,241,'AXIS',15,'soft')+tx(1350,241,'CMD',15,'soft')+tx(1440,241,'STATE',15,'soft');
 ['VX','VY','WZ'].forEach((v,i)=>s+=tx(1250,291+i*48,v,20)+tx(1350,291+i*48,'--',20)+tx(1440,291+i*48,'--',20));
 s+=tx(1250,430,'VX,VY m/s / WZ rad/s',12,'soft')+tx(93,625,'BODY ORIENTATION',15,'soft')+tx(1250,517,'COMMAND / RESPONSE',15,'soft');
 s+=`<path class="stroke soft" d="M431 258v-28h57M1112 230h57v28M431 609v28h57M1112 637h57v-28"/>`+tx(625,719,'TERRAIN OBSERVATION',18,'soft spaced');
 }
 if(type==='record'){
 s+=`<circle cx="92" cy="196" r="6" fill="#ed7566"/>`+tx(112,204,'REC',29)+tx(1225,204,'00:00:03',31)+cutFrame(73,267,261,230,'CAPTURE / CHANNEL')+tx(95,347,'TARGET / 01',19)+tx(95,383,'INSPECTION UNIT',16)+tx(95,464,'VIDEO / ACTIVE',16)+cutFrame(1266,267,261,230,'IMAGE / SIGNAL')+tx(1286,347,'TARGET / 02',19)+tx(1286,383,'BEACON',16)+tx(1286,464,'FRAME / RECORD',16);
 s+=`<g class="cv-target stroke"><path class="faint" d="M436 205H1094V727H436z"/><path class="lit" style="stroke-width:3" d="M436 258v-53h58M1036 205h58v53M436 674v53h58M1036 727h58v-53"/><path d="M725 55h118v156H725z"/><path class="soft" d="M725 120l-42-8H552"/></g>`+tx(446,243,'01 / INSPECTION TARGET',18)+tx(552,99,'02 / BEACON',16,'soft')+tx(951,737,'TRACK 01 / LOCKED',16,'soft');
 [[503,330],[1097,329],[522,673],[1080,673],[908,413],[1001,543],[790,342],[796,650]].forEach(([x,y])=>{s+=`<g class="stroke cv-feature"><circle cx="${x}" cy="${y}" r="4"/><path d="M${x-10} ${y}h5m10 0h5M${x} ${y-10}v5m0 10v5"/></g>`});
 s+=`<g class="cv-scan stroke lit"><path d="M484 313h650"/><path d="M484 318h650" class="faint"/></g>`+tx(95,585,'FIELD RECORDING',15,'soft')+tx(95,639,'CAPTURE / ACTIVE',16)+tx(1286,585,'FEATURE TRACKING',15,'soft')+tx(1286,639,'TRACK / 01 + 02',16);

 }
 if(type==='transfer'&&completed){
 const done=tx(800,178,'FIELD REPORT / RECEIPT CONFIRMED',18,'done-center soft')+
 ring(800,351,96,100)+tx(800,376,'100%',63,'done-center title')+
 tx(800,553,'MISSION COMPLETE',72,'done-center title')+
 tx(800,610,'SITE DATA RECEIVED',22,'done-center soft')+
 `<path class="stroke lit" d="M342 687H1258" style="stroke-width:7"/><path class="stroke soft" d="M260 262V208h90M1250 208h90v54M260 660v65h90M1250 725h90v-65"/>`+
 tx(800,759,'CAPTURE / TRANSFER / CONFIRMED',16,'done-center soft');
 return svg(done).replace('class="hud"','class="hud mission-complete"');
 }
 if(type==='transfer'){
 s+=cutFrame(76,166,685,569,'RECORDING / TRANSFER STATUS')+ring(421,440,203,completed?100:68)+circle(421,440,150,'faint')+circle(421,440,128,'soft','stroke-dasharray="2 10"')+tx(completed?311:346,467,completed?'100%':'68%',79,'title')+tx(355,517,completed?'RECEIVED':'UPLOADING',17,'soft')+arc(421,440,159,-90,completed?269:155,'lit',4)+tx(300,696,completed?'RECEIPT / CONFIRMED':'LINK / TRANSMITTING',16,'soft');
 s+=tx(823,221,'FIELD DATA / UPLINK',17,'soft spaced')+tx(818,301,completed?'MISSION':'DATA',66,'title')+tx(818,372,completed?'COMPLETE':'TRANSFER',66,'title')+ln(823,405,1517,405)+tx(825,463,completed?'SITE DATA RECEIVED':'SENDING SITE RECORDING',24);
 ['CAPTURE COMPLETE',completed?'TRANSFER COMPLETE':'TRANSFER IN PROGRESS',completed?'RECEIPT CONFIRMED':'AWAITING RECEIPT'].forEach((v,i)=>{let y=524+i*49;s+=circle(835,y-6,6,i===2&&!completed?'faint':'lit')+tx(858,y,v,17,i===2&&!completed?'soft':'')});
 s+=tx(833,697,completed?'CAPTURE > TRANSFER > RECEIVED':'CAPTURE > TRANSFER > WAIT',16,'soft')+`<g class="stroke">${Array.from({length:60},(_,i)=>`<path d="M${92+i*24} 772v23" stroke-width="13" class="${i<(completed?60:41)?'lit':'faint'}"/>`).join('')}</g>`+tx(823,735,completed?'END OF TRANSMISSION':'WLAN / ACTIVE',14,'soft');
 }
 return svg(s);
}
