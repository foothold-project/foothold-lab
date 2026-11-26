# 앱 만드는 세션용 입구 (app-design-lx 정리)

> 분류: 인계
> 작성: app-design-lx · 2026-11-26 10:5x
> 근거: 팀장 10:59 「너가 잘 정리해야 app-lx랑 다른 에이전트(앱 만드는 에이전트들)이 업무 잘하는거」 · 이 폴더 문서 · foothold-brand DESIGN.md
> 요지: 앱을 만들거나 검토하는 세션은 이 파일부터 읽는다. 정해진 것 · 어디 있는지 · 하지 말 것
> 상태: 살아 있는 문서 · 정해질 때마다 고침 (마지막 11:0x · app-lx 고침 반영)

## 정본 (값을 새로 만들지 말고 여기서 읽는다)
| 무엇 | 어디 | 상태 |
|---|---|---|
| 화면 색 · 예행 색 · 경고 타일 · 온도 색 · 숫자 글꼴 | [foothold-brand DESIGN.md](https://github.com/foothold-project/foothold-brand/blob/main/DESIGN.md) | 확정 (팀장 10:16 · 10:29) |
| 서비스 전체 흐름 13 단계 | [SERVICE-FLOW.md](SERVICE-FLOW.md) | v0.1 |
| 흐름 그림 8 · 실패 갈래 · 빈칸 점검표 | [FLOWS.md](FLOWS.md) | v0 |
| 팀장 답 원문 | [REQ-LEDGER.md](REQ-LEDGER.md) | 계속 쌓임 |
| 일하는 순서 6 단계 · 관문 | [WORK-PROCESS.md](WORK-PROCESS.md) | 승인됨 |
| 현장 지도 셋 · 장애물 경기장 | [MAP-SITES.md](MAP-SITES.md) · [MAP-ARENA.md](MAP-ARENA.md) | v0 |
| 데모 하루 시나리오 (에이전트 형식) | [DEMO-DAY-v0.yaml](DEMO-DAY-v0.yaml) · 생성기 [gen_demo_day.py](gen_demo_day.py) | v0.1 · 모의 실행 통과 (app-lx 재현) |

## 정해진 것 (요약 · 자세한 값은 정본)
- 밝은 모드 = 현장 폰 가로 기본. 어두운 모드 = 관제 FHD 기본. 강조색은 한 화면 한두 곳.
- 경고 타일: 칸 옅게 물듦 + 1 px 테두리 + 칸 위에 붙은 표지 (「과열」 등). 어두운 모드는 이름 · 숫자도 경고색.
- 예행 (시뮬): 파란 점선 + 「예행」 글자. 숫자 · 단위 자리는 실기 칸과 같다.
- 숫자: Inter Tight 400 · tabular-nums. 한글 Noto Sans KR.
- 동작 단추: 순정은 모두 켬 (인사만 회색 · SDK 번호 없음). 저수준은 동작 8 + 조회 2 만 켬, 나머지 회색 · 터치하면 까닭 한 줄 (PR #501, dev 대상, 안 합침).
- 저수준에서 켜진 동작은 실행기 받는 쪽이 아직 없어서 지금은 RUNNER_NOT_CONNECTED 로 거절됨. 통로는 app-lx 가 만드는 중.
- 키보드 · 앱 · 모바일 · 음성 명령은 순정이든 저수준이든 같은 길로 로봇에 간다: 서버 → foothold-robot → 순정 SDK 또는 START 실행기 (팀장 10:49 · app-lx 전달).
- 음성 호출어는 「Hey, Foothold」 (순정은 Hey, BenBen). 한국어 · 영어 둘 다 (팀장 10:49 · app-lx 전달).
- 시뮬 엔진은 MuJoCo (Gazebo 아님).
- 데모 로봇은 실기와 같은 길 (AgentState · robot_info · CameraFrame). 로봇에 demo=true 칸 하나만 다르고, STOP · 해제 · 일정 (run) · 기록 · 이력은 실기와 같은 서버 길로 DB 에 쌓인다 (팀장 10:49 · app-lx 전달). 뼈대 PR #500, 실기와 똑같이 만드는 일은 app-lx 진행 중.
- Go2 X 는 켠 채 충전 안 됨 → 데모 「충전기」 는 배터리 교체 칸.

## 하지 말 것
- DESIGN.md 에 없는 색 · 글꼴 값을 새로 넣지 않는다. 필요하면 app-design-lx 에 묻는다.
- 시안 견본 (고르기 페이지 그림) 을 타일 배치로 그대로 옮기지 않는다. 견본은 색 · 상태 규칙만 보인다. 타일 배치는 WORK-PROCESS 5 단계에서 따로 나온다.
- 아직 안 정한 것 (둥글기 · 간격 · 움직임 · 타일 배치 · 임무 탭 화면) 을 짐작으로 만들지 않는다.

## 아직 안 정한 것 · 누가
| 무엇 | 누가 |
|---|---|
| 둥글기 · 간격 · 움직임 값 | app-design-lx → 팀장 고르기 |
| 관제 타일 배치 · 임무 탭 · 로봇 탭 화면 | app-design-lx (진행 중) |
| 「운영자 회수」 사건 (retrieve) | app-lx 구현 중 → 시나리오에 넣음 |
| 인사 순정 SDK 번호 | 팀장이 앱 「악수」 (SDK Hello) 를 한 번 누르면 app-lx 가 기록 비교로 가림 |
| 악수 옆 「시험 중」 표시 | 팀장 |
| 리모컨과 앱이 동시에 들어오면 어느 쪽이 먼저인가 (app-lx 안: 리모컨) | 팀장 |
| 음성 코드 위치와 음성 문구 목록 | 팀장 · 민우 |
| SLAM 실기 3 단계 (Point-LIO 를 켜서 새 DDS 참가자를 띄울지) | 팀장 |
| START 중 조회 앞의 순정 정지를 건너뛸지 (app-lx 안: 건너뜀) | 팀장 |
