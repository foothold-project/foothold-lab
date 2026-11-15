# S2 step10 배관 이름 고침과 A3.3 CPU 보고
> 분류: A/정책학습
> 작성: Codex · 2026-10-16
> 근거: step10 작업서 · RobotLab 및 Isaac Lab 소스 AST · 10/16 4차 수집과 첫 배관 원자료 · CPU 시험 로그
> 요지: 학습 배관의 접촉 종료 항을 task별로 고르고, 0단계 사본을 RobotLab Go2 자산과 설정에 연결했다.
> 상태: CPU 검증 완료 · GPU 및 Isaac 미기동

## 실제 실행에서 확인한 문제

첫 배관 실행 `plumbing_A_first_20261016_1417/out/result.json`의 `stop_reason`은 `PlumbingHold: training_cfg_physics_unknown`, 실행 update와 vector step은 모두 0이다. 학습 task `RobotLab-Go2-v0`의 `TerminationsCfg`에는 `illegal_contact`가 있고 `base_contact`는 없다. 기존 배관은 `s2_plumbing.py`의 `assert_training_cfg`와 `s2_train_entry_17v.py`의 진단 설정 비교에서 후자를 읽었다. 기존 가짜 cfg가 `base_contact`를 직접 만들어 이 불일치를 가렸다. 이후 실제 Kit 통과는 미확인이다.

4차 0단계는 `Isaac-Velocity-Rough-Unitree-Go2-v0`에서 256 step을 모았다. B 학습은 `RobotLab-Go2-v0`이므로 그 0단계 결과를 B의 같은 환경 증명으로 쓰지 않는다. 4차는 지도 edge 불일치 0, hit mask 불일치 0, interior 높이 최대 오차 4.58e-6 m였으나 최종 판정은 HOLD였다.
`final_cfg.json`을 다시 파싱해 기본 Go2의 Isaac S3 `go2.usd`, 종료 항 `base_contact`와 `time_out`, 보상 11항을 확인했다.
검사기의 세 이유 `mesh_evidence_content`, `fixed_pose_evidence`, `case_assignment` 중 마지막은 `mesh_collision_verified=false`와 `fixed_pose_verified=false`가 합쳐진 결과다. `terrain_assignment_verified=true`였다.

## 배관 게이트와 실제 소스 대조

`s2_step10/s2_task_contract.py` 한 곳에 `RobotLab-Go2-v0 → illegal_contact`, `Isaac-Velocity-Rough-Unitree-Go2-v0 → base_contact`를 두었다. 미등록 task는 `ValueError(unregistered_contact_termination_task)`로 거절한다. `assert_training_cfg`, entry의 진단 설정 비교, live 결과의 `final_cfg` 검사가 이 표를 쓴다. `s2_train_contract.py`의 닫힌 코드 묶음에도 새 모듈을 넣었다. Step9 short 요청 JSON A와 B는 SHA256까지 동일하다. short를 새 코드로 실행한다면 봉인 manifest는 새 코드 해시로 다시 만들어야 한다.

아래 접근 경로는 `test_s2_step10_source.py`가 B의 지정 여섯 파일을 AST로 파싱해 출력한 것이다. `env_cfg.py`와 `assets/unitree.py`도 import 없이 AST로 읽었다. `dictcfg`는 직렬화된 cfg의 키, `tuplecfg`는 entry의 비교 경로다.

| 파일 | 코드에서 추출한 cfg 및 scene 접근 | 소스 대조 |
|---|---|---|
| `s2_train_entry_17v.py` | `scene['height_scanner']`, `scene['robot']`, `tuplecfg.events.reset_base`, `tuplecfg.scene.robot.init_state`, `tuplecfg.scene.robot.spawn.rigid_props`, `tuplecfg.terminations.illegal_contact` | 일치 |
| `s2_plumbing.py` | `cfg.scene.robot.spawn.rigid_props.disable_gravity`, `cfg.scene.robot.spawn.fix_base`, `cfg.terminations.illegal_contact`; 직렬화 cfg에서도 같은 `spawn` 물리 필드와 `terminations.illegal_contact` | 일치 |
| `s2_env_config_17v.py` | `cfg.curriculum.terrain_levels`, `cfg.events.reset_base.params`, `cfg.scene.num_envs`, `cfg.scene.terrain.max_init_terrain_level`, `.terrain_generator` | 일치 |
| `s2_env_adapter_17v.py` | scanner `offset.pos`, `pattern_cfg.direction`, `.ordering`, `.resolution`, `.size`, `ray_alignment` | `height_scanner` 생성 인자와 `GridPatternCfg` 기본 필드에 일치 |
| `s2_runner_17v.py` | 환경 cfg 및 scene 직접 접근 없음. `cfg.rollout_steps`, `gamma`, `lam`은 독립 runner 설정 | 해당 없음 |
| `s2_sensor_tracker_17v.py` | 환경 cfg 및 scene 직접 접근 없음 | 해당 없음 |

`test_s2_step10_mutants.py`는 entry 비교 경로 또는 배관 게이트 중 하나를 `base_contact`로 되돌려 각각 지정 첫 FAIL `legacy_base_contact`로 잡았다. 정상 소스 검사를 먼저 통과시킨 뒤 각 변이를 평가했다.

## A3.3 사본

`s2_step4a33/`은 A3.2 루트의 49개 작업 파일을 복사해 시작했다. `BASE_TASK`를 `RobotLab-Go2-v0`으로 바꾸고 `robot_lab.tasks` 등록을 사용한다. 종료 항은 `illegal_contact`이고, 자산은 현지 URDF `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf`의 `asset_path`다. 계약은 다른 자산 경로와 `expect_conversions`가 `1`이 아닌 요청을 거절한다. 감독기는 `isolate_state.json`에서 기대값 `1`, 실제 변환 `1`, 빈 blocked 및 warnings, USD 루트 일치를 확인하고 영수증에 남긴다. 승인 JSON은 만들지 않았다.
새 실행 요청과 GPU 배정, 마감, 승인 값은 만들지 않았다. lead는 새 요청에 URDF 경로와 `expect_conversions=1`을 넣어 별도로 봉인해야 한다. 캐시 때문에 실제 변환이 0회라면 이 계약은 HOLD가 되며, 실제 횟수는 Kit 전에는 미확인이다.

RobotLab 명령 설정은 `Go2RLGymCommandCfg` 소스 필드에 맞춰 0 속도와 재표본 및 curriculum 비활성화로 옮겼다. RobotLab의 `randomize_*` 이벤트를 진단 가지에서 끈다. 0단계의 8개 장면, 지도 계산, 오라클, 마스크 의미, 2 mm 및 5 mm 허용치, 256 step은 유지했다. 지도, 어댑터, runner, 센서 tracker, 정책, PPO, 장면 답 JSON의 7개 파일은 A3.2와 SHA256이 같다.
이 사본은 B와 등록 task 및 URDF 자산을 공유하지만 진단 가지에서 중력과 접촉 종료를 끈다. 합격해도 센서에서 지도로 이어지는 연결의 근거이며 학습 물리 전체의 동등성 근거는 아니다.

### 두 환경의 `height_scanner` 소스 대조

기본 Go2는 `IsaacLab/source/isaaclab_tasks/.../velocity/velocity_env_cfg.py:66~73`와 `config/go2/rough_env_cfg.py`, RobotLab은 `tasks/go2/env_cfg.py:65~72`를 읽었다. `update_period`는 각각의 `__post_init__`에서 정한다. `max_distance`는 두 환경 모두 생략해 같은 `RayCasterCfg` 기본값을 쓴다.

| 항목 | 기본 Go2 | RobotLab Go2 | 지도 영향 |
|---|---|---|---|
| attach prim | `{ENV_REGEX_NS}/Robot/base` | 동일 | 설정상 없음 |
| offset | `(0,0,20) m` | 동일 | 설정상 없음 |
| ray_alignment | `yaw` | 동일 | 설정상 없음 |
| pattern | Grid 0.1 m, `[1.6,1.0] m`, `xy` 순서, `(0,0,-1)` 방향, 187 rays | 동일 | 설정상 없음 |
| mesh_prim_paths | `/World/ground` | 동일 | 설정상 없음 |
| update_period | `4 × 0.005 = 0.02 s` | 동일 | 설정상 없음 |
| max_distance | 생략, 공통 기본 `1e6 m` | 동일 | 설정상 없음 |
| debug_vis | `False` | 동일 | 설정상 없음 |

센서 설정은 같지만 로봇 자산, 접촉과 명령 동작이 달라 실제 hit 및 지도 값의 일치까지 보장하지 않는다. A3.3을 해당 환경에서 새로 실행해 판단해야 한다.

## 4차 HOLD 원인 조사

원자료 `capture.npz` SHA256 `5f170abc6b47a54f7a4497f623358f0819581c0b1797c477931c508e2df881a9`, 원래 실행 폴더의 `physx_queries.npz` SHA256 `39ea5e3aaa99cebeb7e66ada0a80088c9f2e6142f0f0e713857ad6d185d27b72`를 읽기만 했다. 재현 숫자는 `s2_step10/attempt4_analysis.json`에 남겼다.

PhysX는 69 표본 step × 8 env × 187 ray = 103,224개 모두 status 0 miss를 냈고 경로도 비었다. 같은 표본에서 RayCaster의 유한 hit은 101,844개였다. 질의는 물리 `step_zero` 직후 기록된 world ray 시작점과 방향으로 수행됐다. 시작 z는 20.400~20.629 m, 방향은 `(0,0,-1)`에 길이 1, 유한 hit의 예상 거리는 20.200~22.600 m, PhysX `max_dist`는 200 m다. +20 m는 이미 RayCaster 시작점에 포함돼 있으며 프로브에서 다시 더하지 않는다. 지형의 `collision_group=-1`, USD mesh의 CollisionAPI와 collision enabled는 관찰됐지만 장면 질의에 실제 등록됐는지는 미확인이다.

가능 원인은 순서대로 (1) PhysX scene query가 `/World/ground/terrain/mesh` collider를 보지 못하는 설정 또는 질의 장면 선택 차이, (2) `raycast_closest` 호출 형식 또는 질의 인터페이스 차이, (3) collision group과 query 필터 상호작용이다. 세 가지 모두 현재 자료만으로 확정할 수 없다. 거리 단위 오류와 +20 m 중복은 위 수치와 코드에서 지지되지 않는다. 의미를 바꾸는 코드는 고치지 않았다. 제안하는 단회 GPU 판별은 학습 없이 8 env × 16 step, 알려진 지면 3광선을 step 전후와 `carb.Float3` 인자 형식으로 질의해 반환 원형, scene path, 필터를 기록하는 것이다. 이 작은 판별 뒤 정식 256 step A3.3은 별도 승인과 실행이 필요하다.

env 6(`stones_0`)의 첫 16 step `root_quat_w` 초과는 wxyz 중 x 성분이다. step 0의 x는 -0.000245, step 15는 -0.005084, 차이 0.004839다. 허용치 0.002를 처음 넘는 곳은 step 7이며 그 뒤 계속 커진다. 같은 기간 root 위치 최대 편차는 0.001693 m, 종료와 reset은 없고 광선 높이는 지면과 0.2 m 돌 윗면을 함께 본다. 로봇 중심은 장면 원점 근처이고 돌은 x 0.20~0.42 m 및 -0.48~-0.31 m 구간에 있다. 발 위치와 접촉 힘을 기록하지 않아 돌 가장자리 접촉 여부는 미확인이다. 후속 단회 판별에 첫 16 step의 발 접촉 힘과 root 각속도를 함께 기록하되, 0.002 허용치는 바꾸지 않는다.

## 시험, 변경 파일, 미확인

step9 대비 `s2_step10/` 변경은 `s2_plumbing.py`, `s2_train_entry_17v.py`, `s2_train_contract.py`, 새 `s2_task_contract.py`, `test_s2_step6_contract.py`, `test_s2_step7.py`, 새 `test_s2_step10_source.py`, `test_s2_step10_mutants.py`, 격리 시험기 `run_s2_step10_ast_clean.py`, `run_a33_isolated_clean.py`, 원자료 읽기 도구와 결과 `analyze_attempt4.py`, `attempt4_analysis.json`이다. A3.2 대비 `s2_step4a33/` 변경은 `s2_env_config_17v.py`, `s2_connect_diag_17v.py`, `s2_stage0_contract_a2.py`, `s2_zero_supervisor.py`, `run_all_s2_step4a3.py`, `test_s2_a32.py`, `test_s2_stage0_contract_a2.py`, 새 `test_s2_a33.py`, 기존 변이 하네스 5개, 새 해시 목록이다. 부모 원본과 step9는 고치지 않았다.

CPU 경로는 `CUDA_VISIBLE_DEVICES=-1`와 `isaac311-moects/python.exe -I -B`로 실행했다. 전체 회귀 및 변이의 최종 수치는 다음과 같다.

- step10 초기 깨끗한 복사본 시험은 새 `s2_task_contract.py`를 코드 묶음 `CODE`에 누락해 `test_s2_step5_clean_import.py`에서 첫 실패했다. 코드를 묶음에 추가했다.
- 새 AST 시험 초안은 `asset_path`를 `UnitreeUrdfFileCfg`의 직접 선언 필드로 잘못 보아 실패했다. 실제 `GO2_CFG_UNITREE`의 URDF 생성 인자로 대조하도록 고쳤다.
- A3.3 시험 초안의 가짜 step 폭이 고정 장면 답과 달라 실패했고, 답 JSON의 폭을 사용하도록 고쳤다. 계약 시험의 과거 `any` 기대값도 `1`로 고쳤다.
- B 깨끗한 복사본 전체: `s2_step10/evidence_s2_step9/step10_final/summary.json`, 39/39 시험, 정상 `PASS` 331개, 지정 첫 FAIL 일치 `CAUGHT` 70/70. 모두 CPU, `-I -B`다.
- 마지막 AST 감사 파일 바이트의 별도 깨끗한 복사본: `s2_step10/evidence_s2_step10_ast/final_ast1/summary.json`, 정상 1 PASS, 두 이름 회귀 변이 2/2 CAUGHT, 각 `first_FAIL=want`.
- A3.3 깨끗한 복사본 전체 회귀: `s2_step10/evidence_s2_step10/a33_isolated_final/summary.json`과 `suite/summary.json`, 23/23 작업 완료. 정상 시험 17개에서 208 PASS, 변이 50/50 CAUGHT, 깨끗한 복사본 모듈 22개 import, A3.3 해시 50/50 일치. 모든 자식 시험도 `-I -B`로 실행했다.

미확인: 실제 RobotLab Kit 기동, 실제 URDF 1회 변환, A3.3 256 step 판정, PhysX 전부 miss의 단일 원인, env 6의 발 접촉 원인. GPU와 Isaac은 이 세션에서 실행하지 않았다. `_eval`과 부모 소스는 읽기만 했다.
