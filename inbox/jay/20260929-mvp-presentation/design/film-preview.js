const stage=document.querySelector('.stage'), statusLine=document.querySelector('.motion-status');
let previewTimers=[];
function stopPreview(){previewTimers.forEach(clearTimeout);previewTimers=[];stage.dataset.phase='still'}
function showStage(id,phase,label){const entry=all.find(x=>x.d[0]===id);const f=entry.fig.querySelector('.frame').cloneNode(true);f.removeAttribute('role');f.removeAttribute('tabindex');if(id==='E7'){f.querySelector('.hud')?.remove();f.insertAdjacentHTML('beforeend',hud('transfer'))}stage.querySelector('.stage-body').replaceChildren(f);stage.dataset.phase=phase;statusLine.textContent=label}
function schedule(steps,duration){stopPreview();document.querySelector('.demo-track i').style.width='0%';steps.forEach(([ms,fn])=>previewTimers.push(setTimeout(()=>{fn();document.querySelector('.demo-track i').style.width=(ms/duration*100)+'%'},ms)));previewTimers.push(setTimeout(()=>document.querySelector('.demo-track i').style.width='100%',duration))}
function preview(mode){
 if(mode==='intro')schedule([[0,()=>showStage('O1','black','완전한 블랙에서 시작')],[600,()=>showStage('O1','torch','화면 밖 이동광이 벽과 통로를 훑으며 공간을 드러냄')],[5700,()=>showStage('O2','still','수직에 가까운 시점으로 바닥 질감 관찰')],[7200,()=>showStage('O3','still','바닥의 가장자리를 발견')],[8400,()=>showStage('O3b','still','복원한 깊은 틈 컷')]],10000);
 if(mode==='mission')schedule([[0,()=>showStage('O3b','still','틈 발견 뒤 블랙 전환')],[900,()=>showStage('O4','black','블랙 · 신호음 진입 지점')],[1500,()=>showStage('O4','boot','신호 수신 · 화면 활성화')],[1800,()=>showStage('O4','flicker','MISSION 활성화')],[2150,()=>{stage.dataset.phase='mission';statusLine.textContent='임무 문구를 읽는 구간'}],[4500,()=>{stage.dataset.phase='blend';statusLine.textContent='배경 시야가 서서히 돌아옴'}],[5500,()=>showStage('O5','still','원경에서 몸 상태와 지형 관측')]],6600);
 if(mode==='observe'){stopPreview();showStage('O5','still','원경 HUD · 로그 미연결 수치는 비워둠')}
 if(mode==='height'){stopPreview();showStage('O6','still','근거리 height scan만 · 주변 HUD 없음')}
 if(mode==='foot'){stopPreview();showStage('O7','still','복원한 발 접촉 구도 · 이후 연속 발걸음으로 연결')}
 if(mode==='reveal')schedule([[0,()=>showStage('E2','mood-start','고정 역광 · 어둠 속 실루엣')],[1100,()=>{stage.dataset.phase='mood-reveal';statusLine.textContent='조명 위치는 고정 · 은색 외장과 얼굴이 서서히 드러남'}]],4600);
 if(mode==='approach')schedule([[0,()=>showStage('E5pre','still','바닥 고정 카메라 · Go2가 위를 통과하는 동작은 영상 제작 문안에 기록')],[2000,()=>showStage('E5','still','뒤에서 턱을 오르는 자세')],[4200,()=>showStage('E5b','still','조금 높은 정면 원경 · 앉아 목표 응시')],[6500,()=>showStage('E6','still','목표 설비 POV · 인식과 촬영')]],7800);
 if(mode==='sit'){stopPreview();showStage('E5b','still','정면 원경 · 앞다리 지지 · 뒷다리 접고 응시')}
 if(mode==='ending')schedule([[0,()=>{completed=false;showStage('E7','still','현장 영상 전송 중')}],[1800,()=>{completed=true;showStage('E7','still','수신 확인 · MISSION COMPLETE')}],[4000,()=>{stage.dataset.phase='flicker';statusLine.textContent='신호 끊김 · 화면 종료'}],[4350,()=>{stage.dataset.phase='shutdown'}],[4550,()=>{stage.dataset.phase='off';statusLine.textContent='영상 종료 · 블랙 유지. 다음 슬라이드로 이동'}]],5000);
 if(mode==='complete'){stopPreview();completed=true;showStage('E7','still','100% · 적색 MISSION COMPLETE · 수신 확인')}
 if(mode==='record'){stopPreview();showStage('E6','still','CV 인식 박스·특징점·추적 표시 · 연출 예시')}
 if(mode==='transfer'){stopPreview();completed=false;showStage('E7','still','전송 HUD · 연출 예시')}
 if(mode==='qa'){stopPreview();showStage('Q1','still','발표용 Pretendard · 가운데 Q&A만 표시')}
}
document.querySelectorAll('[data-demo]').forEach(b=>b.onclick=()=>preview(b.dataset.demo));
document.querySelector('#stopDemo').onclick=()=>{previewTimers.forEach(clearTimeout);previewTimers=[];statusLine.textContent+=' · 정지'};
showStage('O4','mission','MISSION · 블랙 위 임무 화면');
