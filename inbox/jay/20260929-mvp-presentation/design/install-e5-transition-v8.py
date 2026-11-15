from pathlib import Path
import requests,concurrent.futures,json,re
r=Path(__file__).resolve().parents[1]
files=['film-master-v8.mp4','film-ending-v8.mp4','film-e5-transition-v8.mp4','film-e5-transition-comparison-v8.mp4','film-e5-transition-v8-audit.json']
urls=["https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/5204e571-3b0d-49cc-af56-acac495ef28a.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/b4923acf-8689-4f5a-9764-92905465c290.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/f7930eb1-5b67-4ce4-96fc-167bb74fa3d3.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/05292ec9-0ac4-4b26-a4d7-471a64d104aa.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/5df8e30b-8367-415e-a72e-ba3165c9ddc6.json"]
def get(pair):
 f,u=pair;z=requests.get(u,timeout=120);z.raise_for_status();(r/'assets'/f).write_bytes(z.content);return(f,len(z.content))
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:print(list(pool.map(get,zip(files,urls))))
audit=json.loads((r/'assets/film-e5-transition-v8-audit.json').read_text(encoding='utf-8'))
assert audit['audio_bitstream_preserved']
(r/'assets/film-e5-transition-v8.jsx').write_text(audit['native_comparison_script'],encoding='utf-8')
(r/'assets/film-e5-transition-v8-delivery.json').write_text(json.dumps(dict(zip(files,urls)),indent=2),encoding='utf-8')
p=r/'output/FOOTHOLD-film-storyboard.html';s=p.read_text(encoding='utf-8')
s=s.replace('film-master-v7.mp4','film-master-v8.mp4').replace('film-ending-v7.mp4','film-ending-v8.mp4')
s=s.replace('E5pre 정지 꼬리 제거와 접지음을 반영했습니다.','E5pre 정지 꼬리 제거·접지음과 POV→E5 화면 구도 연결 보정을 반영했습니다.')
block='<article id="e5pre-outpoint-review"><h3>POV → 오르기 · 현재 반영된 연결</h3><p>정지 꼬리를 제거한 상태에서 E5 시작의 목표 설비 위치를 POV 끝에 가깝게 맞췄습니다. 처음 약 0.8초 동안 원래 후면 구도로 부드럽게 풀리며, 오르는 동작과 접지음 타이밍은 유지합니다. 아래 6초 영상은 현재 전체본의 같은 구간입니다.</p><video controls preload="metadata" playsinline style="width:100%;background:#000;aspect-ratio:16/9" src="../assets/film-e5-transition-v8.mp4"></video><p><button onclick="const v=document.getElementById(\'masterVideo\');v.currentTime=47.5;v.play();v.scrollIntoView({block:\'center\'})">전체본에서 같은 연결 확인</button></p><details><summary>화면 구도 보정 전후 비교</summary><video controls preload="metadata" playsinline style="width:100%;background:#000;aspect-ratio:16/9" src="../assets/film-e5-transition-comparison-v8.mp4"></video></details></article>'
s,n=re.subn(r'<article id="e5pre-outpoint-review">.*?</article>',lambda m:block,s,flags=re.S);assert n==1
s=re.sub(r'film-master-review.js\?v=[^"]+','film-master-review.js?v=20261001-transition8',s)
p.write_text(s,encoding='utf-8')
p=r/'design/film-master-review.js';s=p.read_text(encoding='utf-8').replace("file:'film-master-v7.mp4'","file:'film-master-v8.mp4'")
s=s.replace('"revision":7','"revision":8')
s=s.replace('현재 전체본에 정지 꼬리 제거와 접지음 8회를 반영했습니다. 보행 POV에서 마지막 움직임 다음에 E5 오르기로 이어집니다. 배경음 믹스는 유지했습니다.','현재 전체본에 정지 꼬리 제거·접지음 8회와 POV→E5 구도 연결 보정을 반영했습니다. E5 첫 20프레임을 당겨 목표 설비 위치를 맞춘 뒤 원래 후면 구도로 풀었습니다. 오르는 동작과 사운드 타이밍은 유지했습니다.')
s=s.replace('E5pre 정지 꼬리 제거·접지음이 기본 전체본과 각 분리본에 반영됐습니다.','E5pre 정지 꼬리 제거·접지음·POV→E5 구도 연결이 기본 전체본과 Ending에 반영됐습니다.')
p.write_text(s,encoding='utf-8')
p=r/'output/FOOTHOLD-MVP-cover.html';s=p.read_text(encoding='utf-8').replace('film-ending-v7.mp4','film-ending-v8.mp4');p.write_text(s,encoding='utf-8')
p=r/'build_presentation.py';s=p.read_text(encoding='utf-8').replace("['film-ending-v7.mp4',","['film-ending-v8.mp4','film-ending-v7.mp4',");p.write_text(s,encoding='utf-8')
with (r/'USER-REQUIREMENTS-LOG.md').open('a',encoding='utf-8') as f:f.write('\n\n### U195 · POV에서 오르기로 바뀌는 화면 튐 보정\n\n사용자는 현재 기본본의 POV→다음 오르기 컷이 튀는 부분을 잡아 업데이트하라고 지시했다. 정지 꼬리 제거만으로 남은 시점 차이를 보완한다. E5 첫 20프레임(약 0.83초)에서 시작 화면을 1.18배로 당기고 목표 설비의 화면 위치를 POV 끝에 가깝게 맞춘 뒤 원래 구도로 부드럽게 풀었다. 컷 길이·동작·시간·사운드는 변경하지 않는다. v7과 v8의 전체 음향 스트림 해시가 동일한지 검사한다. 기본 전체본·Ending·컷별 버튼·발표 HTML Ending을 v8로 교체하며 보정 전후 영상은 같은 스토리보드에 둔다. Opening v7은 그대로 유지한다.\n')

