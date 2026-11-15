> 분류: A/정책학습 · 조사 (S2 코드 확인 · 논문 · AME-2 저장소) 와 다음 실험 설계안 (제안 · 결정은 팀장)
> 작성: 오흥재 (lead 세션 · Claude 조사)
> 근거: S2 묶음 코드 `C:/Users/AI-WS01/s2_lab/s2_step29a_run/frozen_delivery/bundle/` (파일 · 행은 본문) · S2 학습 기록 `updates.jsonl` 과 체크포인트 0 · 2000 (이 조사가 직접 읽어 잼) · S2 평가 `s2_step32_run/results_u2000/S2-AB-UPDATE2000.json` · `PAPERS-architecture.md` · `SURVEY-star-code.md` · `docs/research/20261007-ame2-go2-v1-v6.md` · `leggedrobotics/ame2_minimal` @8beb9a68 · `Kitjesen/ame2` @2e989fa7 · 논문 원문 (절 · 표 번호는 본문)
> 요지: S2 B 는 이미 「지도 encoder + 몸 상태 encoder → 관절 행동」 꼴이었고 지도 encoder 도 학습됐다. 얼린 것은 몸 상태 encoder 다. 실패를 가른 것은 구조보다 학습 방식(눈 먼 부모에 0 으로 시작하는 지도 길을 붙여 E1 학습량의 1.25 % 로 미세조정 · 첫 갱신 KL 40 · 명령 ±0.5 m/s 로 학습하고 1.0 m/s 로 평가)이다. 다음 판은 지도와 몸 상태를 처음부터 함께 학습하고 발 디딤 보상과 보행 위상 관문을 단다. AME-2 껑충 보행은 2 족 코드가 공개되기 전 자체 구현에서도 나왔고, 코드로 확인되는 가장 직접적인 후보는 「고저차 30 cm 이상이면 도약 벌점이 꺼지는」 보상이다
> 상태: 초안 · 2026-10-18 · lead 확인 전 · 커밋 · 이슈 댓글 안 함

# 높이 지도로 발 디딤을 고르는 구조: S2 에서 배운 것, 논문들, 다음 실험

## 0. 결론 먼저 (다섯 줄)

1. **S2 B 는 구조로는 이미 「지도 encoder + 몸 상태 encoder → 관절 행동」 이었다.** 지도 374 열은 지도 encoder(MLP 374 → 128 → 64)를 거쳐 actor 첫 층에 더해졌다. `full_freeze` 가 얼린 것은 **몸 상태 encoder(MoE student encoder)** 이고, 지도 encoder 는 2,000 갱신 동안 학습됐다(첫 층 가중치 노름 6.55 → 10.77, 이 조사가 체크포인트에서 잼). 「지도 쪽이 시드 7 무작위값으로 얼어 있었다」 는 사실이 아니다. 그러니 「구조가 없다」 보다 「두 encoder 를 처음부터 함께 배우지 않았다」 가 정확하다 (2 절).
2. **S2 가 논문들과 가장 크게 다른 것은 학습 방식이다.** 눈 먼 부모(E1)에 0 으로 시작하는 지도 길을 붙였고, 학습량은 E1 의 1.25 %(4,915 만 step)였고, 첫 갱신에서 정책이 크게 흔들렸고(KL B 40.1 · A 22.6), 탐색 잡음 std 가 0.28 → 0.48 로 커졌고, 학습 명령은 ±0.5 m/s 였는데 평가는 1.0 m/s 였다. 학습률도 설계 문서 권고(부모 마지막 0.00017)가 아니라 0.001 로 돌았다 (1 절).
3. **gap · 징검다리를 건너는 지형 인지 논문들은 지도 입력을 처음부터 넣고 함께 학습한다.** 발 디딤 자리는 대부분 관절 행동 안에서 「저절로」 나오고 보상(발 가장자리 · 발 중심 · stumble)으로 다듬는다. 이 조사가 읽은 36 편 안에서 발 디딤을 명시적인 출력으로 내는 것은 계층형(planner 가 발 자리를 정하고 RL 이 따라감) 다섯 편뿐이다 (4 · 5 절).
4. **AME-2 껑충 보행은 「2 족 원본」 이 없어도 나왔다.** 팀원 자체 구현(9/24 v1 · 9/30 v11)에서 이미 대각 지지 0 % 대 · 반복 도약이 기록됐고, 그때는 G1 공개 코드(첫 커밋 10/05)가 없었다. 논문과 공식 코드의 보상은 「고저차 30 cm 미만일 때만 도약 벌점」 이고 보행 위상 보상이 없다. 험지 비율이 큰 학습에서는 도약이 거의 공짜다. 평지 재학습으로 보통 보행이 돌아온 것과도 맞는다. 팀원 최신 코드(v15)는 RunPod 볼륨에 있어 열지 못했다 (`미확인`, 6 절).
5. **제안(결정은 팀장):** 지도 encoder 와 몸 상태 encoder(속도 · 접촉 추정 포함)를 **처음부터 함께** 학습하는 새 판(N 판). 지형 curriculum 은 MARG 의 Go1 치수(Go2 와 같은 크기급), 보상은 E1 15 항 + 발 디딤(`feet_center_any9_v1`, 이미 CPU 구현) + stumble + feet air time, 보행 위상 관문을 결과 전에 등록. D435i 는 잡음 → 시야 · 기억 → depth student 순서. 한 판 약 12 시간(추정, E1 실측 처리량 기준), 대조 두 판 · 시드 둘이면 약 2 일 (7 절).

---

## 1. S2 가 다음 설계에 주는 교훈 (무엇을 피해야 하나)

아래 숫자는 이 조사가 S2 학습 기록과 체크포인트를 직접 읽어 잰 것이다. 평가 숫자는 lead 기록(NIGHT-PLAN 10/18 02:32)과 결과 파일을 옮겼다.

| # | S2 에서 본 것 | 근거 | 다음 판에서 피할 것 |
|---|---|---|---|
| 1 | **눈 먼 부모에 지도 길을 0 으로 붙였다.** 부모 E1 은 지형을 안 보고 2 만 iteration 을 배웠다. 지도 투영 층은 0 에서 시작했다 | `s2_policy.py:163-168` · 설계 `DESIGN-s2-ab-v1.md` | 지도를 쓰는 기술(발 자리 고르기)은 지도와 함께 처음부터 배우게 한다. 붙이기를 다시 쓰려면 학습량 · 얼림 범위부터 바꾼다 |
| 2 | **학습량이 E1 의 1.25 %.** S2 한 판 = 2,000 갱신 × 24 step × 1,024 env = 4,915 만 transition. E1 = 20,000 × 24 × 8,192 = 39.3 억 | manifest 인자 · E1 `agent.yaml` | 새 기술을 배우는 판은 E1 과 같은 자릿수의 학습량을 잡는다 |
| 3 | **첫 갱신에서 정책이 크게 흔들렸다.** 갱신 1 의 평균 KL 이 B 40.1 · A 22.6 (그 뒤 0.014 근처). 학습률이 첫 minibatch 뒤 0.0015 로 올랐다가 같은 갱신 안에서 바닥 1e-5 까지 내려갔다 | `updates.jsonl` 첫 줄 `kl` · `lr_path` (A · B) | 이어 학습이면 부모 마지막 학습률 · warm-up · Adam 상태 이어받기 중 하나를 쓰고, 갱신 1 의 KL 상한을 관문으로 건다 |
| 4 | **학습률이 설계 권고와 달랐다.** 설계(`DESIGN-s2-ab-v1.md:40`)와 ASTRA 17v(`VERIFY-astra-17v.md:185`) 는 부모 마지막 값 0.000170859375 를 권했고, 작업서(`TASK-codex-worker-s2-B-short-single-17af.md:31`)는 「배관용 LR 0.001 을 short 기본값으로 복사하지 않는다」 고 적었다. 실제 manifest 와 요청 파일은 `--lr 0.001` | `runs/shortB-*/in/manifest.json` · `bundle/request_short_A.json` · `request_short_B.json` | 실행 인자를 설계 표와 기계적으로 대조하는 관문. 바뀐 경위는 기록에서 못 찾았다 (`미확인`) |
| 5 | **탐색 잡음이 커졌다.** 행동 std 기하평균 0.276 → 0.480 (B) · 0.493 (A). entropy 1.62 → 8.2 · 8.5 | 체크포인트 0 · 2000 의 `std` · `updates.jsonl` `entropy` | 발 자리를 정밀하게 고르는 학습에서는 entropy 계수를 줄이거나 감쇠시킨다(AME-2 는 0.004 → 0.001, `SURVEY-star-code.md` 1.6) |
| 6 | **환경 curriculum 이 0 부터 다시 돌았다.** 새 env 는 `common_step_counter` 가 0 이라 보상 가중치 curriculum 이 처음 값에서 다시 시작했다. 시작 영수증의 `base_height_l2` 는 -1.0, `lin_vel_z_l2` 는 -2.0 이다. curriculum 설정은 `base_height_l2` 를 5,000 iteration 동안 -1 → -10, `lin_vel_z_l2` 를 1,500 iteration 동안 -2 → 0 으로 옮긴다(`final_cfg.curriculum`). 그래서 E1 이 끝날 때는 -10 · 0 이었고, S2 는 2,000 갱신 끝에 약 -4.6 · 0 이다 (`계산`) | `result.json` `reward_manager_terms` · `robot_lab/tasks/go2/mdp/curriculums.py:176-197` (`current_it = common_step_counter // 24`) | 이어 학습 때 curriculum 상태를 넘기거나 끄고, 시작 · 중간 가중치를 기록한다 |
| 7 | **학습 명령은 ±0.5 m/s, 평가 명령은 1.0 m/s.** 명령 범위 curriculum(누적 20,000 iteration 에서 ±1.0)이 S2 에서는 한 번도 안 켜졌다. B child.log 의 「Command range updated」 출력 0 건 | `final_cfg.commands.base_velocity.ranges` · `commands.py:128-140` · `evaluation_criteria_s2_ab.json` `primary_command fwd10` | 평가 명령은 학습 범위 안에 둔다. 범위 밖 평가는 따로 칸을 둔다 |
| 8 | **학습 지형이 발 자리를 고를 필요가 적었다.** 학습 gap 폭 0.10 ~ 0.25 m, 돌 폭 0.5 ~ 0.7 m · 간격 0.10 m. S2-2 설계도 같은 위험을 적었다 | `final_cfg.scene.terrain` · `S2-2-DESIGN.md` 위험 절 | 발 자리를 골라야만 건너는 수준까지 curriculum 을 둔다 (7.4) |
| 9 | **학습 처리량이 낮았다.** S2 는 갱신당 약 4.2 s · 1,024 env (초당 약 5,800 transition). E1 은 iteration 당 약 4.2 s · 8,192 env (초당 약 47,000) | B 체크포인트 시각 21:13:38 → 23:33:46 · E1 `model_0.pt` 10/10 12:48 → `model_20000.pt` 10/11 12:02 | 긴 학습은 표준 runner 와 4,096 ~ 8,192 env 로, 무거운 검사는 평가 쪽에 둔다 |
| 10 | **학습 중 지형 조우 기록이 비어 있었다.** 효과는 체크포인트 평가로만 읽었다 | `S2-RESULT-PLAN.md` 1 절 · `result.json` `encounters: unmeasured` | 학습 중 gap 넘음 · 낙상 · 정지 비율을 로그로 남긴다 |
| 11 | **학습 시드 하나.** | `S2-AB-UPDATE2000.json` `interval_limit` | 판당 시드 둘 이상을 예산에 넣거나 한계를 결론에 적는다 |

**B 는 지도를 「안 쓴」 것이 아니라 「다르게 썼다」.** 갱신 1,000 ~ 2,000 평균 gradient 노름(clip 전)은 지도 encoder B 0.396 · A 0.0044, 지도 투영 B 0.128 · A 0.00084 로 약 90 ~ 150 배 차이다. 지도 투영 가중치 노름은 B 5.29 · A 1.95 (A 는 상수 입력이라 사실상 bias). 평가에서 B 는 gap 앞에서 거의 나아가지 않고(전진 중앙값 0.08 m · A 1.03 m) 기울어 넘어졌다(17/19). 왜 그렇게 배웠는지는 `미확인` 이다. 후보는 (가) 부모 critic 이 gap 근처 value 를 낮게 보고 멈춤을 배웠다 (나) gap 을 넘는 데 따로 주는 보상이 없다 (다) 1.0 m/s 평가 명령이 학습 범위 밖이다. 가를 탐침: B 평가에서 지도만 0 으로 지운 판 · gap 앞 value 측정 · 0.5 m/s 평가.

**update 0 평가(학습 전 대비)는 이 글을 쓰는 동안 돌고 있다.** 그래서 「S2 미세조정 자체가 E1 을 망쳤나」 는 `미확인` 이다.

---

## 2. S2 의 실제 구조 (코드 · 체크포인트로 확인 · 읽기만 함)

파일은 모두 `C:/Users/AI-WS01/s2_lab/s2_step29a_run/frozen_delivery/bundle/`. 학습 진입은 `s2_train_entry_17v.py:397` 의 `build_s2(...)` 이고 이것이 `s2_policy.S2MapActorCritic` 를 짓는다. 같은 폴더의 `s2_encoder_policy.py` 에 attention 지도 encoder(`AttentionMapEncoder`)가 있지만 **이번 학습에서는 쓰지 않았다**(학습 진입이 부르지 않음 · 그 파일 1 행 스스로 「AME-2 재현이 아니다」).

### 2.1 정책 안에서 자료가 흐르는 길

용어 풀이
- **actor**: 행동(관절 목표 12 개)을 내는 신경망. **critic**: 지금 상태가 얼마나 좋은지(value) 점수를 매기는 신경망. 학습 때만 쓴다.
- **encoder**: 긴 입력을 짧은 요약 숫자 묶음(latent)으로 줄이는 신경망.
- **proprio(몸 상태)**: 관절 각도 · 속도 · 기울기처럼 로봇이 자기 몸에서 재는 값.

| 단계 | 입력 | 신경망 | 출력 | 학습? | 코드 |
|---|---|---|---|---|---|
| 몸 상태 encoder | proprio 이력 450 (45 × 10 step) | MoE student encoder (expert 8) · E1 부모 값 | latent 32 | **얼림** | `s2_policy.py:153` · `188-191` |
| 지도 입력 | B: height 187 + mask 187 = 374. A: 전부 0 | 없음 (계산) | 374 | 해당 없음 | `s2_map_obs.py:113-142` |
| 지도 encoder | 374 | MLP 374 → 128 → 64 · ELU · 초기값만 `map_init_seed 7` | z_map 64 | **학습** | `s2_policy.py:164-166` · `197` |
| 지도 투영 | z_map 64 | Linear 64 → 512 · bias 없음 · **0 으로 시작** | 512 | 학습 | `s2_policy.py:167-168` |
| actor 첫 층 | [latent 32, 현재 proprio 45] = 77 | Linear 77 → 512 (부모 값) **+ 위 지도 투영을 더함** | 512 | 학습 | `s2_policy.py:158` · `198` |
| actor 나머지 | 512 | ELU → 512 → 256 → 128 → 12 | 관절 목표 12 | 학습 | `s2_policy.py:159` · `199` |
| critic | [latent 32 (gradient 끊음), critic obs 275] | 부모 critic MLP | value 1 | 학습 | `s2_policy.py:160` · `214-219` |

- 「더한다」 는 [latent, proprio, z_map] 141 열을 한 층에 넣은 것과 수식이 같다(`s2_policy.py:26-30`). 즉 B 는 **지도 encoder 와 몸 상태 encoder 의 출력을 이어 붙여 actor MLP 에 넣는 꼴**이고, 이것은 MARG 의 구조(지도 MLP → 16 차원 + 추정기 + proprio → actor)와 같은 계열이다.
- 지도 해상도: 격자 1.6 m × 1.0 m · 0.1 m 간격 = 17 × 11 = 187 점, base 중심 · yaw 정렬 (`s2_map_obs.py:30-33` · `final_cfg.scene.height_scanner`). 앞쪽으로는 0.8 m 까지만 본다. height = clip(센서 z − 맞은 점 z − 0.5, −1, 1), mask = 맞았으면 1 (`s2_map_obs.py:113-129`).

### 2.2 `encoder_mode = full_freeze` 가 얼린 것

- 얼린 것은 `student_moe_encoder`(몸 상태 encoder) **하나**다. `requires_grad False` 로 두고 optimizer 에 넣지 않는다 (`s2_policy.py:316-318` · `373-377` · `405-407` · `587-600`). 학습 진입은 갱신마다 「얼림이 켜져 있는가」 를 검사했다 (`s2_train_entry_17v.py:873-874`).
- 지도 encoder · 지도 투영 · actor · critic · std 는 optimizer 묶음에 있고 같은 학습률을 받았다 (`s2_policy.py:251-258` · `400-403`). 실제 갱신 기록의 묶음 이름은 `actor · critic · map_encoder · std` 넷이다 (`updates.jsonl` 첫 줄 `lr_path`).
- **체크포인트로 잰 변화 (이 조사)**

| 매개변수 | 갱신 0 | B 갱신 2000 | A 갱신 2000 |
|---|---|---|---|
| 지도 encoder 첫 층 가중치 노름 | 6.545 | **10.774** | 6.545 (입력이 0 이라 가중치 gradient 0) |
| 지도 encoder 첫 층 bias 노름 | 0.349 | 0.354 | 0.160 |
| 지도 투영 가중치 노름 | 0 | **5.294** | 1.950 |
| actor 첫 층(77 열) 가중치 노름 | 40.789 | 41.578 | 41.498 |
| 행동 std 기하평균 | 0.276 | 0.480 | 0.493 |

결론: 지도 쪽은 시드 7 무작위값에서 **시작해 학습됐다**. 얼어 있던 것은 몸 상태 쪽이다.

### 2.3 critic 이 받는 것

- critic 입력 = [몸 상태 latent 32 (gradient 끊음), critic obs 275]. critic obs = 선속도 3 · 각속도 3 · 중력 3 · 명령 3 · 관절 위치 12 · 관절 속도 12 · 행동 12 · 관절 가속 12 · 토크 12 · 발 접촉력 16 = 88 다음에 **height scan 187** (열 88 ~ 274, clip ±1 뒤 × 2.5) (`s2_policy.py:57-60` · `603-609`).
- **A 와 B 의 critic 은 똑같이 지형을 본다.** A 도 지형을 아는 value 로 학습 신호를 받았다. 둘의 차이는 actor 의 지도 입력뿐이다 (`s2_policy.py:23`).

### 2.4 학습 설정 요약 (manifest)

`--arm B --encoder_mode full_freeze --map_init_seed 7 --seed 11 --num_envs 1024 --updates 2000 --rollout_steps 24 --epochs 5 --minibatches 4 --lr 0.001 --schedule adaptive --desired_kl 0.01 --entropy_coef 0.01 --gap_proportion 0.15 --stones_proportion 0.15` (`runs/shortB-20261017-211253-3bfaf5cd/in/manifest.json`). 보상 15 항에 발 디딤 · stumble · feet air time 항은 없다 (`result.json` `reward_manager_terms`).

### 2.5 평가 결과 (옮김)

`S2-AB-UPDATE2000.json` · NIGHT-PLAN 10/18 02:32. 유효 쌍 기준: gap 19 쌍 A 성공 10 · B 0 (Tango 95 % [−72.7, −27.0] %p) · 징검다리 19 쌍 둘 다 0 · 평지 10 쌍 A 9 · B 6 · 계단 5 쌍 둘 다 0 (결측 5). 계단 전진 중앙값 A 2.3 m · B 10.5 m. 결측 7 (Isaac 자식 비정상 종료). 등록 규칙 판정은 「지도가 좋다」 아님, gap 은 B 가 확실히 나쁨.

---

## 3. 이전 조사와 이 글의 관계 (되풀이하지 않는다)

| 문서 | 이미 정리된 것 | 이 글이 더한 것 |
|---|---|---|
| `inbox/jay/20261012-arch-discussion/PAPERS-architecture.md` (10/13) | AME-2 · MARG · START · JEPLO · MoE-CTS · HiPAN 여섯 편의 입력 · 구조 · 보상 · 학습 단계 · 숫자 · 빠진 숫자 13 항목 | 같은 계열 논문을 넓혔다(4 절). 여섯 편은 요약 한 줄과 우리 설계에 쓰는 사실만 다시 적는다 |
| `inbox/jay/20261008-546-design/SURVEY-star-code.md` (10/08) | ame2_minimal 코드의 신경망 폭 · PPO · 보상 · 지형 · DR, 팀 v14 와의 대조 | 껑충 보행과 관련된 보상 함수 본문(도약 벌점의 고저차 조건 · 이동 보상 · 접촉력 기준)을 행 번호로 다시 읽었다(6 절). Kitjesen/ame2 를 더했다 |
| `docs/research/20261007-ame2-go2-v1-v6.md` (10/07) | 팀원 v1 ~ v14 경과, v15 = 공개 코드 이식 | v1 · v11 의 접촉 기록을 「2 족 원본 가설」 판정에 썼다(6.3) |
| `S2-RESULT-PLAN.md` · `ROADMAP-20261016.md` · `S2-2-DESIGN.md` · `VERIFY-astra-17ag.md` | S2 판정 규칙 · 로드맵 S2-1 ~ S2-4 · 발 디딤 보상 사양 · D435i 제원 | S2 결과를 받아 로드맵의 S2-2 이후를 「붙이기」 가 아니라 「처음부터 함께」 로 다시 짜는 안(7 절) |

**JEPLO 이름 확인:** arXiv 2609.15770 「JEPLO: Joint-Embedding Predictive Learning for LiDAR-Based Legged Locomotion」 (2026-09-14). abs 페이지에서 제목 · 저자를 이 조사가 다시 열어 확인했다. 내용은 `PAPERS-architecture.md` 4 절. 팀장이 말한 「JEPLO」 는 이 논문으로 본다.

---

## 4. 논문 조사

### 4.0 읽은 방법

- 새로 더한 30 편(4.2 · 4.3 의 19 편 + 4.4 의 11 편)은 하위 조사 셋이 arXiv 전문(HTML 또는 PDF 텍스트)을 받아 읽고, 표 · 그림 쪽은 그림으로 렌더하거나 단어 좌표로 대조했다. 코드 저장소는 `gh repo view` · `gh api` 로 있는지 열어 봤다.
- 이 글을 쓴 lead 조사가 원문에서 다시 확인한 것: legged_gym 세 문장(「108 measurements」 · 「neither the reward function nor the action space has any gait-dependent elements」 · 「it always converges to a trotting gait」) · AME-2 v3 두 문장(IV-D1 도약 정의 · VIII-D 접촉 패턴) · Walk These Ways Fig. 4 캡션 · DeepTransition 초록 · DELTA Table III 과 「8 cm 격자」 문장 · JEPLO 제목 · 4.4 의 8 편 arXiv 제목과 날짜(arXiv API). 나머지 숫자는 하위 조사의 읽기를 옮긴 것이고 lead 가 원문에서 다시 재지 않았다.
- 표기: 「논문」 은 논문 원문, 「코드」 는 저장소 기본 설정 파일 값(논문 값 아님), 「README」 는 README 주장. 그림 막대에만 있고 숫자가 인쇄되지 않은 값은 적지 않았다(`미확인`).
- 이전 여섯 편(AME-2 · MARG · START · JEPLO · MoE-CTS · HiPAN)은 `PAPERS-architecture.md` 에 있다. 아래 4.1 에 요약 한 줄씩만 둔다.

### 4.1 이미 정리된 여섯 편 (요약 · 출처 `PAPERS-architecture.md`)

| 논문 | 배포 정책이 지형을 보나 | 지도 encoder · 몸 상태 encoder | 발 자리 | 우리에게 가장 중요한 사실 |
|---|---|---|---|---|
| AME-2 (2601.08485 v3) | 예 (depth → 학습형 고도 지도 + 불확실도) | CNN 점 특징 + 위치 MLP → 전역 max pool. 몸 상태 embedding + 전역 → **query → MHA** (지도 점들) → decoder | 보상 없음 (일부러 안 둠, IV-D1) | 학습 예산 ANYmal-D 약 60 RTX-4090-day. 공식 코드는 G1 만 |
| MARG (2509.20036 v2) | 예 (실기 Mid-360 지도 · 학습은 시뮬 높이 187) | 지도 MLP [128, 64, 16] + 추정기(v̂ · ĉ) + proprio → actor | **보상 (feet center)** + stumble + air time | Go1 학습(Go2 와 같은 크기급), A100 1 장 약 12 시간. 혼합 코스에서 추정기를 빼면 0.96 → 0.1 · 0.0 |
| START (2512.13153 v1) | 예 (**D435i** depth 60 × 60 → 재구성 지도) | depth CNN + proprio GRU → 재구성 지도 → CNN + transformer 융합 | **보상 (feet edge)** | 실기 각 5 회: 디딤돌 76.3 % 1.0 · gap 0.7 m 1.0. FtEdge 를 빼면 gap 0.0 |
| JEPLO (2609.15770 v1) | 예 (Mid-360 → 구면 depth → JEPA latent) | ViT + GRU → latent | 없음 | Go2 · **Isaac Lab** · 코드 공개. gap · 디딤돌 숫자 없음 |
| MoE-CTS (2602.00678 v4) | 아니오 (proprio 만) | MoE student encoder | 없음 | 우리 E1. 학습 지형에 gap · 디딤돌 없음 |
| HiPAN (2604.26504 v1) | 관절 정책은 아니오. 상위 정책만 **D435i** | 상위: depth CNN + GRU | 없음 | 내비게이션 논문 |

### 4.2 새로 더한 논문: 입력 · 구조 · 발 자리

용어 풀이: **scandots / height scan** 은 로봇 둘레 바닥 높이를 격자로 찍은 숫자 묶음. **elevation map(고도 지도)** 은 센서로 만든 바닥 높이 지도. **teacher-student** 는 정답 지도를 보는 teacher 를 먼저 학습하고, 실제 센서만 보는 student 가 teacher 를 따라 하게 하는 2 단계 학습. **DAgger** 는 student 가 직접 움직이며 teacher 의 답을 받아 배우는 방법. **planner** 는 발 놓을 곳을 계산으로 정하는 별도 프로그램.

| 논문 (arXiv · 판) | 로봇 (4 족?) | 배포 정책이 보는 지형: 모양 · 해상도 · 범위 · 틀 | 지도 encoder 와 몸 상태 encoder | 발 자리를 명시적으로 다루나 |
|---|---|---|---|---|
| legged_gym, Rudin 2021 (2109.11978 v3) | ANYmal C 실기 · A1 등 시뮬 · 4 족 | 논문: base 주변 격자 **108 점**, 값 = 지형에서 base 높이까지 (Sec 3.2). 코드: 17 × 11 = 187 · 0.1 m · 1.6 × 1.0 m · yaw 정렬. 이력 없음 | 나누지 않음. 한 벡터로 MLP [512, 256, 128] (코드) | 아니오. 「보상에도 행동 공간에도 gait 에 의존하는 요소가 없다」 (Sec 3.2) |
| Miki 2022 (2201.08117 v1) | ANYmal C | 발마다 원형 표본: 반경 0.08 ~ 0.48 m 다섯 고리, 발당 52 점, 네 발 208. 2.5D 지도 20 Hz (S5 · Table S3) | **나눔 + gate.** teacher: 발별 지형 encoder (80, 60) · privileged encoder → proprio 와 concat → MLP. student: GRU belief encoder 가 **attention gate** α 로 지도를 얼마나 믿을지 정함 (b = g_b(b′) + l_e ⊙ α) (Sec 4 · S6) | 아니오. 행동이 CPG 위상 + residual. swing 발이 주변보다 0.2 m 넘게 높으면 벌점 (S7) |
| ANYmal Parkour, Hoeller (2306.14874 v1) | ANYmal D | 2 m × 1 m 높이 격자 (해상도 `미확인`), perception 신경망이 복원한 2.5D (Table S1) | 신경망 8 개(기술 5 + navigation + perception). locomotion 크기 `미확인` | 아니오 (목표 위치형) |
| Risky Terrains, Zhang (2311.10484 v2) | ANYmal-D | **25 × 16 · 7 cm** (틀 `미확인`) (Table V) | 나누지 않음. 전부 이어 붙여 MLP (512, 256, 128) | 아니오 (목표 위치형 · end-to-end) |
| DTC, Jenelten (2309.15462 v2) | ANYmal C · D | 발 현재 위치와 목표 foothold 를 잇는 선을 따라 높이 40 (Table 2) | MLP 3 × 512. 관측에 planner 출력(foothold 8 · 착지 관절 12 · 접촉 4 · 위상 4 · twist 3) | **예.** planner(TAMOLS)가 발 자리를 정하고 RL 이 따라감. foothold 보상 −ln(‖p* − p‖² + ε) |
| TAMOLS, Jenelten (2206.14049 v2) | ANYmal · RL 아님(최적화) | 2.4 × 2.4 m · 4 cm, 층 3 개 (Sec IV-A) | 해당 없음 | **예.** foothold 와 몸 자세를 함께 최적화 |
| RLOC, Gangapurwala (2012.03094 v3) | ANYmal B · C | 91 × 91 · 0.02 m · 1.8 × 1.8 m · yaw 정렬 → 사전학습 autoencoder 로 96 차원 (Sec II-A · III-A) | **나눔.** 지형 encoder 를 따로 사전학습, footstep planner MLP 512-256-128 | **예.** RL 이 stride 마다 네 발 xy 를 내고 model-based 제어기가 추적 |
| DeepGait, Tsounis (1909.08399 v2) | ANYmal · 시뮬만 | planner 만 지형: 32 × 32 · 4 cm | planner: CNN → FC 128 + proprio 15 → 512 → 256 | **예.** planner RL 이 foothold · 접촉 상태, controller RL 이 추적 |
| Parkour in the Wild, Rudin 2025 (2505.11164 v1) | ANYmal D | student: depth 4 장(앞 2 · 뒤 2, **D435i**) 48 × 32 px · 2 m 에서 자름. expert 는 2 × 1 m 지도 (Sec 2.4 · Table 3) | 이미지마다 CNN → proprio 와 concat → LSTM 2 층 → proprio · 명령과 다시 concat → MLP | 아니오. 평균대 · 디딤돌에서 헛디딘 뒤 회복한다고 저자가 적음 (Sec 4.3) |
| Robot Parkour Learning, Zhuang (2309.05665 v2) | A1 · Go1 | depth 48 × 64 · **D435** · 10 Hz · GRU 기억 (Sec 3.3) | depth CNN → proprio 와 concat → GRU 256 → MLP. proprio 전용 encoder 없음 | 아니오 |
| Extreme Parkour, Cheng (2309.14341 v1) | A1 | depth 58 × 87 · **D435** · 10 Hz · convnet-GRU. teacher scandots (코드 12 × 11 · 0.15 m) | 코드: scan encoder [128, 64, 32] → actor [512, 256, 128] | **보상으로 예.** 접지 발이 가장자리 5 cm 안이면 벌점 r_clearance (Eq. 3) |
| ViNL, Kareer (2210.14791 v3) | AlienGo | teacher 11 × 17 · 1.6 × 1.0 m. student depth (해상도 `미확인`) | **나눔.** 지도 encoder φ MLP [128, 64, 32] 출력을 obs 와 concat. student 는 CNN + LSTM 으로 φ(H) 를 맞힘 | 아니오 (다리-장애물 접촉 벌점) |
| Neural Volumetric Memory, Yang (2304.01201 v1) | A1 | depth 64 × 64 × 5 frame. teacher 고도 21 × 26 · 5 cm + 10 × 19 · 10 cm | 3D 부피 기억(신경망) + proprio concat | 아니오 |
| DreamWaQ++, Nahrendra (2409.19709 v2) | Go1 (+ ANYmal-C · Hound) | point cloud 5 회 누적, D435f 또는 LiDAR. critic 지도 1.1 × 1.7 m · 5 cm | **나눔.** PointNet(지형) + MLP-mixer(몸) → LayerNorm → 다중 모달 MLP-mixer 융합 | 아니오 |
| PIE, Luo (2408.13740 v3) | Lite3 (12.7 kg) | depth 2 frame · **D435i** 10 Hz (해상도 `미확인`) + proprio 10 step | **나눔 + transformer.** depth CNN · proprio MLP → 공유 transformer(cross-modal attention) → GRU → v̂ · 발 높이 ĥ · 지도 latent | 보상은 없음. **발 높이(foot clearance)를 명시적으로 추정**해 입력. 빼면 Step 난이도 9.81 → 3.09 (Table III) |
| SoloParkour, Chane-Sane (2409.13678 v1) | Solo-12 | depth **D405** 48 × 48 · GRU. teacher heightmap (코드 13 × 11 · 0.08 m) | conv → GRU → MLP | 아니오 (stumble 은 제약 조건) |
| LocoTransformer, Yang (2107.03996 v3) | A1 | depth 64 × 64 × 4 + proprio 3 step | **transformer 융합.** proprio MLP + depth 토큰 → transformer 2 층 | 아니오 (장애물 피하기 과제) |
| Barkour, Caluwaerts (2305.14654 v1) | 자체 4 족 11.5 kg | heightfield 17 × 11 · 0.1 m, 실기는 CAD + mocap 으로 만듦 (App E · Sec VIII) | specialist MLP. 통합 정책은 heightfield conv → GPT 2 층 | 아니오 |
| WMP, Lai (2409.16784 v1) | A1 | depth 64 × 64 · **D435i** · FOV 58° × 58° | world model(RSSM, GRU)의 기억 h 를 proprio 와 함께 정책에 | 논문에는 없음. 코드에 feet_edge −1.0 |

### 4.3 새로 더한 논문: 보상 · 학습 · 숫자 · 코드 · 보행

| 논문 | 보상 핵심 (gait 관련) | 학습 단계 · 예산 | 시뮬 · 실기 숫자 (원문에 인쇄된 것) | 코드 | 보행(gait) |
|---|---|---|---|---|---|
| legged_gym | feet air time Σ(t_air − 0.5) 가중 2 (Table 2) | 단일 PPO · 4,096 로봇 · 1,500 갱신 · 험지 20 분 미만 (RTX A6000) | 시뮬 계단 0.2 m 「거의 100 %」 (Fig 5). 실기 숫자 없음 | github.com/leggedrobotics/legged_gym (있음) | 「항상 trot 로 수렴」, 다리 끌기 같은 결함 (Sec 4.2) |
| Miki 2022 | foot clearance 0.003 · slip 0.003 등 (S7) | teacher PPO → student (BC + 재구성). 예산 `미확인` | 실기 계단 30.5 cm 까지 안정 (기준선 20 cm 에서 떨어짐). 등산 2.2 km | 정책 코드 없음. elevation_mapping_cupy 있음 | CPG 위상으로 정함 |
| ANYmal Parkour | stumble(‖F_xy‖ > 2‖F_z‖) −1 · feet air time 없음 · 대칭 증강 사용 (Table S2 · S3) | 기술 5 개 따로 + navigation. dense perception GPU 약 45 GB | 시뮬 Table I 98.2 / 96.3 / 97.6 %. 학습 gap [0.1, 1.2] m (Fig 4G) | 없음 | 「안정된 주기 보행에 기댈 수 없다」 (서론) |
| Risky Terrains | gait 보상 없음 · RND 1.0 (Table IV) | generalist 8,000 iteration → 지형별 specialist 1,000 ~ 3,000. 처음부터 specialist 10,000 은 실패 (Sec IV-C) | 실기 (mocap 지형 · 상태): Stones-2Rows 성공 8/10 · Balance-Beams 5/5 (Table II). 돌 폭 20 cm (Fig 1) | 없음 | 저절로: 쉬운 지형 3 발 walk · trot, 어려우면 pace. 대칭 증강 사용 (Fig 5 · 11) |
| DTC | foothold 6 · consistency 20 (Table 3) | 4,096 로봇 · 90,000 epoch (약 2 주) · 6,000 epoch(약 1 일)이면 배치 가능 | 실기: foothold 추적 오차 2.3 cm. gap 0.1 m 10/10 · 0.6 m gap 4 개 4/4 · 0.2 × 0.2 m 디딤돌 2 m 구간 10 회 통과 | 학습 코드 없음 (그림 자료만 Dryad) | **planner 가 trot 고정** (stride 0.93 s) |
| TAMOLS | (최적화 비용) edge avoidance 3 · footholds on ground 10⁴ (Table I) | 해당 없음 | 실기 gap 27 cm · 벽돌 20 × 20 cm 간격 20 cm trot 0.4 m/s | 공식 없음. 비공식 둘 (tamols-rl · tamols-python, 존재만 확인) | gait 패턴 고정 (여러 개 시연) |
| RLOC | edge cost · stability margin (Eq 16 · 17) | planner SAC 28 + 4 h · 보조 22 h · 6 h (RTX 2080Ti) | 시뮬 bricks 85.3 % (RC 추가 90.2 %) (Table VII · IX) | 없음 | 제어기가 줌 (trot 0.7 확률 등) |
| DeepGait | (planner · controller 보상 Table II) | planner 200k iteration 지형당 약 82 h · controller 58 ~ 116 h | 시뮬 Gaps 96.4 % · Stepping-Stones 96.8 % (Table III) | 없음 | 평지 주기적, 디딤돌 · gap 비주기적 |
| Parkour in the Wild | gait · air time · stumble 항 없음 (Table 2) | expert 9 개 RL → DAgger 증류 → RL fine-tune | 시뮬 디딤돌: expert 98.8 · 증류 73.0 · fine-tune 98.8 %. 평균대 97.3 · 85.2 · 99.5 % (Table 4, 1,000 회) | 없음 | 보고 없음 |
| Robot Parkour Learning | 전진 + 에너지 + 생존. gait 항 없음 (Sec 3.1) | skill 5 개 soft → hard dynamics → DAgger 증류. specialist 하나 RTX 3090 18 h | 시뮬 leap 80 % · climb 86 % (Table 2). 실기 A1 leap 0.60 m 80 % (10 회) | github.com/ZiwenZhuang/parkour (있음 · README: Go2 학습 config 는 논문 성능 보장 안 함) | 이름 없음 |
| Extreme Parkour | edge 벌점 (코드 feet_edge −1) · feet air time 없음 (코드) | scandots RL → depth DAgger. 3090 1 장 20 h 미만 | 시뮬 MEV 0.03 (edge 벌점 없으면 0.08) (Table 2). gap 0.8 m 등 기록 | github.com/chengxuxin/extreme-parkour (있음 · Go2 설정 없음) | 「네 다리를 다 쓰는 gait」 정도 (Sec 3.1) |
| ViNL | legged_gym 보상 + 접촉 벌점 | 1 단계 rough → 2 단계 장애물 fine-tune → 3 단계 student | 시뮬 성공 73.6 % (blind 1.2 %) (Table I). 실기 숫자 없음 | github.com/SimarKareer/ViNL (있음) | **rough 사전학습이 자연스러운 보행을 주고, 장애물에서 처음부터 배우면 발을 지나치게 드는 부자연스러운 보행이 나온다** (Sec III-A Stage 2) |
| NVM | AMP(동작 모방) style 보상 1.0 | teacher PPO → student BC + 재구성 | 시뮬 Stones: student 14.4 % · teacher 70.6 % (Table 2) | 없음 (「Coming Soon」) | AMP 로 자연 보행 유도 |
| DreamWaQ++ | DreamWaQ 보상 그대로 (foot clearance −0.01 등, air time 없음) | 단일 단계 · 3,500 agent · A5000 약 11 h | 계단 Stairs-hard 97.8 % (Table IV) | 공식 없음 | 이름 없음 |
| PIE | gait 항 없음 (Table I) | 단일 단계 10,000 iteration · RTX 4090 20 h 미만 | 시뮬 종료 수준 Gap 9.9 · Step 9.81 (Table III). 실기 1 m gap 등 (그림 성공률 `미확인`) | 공식 없음 | gait 보상 없이 「자연스러운」 보행 (Sec V) |
| SoloParkour | foot air time · 접촉 수 **제약**을 평지 · 초기 수준에서만 (Table 2) | PPO + 제약 → DDPG 계열 visual. RTX 4090 20 h 미만 | 실기 Step 85 · Leap 70 · Crawl 100 % (2 시드 × 10 회) | github.com/Gepetto/SoloParkour (있음) | 제약으로 유도 |
| LocoTransformer | 전진 · 에너지 · 생존 | PPO 1,500 만 sample | 실기 이동 9.6 m 대 concat 5.0 m (Table 6) | github.com/Mehooz/vision4leg (있음) | 이름 없음 |
| Barkour | Feet Clearance 0.25 등 (Table V) | specialist 3 개 → transformer 증류 | 민첩성 점수 0.73 (소형견 1.00) | 정책 코드 없음 (하드웨어 저장소만) | 걷기 specialist trot, **점프 specialist 는 bound(좌우 대칭 행동)** (Sec VI-B · App G) |
| WMP | 코드: feet_air_time 0.5 · AMP | world model + PPO 동시 | 실기 gap 85 cm 등 (그림 성공률 `미확인`) | github.com/bytedance/WMP (있음) | AMP 유도 |

### 4.4 새로 더한 논문: 보행 위상 · 발 디딤 보상 · 2025 ~ 2026 지도 encoder

| 논문 (arXiv · 판) | 로봇 | 지형 입력 · 구조 | 발 자리 · gait 관련 장치 | 학습 · 예산 | 숫자 (원문 인쇄) | 코드 |
|---|---|---|---|---|---|---|
| AME-1 「Attention-Based Map Encoding」, He 외 (2506.09588 v1) | ANYmal-D · GR-1 (휴머노이드) | 지도 L × W × (x, y, z): ANYmal 26 × 16. z 에 CNN 2 층 → 점 특징, **proprio 가 query** → MHA (d 64 · head 16) → proprio 와 이어 MLP | foothold 보상 없음. **attention 이 다음 디딜 곳에 몰린다** (Fig. 7). 「뛰는 gait」 벌점(no-fly)은 GR-1 열에만 있고 ANYmal-D 에는 없다 (Table 2) | 2 단계(정답 지도 → 잡음 · drift · 지형 추가). 4,096 env · 18,000 + 3,600 epoch · A100 한 장 6 일 | 학습 지형 성공률 DTC 보다 26.5 %p 높음 (Fig. 6Ab) | 본문에 없음 |
| DELTA, Park 외 (2608.22033 v1, 2026-08) | RAIBO2 | 지도 26 × 16 · 41 × 25, 2.0 × 1.2 m. proprio query 로 변형(deformable) 표본 위치를 정하는 attention (3 층 · 4 head · 8 점) | foothold 정답 없이 학습 | RaiSim · 200 env · 30,000 iteration · RTX 4060 | **작은 돌(fine-grained) 성공률: 26 × 16 에서 AME 65.7 · DELTA 84.0, 41 × 25 에서 68.0 · 95.9 %** (Table III). 본문: 「약 8 cm 격자 간격이 공간 정밀도를 제한한다」. 실기 21/21, D430 앞뒤 2 대 | 없음 |
| Foot Position Maps, Hwang 외 (2604.02744 v1) | A1 · 실기 없음 | 17 × 11 · 0.1 m 지도 + **발 위치 Gaussian 채널 4 개**. AME-1 꼴 MHA | 보상: 압력 중심(CoP)에서 지지 다각형까지 거리. gap 에서 trot → 도약으로 바뀜 (Sec V-C) | 4,096 env · RTX 4090 약 25 h | 성공률 Ours 77.0 · Attn 64.2 · CNN 69.8 · MLP 58.7 % (Table IV) | 미확인 |
| High-speed discrete terrain, Kim 외 (2506.02835, Sci. Robot. 2025) | Raibo | planner 가 foothold 를 샘플링 최적화 → RL tracker 가 따라감(발마다 다음 목표 2 개 · 167 차원 · MLP [512, 128]) | **명시.** 목표 접지 보상 + **Bound 보상(k = 1)** 으로 바운딩을 장려 (Table S4) | RaiSim · 300 env | 시뮬 1.6 m 간격 · 60° 경사 디딤돌 95 % 넘게. 실기는 미리 얻은 지도 + Vicon | 없음 |
| BeamDojo, Wang 외 (2502.10363 v3) | **G1 휴머노이드** | 15 × 15 · 0.1 m 자기중심 지도 · MLP | **foothold 보상**: 발바닥 표본점 아래 지형이 ε = −0.1 m 보다 낮은 점 수를 벌점 (Eq. 2). feet air time 1.0 | **2 단계: 1 단계는 구멍을 메운 평지를 걸으며 foothold 보상만 실제 지형으로 받고(헛디뎌도 안 끝남) → 2 단계 실제 지형** (Sec IV-C). 단계당 10,000 iteration | 시뮬 디딤돌 95.67 % (medium). 실기 디딤돌 4/5 · gap 5/5 | 공식 없음 |
| Walk These Ways, Margolis (2212.03238 v1) | Go1 · 평지만 | gait 명령 8 차원(다리 위상 차 θ1 ~ θ3 · 주파수 · 발 높이 등) + 다리별 clock sin 4 개 입력 | **접촉 일정을 보상으로 강제** (swing 발 힘 · stance 발 속도 −0.08 · 발 높이 −0.6, Table 1) | 4,096 env · 25.8 억 timestep | 기계 동력 1 m/s: trot 24 · pronk 43 · pace 25 · bound 39 J/s (Table 3). **「pronk 와 trot 가 배우기 쉬워 학습 초기에 pace · bound 를 압도한다」 (Fig. 4 캡션, lead 원문 확인)** | Improbable-AI/walk-these-ways (있음) |
| Symmetry, Mittal 외 (2403.04359 v1) | ANYmal | 대칭 데이터 증강 · mirror loss | gait 는 재지 않음. **「완전히 대칭인 정책은 대칭인 정지 자세에서 한 발을 먼저 들 수 없다」** 그래서 soft 방식을 쓴다 (Sec III) | | 증강이 수렴 · return 이 가장 좋음 (Fig. 4 · Table I) | rsl_rl `extensions/symmetry.py` 가 구현 |
| Energy → gait, Fu 외 (2111.01674) | A1 | | 에너지 최소화 보상으로 gait 출현: 0.375 m/s walk · 0.9 trot · 1.5 「bounce/hopping」 (Sec 4.2). 속도 조건 하나로 여러 속도를 배우면 walk · trot 둘로 붕괴 (Sec 4.3) | 15,000 iteration · 15 억 sample · GPU 1 장 약 24 h | | 없음 |
| DeepTransition, Shafiee 외 (2306.07419 v2) | A1 | | **연속 gap 에서 넘어지지 않으려고 trot → pronk 전환이 저절로 나온다.** walk · trot · bound 로 제한하면 gap 을 높은 성공률로 못 넘음 (초록은 lead 원문 확인, 제한 실험은 Discussion · 하위 조사 읽기) | Isaac Gym · 보상 조합 27 개 | 실기 1.3 m/s 로 30 cm gap | 요청 시 |
| Learned gait transitions, Yang 외 (2104.04644) | A1 | gait 정책(CMA-ES) + MPC | walk < 0.9 · trot 0.9 ~ 1.8 · fly-trot ≥ 1.8 m/s (Sec 5.2) | | | |
| Symmetry-guided gaits, Ding 외 (2403.10723 v4) | **Go2** | clock + 위상 차 입력, 시간 · 형태 · 시간 역전 대칭 | trot · bound 등 자유 전환 | Isaac Gym · 24.6 억 sample | 실기 Go2 0.8 m/s | anonymous 저장소 (열지 않음) |

### 4.5 우리(Go2 · Isaac Lab · D435i)에 옮길 때 걸리는 점 (묶어서)

| 걸리는 점 | 해당 논문 | 무엇을 뜻하나 |
|---|---|---|
| 학습 시뮬레이터 | 36 편 중 Isaac Lab 학습은 JEPLO 하나(`PAPERS-architecture.md` 4 절). 나머지는 Isaac Gym · RaiSim · PyBullet · Gazebo | 보상 · 지형 함수는 다시 짜야 한다. 우리 robot_lab Go2 env 에 이미 있는 함수(feet air time · stumble · mirror)는 그대로 쓸 수 있다 |
| 실기 지형을 mocap · 미리 만든 지도로 받음 | Risky Terrains(Zhang) · Barkour · Kim 2025 | 실기 숫자는 「센서 없이 완벽한 지도」 조건이다. D435i 결과로 읽으면 안 된다 |
| D435 계열 카메라 | START · PIE · WMP (D435i 한 대) · RPL · Extreme Parkour (D435 한 대) · Parkour in the Wild (D435i 4 대) · Miki · DTC (D435 4 대) · DreamWaQ++ (D435f) · DELTA (D430 2 대) · HiPAN (D435i) | 앞 한 대면 발 아래 · 뒤가 안 보인다. 한 대 구성(START · PIE · WMP · RPL · Extreme Parkour)은 모두 기억 장치(GRU · world model · 재구성 신경망)를 둔다 |
| 지도 해상도 | 디딤돌을 푼 것: Zhang 7 cm · AME-2 8 cm(국소 4 cm) · START 5 cm · DTC planner 4 cm · DeepGait 4 cm · RLOC 2 cm. MARG 는 187 점(해상도 미기재). DELTA 는 8 cm 가 작은 돌을 막는다고 적음 | 우리 0.1 m 격자는 큰 돌 · gap 에는 되지만(우리 v2 gap 99 ~ 100 %), 작은 돌에서는 막힐 근거가 있다 |
| 계산 예산 | AME-2 약 60 GPU-day · AME-1 A100 6 일 · DTC 1 ~ 14 일 · MARG A100 12 h · START A6000 16.6 h · PIE 4090 20 h 미만 · Extreme Parkour 3090 20 h 미만 · DreamWaQ++ A5000 11 h · legged_gym A6000 20 분 미만 | 우리 RTX 5080 한 장으로는 MARG · START 급(반나절 ~ 하루)이 현실적이다 |
| 공개 코드로 Go2 에 가까운 것 | JEPLO(Go2 · Isaac Lab) · RPL(Go2 config, README 가 성능 보장 안 함) · Walk These Ways(Go1) · legged_gym · Extreme Parkour(Go1 있음 · Go2 없음) · WMP(A1) · ame2_minimal(G1) | 발 디딤 보상이 있는 공개 코드는 Extreme Parkour(edge)와 WMP(코드 feet_edge) 정도 |

---

## 5. 논문들의 공통 구조: 「지도 + 몸 상태 → 발 디딤」 은 네 가지 모양이다

(범위: 이 조사가 읽은 36 편 · `PAPERS-architecture.md` 여섯 편 포함)

| 모양 | 어떻게 생겼나 | 예 | 발 자리 |
|---|---|---|---|
| (가) 한 벡터로 이어 붙이기 | proprio 와 높이 표본을 이어 붙여 MLP 하나 | legged_gym · Risky Terrains(Zhang) · Barkour specialist · 우리 v2 | 관절 행동에서 저절로 |
| (나) 지도 encoder 와 몸 상태 encoder 를 따로 두고 이어 붙이기 | 지도 MLP · CNN → 짧은 latent, 몸 상태 이력 encoder · 추정기 → actor MLP | **MARG** · ViNL · Extreme Parkour(코드) · RLOC(지형 autoencoder) · Miki teacher · **우리 S2 B** | 관절 행동 + 발 디딤 보상 |
| (다) attention · transformer · gate 로 섞기 | 몸 상태로 query 를 만들어 지도 점에서 고르기, 또는 두 입력을 토큰으로 섞기 | **AME-2 · AME-1** · DELTA · Foot Position Maps · Miki student(gate) · PIE · START · LocoTransformer · DreamWaQ++(MLP-mixer) | 관절 행동. AME-1 은 attention 이 다음 디딜 곳에 몰린다고 보고 |
| (라) 계층형: 발 자리를 명시적으로 출력 | planner(최적화 또는 RL)가 발 자리를 내고 아래 정책이 따라감 | **DTC** · TAMOLS · RLOC · DeepGait · Kim 2025 | **명시적 출력** |

이 표에서 우리에게 중요한 것 넷:

1. **팀장이 말한 「발 놓을 곳이 행동으로 나오는 구조」 를 글자 그대로 하는 것은 (라) 다섯 편뿐이다.** 다섯 모두 공개 학습 코드가 없고(DTC 는 그림 자료만, TAMOLS 는 비공식만), planner 를 Go2 기구학에 맞게 새로 만들어야 한다. 나머지 지형 인지 논문들은 발 자리를 관절 행동 안에서 「고르게」 만들고, 발 디딤 보상(MARG · START · Extreme Parkour · BeamDojo)이나 attention(AME-1 · AME-2 · DELTA)으로 그 고르기를 돕는다.
2. **지형을 보는 정책은 지도와 함께 처음부터 학습된다.** 읽은 논문에서 눈 먼 정책에 지도를 나중에 붙이는 길은 찾지 못했다. 가장 가까운 것은 ViNL(rough 지형 사전학습 → 장애물 fine-tune) · Risky Terrains(generalist → specialist) · Parkour in the Wild(증류 → RL fine-tune)인데, 셋 다 출발 정책이 **이미 지도를 보고** 있었다.
3. **작은 돌에는 격자 해상도가 걸린다.** DELTA Table III 은 같은 방법에서 격자를 26 × 16 → 41 × 25 로 바꾸면 작은 돌 성공률이 84.0 → 95.9 % 가 된다고 적는다. 우리 187 점(0.1 m)은 gap 에는 통했지만(v2) 작은 돌 목표에는 근거가 약하다.
4. **보행 위상은 저절로 trot 가 되기도 하고(legged_gym), gap 에서는 pronk 가 「살아남는」 해답이기도 하다(DeepTransition).** 학습 초기에는 pronk · trot 이 쉬운 끌개다(Walk These Ways Fig. 4). 그래서 gait 를 재는 관문이 필요하다(7.2).

---

## 6. AME-2 저장소와 껑충 보행

### 6.1 찾은 저장소

| 저장소 | 무엇 | 로봇 | 확인 |
|---|---|---|---|
| `leggedrobotics/ame2_minimal` @8beb9a68 (커밋 둘: 2026-10-05 「init」 · 10-06 「update example cpt and readme」) | 저자 쪽 공식 재구현 · Isaac Lab 2.3.2 | **Unitree G1 휴머노이드만** (23 관절) | `gh api` 커밋 목록 · 얕은 clone 으로 코드 읽음. 포크 5 개도 새 커밋 없음 |
| `Kitjesen/ame2` @2e989fa7 | 비공식 독립 구현 · Isaac Lab 0.46 Direct | ANYmal-D (4 족) | README: teacher 학습 중, 「success@0.5m 0 %」. 변경 기록에 무릎 기어가기 · 보행 벌점 6 개 끔 등 |
| 팀원 저장소 | GitHub 공개본 **없음**. `foothold-project` 조직 저장소 5 개 · 팀원 공개 저장소에 AME-2 없음 (`gh repo list`) | | 팀원 실험은 RunPod 볼륨 `limseokheon/ame2_go2` 에 있고, v15 가 「공개 ame2_minimal 8beb9a6 의 G1 teacher 를 Go2 로 이식」 이라고 기록됨 (`docs/research/20261007-ame2-go2-v1-v6.md:300`). **이 조사는 볼륨을 열지 못했다. 팀장이 말한 껑충 보행이 v15 인지 그 뒤 판인지는 `미확인`** |

### 6.2 보행 위상을 정하는 요소 (ame2_minimal 코드 · 논문)

용어 풀이: **보행 위상(gait)** 은 네 발이 땅에 닿고 떨어지는 순서다. trot(트롯)은 대각선 두 발(앞왼 · 뒤오)이 함께 움직인다. bound(바운딩)는 앞 두 발 · 뒤 두 발이 각각 함께 움직인다. pronk(프롱킹)는 네 발이 한꺼번에 뛴다. **duty factor** 는 한 발이 땅에 붙어 있는 시간 비율이다.

| 요소 | ame2_minimal 에서 | 근거 |
|---|---|---|
| gait 보상 (feet air time · 위상 시계 · 대각 동기) | **없다.** 보상 23 항 어디에도 없다 | `ame2/ame2/tasks/ame2_env_cfg.py:408-570` |
| phase / clock 입력 | **없다.** actor 입력은 proprio 82 (G1) + 명령 4 + 지도 | `SURVEY-star-code.md` 1.3 |
| 도약 벌점 | `undesired_leaping` -1: 「모든 발이 떨어짐 **그리고** critic 스캔의 고저차(최고 − 최저) < 0.3 m」 일 때만 1 | 코드 `mdp/rewards.py:368-396` · cfg `450-460`. 논문 IV-D1 「Leaping on flat terrain: All feet are off the ground when the elevation difference is < 30 cm」 |
| 그 스캔의 범위 | base 기준 x −0.5 ~ +1.5 m, y ±0.56 m (2.0 × 1.12 m) | cfg `89-96` |
| 명령 · 속도 | 목표 위치형. 속도 명령 없음. `move2goal` 은 목표 방향으로 0.3 ~ 2.0 m/s 이면 1 (느려도 0.3 만 넘으면 됨). 위치 보상은 마지막 4 s 에만 | `mdp/rewards.py:180-216` · cfg `413-428` |
| 대칭 증강 | critic 에만, G1 함수(23 관절 가정) | `agents/rsl_rl_ppo_cfg.py:180-185` |
| 휴머노이드 상수 | 링크 접촉력 벌점 기준 `robot_weight 400 N` (넘는 몫만 벌점) · 몸통 접촉 종료 400 N · 허벅지(hip_pitch) 가속 종료 100 m/s² (논문은 개 60 · 사람 100) · PD Kp 50 ~ 139 | `ame2_env_cfg.py:524-531` · `587-604` · `mdp/rewards.py:338-350` · `assets/unitree.py:59-112` · 논문 IV-D2 |
| 지형 크기 (G1) | gap 0.18 ~ 1.2 m · climb_up 0.1 ~ 0.65 m | `terrains.py:110-166` · `SURVEY-star-code.md` 1.9 |
| 논문이 적은 한계 | 「주어진 지형 종류에서 학습된 동작은 비슷한 접촉 패턴을 따르는 경향」 | 논문 VIII-D (arXiv 2601.08485v3, WebFetch 로 문장 확인) |

### 6.3 팀장의 두 가설 판정 (코드 근거)

| 가설 | 판정 | 근거 |
|---|---|---|
| (1) 휴머노이드(2 족) 원본을 4 족에 옮겨서 | **필요조건은 아니다. 증폭 요인일 수는 있다** | 같은 증상이 2 족 코드가 공개되기 **전**에 나왔다. 9/24 ~ 9/28 자체 구현(논문 기반 · Go2 · 12 종 험지) v1: 「이동 중 네 발 모두 비접촉 36.30 % → 32.18 % · 대각 두 발 지지 0 %」, 결론 문장 「반복 도약이 유지」. 9/30 v11(평지): 대각 지지 0.40 % · 전후 지지 38.23 % · 체공 8.47 % (`20261007-ame2-go2-v1-v6.md:140` · `212`). ame2_minimal 첫 커밋은 10/05. 다만 v15 이식에서 G1 상수(400 N 접촉 기준 · 100 m/s² · G1 지형 크기 · PD)가 그대로 넘어갔다면 Go2(공개 사양 약 15 kg 이면 무게 약 150 N, 이 조사가 사양을 다시 재지 않음)에게는 400 N 을 넘는 링크 접촉력만 벌점이라 착지 충격 벌점이 잘 안 걸릴 것으로 본다(`추정`). 넘어갔는지는 v15 코드를 못 봐서 `미확인`. 「전후 지지」 의 정확한 정의도 원파일 미확인 |
| (2) 원래 빠른 보행 설정이 넘어와서 | **부분적으로 맞다. 「빠른 설정」 보다 「민첩성 우선 보상 + 보행 규제 없음」** | AME-2 는 속도 명령이 없고 0.3 ~ 2.0 m/s 안이면 이동 보상이 같다(`rewards.py:180-216`). 특정 고속 gait 설정은 코드에 없다. 대신 험지에서 도약을 허용하고(고저차 ≥ 0.3 m 면 벌점 꺼짐), gait 보상이 없다. 속도가 gait 를 가른다는 문헌(Fu 2021: 1.5 m/s 목표에서 bounce/hopping, Yang 2021: 1.8 m/s 넘어 fly-trot)은 「빠를 때」 의 이야기라, 팀원이 본 「느린 껑충」 은 속도보다 보상 · 지형 쪽 설명(C1 · C7)이 더 맞는다 |

### 6.4 다른 원인 후보 (근거와 함께)

| # | 후보 | 근거 | 확인 방법 |
|---|---|---|---|
| C1 | **도약 벌점이 험지에서 꺼짐** (가장 직접적) | 위 표. 논문 지형 비율에서 희소 지형(Gap 5 · Pallets 5 · Stones 30 · Beam 5) 45 % + 오르기 · 내리기 계열(Climbing Up 20 · Down 5 · Consecutive 5) 30 % = 75 % (`계산`, 부록 A 비율 · `PAPERS-architecture.md` 1 절). 팀원 v15 의 지도 26 × 15 는 G1 설정(2.0 × 1.12 m · 0.08 m)과 점 수가 같다(`20261007-ame2-go2-v1-v6.md:300`). 같은 스캔이면 Go2 앞 1.5 m 안에 0.3 m 고저차가 하나만 있어도 벌점이 꺼진다. 지형 수준별로 얼마나 자주 꺼지는지는 `미확인`. 평지만 재학습하면 벌점이 매 step 켜져 체공이 사라진다는 관찰과 맞는다 | 학습 로그에서 `undesired_leaping` 이 켜진 step 비율을 지형별로 센다 · 고저차 문턱 대신 「발 아래 구멍이 있을 때만 허용」 으로 바꾼 판과 비교 |
| C2 | **지형 크기가 Go2 에게 도약을 요구** | 자체 구현은 오르기 상한 0.40 m (MoE-CTS · JEPLO 논문 보상의 base 높이 목표 0.38 m 보다 높다, `PAPERS-architecture.md` 4 · 5 절), G1 코드는 0.65 m · gap 1.2 m. 큰 장애물은 점프로만 넘을 수 있고, 같은 접촉 패턴을 다른 지형에도 쓰는 경향(논문 VIII-D) | 지형 수준별 접촉 패턴(대각 지지 · 체공 비율) 표 |
| C3 | **보행 규제 보상이 없음** | ame2_minimal · 자체 v13 모두 「보행 위상 보상은 없다」 (`20261007-ame2-go2-v1-v6.md:229`). v12 의 trot 보상 대조는 31 회 무렵 사용자 취소 「no artificial gait cycle training」 (`같은 문서:299`) | feet air time 또는 대각 동기 항을 넣은 짧은 대조 |
| C4 | **대칭 증강을 actor 에 썼다면** | Mittal 2024 Sec III: 「완전히 대칭인 정책은 대칭인 정지 자세에서 한 발을 먼저 들 수 없다」. 좌우가 같이 움직이는 gait(bound · pronk)는 이 제약과 충돌하지 않는다. Barkour 의 점프 specialist 는 좌우 대칭 행동으로 bound 였다(Sec VI-B · App G). ame2_minimal 은 critic 에만 쓴다. v15 가 어떻게 했는지는 `미확인` | v15 의 `symmetry_cfg` 확인 |
| C5 | **목표형 명령 · 마지막 4 s 위치 보상** | 중간 속도를 직접 요구하지 않아 느린 도약도 손해가 없다 (논문 VIII-C 「중간 움직임 제어가 덜 직접적」) | 같은 보상에 속도 하한 항을 둔 대조 |
| C6 | **G1 PD · 행동 배율이 Go2 에 그대로** | G1 Kp 50 ~ 139 (`assets/unitree.py`). Go2 Isaac Lab 기본은 Kp 25 근처(`SURVEY-star-code.md` 3.13 「Kp 25」). 이식본 값 `미확인` | v15 actuator 설정 확인 |
| C7 | **gap 이 「뛰는 것」 을 정답으로 만든다** | 논문 근거: 연속 gap 에서 넘어지지 않으려고 trot → pronk 전환이 저절로 나온다(DeepTransition, 4.4). Foot Position Maps 도 gap 에서 trot → 도약(Sec V-C), Risky Terrains 실기는 디딤돌 위에서 「계속 뛴다」(Sec V-A, 하위 조사 읽기). AME-2 gap 은 ANYmal-D 기준 0.1 → 1.1 m. 즉 gap 에서의 껑충은 버그라기보다 보상이 허용한 「살아남는」 해답이고, 문제는 그 접촉 패턴이 다른 지형 · 평지까지 번진 것이다(논문 VIII-D) | gap 칸과 평지 칸의 접촉 패턴을 따로 잰다 |
| C8 | **학습 초기의 쉬운 끌개** | Walk These Ways: 「pronk 와 trot 가 배우기 쉬워 학습 초기에 pace · bound 를 압도」(Fig. 4 캡션). 규제가 없으면 초기에 잡힌 동기 gait 가 남을 수 있다 | 학습 체크포인트별 접촉 패턴 변화 |

**팀원에게 권할 첫 측정 (제안):** 같은 정책으로 평지 · gap · 돌 각 50 판을 돌려 다리별 접촉 시계열에서 (a) 대각 쌍 동기율 (b) 앞 쌍 · 뒤 쌍 동기율 (c) 네 발 체공 비율 (d) duty factor 를 낸다. C1 이 원인이면 「고저차 ≥ 0.3 m 인 칸」 에서만 (b) · (c) 가 높아야 한다.

---

## 7. 다음 실험 설계안 (제안 · 결정은 팀장)

### 7.0 S2 교훈을 설계 원칙으로

| 원칙 | 어디서 왔나 |
|---|---|
| 지도와 몸 상태를 **처음부터 함께** 학습한다. 눈 먼 정책에 지도를 나중에 붙이지 않는다 | 1 절 #1 · #2 · 논문 공통 (4 · 5 절) · 우리 v2(지도를 처음부터 본 계보)는 gap 99 ~ 100 % (`docs/research/20260928-v2-mvp-report.md`, 다시 재지 않음) |
| 학습량은 E1 과 같은 자릿수(수십 억 transition)로, 표준 runner 와 4,096 ~ 8,192 env 로 돌린다 | 1 절 #2 · #9 |
| 실행 인자 · 보상 가중치 · 명령 범위 · curriculum 상태를 **결과 전에 표로 등록**하고 실행 직전에 기계로 대조한다 | 1 절 #4 · #6 · #7 |
| 평가 명령은 학습 명령 범위 안에서 주 지표를 잡는다 | 1 절 #7 |
| 학습 지형은 발 자리를 골라야만 건너는 수준까지 올린다 | 1 절 #8 |
| 보행 위상(gait)을 숫자로 재는 관문을 결과 전에 건다 | 6 절 (AME-2 껑충 보행) · Walk These Ways Fig. 4 (pronk · trot 이 초기 끌개) |
| 학습 중 지형 조우 · 낙상 · 정지 비율을 로그로 남긴다 | 1 절 #10 |

### 7.1 구조: 「지도 encoder + 몸 상태 encoder → 관절 행동」 (N 판)

이 꼴은 MARG 와 같은 계열이고 S2 B 와도 겉모양은 같다. 다른 점은 **둘 다 처음부터 학습**하고, 몸 상태 쪽에 **속도 · 접촉 추정기**를 두고, 발 디딤 보상으로 발 자리를 다듬는 것이다.

| 부분 | 입력 | 신경망 (출발값 · 제안) | 출력 | 근거 |
|---|---|---|---|---|
| 몸 상태 encoder | proprio 이력 45 × 10 = 450 | MLP 450 → 256 → 128 → 32 (또는 E1 의 MoE 구조를 **학습 가능하게**) | z_prop 32 | E1 구조 · MoE-CTS |
| 추정기 (몸 상태 쪽) | z_prop | MLP → 선속도 v̂ 3 · 발 접촉 ĉ 4. 시뮬 정답으로 회귀 손실 | v̂ · ĉ | MARG II-B3 · Fig. 7 (추정을 빼면 혼합 코스 성공 0.96 → 0.1 · 0.0, `PAPERS-architecture.md` 2 절) |
| 지도 encoder | height scan 187 (지금 격자 그대로 · 비교 연속성) | MLP 187 → 128 → 64 → 16 (MARG 와 같은 폭) | z_map 16 | MARG IV-A |
| actor | [현재 proprio 45, z_prop 32, v̂ 3, ĉ 4, z_map 16] = 100 | 512 → 256 → 128 → 12 | 관절 목표 12 | MARG Fig. 2 · E1 |
| critic | [현재 proprio, 특권 88 (E1 critic 항), height scan 187, 발 주변 높이 4 × 9] | 512 → 256 → 128 → 1 | value | E1 critic · START II-A1 (발 주변 heightmap 을 critic 에) |

- **발 자리는 어디서 「행동으로」 나오나.** 이 구조에서 발 자리는 관절 목표 12 개가 만든 결과다. 발 자리를 직접 출력하지 않는다. 논문 대부분(MARG · START · AME-2 · legged_gym)이 이렇게 하고 발 디딤 보상으로 다듬는다. 발 자리를 명시적 출력으로 내는 계층형(5 절 (라))은 이 판이 징검다리에서 막힐 때의 다음 후보로 둔다.
- **지도 격자.** 첫 판은 지금 187 점(0.1 m)을 그대로 쓴다(E1 · S2 와 비교 연속성). 돌 0.25 ~ 0.3 m 수준에서 0.1 m 는 돌 하나에 2 ~ 3 점이다. DELTA Table III 은 8 cm 격자에서도 작은 돌 성공률이 65.7 ~ 84.0 % 에 머물고 격자를 키우면 95.9 % 가 된다고 적는다(4.4). 그래서 둘째 변형으로 앞쪽으로 치우친 0.05 m 격자(START 는 뒤 0.5 m ~ 앞 1.1 m · 폭 0.8 m · 5 cm, `PAPERS-architecture.md` 3 절)를 둔다. 광선 수가 약 3 배라 비용은 `미측정`.
- **attention 변형은 둘째 단계.** AME-2 식(몸 상태로 query 를 만들어 지도 점들에 MHA)은 「지금 내 몸 상태에서 지도의 어디를 볼지」 를 배우는 구조라 발 자리 고르기와 가장 가깝다. 코드에 단순판(`s2_encoder_policy.py` `AttentionMapEncoder`, query 가 몸 상태를 안 씀)이 있으니, N 판이 서면 같은 harness 에서 encoder 만 바꾼 비교로 넣는다.

### 7.2 보행 위상(gait)을 지키는 장치

| 장치 | 내용 (제안) | 근거 |
|---|---|---|
| 평지 · rough 먼저, 희소 지형은 나중 | 표준 terrain curriculum(`max_init_terrain_level` 낮게)이 「평지 먼저」 역할을 한다. 그래도 관문을 못 넘으면 rough 사전학습 → 희소 지형 fine-tune 의 2 단으로 나눈다. ViNL 은 rough 사전학습이 자연스러운 보행을 주고, 장애물에서 처음부터 배우면 발을 지나치게 드는 부자연스러운 보행이 나왔다고 적는다 (Sec III-A Stage 2). 이것은 「눈 먼 정책에 지도 붙이기」 와 다르다: 사전학습 판도 처음부터 지도를 본다 | legged_gym · MARG curriculum · ViNL |
| feet air time | legged_gym 은 gait 항 없이 feet air time(가중 2)만으로 「항상 trot 로 수렴」 했다(Sec 4.2 · Table 2, lead 원문 확인). robot_lab 에 함수가 있고 E1 에는 연결 안 됨(`robot_lab/tasks/go2/mdp/rewards.py:217`). Isaac Lab Go2 rough 는 가중치 0.01 · 문턱 0.5 s, flat 은 0.25 (`velocity/config/go2/rough_env_cfg.py:53` · `flat_env_cfg.py:19`). MARG 는 Σ(t_air − 0.5) 가중 1.0 (legged_gym 척도) | 코드 · MARG Table I |
| 체공 벌점을 **고저차 조건 없이** | AME-2 식 「고저차 < 0.3 m 일 때만」 을 그대로 쓰지 않는다. 우리 목표 gap 폭에서 trot 로 건널 수 있는 범위까지는 네 발 체공을 늘 벌점 | 6 절 C1 |
| 대각 동기 · 대칭 항 · clock (예비) | robot_lab 의 `joint_mirror` · `action_mirror` · `feet_air_time_variance_penalty` 가 있다(`rewards.py:136` · `158` · `263`). 더 센 장치는 Walk These Ways 식 다리 clock 입력 + 접촉 일정 보상(4.4). 관문을 못 넘을 때만 켠다. 팀원 v12 에서 「인위적 gait 주기 학습 금지」 로 취소된 기록이 있어(6 절 C3) 팀장 결정 사항 | 코드 |
| actor 대칭 증강은 첫 판에서 쓰지 않는다 | 쓰면 별도 변수로 비교 | 6 절 C4 |
| **gait 관문 (결과 전 등록)** | 평지 0.5 m/s 50 판에서 다리 접촉 시계열로 (a) 대각 쌍 동기율 (b) 앞 · 뒤 쌍 동기율 (c) 네 발 체공 비율 (d) duty factor. **먼저 E1 을 같은 도구로 재서** 기준값을 정하고, 새 판은 「(a) ≥ E1 − 10 %p · (c) ≤ E1 + 5 %p」 같은 꼴로 건다. 숫자는 E1 측정 뒤 팀장 확인으로 확정 | 6 절 마지막 제안과 같은 도구 |

### 7.3 발 디딤 보상

| 항 | 정의 · 출발 가중치 | 상태 |
|---|---|---|
| `feet_center_any9_v1` | 발 주변 3 × 3 점(반경 2.2 cm 발 · 0.20 m 아래로 떨어지면 위험), 접지 발에 대해 십자 점 위험 1 · 대각 점 2 · 중심 위험 3 의 벌점(발당 최대 3, 네 발 합 최대 12). MARG feet center 를 참고한 우리 사양(원본 복제 아님) | CPU 구현 · 시험 있음 `bundle/s2_foot_reward.py` · `s2_foot_query.py` · `s2_foot_config.py`. Kit 안 발 높이 질의는 `미검증` (ASTRA 17ag) |
| `feet_stumble` | 수평 접촉력 > 4 × 수직 접촉력. MARG · START 같은 4 배 규칙, 가중 -1.0 | 함수 있음 · E1 미연결 (`rewards.py:305`, `S2-2-DESIGN.md`) |
| START feet edge (대안) | 접지 발이 가장자리 2.5 cm · 5 cm 안이면 1.0 · 0.5, 가중 -1.0 | 논문 확인 (START II-D2), 구현 없음 |
| Extreme Parkour edge (참고) | 접지 발이 가장자리 5 cm 안이면 벌점(Eq. 3). 빼면 시뮬 가장자리 위반 MEV 0.03 → 0.08 (Table 2) | 공개 코드 있음 (feet_edge −1) |
| BeamDojo 식 2 단 (선택) | 1 단계는 구멍을 메운 바닥을 걸으며 발 디딤 보상만 실제 지형으로 받는다(헛디뎌도 안 끝남) → 2 단계 실제 지형. 휴머노이드 결과라 4 족 효과는 `미확인` | BeamDojo Sec IV-C |
| 주의 | MARG Fig. 8(b) 의 0/20 은 발 보상 **셋을 모두** 뺀 값이다(feet center 하나의 효과가 아님, ASTRA 17ag 정정). START 는 FtEdge 를 빼면 gap 5/5 → 0/5 (시험 5 회) | `ROADMAP-20261016.md` · `VERIFY-astra-17ag.md` |

### 7.4 학습 지형 (Go2 크기급)

MARG 는 Go1 으로 학습했다(Go2 와 같은 크기급). 그래서 MARG 의 수준별 치수를 출발값으로 쓸 수 있다(`PAPERS-architecture.md` 2 절, MARG Fig. 4): Single-Gap 수준 1 · 4 · 8 = 10 · 40 · 60 cm, Stones-Everywhere 틈 5 · 15 · 40 cm · 돌 80 · 60 · 30 cm, Beams 폭 30 · 25 · 20 cm. START(Lite3)는 gap 최대 0.7 m · 디딤돌 0.2 m · 틈 x 0.25 m. 제안 출발값: gap 0.10 → 0.50 m, 돌 폭 0.60 → 0.25 m · 틈 0.05 → 0.30 m, 평균대 0.30 → 0.20 m, 희소 지형 합 40 ~ 50 % · 나머지는 E1 지형. 값은 ASTRA 검토로 확정한다.

### 7.5 D435i 현실화 순서

| 단계 | 정책이 보는 지도 | 무엇을 넣나 | 근거 |
|---|---|---|---|
| R0 | 시뮬 정답 높이 (지금) | 없음 | |
| R1 | 정답 + 잡음 | 높이 잡음 · drift · 누락 · 지연 DR. 출발값 AME-2 부록 B(지도 잡음 0.05 m · drift ±0.03 m) · MARG(±5 cm) | `PAPERS-architecture.md` 1 · 2 절 |
| R2 | 카메라가 본 칸만 + 기억 | D435i 장착 자세와 시야(HD 16:9 H 87° · V 58°, 최소 거리 1280×720 에서 280 mm · 424×240 에서 105 mm)로 안 보이는 칸을 mask 0 으로. 발 아래 칸은 보이지 않으므로 **기억**(odometry 로 지도 누적, 또는 GRU)이 필요하다. S2 지도에는 이미 mask 채널이 있다 | D400 데이터시트 Rev.020 값 (`ROADMAP-20261016.md` · ASTRA 17ag) · AME-2 V-A · START TR-Net GRU |
| R3 | depth 로 만든 지도 (student) | R1 · R2 teacher 를 depth student 로 증류. START 식(60 × 60 depth → 재구성 지도) 또는 지도 기반(depth → 고도 지도 → 같은 encoder) | START II-B · AME-2 V |
| R4 | 실기 | Go2 EDU + D435i 장착, 지도 누적용 odometry 원천 결정 | 구매 개체 실측 · 장착 위치 · odometry 품질 `미확인` |

### 7.6 비교 실험 · 대조군 · 등록할 판정 규칙

| 판 | 무엇 | 왜 |
|---|---|---|
| E1 | 지형 안 보는 부모 그대로 (학습 없음) | 바닥 기준 |
| N0 | N 구조, 발 디딤 보상 없음 | 「처음부터 함께 학습」 의 효과 |
| N1 | N0 + `feet_center_any9_v1` + `feet_stumble` | 발 디딤 보상의 효과 (N1 − N0) |
| (예비) N1g | N1 + gait 항 | gait 관문을 못 넘을 때만 |
| (둘째 단계) N1a | N1 의 지도 encoder 만 attention 으로 | 지도 표현의 효과 |

같게 둘 것: 지형 curriculum · 학습량 · env 수 · PPO 설정 · 평가 장면 · 학습 시드(판당 둘 제안: 11 · 12).

**등록 규칙 (결과 전 고정 제안 · S2 와 같은 꼴):**
1. 목표 칸(gap · 징검다리)마다 쌍 차의 Tango 95 % 구간 하한 > 0 이고 평균 차 ≥ 10 %p 면 「효과 있음」. 비교는 N0 − E1 (gap · 징검다리) · N1 − N0 (징검다리 우선).
2. 평지 · 계단은 퇴행 감시: 새 판이 대조보다 구간 전체로 나쁘면 「퇴행」.
3. gait 관문 (7.2) 을 못 넘은 판은 성공률과 상관없이 「보행 실패」 로 따로 보고한다.
4. 주 명령은 학습 범위 안(예: 0.5 m/s), 부 명령 0.3 m/s. 1.0 m/s 는 학습 범위가 1.0 을 포함할 때만.
5. 학습 시드가 둘이면 시드별로 보고하고, 두 시드 방향이 다르면 「불명」.
6. 낮은 결과를 다시 돌려 고르지 않는다. 판정 뒤 기준을 넓히지 않는다.
7. 실행 전 관문: 인자 대조표 일치 · 보상 가중치 · 명령 범위 · curriculum 상태 기록 · (이어 학습이면) 갱신 1 의 KL 상한.

### 7.7 GPU 시간 추정 (추정이다)

기준 실측: E1 은 8,192 env · 20,000 iteration 을 약 23 시간 14 분에 돌았다(`model_0.pt` 10/10 12:48 → `model_20000.pt` 10/11 12:02). 초당 약 47,000 transition. 새 판은 actor 에 height scan 이 들어가지만 광선은 이미 critic 용으로 쏘고 있어 비용 차는 작다고 본다(`미측정`). 발 주변 광선 4 × 9 의 비용도 `미측정`.

| 일 | 계산 | 추정 시간 (GPU 한 장) |
|---|---|---|
| N 판 한 번 (8,192 env · 10,000 iteration · 24 step) | 19.7 억 transition ÷ 47,000/s | 약 11.6 시간 |
| N0 · N1 각 시드 하나 | × 2 | 약 23 시간 |
| N0 · N1 각 시드 둘 | × 4 | 약 46 시간 (2 일) |
| 평가 (120 건, S2 와 같은 도구) | S2 실측 00:25 → 02:22 | 판당 약 2 시간 |
| E1 gait 기준 측정 | 평지 50 판 | 1 시간 이내 (`미측정`) |
| R3 depth student | AME-2 는 지도를 켠 학습이 정답 지도 대비 약 절반 속도 (IV-C) | 위 값의 2 배 이상 (`미측정`) |

GPU 1 은 데스크톱 앱이 대부분 쓰고 있어(약 13.8 GB, `S2-RESULT-PLAN.md` 2 절) 한 장 기준으로 적었다. 11/7 마감까지 남은 날로 보면 N0 · N1 시드 하나씩(약 1 일)이 현실적인 첫 단위다.

### 7.8 팀장이 정할 것

1. N 판을 **처음부터** 학습할까, E1 을 **얼림 없이 길게** 이어 학습할까. 추천: 처음부터 (논문 공통 · S2 교훈). 이어 학습을 고르면 1 절 #3 ~ #7 을 먼저 고친다.
2. gait 관문 수치와, 관문을 못 넘을 때 gait 항(trot 쪽 규제)을 켤지. 팀원 v12 의 「인위적 gait 주기 학습 금지」 결정과 부딪힌다.
3. 학습 지형 치수(7.4)와 희소 지형 비율.
4. 시드 수(하나 · 둘)와 GPU 예산.
5. 주 평가 명령(0.5 m/s 제안).
6. N 판 전에 S2 B 탐침(지도 지우기 · gap 앞 value · 0.5 m/s 평가)을 한 번 할지. 비용은 평가 몇 시간.

---

## 8. 미확인 목록

**S2 · 우리 쪽**
1. update 0 평가(학습 전 대비) 결과. 이 글을 쓰는 동안 돌고 있었다. 「S2 미세조정 자체가 E1 을 망쳤나」 는 이것이 나와야 말할 수 있다.
2. B 가 gap 앞에서 멈추고 기울어진 원인 (1 절의 후보 셋은 가설).
3. S2 학습률이 설계 권고 0.00017 이 아니라 0.001 로 바뀐 경위.
4. S2 학습 중 보상 가중치 · 명령 범위의 실제 중간값. 시작 영수증과 코드로 추론했고 학습 중 값은 기록되지 않았다.
5. N 판의 실제 처리량(actor 에 height scan · 발 주변 광선 4 × 9 · 0.05 m 격자 · depth 렌더 비용). 7.7 의 시간은 E1 처리량에서 계산한 추정이다.
6. `feet_center_any9_v1` 의 Kit 안 발 높이 질의 (CPU 구현 · 시험만 있음).
7. D435i 개체 실측 · 장착 위치 · 지도 누적용 odometry 품질.
8. 우리 평가 장면(「1043 unseen10 d0.5」)의 돌 · gap 치수와 학습 지형 치수의 대조.

**AME-2 · 팀원 실험**
9. 팀원 v15 와 그 뒤 판의 코드(RunPod 볼륨 · 이 조사가 못 엶): 껑충 보행이 나온 판이 무엇인지, actor 대칭 증강 여부, PD · 행동 배율, 지형 크기, 400 N 접촉 기준을 Go2 에 맞게 바꿨는지.
10. 「평지 약 6,000 만 step 재학습」 의 설정(env 수 · 보상 · 도약 벌점이 켜졌는지). 1,024 env 라면 약 2,440 iteration (`계산`).
11. v11 보고의 「전후 지지」 정의 (앞 두 발 · 뒤 두 발 동시인지).

**논문**
12. 그림 막대에만 있는 성공률: AME-2 Fig. 16 일부 · RPL Fig. 6 · Extreme Parkour Fig. 7 · PIE Fig. 4 · SoloParkour Fig. 4 · 5 · DreamWaQ++ Fig. 7 · 11 · WMP Fig. 6.
13. 층 크기 · 학습 예산이 없는 것: ANYmal Parkour · Miki(예산) · DTC(시뮬레이터 · GPU) · Parkour in the Wild(LSTM 크기 · 예산) · NVM(시뮬레이터 · 카메라) · PIE(depth 해상도) · DreamWaQ++(점 개수).
14. legged_gym 의 지형 표본: 논문은 108 점, 코드는 187 점. 논문의 격자 모양은 없다.
15. BeamDojo 의 발바닥 표본점 수 n, 공식 코드.
16. 학회 · 저널 게재판이 arXiv 판과 다른지 (AME-1 Science Robotics 판 · DeepTransition Nature Communications 판 등 열지 않음).
17. 일반 속도 추종 RL 에서 명령 속도 범위나 air time 목표를 바꿔 bound · pronk 수렴을 체계적으로 가른 논문은 찾지 못했다.
18. 하위 조사가 열지 못한 2026 후보: Walking with Terrain Reconstruction (2409.15692, START 전작) · GLAD (2606.00637) · PointWalker (2610.15548) · MARCH (2606.10288) · Mind Your Steps (2606.08253) · StairMaster (2606.25765). 제목 · 내용 미확인.
19. 4.2 ~ 4.4 의 숫자는 하위 조사의 원문 읽기를 옮긴 것이다. lead 가 원문에서 다시 잰 것은 4.0 에 적은 문장과 DELTA Table III · Walk These Ways Fig. 4 캡션 · DeepTransition 초록, 그리고 새 논문 8 편의 arXiv 제목 · 날짜(arXiv API)뿐이다.

---

## 9. 이 조사가 한 일과 남긴 것

- **읽기만 함:** S2 묶음 코드 · manifest · 요청 파일 · `updates.jsonl`(A · B 2,000 줄씩) · `result.json` · 체크포인트 0 · 2000 (CPU 로 `torch.load`, GPU 안 씀) · E1 체크포인트 시각 · robot_lab · Isaac Lab 소스 · foothold-lab 문서 · GitHub 저장소(`gh`).
- **저장소 밖에 만든 임시 파일 (지워도 됨):** `C:/Users/AI-WS01/s2_lab/_research_tmp/` (집계 스크립트 둘 · 초안 조각 · arXiv 목록), `C:/Users/AI-WS01/s2_lab/_research_repos/` (ame2_minimal · Kitjesen/ame2 얕은 clone, 실행 안 함), `C:/Users/AI-WS01/s2_lab/_research_pdf/` (논문 PDF 셋), 하위 조사가 만든 `C:/Users/AI-WS01/AppData/Local/Temp/paperverify.bkwlIP/`.
- **저장소 안에 만든 것:** 이 파일 하나 (`inbox/jay/20261018-next-arch/`). 커밋 · 푸시 · 이슈 댓글은 하지 않았다. 다른 사람의 커밋 안 된 파일은 건드리지 않았다.
- **하위 조사 셋:** (1) 지형 인지 RL 고전 9 편 (2) depth · parkour 10 편 (3) gait · 발 디딤 보상 · 2025 ~ 2026 논문 11 편. 셋 다 원문을 내려받아 읽고 위치를 달아 보고했다.

