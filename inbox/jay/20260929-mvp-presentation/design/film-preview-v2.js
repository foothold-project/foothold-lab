const stage=document.querySelector('.stage'), statusLine=document.querySelector('.motion-status');
let previewTimers=[];
function stopPreview(){previewTimers.forEach(clearTimeout);previewTimers=[];stage.dataset.phase='still'}
function showStage(id,phase,label){const entry=all.find(x=>x.d[0]===id);const f=entry.fig.querySelector('.frame').cloneNode(true);f.removeAttribute('role');f.removeAttribute('tabindex');if(id==='E7'){f.querySelector('.hud')?.remove();f.insertAdjacentHTML('beforeend',hud('transfer'))}stage.querySelector('.stage-body').replaceChildren(f);stage.dataset.phase=phase;statusLine.textContent=label}
function schedule(steps,duration){stopPreview();document.querySelector('.demo-track i').style.width='0%';steps.forEach(([ms,fn])=>previewTimers.push(setTimeout(()=>{fn();document.querySelector('.demo-track i').style.width=(ms/duration*100)+'%'},ms)));previewTimers.push(setTimeout(()=>document.querySelector('.demo-track i').style.width='100%',duration))}
function preview(mode){
 if(mode==='intro')schedule([[0,()=>showStage('O1','black','완전한 블랙에서 시작')],[650,()=>showStage('O1','reveal-dark','가까운 바닥에 빛이 들어옴')],[700,()=>{stage.dataset.phase='reveal'}],[2300,()=>showStage('O2','still','가까운 디딤의 끝')],[4000,()=>showStage('O3','still','가야 할 곳이 보임')]],5500);
 if(mode==='mission')schedule([[0,()=>showStage('O3','still','목표 확인 후 시야 전환')],[900,()=>showStage('O4','black','블랙 · 신호음 진입 지점')],[1500,()=>showStage('O4','boot','신호 수신 · 화면 활성화')],[1800,()=>showStage('O4','flicker','MISSION 활성화')],[2150,()=>{stage.dataset.phase='mission';statusLine.textContent='임무 문구를 읽는 구간'}],[4500,()=>{stage.dataset.phase='blend';statusLine.textContent='배경 시야가 서서히 돌아옴'}],[5500,()=>showStage('O5','still','가까운 디딤과 몸 상태 관측')]],6600);
 if(mode==='observe'){stopPreview();showStage('O5','still','관측 HUD · 예시 데이터. 실제 실험 수치가 아닙니다.')}
 if(mode==='reveal')schedule([[0,()=>showStage('E2','reveal-dark','어둠 속 높은 정면 시점')],[1000,()=>{stage.dataset.phase='reveal';statusLine.textContent='배경과 Go2가 함께 드러남'}]],3000);
 if(mode==='ending')schedule([[0,()=>{completed=false;showStage('E7','still','현장 영상 전송 중')}],[1800,()=>{completed=true;showStage('E7','still','수신 확인 · MISSION CLEAR')}],[4000,()=>{stage.dataset.phase='flicker';statusLine.textContent='신호 끊김 · 화면 종료'}],[4350,()=>{stage.dataset.phase='shutdown'}],[4550,()=>{stage.dataset.phase='off';statusLine.textContent='영상 종료 · 블랙 유지. 다음 슬라이드로 이동'}]],5000);
 if(mode==='qa'){stopPreview();showStage('Q1','still','별도 Q&A 슬라이드 · 로고와 홈페이지 유지')}
}
document.querySelectorAll('[data-demo]').forEach(b=>b.onclick=()=>preview(b.dataset.demo));
document.querySelector('#stopDemo').onclick=()=>{previewTimers.forEach(clearTimeout);previewTimers=[];statusLine.textContent+=' · 정지'};
showStage('O4','mission','MISSION · 블랙 위 임무 화면');
