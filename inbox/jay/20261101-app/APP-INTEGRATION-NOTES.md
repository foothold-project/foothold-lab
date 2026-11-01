> 분류: 계획 메모 · foothold-app 과 실험 보행 연결
> 작성: lead · 2026-11-01 23:1x
> 근거: foothold-project/foothold-app dev 읽기(하위 조사 + lead 직접 확인 2 곳: `mobile/sim/policy-adapters.js:2,164` · `apps/agent/foothold_agent/go2_direct/sdk.py:60-66`) · foothold-lab `foothold_s2/deploy/params/deploy.yaml` · `foothold_s2/curriculum/ex40.yaml` · 팀장 11/01 지시
> 요지: 앱은 우리 실험에 맞춘다(앱이 기준이 아니다). 우리 보행 모드를 정답 · 복원 · 끔 세 지도 모드로 넣고, 깊이 입력 경로와 10 걸음 이력을 앱에 만든다. 실기는 지금 Unitree 순정 보행이고 저수준 경로는 새 작업이다.
> 상태: v0.1 · 팀원 전달 전 초안 · 결정 대기 표시 있음

# foothold-app 연결 메모

## 1. 지금 앱 (사실)

| 항목 | 지금 | 근거 |
|---|---|---|
| 보행 모드 | foothold-v2 · ame2-demo 둘, START 는 「undefined」 | `mobile/sim/policy-adapters.js:2,164` (lead 확인) |
| 시뮬 | 브라우저 안 MuJoCo WASM(물리) + Three.js(표시), 추론은 순수 JS · CPU | 하위 조사 |
| 정책 파일 | .pt → TorchScript → npz → float32 가중치 파일 | `docs/POLICY-PROVENANCE.md:12-14` (하위 조사) |
| 지도 입력 | 시뮬 안 수직 광선 높이 스캔(정답 지도에 해당), 깊이 입력 없음 | 하위 조사 |
| 실기 | 에이전트(로봇 쪽 컴퓨터)가 서버와 wss 로 붙고 unitree_sdk2py `SportClient.Move(vx, vy, wz)` 호출 = Unitree 순정 보행 | `sdk.py:60-66` (lead 확인) |
| 저수준 경로 | LowCmd 없음 | 하위 조사(코드 검색 0 건) |
| 키보드 명령 | vx · vy ±1.5, wz ±0.5 | `apps/web/src/serverdrive.tsx:16-21` (하위 조사) |
| 제어 규격 | 50 Hz · Kp 25 · Kd 0.5 · 행동 배율 0.25 · Isaac 관절 순서 | 앱: 하위 조사 · 우리: `deploy.yaml` step_dt 0.02 · stiffness 25 · damping 0.5 · scale 0.25 (같음) |
| Nav2 | NavigateToPose 클라이언트 있음 | `executor/nav2/owner.py:27-63` (하위 조사) |
| SLAM | 저장소 밖 control-app | `README.md:31` (하위 조사) |

## 2. 팀원 전달 사항 (팀장 확인 뒤 전달)

1. 우리 보행 모드 추가: 지도 모드 셋(정답 · 복원 · 끔)을 고를 수 있게. AME-2 모드도 필요한 입력을 갖추게.
2. 입력 셋: 몸감각 10 걸음 이력(45 × 10) · 깊이 2 × 60 × 60(MuJoCo 렌더, 정해진 카메라 위치 · 시야) · 높이 지도 32 × 16(5 cm, 몸 뒤 0.5 m ~ 앞 1.1 m, 폭 0.8 m, 기존 광선 높이 스캔 함수의 격자만 바꿈).
3. 추론 방식: ONNX + 브라우저용 ONNX 런타임(결정 대기 E5).
4. 명령: 가속 제한(갑자기 0 → 1.5 가 아니라 서서히) · 범위는 우리 학습 범위 안으로(결정 대기 E6).
5. 깊이 입력 경로(D435i)를 실기 쪽에도 만들 것.
6. SLAM 은 control-app 이 아니라 foothold-app 안으로.
7. 도메인 이전 때 바꿀 곳: `FH_SITE` · `FH_WS_ORIGIN` · `FOOTHOLD_AGENT_WS_URL` · `FOOTHOLD_PHONE_ORIGINS` · `FH_SIM_AGENT_WS_URL` · 터널 허용 정규식(`phone/origins.py:10`, 지금 `*.trycloudflare.com` 만). 웹은 `location.host` 기준이라 그대로.
8. API 주소 공유: 코드에 박지 않고 환경 변수 · `.env.example` 로. 비밀값은 저장소 비밀 설정으로.

## 3. 단계

| 단계 | 내용 | 시점 |
|---|---|---|
| R0 | 앱 시뮬에 우리 보행(세 지도 모드) · AME-2 입력 정비 | 지금부터 팀원 작업 |
| R1 | 같은 cmd_vel 로 시뮬 · 실기 동시, 장애물 돌아가기 시연 | 이미 일부 됨 |
| R2 | ROS 2 로 Go2 순정 보행 데이터(관절 · 토크 · 명령)를 모아, 그것을 따라 하는 정책을 학습 → 웹 시뮬에 「Go2 순정」 모드 | 11/9 실기 받은 뒤 · 팀 배분 |
| R3 | 저수준 제어로 우리 정책 · AME-2 student 를 실기에 | 추후 논의 |
| R4 | 단층 SLAM → Nav2 → 임무(장애물 앞 정지 · 저장 지도와 스캔 비교 · 도착 사진 · ArUco · 반복 순찰 · 결과 페이지) | 설계 필요 |
| R5 | 복층(층마다 지도) | 목표 |
