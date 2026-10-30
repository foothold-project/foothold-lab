> 분류: 운영 · 평가 실행
> 작성: 오흥재 (runner 반영) · 2026-10-30
> 근거: WORKLIST D73 · D74 · lead EX-40 v8 지시와 22:0x 잡음 정정 · Isaac Lab 설치 소스
> 요지: EX-40 v8 DR reset/interval 연결과 update별 readback을 구현하고 미검증 기동을 차단한다
> 상태: CPU 시험 통과 · 범위표 미수신 · Kit/GPU 미실행 · 기동 차단

# EX-40 v8 DR 연결 보고

## 결과

전용 worktree `C:/mai/wt/foothold-lab/runner-ex40-v8`에서 작업했다. D74 일정은 D 길이 1500 update로 고정했다. B0은 배율 0, B1~B3c는 update 1501~6000의 0~0.5 보간, D는 6001~7500의 1, T0는 7501~8000의 1이다. `max_iterations`는 8001이다. 이는 설정값이며 실측 결과가 아니다.

설치된 Isaac Lab 소스에서 `randomize_rigid_body_com`, `randomize_actuator_gains`, `push_by_setting_velocity`, `EventTermCfg`의 실제 인자와 호출 방식을 읽고 adapter를 연결했다. Reset 이벤트는 COM, 관절 이득, DCMotor 한도를 적용한다. Interval 이벤트는 Isaac Lab의 velocity push를 호출한다. 지연 액션은 reset마다 현재 배율에 맞춰 최대 지연 tick을 바꾸고 표본 히스토그램을 기록한다. trainer의 `train_extra.jsonl`에 매 update 이벤트 표본 수, 실제 물리값 요약, 지연 분포, 일정 배율과 고정 잡음 설정을 남긴다. 재개 상태에는 DR 설정 해시와 직전 update를 넣어 다음 update 연속성을 검사한다.

관측 잡음은 팀장 정정에 따라 처음부터 끝까지 고정 1×로 기록하며 DR 일정 항목에서 제외했다. 마찰 0.2~1.2와 질량 변화 -1~3 kg는 보존 startup 설정으로 그대로 둔다. 범위가 확인되지 않은 COM, actuator gains, motor strength, push velocity와 push interval은 채우지 않았다.

## 실행 차단과 검증 한계

지정 범위표 `C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/DR-RANGES-EX40-1030.md`가 현재 없다. 네 가지 미확정 범위 및 push interval을 임의로 채우지 않았고 `runtime_adapter_status`를 `implementation_in_progress`로 유지했다. launch guard는 범위가 채워지고 adapter 검증 상태가 `verified`가 아니면 AppLauncher 생성 전에 거부한다.

Kit smoke 구현은 B0, ramp, D 진입에서 reset 이벤트를 실제 호출하고 interval 이벤트도 실제 EventManager에 호출한 뒤 event sample readback을 확인하도록 했다. 다만 이번에는 Kit/GPU를 띄우지 않았으므로 이벤트 적용, PhysX readback, 첫 reset, interval push, 재개 뒤 동작은 미확인이다. Kit smoke 결과가 없으므로 runtime adapter는 검증 완료 상태가 아니다.

## CPU 검증

- `py_compile` 대상 파일 구문 확인 통과.
- `pytest -q foothold_s2/tests/test_ex40_dr_v8_cpu.py foothold_s2/tests/test_ex40_v7_continue_cpu.py`: 18 passed.
- 답을 아는 입력으로 일정 경계, 1500 update 길이 고정, 지연 tick 반올림, 합성 범위 스키마, 고정 잡음 1×, 빈 범위 기동 거부, readback 누락 및 실제 event 표본 0건 반례를 확인했다.
- 설치 Isaac Lab 소스의 API 시그니처를 AST로 확인했다. 이 확인은 소스 계약 대조이며 Kit 실행 증거가 아니다.

## 변경 파일

- `foothold_s2/curriculum/ex40_dr.py`
- `foothold_s2/curriculum/ex40.yaml`
- `foothold_s2/curriculum/ex40_dr_runtime.py`
- `foothold_s2/tasks/delayed_action.py`
- `foothold_s2/scripts/train_sol23f_common.py`
- `foothold_s2/runners/start_runner.py`
- `foothold_s2/curriculum/continuous.py`
- `foothold_s2/ex40_kit_smoke.py`
- `foothold_s2/tests/test_ex40_dr_v8_cpu.py`
- `inbox/jay/20261030-plan/REPORT-runner-ex40-v8.md`

다음에는 범위표 수신 뒤 CPU 계약을 갱신하고, 별도 승인된 Kit smoke에서 reset·push 표본과 PhysX readback을 확인해야 한다. 그 전까지 EX-40 v8 기동은 차단된다.
