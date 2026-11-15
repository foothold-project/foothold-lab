# EX-39 실제 명령 계약 고침
> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-10-29
> 근거: lead의 EX-39 Kit smoke try01 run.log 254행, 코드 `a9d82992`, D55 슬롯 정의
> 요지: EX-39 생성 명령을 EX-38 계약으로 검사해 멈춘 결함을 전용 계약과 실제 소비 명령 시험으로 고쳤다.
> 상태: CPU 검증 완료 · Kit 재기동 미실행 · lead 재확인 대기

## 실제 실패와 원인

`C:\Users\AI-WS01\s2_lab\basic_gait_runs\ex39a_kit_smoke\try01\receipts\ex39\A_20261029_221734_998129\run.log`의 첫 학습 회차 iter 3002에서 명령 계약 `basic_gait_v1` 위반 584 env로 중단됐다. 첫 예는 `[0, 0, -1.484276]`이다. EX-39의 제자리 회전 범위는 `|wz| ≤ 1.5`이므로 정상 명령이지만 EX-38 검사는 `|wz| ≤ 1.2`만 받았다.

`sol23f_contract.command_settings`가 `basic_ex39_arm`에도 `basic_gait_v1`을 반환했고, `train_sol23f_common`이 이를 runner `pc["contract"]`에 넣었다. `start_runner.learn`은 매 rollout step에서 실제 소비 명령을 읽은 뒤 이 계약을 적용한다. 기존 CPU 시험은 EX-39 슬롯 비율과 명령 범위, EX-38 계약의 옛 표집기만 따로 검증했고 EX-39 표집 결과를 runner가 선택한 계약에 넣지 않았다. 그 연결 공백 때문에 놓쳤다.

## 수정 계약

EX-39만 `basic_gait_ex39`를 선택한다. EX-38의 `basic_gait_v1`과 START·EX-35 계약은 그대로 둔다. 비 heading 명령은 D55의 13 슬롯 범위를 검사한다. 전진 `[0.3,1.5]`, 걸으며 돌기 `vx [0.3,0.8]`와 `|wz| [0.2,0.5]`, 제자리 `|wz| [0.5,1.5]`, 후진 `vx [-1.0,-0.2]`, 옆걸음 `|vy| [0.2,0.6]`, 대각 `|vx| [0.3,0.6]`와 `|vy| [0.2,0.5]`, 정지 세 칸 0이다. heading 표시가 참인 env는 전진 또는 제자리만 허용하고, 매 step 다시 쓴 `|wz| ≤ 2.0`을 검사한다. heading 배열이 없거나 명령 행과 모양이 다르면 예외로 거절한다. 모든 명령의 NaN·Inf도 거절한다.

runner는 `env.step` 이전에 `vel_command_b`와 같은 시점의 `term.heading`을 복사해 검사한다. Kit probe는 runner의 실제 계약 이름이 `basic_gait_ex39`인지 확인한 뒤에만 계약 확인 칸을 PASS로 쓴다. RewardSplit의 기본 보행 기록도 새 이름을 받는다.

## 전수 검색

| 위치 | EX-39 영향과 조치 |
|---|---|
| `sol23f_contract.py` · `train_sol23f_common.py` | 명령 설정과 실제 runner 계약 연결. EX-39 전용 이름으로 수정. |
| `runners/contracts.py` · `runners/start_runner.py` | 실제 rollout 명령의 유일한 치명 범위 검사. 슬롯·heading 검사 추가. |
| `ex39_kit_probe.py` | 종전에는 `command_contract=True`만 기록했다. 이제 실제 runner 계약 이름을 확인. |
| `runners/reward_split.py` 호출부 | 보상 기록용 basic 분류. EX-39도 기본 보행으로 분류. 범위 거절은 하지 않는다. |
| `eval/eval_map_modes.py` · `eval/turn_probe.py` | 평가 고정 명령에서 heading을 끄는 검사이며 학습 슬롯 범위 검사는 아니다. 기존 EX-39 heading guard 유지. |
| `basic_gait_launch.py` · `basic_gait_extend_parent.py` | EX-36/38 및 EX-38 부모 판의 `basic_gait_v1` 영수증 검사. EX-39 현재 rollout 계약이 아니므로 유지. |
| `eval/judge*.py` · `deploy/command_filter.py` | 평가 결과 지표 또는 실기 명령 필터. EX-39 학습 명령 범위의 추가 치명 검사는 검색되지 않았다. 별도 평가 수치는 Kit 재실행 전 미확인. |

검색식: `rg -n 'basic_gait_v1|basic_gait_contract_bad|contract_bad_fn|command_contract|ex39_arm|wz_max|spin_wz' foothold_s2 --glob '*.py'`. 전수 범위는 이 작업 사본의 `foothold_s2` Python 파일이다.

## CPU 증거와 남은 일

`isaac311`의 관련 시험 7개 파일에서 60 PASS. 새 반례는 실제 실패 값 `wz=-1.484276`의 옛 계약 거절·새 계약 수용, 잘못된 대각·비 heading 큰 회전·상한 초과 heading·NaN 거절이다. A/B 각각 100,000 env의 `resample_ex39` 출력에 `apply_heading`을 적용한 뒤 실제 runner가 쓰는 `command_sample_bad`에 넣어 전부 통과했다. 기존 START·EX-35·EX-38 시험도 함께 통과했다.

Kit·GPU는 이 고침 뒤 실행하지 않았다. lead가 같은 고정 커밋의 A/B를 다시 시작해 첫 rollout, 실제 보상 probe, B 평가 heading 영수증을 확인해야 한다. 이전 try01 실패 기록과 출력은 수정하지 않았다. 코드 바이트 목록은 `SHA256SUMS-EX39-contract-fix.txt`이다.
