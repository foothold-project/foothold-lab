> 분류: A/평가 · 공통 평가 계약 CE12-v1 · 1 단계 이식 진단 ① (adapter · native 기록기 · 대조기 · 실행기 · 기록 검증기)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:42 · 실행기 · 검증기 추가 19:17 (`date` 로 잼)
> 근거: inbox/jay/20261012-arch-discussion/DESIGN-astra-12-common-eval.md 2.1 · 2.2 · 2.4 · 5.1 · 5.2 · VERIFY-astra-17.md 8 · robot_lab env_cfg.py · actor_critic_moe_cts.py · IsaacLab observation_manager.py · circular_buffer.py · joint_actions.py · ray_caster.py · patterns.py · _eval/q_eval_cmdr.py · foothold-lab models/foothold-v2.env.yaml · sim/eval/gap_observations.py · eval_command_response.py · eval_generalization.py · lead 지시 10/13 19:03 · _eval/isaac_slot.py v2 · usd_isolate_run.py v2 · gpu_guard.py · IsaacLab spawners/from_files.py · terrain_importer.py · isaaclab_assets unitree.py (모두 읽기만)
> 요지: 원시 상태에서 native 와 같은 관측 (CTS 450 + 45 · v2 235) 과 joint target 을 만드는 adapter 를 만들고 CPU 알려진 답 시험 22 칸 통과 · 변이 21 개 모두 잡음. 기록기는 run_dump.py 로 띄우고 validate_dump.py 로 검증한다 (실행기 · 검증기 시험 37 칸 통과 · 변이 33 개 모두 잡음). Isaac 실행은 lead 몫이다.
> 상태: CPU 시험 · 변이 통과 (실행기는 실제 isaac_slot · usd_isolate_run 에 가짜 guard · 가짜 기록기를 물려 시험). Isaac 실행 0 회 · native 기록 0 건 · 그래서 「adapter 가 native 와 같다」 는 아직 미확인

# CE12 1 단계 · 이식 진단 ①

## 무엇을 만들었나 (모두 `_eval/ce12/` 새 파일 · 기존 파일 수정 0)

| 파일 | 하는 일 |
|---|---|
| `adapters.py` | `CTSStudentAdapter` · `V2Adapter` · 행동 해석 `decode_action` · 서명 JSON `write_signature`. 순서 · scale · clip · 이력 · 기본 자세는 원래 설정 파일 (`env_cfg.py` · `unitree.py` 는 ast 로, v2 는 `foothold-v2.env.yaml`) 을 읽어 정한다. 상수로 적어 두지 않는다. native 기록 npz 형식 (`DUMP_COMMON` · `DUMP_CTS` · `DUMP_V2`) 도 여기 |
| `dump_native_cts.py` | (Isaac · lead 실행) q_eval_cmdr.py 와 같은 평가 환경에서 평지 stand · fwd03 · yawL05 를 60 step 기록. 학습 run 의 params/env.yaml 과 관측 · 행동 · decimation 이 다르면 멈춘다 (종료 3) |
| `dump_native_v2.py` | (Isaac · lead 실행 · isaac311 환경) v2 평가기와 같은 환경 (rough 설정 + 평면 · 규격 2 height) 에서 같은 세 칸 기록. 런타임 관측 · 행동 설정이 env.yaml 과 다르면 멈춘다 (종료 3). v2 관절 순서의 정본은 이 기록 |
| `compare_native.py` | (CPU) npz 를 읽어 adapter 를 같은 순서로 다시 돌리고 칸마다 대조. 첫 불일치를 step · env · term · 이력 칸 · 관절 이름 (또는 광선 번호와 지역 xy) 으로 보고 |
| `test_adapters.py` | CPU 알려진 답 시험 22 칸 (GPU 를 가리고 돈다) |
| `mutate_adapters.py` | 일부러 틀린 사본 21 개 (adapter 18 · 대조기 3) 가 지정 시험에 걸리는지 |
| `run_dump.py` | (19:17 추가) 기록기 실행기. cts: isaac_slot (--usd_root · --attempt · 잠금 · 멈춤 파일 · 마감) -> gpu_guard -> usd_isolate_run -> dump_native_cts.py. v2: slot 없이 gpu_guard -> usd_isolate_run -> dump_native_v2.py, 끝난 뒤 격리 상태 · 변환 흔적 확인 (92 · 93). 이미 있는 출력은 거절 |
| `validate_dump.py` | (19:17 추가) 이번 attempt 의 기록이 제대로 끝났는지 검사 (cts 16 · v2 13 항목, 모두 돌려 실패를 다 보고). 통과하면 stamp |
| `test_run_dump.py` · `mutate_run_dump.py` | (19:17 추가) 실행기 RT 11 칸 · 검증기 VT 26 칸 (결함 하나에 검사 하나만 걸리는지) · 변이 33 개 |

### adapter 가 지키는 것 (코드 위치)

- CTS policy 450: term 마다 이력 10 칸을 oldest -> newest 로 편 뒤 term 끼리 잇는다 (observation_manager.py:424 · 433 · circular_buffer.py:80-90). 최신 명령 87:90 · single 명령 6:9.
- 각 term 은 clip [-100, 100] 다음 scale (ang vel 0.25 · joint vel 0.05 · 나머지 1.0) (observation_manager.py:404-407).
- reset(ids) 뒤 첫 갱신은 그 표본을 10 칸 모두에 (circular_buffer.py:136-139). reset 은 칸을 0 으로 지우고 횟수를 0 으로 (circular_buffer.py:106-110). 기억한 raw action 도 0 (action_manager.py:364-365).
- 갱신은 `observe(update_history=True)` 정책 step 당 한 번. `update_history=False` 읽기는 저장된 버퍼를 돌려줄 뿐 전진하지 않는다. 버퍼가 아직 없을 때의 읽기는 임시로 채워 돌려주고 저장하지 않는다 (observation_manager.py:411-420 과 같다).
- 관절은 이름으로 맞춘다. CTS 는 JOINT_NAMES (FL · FR · RL · RR 의 hip · thigh · calf). v2 는 런타임 이름 목록을 반드시 인자로 받는다 (기본값 없음 · 없으면 거절).
- v2 235: scale 없음. height = clip(where(유효, pos_w_z - hit_z - 0.5, +1.0), -1, 1). pos_w 는 몸통 프림 위치이고 광선 시작의 +20 m 는 들어 있지 않다 (ray_caster.py:224 · 241-248). 187 광선은 x 가 가장 빨리 도는 순서 (i = iy x 17 + ix · patterns.py:41-53).
- 행동: target = clip(raw x scale + offset). offset 기본은 기본 자세 · native 의 motor offset DR 값을 인자로 받을 수 있다. raw 는 다음 관측의 last_action 으로 기억한다.
- 추론: CTS 는 `act_inference` 에 policy · single_obs 만 넣는다 (critic 열쇠 없이). 생성자만 critic 차원 275 를 요구한다 (actor_critic_moe_cts.py:70 · 90 · 225-234).

## 시험 결과 (2026-10-13 · CPU · isaac311-moects · GPU 가림)

`test_adapters.py`: **22/22 PASS**. 기대값은 adapter 를 부르지 않고 손으로 적었다 (T21 · T22 의 가짜 기록만 adapter 로 만들고, 그것은 대조기의 위치 보고 · 재계산 경로를 보는 용도다).

| 칸 | 내용 |
|---|---|
| T01 · T02 | 원본 설정 읽기: CTS 항 순서 · scale · clip · 이력 10/1 · 행동 0.25 · clip · 기본 자세 / v2 3+3+3+3+12+12+12+187 · scale 없음 · height clip 만 · offset 0.5 · miss 1.0 |
| T03 | 손으로 만든 3 step: term-major · 첫 표본 8 칸 반복 + s2 + s3 · 최신 명령 87:90 · 가장 오래된 명령 60:63 · single 6:9 · 1 step 만이면 10 칸 모두 같은 표본 |
| T04 | reset(env0) 뒤 env0 은 s4 를 10 칸 · env1 은 이어감 · reset env 의 last_action 0 |
| T05 | 디버그 읽기 두 번이 전진하지 않음 · 버퍼 없을 때 읽기는 저장 안 됨 |
| T06 · T07 | 경계: ang 400 -> 25 · dq 150 -> 5 · 경계 100 유지 · q_rel 150 -> 100 · action 120 -> 100 / v2 는 같은 입력이 scale · clip 없이 통과 |
| T08 · T09 | 관절 이름 순서를 섞은 입력이 비트 동일 관측 (CTS 두 step 이력 포함 · v2) |
| T10 · T11 · T12 | v2 height: 0.4 · 0 -> -0.1 · inf · -inf · NaN -> +1 · clip / 저장소 gap_observations.py 와 비트 동일 / 광선 0 · 16 · 17 · 93 · 186 의 지역 좌표와 순서 보존 |
| T13 · T14 · T15 | 관절마다 다른 target 을 모델별 역변환 raw 로 넣으면 두 adapter 모두 이름으로 복원 · 같은 raw 가 모델마다 다른 target / clip 은 target 에 / raw 가 다음 last_action |
| T16 | v2 는 이름 없이 못 만든다 · 빠진 · 겹친 이름 거절 |
| T17 · T18 · T19 | 작은 무작위 ActorCriticMoECTS 와 실제 E1 model_20000 (CPU strict 적재): critic 을 바꿔도 action 비트 동일 · policy · single 을 바꾸면 변함 · critic 없는 adapter.infer 와 같음 · student 경로 손 계산과 같음 / v2 체크포인트 CPU 적재 |
| T20 | 서명 JSON: CTS 450/45 · [87,90] · [6,9] · v2 235 · sha256 |
| T21 · T22 | 대조기: 한 칸을 바꾸면 그 step · env · term · 이력 칸 · 관절 · 광선을 첫 불일치로 / 실제 정책 닫힌 고리 가짜 기록에서 --recompute_action 차 0 |

`mutate_adapters.py`: **21/21 CAUGHT**. 의뢰의 셋 (M01 time-major 이력 · M02 0 으로 채운 초기 이력 · M03 scale 누락) 과 M04 scale-clip 순서 · M05 miss -1 · M06 +20 m · M07 자리 순서 대응 · M08 읽기가 전진 · M09 reset 횟수 · M10 clip 을 raw 에 · M11 v2 에 CMD-R scale 복사 · M12/M18 reset 이 raw 를 안 지움 · M13 raw 를 기억 안 함 · M14 최신을 앞에 · M15 height clip 버림 · M16 광선 ij 순서 · M17 infer 가 표본 · C01 대조기 위치 한 칸 밀림 · C02 대조기가 reset 무시 · C03 재계산이 한 step 늦은 관측.

## lead 가 돌릴 명령 (19:17 판 · run_dump.py 로만 띄운다 · 기록기를 직접 띄우지 말 것)

18:42 판의 명령은 isaac_slot.py v2 의 필수 인자 `--usd_root` · `--attempt` 가 없어 인자 오류로 끝난다 (lead 지적 · 변이 MR01 로 재현). 아래로 바꾼다.

```bash
cd C:/isaac/ext/go2_rl_robotlab/_eval
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192

# 먼저 명령만 확인 (아무것도 안 만든다)
"$PY" ce12/run_dump.py --which cts --checkpoint $E1/model_20000.pt --tag cts_e1_m20000 --dry_run

# CTS (E1 model_20000) · 기본 --gpu 1 · --min_free_mib 4096 · --stop_file _eval/out_ce12/STOP · --deadline 0
"$PY" ce12/run_dump.py --which cts --checkpoint $E1/model_20000.pt --tag cts_e1_m20000
"$PY" ce12/validate_dump.py --which cts --tag cts_e1_m20000 --checkpoint $E1/model_20000.pt --attempt <출력된 attempt> --stamp

# v2 (기록기는 isaac311 python · 체크포인트 기본 models/foothold-v2.pt)
"$PY" ce12/run_dump.py --which v2 --tag v2_flat
"$PY" ce12/validate_dump.py --which v2 --tag v2_flat --checkpoint "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.pt" --attempt <출력된 attempt> --stamp

# 대조 (CPU)
"$PY" ce12/compare_native.py --dump out_ce12/native/cts_e1_m20000/native.npz --recompute_action
"$PY" ce12/compare_native.py --dump out_ce12/native/v2_flat/native.npz --recompute_action
```

- 실행기가 정하는 것: CUDA_DEVICE_ORDER=PCI_BUS_ID · CUDA_VISIBLE_DEVICES=--gpu · OMNI_KIT_ACCEPT_EULA · cwd `_eval`. attempt 이름 `<tag>-<YYYYmmdd-HHMMSS>-<pid>`.
- cts 명령: `isaac_slot.py --watch_log <native>/<tag>.log --record <native>/<tag>.slot.json --usd_root <native>/_attempts/<attempt>/usd --attempt <attempt> --lock _eval/slot/isaac_convert.lock --registry _eval/slot/isaac_usd_registry.json --scan_dirs _eval/out_ce12/native,_eval/out_branch,_eval/out_uncr,_eval/out_rand --stop_file ... --deadline ... -- gpu_guard.py --gpu .. --min_free_mib .. --log .. --summary .. -- <isaac311-moects> usd_isolate_run.py ce12/dump_native_cts.py --headless --checkpoint .. --tag .. --outdir <native>`.
- 출력 배치: `<native>/<tag>/` (native.npz · meta.json · signature.json · validate_stamp.json) · `<native>/<tag>.log` · `.slot.json` (cts) · `.guard.json` · `<native>/_attempts/<attempt>/run.json` · `<native>/_attempts/<attempt>/usd/`. 감시 로그를 `<native>` 바로 아래 두는 까닭: isaac_slot 의 `--scan_dirs` 는 그 폴더의 `*.log` 만 훑는다. 하나라도 이미 있으면 거절 (종료 2 · 옮긴 뒤 다시).
- 종료 코드: 0 · 2 거절 · 98 멈춤 파일 · 마감 · cts 는 isaac_slot 의 코드 (94 루트 밖 · 95 폴더 수 · 96 충돌 · 97 변환 시간 · 자식 코드) · v2 는 guard 코드 (99 정지 · 자식 코드) 또는 92 (격리 상태 없음) · 93 (변환 흔적).
- 기록기에 더 줄 인자는 맨 뒤 `--` 다음에. CMD-R 갈래 체크포인트는 `-- --train_yaml $E1/params/env.yaml --agent_yaml $E1/params/agent.yaml`. `--tag` · `--outdir` · `--checkpoint` 는 실행기가 정하므로 거절한다.
- 검증 (validate_dump.py) 항목: R1 run.json 의 attempt · which · tag · 체크포인트 · R2 시험용 바꿔치기 없음 · S1~S8 slot (attempt · slot_rc 0 · child_rc 0 · scene_built · USD 하나 · 루트 밖 없음 · 충돌 없음 · 명령에 usd_isolate_run.py · dump_native_cts.py · tag · 체크포인트) · G1 guard 0 · L1 Traceback 없음 · L2 `[CE12-DUMP] done <tag> N ` · N1 npz 형식 · M1 메타의 체크포인트 sha256 = 지금 파일 · M2 메타 model · tag · 시작 시각이 이 attempt 요청 이후. v2 는 S1~S8 대신 V1 실행 rc 0 · V2 isolate_state.json 의 patched_by · V3 assigned.jsonl 비었음 · V4 로그에 IsaacLab.usd_ 없음 · V5 명령. 모두 통과해야 stamp.
- 대조 판정: `[CE12-COMPARE] ALL PASS` (종료 0). 불일치면 종료 1 과 첫 위치. 보고 JSON 은 npz 옆 `compare_report_<시각>.json`.

### v2 를 slot 없이 띄우는 근거 (코드 읽기)

1. Isaac Lab 에서 변환기를 만드는 곳은 `spawn_from_urdf` (sim/spawners/from_files/from_files.py:118 UrdfConverter) 와 `spawn_from_mjcf` (:160 MjcfConverter) 둘뿐이다 (isaaclab · isaaclab_assets · isaaclab_tasks grep). MeshConverter 를 만드는 spawner 는 없다.
2. v2 기록기 장면: robot = UNITREE_GO2_CFG (isaaclab_assets/robots/unitree.py:140-142 UsdFileCfg · go2.usd) · terrain "plane" (terrain_importer.py:108 · :223 GroundPlaneCfg · from_files_cfg.py:206 USD 파일) · DomeLight · RayCaster · ContactSensor (velocity_env_cfg.py MySceneCfg). velocity 과제 폴더에 UrdfFileCfg · MjcfFileCfg 없음. 학습 기록 env.yaml 의 robot spawn 도 spawn_from_usd.
3. 그래서 v2 에는 IsaacLab.usd_* 폴더가 없고 isaac_slot 은 자식 종료 0 이어도 95 를 낸다 (가짜 시험에서 재현: 변이 MR11 이 RT8 을 95 로 깬다).
4. 근거가 틀렸을 때의 관문: isaaclab.sim 을 import 하면 converters 가 함께 올라오므로 (sim/__init__.py:29 · converters/__init__.py:19) usd_isolate_run 은 v2 에서도 감싸고 isolate_state.json 을 쓴다. 그것이 없으면 92, assigned.jsonl 에 줄이 있거나 로그에 IsaacLab.usd_ 가 보이면 93. validate_dump.py 가 V2 · V3 · V4 로 다시 본다.
5. v2 는 변환 잠금을 잡지 않는다 (막을 공유 쓰기가 없다 · 위 근거가 맞을 때). 멈춤 파일 · 마감은 실행기가 띄우기 전에 본다.

## 허용 오차 (대조기 · 기록을 보기 전에 정함)

| 항목 | 값 | 근거 |
|---|---|---|
| 관측 칸 | 1e-6 | 계약 5.2 「같은 FP32 계산 1e-6 목표」. 관측은 뺄셈 · 곱셈 · clamp · where 뿐이라 GPU 와 CPU 가 같은 값을 내야 한다 (기대 0) |
| joint target · 기억한 last action · 기본 자세 · 광선 지역 좌표 | 1e-6 | 같은 근거 |
| CPU 재계산 action (`--recompute_action`) | 1e-4 | 행렬곱 합산 순서 차이. 측정이 아니라 사전 설정 (근거 미확인) |
| 이름 · 배치 · 차원 · 이력 길이 | 정확히 같음 | 수치 오차로 넘어갈 수 없다 |

## 계약 · 의뢰 문구와 코드가 다른 곳 (코드를 따랐다)

1. **행동 clip 의 자리.** 계약 2.2 와 의뢰는 `q_default + 0.25 x clip(raw)` 라고 적었다. Isaac Lab 은 clip 을 raw 가 아니라 target 에 건다 (`joint_actions.py:173-178` process_actions: `processed = raw * scale + offset` 뒤 clamp). CTS 는 target 을 [-100, 100] rad 로 자르고 (|raw| 가 약 390 을 넘어야 걸린다 · 계산상 추정) v2 는 clip 이 없다. 두 평가기 모두 RslRlVecEnvWrapper clip_actions 는 None (q_eval_cmdr.py · v2 agent.yaml `clip_actions: null`). 변이 M10 이 이 차이를 잡는다.
2. **offset 은 q_default 가 아닐 수 있다.** CMD-R 평가기 (q_eval_cmdr.py) 는 push 만 끄고 motor zero offset DR (env_cfg.py:296-303 · events.py randomize_action_joint_pos_offset, +-0.035 rad) 을 켜 둔다. 그래서 native target 의 offset 은 reset 마다 q_default + U(-0.035, 0.035) 다. 기록기는 step 마다 `action_offset` 을 남기고 대조기는 그 값을 넘겨 비교한다. 기본 자세로 해석했을 때의 차이는 `info.offset_minus_default` 로만 보고한다 (P0 · R0 는 이 DR 이 꺼진다).
3. **v2 관절 관측은 「12 관절」 이 아니라 「전 관절」.** env.yaml 의 joint_pos_rel · joint_vel_rel 은 params 가 비어 있어 articulation 의 모든 관절을 그 순서로 읽는다. Go2 는 12 개라 차원은 같다. adapter 는 런타임 이름 목록 길이로 차원을 확인한다.
4. **CircularBuffer reset 은 칸을 0 으로 지운다.** 계약은 「첫 표본 반복」 만 적었다. reset 과 다음 갱신 사이에 이력을 읽으면 0 이 나온다. adapter 도 그렇게 둔다 (계약과 모순은 아니고 덧붙임).
5. **생성자의 critic 요구.** 계약 2.2 대로 ActorCriticMoECTS 생성자가 critic 열쇠와 차원 (275) 을 요구한다. act_inference 는 critic 을 읽지 않는다. adapter 의 infer 는 critic 열쇠 없이 부르고 T17 · T18 에서 critic 이 있는 호출과 비트 동일을 확인했다.

## 확인된 것과 미확인

확인됨 (이번에 실행하거나 파일에서 읽음)
- CPU 22 칸 · 변이 21 개 (위).
- E1 model_20000 · foothold-v2.pt 를 CPU 로 strict 적재 (E1 은 params/agent.yaml 의 student_encoder_hidden_dims [512, 256, 256] 로 짓는다 · 클래스 기본 [512, 256, 128] 과 다르다). 두 체크포인트 모두 관측 정규화가 꺼져 있고 정규화 상태 열쇠가 없다.
- 기존 CMD-R 평가 meta (out/cq_off22000_flat_fwd01_off_s1000/meta.json) 의 action_joint_names 가 JOINT_NAMES 순서이고, 관측 · 행동 설정 차이 수가 0.
- IsaacLab gap_training 판 height_scan_with_gap 의 식은 저장소 판과 같다 (읽기만 · 그 파일은 isaaclab 을 import 해서 실행 비교는 안 했다).

미확인
- **adapter 출력이 native 와 같은가** 자체. 기록기를 안 돌렸다. 위 CPU 시험은 코드에서 읽은 규칙을 시험한 것이지 실제 Isaac 출력과의 일치가 아니다.
- v2 의 런타임 관절 순서 (기록기가 남긴다). CTS articulation 순서도 미확인 (adapter 는 이름으로 맞추므로 영향 없음).
- 기록기 두 파일은 py_compile 만 통과했다. Isaac 안에서의 실행 오류 여부 미확인.
- **v2 의 변환 없음은 코드 읽기와 가짜 시험으로만 확인했다.** 실제 Isaac 에서 isolate_state.json 이 쓰이는지 (isaac311 의 Kit 안에서 loader 감싸기가 걸리는지) 는 미확인. cts 쪽은 lead 의 18:55 실제 확인이 있다 (이 세션이 잰 것은 아니다). 안 걸리면 run_dump 가 92 로 알린다.
- **실행기 · 검증기는 가짜 자식으로만 시험했다.** gpu_guard 는 가짜 (NVML 을 안 부른다). 실제 gpu_guard · 실제 Isaac 과의 연결 (로그에 장면 생성 줄 · USD 경로가 찍히는 형식) 은 미확인.
- run_dump 는 cts 실행이 isaac_slot 의 잠금을 기다리는 동안 다른 Isaac 실행 (밤 평가기) 과 경합한다. 대기 시간은 미확인. 마감은 --deadline 으로 준다.
- GPU 관측과 CPU adapter 관측이 비트 동일할 것이라는 기대 (근거는 연산 종류뿐). 재계산 action 허용 1e-4 의 근거.
- 평지 60 step 에서 reset 이 거의 없을 것이라 reset 이후 이력 재충전은 native 자료로 시험되지 않을 수 있다 (`reset_events` 가 0 이면 그 경로는 CPU 시험 T04 만). 평면이라 v2 height 의 miss (+1) 경로도 native 로는 시험되지 않는다 (T10 · T11 만).
- 기록 시각: 상태를 env.step 이 끝난 뒤 읽는다. 관측 계산과 반환 사이에 상태가 안 바뀐다는 전제다 (대조가 통과하면 그것으로 확인된다).
- CMD-R 갈래 체크포인트의 관측 · 행동 설정 동일성은 기존 meta 한 건 (cmdr_s1042_off_u4000 model_22000) 에서만 0 으로 확인. 다른 갈래는 기록기의 종료 3 관문이 막는다.
- 이번 범위 밖 (안 함): 2 단계 P0 · P1 세 칸 진단, WORLD_PATH 명령 변환, terminal pre-reset recorder, P0 manifest, MapABAdapter.
