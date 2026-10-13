> 분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 · 코드와 CPU 시험 (학습 · Isaac · GPU 실행 없음)
> 작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 2026-10-13 19:35
> 근거: foothold-lab `inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md` 3 절 · 4 절 · `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py` · `networks/moe.py` · `algorithms/moe_cts.py` · E1 `params/agent.yaml` · `params/env.yaml` 446 ~ 490 · 1145 ~ 1177 · IsaacLab `envs/mdp/observations.py` 292 ~ 300 · `sensors/ray_caster/ray_caster.py` 218 ~ 248 · `patterns/patterns.py` grid_pattern · `utils/warp/ops.py` raycast_mesh
> 요지: 설계 3 절 구조 (지도 encoder 374 → 128 → 64 · actor 첫 층의 지도 64 열 0 시작 · no_grad 풀림 · 부모 critic · 새 Adam) 와 B 의 height · mask 의미를 코드로 만들었다. 시험 T1 ~ T7 은 7/7 PASS (115 칸) · 변이 21 개 ALL CAUGHT 21/21. 부모 체크포인트 sha256 은 시험 전후 같다
> 상태: CPU 시험 · 변이까지. Isaac 안의 실제 RayCaster 자료 · GPU · 학습기 (runner · algorithm) 연결은 하지 않았다 (7 절 미확인)

# S2 A/B 입력 경로 1 단계

표기: **확인됨** = 이 폴더의 시험을 돌려 잼 · **소스 확인** = 코드를 열어 읽음 (실행은 안 함) · **미확인** = 재지 않음.

## 1. 만든 것

| 파일 | 행 | 하는 일 |
|---|---|---|
| `s2_map_obs.py` | 117 | RayCaster 자료 (`pos_w` · `ray_hits_w`) → B 의 height 187 · mask 187 · A 의 상수 (모두 0) · 광선 몸체 좌표 · 시험용 RayCaster 흉내 (`ray_hits_from_terrain`) |
| `s2_policy.py` | 256 | E1 20000 을 CPU 로 strict 적재 (`load_parent_cpu`) · `S2MapActorCritic` (A/B) · `make_optimizer` (새 Adam · 부모 마지막 lr) |
| `test_s2.py` | 559 | T1 ~ T7. 기대값은 손으로 적음. 부모는 시험이 손으로 적은 구조로 스스로 짓고 strict 적재 |
| `mutate_s2.py` | 191 | 사본에서 관문을 하나씩 망가뜨려 시험이 잡는지 확인 (원본 sha256 시작 · 끝 대조) |
| `test_s2.log` · `mutate_s2.log` | | 마지막 실행 기록 (2026-10-13 19:3x) |

실행 (GPU 를 가림 · 그 환경에 설치한 것 없음):

```
cd C:/isaac/ext/go2_rl_robotlab/_eval/s2
CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I test_s2.py      # 약 5 초
CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I mutate_s2.py    # 약 2 분 (사본 22 번)
```

`test_s2.py` 는 torch 를 부르기 전에 `CUDA_VISIBLE_DEVICES=-1` 을 스스로 건다. `sys.dont_write_bytecode` 로 rsl_rl · IsaacLab 폴더에 pyc 를 쓰지 않는다 (실행 뒤 두 폴더에 새 파일 없음을 `find -newer` 로 확인함). 변이 사본은 `%TEMP%/s2_mut_*` 에 만들고 끝나면 지운다.

## 2. 구조 (설계 3 절 · 확인됨)

```
지도 입력 m = [height 187, mask 187]     열 0 ~ 186 height · 187 ~ 373 mask · 광선 순서는 센서 순서 (grid xy)
z_map = map_encoder(m)                   rsl_rl MLP: Linear(374, 128) · ELU · Linear(128, 64)  (출력은 선형)
pre   = actor_in([latent 32, single_obs 45]) + actor_in_map(z_map)
action mean = actor_rest(pre)            actor_in · actor_rest 는 부모 actor 값 그대로 · actor_in_map 은 [512, 64] 0 시작
value = critic([latent.detach(), critic obs 275])   부모 evaluate(is_teacher=False) 와 같은 식
```

- 부모에서 복사: student encoder (16 매개변수) · actor 8 · critic 8 · std = 33 열쇠. teacher encoder 6 열쇠는 가져오지 않는다. 새 열쇠 5 개 (`map_encoder.network.{0,2}.{weight,bias}` · `actor_in_map.weight`). 모두 깊은 복사라 부모와 저장소를 나누지 않는다 (T7).
- `act()` 에 `no_grad` 가 없다. PPO gradient 가 student encoder 까지 간다 (T5).
- A · B 는 같은 시드 (`MAP_INIT_SEED = 0`) 로 map encoder 를 지어 state_dict 가 열쇠 · 값 모두 같다 (T4). 다른 것은 입력뿐이다.
- A 정책은 상수가 아닌 지도 입력이 들어오면 `ValueError` 를 낸다 (`guard_a_constant`, 기본 켬). 파이프라인 실수로 A 가 지형을 보는 길을 막는 이중 관문이다.
- `make_optimizer`: 새 Adam 하나에 student_encoder · map_encoder · actor · critic · std 다섯 묶음, 모두 같은 lr. 부모 마지막 lr 은 체크포인트 `optimizer_state_dict` 네 묶음 모두 `0.00017085937500000009` (확인됨 · `load_parent_cpu` meta `last_lr`).

### B 의 height · mask (설계 3 절 · 확인됨)

| 경우 | height | mask |
|---|---|---|
| 맞음 · 센서 (base) 아래 깊이 ≤ 1.0 m | clip(센서 z − 맞은 점 z − 0.5, −1, 1) | 1 |
| 안 맞음 (inf · −inf · nan) | 1 (「깊음」 쪽) | 0 |
| 맞음 · 깊이 > 1.0 m | 1 | 0 |
| 맞음 · 센서보다 위 (벽) | clip 으로 −1 | 1 |

「센서 z」 는 RayCaster `data.pos_w` 의 z 이고, 이것은 base 위치다. env.yaml 의 `offset (0, 0, 20)` 은 `ray_starts` 에만 더해지고 `pos_w` 에는 안 들어간다 (`ray_caster.py` 218 ~ 224 · 238 ~ 248 · **소스 확인**). 그래서 설계 T1 의 「센서 0.4 m」 는 base 높이 0.4 m 다.

## 3. 시험 T1 ~ T7 (확인됨 · 7/7 PASS · 115 칸)

| 시험 | 칸 | 손으로 적은 기대값 · 대조 대상 |
|---|---|---|
| T1 평지 | 10 | 센서 0.4 · 맞은 점 0 → −0.1 · mask 1 (187 칸). 세계 높이 10 m 에 선 env · 맞은 점 xy 무작위도 같은 값. 배치 [height, mask]. A 는 374 칸 모두 0. IsaacLab `height_scan` 의 offset 기본 0.5 와 식을 소스 문자열로 대조 |
| T2 단차 · 구멍 | 12 | 앞쪽 88 광선 (`k % 17 >= 9`) 만 −0.2. inf · nan · −inf · 깊이 2 m 구멍 바닥 (센서 아래 2.4 m) · 센서 아래 1.1 m → mask 0 · height 1. 센서 아래 0.9 m → mask 1 · 0.4. 벽 → −1. mask 0 칸 수 정확히 5. yaw 0 · ±90° · 180° 에서 몸 앞쪽 광선이 세계의 맞는 쪽을 봄 |
| T3 광선 순서 | 27 | 광선 0 · 1 · 16 · 17 · 93 · 186 의 몸체 좌표를 손으로 적고, IsaacLab `patterns.py` 를 파일에서 직접 불러 (Isaac 앱 없이 CPU) `grid_pattern` 과 187 광선 비트 동일. env.yaml height_scanner 설정 8 줄 대조. 광선 k 의 z = 0.001 k 로 순서 보존 |
| T4 0 초기화 동치 | 18 | 실제 E1 model_20000 을 CPU strict 적재한 부모의 `act_inference` 와 B (무작위 지도 둘 · 거친 지형 지도 · ×100 큰 값) · A 의 action 이 int32 로 본 비트까지 같음 (N 256). `act()` 의 평균 · std, `evaluate` 도 비트 동일. 대조군: 새 열에 0.01 × 정규난수 → 지도 1 vs 2 action 최대 차 1.304e-01 · 부모 대비 1.582e-01 |
| T5 gradient 경로 | 27 | PPO 손실 모양 (clip 0.2 surrogate · clipped value loss · entropy 0.01 · grad norm 1.0 · `moe_cts.py` 297 ~ 334 와 agent.yaml 값). 갱신 전 (A · B): 새 열 gradient 있음 · map encoder 4 매개변수 gradient 정확히 0 (None 아님) · student encoder 16 매개변수 모두 gradient 있음. 한 번 Adam 갱신 (lr 1.7086e-4) 뒤: B 의 map encoder 4 매개변수 모두 0 아님 · A 는 첫 층 weight 정확히 0 · bias 와 둘째 층은 0 아님. B 는 지도를 바꾸면 action 최대 차 1.726e-02. value 손실만으로는 student encoder gradient 0 (detach) · 지도 경로 gradient 없음. optimizer 가 모든 매개변수를 한 번씩 덮음 |
| T6 A 의 정보 차단 | 9 | 평지 · 거친 지형 (단 · inf 구멍 · −2 m 구덩이) · 직접 넣은 구멍 셋에서 A 지도 입력 = 0 (374 칸) · A action 비트 동일 (새 열을 0.01 로 채운 상태에서도). B action 은 지형 · 구멍에 따라 바뀜. A 정책에 B 지도를 넣으면 `ValueError` |
| T7 부모 보존 | 12 | 체크포인트 sha256 `c8951b79…f47e8` (sha256sum 으로 잰 값을 손으로 적음) 이 시험 전 · 후 같음. T4 ~ T6 과 T7 안의 lr 1e-2 갱신 뒤에도 부모 모듈 39 열쇠가 파일 값과 같음. 복사 대상 33 열쇠 값이 부모와 같음 (손으로 적은 열쇠 대응). 새 열쇠 5 개. teacher 없음. S2 매개변수와 부모의 저장소 공유 없음 |

시험 뒤 `sha256sum` 으로 따로 잰 체크포인트 해시도 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8` 다.

## 4. 변이 (확인됨 · ALL CAUGHT 21/21)

변이 없는 사본이 먼저 7/7 PASS 인지 보고 (BASELINE), 변이마다 새 사본에서 문자열 한 곳만 바꾼다 (정확히 한 번 걸리지 않으면 실행기가 멈춘다). 기대한 시험이 FAIL 해야 CAUGHT.

| id | 망가뜨린 것 | 기대 | 실제 FAIL |
|---|---|---|---|
| m01 | A 에 mask 실제 값 | T6 | T1 · T5 · T6 |
| m02 | A 에 height 실제 값 | T6 | T1 · T5 · T6 |
| m03 | 새 64 열을 0 이 아닌 값 (std 1e-3) 으로 시작 | T4 | T4 · T5 |
| m04 | height 부호 반대 | T1 | T1 · T2 · T3 |
| m05 | inf (안 맞음) 를 mask 1 로 | T2 | T2 · T3 · T6 |
| m06 | 광선 순서 ij | T3 | T2 · T3 |
| m07 | student encoder 의 no_grad 를 그대로 둠 | T5 | T5 · T7 |
| m08 | map encoder 출력 detach | T5 | T5 |
| m09 | optimizer 에서 map encoder 빠짐 | T5 | T5 |
| m10 | critic 의 latent.detach 뺌 | T5 | T5 |
| m11 | 1 m 보다 깊은 곳도 mask 1 | T2 | T2 |
| m12 | mask 0 칸 height 0 | T2 | T2 · T3 |
| m13 | height clip 뺌 | T2 | T2 |
| m14 | 지도 배치 [mask, height] | T1 | T1 · T2 · T3 · T6 |
| m15 | actor 뒤쪽을 부모와 공유 (깊은 복사 안 함) | T7 | T7 |
| m16 | std 를 1 로 | T4 | T4 · T7 |
| m17 | A · B 의 map encoder 시드가 다름 | T4 | T4 |
| m18 | A 상수 관문 끔 | T6 | T6 |
| m19 | actor 입력 순서 [single_obs, latent] | T4 | T4 |
| m20 | S2 를 지으며 부모 모듈 값을 바꿈 (메모리 안) | T7 | T4 · T7 |
| g01 | (관문 자체) T7 의 sha256 기대값만 틀린 값으로 | T7 | T7 |

원본 세 파일의 sha256 은 변이 실행 시작 · 끝이 같다. g01 은 구현이 아니라 해시 대조가 헛돌지 않는지를 본다 (체크포인트 파일은 건드리지 않는다. 파일 자체를 바꾸는 변이는 위험해서 만들지 않았다).

## 5. 설계와 다르게 한 곳 · 까닭

1. **actor 첫 층을 두 장으로.** 설계는 「actor 첫 층 입력 77 → 141」. 코드는 `Linear(77, 512)` (부모 값 그대로) + `Linear(64, 512, bias 없음, 0 시작)` 의 합이다. `[W_parent | W_map] @ [x; z] + b` 와 수식이 같고, Adam 은 원소별 · grad clip 은 전체 norm 이라 학습도 같다. 까닭: 0 초기화 동치를 「부모와 같은 모양의 matmul + 정확한 0」 으로 만들어 BLAS 가 K (77 vs 141) 에 따라 합 순서를 바꿔도 비트 동일이 깨지지 않게 한다. 한 번 재 본 바로는 CPU (MKL · 32 스레드 · N 256) 에서 141 열 한 장도 비트 동일이었다. GPU 는 미확인. 141 열 행렬이 필요하면 `actor_first_layer_weight()` 가 [512, 141] 로 이어 준다.
2. **A 상수 관문 추가.** 설계에는 없다. A 정책이 상수가 아닌 지도를 받으면 예외. 학습 때 GPU 동기화 한 번이 붙는다 (비용 미확인 · `guard_a_constant=False` 로 끌 수 있으나 T6 의 관문 칸이 FAIL 한다).
3. **「몸 아래 1 m 안」 의 기준.** 설계 문구에 기준점이 없어 RayCaster `pos_w` (base 원점) 의 z 에서 잰 깊이 ≤ 1.0 m (경계 포함) 로 두었다. 발 · 지면 기준이 의도였다면 바꿔야 한다 (`MASK_MAX_DEPTH`).
4. **T2 의 「깊이 2 m」.** 구멍 바닥 z = −2 m (센서 아래 2.4 m) 로 두었고, 1 m 경계 양쪽 (0.9 m · 1.1 m) 칸을 더했다.
5. **T5 의 손실.** 예시였던 「행동 평균 제곱 오차」 대신 부모 알고리즘과 같은 꼴의 PPO 손실 (clip surrogate · clipped value · entropy · grad clip 1.0) 을 썼다. 갱신 뒤 gradient 를 다시 잴 때 같은 rollout 을 쓴다.
6. **시험을 더한 곳.** T3 에 광선 1 번 · env.yaml 설정 대조 · 순서 보존, T4 에 `act()` · `evaluate` · A/B 같은 출발점 · `load_parent_cpu` 대조, T5 에 optimizer 덮음 · value 손실 경로, T7 에 갱신 뒤 부모 보존 · 저장소 공유.

설계 문구 중 코드와 대조해 맞은 것: 2 절 표의 차원 (student 450 · 은닉 512 · 256 · 256 · expert 8 · latent 32 · actor 77 → 512 · 256 · 128 → 12 · scalar std · 정규화 끔) · `act(is_teacher=False)` 의 `no_grad` (210 ~ 224) · height_scanner 446 ~ 480 행. critic obs 는 체크포인트에서 275 (critic 첫 층 307 − 32) 다.

## 6. 설계 5 절 물음에 닿는 사실 (판단은 하지 않음)

- 부모는 student encoder 를 따로 Adam (lr 0.001 · `optimizer_stu_enc_state_dict`) 으로, 재구성 손실 + load balance 손실 (`load_balance_coef` 0.01) 로 학습했다. S2 에서는 encoder 가 PPO gradient 만 받고 lr 은 PPO 묶음과 같은 1.7086e-4 다. MoE gating 의 load balance 손실이 빠진다.
- 부모 critic 의 height 항 (IsaacLab `height_scan`) 은 안 맞은 광선을 −inf → clip −1 (「높음」 쪽) · × 2.5 로 본다 (**소스 확인** · `observations.py` 300 의 식과 env.yaml 1173 ~ 1176 clip · scale. 실행은 안 함). B 의 actor 지도는 같은 광선을 height 1 (「깊음」 쪽) · mask 0 으로 본다. 같은 광선을 critic 과 actor 가 반대쪽으로 읽는다. 실제 S2 지형에서 안 맞는 광선이 얼마나 나오는지는 미확인.
- B 의 height 는 clip [−1, 1] 만 하고 × 2.5 는 하지 않는다 (설계 그대로). critic 의 높이 항은 [−2.5, 2.5] 다.

## 7. 미확인

- Isaac 안의 실제 RayCaster 자료 (`pos_w` · `ray_hits_w`) 로 `s2_map_obs` 를 돌린 적 없다. `pos_w` 가 base 위치라는 것은 소스 읽기로만 확인했다.
- 0 초기화 동치는 CPU 에서만 쟀다. GPU · 다른 배치 크기 · 다른 스레드 수에서의 비트 동일은 미확인.
- 학습기 연결 없음: env 에 `map` 관측 그룹을 넣는 법, `RolloutStorageCTS` 가 `map` 을 저장 · 미니배치로 나누는지, `MoECTS` 대신 PPO 만 쓰는 알고리즘. 이번 범위 밖이다.
- no_grad 를 푼 뒤 첫 몇 갱신에서 부모 latent 분포가 무너지는지 (설계 5.3) 는 재지 않았다.
- A 상수 관문의 GPU 학습 중 비용.
