> 분류: 운영 · 평가 실행
> 작성: 오흥재 (runner 반영) · 2026-10-30
> 근거: WORKLIST D73 · D74 · lead EX-40 v8 지시와 22:0x 잡음 정정 · Isaac Lab 설치 소스
> 요지: EX-40 v8 DR reset/interval 연결과 update별 readback을 구현하고 미검증 기동을 차단한다
> 상태: CPU 시험 통과 · 범위표 미수신 · Kit/GPU 미실행 · 기동 차단

# EX-40 v8 DR 연결 보고

## 결과

전용 worktree `C:/mai/wt/foothold-lab/runner-ex40-v8`에서 작업했다. D74 일정은 D 길이 1500 update로 고정했다. B0은 배율 0, B1~B3c는 update 1501~6000의 0~0.5 보간, D는 6001~7500의 1, T0는 7501~8000의 1이다. `max_iterations`는 8001이다. 이는 설정값이며 실측 결과가 아니다.

설치된 Isaac Lab 소스에서 `randomize_rigid_body_com`, `randomize_actuator_gains`, `push_by_setting_velocity`, `EventTermCfg`의 실제 인자와 호출 방식을 읽고 adapter를 연결했다. Interval 속도 readback은 installed source `isaaclab/assets/articulation/articulation_data.py:532`가 부르는 `get_root_velocities()`로 수정했다. Reset 이벤트는 COM, 관절 이득, DCMotor 한도를 적용한다. COM과 torque 한도는 매 reset마다 저장한 명목값을 먼저 복원해 반복 reset에서 누적되지 않게 한다. Interval 이벤트는 Isaac Lab의 velocity push를 호출한다. 지연 액션은 reset마다 현재 배율 상한을 physics tick 단위로 내림 양자화하고 표본 히스토그램을 기록한다. trainer의 `train_extra.jsonl`에 매 update 이벤트 표본 수, 실제 물리값 요약, 설정 상한, 실현 tick 및 ms 분포, 고정 잡음 설정을 남긴다. 재개 상태에는 DR 설정 해시와 직전 update를 넣어 다음 update 연속성을 검사한다.

관측 잡음은 팀장 정정에 따라 처음부터 끝까지 고정 1×로 기록하며 DR 일정 항목에서 제외했다. 마찰 0.2~1.2와 질량 변화 -1~3 kg는 보존 startup 설정으로 그대로 둔다. 범위가 확인되지 않은 COM, actuator gains, motor strength는 비워 두었다. 밀기 범위와 간격은 D76 결정값을 설정 파일에 기록했다.

## 실행 차단과 검증 한계

지정 범위표 `C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/DR-RANGES-EX40-1030.md`가 현재 없다. 세 가지 미확정 범위를 임의로 채우지 않았고 `runtime_adapter_status`를 `implementation_in_progress`로 유지했다. launch guard는 범위가 채워지고 adapter 검증 상태가 `verified`가 아니면 AppLauncher 생성 전에 거부한다.

Kit smoke 구현은 B0, ramp, D 진입에서 reset 이벤트를 실제 호출하고 interval 이벤트도 실제 EventManager에 호출한 뒤 event sample readback을 확인하도록 했다. 다만 이번에는 Kit/GPU를 띄우지 않았으므로 이벤트 적용, PhysX readback, 첫 reset, interval push, 재개 뒤 동작은 미확인이다. Kit smoke 결과가 없으므로 runtime adapter는 검증 완료 상태가 아니다.

## CPU 검증

- `py_compile` 대상 파일 구문 확인 통과.
- `pytest -q foothold_s2/tests/test_ex40_dr_v8_cpu.py foothold_s2/tests/test_ex40_v7_continue_cpu.py`: 19 passed.
- 답을 아는 입력으로 일정 경계, 1500 update 길이 고정, 지연 tick 내림 양자화, 7.5 ms 상한의 5 ms 최대 표본, 15 ms 상한의 15 ms 최대 표본, COM 및 motor nominal 복원, 고정 잡음 1×, 빈 범위 기동 거부, readback 누락 및 실제 event 표본 0건 반례를 확인했다.
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

## 10/30 COM 대상과 관절 범위 후속

`reset_base_com` 이벤트 설정을 설치 S1 설정과 맞춰 `SceneEntityCfg("robot", body_names="base")`로 한정했다. 기존 `SceneEntityCfg("robot")`는 `body_ids=slice(None)`로 모든 링크에 오프셋을 적용할 수 있었다. 설치된 `SceneEntityCfg.resolve`와 설치 `randomize_rigid_body_com` 함수 본문을 그대로 AST 로드해 CPU 시험에서 실제 호출했고, 반복 reset 뒤에도 base 이외 링크의 COM 값이 명목값으로 유지되는 것을 확인했다.

모터 세기와 actuator gain 설정은 `joint_names=".*"`를 명시한다. 설치된 SceneEntityCfg의 실제 resolve 결과가 모든 관절 ID인지 확인하고, 두 reset adapter가 부분 관절 선택을 거부하도록 했다. COM 및 torque 명목값 반복 reset 시험도 유지했다.

검증: `py_compile` 통과, `pytest -q foothold_s2/tests/test_ex40_dr_v8_cpu.py foothold_s2/tests/test_ex40_v7_continue_cpu.py` 결과 19 passed. COM 시험은 설치 함수와 설치 설정 클래스를 실행했으며, PhysX view는 CPU 시험용 인터페이스 대역이다. Kit/GPU 실측은 하지 않았으므로 실제 시뮬레이터 적용은 미확인이고 EX-40 launch guard 상태를 바꾸지 않는다.


## D76 밀기 설정

D76 지시에 따라 `ex40.yaml`의 수평 속도 축 `x`, `y` 범위를 각각 -1.0~1.0 m/s, interval 간격을 10~15 s로 기록했다. 수직 및 각속도 축은 0으로 고정했다. 기존 일정에서 B3c 마지막 배율 0.5일 때 수평 범위는 각 -0.5~0.5 m/s이고 D 단계 배율 1일 때 -1.0~1.0 m/s가 된다. CPU 시험은 설정값, 전체 범위 구조, 두 배율의 기대값을 확인했다.

앞서 보고한 새 막음 1은 COM 설정을 `body_names="base"`로 제한하고 실제 설치 함수 호출 시험을 추가해 닫았다. COM 이외의 세 범위는 여전히 미기입이므로 `runtime_adapter_status`는 `implementation_in_progress`이고 launch guard는 열지 않았다. 이번 범위는 CPU 시험만 수행했으며 Kit/GPU 효과는 미확인이다.
