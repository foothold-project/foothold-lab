/* English concept HUD. Values illustrate typography and motion, not measured telemetry. */
function textAt(x,y,value,size=18,extra=''){return `<text x="${x}" y="${y}" font-size="${size}" ${extra}>${value}</text>`}
function line(x1,y1,x2,y2,extra=''){return `<path d="M${x1} ${y1}L${x2} ${y2}" ${extra}/>`}
function ticks(cx,cy,r,start,end,count){return Array.from({length:count+1},(_,i)=>{let a=(start+(end-start)*i/count)*Math.PI/180,b=r+(i%5===0?14:6);return line(cx+r*Math.cos(a),cy+r*Math.sin(a),cx+b*Math.cos(a),cy+b*Math.sin(a),'class="tick"')}).join('')}
function shell(label){return `<g class="hair dim"><path d="M52 112V52H184M1416 52h132v60M52 788v60h132M1416 848h132v-60"/><path d="M290 54h1020M290 846h1020"/>${line(800,43,800,65)}${line(800,835,800,857)}</g>${textAt(76,86,'FH / FIELD SYSTEM',17,'class="soft"')}${textAt(1524,86,label,17,'text-anchor="end" class="soft"')}`}
function svg(body){return `<div class="hud"><svg class="hud-vector" viewBox="0 0 1600 900" aria-hidden="true">${body}</svg><div class="crt"></div></div>`}
function hud(type){
 if(!type)return '';
 if(type==='brand')return `<div class="qa-slide"><img src="../assets/foothold-lockup-compact-dark.svg" alt="FOOTHOLD"><div class="qa-word">Q&amp;A</div><a href="https://foothold-project.vercel.app" target="_blank" rel="noopener">foothold-project.vercel.app</a></div>`;
 let s=shell(type==='mission'?'MISSION BRIEF':type==='observe'?'TERRAIN VIEW':type==='record'?'RECORDING':'DATA LINK');
 if(type==='mission'){
 s+=`<g class="hair dim">${ticks(380,437,134,-150,150,60)}<circle cx="380" cy="437" r="112" stroke-dasharray="184 20 67 28"/><path d="M260 437h54m132 0h54M380 317v52m0 137v51"/><path d="M333 455l47-69 47 69-47-17z"/></g>`;
 s+=textAt(380,634,'FIELD / 01',17,'text-anchor="middle" class="soft"')+textAt(620,270,'INCOMING ASSIGNMENT',19,'class="soft spaced"')+textAt(616,359,'MISSION',78,'class="title"')+`<g class="hair">${line(620,395,1330,395)}<path d="M620 395h84" stroke-width="4"/></g>`+textAt(620,468,'REACH THE TARGET',32)+textAt(620,522,'CAPTURE SITE STATUS',32)+textAt(620,624,'GO2 / FIELD INSPECTION',18,'class="soft spaced"')+textAt(620,660,'AWAITING VISUAL FEED_',18,'class="soft cursor"');
 }
 if(type==='observe'){
 s+=`<g class="hair soft">${ticks(177,596,82,-150,150,30)}<path d="M96 596h45m73 0h44M153 582l24 14 24-14"/><g transform="rotate(-4 177 596)"><path d="M121 596h112M151 570h52M160 548h34M151 622h52"/></g></g>`+textAt(86,474,'ATTITUDE',18,'class="soft"')+textAt(86,740,'ROLL   +04.0°',19)+textAt(86,774,'PITCH  -02.0°',19);
 s+=`<g class="hair dim">${Array.from({length:13},(_,i)=>line(1480,230+i*31,1490+(i%3===0?13:0),230+i*31)).join('')}</g>`+textAt(1430,219,'BODY RATE',16,'text-anchor="end" class="soft"')+textAt(1430,251,'-0.01 rad/s',21,'text-anchor="end"');
 s+=`<g class="terrain-focus hair"><path d="M565 647l152-68 232 51-187 95z" fill="#67ffbd0a" stroke-dasharray="8 7"/><path d="M565 647l27-12m-27 12 27 14M949 630l-29-7m29 7-25 14M762 725l-27-11m27 11 25-13" stroke-width="3"/><path d="M949 630L1040 582"/></g>`+textAt(1060,548,'HEIGHT SAMPLE',16,'class="soft"')+textAt(1060,583,'+0.12 m',27)+textAt(660,783,'LOCAL TERRAIN',16,'class="soft spaced"');
 s+=`<g class="hair dim">${line(1060,658,1432,658)}</g>`+textAt(1060,689,'VELOCITY',16,'class="soft"')+textAt(1250,689,'CMD',16,'text-anchor="end" class="soft"')+textAt(1432,689,'STATE',16,'text-anchor="end" class="soft"');
 [['VX / m/s','0.80','0.72'],['VY / m/s','0.00','0.02'],['WZ / rad/s','0.00','-0.01']].forEach((r,i)=>{let y=727+i*30;s+=textAt(1060,y,r[0],17)+textAt(1250,y,r[1],21,'text-anchor="end"')+textAt(1432,y,r[2],21,'text-anchor="end"')});
 s+=textAt(82,149,'APPROACH / TARGET',17,'class="soft"')+textAt(1518,149,'WLAN / LINK',17,'text-anchor="end" class="soft"');
 }
 if(type==='record'){
 s+=`<circle cx="92" cy="143" r="6" fill="#ed7566"/>`+textAt(111,150,'REC',22)+textAt(1518,150,'00:00:03',24,'text-anchor="end"');
 s+=`<g class="hair soft"><path d="M431 300v-30h48M1121 270h48v30M431 630v30h48M1121 660h48v-30"/>${line(775,245,825,245)}${line(775,685,825,685)}</g>`+textAt(800,735,'CAPTURE / SITE STATUS',19,'text-anchor="middle" class="spaced"')+textAt(82,792,'FIELD RECORDING',17,'class="soft"')+textAt(1518,792,'WLAN / READY',17,'text-anchor="end" class="soft"');
 }
 if(type==='transfer'){
 s+=`<g class="hair soft">${ticks(367,436,94,-180,135,42)}<path d="M340 435l20 20 38-44" stroke-width="3"/></g>`+textAt(570,339,completed?'RECEIPT CONFIRMED':'FIELD RECORDING',18,'class="soft spaced"')+textAt(566,418,completed?'MISSION CLEAR':'TRANSMITTING',52,'class="title"')+textAt(570,480,completed?'SITE DATA RECEIVED':'SENDING SITE DATA',23);
 s+=`<g class="hair dim">${line(570,559,1360,559)}</g><path class="hair" stroke-width="3" d="M570 559h${completed?790:537}"/>`+textAt(570,613,completed?'LINK CLOSED':'WLAN / ACTIVE',17,'class="soft"')+textAt(1360,613,completed?'100%':'68%',28,'text-anchor="end"');
 }
 return svg(s);
}
