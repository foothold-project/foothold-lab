> 분류: 구현 검증
> 작성: verifier-lx · 2026-11-12 01:41
> 근거: lead-lx 재측정 뒤 자동 손넘김 의뢰 · 01:20 예산 정의 · 통합 f7a48c25 · CPU 원출력
> 요지: P1 다음 단계 실행 인자 연결 · 실제 채택 계보 예산 · 단계 증거 생산 · E1F→E2 CPU 손넘김
> 상태: CPU 검증 · GPU/Kit/본 실행 미실행 · 후속 단계 판정기와 실측 생산자는 아래 경계

# EX-42 자동 손넘김

## 바뀐 소비 경로

| 자리 | 전 | 후 |
|---|---|---|
| stage_launcher.p1_argv | next-stage 인자 없음, PASS여도 no_launcher | 같은 잠근 소스의 launcher · queue · dispatch를 P1에 전달 |
| 다음 단계 template | 수동 환경 설정 필요 | 실행 중인 불변 plan/approvals를 다음 template으로 전달 |
| 누적 예산 | 고정 EX42_MATERIALIZE_BUDGET_USED | 출구 manifest 실제 완료 회차 + 부모 cumulative_update − E0 부모 cumulative_update |
| 증거 파일 | 사전 작성한 target.json만 소비 | 실제 P1/측정·평가 mesh·W08/W09 pin에서 새 파일 생성, 다른 생산자는 SHA 고정 입력 |
| 손넘김 실행 | 등록된 launcher가 있을 때만 기존 _hand_off 수행 | 기존 _hand_off/start_launcher/queue 등록 로직 유지, 위 입력 생산을 연결 |

현재 계보의 예산은 E0 250 + 채택한 E1 재학습 1000 = 1250. E1F 500회 종료면 1750. stage zero m12000→m13000은 원점 밖이며 버려진 첫 E1은 이 부모 계보에 없으므로 합산하지 않는다. 환경 변수에 999999를 넣어도 이 계산이 유지되는 CPU 반례를 포함했다. 계보가 다른 정책을 합쳐 전체 장비 사용량을 나타내는 수치는 아니다.

## CPU 증거

- 기존 연결 회귀: `149 passed in 142.46s (0:02:22)`.
- 실제 `_hand_off` → `start_launcher` → queue 등록은 fake 자식으로 `1 passed in 13.91s`. 가짜 PASS는 시험 안에만 만들었다.
- E1F 실제 flag 판정기와 원 trace 검증, materialize, transition 재계산을 거쳐 E2의 `train_start.py --ex42_stage_dry_run` rc0. `training_blockers=[]`, `app_launcher_started=false`.
- E2 dry는 로컬 실물 E2 메시 profile을 읽었다. 부모 pt와 M0~M3 영수증은 명시적인 CPU fixture이므로 실제 학습 기동 증명이 아니다.
- 없는 model, checkpoint SHA 다름, manifest 진행도 다름, source plan SHA 다름을 거절했다.
- 평가 뒤 메시 바이트 변경, 평가 영수증 checkpoint 섞임, M0~M3 binding SHA 다름을 거절했다.
- 원출력: `/home/jay/mai/tmp/verifier-lx/handoff-1112/regression.log`, `actual.log`, `test3/…/E2-cli.log`.

### 고정 사본과 추가 반례

- 커밋 0f9a066c의 git archive 고정 사본: 새 시험 `12 passed in 66.92s`. 경로 `/home/jay/mai/tmp/verifier-lx/handoff-1112/locked-0f9a066c`.
- launcher 인자 누락, 예산 0 고정, 메시 SHA 검사 제거, 필수 생산자 누락 허용, checkpoint 섞임 허용 돌연변이 5개를 각각 잡았다. 원문 `mutants.json` 및 이름별 `.log`.
- M0~M3는 파일 SHA만 맞는 HOLD, 항목 누락, 원자료 변조, 다른 메시를 거절한다. 새 파일 생산 시뿐 아니라 기존 E2.json을 주는 경로도 검사한다. 두 경로 모두 고침 전 DID NOT RAISE를 직접 확인했고 고침 뒤 `16 passed in 82.23s` + 기존 파일 우회 시험 `1 passed in 6.80s`.
- M0~M3 제안 꼴은 `format=foothold-ex42-m0-m3/1`, `status=PASS`, `stage_id=E2`, `checks.M0~M3.status/evidence`, `mesh.geometry_sha256/files`. analyst 생산자와 키 조율 중이다. 이 검사는 실측을 대신 수행하지 않는다.

## 단계별 입력 생산자

| 단계 | 자동으로 잇는 것 | 별도 필수 생산자 / 미확인 |
|---|---|---|
| E1F | 재측정 다리 PR731의 E1 PASS · W09 baseline · W08 calibration · 실제 부모와 cap | 1000회 채택 run 실제 종료 및 관문 PASS |
| E2 | E1F PASS, eval_receipt의 실제 메시, inherited W09/W08 | M0~M3 실측 JSON과 SHA, analyst 생산 중 |
| E3 | 앞 단계 PASS · 메시 · W08 | 종류 개방 순서 실측, planner 사전 고정 진입 축 |
| E4 · E5 | 앞 단계 PASS · 메시 · W08 | planner 사전 고정 진입 축, 단계 판정기 별도 작업 |
| E6a | E5 실제 stage_id · PASS · 메시 · W08 | 자세 판정기, planner 진입 축 |
| E6b | E6a PASS · 메시 · W08 | Q12 센서 결정, 최종 종류 판정기, planner 진입 축 |
| M | W08 pin, 실제 누적 계수 | 진입 조건 · 원천 단계 · 복귀 회계 · mapoff 판정, 후속 작업 |

`EX42_MATERIALIZE_BINDINGS_FILE`은 target별 등록된 prerequisite 경로만 받아 실제 파일 SHA를 검증한다. M0~M3는 CPU manifest · 생성 시간 · 메모리 · 광선 실측을 뜻한다. 유지 관문 PASS를 이 영수증으로 둔갑시키지 않는다. 원자료가 없으면 자동 증거 파일을 발행하지 않는다.

## 남은 경계

E1F→E2 연결 CPU만 통과했다. 모든 뒷단계의 출구 판정 구현 완료나 실제 자동학습 성공을 뜻하지 않는다. integration f7a48c25의 E3 이후 다중축 승인 칸은 axis=null이므로 planner 사전 등록이 필요하다. 결과를 보고 gate에서 축을 골라 넣는 fallback은 사용하지 않는다. E6b Q12는 미결이면 계속 막힌다. GPU 학습, 실제 launcher 자식, 실제 queue 등록을 이번 검증에서 실행하지 않았다.
