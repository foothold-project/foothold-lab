> 분류: A/정책학습 · Codex Worker 작업서 (sol) · 배관 게이트 이름 불일치 고침과 0단계를 학습 환경(RobotLab-Go2-v0)으로 옮기기 (A3.3)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 14:23
> 근거: 10/16 14:15 4차 수집과 14:17 첫 배관 실행 결과 (증거 `night-tools-20261013/s2_stage0_first_collection/attempt4_20261016_1415/` · `plumbing_A_first_20261016_1417/` · 분석 `attempt4_analysis_output.txt`) · ASTRA 17af 2절(0단계 자료가 B 학습 경로에 적용돼야 한다)
> 요지: 처음 실제 Kit 에서 돌린 두 실행에서 설정 불일치 둘이 나왔다. (1) 배관 게이트가 `terminations.base_contact` 를 읽는데 학습 환경(RobotLab-Go2-v0, E1)의 이름은 `illegal_contact` 이다 (2) 0단계 수집(A3 · A3.1 · A3.2)은 `Isaac-Velocity-Rough-Unitree-Go2-v0`(Isaac Lab 기본 Go2, S3 자산) 로 돌았고 B 는 `RobotLab-Go2-v0`(URDF Go2, 변환 1회) 로 학습한다. 같은 환경에서 다시 증명해야 한다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다 · step9 의 연장 없는 단회 short 와 foot reward 작업서는 이 일 뒤)

# sol 작업서: 배관 이름 불일치 고침 + A3.3

## 0. 지킬 것

step9 와 같다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 사본 `codexE/s2_step10/` (step9 를 복사해 시작, step9 와 저장소는 고치지 않는다). 정상 먼저, 변이는 지정 첫 FAIL. em dash 금지. 첫 실패도 보고서에. A3.2 의 지도 모듈(5/6) 바이트는 바꾸지 않는다(바꿔야 하면 이유와 줄을 먼저 보고하고 멈춘다).

## 1. 확인된 사실 (lead 가 원자료에서 읽었다)

- 배관 14:17:42~14:17:59, 17초: `result.json` `stop_reason = PlumbingHold: training_cfg_physics_unknown`, executed_updates 0, vector_steps 0, plumbing_checks HOLD. `s2_plumbing.py:25~30` `assert_training_cfg` 가 `cfg.terminations.base_contact` 를 읽다 AttributeError 를 냈고, `s2_train_entry_17v.py:153` 의 경로 목록도 같은 이름을 쓴다.
- 실제 학습 환경 `C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/tasks/go2/env_cfg.py`: `TerminationsCfg` = [`time_out`, `illegal_contact`], `EventCfg` 에 `reset_base` 있음, `Go2SceneCfg` = [terrain, robot, height_scanner, height_scanner_small, contact_forces, sky_light]. E1 `params/env.yaml` terminations 도 `time_out`, `illegal_contact`. `base_contact` 는 이 소스 어디에도 없다.
- 4차는 `s2_step4a3/s2_env_config_17v.py:13` `BASE_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"` 이고 `final_cfg.json` 의 자산은 Isaac Lab 기본 Go2(S3 URL), 종료 `base_contact`, 보상 11항이다. `s2_step8/s2_env_config_17v.py` 는 `RobotLab-Go2-v0`. 단, step8 의 `s2_connect_diag_17v.py` 는 A3.2 의 고침(중력 · 종료 · 오라클 점검)이 반영된 판이 아니다.
- 4차 지도 연결 값은 정답과 맞았다(기본 Go2 환경에서): edge 불일치 0 · hit mask 불일치 0 · 높이 최대 오차 4.6e-6 m. HOLD 이유 3개의 실제 원인은 둘이다: (a) `mesh_evidence.json` 의 PhysX 질의가 **모든 표본에서 `{'hit': False}`** 를 반환(`physx_queries.npz`; ground env 0 에서 12,903 중 12,903 hit_miss_mismatch) → `kind: unverified_collision_mesh` (b) env 6(stones_0)의 첫 16 step `root_quat_w` 편차 0.00484 > 허용 0.002 (위치 편차 0.0017 은 허용 안).

## 2. 할 일

**2-1. 배관 게이트 (작게, 먼저)**
- 종료 항 이름을 하드코딩하지 말고 `BASE_TASK → 접촉 종료 항 이름` 표를 한 곳에 둔다: `RobotLab-Go2-v0` → `illegal_contact`, `Isaac-Velocity-Rough-Unitree-Go2-v0` → `base_contact`. 표에 없는 task 는 닫힌 거절. `assert_training_cfg` 와 `entry:153` 경로 목록이 같은 표를 쓴다.
- **실제 소스 대조 시험(필수):** `env_cfg.py` 와 `assets/unitree.py` 를 `ast` 로 읽어(isaaclab import 없이) B 번들 코드(`s2_train_entry_17v.py` · `s2_plumbing.py` · `s2_env_config_17v.py` · `s2_env_adapter_17v.py` · `s2_runner_17v.py` · `s2_sensor_tracker_17v.py`)가 cfg / scene 에서 접근하는 모든 이름이 실제 클래스에 있는지 확인한다. 접근 이름 목록은 코드에서 뽑아 보고서에 표로 적는다(손으로 나열하지 않는다). 변이: 이름 하나를 `base_contact` 로 되돌리면 이 시험이 지정 첫 FAIL 로 잡혀야 한다. 가짜 cfg 로만 도는 기존 시험이 이 불일치를 못 잡았다는 사실을 보고서에 적는다.

**2-2. A3.3: 0단계를 RobotLab-Go2-v0 로**
- A3.2(49개 파일)를 복사해 `BASE_TASK` 를 `RobotLab-Go2-v0` 로 바꾸고, 진단 가지의 `base_contact` · 자산 · 변환 수(예상 URDF 변환 1회, 요청 `expect_conversions` 와 감독기 USD 증거)를 새 환경에 맞춘다. 장면 · 지도 · 오라클 · 마스크 의미 · 검사 기준(허용 오차 포함)은 바꾸지 않는다. 사본 이름 `s2_step4a33/`, 새 `SHA256SUMS.txt`, 새 시험.
- 두 환경의 `height_scanner` 설정(attach prim · offset · ray_alignment · pattern · mesh_prim_paths · update_period · max_distance · debug_vis)을 소스에서 읽어 **항목별 대조표**로 보고서에 쓴다 (기본 Go2 = `isaaclab_tasks` 소스, RobotLab = `env_cfg.py:65~79`). 다르면 어떤 항목이 지도 값에 영향을 주는지.
- 4차의 두 원인 조사 (CPU 만, 원자료는 읽기만):
  (a) PhysX 질의가 전부 hit False 인 이유. 프로브 코드(`s2_mesh_probe_a2.py`)의 광선 시작점 · 방향 · 거리 단위, 질의 시점(물리 step 전후), 시작점에 더하는 +20 m 의 처리, 질의 대상 collision group 을 `physx_queries.npz` 값으로 확인해 가능한 원인을 순위와 근거로 적는다. 의미를 바꾸는 수정은 하지 않고, 수정안과 필요한 GPU 단회의 크기만 적는다.
  (b) env 6 의 quat 편차 0.00484. 어느 성분인지, 어느 step 에서 생기는지(`capture.npz` 의 root_quat_w[:16]), 접촉 · 돌 가장자리와 관련이 있는지. 허용치(.002)를 바꾸자는 제안이면 그 근거와 위험을 적고 값은 바꾸지 않는다.

**2-3. step9 와의 관계**
- 단회 short 의 요청 JSON 은 이번에 건드리지 않는다. 단, 2-1 의 이름 표가 short 경로에도 적용되는지 확인해 보고한다.

## 3. 끝나면

`REPORT-s2-step10.md` (사실 확인 · 2-1 시험과 변이 · 접근 이름 표 · 2-2 대조표와 두 원인 조사 · 바뀐 파일 · 시험 수 · 첫 실패 · 미확인), `S2-STEP10-SHA256SUMS.txt`, #550 댓글 초안(미게시). 깨끗한 복사본 `-I` 전체 회귀(step9 시험 전부 + 새 것). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
