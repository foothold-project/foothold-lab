// U205: reversible, click-controlled scenes. A shared background never travels twice.
const sharedMoves=[];
function sharedVisible(el){
 const slide=el.closest('.slide');
 if(el.classList.contains('technical-robot')&&['1','2','3','6','7'].includes(slide.dataset.currentStep))return false;
 if(el.closest('.army-single')&&slide.dataset.currentStep!=='0')return false;
 for(let node=el;node&&node!==slide;node=node.parentElement){const css=getComputedStyle(node);if(css.visibility==='hidden'||css.display==='none'||Number(css.opacity)<.01)return false;}
 return true;
}
function captureShared(slide){return [...slide.querySelectorAll('[data-shared]')].filter(sharedVisible).map(el=>({key:el.dataset.shared,el,rect:el.getBoundingClientRect()}))}
function animateShared(before,slide){
 sharedMoves.splice(0).forEach(x=>{x.animation.cancel();x.dest.style.visibility='';x.el.remove()});
 if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 for(const old of before){
  if(old.key==='progress')continue;
  const dest=slide.querySelector(`[data-shared="${old.key}"]`);if(!dest||!sharedVisible(dest))continue;
  const r=dest.getBoundingClientRect();
  if(Math.abs(old.rect.left-r.left)<1&&Math.abs(old.rect.top-r.top)<1&&Math.abs(old.rect.width-r.width)<1&&Math.abs(old.rect.height-r.height)<1)continue;
  const clone=dest.cloneNode(true);clone.removeAttribute('data-shared');clone.className='scene-traveler '+(dest.classList.contains('robot-cutout')?'robot-cutout':'');
  Object.assign(clone.style,{left:r.left+'px',top:r.top+'px',width:r.width+'px',height:r.height+'px',margin:'0',opacity:'1',border:'0',background:'transparent',objectFit:'contain'});
  document.body.append(clone);dest.style.visibility='hidden';
  const animation=clone.animate([{transform:`translate(${old.rect.left-r.left}px,${old.rect.top-r.top}px) scale(${old.rect.width/r.width},${old.rect.height/r.height})`},{transform:'translate(0,0) scale(1)'}],{duration:800,easing:'cubic-bezier(.22,.7,.25,1)',fill:'forwards'});
  const item={el:clone,animation,dest};sharedMoves.push(item);animation.finished.catch(()=>{}).finally(()=>{dest.style.visibility='';clone.remove();const i=sharedMoves.indexOf(item);if(i>=0)sharedMoves.splice(i,1)});
 }
}
function addRoutePets(){
 document.querySelectorAll('.route').forEach(route=>{
  const line=route.querySelector('.route-line');line.innerHTML='<svg viewBox="0 0 330 32" aria-hidden="true"><path d="M0 24 H330"/></svg><div class="route-pet"><canvas class="pixel-go2" width="128" height="128" data-row="2" aria-label="Go2 진행 표시"></canvas></div>';
  const pet=line.querySelector('.route-pet');
  const section=route.closest('.slide').querySelector('.eyebrow')?.textContent||'';
  const progress=/다음 걸음|남은 과제/.test(section)?1:/MVP 성과/.test(section)?.75:/실패에서/.test(section)?.5:/로봇의 이해|정책의 이해|학습과 평가/.test(section)?.25:0;
  pet.style.left=(progress*289)+'px';
  const labels=document.createElement('div');labels.className='route-labels';labels.innerHTML='<span>필요</span><span>질문</span><span>실험</span><span>성과</span><span>다음 걸음</span>';route.append(labels);
 });
}
addRoutePets();
const pixelAtlas=new Image();pixelAtlas.src='../assets/go2-pixel-alpha-v2.png';
let lastPixel=0;
function paintPixels(t){
 if(pixelAtlas.complete&&pixelAtlas.naturalWidth&&t-lastPixel>105){lastPixel=t;
  document.querySelectorAll('.slide.active canvas.pixel-go2,.scene-traveler canvas.pixel-go2').forEach(c=>{
   const row=Number(c.dataset.row||0),frame=matchMedia('(prefers-reduced-motion: reduce)').matches?0:Math.floor(t/130)%8;
   const ctx=c.getContext('2d'),w=pixelAtlas.naturalWidth/8,h=pixelAtlas.naturalHeight/4;
   ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(pixelAtlas,frame*w,row*h,w,h,0,0,c.width,c.height);
  });
 }
 requestAnimationFrame(paintPixels);
}
requestAnimationFrame(paintPixels);
let questionAnimation=null;
function pixelArrival(slide,stage,previous){
 const real=slide.querySelector('.question-robot'),pixel=slide.querySelector('.question-pixel'),pet=slide.querySelector('.route-pet');
 if(questionAnimation){questionAnimation.cancel();questionAnimation=null}
 pet.classList.remove('arrived');pixel.style.opacity='0';pixel.style.transform='none';real.style.opacity='1';
 if(stage!==2)return;
 real.style.opacity='0';pixel.style.opacity='1';
 const a=pixel.getBoundingClientRect(),b=pet.getBoundingClientRect(),scale=Number(getComputedStyle(document.documentElement).getPropertyValue('--scale'))||1;
 const x=(b.left-a.left)/scale,y=(b.top-a.top)/scale,shrink=b.width/a.width;
 questionAnimation=pixel.animate([{opacity:0,transform:'translate(0,0) scale(1)',offset:0},{opacity:1,transform:'translate(0,0) scale(1)',offset:.27},{opacity:1,transform:`translate(${x}px,${y}px) scale(${shrink})`,offset:1}],{duration:1400,easing:'cubic-bezier(.22,.7,.25,1)',fill:'forwards'});
 pixel.style.transformOrigin='top left';const running=questionAnimation;
 running.finished.then(()=>{if(slide.dataset.currentStep==='2'){pet.classList.add('arrived');pixel.style.opacity='0';running.cancel();questionAnimation=null}}).catch(()=>{});
}
function renderStoryState(slide,stage){
 const previous=Number(slide.dataset.currentStep??-1);slide.dataset.currentStep=stage;
 // Stop off-screen model motion and explanatory soundless clips.
 document.querySelectorAll('.technical-player,.continuous-player,.policy-v5-player,.axes-player,.fat-player').forEach(c=>{if(!slide.contains(c)){c.seq=(c.seq||0)+1;c.go2Technical?.stop();c.go2V5?.stop()}});
 slide.querySelectorAll('[data-only-step]').forEach(el=>el.classList.toggle('is-current',el.dataset.onlyStep.split(' ').includes(String(stage))));
 // U206: page 3 has no pixel migration; the route starts on page 4.
 if(slide.classList.contains('hardware-page'))playHardware(slide,stage);
 if(slide.classList.contains('policy-page'))playPolicy(slide,stage,previous);
 if(slide.classList.contains('army-page'))playArmy(slide,stage,previous);
 if(slide.classList.contains('axes-page')&&typeof playAxes==='function')playAxes(slide,stage,previous);
 if(slide.classList.contains('feetair-page')&&typeof playFeetAir==='function')playFeetAir(slide);
}
async function playHardware(slide,stage){
 // ★ 2026-10-02 v6: 캔버스 하나(.continuous-player)로 0~7 단계를 잇는다. 0~2 는 v5 그대로
 // (front · turntable · four_legs), 3 부터는 v6 구간(assemble 뒤 joints · contact+feedback ·
 // sensors · commands). 단계 n 의 시작 상태 = n-1 의 끝 상태라 넘어갈 때 바꿔칠 것이 없다.
 // 되돌릴 때(이전)는 그 단계의 끝 상태 정지화. v4 technical-player 는 더 안 쓴다(인쇄는 정지화).
 // 프레임은 build_v6.py 의 설명용 기구학이지 정책 출력이 아니다.
 const continuous=slide.querySelector('.continuous-player');if(!continuous||!window.Go2V5Player)return;
 if(window.GO2_V6_MANIFEST&&window.GO2_V5_MANIFEST&&!GO2_V5_MANIFEST.segments.commands){Object.assign(GO2_V5_MANIFEST.states,GO2_V6_MANIFEST.states);Object.assign(GO2_V5_MANIFEST.segments,GO2_V6_MANIFEST.segments);}
 slide.querySelector('.technical-player')?.go2Technical?.stop();
 const previous=continuous.lastStage;continuous.lastStage=stage;
 const seq=(continuous.seq||0)+1;continuous.seq=seq;
 const END=['front','three_quarter','four_legs','joints_close','feedback_end','sensors_end','sensors_end','commands_end'];
 const PLAY={1:['turntable'],2:['four_legs'],3:['assemble','joints'],4:['contact','feedback'],5:['sensors'],7:['commands']};
 // 카드 글줄 점등: 현재 층의 [data-from] 은 그 프레임에 닿으면 켜진다(정지화도 끝 프레임이라 전부 켜진다).
 const light=f=>{const fr=Number(f.frame)||0;slide.querySelectorAll('.tech-layer.is-current [data-from]').forEach(el=>el.classList.toggle('on',fr>=Number(el.dataset.from)));};
 if(!continuous.go2V5)continuous.go2V5=new Go2V5Player(continuous,'../assets/go2-blender',{cacheLimit:420,initial:END[stage],onFrame:light});
 const p=continuous.go2V5;p.stop();await p.ready;if(continuous.seq!==seq||!slide.classList.contains('active'))return;
 const prefetch=ids=>{for(const id of ids||[]){const seg=p.manifest.segments[id];if(!seg)continue;for(let f=seg.start;f<=seg.end;f++)p.load(seg.pattern.replace('{frame:04d}',String(f).padStart(4,'0'))).catch(()=>{});}};
 const backward=previous!==undefined&&previous>=stage;
 if(backward||!PLAY[stage]){await p.setState(END[stage]);if(continuous.seq===seq&&!backward)prefetch(PLAY[stage+1]);return;}
 await p.setState(END[stage-1]);if(continuous.seq!==seq)return;
 for(const id of PLAY[stage]){if(continuous.seq!==seq||!slide.classList.contains('active'))return;await p.playSegment(id);}
 if(continuous.seq===seq)prefetch(PLAY[stage+1]);
}
async function playPolicy(slide,stage,previous){
 // ★ 2026-10-02 v6: 0단계 정면(front6 · v5 front 와 같은 카메라) → 1단계 클릭에 그 자리에서 돌아
 // 측면(front_to_side) → 레이저가 위에서 내려와 187 점을 훑는다(scan_rays) → 2~4 단계는 scan_done 정지.
 // 캔버스 위치는 단계마다 같다(CSS). 되돌릴 때는 정지화.
 const canvas=slide.querySelector('.policy-v5-player');if(!canvas||!window.Go2V5Player)return;
 if(window.GO2_V6_MANIFEST&&window.GO2_V5_MANIFEST&&!GO2_V5_MANIFEST.segments.scan_rays){Object.assign(GO2_V5_MANIFEST.states,GO2_V6_MANIFEST.states);Object.assign(GO2_V5_MANIFEST.segments,GO2_V6_MANIFEST.segments);}
 const seq=(canvas.seq||0)+1;canvas.seq=seq;
 if(!canvas.go2V5)canvas.go2V5=new Go2V5Player(canvas,'../assets/go2-blender',{cacheLimit:200,initial:stage===0?'front6':'scan_done'});
 const p=canvas.go2V5;p.stop();await p.ready;if(canvas.seq!==seq||!slide.classList.contains('active'))return;
 const prefetch=ids=>{for(const id of ids){const seg=p.manifest.segments[id];if(!seg)continue;for(let f=seg.start;f<=seg.end;f++)p.load(seg.pattern.replace('{frame:04d}',String(f).padStart(4,'0'))).catch(()=>{});}};
 if(stage===0){await p.setState('front6');if(canvas.seq===seq)prefetch(['front_to_side','scan_rays']);return;}
 if(stage===1&&previous<1){await p.setState('front6');if(canvas.seq!==seq)return;await p.playSegment('front_to_side');if(canvas.seq!==seq)return;await p.playSegment('scan_rays');return;}
 await p.setState('scan_done');
}
function playArmy(slide,stage,previous){
 const video=slide.querySelector('video'),counter=slide.querySelector('.env-counter');
 if(stage===0){video.pause();video.currentTime=0;counter.textContent='1';return;}
 if(stage===1&&previous!==1){video.currentTime=0;video.play().catch(()=>{});counter.textContent='1';return;}
 if(stage===2){video.play().catch(()=>{});const start=performance.now(),serial=(slide.counterSerial||0)+1;slide.counterSerial=serial;
 const tick=t=>{if(slide.dataset.currentStep!=='2'||slide.counterSerial!==serial)return;const p=Math.min(1,(t-start)/2600),e=1-Math.pow(1-p,3);counter.textContent=Math.round(1+4095*e).toLocaleString('en-US');if(p<1)requestAnimationFrame(tick)};requestAnimationFrame(tick);}
}
// Explain the actual 17x11 ray pattern. Heights are schematic, not recorded telemetry.
function paintHeightGrid(t){
 const canvas=document.querySelector('.policy-page.active:not([data-current-step="0"]) .scan-canvas');
 if(canvas){const ctx=canvas.getContext('2d');ctx.clearRect(0,0,900,380);const grid=[];
  for(let i=0;i<17;i++){grid[i]=[];for(let j=0;j<11;j++){const h=i>9?14:0;grid[i][j]=[120+i*32+j*14,82+j*16-i*1.3-h];}}
  ctx.strokeStyle='#5f99886b';ctx.lineWidth=1;
  for(let i=0;i<17;i++)for(let j=0;j<11;j++){const [x,y]=grid[i][j];for(const [a,b] of [[i+1,j],[i,j+1]]){if(a<17&&b<11){ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(...grid[a][b]);ctx.stroke()}}const pulse=(Math.floor(t/150)%17)===i;ctx.fillStyle=pulse?'#13bd92':'#478d76';ctx.beginPath();ctx.arc(x,y,pulse?3:1.7,0,Math.PI*2);ctx.fill();}
 }
 requestAnimationFrame(paintHeightGrid);
}
// The height grid is now part of the same Blender render as the robot.
