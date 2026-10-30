> 분류: 운영 · 평가 실행
> 작성: 오흥재 (runner 반영) · 2026-10-30
> 근거: WORKLIST D73 · D74 · lead EX-40 v8 지시와 22:0x 잡음 정정 · Isaac Lab 설치 소스
> 요지: EX-40 v8 DR 범위와 runtime 연결을 기록하고 Kit 미검증 상태 및 기동 관문을 보존한다
> 상태: 분석 범위 반영 · CPU 시험 통과 · Kit/GPU 미실행 · 본 학습 기동 차단

# EX-40 v8 DR 연결 보고

## 결과

전용 worktree `C:/mai/wt/foothold-lab/runner-ex40-v8`에서 작업했다. D74 일정은 D 길이 1500 update로 고정했다. B0은 배율 0, B1~B3c는 update 1501~6000의 0~0.5 보간, D는 6001~7500의 1, T0는 7501~8000의 1이다. `max_iterations`는 8001이다. 이는 설정값이며 실측 결과가 아니다.

설치된 Isaac Lab 소스에서 `randomize_rigid_body_com`, `randomize_actuator_gains`, `push_by_setting_velocity`, `EventTermCfg`의 실제 인자와 호출 방식을 읽고 adapter를 연결했다. Interval 속도 readback은 installed source `isaaclab/assets/articulation/articulation_data.py:532`가 부르는 `get_root_velocities()`로 수정했다. Reset 이벤트는 COM, 관절 이득, DCMotor 한도를 적용한다. COM과 torque 한도는 매 reset마다 저장한 명목값을 먼저 복원해 반복 reset에서 누적되지 않게 한다. Interval 이벤트는 Isaac Lab의 velocity push를 호출한다. 지연 액션은 reset마다 현재 배율 상한을 physics tick 단위로 내림 양자화하고 표본 히스토그램을 기록한다. trainer의 `train_extra.jsonl`에 매 update 이벤트 표본 수, 실제 물리값 요약, 설정 상한, 실현 tick 및 ms 분포, 고정 잡음 설정을 남긴다. 재개 상태에는 DR 설정 해시와 직전 update를 넣어 다음 update 연속성을 검사한다.

관측 잡음은 팀장 정정에 따라 처음부터 끝까지 고정 1×로 기록하며 DR 일정 항목에서 제외했다. 마찰 0.2~1.2와 질량 변화 -1~3 kg는 보존 startup 설정으로 그대로 둔다. COM, actuator gains, motor strength 범위는 10/31 analyst 보고서 §1.2에 따라 설정했다. 밀기 범위와 간격은 D76 결정값이다.

## 실행 차단과 검증 한계

지정 범위표 `C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/DR-RANGES-EX40-1030.md`는 확인했다. §1.2의 base COM xyz ±0.05 m, stiffness/damping 배율 [0.9, 1.1], motor strength [0.9, 1.1]를 `ex40.yaml`에 반영했다. `runtime_adapter_status`는 `implementation_in_progress`로 유지했다. 일반 본 학습 경로는 범위가 완전해도 adapter가 `verified`가 아니면 AppLauncher 전에 거부한다.

별도 `--curriculum-kit-smoke` 경로는 완전한 범위표와 D76 10~15 s 간격을 요구하고, `validate_continuous_launch`가 18 update, smoke 출력 경로, 비재개 실행을 검사한다. 이 경로만 adapter 미검증 상태에서 짧은 smoke 진입을 허용하며, 본 학습의 `require_launchable`은 계속 거부한다. 이번에는 Kit/GPU를 띄우지 않았으므로 이벤트 적용, PhysX readback, 첫 reset, interval push, 재개 뒤 실제 동작은 미확인이고 `verified`로 바꾸지 않았다.

## CPU 검증

- `py_compile` 대상 파일 구문 확인 통과.
- `pytest -q foothold_s2/tests/test_ex40_dr_v8_cpu.py foothold_s2/tests/test_ex40_v7_continue_cpu.py`: 아래 10/31 후속 검증 결과 참조.
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

다음에는 별도 승인된 Kit smoke에서 reset·push 표본과 PhysX readback을 확인해야 한다. 그 전까지 본 학습은 차단되며 runtime adapter는 미검증이다.

## 10/30 COM 대상과 관절 범위 후속

`reset_base_com` 이벤트 설정을 설치 S1 설정과 맞춰 `SceneEntityCfg("robot", body_names="base")`로 한정했다. 기존 `SceneEntityCfg("robot")`는 `body_ids=slice(None)`로 모든 링크에 오프셋을 적용할 수 있었다. 설치된 `SceneEntityCfg.resolve`와 설치 `randomize_rigid_body_com` 함수 본문을 그대로 AST 로드해 CPU 시험에서 실제 호출했고, 반복 reset 뒤에도 base 이외 링크의 COM 값이 명목값으로 유지되는 것을 확인했다.

모터 세기와 actuator gain 설정은 `joint_names=".*"`를 명시한다. 설치된 SceneEntityCfg의 실제 resolve 결과가 모든 관절 ID인지 확인하고, 두 reset adapter가 부분 관절 선택을 거부하도록 했다. COM 및 torque 명목값 반복 reset 시험도 유지했다.

검증: `py_compile` 통과, `pytest -q foothold_s2/tests/test_ex40_dr_v8_cpu.py foothold_s2/tests/test_ex40_v7_continue_cpu.py` 결과 19 passed. COM 시험은 설치 함수와 설치 설정 클래스를 실행했으며, PhysX view는 CPU 시험용 인터페이스 대역이다. Kit/GPU 실측은 하지 않았으므로 실제 시뮬레이터 적용은 미확인이고 EX-40 launch guard 상태를 바꾸지 않는다.


## D76 밀기 설정

D76 지시에 따라 `ex40.yaml`의 수평 속도 축 `x`, `y` 범위를 각각 -1.0~1.0 m/s, interval 간격을 10~15 s로 기록했다. 수직 및 각속도 축은 0으로 고정했다. 기존 일정에서 B3c 마지막 배율 0.5일 때 수평 범위는 각 -0.5~0.5 m/s이고 D 단계 배율 1일 때 -1.0~1.0 m/s가 된다. CPU 시험은 설정값, 전체 범위 구조, 두 배율의 기대값을 확인했다.

앞서 보고한 새 막음 1은 COM 설정을 `body_names="base"`로 제한하고 실제 설치 함수 호출 시험을 추가해 닫았다. 이 시점의 미기입 범위 상태는 아래 10/31 인계에서 갱신했다. Kit/GPU 효과는 미확인이다.

## B10 고정 사본 통합

고정 사본 `C:/mai/wt/foothold-lab/runner-ex40-b10`에서 v7 기반과 v8 구현을 포함한 `bc926bb0` 위에 score v8 `1910d2fb` 및 단계 Git 보고서 `9c911b87`을 병합했다. 병합 커밋은 `09d43399`이며 충돌 없이 만들어졌다. 통합 후 D76 수평 밀기 범위와 base 전용 COM 설정이 유지되는 것을 확인했다.

통합 확인 중 W55 Kit smoke CPU fixture가 v8의 `ex40_dr` readback 및 단계 probe 계약을 채우지 않아 실패했다. 시험 fixture에 18개 update 행과 B0/ramp/D probe receipt를 추가해 입력 계약을 맞췄다. 당시 CPU 통합 시험은 71 passed였다. 실제 Kit/GPU 실행은 하지 않았고 본 학습 launch guard는 계속 닫혀 있다.

## 10/31 analyst 범위 인계와 smoke 관문

Analyst `DR-RANGES-EX40-1030.md` §1.2에 따라 `ex40.yaml`의 세 범위를 채웠다. base COM은 x/y/z 각각 ±0.05 m, stiffness와 damping은 각각 [0.9, 1.1], motor strength는 [0.9, 1.1]이다. 관측 잡음은 고정 1×, D76 밀기는 world xy 각각 ±1.0 m/s와 10~15 s 간격이며 z 및 회전축은 0이다. D75의 null 표기는 반영하지 않았다.

DR 일정 경계는 기존대로 update 1500까지 배율 0, 1501~6000에서 0~0.5, 6001~7500에서 1.0, 7501~8000에서 1.0이다. 재개 계약의 CPU 시험은 저장된 DR 설정 해시와 직전 update를 검사하고 다음 update에서 schedule 배율을 복원한다. 이는 schedule 연속성 검사이며 실제 Kit에서 물리 표본이 bitwise 동일하게 재개되는 증거는 아니다.

smoke 경로만 `require_smoke_ready`를 사용한다. 이 함수는 완전한 범위와 정확한 D76 push interval을 검사하지만 adapter를 `verified`로 올리지 않는다. 본 학습은 `require_launchable` 관문에 계속 막히고, smoke 실행도 하지 않았다. 준비용 명령 형식은 다음과 같으며 실제 기동 명령이나 승인이 아니다. `<A|B>`와 경로 및 종료시각은 담당자가 정해야 한다.

```text
python foothold_s2/scripts/train_sol23f_common.py --task FootholdS2-Go2-S2-SB-v0 --variant SB --command_mode basic_gait --clock_scatter off --p_map_off 0.1 --seed 42 --num_envs 3072 --max_iterations 18 --curriculum foothold_s2/curriculum/ex40.yaml --curriculum-arm <A|B> --curriculum-kit-smoke --basic-stage smoke --basic-new-share 0.30 --basic-log-root <absolute-smoke-log-dir> --curriculum-score-dir <absolute-score-dir> --end-by <ISO8601-with-timezone> --max-wall-s 86400 --device <approved-device>
```

2026-10-31 후속 CPU 검증: `py_compile` 대상 파일 통과, 통합 pytest 73 passed. 세 범위의 실제 설정값, D76 경계, 고정 잡음, smoke-only 통과 및 main launch 거부, smoke 18 update 초과 거부, RuntimeReadback의 config SHA/next-update 재개 검사를 확인했다. 실제 설치 Isaac Lab의 event 함수 및 `SceneEntityCfg` 소스는 기존 CPU 시험에서 호출/API 대조를 유지했다. Kit/GPU 실측과 runtime adapter 검증은 미실행이다.
