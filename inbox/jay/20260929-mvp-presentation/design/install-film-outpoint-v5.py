from pathlib import Path
import requests,concurrent.futures,json,re
r=Path(__file__).resolve().parents[1]
files=['film-e5pre-outpoint-comparison-v5.mp4','film-master-v5.mp4','film-ending-v5.mp4','film-outpoint-v5-audit.json']
urls=["https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/b31774b6-f968-4d14-9085-45fdd485a0b6.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/082bd1d8-17ea-4e94-b4d5-48065a95c3b7.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/318ef5b4-9c25-4103-9c5a-656b44587367.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/168b054f-7953-4ee0-82e3-90d1ecaaefa9.json"]
def get(pair):
 f,u=pair;res=requests.get(u,timeout=120);res.raise_for_status();(r/'assets'/f).write_bytes(res.content);return (f,len(res.content))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p: print(list(p.map(get,zip(files,urls))))
q=json.loads((r/'assets/film-outpoint-v5-audit.json').read_text(encoding='utf-8'))
(r/'assets/film-outpoint-v5.jsx').write_text(q['native_script'],encoding='utf-8')
p=r/'output/FOOTHOLD-film-storyboard.html';s=p.read_text(encoding='utf-8')
# Keep the established full master intact; offer new trimmed full/ending as explicit review candidates.
block='<article id="e5pre-outpoint-review"><h3>E5pre → E5 · 끝점 1·2프레임 비교</h3><p>원본 → 1프레임 단축 → 2프레임 단축 순서입니다. 각 7초, 구간 사이 0.5초 블랙. 24fps에서 2프레임은 약 0.083초입니다. POV 마지막만 줄이고 E5의 시작 동작은 유지했습니다. 발소리와 배경음은 같은 믹스를 따라 연결했습니다.</p><video controls preload="metadata" playsinline style="width:100%;background:#000;aspect-ratio:16/9" src="../assets/film-e5pre-outpoint-comparison-v5.mp4"></video><p><a href="../assets/film-master-v5.mp4">2프레임 단축 전체본 후보</a> · <a href="../assets/film-ending-v5.mp4">2프레임 단축 Ending 후보</a></p><p>기본 전체본은 v4를 유지합니다. 위 두 링크는 끝점 수정 검토용 v5입니다. O1 좌우 탐색 보완은 별도 작업이며 이 끝점 수정본에는 아직 반영되지 않았습니다.</p></article>\n'
if 'id="e5pre-outpoint-review"' not in s:s=s.replace('<article id="e5pre-audio-review">',block+'<article id="e5pre-audio-review">')
p.write_text(s,encoding='utf-8')
(r/'assets/film-outpoint-v5-delivery.json').write_text(json.dumps(dict(zip(files,urls)),indent=2),encoding='utf-8')
with (r/'USER-REQUIREMENTS-LOG.md').open('a',encoding='utf-8') as f:f.write('\n\n### U192 · E5pre 끝점과 O1 좌우 탐색 누락\n\n사용자는 E5 오르기 직전 POV 끝점을 1~2프레임 당길 필요를 제안했다. 24fps 원본·1프레임·2프레임 단축 비교를 만든다. 뒤 컷의 오르기 시작과 기존 접지음은 유지한다. 기본 전체본은 v4이며 v5 전체·Ending은 검토 후보로 둔다. 이어 O1에서 주변을 더 두리번거린 뒤 O2 바닥으로 연결하는 수정이 스토리보드에 반영되었는지 재질문했다. 기존 페이지에는 미반영이었다. O1 v4 후보 생성에 왼쪽 기둥·수면, 오른쪽 끊긴 길, 정면 재확인, 바닥 틸트를 명시했다. 거의 암전·작은 빨간 점 두 번·카메라 측 이동광·주변 암부 유지·천장 조명 금지·과도한 HDR 금지를 유지한다. 접수 ID 9af80866-fc3e-4b09-a56e-dcd0e22b5cc9, Seedance 2.5 480p 8초 음향 포함, 견적 24크레딧. 생성 결과 검토 전 완료 또는 승인으로 기록하지 않는다.\n')

