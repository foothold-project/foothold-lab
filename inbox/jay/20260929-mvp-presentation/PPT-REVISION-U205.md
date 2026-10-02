# U205 · 동일 Go2를 중심으로 한 발표 수정

> 분류: 결정
> 작성: 오흥재 · 2026-10-02 01:10
> 근거: 이번 사용자 장문 피드백과 표시 이미지 2개
> 요지: 잘못된 배치와 표면적 모션을 수정하고, 도입·기술 설명을 연속 장면으로 연결
> 상태: 수정 구현 및 검토 중. 사용자 승인 전
> 판: v1.0

기존 이슈 #490. 이전 지시 U202~204를 대체하거나 잊지 않는다. 아래는 요구사항을 빠짐없이 실행 단위로 나눈 기록이다. 발화 시각은 미확인이고 머리 시각은 기록 시각이다.

## 사용자 요구

1. 2페이지 진입 시 영상 바로 재생. 발표에 필요한 기본 동작으로 도입.
2. 발표 멘트는 사용자가 직접 작성한 화제 제시와 이야기 전개·다음 질문의 흐름을 반영. 에이전트가 깔끔하게 요약한 별도 원고로 대체하지 말 것.
3. 제품 상세 이미지처럼 표기선의 시작점·끝점·테두리 연결을 정교하게. 선이 박스 안이나 원 안에 침범하지 않음.
4. 사진의 비율·비례·표현 방법을 발표에 맞춰 결정. 대충 잘라 붙인 작은 스티커처럼 보이지 않게.
5. 3페이지 최초에는 픽셀 대신 큰 정면 실사 Go2. 질문과 라인 애니메이션 후 실사→픽셀→우측 상단 진행 표시로 연결.
6. 진행선은 에러처럼 보이는 험지 굴곡 대신 직선. 픽셀을 현재보다 축소(사용자 표현: 지금보다 70프로 작아도). 투명 알파 배경, 사각 바탕 제거.
7. 좌측 FOOTHOLD·섹션명과 우측 진행 표시는 모든 페이지에서 같은 좌표. 험지 페이지도 예외 아님.
8. 4→5 전환 시 같은 배경이 이동했다 복귀하는 버벅임 제거. 이미지 고정.
9. 5페이지의 빨간 표시: 좌측 포인트를 왼쪽으로 옮기고, 우측 상자 둘의 위치·폭·간격을 정렬. 선은 점→꺾임→상자 테두리에서 끝나야 함. 표시색 빨강을 디자인색 채택으로 해석하지 않음.
10. 6페이지는 첫 클릭 이전에 투명 정면 Go2만 크게 중앙. 원 안으로 사진을 클리핑하지 않음. 얇은 원 외곽선이 그려지고 설명과 외곽 박스/선이 단계 등장. 선이 원 내부에 침범하지 않음. 초기부터 선을 보여주지 않음.
11. 7페이지 실사 이미지와 8페이지 이동 방식 비교도 같은 비율·레이아웃 문제 해결. 중앙에 같은 투명 Go2 사용.
12. 10페이지의 '학습 환경 속 같은 Go2', '몸을 둘러보면 네 다리가 연결됩니다', '정면에서 측면으로', '연결된 부품을 펼쳐 봅니다' 등 제작 동작 설명을 삭제.
13. 기술 설명의 목적: 힘 전달·관절 위치·4다리×3자유도·LiDAR·카메라·Depth·발끝 힘·앞뒤 관절 움직임·시각/깊이 정보·마이크·4D LiDAR L2 데이터 등을 청자가 로봇 위의 위치와 역할로 이해하게 할 것.
14. 기존11페이지 별도 이미지 대신 같은 Blender Go2에 센서 포인트와 설명을 연결.
15. 같은 로봇에서 몸 상태·명령·이전 행동·지면 높이 스캔 등 관측 입력을 애니메이션으로 설명.
16. 기존13 신경망: Go2 중앙 정면, 좌측 입력/Critic, 우측Actor와12출력처럼 같은 장면에서 연결. Manim 또는 적절한 모션 도구. Critic→Actor 직렬로 오해시키지 않음.
17. 기존16까지를 연속 장면으로 통합할 수 있음. 정면 Go2가 시뮬레이션 공간으로 들어간 뒤 카메라가 빠져4,096환경 설명으로 연결.

표시 원본: C:/Users/AI-WS01/AppData/Local/Temp/orca-paste-1790868615923-fcf329ed-3db5-4288-930e-a31421b1e4d0.png 및 orca-paste-1790868944492-7e30372f-751d-4c87-b61a-97f3f4f6c266.png. 임시 원본을 지속 보존하려면 assets/feedback-u205-* 사본을 사용.

## 반영 방법과 사실 구분

- 발표 HTML 진입점 유지. design/scene_revision.py·css, technical_scene.py·css와 intro_story.js에서 이번 수정 구현.
- 10~16의 내용을 하드웨어, 정책 흐름, 병렬 학습의 3개 장면으로 묶음. 장 내부에서 다음/이전 클릭으로 설명 단계 변경. 전체42장으로 변경.
- 기술 근거는 PPT-TECHNICAL-SCENE-EVIDENCE.md에 로컬 학습 설정과 체크포인트를 직접 열어 기록.
- 235입력과 Actor/Critic·0.25action scale은 실제 설정. 움직이는 네트워크점과 높이격자는 설명 모션이고 저장된 활성값/높이시계열이 아님.
- Blender 관절 구동은 원본 USD 기구학 설명. 실제 RL정책이 만든 보행이라고 부르지 않음.
- 학습설정4096과 기존학습영상렌더600을 구별해 화면·메모에 명시. 연속Isaac카메라로4096전체를 새 촬영했다는 주장이 아님.
- 기본RGB와 추가D435i구분. 카메라/원본LiDAR/발접촉력이 현재235에직접들어가는것처럼연결하지않음.
- 알파 추출은 built-in imagegen 사용. assets/go2-front-alpha-v1.png, go2-pixel-alpha-v2.png. 기존 승인 원본 유지.

## 알파 편집 프롬프트

정면: Use case background-extraction. Extract ONLY the exact front-facing Go2 robot from the top-left panel of the approved sheet into one RGBA PNG. Preserve exact identity, proportions, pose, camera, lidar, materials and scratches. Remove backdrop, floor, shadow, labels, borders, other views. Single centered full body, actual transparent alpha.

픽셀: Use case background-extraction. Edit the exact8×4 sheet. Remove only pale ivory background and shadow, output real RGBA alpha. Preserve32sprites at exact grid locations, poses, colors, framing and2:1aspect. Include transparency between legs, no opaque checkerboard.
