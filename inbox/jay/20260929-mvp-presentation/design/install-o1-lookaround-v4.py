from pathlib import Path
import requests,json
r=Path(__file__).resolve().parents[1]
url='https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/546a06fb-2cc8-4179-8434-f5df3ee46c15.mp4'
res=requests.get(url,timeout=120);res.raise_for_status();(r/'assets/film-o1-o2-lookaround-v4.mp4').write_bytes(res.content)
p=r/'output/FOOTHOLD-film-storyboard.html';s=p.read_text(encoding='utf-8')
block='<article id="o1-lookaround-review"><h3>O1 → O2 · 좌우 탐색 후 바닥 연결 후보</h3><p>새 O1 8초와 기존 O2 2.25초를 붙였습니다. 암전과 작은 빨간 점으로 시작해 왼쪽 기둥·수면, 오른쪽 길을 살핀 뒤 가까운 바닥으로 내려봅니다. 빛이 닿는 부분만 드러나는 생성 결과입니다. O1은 아직 전체본에 교체하지 않았습니다. 이 검토본은 컷의 생성 원음이며 최종 통합 믹스가 아닙니다.</p><video controls preload="metadata" playsinline style="width:100%;background:#000;aspect-ratio:16/9" src="../assets/film-o1-o2-lookaround-v4.mp4"></video><p><a href="../assets/opening-o1-seedance25-v4.mp4">새 O1 단독 원본</a> · <a href="../assets/opening-o1-seedance25-v3.mp4">이전 O1 원본</a></p></article>\n'
if 'id="o1-lookaround-review"' not in s:s=s.replace('<article id="e5pre-audio-review">',block+'<article id="e5pre-audio-review">')
s=s.replace('film-master-review.js?v=20261001-footsteps4','film-master-review.js?v=20261001-lookaround4')
p.write_text(s,encoding='utf-8')
p=r/'design/film-master-review.js';s=p.read_text(encoding='utf-8')
extra="""\n// New O1 candidate kept separate from established full master until review.
videoAssets.o1lookaround4={title:'O1 → O2 · 좌우 탐색 수정 후보',file:'film-o1-o2-lookaround-v4.mp4',poster:'',copy:'새 O1 8초 + 기존 O2 2.25초. 암전·작은 빨간 점·좌우 시선 탐색·가까운 바닥 연결. 생성 원음 검토용이며 전체본에는 아직 미반영.'};
videoLabels.o1lookaround4='새 O1 → O2 · 좌우 탐색';
{const n=all.findIndex(x=>x.d[0]==='O1');shotVideos.O1=['o1lookaround4',...(shotVideos.O1||[])];all[n].fig.insertAdjacentHTML('beforeend',\x60<div class="extra"><button data-video="o1lookaround4" data-shot-index="\x24{n}">새 O1 → O2 · 좌우 탐색</button></div>\x60);}
"""
if 'videoAssets.o1lookaround4=' not in s:s+=extra
p.write_text(s,encoding='utf-8')
(r/'assets/film-o1-o2-lookaround-v4.delivery.json').write_text(json.dumps({'url':url,'source_job':'9af80866-fc3e-4b09-a56e-dcd0e22b5cc9','cost_credits':24,'status':'Review candidate, not integrated into master'},indent=2),encoding='utf-8')
print('O1 candidate added to top review and O1 card')

