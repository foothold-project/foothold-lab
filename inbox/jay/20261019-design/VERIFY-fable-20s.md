> 분류: A/정책학습 · 설계 반영 · 검증 (fable 20s · lead 답 8 항 반영 · 판정식 몬테카를로 · 공식 저장소 재측)
> 작성: fable 세션 · lead 의뢰 20s · 10/20 17:1x
> 근거: lead 20s 답(SendMessage 10/20 17:0x) · `evidence/baselines/axis1_cells.csv`(S0 · sonnet 측정 · lead 재계산 확인 e0a77b38) · 51 §2 「축 1 한 판 27 분」 실측 · 세션 scratchpad `mc20s.py` · `mc20s_asym.py`(numpy 이항 표집 20,000 회 · 시드 20261020 · 777 · CPU) · sonnet-code 커밋 7c072ced · 5a2a7257 · e9460aac · 0fb4c111(`git show` · 파일 읽기) · 공식 저장소 얕은 clone(fable 10/20 17:0x · unitree_sdk2 d1abf00 · unitree_rl_lab 4960b84 · unitree_sdk2_python 814556d · 읽기만, 설치 · 실행 없음) · 43-COMMS-CONTROL.md(63630519) · VERIFY-fable-20m · 20n · 20o · 20q
> 요지: (1)(2) 팀장 식(A 합산 하한 ≥ −0.03 · B 칸별 상한 < −0.10 · z 1.96)은 칸당 n 100 에서 E1 · NVIDIA 분포의 같은 정책 재측정 통과가 0.79 라 목표 미달이고, **n 200 이면 0.987 · 5 %p 검출 1.000 · 25 %p 한 칸 검출 최저 0.904** 로 세 목표를 넘는다(기준 판도 200 판이어야 함). 식은 그대로 두고 n 200 을 골라 41 §8 에 표와 함께 적었다(팀장 N-6 「칸당 100 판 유지」 변경이라 팀장 확인). (3)~(7) 은 19 파일에 반영. (8) sonnet 의 공식 저장소 주장 넷은 clone 원문 줄로 모두 확인(FixStand 값의 자리만 config.yaml 로 정정)
> 상태: 완료 · 미커밋(lead 커밋) · 코드 · 학습 · GPU · Kit 없음

# VERIFY-fable-20s · lead 답 8 항 반영

## 1. 판정식 몬테카를로 (lead 1 · 2)

**설정**: 모집단 = S0 실측 칸 성공률(NVIDIA · v2 · E1 세 판) × 관문 칸 집합 셋 = 아홉 조합. S1-scan 판정 26 칸(overall) · 범위 안 32 칸(overall · S1-b · S2-a · S4) · F26 사전 (1) 이어진 16 칸(S 생존 = csv `S_rate`). 기준 판 · 새 판을 같은 n 으로 독립 이항 표집. 가설 셋: 같은 정책 재측정(H0) · 모든 칸 −5 %p(0 아래는 0) · 성공률 ≥ 0.8 인 칸 하나만 −25 %p(해당 칸을 하나씩 떨어뜨려 재고 최저값 · 중앙값). 격자: (A) 9 꼴(합산 Newcombe 하한 허용폭 0.03 · 0.04 · 0.05 × z 1.96 · 1.645, 점 추정 0.02 · 0.025 · 0.03) × (B) 9 꼴(칸별 Newcombe 상한 허용폭 0.10 · 0.15 × z 1.96 · 1.645 · 1.28, 점 추정 0.15 · 0.20 · 0.25) × n 100 · 200 · 300 = 243 조합. 목표(lead): 재측정 통과 ≥ 95 % · 5 %p 검출 ≥ 95 % · 25 %p 한 칸 검출 ≥ 80 %, 아홉 조합 전부.

**결과(팀장 식 · 아홉 조합의 최악값)**:

| 식 | 칸당 n | 재측정 통과 | 5 %p 검출 | 25 %p 한 칸 검출 최저 / 중앙 | 목표 | 범위 안 32 칸 GPU / 판(가정) |
|---|---|---|---|---|---|---|
| (A) 하한 ≥ −0.03 · (B) 상한 < −0.10 · z 1.96 | 100 | 0.792 | 1.000 | 0.804 / 0.877 | 미달 | 약 22 분 |
| 같은 식 | **200** | **0.987** | 1.000 | **0.904** / 0.976 | **충족** | **약 44 분** |
| 같은 식 | 300 | 1.000 | 1.000 | 0.979 / 0.998 | 충족 | 약 66 분 |
| 대안 (A) 점 추정 d̄ ≥ −0.025 · (B) 상한 < −0.10 · z 1.28 | 100 | 0.971 | 0.980 | 0.848 / 0.935 | 충족(여유 작음) | 약 22 분 |

n 200 · 팀장 식의 조합별 값:

| 판 / 칸 집합 | 재측정 통과 | 5 %p 검출 | 25 %p 한 칸 최저 / 중앙 (해당 칸 수) |
|---|---|---|---|
| v2 / 26 · 32 · 16 | 1.000 · 1.000 · 1.000 | 1.000 | 0.998 / 1.000 (24) · 0.997 / 1.000 (30) · 1.000 / 1.000 (16) |
| E1 / 26 · 32 · 16 | 0.987 · 0.992 · 1.000 | 1.000 | 0.925 / 0.978 (17) · 0.919 / 0.976 (17) · 0.997 / 1.000 (16) |
| NVIDIA / 26 · 32 · 16 | 0.998 · 1.000 · 1.000 | 1.000 | 0.912 / 1.000 (18) · **0.904** / 1.000 (18) · 0.974 / 1.000 (15) |

n 100 에서 떨어지는 곳: E1 26 칸 0.795 · E1 32 칸 0.803 · NVIDIA 26 칸 0.792 · NVIDIA 32 칸 0.866(재측정 통과). v2 는 전부 1.000.

**읽은 것**:
- n 100 이 안 되는 원인은 (A) 다. 중간 성공률 칸이 많은 판(E1 32 칸 평균 0.67 · 0.2~0.8 칸 9 개, NVIDIA 평균 0.57)에서 합산 구간의 반폭이 약 0.025 라 허용폭 0.03 과 거의 같다. 같은 정책을 다시 재도 d̄ 가 −0.005 아래로 내려가는 약 1/3 이 (A) 에서 걸린다. lead 가 본 「66 % 통과」 와 같은 현상이고 B′ 탓이 아니다. (B) 만 떼어 보면 n 100 에서도 재측정 통과 ≥ 0.987.
- 25 %p 한 칸 검출은 0.8 → 0.55 칸이 가장 어렵다(n 100 에서 0.80 · 200 에서 0.90 · 300 에서 0.98). 1.0 → 0.75 칸은 n 100 에서도 0.96.
- 기준 판을 S0 의 100 판 그대로 두고 새 판만 200 · 300 으로 재면(비대칭 · `mc20s_asym.py`) E1 26 칸 재측정 통과 0.918 · 0.951, NVIDIA 26 칸 0.948 · 0.977 로 목표에 못 미친다. 그래서 **기준 판도 200 판**: v2 범위 안 32 칸 1 회(S1-scan 기준), S1a-blind-v1 · S2-G0 는 처음부터 200 판.
- 243 조합 중 목표를 넘는 것은 n 100 에서 5 개(모두 (A) 점 추정 또는 허용폭 0.04 · 0.05 + (B) z 1.28), n 200 에서 36 개, n 300 에서 49 개.
- GPU 시간은 51 §2 「48 칸 × 100 판 약 27 분(E1 실측)」 을 에피소드 길이(12 · 6 · 4 s) 비례로 나눈 **가정**: 범위 안 32 칸 100 판 ≈ 22 분 → 200 판 ≈ 44 분 / 판, 이어진 16 칸 200 판 ≈ 22 분. 관문 하나 = 새 판 44 분 + 기준 판 44 분(재측 1 회) ≈ 1.5 h, 다섯 관문 약 5~6 h.

**고른 것**: 식은 N-6 그대로(허용폭 0.03 · 0.10 · z 1.96) · **칸당 n 200** · 기준 판도 200 판. n 100 대안은 여유가 작고(0.97 · 0.98 · 0.85) 검정력이 낮아 안 골랐다. n 300 은 GPU 22 분이 더 들고 이득은 25 %p 한 칸 검출 0.90 → 0.98 뿐. **팀장 N-6 의 「칸당 100 판 유지」 를 바꾸는 것이라 팀장 확인**.

**적은 자리**: 41 §2 37 행 · §8 등록값 · §8 새 bullet(표 · 까닭 · 비대칭 · GPU) · §9 다섯 관문 행 · §10 gates 필드 n 200 · §11 L0 n 200 예(같은 Newcombe 함수로 계산: (5200, 5200, 5200, 5200) → L −0.0007 · (4012, 5200, 4012, 5200) → L −0.0161 · (k, 200, 200, 200) 은 k ≤ 170 에서 큰 하락(U −0.1032) · 171 통과(−0.0989) · (110, 200, 160, 200) → U −0.1592 · (160, 200, 180, 200) → U −0.0300) · §11 열린 항목 · 51 §2 GPU 행 · 90 D54.

## 2. 반영 표 (lead 3~7)

| lead | 반영 자리 | 무엇을 |
|---|---|---|
| 3 다른 곳 11 건 | 21 §96 · 52 28 · 49 · 50 · 62 · 65 · 55 51 · 56 · 60 32 · 70 65 · 125 · DAILY-PLAN 33 | 옛 「Newcombe 하한 < −0.05 · 진짜 하락 0」 → 「41 §8 (A)(B) · 칸당 200 판 · N-6」, 「heading 75 %」 → 「50 % · N-7」. 55 51 행(대조판 관문 문장)은 lead 목록 밖이나 같은 표현이라 같이 고침 |
| 4 통신 · 관제 정본 43 | 42 T0 행 ④ · 42 §1.1 통째(체크리스트 표 · 장면 표 제거 → 43 §3 · §4 · §5 를 가리키는 세 문장 + 묶음 규칙) · 42 §2 상태기계 bullet(C3 참조) · 23 §4 deadman 행 · §10 | 「④(43 §4 C1~C9) 통과 전 T6 금지」 유지 |
| 5 31 날짜 · 「제때」 | 31 §3 표 머리 · 권한 문단 · §10 | 「lead 제안 · 팀장 확인 대기」 표시. 「제때」 = 판단층 조언이 상황 발생 뒤 0.5 s 안 도착(**가정** · lead 20s). 위험 장면 집계는 가정 그대로 |
| 6 deploy.yaml | 13 §6 수출 행 | `exported/policy.onnx`(sonnet `deploy/export.py` · obs 495 · opset 17 · 원본과 1e-5) + `params/deploy.yaml` 칸 이름 전부(sonnet `deploy/record_isaac.py` 69~88 행 · 공식 `export_deploy_cfg.py` 와 같은 꼴) |
| 7 20m 코드 넷(sonnet 7c072ced · 5a2a7257) | 14 §3 41 행 · §4 105 행 · §5 116 행 · 15 §4 71 행 · 16 §7 85~86 행 | 깃발 열 0.5 · 1.5 · 2.5 · 3.5 m(코드 `straight_flag_line` 259~269 행 · lead 확정) · 깃발 속도 커리큘럼 `update_flag` · 제자리 회전 시간 제외 `judge_flag`(걷는 시간 비율 · 25 % 미만 제외는 가정) · 켜짐 비율 로그 `penalty_log.py` · A/B 키 |
| 7 20m 문서 넷(코드대로) | 13 §2 29 행 · 14 §2 28 행(관측 배율 없음) · 17 §7 90 행(투영 중력 각 1.5 rad) · 17 §9 103 행(21.66) · 13 §6 99 행(task 이름 S1a-scan · S1a-blind · S2-G0 · G1 · G3 · 별칭 S2) | `s1_env_cfg.py` 83~90 · 152~153 · `s1_ppo_cfg.py` 16 · `tasks/__init__.py` 9 · 22 · 30 행 |
| 7 20n ② ④ ⑫ · 20o ④ 채택 | 12 §3 43 행 · §12 ② ④ ⑫ 행 · 15 §4 61 행 | ② 3×3 s1 p1 · 활성화 없음(가정) → rl 코드 101 행 수정 대기 / ④ prop 토큰 자리 출력만(코드 그대로 · 가정, LocoTransformer 식은 대안 기록) / ⑫ H^f 도 base z 기준(H^b 와 같은 틀) / 20o ④ 고무작위 열 r = 레벨 비례(L / 9 · 레벨 9 = START 최대값 · 선행 284 행 꼴) · 저무작위 r = 0 유지 → sonnet 코드 수정 대기 |
| 기록 | 90 D54 · §2 닫힌 것 | lead 20s 8 항 한 행 · 팀장 확인 둘(판정 n 200 · 31 날짜) |

19 파일 85 + / 90 − · em dash 0 · LF · 상태 줄 stamp 19.

## 3. 공식 저장소 재측 (lead 8 · sonnet 7b5cf869 주장 넷)

fable 이 10/20 17:0x 에 얕은 clone(depth 1 · 읽기만)을 떠서 원문 줄을 봤다. 세 저장소 HEAD 가 sonnet 이 적은 커밋과 같았다(unitree_sdk2 d1abf00 2026-10-15 · unitree_rl_lab 4960b84 2025-11-19 · unitree_sdk2_python 814556d 2026-09-21). unitree_rl_lab 은 g1 dance 파일 몇 개가 Windows 경로 길이로 체크아웃 실패했으나 go2 · include 파일은 전부 있음. unitree_mujoco 는 이번 넷에 없어 안 땄다.

| # | sonnet 주장 | 원문 | 판정 |
|---|---|---|---|
| 1 | unitree_sdk2 는 Ubuntu 20.04 전제 | `unitree_sdk2/README.md` 5 행 「* OS (Ubuntu 20.04 LTS)」 · 17 행 「install the required packages on Ubuntu 20.04」 | **확인** |
| 2 | SDK 관절 순서 FR FL RR RL(hip thigh calf) | `unitree_rl_lab/source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py` 122~127 행 `joint_sdk_names=["FR_hip_joint", "FR_thigh_joint", "FR_calf_joint", "FL_…", "RR_…", "RL_…"]` · `utils/export_deploy_cfg.py` 25~36 행이 `joint_ids_map` · `step_dt` · `stiffness` · `damping` · `default_joint_pos` 를 씀 | **확인** |
| 3 | FixStand qs 0 → 1.36/−2.65 → 0.8/−1.5 · kp 60/80/80 · kd 5/4/4 · Passive mode 1 · kd 3 · `bad_orientation(1.0)` 이면 Passive | 값은 `deploy/robots/go2/config/config.yaml`(Passive mode 1 · kd 3, FixStand kp [60, 80, 80 …] · kd [5, 4, 4 …] · ts [0, 1, 2] · qs [[], [0.0, 1.36, −2.65 …], [0, 0.8, −1.5 …]]) 에 있고 `include/FSM/State_FixStand.h` 16 · 23~24 · 46 행이 읽어 선형 보간. `deploy/robots/go2/src/State_RLBase.cpp` 20~21 행 `isaaclab::mdp::bad_orientation(env.get(), 1.0)` → `"Passive"`. `include/isaaclab/envs/mdp/terminations.h` 10~15 행: acos(−g_z) > limit_angle(기본 1.0) | **확인** · 자리 정정: 값은 State_RLBase.cpp 가 아니라 config.yaml(42 §1.2 · 23 §4 의 「공식 0.0/0.8/−1.5」 는 그대로 맞음) |
| 4 | 공식 관측은 base_ang_vel · projected_gravity · joint_pos(_rel) · joint_vel_rel · last_action · velocity_commands · gait_phase, history_length 지원, base_lin_vel · 높이 스캔 없음 | `deploy/include/isaaclab/envs/mdp/observations/observations.h` 의 `REGISTER_OBSERVATION` 8 개: base_ang_vel · gait_phase · joint_pos · joint_pos_rel · joint_vel_rel · last_action · projected_gravity · velocity_commands(base_lin_vel · height_scan 없음). `manager/observation_manager.h` 131 행 `history_length = yaml["history_length"].as<int>(1)`(항마다) · 72~74 · 121~122 행 `use_gym_history` | **확인** |

덤으로 본 것: `unitree_rl_lab/README.md` 88~140 행 Deploy 절 = unitree_mujoco sim2sim → `./g1_ctrl --network eth0`(go2 는 `go2_ctrl`), `unitree_sdk2_python/unitree_sdk2py/utils/crc.py` 30 행 `if self.platform == "Linux"` 분기(sonnet 의 「Windows 는 파이썬 CRC」 와 일치). 설계 42 §1.2 · 23 §1 의 「sonnet 7b5cf869」 출처 표기는 유지했고 「미재측」 은 이 문서로 닫힌다(42 · 23 본문은 안 바꿈 · 값이 같음).

## 4. 가정 · lead 가 정할 것

- **팀장 확인 둘**: 판정 칸당 n 100 → 200(N-6 「100 판 유지」 변경) · 31 §3 날짜.
- 20s 가 새로 둔 가정: GPU 시간 비례 환산(27 분 실측 기준) · 「제때」 0.5 s(lead) · `judge_flag` 걷는 시간 25 % 미만 제외(sonnet) · 20n ④ prop 토큰 자리(코드 그대로) · ⑫ base z 기준 · 20o ④ 레벨 비례 r = L / 9(선행 284 행의 꼴을 START 최대값에 맞춘 것 · 정확한 선행 곡선은 미기재).
- 코드 수정 대기(문서만 바꿈): rl `start_perception.py` 101 행 1×1 → 3×3(②), sonnet `sparse_terrains.py` 28~30 · `start_sheet.py` 117~119 · 129~133 행 고무작위 r 레벨 비례(20o ④), 평가 도구 `compare.py` 의 `newcombe_bounds` 와 gates-v1.json n 200(아직 파일 없음).
- 20q 때 lead 판단으로 남긴 「(A) 합산 식 선택」 은 그대로 가정(몬테카를로도 이 식으로 돌렸다).
- 몬테카를로 한계: 칸 사이 독립 이항 가정(같은 지형 10 env 의 운 공유 · 시드 고정은 모델에 없음) · 모집단은 S0 세 판뿐(S1 · S2 판의 분포는 다를 수 있음 · S1-blind 는 E1 과 NVIDIA 사이로 예상) · 5 %p 하락을 0 아래로 못 내리는 칸(성공률 0.00~0.05)은 「하락 없음」 으로 들어감.

## 5. 기록 (판정 아님)

- 미커밋(lead 커밋) 20 파일: 설계 12 · 13 · 14 · 15 · 16 · 17 · 21 · 23 · 31 · 41 · 42 · 51 · 52 · 53 · 55 · 60 · 70 · 90 · DAILY-PLAN-1020-1024 + VERIFY-fable-20s.
- 몬테카를로 스크립트 · 결과 json 은 세션 scratchpad(`mc20s.py` · `mc20s_results.json` · `mc20s_asym.py`)에만 있다. 저장소에 둘지는 lead 판단(둔다면 `evidence/baselines/` 옆 · 코드라 fable 은 안 넣음).
- 공식 저장소 clone 은 scratchpad `official/` 에 읽기 전용으로 있다. 설치 · 빌드 · 실행 없음.
- 코드 · 학습 · GPU · Kit · 커밋 없음.
