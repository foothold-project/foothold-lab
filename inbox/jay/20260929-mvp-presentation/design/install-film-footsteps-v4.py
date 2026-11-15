from pathlib import Path
import requests,concurrent.futures,zipfile,json,re
r=Path(__file__).resolve().parents[1]
files=["film-master-v4.mp4","film-ending-v4.mp4","film-e5pre-footsteps-comparison-v4.mp4","film-footsteps-v4-work.zip"]
urls=["https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/889bf76b-9aee-4280-9cf2-d12694b7d0e7.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/0a4be51b-0b34-47d0-a314-7ac21fa8d5dc.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/cc74a85e-e00a-4acc-803b-910580c78ece.mp4","https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/135ce82c-b4c7-4b07-9ca5-ac89bc0d645a.zip"]
def get(pair):
 name,url=pair
 resp=requests.get(url,timeout=120);resp.raise_for_status();(r/'assets'/name).write_bytes(resp.content)
 return (name,len(resp.content))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: print(list(pool.map(get,zip(files,urls))))
with zipfile.ZipFile(r/'assets/film-footsteps-v4-work.zip') as z:
 for source,target in [('qa.json','assets/film-footsteps-v4.audit.json'),('events.json','assets/film-footsteps-v4.events.json'),('contact-edit.jsx','assets/film-footsteps-v4.jsx'),('comparison-edit.jsx','assets/film-e5pre-footsteps-comparison-v4.jsx')]:
  (r/target).write_bytes(z.read(source))
p=r/'output/FOOTHOLD-film-storyboard.html';s=p.read_text(encoding='utf-8')
s=s.replace('film-master-v3.mp4','film-master-v4.mp4').replace('film-ending-v3.mp4','film-ending-v4.mp4').replace('film-e5pre-audio-comparison-v3.mp4','film-e5pre-footsteps-comparison-v4.mp4')
s=s.replace('전체 연결본 · 81.2초 · E5pre 연결 음향 보정','전체 연결본 · 81.2초 · E5pre 발소리 추가')
s=s.replace('기존 E5pre 화면을 유지하고 원음 억제·반복 발소리 덧입힘을 수정했습니다. 앞뒤 공간음 연결을 보정했으며 영상 프레임은 이전 전체본과 동일합니다.','승인받은 E5pre 화면과 배경음을 유지하고 앞뒤 E4·E5에서 가져온 접지음 8회를 보행 박자에 맞춰 추가했습니다. 영상 프레임은 이전 전체본과 동일합니다.')
s=s.replace('E5pre · 기존 화면 유지, 앞뒤 연결 음향 보정','E5pre · 발소리 추가 전후 비교')
s=s.replace('새 발소리 반복을 빼고 원본 공간음을 회복했습니다.','BEFORE는 승인받은 배경음 보정본, AFTER는 같은 배경음에 접지음 8회를 추가한 본입니다. 마지막 보행 이후에는 발소리도 멈춥니다.')
s=s.replace('음향 전후 비교 다운로드','발소리 전후 비교 다운로드')
s=s.replace('<a href="../assets/film-master-v2.mp4">음향 수정 전 전체본</a>','<a href="../assets/film-master-v3.mp4">발소리 추가 전 전체본</a>')
s=s.replace('<a href="../assets/film-ending-v2.mp4">음향 수정 전 Ending</a>','<a href="../assets/film-ending-v3.mp4">발소리 추가 전 Ending</a>')
s=re.sub(r'film-master-review.js\?v=[^"]+','film-master-review.js?v=20261001-footsteps4',s)
p.write_text(s,encoding='utf-8')
p=r/'design/film-master-review.js';s=p.read_text(encoding='utf-8').replace('film-master-v3.mp4','film-master-v4.mp4')
s=s.replace('E5pre 원음을 다른 컷과 같은 비율로 회복하고, 반복 E4 발소리 덧입힘을 제거해 앞뒤 공간음을 연결했습니다.','승인받은 배경음을 유지하고 E4·E5 접지음 8회를 POV 보행 박자에 맞춰 추가했습니다. 동일한 소리 하나를 반복하지 않고 접지음 여러 개와 강약을 사용했습니다.')
s=s.replace('E5pre 원음을 다른 컷보다 15.8dB 더 낮춘 편집 오류를 수정하고 반복 발소리 덧입힘을 제거했습니다.','배경음 보정본에 E4·E5 접지음을 보행 간격에 맞춰 추가했습니다.')
p.write_text(s,encoding='utf-8')
v=(r/'design/verify-film-audio-v3.py').read_text(encoding='utf-8').replace('v3','v4').replace('film-audio-v4.audit.json','film-footsteps-v4.audit.json')
(r/'design/verify-film-footsteps-v4.py').write_text(v,encoding='utf-8')
p=r/'USER-REQUIREMENTS-LOG.md'
with p.open('a',encoding='utf-8') as f:f.write('\n\n### U191 · E5pre 배경음 승인과 접지음 보완\n\n사용자는 음향 전후 비교에서 배경 사운드가 좋다고 확인했다. 빠진 발자국 소리를 앞뒤 컷에서 가져와 보행 간격에 맞춰 넣도록 지시했다. 화면 재생성이나 배경음 교체 요청이 아니다. v4는 승인받은 v3 화면·배경음을 유지하고 E4·E5 접지음 8회를 기존 POV 카메라의 보행 박자에 맞춰 추가한다. 박자는 연출용 카메라 키프레임이며 실기 센서 측정값이 아니다. 전체본·Ending·전후 비교를 기존 스토리보드에 갱신한다. 최종 청취 승인은 대기 중이다.\n')
(r/'assets/film-footsteps-v4-delivery.json').write_text(json.dumps(dict(zip(files,urls)),indent=2),encoding='utf-8')

