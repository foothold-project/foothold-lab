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
 document.querySelectorAll('.technical-player,.continuous-player,.policy-v5-player').forEach(c=>{if(!slide.contains(c)){c.seq=(c.seq||0)+1;c.go2Technical?.stop();c.go2V5?.stop()}});
 slide.querySelectorAll('[data-only-step]').forEach(el=>el.classList.toggle('is-current',el.dataset.onlyStep.split(' ').includes(String(stage))));
 // U206: page 3 has no pixel migration; the route starts on page 4.
 if(slide.classList.contains('hardware-page'))playHardware(slide,stage);
 if(slide.classList.contains('policy-page'))playPolicy(slide,stage,previous);
 if(slide.classList.contains('army-page'))playArmy(slide,stage,previous);
}
async function playHardware(slide,stage){
 const canvas=slide.querySelector('.technical-player');if(!window.Go2TechnicalPlayer)return;
 const continuous=slide.querySelector('.continuous-player');
 if(continuous){continuous.go2V5?.stop();continuous.seq=(continuous.seq||0)+1;continuous.style.opacity='';canvas.style.visibility='';}
 // ★ 2026-10-02. 0단계도 같은 v5 캔버스를 쓴다. 전에는 0단계가 v4 정지
 // 그림(go2-front-v4.png)이고 1단계가 v5 캔버스였다. 둘은 화각도 위치도
 // 달랐고 정지 그림에 0.5초 페이드가 걸려 있어 «잔상» 으로 겹쳤다.
 // 같은 캔버스에서 front 로 서 있다가 그대로 돌기 시작하면 바꿔칠 것이 없다.
 if(stage===0||stage===1||stage===2){
  canvas.seq=(canvas.seq||0)+1;canvas.go2Technical?.stop();
  if(!continuous.go2V5)continuous.go2V5=new Go2V5Player(continuous,'../assets/go2-blender');
  const seq=continuous.seq;await continuous.go2V5.ready;
  if(continuous.seq!==seq||!slide.classList.contains('active'))return;
  await continuous.go2V5.setState(stage===2?'three_quarter':'front');
  if(continuous.seq!==seq)return;
  if(stage===0)return;                      // 0단계는 서 있기만 한다
  await continuous.go2V5.playSegment(stage===1?'turntable':'four_legs');return;
 }
 const seq=(canvas.seq||0)+1;canvas.seq=seq;
 if(!canvas.go2Technical)canvas.go2Technical=new Go2TechnicalPlayer(canvas,'../assets/go2-blender');
 const p=canvas.go2Technical;p.stop();await p.ready;if(canvas.seq!==seq)return;
 if(stage===3){
  if(continuous?.go2V5){continuous.style.opacity='1';canvas.style.visibility='hidden';await continuous.go2V5.setState('four_legs');if(canvas.seq!==seq)return;await continuous.go2V5.playSegment('assemble');if(canvas.seq!==seq||!slide.classList.contains('active'))return;continuous.style.opacity='';canvas.style.visibility='';}
  await p.setState('single_leg');for(const id of ['hip','thigh','calf']){if(canvas.seq!==seq||!slide.classList.contains('active'))return;await p.playSegment(id)}if(canvas.seq===seq)await p.setState('twelve_axes');}
 else if(stage===7){for(const id of ['forward','lateral','yaw']){if(canvas.seq!==seq||!slide.classList.contains('active'))return;await p.playSegment(id)}}
 else await p.setState('front');
}
async function playPolicy(slide,stage,previous){
 const canvas=slide.querySelector('.policy-v5-player');if(!canvas||!window.Go2V5Player)return;
 const seq=(canvas.seq||0)+1;canvas.seq=seq;
 if(!canvas.go2V5)canvas.go2V5=new Go2V5Player(canvas,'../assets/go2-blender');
 const p=canvas.go2V5;p.stop();await p.ready;if(canvas.seq!==seq)return;
 if(stage===0){await p.setState('front');return;}
 if(stage===1&&previous===0){await p.setState('assembled');if(canvas.seq!==seq)return;await p.playSegment('to_side');if(canvas.seq!==seq)return;await p.playSegment('scan');}
 else await p.setState('scan');
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
