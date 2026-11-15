# EX-39 보상 기록기와 명령 소비 경로 수정
> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-10-29
> 근거: Kit try02 A run.log 257행, `foothold_s2` 실제 호출 경로, CPU 정답 입력 시험
> 요지: 대각 명령을 여섯 묶음으로 해석해 실패하던 보상 기록기를 13 슬롯으로 바꾸고 기록 소비 경로를 점검했다.
> 상태: CPU 확인됨 · Kit 재실행 대기

## 실패와 수정

try02 A 로그 `C:/Users/AI-WS01/s2_lab/basic_gait_runs/ex39a_kit_smoke/try02/receipts/ex39/A_20261029_223045_999792/run.log:257`의 `basic reward split saw a command outside the six groups`는 보상 계산 직후의 대각 명령을 `basic_group_ids`가 `-1`로 분류해 `summary()`에서 일어났다. B도 같은 위치에서 멈췄다. 이전 CPU 시험은 명령 생성기와 계약 검사기만 불렀고 실제 `RewardSplit.summary()`를 EX-39 대각 입력으로 부르지 않아 놓쳤다.

`RewardSplit`은 EX-39 계약 때 `term.slot_current`, 깃발 환경 마스크, heading 마스크를 보상 계산 직후에 함께 복사한다. 자유 명령은 13 슬롯별 `by_command_slot`로 기록하고 깃발 env는 `flag_env_steps`에 따로 기록한다. 미등록 자유 슬롯 `-1` 또는 `13`은 여전히 실패한다. 기존 `basic_gait_v1`의 여섯 묶음과 학습 보상 값은 그대로다. 목표에 닿아 `wz=0`이 된 heading 회전 슬롯은 실제 선속도와 요속도가 작을 때에만 슬롯 추종으로 센다. `start_runner.py:310`은 이 모드를 `basic_gait_ex39`에만 켠다.

추가로 `kl_probe.py:23`이 순수 옆걸음을 `stand`에 넣던 기록 오류를 수정했다. 수평 속도 두 축 중 하나라도 명령을 받으면 기존 `walk` 대분류로 센다. 이는 KL 로그 분류만 바꾸며 PPO 계산은 바꾸지 않는다.

## 명령 소비자 전수 대조

대표 입력: 전진, 좌우 걸으며 돌기, 좌우 제자리 회전 1.5, 정지, 후진 -1.0, 좌우 옆걸음 0.6, 네 대각, heading 전진 `wz=2.0`, 목표 도달 heading 회전 `wz=0`. CPU 호출은 `test_ex39_command_consumers_cpu.py`와 `test_ex39_cpu.py`의 실제 함수로 했다.

| 소비 경로 | 파일:줄 | 실제 CPU 확인과 결론 |
|---|---|---|
| 생성 · 슬롯 영수증 | `commands/mixed_core.py:212,229`, `mixed_command.py:187` | 13 슬롯 비율과 A/B 같은 난수열, 슬롯 명칭을 기존 EX-39 시험에서 호출해 확인 |
| rollout 계약 | `runners/contracts.py:59,95`, `start_runner.py:342,363` | 13 슬롯과 heading 2.0 허용, 2.1 거절. 보상 기록기 실패보다 앞선 관문 |
| 보상 분리 | `runners/reward_split.py:53,109,221,274` | 대각 포함 13 슬롯과 깃발 env 전 env-step 보존. 보상 계산 직후 복사와 reset 뒤 변경 반례, 잘못된 슬롯 거절 |
| 정지 접촉 · hip · 정지 자세 보상 | `rewards/basic_gait_bundle.py:61,79`, `rewards/mgdp_core.py:51` | EX-39 명령으로 실제 함수 호출. 정지에서만 네 발 보상, 회전 1.5에서 정지 자세 벌점 꺼짐 |
| 행동 통계 | `runners/action_stats.py:64`, `start_runner.py:385` | 실제 `add/summary` 호출. 입력은 행동과 done이며 명령 수치 범위 검사는 없음 |
| 훈련 trace | `eval/training_trace_bridge.py:101,114` | 실제 `pre_step` 호출 후 명령 버퍼 변경, 저장본의 후진 -1.0과 옆 0.6 유지 |
| 지도 전환 통계 | `runners/map_switch.py:149`, `start_runner.py:377` | 실제 `add_step/summary` 호출. map_off, reward, done, level을 받으며 명령 범위 분류 없음 |
| KL 대분류 | `runners/kl_probe.py:23,32` | 실제 `command_branch/summarize` 호출. 옆·대각은 `walk`, 회전은 `spin`, 정지는 `stand` |
| 새 과제 표시 | `commands/mixed_core.py:335,369` | 실제 `new_task_mask` 호출. 정지·후진·옆·대각·걸으며 돌기와 heading 전진을 표기 |
| 노출 로그 | `commands/mixed_core.py:575,609,613` | 실제 `ExposureLog.add/snapshot` 호출. 여섯 방향 대분류는 대각을 큰 축에 넣는다. 별도 13 슬롯 빈도는 `take_slot_counts`로 기록 |
| manifest 요약 | `sol23f_contract.py:59,72`, `start_runner.py:443,448,560` | 기존 EX-39 시험이 실제 `command_settings`와 parser를 호출. 13 슬롯 빈도는 `extra.command_slots`에 기록. 보상 세부는 `extra.reward_split` |
| 고정 평가 칸 | `eval/map_mode_cells.py:39,51,103`, `eval/eval_map_modes.py:298,322,335` | 실제 `summarize`에 모든 대표 명령 호출. B term heading 끔과 고정 명령 보존은 기존 EX-39 CPU 시험. Kit 확인은 미실행 |

진단 전용 `diag_*`, 영상 `record_sol23f.py`, S1 평가 어댑터는 EX-39 훈련기의 활성 경로가 아니다. 읽기 점검에서 범위가 다른 별도 오류를 발견하지 못했지만 이 도구들의 Kit 동작은 미확인이다. KL의 `walk`와 노출 로그의 여섯 방향은 진단용 큰 묶음이며 EX-39 13 슬롯 판정 대신 쓰지 않는다.

## 시험과 인도

- 지정 첫 FAIL: `test_ex39_reward_split_all_slots_and_flag`가 `split_stats() got an unexpected keyword argument 'ex39_mode'`로 실패했다.
- 수정 뒤 `isaac311/python.exe -m pytest`로 `test_ex39_cpu.py`, `test_ex39_kit_smoke_cpu.py`, `test_ex39_command_consumers_cpu.py`, `test_basic_gait_cpu.py`, `test_x11b.py`, `test_x13.py`를 실행해 95 PASS. 이 묶음은 Isaac 앱을 띄우지 않는다.
- `ruff check --select F`, `pyflakes`, `py_compile`, `git diff --check`는 변경 Python 파일에서 0건.
- EX-39 A/B 실제 Kit smoke는 lead가 새 고정본에서 재실행해야 한다. 여기서는 GPU · Kit을 실행하지 않았다.
