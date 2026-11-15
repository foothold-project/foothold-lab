> 분류: A/평가 · 공통 평가 계약 CE12-v1 · 1 단계 이식 진단 ① (adapter · native 기록기 · 대조기 · 실행기 · 수집 검증 · 자료 승인)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:42 · 실행기 19:17 · ASTRA 17d 고침 23:46 · 실제 기록 대조 · ASTRA 17f 고침 2026-10-14 01:02 (`date` 로 잼)
> 근거: DESIGN-astra-12-common-eval.md 2.1 · 2.2 · 2.4 · 5.1 · 5.2 · VERIFY-astra-17.md 8 · VERIFY-astra-17d.md 2.5 · 2.6 · 2.7 · 4 · 7 · VERIFY-astra-17f.md 3 · 4 · 6 · lead 지시 19:03 · 20:06 · 23:30 · 00:29 · 실제 기록 out_ce12/native/cts_e1_m20000 (10/14 00:25 · 읽기만) · robot_lab env_cfg.py · actor_critic_moe_cts.py · IsaacLab observation_manager.py · circular_buffer.py · joint_actions.py · ray_caster.py · patterns.py · spawners/from_files.py · terrain_importer.py · _eval/q_eval_cmdr.py · isaac_slot_v3.py · usd_isolate_run_v3.py · gpu_guard.py · foothold-lab models/foothold-v2.env.yaml · sim/eval/gap_observations.py (모두 읽기만)
> 요지: 실제 CTS E1 20000 native 기록 (GPU 1 · 60 step · 일부 reset · 명령 전환) 을 CPU 로 대조하니 관측 · joint target · last action 은 최대 차 0, CPU 재계산 action 은 최대 2.15e-6 (허용 1e-4) 이다. 대조기는 그 기록의 문자열 dims 에서 죽었고 고쳤다. 승인은 실행 당시 출처 (A9) 가 없어 REJECTED 다.
> 상태: CTS native 이식 진단 수치는 이 한 기록에서 통과. 이 기록의 정식 승인은 안 됨 (gpu_guard 해시 미기록 · 그 뒤 기록기 · 실행기 · cells 를 고침). v2 native 기록 0 건

# CE12 1 단계 · 이식 진단 ①

## 실제 기록 대조 결과 (10/14 00:50 · CPU · 원본은 읽기만)

대상: `out_ce12/native/cts_e1_m20000/native.npz` (sha256 c9b9e88d…) · attempt `cts_e1_m20000-20261014-002459-122864` · E1 `model_20000.pt` (c8951b79…) · stand · fwd03 · yawL05 × 4 env · 60 step · env 1 · 6 을 step 29 안에서 reset · env 0 을 관측 40 부터 fwd03 으로 전환. 보고서: `out_ce12/native/cts_e1_m20000/compare_report_20261014-005010.json` (새 파일 · sha256 4337907a…).

| 대조 | 최대 절대차 | 비교 칸 수 | 위치 | 허용 |
|---|---|---|---|---|
| 관측 policy 450 | 0 | 329,400 | 차 없음 | 1e-6 |
| 관측 single_obs 45 | 0 | 32,940 | 차 없음 | 1e-6 |
| joint target (기록한 offset 사용) | 0 | 8,640 | 차 없음 | 1e-6 |
| 기억한 last action | 0 | 8,784 | 차 없음 | 1e-6 |
| CPU 재계산 action (adapter 관측) | 2.15e-6 | 8,640 | step 2 · env 6 · RR_calf_joint | 1e-4 |
| CPU 재계산 action (native 관측) | 2.15e-6 | 8,640 | 같은 칸 | 1e-4 |
| reset 뒤 env 1 · 6 (관측 30~39 · 이력 재충전 구간) | 관측 0 · last action 0 · target 0 · action 1.91e-6 (env 1 step 39 RR_calf) · 1.67e-6 (env 6 step 56 FL_calf) | env 마다 관측 4,500 · action 360 | native 의 첫 관측 last action = 0 | |
| 전환 뒤 env 0 (관측 40~60 · action 20 step) | 관측 0 · target 0 · action 1.43e-6 (step 49 FL_calf) | action 240 | | |

- 관측은 adapter 와 native 가 비트 단위로 같다 (CPU 와 GPU 의 차가 0). action 차 2.15e-6 은 CPU 와 GPU 의 행렬곱 차로 보이며 (adapter 관측과 native 관측이 같아 두 재계산 값이 같다) 허용 1e-4 안이다. 이 1e-4 자체의 근거는 여전히 미확인이다.
- motor offset DR 로 target 이 기본 자세 기준과 다른 크기: 최대 0.0349 rad (기록한 offset 으로 비교해서 차 0).
- CTS articulation 관절 순서는 런타임에서 FL_hip · FR_hip · RL_hip · RR_hip · FL_thigh … (부위별) 로, JOINT_NAMES (다리별) 와 다르다. adapter 는 이름으로 맞춰 차 0 이 났다.
- coverage: reset 2 회 · reset 뒤 action 60 step · 명령 전환 1 회 · 전환 뒤 action 20 step · height miss 미측정 (CTS 기록에는 광선 원자료가 없다 · 미확인 목록에 표시).
- 승인 (validate_dump --approve 와 이 보고서): 수집 22 항목 통과 · A1~A8 통과 · **A9 실패** → **REJECTED**. 실행 당시 해시와 지금 파일:

| 파일 | 실행 당시 | 지금 | |
|---|---|---|---|
| run_dump.py | 7a3046ca… | 075a7fd9… | 다름 (17f 4.3 출처 기록 · 87 추가) |
| cells.py | 9a393d6c… | 6d9f61bb… | 다름 (17f 4.4 switch_step ≤ T-1) |
| dump_native_cts.py | 7b6c3ad2… | a8ada54e… | 다름 (dims 를 int 로) |
| adapters.py | 39c1a293… | 39c1a293… | 같음 |
| isaac_slot_v3.py | 974919b0… | 974919b0… | 같음 |
| usd_isolate_run_v3.py | 30dc2ea9… | 30dc2ea9… | 같음 |
| gpu_guard.py | 기록 없음 | 7fabec30… (파일 수정 시각 10/12 11:58 · 기록보다 앞) | 출처를 해시로 이을 수 없다 |

  이 기록을 정식 승인하려면 코드를 고정한 뒤 같은 요청으로 다시 기록해야 한다 (새 run_dump 가 provenance 를 남긴다). `--code_bundle` 로 실행 당시 해시 묶음을 대도 gpu_guard 해시가 없어서 통과하지 않는다.

### 실제 기록에서 난 오류와 고침

- `compare_native.py` 가 `int(np.prod(x))` 에서 `UFuncNoLoopError (<U2)` 로 죽었다. 원인: 기록기가 meta `obs_layout.dims` 의 numpy 정수를 `json.dump(default=str)` 로 적어 policy · single_obs 의 dims 가 `"30"` 같은 문자열이 됐다 (critic 은 정수). 가짜 기록 시험은 정수를 써서 이 길을 안 밟았다.
- 대조기: 숫자 문자열도 읽고 (`_dim`), 숫자가 아니면 배치 확인 실패로 보고한다 (죽지 않음). 보고서에 `dims_written_as_text` 를 남긴다.
- 기록기 (앞으로): dims 를 `int` 로 적는다 (dump_native_cts.py · dump_native_v2.py).
- 실제 기록 사본으로 도는 시험: test_adapters.py T23 (대조기 · 원본 sha256 고정 · 없거나 바뀌면 실패) · test_run_dump.py VA-real (검증기 · 원본 읽기만). 변이 C04 (옛 int(np.prod)) 가 T23 에 걸린다.

## ASTRA 17f 고침 (10/14 01:02)

| 절 | 결함 (17f 재현) | 고침 | 시험 · 변이 |
|---|---|---|---|
| 3 | 실행기가 v2 공용 registry 를 v3 에 넘김 | lead 가 00:22 `isaac_usd_registry_v3.json` 으로 바꿈 (시험 362 · 467 줄 포함 · 이 판도 그대로) | RT1 · RT7 |
| 4.2 | `--check_approval` 이 attempt 와 파일 해시만 봐서, 승인된 v2 묶음에 cts · E1 체크포인트로 물어도 STILL VALID | 승인 stamp 에 대상 (which · tag · attempt · 정규화한 체크포인트 경로와 sha256 · model) 을 적고, 재확인은 요청이 그 대상과 모두 같을 때만 통과. 같은 내용의 다른 경로 체크포인트도 실패 | VA-ck-target · MV-CKT |
| 4.3 | 실행 당시 코드 해시가 승인과 이어지지 않음 (run.json 해시를 0 으로 바꿔도 APPROVED) | 실행기가 시작 · 끝에 기록기 · adapter · cells · 실행기 · slot · isolate · guard 의 경로와 sha256 을 run.json `provenance` · `provenance_end` 에 남기고, 실행 중 바뀌면 87. 승인 A9: 실행 당시 해시가 모두 있고 · 옛 칸 (run.json · capabilities · meta) 과 모순 없고 · 실행 중 안 바뀌고 · 승인 대상 코드 (`--code_bundle` SHA256SUMS 또는 지금 파일) 와 같아야 통과. 비교 단계 출처 (compare · adapters · cells) 는 A6 와 stamp `compare_provenance` 에 따로 | VA-*-A9 (4 종 × 2) · VA-bundle · RT13 · VA-real · MR17 · MR18 · MV-A9 · MV-A9b~d |
| 4.4 | 마지막 관측의 전환도 전환 경로 승인으로 셈 (action 0 개) · height miss 미측정이 미확인 목록에서 빠짐 | `cells.fixture_problem` 이 switch_step 을 1..T-1 로 제한 (실행기 · 기록기 · 승인 A2 가 같은 규칙). coverage 에 reset 뒤 · 전환 뒤 action step 수를 세고 A7 · A8 은 그 수가 0 이면 보류. height miss 는 「미측정 (None)」 과 「0 회」 를 따로 미확인 목록에 넣음. 보고서 `focus` 에 reset 뒤 · 전환 뒤 관측 · target · action 의 최대 차와 위치 | RT6 (switch 60/60 거절) · VA-terminal · VA-terminal-reset · VA-cov · T23 · C05 · C06 · MV-A7p · MV-A8p · MV-A2f |

## 무엇을 만들었나 (모두 `_eval/ce12/` · 공용 파일 수정 0)

| 파일 | 하는 일 |
|---|---|
| `adapters.py` | `CTSStudentAdapter` · `V2Adapter` · `decode_action` · `write_signature`. 순서 · scale · clip · 이력 · 기본 자세는 원래 설정 파일을 읽어 정한다 |
| `cells.py` | 기록 칸 표 · 강제 reset · 명령 전환 규칙 (switch_step ≤ T-1) · 기대 명령 시간열 |
| `dump_native_cts.py` · `dump_native_v2.py` | (Isaac · lead 실행) native 기록기. 선택: 일부 env 강제 reset · 한 env 명령 전환. meta 에 schedule · coverage. dims 는 int |
| `compare_native.py` | (CPU) 칸마다 대조 · 첫 불일치와 최대 차 위치 · 읽은 입력 해시 · coverage · focus |
| `run_dump.py` | 실행기 v2. slot v3 -> gpu_guard -> usd_isolate_run v3 -> 기록기 · 변환 예상 cts 1 · v2 0 · 기록기 인자 허용 목록 · 출력 위치 확인 (88) · 실행 출처 기록 · 실행 중 코드 변경 87 |
| `validate_dump.py` | 수집 22 검사 (COLLECTED) · 승인 9 검사 (APPROVED · REJECTED · PENDING) · 승인 대상과 요청을 대조하는 재확인 |
| `test_adapters.py` · `mutate_adapters.py` | 시험 23 칸 (T23 실제 기록) · 변이 24 개 |
| `test_run_dump.py` · `mutate_run_dump.py` | 시험 132 칸 (RT 13 · VT 68 · VA 51) · 변이 65 개 (실행기 18 · 검증기 47) |

### adapter 가 지키는 것 (코드 위치)

- CTS policy 450: term 마다 이력 10 칸을 oldest -> newest 로 편 뒤 term 끼리 잇는다 (observation_manager.py:424 · 433). 최신 명령 87:90 · single 6:9.
- 각 term 은 clip [-100, 100] 다음 scale (ang vel 0.25 · joint vel 0.05) (observation_manager.py:404-407).
- reset 뒤 첫 갱신은 그 표본을 10 칸 모두에 (circular_buffer.py:136-139) · 기억한 raw action 0 (action_manager.py:364-365). 실제 기록에서 reset 뒤 관측 30~39 차 0 으로 확인.
- 관절은 이름으로 맞춘다. v2 는 런타임 이름 목록을 반드시 인자로 받는다.
- v2 235: scale 없음 · height = clip(where(유효, pos_w_z - hit_z - 0.5, +1.0), -1, 1) · pos_w 에 광선 시작 +20 m 없음 · 187 광선은 x 가 가장 빨리.
- 행동: target = clip(raw x scale + offset). 실제 기록에서 기록한 offset 으로 차 0.
- 추론: CTS 는 `act_inference` 에 policy · single_obs 만.

## 시험 결과 (2026-10-14 01:01 · CPU · isaac311-moects · GPU 가림)

- `test_adapters.py`: **23/23 PASS** (T23 실제 기록 사본) · `mutate_adapters.py`: **24/24 CAUGHT**.
- `test_run_dump.py`: **132/132 PASS** (RT 13 · VT 68 · VA 51). 관문은 실제 v3 두 파일의 사본 (isaac_slot_v3.py 974919b0… · usd_isolate_run_v3.py 30dc2ea9…). 가짜는 guard 와 기록기뿐. VA-real 은 실제 기록을 읽기만 한다.
- `mutate_run_dump.py`: **65/65 CAUGHT**. 그중 MV-A7b 는 처음에 놓쳤다: reset 0 회 분기를 지워도 「reset 뒤 action 0」 분기가 같은 보류를 내서 결과가 같았다. 보류 사유의 구분 (「한 번도 없다」 와 「뒤의 action 0」) 을 VA-pending 에 넣어 잡았다.

## lead 가 돌릴 명령 (10/14 판 · run_dump.py 로만 띄운다)

```bash
cd C:/isaac/ext/go2_rl_robotlab/_eval
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
V2=C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.pt
FIX="--reset_envs 1,6 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03"   # reset · 전환 경로 (승인 A7 · A8)
T=cts_e1_m20000_r2   # 새 tag (옛 기록은 그대로 둔다)

"$PY" ce12/run_dump.py --which cts --checkpoint $E1/model_20000.pt --tag $T --dry_run -- $FIX
"$PY" ce12/run_dump.py --which cts --checkpoint $E1/model_20000.pt --tag $T -- $FIX
"$PY" ce12/validate_dump.py --which cts --tag $T --checkpoint $E1/model_20000.pt --attempt <attempt> --stamp
"$PY" ce12/compare_native.py --dump out_ce12/native/$T/native.npz --recompute_action
"$PY" ce12/validate_dump.py --which cts --tag $T --checkpoint $E1/model_20000.pt --attempt <attempt> --approve --compare_report out_ce12/native/$T/compare_report_<시각>.json [--code_bundle <SHA256SUMS>]
"$PY" ce12/validate_dump.py --which cts --tag $T --checkpoint $E1/model_20000.pt --attempt <attempt> --check_approval
# v2 도 같은 순서 (--which v2 · 기록기는 isaac311 · 변환 예상 0)
```

- 승인 A9 는 실행 당시 코드와 승인 대상 코드가 같아야 한다. 기록과 승인 사이에 ce12 · 관문 파일을 고치면 REJECTED 가 된다. 고정 묶음으로 승인하려면 `--code_bundle` 에 그 SHA256SUMS 를 준다.
- 종료 코드 (실행기): 0 · 2 거절 · 98 멈춤 · 마감 · slot v3 의 89 (변환 예상 위반) · 90 · 91 · 94~97 · 자식 · guard 99 · 88 출력 위치 · 87 실행 중 코드 변경.
- 종료 코드 (검증기): 0 COLLECTED (와 APPROVED) · 1 INVALID · REJECTED · 승인 무효 · 3 PENDING.
- 기록기 인자 허용 목록 · 출력 배치 · v2 변환 예상 0 의 근거는 23:46 판과 같다 (run_dump.py 머리).

## 허용 오차 (기록을 보기 전에 정함 · 실제 기록 뒤에도 바꾸지 않음)

| 항목 | 값 | 실제 기록 |
|---|---|---|
| 관측 · joint target · last action · 기본 자세 · 광선 좌표 | 1e-6 | 0 |
| CPU 재계산 action | 1e-4 (근거 미확인) | 2.15e-6 |
| 이름 · 배치 · 차원 · 이력 길이 · 명령 시간열 | 정확히 같음 | 같음 |

## 계약 · 의뢰 문구와 코드가 다른 곳 (코드를 따랐다)

1. 행동 clip 은 target 에 (joint_actions.py:173-178) · CTS [-100, 100] rad · v2 없음.
2. offset 은 motor offset DR 때문에 기본 자세가 아닐 수 있다 (실제 기록 최대 0.0349 rad) · 기록한 offset 으로 비교.
3. v2 관절 관측은 전 관절 (Go2 12 개).
4. CircularBuffer reset 은 칸을 0 으로 지운다.
5. 생성자는 critic 을 요구하지만 act_inference 는 읽지 않는다.
6. (10/14) 승인 단계의 출처 연결은 「승인 시점 파일을 해시」 가 아니라 「실행 당시 해시 = 승인 대상 코드」 로 바꿨다 (17f 4.3).

## 미확인

- **v2 native 기록 0 건.** v2 의 adapter 일치 · 예상 0 의 실제 잠금 해제 · isaac311 Kit 안의 감싸기는 미확인.
- CTS 는 이 한 기록 (60 step · 평지 · 12 env) 만. 다른 지형 · 긴 episode · 자연 종료 (넘어짐) 뒤 reset · 경계 clip · height miss 경로는 native 로 안 봤다.
- action 허용 1e-4 의 근거 (이번 실측 2.15e-6 은 한 기록의 값).
- 이 기록의 정식 승인: gpu_guard 해시 미기록 · 그 뒤 코드 변경으로 불가. 새 기록이 필요하다.
- 기록 중 강제 reset 은 time-out 경로로 나왔다 (reset_after_step · time_out 둘 다 확인). 자연 종료 (terminated) 경로는 0 회.
- 실제 gpu_guard (NVML) 의 시작 전 여유 검사 · 장치 UUID 일치 (17d §3) 는 이 세션이 재지 않았다 (guard 0 은 lead 보고).
- slot v3 · isolate v3 가 더 바뀌면 test_run_dump.py 를 다시 돌려 새 사본으로 확인 (끝 줄 sha256).
- 17f §3 의 v2 registry 읽기 전용 대조 · 상대 로그 스캔 범위 확인은 이 세션의 범위 밖 (lead 가 registry 이름만 바꿈).
- 범위 밖: 2 단계 P0 · P1 진단 · WORLD_PATH · terminal pre-reset recorder · P0 manifest · MapABAdapter.
