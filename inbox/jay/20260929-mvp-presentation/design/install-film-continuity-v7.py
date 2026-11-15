from pathlib import Path
import requests,concurrent.futures,json,re
r=Path(__file__).resolve().parents[1]
files=['film-master-v7.mp4','film-opening-v7.mp4','film-ending-v7.mp4','film-o1-o2-matched-v5.mp4','film-continuity-v7-audit.json']
urls=["https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/58d3bc1f-d674-4c39-adb9-3d9e804103b4.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/e0631f71-7e2e-4eb7-9b59-8ba32367b0dd.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/5a707c39-51d3-4072-978c-a22cc4f86c09.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/c73a34e3-be6e-4665-958d-c96c2a2b45e3.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/72a2c2dc-17de-469d-9d6d-a745ef644c64.json"]
def get(pair):
 f,u=pair;z=requests.get(u,timeout=120);z.raise_for_status();(r/'assets'/f).write_bytes(z.content);return(f,len(z.content))
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:print(list(pool.map(get,zip(files,urls))))
audit=json.loads((r/'assets/film-continuity-v7-audit.json').read_text(encoding='utf-8'))
(r/'assets/film-continuity-v7.jsx').write_text(audit['native_script'],encoding='utf-8')
(r/'assets/film-continuity-v7-delivery.json').write_text(json.dumps(dict(zip(files,urls)),indent=2),encoding='utf-8')
p=r/'output/FOOTHOLD-film-storyboard.html';s=p.read_text(encoding='utf-8')
def replace_article(id,body):
 global s
 s,n=re.subn(r'<article id="'+id+r'">.*?</article>',lambda m:'<article id="'+id+'">'+body+'</article>',s,flags=re.S)
 assert n==1,(id,n)
def player(file,id=''):
 return '<video '+('id="'+id+'" ' if id else '')+'controls preload="metadata" playsinline style="width:100%;background:#000;aspect-ratio:16/9" src="../assets/'+file+'"></video>'
replace_article('film-master','<h3>전체 연결본 · 80.6초 · 최신 교체본</h3><p>새 O1 좌우 탐색, O1→O2 바닥·조명 연결 보정, E5pre 정지 꼬리 제거와 접지음을 반영했습니다. 끝의 브랜드 클로징도 포함합니다. 기존 배경음 믹스는 유지했으며 별도 영화 음악과 최종 통합 믹싱은 아직 완료 전입니다.</p>'+player('film-master-v7.mp4','masterVideo')+'<p><a href="../assets/film-master-v7.mp4" download>전체 영상 다운로드</a> · <button onclick="const v=document.getElementById(\'masterVideo\');v.currentTime=68.916667;v.play()">브랜드 클로징 재생</button></p>')
replace_article('e5pre-outpoint-review','<h3>E5pre → E5 · 현재 전체본의 연결</h3><p>끝에서 멈춰 보이던 14프레임을 제거했습니다. 아래 버튼은 최신 전체본의 E4 → E5pre → E5 연결을 재생합니다.</p><button onclick="const v=document.getElementById(\'masterVideo\');v.currentTime=40.291667;v.play();v.scrollIntoView({block:\'center\'})">현재 전체본에서 연결 확인</button><details><summary>이전 -2 FRAMES와 정지 꼬리 제거 비교</summary>'+player('film-e5pre-outpoint-comparison-v6.mp4')+'</details>')
replace_article('o1-lookaround-review','<h3>O1 → O2 · 현재 반영된 연결</h3><p>좌우 탐색 뒤 가까운 바닥으로 내려봅니다. O2 시작의 바닥 위치와 빛의 밝기 분포를 O1 끝에 맞추고, 1초 동안 원래 조명 움직임으로 이어지도록 보정했습니다. 아래 영상과 전체본·Opening은 같은 화면과 믹스를 사용합니다.</p>'+player('film-o1-o2-matched-v5.mp4')+'<details><summary>보정 전 연결 참고</summary><a href="../assets/film-o1-o2-lookaround-v4.mp4">조명 보정 전 O1→O2</a></details>')
# Keep historical audio A/B available but collapsed.
s=re.sub(r'(<article id="e5pre-audio-review">)(.*?)(</article>)',lambda m:m[1]+'<details><summary>이전 발소리 추가 전후 비교</summary>'+m[2]+'</details>'+m[3],s,flags=re.S)
# Replace default split exports only, preserve historical references in collapsed comparisons.
s=s.replace('../assets/film-opening-v1.mp4','../assets/film-opening-v7.mp4')
s=s.replace('../assets/film-ending-v4.mp4','../assets/film-ending-v7.mp4')
s=s.replace('Ending · 50.1초 · 브랜드 클로징 포함','Ending · 49.5초 · 최신 교체본')
s=re.sub(r'film-master-review.js\?v=[^"]+','film-master-review.js?v=20261001-continuity7',s)
p.write_text(s,encoding='utf-8')
p=r/'design/film-master-review.js';s=p.read_text(encoding='utf-8')
m=re.search(r'const masterPlan = (.*?);\n',s);plan=json.loads(m[1])
starts={'O1':0,'O2':192,'O3':247,'O3b':295,'O4':361,'O5':445,'O6':553,'O7':625,'E2':751,'E3':871,'E4':967,'E5pre':1087,'E5':1193,'E5b':1307,'E6':1427}
for c in plan['clips']:
 c['at']=starts[c['shot']]/24
 if c['shot']=='O2':c['dur']=55/24
 if c['shot']=='E5pre':c['dur']=(1193-1087)/24
 if c['shot']=='O1':
  c['file']='opening-o1-seedance25-v4.mp4';c['url']='https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20261001_015642_9af80866-fc3e-4b09-a56e-dcd0e22b5cc9.mp4'
plan.update(e7=1535/24,e7dur=119/24,total=80.625,brand_at=1654/24,revision=7,status='User requested replacement with new O1 and trimmed E5pre; lighting seam locally matched')
s=s[:m.start(1)]+json.dumps(plan,ensure_ascii=False,separators=(',',':'))+s[m.end(1):]
s=s.replace("file:'film-master-v4.mp4'","file:'film-master-v7.mp4'").replace("at:masterPlan.e7,dur:5","at:masterPlan.e7,dur:masterPlan.e7dur")
s=re.sub(r"e5preState.textContent=.*?;\n",lambda m:"e5preState.textContent='현재 전체본에 정지 꼬리 제거와 접지음 8회를 반영했습니다. 보행 POV에서 마지막 움직임 다음에 E5 오르기로 이어집니다. 배경음 믹스는 유지했습니다.';\n",s)
s=re.sub(r"productionSummary.innerHTML=.*?;\n",lambda m:"productionSummary.innerHTML='<h3>제작 현황</h3><p>전체 80.625초 · Opening 31.125초 · Ending 49.5초. 새 O1 좌우 탐색과 O1→O2 조명·구도 연결, E5pre 정지 꼬리 제거·접지음이 기본 전체본과 각 분리본에 반영됐습니다. 브랜드 클로징 포함.</p><p>현재 480p 검토본입니다. 기존 배경음 믹스를 유지했으며 별도 영화 음악과 최종 통합 믹싱은 아직 완료 전입니다. HUD 수치와 보행 진동은 연출값입니다.</p>';\n",s)
s=s.replace("file:'film-o1-o2-lookaround-v4.mp4'","file:'film-o1-o2-matched-v5.mp4'")
s=s.replace("title:'O1 → O2 · 좌우 탐색 수정 후보'","title:'O1 → O2 · 현재 반영본'")
s=s.replace("새 O1 8초 + 기존 O2 2.25초. 암전·작은 빨간 점·좌우 시선 탐색·가까운 바닥 연결. 생성 원음 검토용이며 전체본에는 아직 미반영.","전체본에 반영된 연결입니다. 암전·작은 빨간 점·좌우 시선 탐색·가까운 바닥. O2 구도와 조명을 맞췄으며 같은 배경음 믹스를 사용합니다.")
s=s.replace("새 O1 → O2 · 좌우 탐색","현재 O1 → O2 · 조명 연결 보정")
p.write_text(s,encoding='utf-8')
# Bounded asset substitutions in presentation only; do not rebuild or change slide content.
p=r/'output/FOOTHOLD-MVP-cover.html';s=p.read_text(encoding='utf-8')
s=re.sub(r'film-opening-v\d+\.mp4','film-opening-v7.mp4',s);s=re.sub(r'film-ending-v\d+\.mp4','film-ending-v7.mp4',s);p.write_text(s,encoding='utf-8')
p=r/'build_presentation.py';s=p.read_text(encoding='utf-8').replace("clip('film-opening-v1.mp4'","clip('film-opening-v7.mp4'")
s=s.replace("['film-ending-v3.mp4',","['film-ending-v7.mp4','film-ending-v3.mp4',")
p.write_text(s,encoding='utf-8')
with (r/'USER-REQUIREMENTS-LOG.md').open('a',encoding='utf-8') as f:f.write('\n\n### U194 · 새 영상으로 기본 재생본 교체 및 O1→O2 조명 일치\n\n사용자는 새 O1과 정지 꼬리를 제거한 POV를 새 버전으로 모두 교체하라고 지시했다. O1 마지막 바닥과 O2 시작 바닥의 조명이 달라 튀는 문제도 지적했다. O2 시작의 바닥 위치를 약 5픽셀 내려 맞추고 저주파 조명 밝기 분포를 O1 마지막 프레임에 맞춘 뒤 1초 동안 보정을 완화했다. 전체본 v7·Opening v7·Ending v7·컷별 재생·발표 HTML 영상 링크를 함께 교체한다. 기존 사운드 믹스와 접지음은 유지한다. 이전 비교본은 참고용으로 접어두며 기본본으로 사용하지 않는다. 신규 생성 없이 기존 소스의 연결을 보정한 작업이다.\n')
print('Default storyboard, shot links and presentation video links now reference v7')

