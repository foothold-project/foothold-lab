> 분류: A/정책학습 · 구현 인계 (SC-3 START 시험지 · SC-4 S1-a 코드)
> 작성: sonnet-code 세션 (10/20 10:50, 컨텍스트 83 % 에서 단위를 끊음)
> 근거: 설계 커밋 28114f68 (14 · 15 · 16 · 17 · 52 · 13 · 18 · APPROVED-DIRECTION, 이 사본에 병합됨), lead 의뢰 SC-3 · SC-4
> 요지: SC-3 START 시험지는 Kit 연결 · 미리보기 · 측정 1 차 완료, 10 인스턴스 재측정이 GPU 에서 대기 중. SC-4 S1-a 는 순수 계산(명령 · 승급 · 열 배정 · 보상 · Go2 모델) L0 56 통과, Kit 쪽 모듈(명령 term · 승급 term · 지형 cfg · env cfg · 등록)은 아직 안 씀
> 상태: 진행 중 · 본 학습 안 함 · L1 은 lead 검수 뒤

# 인계

## SC-3 START 시험지 (GPU 측정 중)
- 미리보기: `evidence/baselines/start_preview/` (4 종 레벨 9 그림 + 전체 4 x 4 그림). Kit 메시에서 읽은 치수가 논문값과 맞음(징검돌 돌 0.2 · 구덩이 76.2 %, 평균대 폭 0.175, 디딤 빔 0.15 · 0.275 · 64.2 %, 틈 0.7).
- 1 차 측정(`eval_new/start/<판>/`, 칸 하나당 판 100, 칸 인스턴스 1 개): E1 R 0.074 (4 종 평균), v2 0.383, NVIDIA 는 끝났으나 표 미작성. **한계**: 같은 (종류, 레벨) 판들이 칸 하나(구덩이 깊이 · 돌 배치 하나)를 공유해 레벨별 값이 칸 하나의 운에 끌림(v2 틈 레벨 4~8 R 0 인데 레벨 9 R 0.99). Wilson 구간이 과소.
- 재측정: 종류 x 레벨마다 독립 칸 10 개(인스턴스), 칸당 10 판 = (종류, 레벨)당 100 판. 대기 스크립트 `eval_new/start10_all.sh` 가 smoke2(`eval_new/start_smoke2`) 통과를 보고 E1(GPU 0)→NVIDIA(GPU 0) · v2(GPU 1) 를 `eval_new/start10/<판>/` 에 돌림. 끝나면 `eval_new/start10/done.txt`. 표는 `python -m foothold_s2.eval.start_tables --root eval_new/start10 --out <폴더>` 로 만들고 evidence/baselines 에 복사 + README 갱신 + lead 보고.
- MEV 는 이 실행에서 안 재(발 디딤 위치 미수집). 주파율은 `crossing_ratio`.
- 코드: `foothold_s2/eval/` 의 `start_preview.py` `start_tables.py`, `run_eval.py start`, `terrain_sets.start_generator(instances)`, `assign_tiles`.

## SC-4 S1-a 코드: 한 것 (L0 56 통과, 전체 pytest 122 통과, pyflakes 0)
- `foothold_s2/commands/mixed_core.py` (torch): 자유 속도 표집 · 모드 비율(정지 > 회전 > heading > 자유 wz, 1,000 회 전후 플래그 0.333 / 0.417) · heading 식 · 깃발 상태기계(직선 4 깃발, 0.5 m 도달, 마지막 2 s 정지, 제자리 회전 v < 0.3, 물러나기) · 범위 커리큘럼 · 노출 로그. 시험 `tests/test_commands.py` 23.
- `foothold_s2/curriculum/rules.py`: 승급 · 강등(자유 속도 · 깃발). `terrains/columns.py`: Isaac 고정 배치 식으로 열 수 계산, `terrains/progression.py`: p_advance(S1-b 용). 시험 `tests/test_terrains_curriculum.py` 12.
- `foothold_s2/robots/go2_params.py`: 종아리 DCMotor(45.43 · 15.70) · PIE 범위 · `dc_motor_clip`. 시험 `tests/test_go2_model.py`: 설치 Isaac Lab `_clip_effort` 소스를 AST 로 꺼내 CPU 에서 실행해 ASTRA 표(+100: 45.43 · 22.715 · 0 · −12.443, −100: 전부 −45.43)와 대조, URDF 관절 12 개가 8 + 4 로 갈리는지, URDF 종아리 값 일치.
- `foothold_s2/rewards/core.py` (14 항 식 + 가중치 표, B 식, S1 발 가장자리 0) 시험 `tests/test_rewards.py` 11. `rewards/start_rewards.py`(Isaac 보상 cfg, **Kit 에서 import 시험 안 함**).

## SC-4 Kit 쪽 모듈 (10/20 오후 작성, L0: pytest 133 통과 · AST 이름 대조 11 · pyflakes 미사용 import 외 0)
- `commands/mixed_command.py` (MixedVelocityCommand): env 번호 % 5 == 0 이 깃발 env, reset 때 기록 · 깃발 갱신, `max_dist` `cmd_sum_xy` `goals` `iteration`. S2 는 `flag_provider` 로 깃발 목록을 갈아 끼움.
- `curriculum/terrain_levels_mixed.py`: `terrain_levels_mixed`(rules.judge 호출, cmd 합을 재추출 단위로 환산), `command_range_curriculum`(반복당 한 번 vmax 올림).
- `robots/go2_cfg.py`, `terrains/rough_go2_cfg.py`(23 열, `build_generator` 는 S1-b/S2 가 비율만 바꿔 씀), `tasks/mdp_extra.py`(발 접촉 관측 · 발 지면 아래 종료), `tasks/s1_env_cfg.py`(Scan/Blind, S2 는 상속), `tasks/agents/s1_ppo_cfg.py`, `tasks/__init__.py`(등록 `FootholdS2-Go2-S1a-scan-v0` · `-blind-v0`), `train_s1.py`(설치 train.py 를 읽어 우리 task 등록 줄만 끼워 실행).
- `tests/test_kit_names.py`: 설치 Isaac Lab 소스와 `mdp.X` · import · `params` 키 대조(없는 이름을 넣으면 걸림을 확인).
- **Kit 에서 처음 도는 것(미확인, L1 에서 드러날 것)**: 충돌 링크 이름 `Head_.*`, 정확한 `history_length` 관측 크기(495), `sky_light=None`, 발 지면 아래 종료의 스캔 점 조회, 명령 term reset 순서.
- 다음: lead L0 검수 → L1(GPU 0 scan · GPU 1 blind 첫 10 update, Traceback 0, steps/s, 메모리, env별 명령 방식 로그).

## 해석 · 문서와 다르게 한 곳 (lead 확인 필요)
- **S1-a 열 수 23**: 이어진 지형만 학습하면 Isaac 이 비율을 합 1 로 정규화해, 15 §2 의 50 열이면 비율이 정수 열로 안 떨어짐(50 열에 이어진 7 종만 배정 시 10.87 열 등). 23 열은 정수(5 5 4 4 2 2 1). 50 열 전체 혼합(S1-b · S2)은 `columns.FULL` 로 시험함.
- 14 §9 의 「1,000 표본 ±0.03」 은 비율 0.5 에서 1.9 시그마(우연히 약 6 % 실패)라 시험은 1,000 표본 ±0.05, 20 만 표본 ±0.005 로 이중화.
- 17 §9 의 「+21.67」 은 식으로 21.655 (문서 반올림).
- 시스템 지연 0~15 ms · 모터 세기 배율은 DCMotor 로는 구현 안 함(DelayedPD 가 필요) → 열린 항목. 초기 관절 0.5~1.5 단위 열린 채 Isaac 기본 유지.
- critic 관측(S1)은 문서에 없음: o_t + 몸 선속도 3 + 발 접촉 4 (가정).
- START 4 종은 8 x 4 m 칸이라 축 3 옆 · 뒤 명령을 못 잼(앞서 보고).

## 10/20 12:0x 중단 시점 (사용 한도 97 %)
- L1 결과: blind 2회 · scan 1회 모두 rc 0, Traceback 0. blind 19.3k steps/s (policy 495), scan 20.9k steps/s (policy 232), critic 52. 방식 비율이 14 §3.2 와 맞음(깃발 0.200 · 정지 0.083 · heading 0.235 · 자유 wz 0.483). 로그 `C:/Users/AI-WS01/s2_lab/s1_l1/{blind,blind2,scan}/run.log`.
- 확인 셋(probe_s1, `s1_l1/probe/run.log`): 행동 지연 불일치 0 (지연 0~3 모두 나옴), 모터 세기 배율 0.909~1.097 · env 64 개 모두 다름 · saturation = limit, 발 지면 아래 종료 오탐 0 · 참 양성 64/64. PASS.
- 새로 넣음(미실행): `eval/adapters.py` 의 `S1Adapter` + `run_eval.py --policy s1blind|s1scan` + 명령 term `fixed_cmd` · `flag_stride 0`. pytest 134 통과, 아직 Kit 에서 안 돌림.
- 다음 한 걸음: blind 체크포인트(`logs/rsl_rl/foothold_s1a/2026-10-20_11-35-41/model_9.pt`)로 예행 평가 8 판(축 1 한 칸 · 축 3 한 칸, GPU 1)을 돌려 CSV 가 나오는지 확인 → S1 L1 완료 보고 → `s2_env_cfg` (관측 묶음 policy 45 · depth 60x60 · gt_map 512 · gt_feet 100 · base_vel 3 · contacts 4, rl 사본 start_runner.py 머리말).
- 미커밋 파일: 이 커밋 직전까지 모두 커밋 대상(adapters.py · run_eval.py · mixed_command.py · tasks/probe_s1.py · 이 문서).

## 10/20 오후 S2 L0 (커밋 649ce407 · 19db2018 · 이어서)
- rl 지각 모듈(feature/s2-perception-rl 2aef7f91) 로컬 병합. 병합 뒤 pytest 178 통과(Kit python 으로는 rl 의 test_start_runner 가 `store_code_state` import 오류: 이 환경의 rsl_rl 이 ext 쪽 사본으로 잡힘, rl 쪽 환경 문제).
- (1) `terrains/sparse_terrains.py`: START 시험지 치수를 8x8 칸 가운데 띠에 놓음(가정), 칸 좌표 side table, 월드 변환 `tile + (row*8, col*8)`, 모서리 마스크(낙하 0.2 m, 2.5 · 5 cm 띠, 해상도 2.5 cm = 칸당 320x320), 깃발 4개를 발판 위로 옮김. 칸은 (종류, 난이도) 만으로 결정. 시험 `test_sparse_terrains.py` 15.
- (2) `terrains/s2_layout.py` · `s2_runtime.py` · `curriculum/terrain_levels_mixed.terrain_levels_s2` · `attach_s2_tables`: 생성기 호출 순서(열 우선, 줄 순서)로 side table 을 (줄, 열)에 묶고, 가정이 깨지면 오류. 시험 `test_s2_runtime.py` 9.
- (3) `rewards/core.foot_edge_penalty_tiles` + `start_rewards.foot_edge_term`(표 없으면 0). 시험 `test_rewards.py` 에 1 추가.
- **Kit 에서 처음 도는 것(미확인)**: 생성기 호출 순서 가정(`bind_all` 이 검사함), 대량 칸에서 trimesh 박스 수, `attach_s2_tables` 를 부르는 실행기(`train_s2.py` 는 아직 없음), apply_start_perception 병합 후 env 생성.
- 다음: lead 에 L0 완료 알림 → Kit 예행(G0 64 env 정도) 허가 받아 생성 · reset · 첫 update 확인.

## 10/20 오후 SC-6 정책 노드 (커밋 7b5cf869 · e9460aac)
- `foothold_s2/deploy/`: `obs.py`(S1-blind 관측 조립, Isaac 기록과 0.0 오차) · `sdk_joints.py`(SDK FR FL RR RL ↔ Isaac hip 넷 · thigh 넷 · calf 넷 순열) · `command_filter.py`(31 §5) · `safety.py`(PASSIVE → FIXSTAND → POLICY → HOLD(STOP 래치, 자동 재개 없음) → SPORT/DAMP, deadman 0.3 s · heartbeat 1.0 s) · `export.py`(체크포인트 → ONNX) · `record_isaac.py`(Kit 기록기) · `params/deploy.yaml` · `testdata/s1blind_record.npz` · `exported/policy.onnx`(10 update 체크포인트, 형식 확인용). 설계 `DESIGN-policy-node.md`. 시험 `tests/test_deploy.py` 20(ONNX 1개는 `C:/Users/AI-WS01/s2_lab/pylib` 에 onnx 1.18 + onnxruntime 이 있어야 돌고 없으면 skip).
- 메모(lead): 정리기의 전진 상한 1.0 은 고정값이 아니라 «학습 로그의 최종 커리큘럼 상한(vmax_x)» 을 deploy.yaml 에 내보내 읽게 바꾼다(지금은 가정값 1.0).
- 이전(Linux, 10/22) 뒤 첫 일: unitree_mujoco 파이썬 경로(`simulate_python`, DOMAIN_ID 1, INTERFACE lo)로 FIXSTAND → S1-blind 서기 · 걷기. 먼저 확인할 것: IMU quat 정의(w x y z, 몸 → 세계)가 Isaac `root_quat_w` 와 같은지, gyro 부호, 우리 기본 자세로 서는지. 정책은 정식 S1 체크포인트가 나온 뒤(10 update 체크포인트는 걷지 못함). WSL 에 cyclonedds 등을 까는 것은 하지 않기로 함(lead 결정).
- S2: 학습은 rl 의 `foothold_s2/scripts/train_start.py` + `FootholdS2-Go2-S2-{G0,G1,G3}-v0`(isaac311 python, 판 확인 assert 는 train_start 에 있음). 도움이 되는 probe: `tasks/probe_s2.py`(물러나기) · `probe_s2_edge.py`(발 가장자리) · `probe_s2_recon.py`(재구성 지도 그림). 대기 중인 판단: lead 의 S2 첫 update 확인 항목(foot_edge 평균 음수 여부).

## 10/20 저녁 S1-a 본 학습 실행 준비 (승인 뒤에만 띄움)
- 실행: `bash foothold_s2/run_s1.sh scan cuda:0` · `bash foothold_s2/run_s1.sh blind cuda:1` (6,000 회 · 4096 env · isaac311-moects python · 로그 `logs/s1a_<variant>_<시각>/run.log`, git_head.txt · git_status.txt 가 같이 남음). 띄운 뒤 1~2 분 안에 PID(`Get-Process python`) · 첫 `Learning iteration` 줄 · Traceback 0 을 직접 확인한다. 한 장이 도는 중에는 다른 장에 걸어도 됨(L1 에서 4096 env 가 장당 문제없이 돌았음).
- 예행(64 env 10 update, 깃발 열 +0.5~+3.5 · flag_vmax · penalty_on 로그) 통과: `s1_l1/flags`(깃발 오프셋 x 0.5~3.5, y 0), `s1_l1/blind3`(Curriculum/command_range/{vmax_x,flag_vmax}, Curriculum/penalty_on/{collision,stumble,foot_edge}, Metrics/base_velocity/flag_vmax 모두 찍힘).

## 10/20 저녁 S1 실행 환경 · 재개 상태 (lead 요청)
- S1 도 isaac311(rsl-rl-lib 3.1.2)로 통일: `run_s1.sh` · `train_s1.py` 모두 isaac311. `train_s1.py` 는 설치 train.py 를 읽어 고치던 방식을 버리고 rl 의 train_start.py 와 같은 흐름(판 확인 assert · 상태 파일 · 끝나면 os._exit)으로 다시 썼다.
- `foothold_s2/s1_runner.py` (S1Runner): 설치 OnPolicyRunner + env 상태(common_step_counter · 지형 레벨 · 칸 · range_curriculum 의 vmax_x · vmax_y · flag_vmax · history) · adaptive 학습률 · 난수 저장 · 복원(rl StartRunner 의 같은 함수 사용), latest.pt 100 회마다(임시 파일 + os.replace), 상태 파일 train_start_status.json(starting · running · done · failed), 재개 때 저장된 회차 «다음부터» · max_iterations 는 전체 목표로 읽어 남은 회차만. 설치 runner 의 model_N.pt 는 env 상태가 없어 load 가 거부한다.
- 이어 학습: `bash foothold_s2/run_s1.sh blind cuda:1 --resume --load_run <폴더> --checkpoint latest.pt`. 시험 `tests/test_s1_runner.py` 9(가짜 env).
- Kit 확인: isoA(64 env 6 회, rc 0) → isoB 이어(전체 10, 남은 4): 회차 6 부터, common_step_counter 144 → 240 으로 이어짐, 학습률 저장 · 복원, 상태 파일 done iter 9.

## 10/20 밤 S1-b · 사슬 (SC-9 이후)
- S1-b: `bash foothold_s2/run_s1b.sh cuda:N` (S1-a blind 가장 최근 폴더의 model_5999.pt 에서 단계 전이: 가중치 · optimizer · iteration · common_step_counter · range_curriculum 만 옮기고 지형 칸은 새로; 전체 목표 9000 = 3000 회 더). task `FootholdS2-Go2-S1b-blind-v0`(`tasks/s1b_env_cfg.py` · `s1b_env.py`), p_advance 는 자체 반복 수 T_start 0 · T_end 1500(`env.stage_iteration_offset` 을 체크포인트에 저장 · 복원). 이어: `... --resume --load_run <폴더> --checkpoint latest.pt --load_experiment foothold_s1b`. 돌고 있는 S1-a 의 run_s1.sh 는 고치지 않았다(bash 가 스크립트를 조금씩 읽어서).
- 사슬: `python -m foothold_s2.chain.start foothold_s2/chain/chain_s1a_night.yaml` (상태 폴더 C:/Users/AI-WS01/s2_lab/chain). 실행기는 yaml 이 바뀌면 «아직 안 띄운» 작업 정의를 다시 읽는다(reload). 15 작업, priority · require_file · require_any_file · skip_if_done · accept_rc · vars.
