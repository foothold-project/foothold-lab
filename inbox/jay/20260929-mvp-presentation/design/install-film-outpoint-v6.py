from pathlib import Path
import requests,concurrent.futures,json,re
r=Path(__file__).resolve().parents[1]
files=['film-e5pre-outpoint-comparison-v6.mp4','film-master-v6.mp4','film-ending-v6.mp4','film-outpoint-v6-audit.json']
urls=["https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/697ece74-3d36-48db-9b0d-c1ba1d4fd3d4.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/fb5f4e92-e7ff-4ddf-91a2-67ecb8ba2e1b.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/81c27202-e0a6-451d-a79f-bf7dd5bfa877.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/09971c34-3f61-4658-ac0d-23d845e1f8ed.json"]
def get(pair):
 f,u=pair;res=requests.get(u,timeout=120);res.raise_for_status();(r/'assets'/f).write_bytes(res.content);return(f,len(res.content))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:print(list(p.map(get,zip(files,urls))))
p=r/'output/FOOTHOLD-film-storyboard.html';s=p.read_text(encoding='utf-8')
block='<article id="e5pre-outpoint-review"><h3>E5pre → E5 · 정지 꼬리 제거</h3><p>첫 구간은 문제가 남은 POV OUT -2 FRAMES, 두 번째는 정지 꼬리를 제거한 수정본입니다. 각 7초, 사이 0.5초 블랙. v4 원본 끝에서 거의 멈춘 14프레임(약 0.58초)을 제거해 마지막 움직임 다음에 바로 E5 오르기를 붙였습니다. 마지막 접지음은 남겼습니다.</p><video controls preload="metadata" playsinline style="width:100%;background:#000;aspect-ratio:16/9" src="../assets/film-e5pre-outpoint-comparison-v6.mp4"></video><p><a href="../assets/film-master-v6.mp4">정지 꼬리 제거 전체본 후보 v6</a> · <a href="../assets/film-ending-v6.mp4">Ending 후보 v6</a></p><p>기본 전체본은 v4를 유지하며 v6는 검토 후보입니다. 이전 -2 FRAMES(v5)는 정지 구간이 남아 채택하지 않습니다. O1 좌우 탐색은 아래 별도 검토본입니다.</p></article>'
s=re.sub(r'<article id="e5pre-outpoint-review">.*?</article>',lambda m:block,s,flags=re.S)
p.write_text(s,encoding='utf-8')
(r/'assets/film-outpoint-v6-delivery.json').write_text(json.dumps(dict(zip(files,urls)),indent=2),encoding='utf-8')
with (r/'USER-REQUIREMENTS-LOG.md').open('a',encoding='utf-8') as f:f.write('\n\n### U193 · POV OUT -2 FRAMES의 정지 꼬리\n\n사용자는 -2 FRAMES 기준으로 마지막 동일 프레임이 남아 오류처럼 보인다고 지적했다. v5는 채택하지 않는다. v4를 프레임별 비교하니 1193~1206번이 거의 정지한 구간이었고, 단순 2프레임 단축으로 제거되지 않았다. v6는 해당 14프레임을 제거하여 마지막 움직임 프레임 1192 다음에 기존 E5 첫 프레임 1207을 붙인다. 마지막 접지음은 제거 구간 이전에 끝난다. 검토본을 같은 스토리보드에 올리고 기본 전체본은 승인 전까지 유지한다.\n')

