"""Point the single storyboard at the closing-appended review exports."""
from pathlib import Path
import json
r=Path(__file__).resolve().parents[1]
p=r/'output/FOOTHOLD-film-storyboard.html'
s=p.read_text(encoding='utf-8')
s=s.replace('전체 연결본 · 69.5초','전체 연결본 · 81.2초 · 브랜드 클로징 추가')
s=s.replace('../assets/film-master-v1.mp4','../assets/film-master-v2.mp4')
s=s.replace('../assets/film-ending-v1.mp4','../assets/film-ending-v2.mp4')
s=s.replace('Ending · 38.4초','Ending · 50.1초 · 브랜드 클로징 포함')
s=s.replace('MISSION COMPLETE와 암전까지.','MISSION COMPLETE와 암전 뒤 제공받은 브랜드 클로징까지.')
s=s.replace('전체 영상 다운로드</a>','전체 영상 다운로드</a> · <button onclick="const v=document.getElementById(\'masterVideo\');v.currentTime=69.5;v.play()">추가한 브랜드 클로징 재생</button> · <a href="../assets/film-master-v1.mp4">이전 전체본</a>')
s=s.replace('Ending 다운로드</a>','Ending 다운로드</a> · <a href="../assets/film-ending-v1.mp4">이전 Ending</a>')
s=s.replace('별도 영화 음악은 아직 없습니다.','별도 영화 음악은 아직 없습니다. 끝에 사용자 제공 브랜드 영상 11.7초와 그 원음을 붙였습니다. 기존 장면과 브랜드 영상의 사운드는 아직 최종 통합 믹싱 전입니다.')
s=s.replace('완성본은 음향·전체화면·탐색 막대가 있는 플레이어로 제공합니다.','검토본은 음향·전체화면·탐색 막대가 있는 플레이어로 제공합니다.')
s=s.replace('film-master-review.js?v=20261001-master1','film-master-review.js?v=20261001-master2')
p.write_text(s,encoding='utf-8')
p=r/'design/film-master-review.js';s=p.read_text(encoding='utf-8')
s=s.replace("file:'film-master-v1.mp4'","file:'film-master-v2.mp4'")
s=s.replace('전체 69.5초 · Opening 31.125초 · Ending 38.375초.','전체 81.208초 · Opening 31.125초 · Ending 50.083초. 제공받은 브랜드 클로징 11.708초를 전체본과 Ending 뒤에 붙였습니다.')
s=s.replace('통합 사운드가 포함된','임시 사운드가 포함된')
p.write_text(s,encoding='utf-8')
manifest={'source':'https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260930_233959_ae4a4a56-1db5-4f21-bd67-15ec33363dab.mp4','source_video_frames':281,'fps':24,'append_at':69.5,'master_seconds':1949/24,'ending_seconds':1202/24,'opening_unchanged':'film-opening-v1.mp4','master':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/894ac413-67fa-45e4-9ffb-6eae98b6e637.mp4','ending':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/5223eea0-9ad8-4b5c-bf51-9dc1652de4bb.mp4','render':'Higgsedit native composition, original audio concatenation, exact ending split','sound_status':'Existing temporary mix plus supplied closing audio. Full cinematic score and final sound mix remain incomplete.','source_text':'FIND THE NEXT STEP is in the user supplied clip. Preserved without alteration.'}
(r/'assets/film-append-closing-v2.outputs.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
