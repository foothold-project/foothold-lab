/* 두 잣대 장 + 21쪽 feet_air_time · v6 세그먼트(walk_side · to_commands · commands)를 v5 플레이어로 재생.
   프레임은 build_v6.py 의 설명용 기구학이다. 정책 출력이 아니다. */
(function(){
 if(window.GO2_V6_MANIFEST&&window.GO2_V5_MANIFEST){Object.assign(GO2_V5_MANIFEST.states,GO2_V6_MANIFEST.states);Object.assign(GO2_V5_MANIFEST.segments,GO2_V6_MANIFEST.segments);}
})();
const AXES_BASE='../assets/go2-blender';
const WALK_T0=864,WALK_LO=888,WALK_HI=935,WALK_CYCLE=24;      // build_v6.py gait_pose: (frame-864)/24 주기
const LEG_PHASE={FL:0,RR:0,FR:Math.PI,RL:Math.PI};            // 트롯: FL·RR 같이, FR·RL 같이
function v6Frames(p,segId,lo,hi){const seg=p.manifest.segments[segId];return Promise.all(Array.from({length:hi-lo+1},(_,i)=>p.load(seg.pattern.replace('{frame:04d}',String(lo+i).padStart(4,'0')))));}
function v6Player(canvas,onFrame,initial){if(!canvas.go2V5)canvas.go2V5=new Go2V5Player(canvas,AXES_BASE,{initial:initial||'side_walk',cacheLimit:260,onFrame:onFrame||(()=>{})});return canvas.go2V5;}
// 램프(864~887) 한 번 뒤 루프(888~935)를 ms 동안 24 fps 로 그린다. canvas.seq 가 바뀌면 멈춘다.
function walkFor(canvas,p,seq,ramp,loop,ms){return new Promise(res=>{const t0=performance.now();
 const tick=now=>{if(canvas.seq!==seq){res(false);return;}const el=now-t0;const k=Math.floor(el/1000*24);let im,f;
  if(k<ramp.length){im=ramp[k];f=WALK_T0+k;}else{const j=(k-ramp.length)%loop.length;im=loop[j];f=WALK_LO+j;}
  p.paint(im,'walk_side',f);if(el>=ms){res(true);return;}requestAnimationFrame(tick);};requestAnimationFrame(tick);});}
function axesFrame(slide,f){if(f.state!=='commands')return;slide.querySelectorAll('.cmd-card').forEach(c=>c.classList.toggle('on',f.frame>=Number(c.dataset.from)));}
async function playAxes(slide,stage,previous){
 const canvas=slide.querySelector('.axes-player');if(!canvas||!window.Go2V5Player)return;
 const seq=(canvas.seq||0)+1;canvas.seq=seq;
 slide.querySelectorAll('.cond-card[data-on-from]').forEach(c=>c.classList.toggle('on',stage>=Number(c.dataset.onFrom)));
 if(stage===7)slide.querySelectorAll('.cmd-card').forEach(c=>c.classList.add('on'));
 slide.dataset.axis=stage>=6?'2':'1';
 const setPos=(pos,cls)=>{slide.classList.remove('axes-animating','axes-turning');if(cls)slide.classList.add(cls);slide.dataset.pos=String(pos);};
 const p=v6Player(canvas,f=>axesFrame(slide,f),'scan_done');p.stop();await p.ready;if(canvas.seq!==seq)return;
 if(stage===0){setPos(0);await p.setState('scan_done');return;}   // 11쪽 끝 포즈(격자)에서 시작
 if(stage<=5){
  const restart=previous<=0||previous>=6||slide.dataset.pos!=='w1';
  if(!restart)return;                                   // 1~5 사이 이동: 로봇은 그 자리, 카드만 켜진다
  await p.setState('scan_done');if(canvas.seq!==seq)return;
  setPos(0);void canvas.offsetWidth;
  setPos('w0','axes-turning');                          // 격자가 꺼지고 정면을 지나 오른쪽 옆모습으로 돈다 · 캔버스는 트랙 출발점으로
  await p.playSegment('scan_to_walk');if(canvas.seq!==seq)return;
  const ramp=await v6Frames(p,'walk_side',WALK_T0,WALK_LO-1),loop=await v6Frames(p,'walk_side',WALK_LO,WALK_HI);
  if(canvas.seq!==seq)return;
  setPos('w1','axes-animating');                        // 4.5 s 동안 트랙을 건넌다
  await walkFor(canvas,p,seq,ramp,loop,4500);
  return;
 }
 if(previous<6){                                        // 옆모습 → 그 자리에서 돌아 명령 장면으로
  await p.setState('side_walk');if(canvas.seq!==seq)return;
  setPos(2,'axes-turning');
  await p.playSegment('to_commands');if(canvas.seq!==seq)return;
  await p.playSegment('commands');return;
 }
 setPos(2);
 if(stage===6){await p.setState('commands_start');if(canvas.seq!==seq)return;await p.playSegment('commands');}
 else await p.setState('commands_end');
}
// 21쪽: 같은 걷기 위에 발 네 개의 공중 시간 막대. 2주기 느리게(공중 > 0.5 s) · 2주기 빠르게(공중 < 0.5 s).
async function playFeetAir(slide){
 const canvas=slide.querySelector('.fat-player');if(!canvas||!window.Go2V5Player)return;
 const seq=(canvas.seq||0)+1;canvas.seq=seq;
 const p=v6Player(canvas);p.stop();await p.ready;if(canvas.seq!==seq)return;
 const loop=await v6Frames(p,'walk_side',WALK_LO,WALK_HI);if(canvas.seq!==seq)return;
 const rows={};slide.querySelectorAll('.fat-row').forEach(r=>{rows[r.dataset.leg]={fill:r.querySelector('.fat-bar i'),badge:r.querySelector('.fat-badge'),air:0,wasAir:false,timer:0};});
 const THR=0.5,SCALE=0.8;let mode=0,cyc=0,idx=0,acc=0,last=performance.now();slide.dataset.fatMode='0';
 const tick=now=>{if(canvas.seq!==seq)return;const dt=Math.min(.05,(now-last)/1000);last=now;const fps=mode?38.4:18;acc+=dt*fps;
  while(acc>=1){acc-=1;idx++;if(idx>=loop.length){idx=0;if(++cyc>=2){cyc=0;mode=1-mode;slide.dataset.fatMode=String(mode);}}}
  const f=WALK_LO+idx;p.paint(loop[idx],'walk_side',f);const t=(f-WALK_T0)/WALK_CYCLE;
  for(const leg in rows){const r=rows[leg];const inAir=Math.sin(2*Math.PI*t+LEG_PHASE[leg])>0.02;
   if(inAir){r.air+=dt;r.wasAir=true;r.fill.style.width=(Math.min(1,r.air/SCALE)*100)+'%';}
   else if(r.wasAir){const d=r.air-THR;r.badge.textContent=(d>=0?'+':'−')+Math.abs(d).toFixed(2)+' s';r.badge.className='fat-badge '+(d>=0?'ok':'bad');r.timer=now;r.air=0;r.wasAir=false;r.fill.style.width='0%';}
   if(r.timer&&now-r.timer>900){r.badge.className='fat-badge';r.timer=0;}
  }
  requestAnimationFrame(tick);};
 requestAnimationFrame(tick);
}
