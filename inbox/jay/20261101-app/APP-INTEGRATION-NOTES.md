> 분류: 계획 메모 · foothold-app 과 실험 보행 연결 (팀원 전달 원본)
> 작성: lead · 2026-11-01 23:1x 처음 · 11/02 01:5x v0.2
> 근거: foothold-project/foothold-app dev 읽기(하위 조사 + lead 직접 확인: `mobile/sim/policy-adapters.js:2,164` · `apps/agent/foothold_agent/go2_direct/sdk.py:60-66` · `apps/web/src/serverdrive.tsx:20-28,195`) · foothold-lab `foothold_s2/deploy/params/deploy.yaml` · `foothold_s2/models/start_perception.py` · `foothold_s2/curriculum/ex40.yaml` · 팀장 11/01 · 11/02 결정(WORKLIST D103 · D106~D112)
> 요지: 앱은 우리 실험에 맞춘다(앱이 기준이 아니다). 우리 보행을 정답 · 복원 · 끔 세 지도 모드로 넣고, 깊이 입력 · 10 걸음 이력 · 모델별 명령 상한을 앱에 만든다. 추론은 ONNX 우선. 실기는 지금 Unitree 순정 보행이고 저수준 경로는 새 작업이다.
> 상태: v0.2 · 3 절 입력 명세의 빈칸(깊이 카메라 값 등)은 analyst 가 코드에서 채워 v0.3 으로 · 그 뒤 팀원 전달

# foothold-app 연결 메모

## 1. 지금 앱 (사실)

| 항목 | 지금 | 근거 |
|---|---|---|
| 보행 모드 | foothold-v2 · ame2-demo 둘, START 는 「undefined」 | `mobile/sim/policy-adapters.js:2,164` (lead 확인) |
| 시뮬 | 브라우저 안 MuJoCo WASM(물리) + Three.js(표시), 추론은 손으로 짠 JS · CPU | 하위 조사 |
| 정책 파일 | .pt → TorchScript → npz → float32 가중치 파일 | `docs/POLICY-PROVENANCE.md:12-14` (하위 조사) |
| 지도 입력 | 시뮬 안 수직 광선 높이 스캔(= 정답 지도). 깊이 입력 · 몸감각 이력 없음 | 하위 조사 |
| 실기 조종 | 키를 누르는 동안 고정값(앞 · 뒤 · 옆 1.5 m/s, 회전 0.5 rad/s), 떼면 0. 서서히 올리는 장치는 이 화면 코드에 없음 | `serverdrive.tsx:20-21,195` (lead 확인) |
| 실기 경로 | 2 절 그림 | |
| 저수준 경로 | LowCmd 없음 | 하위 조사(코드 검색 0 건) |
| Nav2 | NavigateToPose 클라이언트 있음 | `executor/nav2/owner.py:27-63` (하위 조사) |
| SLAM | 저장소 밖 control-app | `README.md:31` (하위 조사) |
| ame2-demo | 앱 시뮬에서 계단을 못 오름(석헌 원 실험에서는 오름). 원인 조사 중(analyst) | 팀장 11/02 관찰 |

## 2. 명령이 실기로 가는 길 (지금)

1. 사람이 브라우저(노트북이든 휴대폰이든) 화면에서 키를 누른다.
2. 브라우저 → 서버(NaverCloud, FastAPI): WebSocket `wss://<서버>/api/v1/ws` 로 50 ms 마다 `rt.cmd`(vx, vy, wz).
3. 서버 → 에이전트: 서버가 같은 허용 표로 검사한 뒤 `/api/v1/agent/ws` 로 중계(`apps/server/fh_server/realtime.py:2242-2243`).
4. 에이전트 = Go2 와 랜선(10 m)으로 이어진 노트북에서 도는 프로그램. 에이전트가 먼저 서버에 wss 로 접속해 두고 명령을 받는다.
5. 에이전트 → Go2: `unitree_sdk2py` 의 `SportClient.Move(vx, vy, wz)` 를 부른다(`sdk.py:60-66`). 통신은 랜선 위 DDS(ROS 2 가 쓰는 것과 같은 통신 방식).
6. Go2 안의 Unitree 순정 제어기가 다리를 움직인다(sport mode).

ROS 2 는 이 길에 없다. ROS 2 가 쓰이는 곳: 서버 시뮬 연결(`ros_bridge` 가 `/v2_live/cmd_vel` 을 내고 `/v2_live/state` · `/v2_live/odom` 을 받음, `ros_bridge/node.py:179,264-297`) · Nav2 실행기(에이전트 안 `executor/nav2`, `/v2_map/map` · `/v2_map/scan` · `/tf` 구독).

## 3. 우리 보행 모드 입력 명세 (팀원 구현용)

| 입력 | 모양 | 뜻 | 정본 위치 |
|---|---|---|---|
| 몸감각 이력 | 10 × 45 | 최근 10 걸음(0.2 s)의 몸감각 45 개. 첫 걸음은 리셋 때 채움 | `start_perception.py` · env 관측 정의 (analyst 가 순서 · 축척 표로 v0.3) |
| 깊이 | 2 × 60 × 60 | 머리 깊이 카메라 2 프레임. 10 Hz(정책 5 걸음마다 갱신) · 1 프레임(0.1 s) 지연 | `start_perception.py:64-65` · 카메라 위치 · 시야 · 거리 범위는 `foothold_s2/tasks/s2_23f_camera.py` · depth_cam_cfg (v0.3 에 값) |
| 높이 지도 | 32 × 16 | 5 cm 격자, 몸 뒤 0.5 m ~ 앞 1.1 m, 폭 0.8 m. 정답 지도 모드에서만 씀 | `start_perception.py:26-28` |
| 명령 | 3 | vx, vy, wz (몸감각 45 안에 포함) | |
| 지도 모드 | 셋 | 정답(광선 높이 지도) · 복원(깊이 → 지각 모듈이 지도 복원) · 끔(지도 칸 0) | AdaSmpl · p_map_off |
| 기억 | GRU 둘 | 몸감각 GRU(매 걸음) · 깊이 GRU(10 Hz 틱에만). 리셋 때 0 | `start_perception.py:9,286` |

제어 규격(우리 배포 설정, `deploy.yaml`): 정책 50 Hz(step_dt 0.02) · 관절 PD Kp 25 · Kd 0.5 · 행동 배율 0.25 · 기본 자세 hip ±0.1 · thigh 0.8(앞) 1.0(뒤) · calf −1.5 · Isaac 관절 순서(hip 4 → thigh 4 → calf 4). 앱 foothold-v2 와 같다(하위 조사 대조). 추가로 대조할 것: 행동 자르기 · 관측 축척 · 토크 한계(hip · thigh 23.5 · calf 45.43 N·m) · 물리 간격(0.005 × 4).

## 4. 팀원 전달 사항

1. 우리 보행 모드 추가: 지도 모드 셋(정답 · 복원 · 끔)을 고를 수 있게. AME-2 모드도 필요한 입력을 갖추게.
2. 3 절 입력 셋을 앱에 만든다: 10 걸음 이력 버퍼 · MuJoCo 깊이 렌더(카메라 값은 v0.3) · 높이 지도 격자 32 × 16.
3. 추론: ONNX + 브라우저용 ONNX 런타임 우선(D107). 같은 입력에서 PyTorch 와 출력 차이 1e-4 안 시험을 통과해야 모드로 연다. 기기별 속도 측정.
4. 명령 상한은 모델마다 다르다. 정책 파일과 함께 「명령 범위 파일」(JSON)을 내보내고, 앱은 그 범위로 자른다. 우리 학습이 넓어지면 파일만 바뀐다(D108). 지금 값은 5 절.
5. 키 입력은 누르는 길이에 따라 서서히 오르게(가속 제한). 실기 안전에도 필요.
6. 깊이 입력 경로(D435i)를 실기 쪽에도 만든다.
7. SLAM 은 control-app 이 아니라 foothold-app 안으로.
8. 도메인 이전 때 바꿀 곳: `FH_SITE` · `FH_WS_ORIGIN` · `FOOTHOLD_AGENT_WS_URL` · `FOOTHOLD_PHONE_ORIGINS` · `FH_SIM_AGENT_WS_URL` · 터널 허용 정규식(`phone/origins.py:10`, 지금 `*.trycloudflare.com` 만). 웹은 `location.host` 기준이라 그대로. 상세는 super2 문서(mai-os `os/site-domain-migration.md`).
9. API 주소 공유: 코드에 박지 않고 환경 변수 · `.env.example` 로. 비밀값은 저장소 비밀 설정으로.
10. 역할(팀장 11/02): 오현민 = foothold-app 주 개발(커밋 계정 less82) · 도메인 설정 반영. 이민우 = 실기 주행 + ROS 로 들어오는 관절 데이터 모으기(R2).

## 5. 명령 범위 (우리 학습이 기준)

| 축 | 우리 학습(지금 → EX-41) | 앱 상한 권고 |
|---|---|---|
| 전진 | 0.3 ~ 1.5 | 1.5 |
| 후진 | −1.0 → −1.3 (D105) | −1.3 |
| 옆 | 0.2 ~ 0.5 | 0.5 (학습이 넓어지면 0.8) |
| 제자리 회전 | 0.5 ~ 1.2 | 1.2 |
| 걸으며 회전 | 0.2 ~ 0.5 | 0.5 |

배운 범위 밖 명령은 정책이 예측할 수 없게 움직인다(예: 후진을 안 배운 foothold-v2 는 후진 명령에 뒤로 넘어짐, 팀장 관찰). 그래서 모드마다 상한을 건다.

## 6. 단계

| 단계 | 내용 | 시점 |
|---|---|---|
| R0 | 앱 시뮬에 우리 보행(세 지도 모드) · AME-2 입력 정비 · ame2-demo 계단 문제 원인 | 지금부터 |
| R1 | 같은 cmd_vel 로 시뮬 · 실기 동시, 장애물 돌아가기 시연 | 이미 일부 됨 |
| R2 | Go2 순정 보행을 따라 하는 정책: Go2 앱 apk 분석으로 Sport_Mode 보행을 받을 수 있는지(analyst) → 안 되면 ROS 2 로 관절 · 토크 · 명령을 모아 모방 학습 → 웹 시뮬에 「Go2 순정」 모드 | 계획은 지금 · 수집은 11/9 실기 뒤 |
| R3 | 저수준 제어로 우리 정책 · AME-2 student 를 실기에. 정책은 로봇 쪽 컴퓨터에서 돈다(서버 경유 아님) | 추후 논의 |
| R4 | 단층 SLAM → Nav2 → 임무(장애물 앞 정지 · 저장 지도와 스캔 비교 · 도착 사진 · ArUco · 반복 순찰 · 결과 페이지) | 설계 필요 |
| R5 | 복층(층마다 지도) | 목표 |
