// Explicit review state. A completed generation is not an approved shot.
Object.assign(videoAssets,{
 o5v3:{title:'O5 · 센서 POV 수정 v3',file:'opening-o5-seedance25-v3.mp4',poster:'hud-observe-sunburst-v2.png',copy:'5초 · Seedance 2.5 · 480p · 생성 음향. 0.05~4.8초 10개 프레임에서 사람·로봇 몸체·발이 없는 것을 확인했습니다. 수치 변화는 있으나 명령한 감속 순서를 정확히 따르지 않아 UI 값 검증은 미완료입니다. 최종 승인 전 후보입니다.'},
 o1review:{title:'O1 v2 · 조명 방향 불일치',file:'opening-o1-seedance25-v2.mp4',poster:'opening-o1-sunburst-v2.png',copy:'검토용. 국소 조명은 보이지만 광원이 카메라 쪽이 아닌 왼쪽 기둥 뒤에 있는 것처럼 보입니다. 시작도 완전 블랙이 아닙니다. 요청된 O1로 승인하지 않습니다.'},
 o1bridge:{title:'O1→O2 연결 후보 · 아래보기',file:'opening-o1b-seedance25-v1.mp4',poster:'opening-o1-sunburst-v2.png',copy:'약 2초부터 바닥으로 내려가고 약 3.5초부터 O2 근접 바닥 구도에 도달합니다. 연결 움직임은 생겼으나 O1의 잘못된 측면 광원을 계승하므로 최종 연결 승인 전입니다.'}
});
Object.assign(videoLabels,{o5v3:'수정 영상 v3 · 몸체 없는 POV',o1review:'O1 v2 · 조명 오류 확인',o1bridge:'O1→O2 · 연결 후보 확인'});
for(const [id,keys] of [['O5',['o5v3']],['O1',['o1review','o1bridge']]]){
 const n=all.findIndex(x=>x.d[0]===id);
 shotVideos[id]=[...keys,...(shotVideos[id]||[]).filter(k=>!keys.includes(k))];
 const bar=document.createElement('div');bar.className='extra';bar.dataset.latestVideoReview=id;
 bar.innerHTML=keys.map(k=>`<button data-video="${k}" data-shot-index="${n}">${videoLabels[k]}</button>`).join('');
 all[n].fig.append(bar);
}
const e5preState=document.createElement('p');e5preState.className='caption-note';e5preState.id='e5pre-video-review-status';
e5preState.textContent='Kling 후보 제외: 로봇 몸체·다리가 등장해 POV 조건 위반. 앞 컷 E4의 실제 음원을 참고로 넣은 Seedance 수정본 생성 중. 기존 후보를 연결 편집에 사용하지 않습니다.';
all.find(x=>x.d[0]==='E5pre').fig.append(e5preState);
const producedShots=[
 ['O2','opening-o2-seedance25-v1.mp4','opening-o2-sunburst-v1.png','가까운 바닥 탐색'],
 ['O3','opening-o3-seedance25-v1.mp4','opening-o3-sunburst-v1.png','부서진 가장자리'],
 ['O3b','opening-o3b-seedance25-v1.mp4','opening-o3b-sunburst-v1.png','깊은 틈'],
 ['O4','opening-o4-seedance25-v1.mp4','hud-mission-sunburst-v2.png','블랙에서 임무 수신'],
 ['O6','opening-o6-seedance25-v1.mp4','hud-scan-sunburst-v2.png','근거리 표면 스캔'],
 ['E3','ending-e3-seedance25-v1.mp4','ending-e3-sunburst-v3.png','후면 추적'],
 ['E4','ending-e4-seedance25-v1.mp4','ending-e4-sunburst-v3.png','측면 틈 통과'],
 ['E5','ending-e5-seedance25-v1.mp4','ending-e5-sunburst-v1.png','뒤에서 턱 오르기'],
 ['E6','ending-e6-seedance25-v1.mp4','hud-record-sunburst-v2.png','CV 관측·촬영']
];
for(const [id,file,poster,title] of producedShots){
 const key=id.toLowerCase()+'review',n=all.findIndex(x=>x.d[0]===id),entry=all[n];
 videoAssets[key]={title:`${id} · ${title}`,file,poster,copy:'Seedance 2.5 · 5초 · 480p · 생성 음향 포함. 영상 초안 생성 완료, 사용자 영상 승인 및 앞뒤 연결 검토 전입니다.'};
 videoLabels[key]='영상 초안 재생';shotVideos[id]=[key];
 const bar=document.createElement('div');bar.className='extra';bar.innerHTML=mediaButtons(id,n);entry.fig.append(bar);
 entry.d[2]=videoAssets[key].copy;
 entry.fig.querySelector('figcaption .caption-note').textContent=entry.d[2];
}
const productionSummary=document.createElement('section');productionSummary.id='film-production-status';
productionSummary.innerHTML=`<h3>컷 제작 현황 · 생성 완료와 승인 구분</h3><table style="width:100%;border-collapse:collapse;text-align:left"><thead><tr><th>구간</th><th>현재 상태</th></tr></thead><tbody>
<tr><td>O7 · E2</td><td>기존 발 영상·선호 보행 영상. 두 컷 연결 편집 v2 있음.</td></tr>
<tr><td>O2 · O3 · O3b · O4 · O6</td><td>영상 초안 생성 완료. 아래 컷별 재생 버튼 연결. 사용자 영상 승인 전.</td></tr>
<tr><td>E3 · E4 · E5 · E5b · E6</td><td>영상 초안 생성 완료. 아래 컷별 재생 버튼 연결. 사용자 영상 승인 전.</td></tr>
<tr><td>O1 · O1→O2</td><td>원경→바닥 연결 후보 있음. 카메라 방향 광원·완전 암전 시작은 미해결.</td></tr>
<tr><td>O5</td><td>v3 몸체 없는 POV 후보 생성. HUD 감속 수치 정확성 미해결.</td></tr>
<tr><td>E5pre</td><td id="e5pre-summary-status">Kling 후보 제외. E4 음원 참조 Seedance 수정본 검토 중.</td></tr>
<tr><td>E7</td><td>생성 요청 실패. 전송→적색 완료→암전 영상 미완료.</td></tr>
<tr><td>전체 · Opening · Ending</td><td>전체 연결 편집 미완료. 상단 세 영상은 아직 없음.</td></tr>
<tr><td>통합 사운드 · 1080p</td><td>미완료. 개별 컷의 생성 원음은 최종 믹스가 아님.</td></tr>
</tbody></table>`;
document.querySelector('#film-deliverables').append(productionSummary);
videoAssets.e5prepov={title:'E5pre · 몸체 없는 보행 POV 수정 v2',file:'ending-e5pre-seedance25-v2.mp4',poster:'ending-e5pre-pov-start-v1.png',copy:'Seedance 2.5 · 5초 · 480p · 생성 음향. 앞 컷 E4 원음 참조를 전달했습니다. 10개 표본 프레임에서 몸체·다리 없이 턱으로 접근하는 것을 확인했습니다. 스캔은 짧은 선 형태로 나타납니다. 앞뒤 컷과 발소리·박자를 맞춘 연결 편집은 아직 미완료입니다.'};
videoLabels.e5prepov='수정 영상 v2 · 보행 POV';shotVideos.E5pre=['e5prepov'];
const povIndex=all.findIndex(x=>x.d[0]==='E5pre');
all[povIndex].fig.insertAdjacentHTML('beforeend',`<div class="extra">${mediaButtons('E5pre',povIndex)}</div>`);
e5preState.textContent='Kling 후보 제외. E4 음원 참조 Seedance 수정본 생성 완료. 몸체 없는 보행 POV 후보이며, 스캔 표현과 발소리·앞뒤 연결은 검토 전입니다.';
document.querySelector('#e5pre-summary-status').textContent='Seedance 수정본 생성. 표본에서 몸체 없음. 스캔 표현·발소리·앞뒤 연결 검토 전.';
