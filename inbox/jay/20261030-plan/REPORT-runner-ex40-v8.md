> 분류: 운영 · 평가 실행
> 작성: 오흥재 (runner 반영) · 2026-10-31
> 근거: WORKLIST D72~D76 · analyst DR-RANGES-EX40-1030 §1.2 · Isaac Lab 설치 소스
> 요지: EX-40 v8 DR 연결과 D72~D76 일정을 기록하고 smoke와 본 학습의 기동 관문을 분리한다
> 상태: CPU CLI와 셸 DRY 확인 · Kit/GPU 미실행 · 본 학습 기동 차단

# EX-40 v8 DR 연결 보고

## 결과

기존 v8 변경은 `C:/mai/wt/foothold-lab/runner-ex40-v8`에서 했다. 현재 D72~D76 일정은 B0 m0~1500, B1 m1501~3000, B2 m3001~4500, B3a m4501~5000, B3b m5001~5500, B3c m5501~6000, D m6001~7500, T0 m7501~8000이다. D 길이는 1500 update, 마지막 update는 m8000, `max_iterations`는 8001이다. 이는 설정값이며 실측 결과가 아니다. 과거 D73 초안의 D 1500 또는 3000 선택 대기는 D74에서 1500으로 결정되었다.

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

작업 기준 고정 HEAD는 `3010ba45`였고, 구현 변경은 `41c73dd2`에 기록했다. 이번 변경 파일은 `foothold_s2/curriculum/ex40.yaml`, `foothold_s2/curriculum/ex40_dr.py`, `foothold_s2/scripts/train_sol23f_common.py`, `foothold_s2/tests/test_ex40_dr_v8_cpu.py`, 이 보고서다.

Analyst `DR-RANGES-EX40-1030.md` §1.2에 따라 `ex40.yaml`의 세 범위를 채웠다. base COM은 x/y/z 각각 ±0.05 m, stiffness와 damping은 각각 [0.9, 1.1], motor strength는 [0.9, 1.1]이다. 관측 잡음은 고정 1×, D76 밀기는 world xy 각각 ±1.0 m/s와 10~15 s 간격이며 z 및 회전축은 0이다. D75의 null 표기는 반영하지 않았다.

현재 DR 일정은 update 1500까지 배율 0, 1501~6000에서 0~0.5, 6001~7500에서 1.0, 7501~8000에서 1.0이다. B3의 세 하위 단계는 D72 경계 4501, 5001, 5501이며, D74가 D 길이 1500과 T0 m7501~8000을 확정했다. 재개 계약의 CPU 시험은 저장된 DR 설정 해시와 직전 update를 검사하고 다음 update에서 schedule 배율을 복원한다. 이는 schedule 연속성 검사이며 실제 Kit에서 물리 표본이 bitwise 동일하게 재개되는 증거는 아니다.

smoke 경로만 `require_smoke_ready`를 사용한다. 이 함수는 완전한 범위와 정확한 D76 push interval을 검사하지만 adapter를 `verified`로 올리지 않는다. 본 학습과 resume은 `require_launchable` 관문에 계속 막힌다. 이 시점에는 공식 `ex40_launch`가 smoke에도 `require_launchable`을 호출해 막았으며, 아래 학습기 직접 호출 형식은 공식 런처 smoke의 성공 증거가 아니었다. `<A|B>`와 경로 및 종료시각은 담당자가 정해야 했다.

```text
python foothold_s2/scripts/train_sol23f_common.py --task FootholdS2-Go2-S2-SB-v0 --variant SB --command_mode basic_gait --clock_scatter off --p_map_off 0.1 --seed 42 --num_envs 3072 --max_iterations 18 --curriculum foothold_s2/curriculum/ex40.yaml --curriculum-arm <A|B> --curriculum-kit-smoke --basic-stage smoke --basic-new-share 0.30 --basic-log-root <absolute-smoke-log-dir> --curriculum-score-dir <absolute-score-dir> --end-by <ISO8601-with-timezone> --max-wall-s 86400 --device <approved-device>
```

2026-10-31 후속 CPU 검증: `py_compile` 대상 파일 통과, 아래 통합 pytest 73 passed. 세 범위의 실제 설정값, D76 경계, 고정 잡음, smoke-only 통과 및 main launch 거부, smoke 18 update 초과 거부, RuntimeReadback의 config SHA/next-update 재개 검사를 확인했다. 실제 설치 Isaac Lab의 event 함수 및 `SceneEntityCfg` 소스는 기존 CPU 시험에서 호출/API 대조를 유지했다. Kit/GPU 실측과 runtime adapter 검증은 미실행이다.

```text
pytest -q foothold_s2/tests/test_ex40_dr_v8_cpu.py foothold_s2/tests/test_ex40_v7_continue_cpu.py foothold_s2/tests/test_ex40_scorer_cpu.py foothold_s2/tests/test_ex40_stage_publish_cpu.py foothold_s2/tests/test_axis_v2_cells.py foothold_s2/tests/test_axis_v2_run_cpu.py foothold_s2/tests/test_ex40_kit_argv_cpu.py foothold_s2/tests/test_w55_continuous_cpu.py
```

## 10/31 후속: 공식 launcher smoke 경로와 문서 정정

후속 기준은 `303659571b2436ee3dd4db870890202435468ff5`이고 작업은 별도 `runner-ex40-b12-smoke` worktree에서 했다. `ex40_launch.py`의 scratch 경로는 이제 `--smoke`일 때만 `require_smoke_ready`를 호출하고, 일반 scratch는 `require_launchable`을 호출한다. resume 경로는 옵션과 무관하게 `require_launchable`을 먼저 통과해야 한다. 따라서 adapter 미검증 상태에서 bounded smoke 계획을 출력할 수 있지만, main과 resume는 계속 거절된다.

공식 CLI 양성 사례는 `--smoke`에서 rc 0과 `CPU_PREPARED_NOT_LAUNCHED`, `max_iterations=18`, `kit_verified=false`, `training_started=false` 영수증을 냈다. main 및 존재하지 않는 resume spec 입력은 각각 rc 2, `runtime adapter is not verified`로 거절되어 resume 파일을 열기 전에 종료했다. 셸 `run_ex40.sh ... smoke` DRY도 `prestart_pass`, `training_started=false`, `DRY: training not started`로 끝났다. 따라서 CLI/셸 준비 경로만 확인됐으며 Kit, GPU, 이벤트 실현 및 PhysX readback은 미확인이다.

D72~D76에 맞춘 현재 단계 끝은 m1500, 3000, 4500, 5000, 5500, 6000, 7500, 8000이고, D 단계는 1500 update이다. 이전 D73 초안의 1500 또는 3000 선택 문구와 6000 상한, D72 전의 단계 구성은 과거 결정 이력으로 남기고 현재 설정으로 읽히지 않도록 이 단락에서 정정한다. `promotion: fixed, shadow_gate: true`는 D72의 회차 전환과 그림자 성과 기록을 뜻한다. 지형은 현재 설정 `fixed_l02`로서 L0~L2 자동 승급을 끄지만, D72~D76에는 지형 정책 최종 결정이 없어 결정 대기는 유지된다. 실제 레벨 배치와 승급 억제는 Kit에서 미확인이다.

이번 후속 변경은 공식 런처 분기, CLI 회귀 시험, 이 보고서와 실행 카드다. 신규 smoke/main/resume CLI 사례 3개를 포함한 지정 CPU 묶음은 24 passed였다. 기존 EX-40 CPU 계약 및 통합 시험 전체는 이 후속에서 다시 실행하지 않았다.
