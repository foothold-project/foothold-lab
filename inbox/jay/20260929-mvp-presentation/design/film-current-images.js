/* Current approved image references. AI HUD pixels are not duplicated by SVG. */
const currentFilmImages={
 O1:['opening-o1-sunburst-v2','빛이 닿은 곳만 보인다','조명 참고 후보. 영상은 완전 블랙에서 먼 빨간 점이 두 번 깜빡인 뒤 이동광으로 바닥과 기둥을 훑습니다. 천장 조명 점등 없음.'],
 O4:['hud-mission-sunburst-v2','블랙에서 임무가 들어온다','대비·재질 수정 v2 사용자 승인. 블랙 위 임무 수신 후 관측 화면으로 연결합니다.'],
 O5:['hud-observe-sunburst-v2','넓은 시야에서 몸과 지형을 본다','대비·재질 수정 v2 사용자 승인. 자세와 명령·반응값은 연출용 예시입니다. 영상에서는 카메라·보행과 함께 반응하도록 제작합니다.'],
 O6:['hud-scan-sunburst-v2','발앞의 높이만 살핀다','대비·재질 수정 v2 사용자 승인. 근거리 scan만 표시합니다. 영상에서 표면 부착과 틈의 빈 공간을 유지해야 합니다.'],
 E5b:['ending-e5b-seated-region-v1','정면에서 멈추고 앉는다','서 있는 시작·앉은 끝 이미지 모두 사용자 승인. 원래 구도와 뒤 중앙 경로를 유지한 자세 한 쌍입니다. 아래 버튼으로 비교합니다.'],
 E6:['hud-record-sunburst-v2','대상을 인식하고 촬영한다','대비·재질 수정 v2 사용자 승인. 설비와 경광등에 맞춘 CV 박스, REC·촬영 시간. 실제 검출 로그가 아닌 콘셉트입니다.'],
 E7:['hud-transfer-sunburst-v2','전송하고 수신 완료를 확인한다','전송·붉은 MISSION COMPLETE 이미지 승인. 아래 버튼으로 두 상태를 비교합니다. 영상에서는 진행률 상승 후 수신 확인, 지지직 블랙 순서입니다.'],
 T1:['terrain-question-bright-v1','어떤 로봇으로 이 험지를 건너겠습니까?','사용자 승인한 밝은 원경. 오프닝 뒤 발표 질문용으로 사용하며 영상의 암전 시작과 구분합니다.']
};
const bakedHudShots=new Set(['O4','O5','O6','E6','E7']);
function singleImageStyle(name){return `background-image:url('../assets/${name}.png');background-size:cover;background-position:center`}
for(const [id,[file,title,copy]] of Object.entries(currentFilmImages)){
 const entry=all.find(x=>x.d[0]===id); if(!entry)continue;
 entry.d[1]=title;entry.d[2]=copy;
 const frame=entry.fig.querySelector('.frame');
 frame.querySelector('.photo').setAttribute('style',singleImageStyle(file));
 entry.fig.dataset.currentPhoto=singleImageStyle(file);
 if(bakedHudShots.has(id)){frame.dataset.baked='true';frame.querySelectorAll('.hud').forEach(x=>x.remove());}
 entry.fig.querySelector('figcaption').innerHTML=`<strong>${id}</strong>${title}<div class="caption-note">${copy}</div>`;
 if(id==='O4')frame.insertAdjacentHTML('afterend',`<div class="extra image-review-actions">${reviewButtons(all.indexOf(entry))}</div>`);
}
const originalPhotoStyleBeforeCurrent=originalPhotoStyle;
originalPhotoStyle=function(id){
 if(['O4','E6','E7'].includes(id))return `background-image:url('FOOTHOLD-film-hud-v4-${{O4:'mission',E6:'record',E7:'transfer'}[id]}.png');background-size:cover;background-position:center`;
 if(id==='T1')return "background-image:url('../assets/opening-storyboard-v6.png');background-size:200% 307.2%;background-position:0% 0%";
 return originalPhotoStyleBeforeCurrent(id);
};
function setTransmissionImage(frame,done){
 frame.querySelectorAll('.hud').forEach(x=>x.remove());
 frame.dataset.baked='true';
 frame.querySelector('.photo').setAttribute('style',singleImageStyle(done?'hud-complete-sunburst-v2':'hud-transfer-sunburst-v2'));
}
document.querySelector('#transferToggle').onclick=e=>{
 completed=!completed;
 const entry=all.find(x=>x.d[0]==='E7');setTransmissionImage(entry.fig.querySelector('.frame'),completed);
 entry.fig.dataset.currentPhoto=entry.fig.querySelector('.photo').getAttribute('style');
 e.target.textContent=completed?'전송 중 상태 보기':'수신 완료 상태 보기';if(viewer.open)show(current);
};
const e7entry=all.find(x=>x.d[0]==='E7');
e7entry.fig.querySelector('.image-review-actions').insertAdjacentHTML('beforeend','<button data-current-complete>붉은 완료 화면</button>');
document.querySelector('[data-current-complete]').onclick=()=>document.querySelector('#transferToggle').click();
document.querySelector('[data-e5b-standing]').onclick=()=>{
 const e=all.find(x=>x.d[0]==='E5b');
 e.fig.querySelector('.photo').setAttribute('style',singleImageStyle('ending-e5b-standing-region-v1'));
};
document.querySelector('[data-e5b-standing]').textContent='승인한 서 있는 시작';
const approachEntry=all.find(x=>x.d[0]==='E5pre');
approachEntry.d[1]='보행 POV로 턱에 접근 · 새 이미지 제작 전';
approachEntry.d[2]='확정 연출: 틈을 건넌 뒤 보행 POV로 접근, 턱이 가까워지면 표면 스캔, 턱 바로 앞에서 컷, E5 후면 오르기로 연결. 현재 그림은 보존한 이전 바닥 카메라안입니다.';
approachEntry.fig.querySelector('figcaption').innerHTML=`<strong>E5pre</strong>${approachEntry.d[1]}<div class="caption-note">${approachEntry.d[2]}</div>`;
// Generated HUD is integrated into image pixels; the old SVG-only switch cannot hide it.
document.querySelector('#toggle').textContent='HUD 통합 이미지';
document.querySelector('#toggle').disabled=true;
document.querySelector('#toggle').title='원화 비교 버튼으로 이전 화면을 확인할 수 있습니다.';
document.body.classList.remove('no-ui');
showStage('O4','still','사용자 승인한 임무 수신 이미지 · 정지 시안');
Object.assign(videoAssets,{
 o5:{title:'O5 · 관측 HUD 영상 v1',file:'opening-o5-seedance25-v1.mp4',poster:'hud-observe-sunburst-v2.png',copy:'Seedance 2.5 · 5초 · 480p · 생성 음향 포함. 승인된 HUD v2로 제작. 샘플 프레임에서 감속 수치가 변하지 않아 수정 대상입니다. 영상 승인 전입니다.'},
 e5b:{title:'E5b · 앉는 동작 영상 v1',file:'ending-e5b-seedance25-v1.mp4',poster:'ending-e5b-standing-region-v1.png',copy:'Seedance 2.5 · 5초 · 480p · 생성 음향 포함. 승인된 서 있음·앉음 이미지를 시작·끝 프레임으로 사용했습니다. 영상 승인 전입니다.'}
});
Object.assign(videoLabels,{o5:'영상 재생 · 관측 HUD',e5b:'영상 재생 · 앉는 동작'});
for(const [id,key] of [['O5','o5'],['E5b','e5b']]){
 shotVideos[id]=[key];const index=all.findIndex(x=>x.d[0]===id);
 all[index].fig.insertAdjacentHTML('beforeend',`<div class="extra">${mediaButtons(id,index)}</div>`);
}
approachEntry.d[1]='보행 POV로 턱에 접근 · 시작 이미지 후보';
approachEntry.d[2]='새 POV 시작 후보입니다. 보행하며 턱에 접근하고 표면 스캔 후 턱 바로 앞에서 컷, E5 후면 오르기로 연결합니다. 시작 이미지 승인 전이며 스캔 끝 프레임은 남아 있습니다. 원화 버튼으로 이전 바닥 카메라안을 보존합니다.';
approachEntry.fig.querySelector('.photo').setAttribute('style',singleImageStyle('ending-e5pre-pov-start-v1'));
approachEntry.fig.dataset.currentPhoto=singleImageStyle('ending-e5pre-pov-start-v1');
approachEntry.fig.querySelector('figcaption').innerHTML=`<strong>E5pre</strong>${approachEntry.d[1]}<div class="caption-note">${approachEntry.d[2]}</div>`;
