> 분류: A/평가 · 공통 평가 계약 CE12-v1 · 1 단계 이식 진단 ① (adapter · native 기록기 · 대조기 · 실행기 · 수집 검증 · 자료 승인)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:42 · 실행기 19:17 · ASTRA 17d 고침 23:46 (`date` 로 잼)
> 근거: inbox/jay/20261012-arch-discussion/DESIGN-astra-12-common-eval.md 2.1 · 2.2 · 2.4 · 5.1 · 5.2 · VERIFY-astra-17.md 8 · VERIFY-astra-17d.md 2.5 · 2.6 · 2.7 · 4 · 7 · lead 지시 19:03 · 20:06 · 23:30 · robot_lab env_cfg.py · actor_critic_moe_cts.py · IsaacLab observation_manager.py · circular_buffer.py · joint_actions.py · ray_caster.py · patterns.py · spawners/from_files.py · terrain_importer.py · _eval/q_eval_cmdr.py · isaac_slot_v3.py · usd_isolate_run_v3.py · gpu_guard.py · foothold-lab models/foothold-v2.env.yaml · sim/eval/gap_observations.py · eval_command_response.py · eval_generalization.py (모두 읽기만)
> 요지: 원시 상태에서 native 와 같은 관측 (CTS 450 + 45 · v2 235) 과 joint target 을 만드는 adapter 와, 기록기 두 개 · 실행기 · 수집 검증 · 자료 승인을 만들었다. CPU 시험 22 + 117 칸 통과 · 변이 21 + 55 개 모두 잡음. 「수집 성공」 과 「S0 1 단계 승인」 을 나눴다.
> 상태: CPU 시험 · 변이 통과. Isaac 실행 0 회 · native 기록 0 건 · 그래서 「adapter 가 native 와 같다」 는 아직 미확인

# CE12 1 단계 · 이식 진단 ①

## 무엇을 만들었나 (모두 `_eval/ce12/` 새 파일 · 공용 파일 수정 0)

| 파일 | 하는 일 |
|---|---|
| `adapters.py` | `CTSStudentAdapter` · `V2Adapter` · 행동 해석 `decode_action` · 서명 JSON `write_signature`. 순서 · scale · clip · 이력 · 기본 자세는 원래 설정 파일 (`env_cfg.py` · `unitree.py` 는 ast 로, v2 는 `foothold-v2.env.yaml`) 을 읽어 정한다. native 기록 npz 형식 (`DUMP_COMMON` · `DUMP_CTS` · `DUMP_V2`) 도 여기 |
| `cells.py` | (23:46) 기록 칸 표 · 강제 reset · 명령 전환 규칙 · 기대 명령 시간열. 기록기 · 실행기 · 검증기가 이 한 곳을 쓴다 (순수 Python) |
| `dump_native_cts.py` | (Isaac · lead 실행) q_eval_cmdr.py 와 같은 평가 환경에서 평지 칸을 기록. 학습 설정과 관측 · 행동 · decimation 이 다르면 멈춘다 (종료 3). 선택: 일부 env 강제 reset · 한 env 명령 전환. meta 에 schedule · coverage (reset · 전환 · miss 수) |
| `dump_native_v2.py` | (Isaac · lead 실행 · isaac311) v2 평가기와 같은 환경 (rough + 평면 · 규격 2 height). 런타임 설정이 env.yaml 과 다르면 멈춘다 (종료 3). 같은 선택 · 같은 coverage. v2 관절 순서의 정본은 이 기록 |
| `compare_native.py` | (CPU) npz 를 adapter 로 다시 돌려 칸마다 대조 · 첫 불일치를 step · env · term · 이력 칸 · 관절 (광선) 로 보고. 23:46 부터 보고서에 읽은 입력 해시 (npz · meta · signature · checkpoint · 설정 · 코드) 와 coverage 를 남긴다 |
| `run_dump.py` | 실행기 v2. cts 와 v2 모두 `isaac_slot_v3.py` -> `gpu_guard.py` -> `usd_isolate_run_v3.py` -> 기록기. 변환 예상 cts 1 · v2 0. 기록기 인자는 허용 목록만. 끝나면 출력 위치를 직접 확인 |
| `validate_dump.py` | 검증기 v2. 수집 검사 22 개 (COLLECTED) · 승인 검사 8 개 (APPROVED · REJECTED · PENDING) · 승인 stamp 재확인 |
| `test_adapters.py` · `mutate_adapters.py` | adapter · 대조기 시험 22 칸 · 변이 21 개 |
| `test_run_dump.py` · `mutate_run_dump.py` | 실행기 RT 12 칸 · 수집 VT 68 칸 · 승인 VA 37 칸 · 변이 55 개 |

### adapter 가 지키는 것 (코드 위치)

- CTS policy 450: term 마다 이력 10 칸을 oldest -> newest 로 편 뒤 term 끼리 잇는다 (observation_manager.py:424 · 433 · circular_buffer.py:80-90). 최신 명령 87:90 · single 명령 6:9.
- 각 term 은 clip [-100, 100] 다음 scale (ang vel 0.25 · joint vel 0.05 · 나머지 1.0) (observation_manager.py:404-407).
- reset(ids) 뒤 첫 갱신은 그 표본을 10 칸 모두에 (circular_buffer.py:136-139). reset 은 칸을 0 으로 지우고 횟수를 0 으로 (circular_buffer.py:106-110). 기억한 raw action 도 0 (action_manager.py:364-365).
- 갱신은 `observe(update_history=True)` 정책 step 당 한 번. `update_history=False` 읽기는 전진하지 않는다 (observation_manager.py:411-420).
- 관절은 이름으로 맞춘다. CTS 는 JOINT_NAMES. v2 는 런타임 이름 목록을 반드시 인자로 받는다 (없으면 거절).
- v2 235: scale 없음. height = clip(where(유효, pos_w_z - hit_z - 0.5, +1.0), -1, 1). pos_w 에는 광선 시작의 +20 m 가 없다 (ray_caster.py:224 · 241-248). 187 광선은 x 가 가장 빨리 (patterns.py:41-53).
- 행동: target = clip(raw x scale + offset). offset 기본은 기본 자세 · native motor offset DR 값을 인자로 받을 수 있다.
- 추론: CTS 는 `act_inference` 에 policy · single_obs 만 (critic 열쇠 없이) (actor_critic_moe_cts.py:70 · 90 · 225-234).

## ASTRA 17d 고침 (23:46)

| 절 | 결함 (17d 재현) | 고침 | 시험 · 변이 |
|---|---|---|---|
| 2.5 | 추가 인자가 정확히 `--outdir` 일 때만 거절해 `--outdir=...` 로 출력이 빠져나감 (rc 0) | 기록기마다 허용 목록만 받는다. 이름은 정확히 같아야 하고 (argparse 축약 거절) 한 번만, 값은 형식 검사. `--allow_cfg_diff` · `--outdir` · `--tag` · `--checkpoint` · `--env_yaml` · `--device` · `--headless` 는 어떤 표기로도 거절. cells · envs_per_cell · steps 는 늘 명시해서 넘겨 요청이 run.json 에 남는다. 자식이 0 이어도 `<native>/<tag>/` 에 npz · meta · signature 가 있고 meta 의 outdir · tag · checkpoint · allow_cfg_diff 가 맞아야 한다 (아니면 88) | RT6 (등호형 · 축약 · 중복 · 금지 · 틀린 값 21 가지) · RT10 · MR03~MR07 · MR15 · MR16 |
| 2.6 | v2 를 잠금 없이 띄우고 끝난 뒤 assigned.jsonl 을 보던 방식은 쓰기를 막지 못함 | v2 도 slot v3 를 거치고 `--expect_conversions 0` (slot v3 가 자식 환경 FOOTHOLD_EXPECT_CONVERSIONS 로 넘기고 usd_isolate_run_v3 가 변환기 진입 즉시 막는다). cts 는 1. slot · isolate v3 원본에 그 기능 이름이 안 보이면 v2 는 띄우지 않는다 (2). 관문 경로는 상수 하나씩 (`SLOT` · `ISOLATE`). 검증기의 명령 검사도 `usd_isolate_run_v3.py` · `isaac_slot_v3.py` 이름으로 | RT2 · RT3 · RT8 · RT9 (뜻밖의 변환: 89 · 폴더 · 공용 경로 · assigned 줄 없이 거절 줄만) · MR08~MR10 |
| 2.7 | VALID stamp 이 서명 누락 · allow_cfg_diff · 설정 차이 · teacher 입력 action 차 · 틀린 steps/cells 를 못 거름 · 없는 서명을 해시 목록에서 조용히 뺌 | 「수집 성공」 (22 검사) 과 「자료 승인」 (8 검사) 을 나눴다. 승인: A1 서명 내용 = 지금 adapter · A2 요청 cell · T · N · 강제 reset = npz · A3 명령 시간열 = 칸 + 전환 · A4 금지 override · 설정 차이 0 · A5 student 경로 (기록기 자체 검사 + CPU 재계산 critic invariance) · A6 `--recompute_action` 보고서 (입력 해시가 지금 파일과 같아야) · A7 · A8 reset · 전환 경로. 끝나지 않은 검사는 보류 (PENDING · 종료 3). 승인 stamp 은 `--check_approval` 로 다시 대조 (바뀌면 무효). 수집 stamp 은 파일이 하나라도 없으면 쓰지 않는다 | VT (검사마다 결함 하나 → 그 검사만) · VA (같은 방식) · VA-teacher (17d 반례 묶음) · RT12 (끝까지) · MV-* 39 개 |
| 4 | 60 step 평지 기록으로 reset 뒤 이력 · 명령 전환 · miss 를 검증했다고 할 수 없음 | 기록기에 `--reset_envs` · `--reset_step` (그 env 들만 그 step 에서 native time-out 경로로 reset) 과 `--switch_env` · `--switch_step` · `--switch_cell` (한 env 명령 전환). 기본은 끔. meta · 비교 보고서 · 승인 출력에 reset · 전환 · miss 수를 내고 0 이면 「미확인 경로」 로 표시. 승인은 reset · 전환이 0 이면 보류 | VA-pending · A2c · A3b · MV-A7 · MV-A7b · MV-A8 |

## 시험 결과 (2026-10-13 23:46 · CPU · isaac311-moects · GPU 가림)

- `test_adapters.py`: **22/22 PASS** · `mutate_adapters.py`: **21/21 CAUGHT** (내용은 18:42 판과 같다 · 대조기 보고서에 해시를 더한 뒤 다시 돌림).
- `test_run_dump.py`: **117/117 PASS** (RT 12 · VT 68 · VA 37). 관문은 실제 `isaac_slot_v3.py` · `usd_isolate_run_v3.py` 를 시험 시작 때 사본으로 떠서 쓴다 (원본이 고쳐지는 중이어도 한 판). 가짜는 gpu_guard 와 기록기 (가짜 isaaclab 변환기 포함) 뿐이다. 승인 시험 (VA) 의 raw action 은 실제 E1 model_20000 · foothold-v2.pt 를 CPU 로 돌린 닫힌 고리 출력이고, A5 · A6 도 그 체크포인트를 CPU 로 읽는다 (읽기만).
- `mutate_run_dump.py`: **55/55 CAUGHT** (실행기 16 · 수집 검사 22 · 승인 검사 17).
- 시험에 쓴 v3 사본의 sha256 은 시험 끝 줄에 찍힌다. 이번 판 (23:49): isaac_slot_v3.py 974919b0… (20:10 수정본) · usd_isolate_run_v3.py 30dc2ea9… (20:08 수정본).

## lead 가 돌릴 명령 (23:46 판 · run_dump.py 로만 띄운다)

```bash
cd C:/isaac/ext/go2_rl_robotlab/_eval
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
V2=C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.pt
FIX="--reset_envs 1,6 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03"   # 선택: reset · 전환 경로 (승인 A7 · A8)

# 먼저 명령만 확인 (아무것도 안 만든다)
"$PY" ce12/run_dump.py --which cts --checkpoint $E1/model_20000.pt --tag cts_e1_m20000 --dry_run -- $FIX

# 1. 수집 (기본 --gpu 1 · --min_free_mib 4096 · --stop_file _eval/out_ce12/STOP · --deadline 0)
"$PY" ce12/run_dump.py --which cts --checkpoint $E1/model_20000.pt --tag cts_e1_m20000 -- $FIX
"$PY" ce12/validate_dump.py --which cts --tag cts_e1_m20000 --checkpoint $E1/model_20000.pt --attempt <출력된 attempt> --stamp
# 2. CPU 재계산 대조
"$PY" ce12/compare_native.py --dump out_ce12/native/cts_e1_m20000/native.npz --recompute_action --report out_ce12/native/cts_e1_m20000/compare.json
# 3. 승인 (APPROVED · REJECTED · PENDING) · 나중에 다시 확인
"$PY" ce12/validate_dump.py --which cts --tag cts_e1_m20000 --checkpoint $E1/model_20000.pt --attempt <attempt> --approve --compare_report out_ce12/native/cts_e1_m20000/compare.json
"$PY" ce12/validate_dump.py --which cts --tag cts_e1_m20000 --checkpoint $E1/model_20000.pt --attempt <attempt> --check_approval

# v2 는 같은 순서 (기록기는 isaac311 python · 변환 예상 0)
"$PY" ce12/run_dump.py --which v2 --tag v2_flat -- $FIX
"$PY" ce12/validate_dump.py --which v2 --tag v2_flat --checkpoint "$V2" --attempt <attempt> --stamp
```

- 실행기가 정하는 것: CUDA_DEVICE_ORDER=PCI_BUS_ID · CUDA_VISIBLE_DEVICES=--gpu · OMNI_KIT_ACCEPT_EULA · FOOTHOLD_EXPECT_CONVERSIONS · cwd `_eval`. attempt 이름 `<tag>-<YYYYmmdd-HHMMSS>-<pid>`.
- 명령 (cts): `isaac_slot_v3.py --watch_log <native>/<tag>.log --record <native>/<tag>.slot.json --usd_root <native>/_attempts/<attempt>/usd --attempt <attempt> --lock _eval/slot/isaac_convert.lock --registry _eval/slot/isaac_usd_registry.json --scan_dirs _eval/out_ce12/native,_eval/out_branch,_eval/out_uncr,_eval/out_rand --stop_file .. --deadline .. --expect_conversions 1 -- gpu_guard.py --gpu .. --min_free_mib .. --log .. --summary .. -- <isaac311-moects> usd_isolate_run_v3.py ce12/dump_native_cts.py --headless --checkpoint .. --tag .. --outdir <native> --cells .. --envs_per_cell .. --steps ..`. v2 는 `--expect_conversions 0` 과 isaac311 python.
- 출력 배치: `<native>/<tag>/` (native.npz · meta.json · signature.json · validate_stamp.json · approval_stamp.json) · `<native>/<tag>.log` · `.slot.json` · `.guard.json` · `<native>/_attempts/<attempt>/run.json` · `usd/`. 하나라도 이미 있으면 거절 (2 · 옮긴 뒤 다시).
- 기록기 인자 허용 목록 (맨 뒤 `--` 다음): 공통 `--cells --envs_per_cell --steps --reset_envs --reset_step --switch_env --switch_step --switch_cell` · cts `--family --difficulty --eval_seed --physx_small_buffers --train_yaml --agent_yaml` · v2 `--seed --env_spacing --dr_profile --spawn_xy_range --yaw_range_deg --joint_pos_scale`. CMD-R 갈래 체크포인트는 `-- --train_yaml $E1/params/env.yaml --agent_yaml $E1/params/agent.yaml`.
- 종료 코드: 0 · 2 거절 · 98 멈춤 파일 · 마감 · slot v3 의 코드 (89 변환 예상 위반 · 90 관문 판정 못 함 · 91 assigned 미연결 · 94 루트 밖 · 95 폴더 수 · 96 충돌 · 97 변환 시간 · 자식 코드 · guard 99) · 88 (자식 0 인데 출력 위치 · 내용이 다름).
- 검증기 종료 코드: 0 COLLECTED (와 --approve 면 APPROVED) · 1 INVALID 또는 REJECTED 또는 승인 무효 · 3 PENDING.

### v2 변환 예상 0 의 근거 (코드 읽기 · 19:17 판에서 이어짐)

1. Isaac Lab 에서 변환기를 만드는 곳은 `spawn_from_urdf` (sim/spawners/from_files/from_files.py:118) 와 `spawn_from_mjcf` (:160) 둘뿐이다. MeshConverter 를 만드는 spawner 는 없다.
2. v2 기록기 장면: robot = UNITREE_GO2_CFG (isaaclab_assets/robots/unitree.py:140-142 UsdFileCfg) · terrain "plane" (terrain_importer.py:108 · :223 GroundPlaneCfg · from_files_cfg.py:206) · DomeLight · RayCaster · ContactSensor. velocity 과제 폴더에 UrdfFileCfg · MjcfFileCfg 없음. ASTRA 17d §2.6 도 이 판단을 확인했다.
3. 이 판단이 틀리면 (뜻밖의 변환) usd_isolate_run_v3 가 변환기 진입에서 막고 slot v3 가 89 를 낸다 (RT9). 「폴더 없어도 통과」 로 완화한 것이 아니다.

## 허용 오차 (대조기 · 기록을 보기 전에 정함 · ASTRA 17d §4 는 초기 기준으로 수용)

| 항목 | 값 | 근거 |
|---|---|---|
| 관측 칸 | 1e-6 | 계약 5.2 「같은 FP32 계산 1e-6 목표」. 관측은 뺄셈 · 곱셈 · clamp · where 뿐 (기대 0) |
| joint target · 기억한 last action · 기본 자세 · 광선 지역 좌표 | 1e-6 | 같은 근거 |
| CPU 재계산 action (`--recompute_action`) | 1e-4 | 행렬곱 합산 순서 차이. 사전 설정 (근거 미확인). 넘으면 보류하고 원인을 나눠 본다 (native GPU 대 CPU · CPU native 관측 대 CPU adapter 관측). 사후에 올리지 않는다 |
| 이름 · 배치 · 차원 · 이력 길이 · 명령 시간열 | 정확히 같음 | 수치 오차로 넘어갈 수 없다 |

## 계약 · 의뢰 문구와 코드가 다른 곳 (코드를 따랐다)

1. **행동 clip 의 자리.** 계약 2.2 와 의뢰는 `q_default + 0.25 x clip(raw)`. Isaac Lab 은 target 에 clip (`joint_actions.py:173-178`). CTS 는 [-100, 100] rad (|raw| 가 약 390 을 넘어야 걸림 · 계산상 추정) · v2 는 clip 없음. ASTRA 17d §4 가 이 정정을 확인했다.
2. **offset 은 q_default 가 아닐 수 있다.** q_eval_cmdr.py 는 motor zero offset DR (+-0.035 rad) 을 켜 둔다. 기록기는 step 마다 `action_offset` 을 남기고 대조기는 그 값으로 비교한다.
3. **v2 관절 관측은 「전 관절」.** Go2 는 12 개라 차원은 같다.
4. **CircularBuffer reset 은 칸을 0 으로 지운다.** adapter 도 그렇게 둔다.
5. **생성자의 critic 요구.** act_inference 는 critic 을 읽지 않는다 (T17 · T18 · 승인 A5).

## 확인된 것과 미확인

확인됨 (이번에 실행하거나 파일에서 읽음)
- 위 CPU 시험 · 변이. 실제 slot v3 · isolate v3 사본으로 cts (예상 1) 와 v2 (예상 0 · 뜻밖의 변환 거절) 경로를 가짜 기록기와 끝까지 돌렸다.
- E1 model_20000 · foothold-v2.pt 의 CPU strict 적재 · 정규화 꺼짐.
- slot v3 의 CLI (`--expect_conversions 0|1` · 기록 칸 expect_conversions · conversion_attempts · expect_violation · launcher_blocked · 종료 89) 와 isolate v3 의 FOOTHOLD_EXPECT_CONVERSIONS (0 · 1 · any) 를 23:30 원본에서 읽고 맞췄다.

미확인
- **adapter 출력이 native 와 같은가** 자체. 기록기를 안 돌렸다.
- 기록기 두 파일은 문법 검사만 통과. 강제 reset (episode_length_buf 를 max-1 로 두어 time-out) 과 명령 전환이 실제 Isaac 에서 의도대로 도는지, 그 뒤 기록이 승인 A2 · A3 와 맞는지는 미확인.
- 실제 Isaac (Kit) 안에서 isolate v3 의 감싸기 · 변환 예상 0 거절이 걸리는지. v2 실제 실행에서 slot v3 가 장면 생성 줄로 잠금을 푸는지 (예상 0 의 해제 규칙).
- 실제 gpu_guard (NVML) 와 실제 Isaac 로그 형식과의 연결. 시험의 guard 와 기록기는 가짜.
- slot v3 · isolate v3 는 다른 하위 작업이 아직 고치는 중일 수 있다. 바뀌면 `test_run_dump.py` 를 다시 돌려 새 사본으로 확인해야 한다 (끝 줄의 sha256 으로 판을 구별).
- GPU 관측과 CPU adapter 관측의 비트 동일 기대 · 재계산 action 허용 1e-4 의 근거.
- v2 는 평면이라 height miss (+1) 경로가 native 로는 0 (승인 출력에 「미확인 경로」 로 표시 · 승인을 막지는 않는다).
- CMD-R 갈래 체크포인트의 설정 동일성은 기존 meta 한 건에서만 0 으로 확인.
- 이번 범위 밖: 2 단계 P0 · P1 세 칸 진단, WORLD_PATH 명령 변환, terminal pre-reset recorder, P0 manifest, MapABAdapter, 실제 GPU 메모리 · 장치 UUID 확인 (17d §3).
