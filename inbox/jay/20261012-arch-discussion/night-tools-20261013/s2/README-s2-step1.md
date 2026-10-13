> 분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 판 2 · 코드와 CPU 시험 (학습 · Isaac · GPU 실행 없음)
> 작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 판 1 2026-10-13 19:35 · 판 2 2026-10-13 23:47
> 근거: foothold-lab `inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md` 6 절 (위 1 ~ 5 절과 다르면 6 절) · `VERIFY-astra-17d.md` 6.1 ~ 6.4 · `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py` · `networks/moe.py` · `algorithms/moe_cts.py` · E1 `params/agent.yaml` · `params/env.yaml` 446 ~ 490 · 865 ~ 1177 · IsaacLab `envs/mdp/observations.py` 292 ~ 300 · `sensors/ray_caster/ray_caster.py` 218 ~ 248 · 278 ~ 279 · `patterns/patterns.py` grid_pattern · `utils/math.py` quat_apply_yaw · `utils/warp/ops.py` 71
> 요지: ASTRA 17d 반영. mask 를 지형 충돌 여부로 바꾸고 (유한 hit 은 mask 1 · 정상 miss 만 mask 0 · 1 m 깊이 분류 삭제), 센서 · hit 의 NaN 은 구멍이 아닌 고장으로 따로 센다 (A · B 같은 관문). critic 점검 함수와 encoder 고정 구간 (W · r 기본값 없음) 을 더했다. 시험 T1 ~ T10 은 10/10 PASS (187 칸) · 변이 39 개 + 관문 자체 1 개 ALL CAUGHT 40/40. 부모 체크포인트 sha256 은 시험 전후 같다
> 상태: CPU 시험 · 변이까지. S2 학습 기동은 보류 (설계 6 절). Isaac 접속 · reset 시점 · 학습기 연결 · 공정성 등록은 하지 않았다 (7 절)

# S2 A/B 입력 경로 1 단계 · 판 2

표기: **확인됨** = 이 폴더의 시험을 돌려 잼 · **소스 확인** = 코드를 열어 읽음 (실행은 안 함) · **미확인** = 재지 않음.

## 1. 판 1 에서 바뀐 것

| 판 1 (2026-10-13 19:35 · ASTRA 17d 가 검증한 판) | 판 2 | 근거 |
|---|---|---|
| mask 1 = 「유한하고 base 아래 1 m 안」. 1 m 보다 깊은 유한 바닥 · NaN · 안 맞음을 모두 (height 1, mask 0) | **mask = 지형 충돌 여부.** 유한 hit 은 mask 1 · height clip [−1, 1] (깊은 바닥도 mask 1). 정상 miss (xyz 모두 +inf) 만 (1, 0) | 설계 6 절 · 17d 6.2 |
| 센서 NaN · hit NaN 도 구멍 (1, 0) | 센서 위치 비유한 · ray packet 손상 (NaN · −inf · 일부 좌표만 inf) 은 **고장**. 자리표시 (0, 0) 로 두고 `MapFaults` 로 돌려줌 · `strict=True` 면 `MapObsFault`. 판정은 A · B 가 같은 함수로 같게. `RunValidityGate` 가 rollout 단위로 세고 하나라도 있으면 무효 | 설계 6 절 · 17d 6.2 「기동 전 필수」 |
| critic 은 「부모 그대로」 | 구조 · 가중치는 부모에서 시작 · 값은 그대로. `critic_check` 가 critic 입력 · value 유한성과 정상 miss 광선 칸의 critic 입력 값을 기록 (부모 식으로 −2.5) | 설계 6 절 · 17d 6.2 마지막 문단 |
| encoder no_grad 를 조건 없이 풂 | `EncoderSchedule`: 처음 W update 동안 student encoder 고정 (requires_grad 끔 · 그 묶음 lr 0), 그 뒤 encoder lr = r × actor lr. **W · r 은 기본값 없이 인자로만** | 설계 6 절 · 17d 6.3 |
| 「부모 Adam 은 차원이 달라 못 씀」 | 철회. 새 Adam 은 「선택」 으로 적음 | 설계 6 절 · 17d 6.1 |
| 시험용 RayCaster 흉내가 `s2_map_obs.py` 안 (yaw 를 손으로 회전) | `test_s2.py` 로 옮기고 IsaacLab 의 `grid_pattern` · `quat_apply_yaw` 를 파일에서 직접 불러 ray_starts (offset z 20 포함) 를 만든다 | 17d 6.4 |

판 1 의 파일 일곱 개 (코드 · 시험 · 변이 · README · 기록) 는 `v1/` 에 그대로 두었다. 17d 8 절이 적은 판 1 해시 (`s2_map_obs.py` 451cfed9… · `s2_policy.py` 8897ed64… · `test_s2.py` 0f82662d… · README bed6803c…) 와 `v1/` 사본의 sha256 이 같다.

## 2. 파일

| 파일 | 행 | 하는 일 |
|---|---|---|
| `s2_map_obs.py` | 192 | `classify_rays` (유효 hit · 정상 miss · 고장) · `height_and_mask` · `map_obs` (A/B · 같은 고장 판정) · `MapFaults` · `MapObsFault` · `RunValidityGate` |
| `s2_policy.py` | 338 | E1 20000 CPU strict 적재 · `S2MapActorCritic` · `EncoderSchedule` · `make_optimizer` (W · r 필수) · `critic_check` |
| `test_s2.py` | 793 | T1 ~ T10. 기대값은 손으로. 부모는 시험이 손으로 적은 구조로 스스로 짓고 strict 적재. T7 은 맨 마지막에 돈다 |
| `mutate_s2.py` | 241 | 변이 39 개 + 관문 자체 1 개. 바꿀 문자열이 원본에 정확히 한 번 있는지 먼저 본다 |
| `test_s2.log` · `mutate_s2.log` | | 마지막 실행 기록 |
| `v1/` | | 판 1 사본 (고치지 않음 · import 하지 않음) |

```
cd C:/isaac/ext/go2_rl_robotlab/_eval/s2
CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I test_s2.py      # 약 6 초
CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I mutate_s2.py    # 약 4 분 (사본 41 번)
```

## 3. 지도 입력의 의미 (판 2 · 확인됨)

| 광선 | height | mask | 고장 |
|---|---|---|---|
| 센서 정상 · hit xyz 유한 | clip(센서 z − hit z − 0.5, −1, 1) | 1 | 아님 |
| 센서 정상 · hit xyz 모두 +inf (raycast_mesh 의 안 맞음) | 1 | 0 | 아님 (정상 miss) |
| 센서 정상 · hit 에 NaN · −inf · 일부 좌표만 inf | 0 (자리표시) | 0 | ray packet 고장 |
| 센서 위치에 NaN · inf | 0 (그 env 의 187 칸 모두) | 0 | 센서 고장 (env 하나로 셈 · packet 쪽에 두 번 세지 않음) |

- 「센서 z」 는 RayCaster `data.pos_w` 의 z, 곧 base 위치다. offset (0, 0, 20) 은 `ray_starts` 에만 더해진다 (`ray_caster.py` 218 ~ 224 · 278 ~ 279 **소스 확인**). T8 은 IsaacLab 식으로 만든 ray 시작 z 가 20.4 일 때 지면 0.3 의 height 가 −0.4 임을 본다 (20 m 를 다시 더하면 clip 1).
- 자리표시 (0, 0) 는 정상 hit (mask 1) 와도 정상 miss (1, 0) 와도 겹치지 않는다. 고장 칸의 값은 뜻이 없고, 그 rollout 은 관문에서 무효가 된다.
- A 는 지도 값으로 언제나 0 (374 칸) 을 받지만 고장 판정 · strict 예외는 B 와 같은 함수를 지난다.

## 4. 시험 T1 ~ T10 (확인됨 · 10/10 PASS · 187 칸)

| 시험 | 칸 | 손으로 적은 기대값 |
|---|---|---|
| T1 평지 | 11 | 센서 0.4 · hit 0 → (−0.1, 1) 187 칸 · 고장 0 · 세계 높이 10 m · hit xy 무작위에도 같음 · 배치 [height, mask] · A 는 0 |
| T2 단차 · 정상 miss · 깊은 바닥 | 9 | 앞쪽 88 광선만 −0.2. 정상 miss (1, 0). 구멍 바닥 −2 m · −10 m → (1, 1). 센서 아래 0.9 m → (0.4, 1) · 1.1 m → (0.6, 1) (1 m 분류 없음). 센서보다 1.1 m 위 → (−1, 1) · 0.05 m 위 → (−0.55, 1). mask 0 은 정상 miss 한 칸뿐 · 고장 0 |
| T3 광선 순서 | 27 | 광선 0 · 1 · 16 · 17 · 93 · 186 의 몸체 좌표 · IsaacLab `grid_pattern` 과 187 광선 비트 동일 · env.yaml height_scanner 8 줄 · 순서 보존 |
| T4 0 초기화 동치 | 18 | B (지도 4 종) · A 의 action 이 부모 `act_inference` 와 int32 비트 동일. `act()` 평균 · std · `evaluate` 비트 동일. 대조군 (새 열 0.01): 지도 1 vs 2 최대 차 1.304e-01 · 부모 대비 1.582e-01 |
| T5 gradient 경로 | 27 | 시험 값 W 0 · r 1 (고정 없음). 갱신 전 map encoder gradient 정확히 0 · 새 열 · student encoder 16 매개변수 gradient 있음. 한 번 갱신 뒤 B map encoder 4 매개변수 0 아님 · A 첫 층 weight 0 (bias 아님). B 지도 바꿈 action 최대 차 1.143e-02. value 손실만으로는 student encoder gradient 0 |
| T6 A 의 정보 차단 | 9 | 평지 · 거친 지형 · 정상 miss 셋에서 A 지도 입력 0 · A action 비트 동일 (새 열 0.01). B 는 바뀜. A 에 B 지도 → ValueError |
| T8 입력 의미 (17d 6.4) | 31 | 아래 |
| T9 encoder 고정 구간 | 31 | 아래 |
| T10 critic 점검 | 12 | 아래 |
| T7 부모 보존 (맨 마지막) | 12 | 체크포인트 sha256 `c8951b79…f47e8` 시험 전 · 후 같음 · 모든 시험 뒤 부모 모듈 39 열쇠 == 파일 · 복사 33 열쇠 · 새 5 열쇠 · 저장소 공유 없음 |

**T8:** 센서 (NaN, 0, 0.4) · (0, 0, inf) 인 env 두 개만 센서 고장 · packet 고장 0 · 그 env 지도는 (0, 0) 이고 정상 miss 꼴 (1, 0) 이 없음 · 정상 env 는 그대로. packet: z NaN · z −inf · x NaN · z 만 +inf · (inf, inf, −inf) 다섯이 고장 (광선 10 · 11 · 12 · 13 · 15) 이고 xyz +inf (광선 14) 는 정상 miss. strict: 정상 miss 만이면 예외 없음 · 센서 · packet 고장은 `MapObsFault` (A 도). A · B 고장 판정 텐서가 같음. 관문: 정상 miss 만이면 유효 · packet 고장 뒤 counts 가 손으로 적은 dict 와 같고 무효 · `require_valid` 예외 · advantage NaN 도 무효. 20 m: 위 3 절. 평행 이동 · yaw (IsaacLab `quat_apply_yaw`): 0.1 m 블록이 걸리는 광선이 yaw 0 앞 0.3 m → 96 · 0.3 m 앞으로 옮기면 93 (발밑) · yaw +90 에서 세계 +y 0.3 m → 96 (몸 앞) · 그쪽으로 옮기면 93 · yaw +90 에서 세계 +x → 42 (몸 오른쪽) · yaw −90 에서 세계 +x → 144 (몸 왼쪽).

**T9:** `make_optimizer` · `EncoderSchedule` 의 W · r 에 기본값 없음 (signature) · 없이 부르면 TypeError · None TypeError · 음수 · 정수 아님 · bool · NaN · inf ValueError. 시험 값 W 3 · r 0.25 (등록 값 아님): 만들자마자 encoder requires_grad 꺼짐 · update 0 ~ 2 는 고정 (encoder gradient None · 매개변수가 처음과 비트 동일 · actor 는 움직임) · encoder lr 0 · 나머지 lr 부모 마지막 값. update 3 부터 encoder lr = 4.271484375000002e-05 (0.25 × 0.00017085937500000009 손 계산 · 정확히 같음). 풀린 첫 update 에서 encoder 원소 걸음이 모두 r × lr (+ float32 ulp) 이하 · 최대 4.2714e-05 · encoder Adam step 1 (고정 중 moment 안 쌓임) · actor step 4.

**T10:** `CRITIC_HEIGHT_START` 88 = 3+3+3+3+12+12+12+12+12+16 (env.yaml critic 항 순서를 시험이 파일에서 읽어 대조 · 체크포인트 critic 첫 층 307 = 32 + 88 + 187). critic height 를 IsaacLab 식 (clip 뒤 × 2.5) 으로 손으로 만들고: 정상 miss 7 광선 칸의 critic 입력 값이 모두 −2.5 · critic 입력 NaN 1 칸 1 env · value NaN 1. 점검 앞뒤로 critic 입력 (NaN 포함 비트) · value 비트 동일. A · B 점검 결과 같음. 관문: 고장 없는 env 는 유효 · NaN 뒤 무효.

## 5. 변이 (확인됨 · ALL CAUGHT 40/40)

변이 없는 사본이 먼저 10/10 PASS 인지 보고 (BASELINE), 원본 세 파일 sha256 을 시작 · 끝에 대조했다 (같음). 실제 FAIL 은 `mutate_s2.log`.

| 묶음 | id | 망가뜨린 것 | 기대 시험 |
|---|---|---|---|
| 지도 (판 1 부터 · 새 의미로) | m01 · m02 | A 에 mask · height 실제 값 | T6 |
| | m04 | height 부호 반대 | T1 |
| | m05 | 정상 miss (+inf) 를 hit (mask 1) 로 | T2 |
| | m06 | 광선 순서 ij | T3 |
| | m11 | 판 1 의 1 m 깊이 분류를 되살림 | T2 |
| | m12 · m13 | 정상 miss height 0 · clip 뺌 | T2 |
| | m14 · m14b | 배치 [mask, height] (map_obs_b · map_obs) | T1 |
| 지도 (판 2 고장 분리) | n01 | 센서 NaN · inf 를 못 알아봄 | T8 |
| | n02 | 판 1 처럼 비유한 hit 를 모두 정상 miss 로 | T8 |
| | n03 · n04 | z 만 +inf 인 packet 을 miss 로 · x NaN 을 hit 로 | T8 |
| | n05 | 20 m offset 을 센서 높이에 다시 더함 | T8 |
| | n06 | A 만 고장 판정 · strict 건너뜀 | T8 |
| | n07 · n08 | 고장 자리표시를 (1, 0) 으로 · strict 끔 | T8 |
| | n09 · n10 | 관문이 packet 고장 · value NaN 무시 | T8 · T10 |
| 정책 (판 1 부터) | m03 · m16 · m17 · m19 | 새 열 0 아닌 시작 · std 1 · A/B 시드 다름 · 입력 순서 | T4 |
| | m07 · m08 · m09 · m10 | forward 에 no_grad · map encoder detach · optimizer 누락 · critic detach 뺌 | T5 |
| | m15 · m20 | 부모와 저장소 공유 · 부모 값 바꿈 | T7 |
| | m18 | A 상수 관문 끔 | T6 |
| 정책 (판 2) | p01 · p02 · p03 · p04 · p05 | 고정 구간 하나 더 김 · r 안 곱함 · lr 0 으로만 고정 · W · r 기본값 · 만들 때 규칙 안 걺 | T9 |
| | p06 · p07 · p08 | critic 점검이 입력을 고쳐 씀 · 열 한 칸 어긋남 · value NaN 안 셈 | T10 |
| 관문 자체 | g01 | T7 sha256 기대값만 틀리게 (파일은 안 건드림) | T7 |

판 1 의 변이 m11 (「1 m 보다 깊은 곳도 mask 1」 을 잘못으로 잡던 것) 은 새 의미에서 정답이 되었으므로 뒤집어 「1 m 분류를 되살림」 으로 바꿨다. 17d 6.4 의 지적대로 변이가 다 잡혀도 그 정답이 과학적으로 옳다는 보증은 아니다. 정답은 설계 6 절의 정의를 따른 것이다.

## 6. 설계와 다르게 한 곳 · 해석한 곳

1. **actor 첫 층을 두 장으로** (판 1 과 같음). `Linear(77, 512)` 부모 값 + `Linear(64, 512, bias 없음, 0 시작)`. 17d 6.1 이 「타당」 으로 확인했다. GPU 동치는 미확인.
2. **A 상수 관문** (판 1 과 같음 · 설계에 없음). A 정책에 상수가 아닌 지도가 들어오면 ValueError.
3. **정상 miss 의 표현을 「xyz 모두 +inf」 로 좁혔다.** raycast_mesh 가 버퍼를 +inf 로 채우고 맞은 광선만 덮어쓰기 때문이다 (`ops.py` 71 · `kernels.py` 70 ~ 73 소스 확인). 그 밖의 비유한 꼴은 모두 고장이다.
4. **고장 칸 자리표시 (0, 0).** 설계는 「고장 횟수로 기록 · rollout 무효」 만 정했다. 정책에 NaN 이 들어가 시뮬로 퍼지지 않게 유한한 자리표시를 두고, 무효 판정은 `MapFaults` · `RunValidityGate` · `strict` 로 한다.
5. **encoder 고정은 requires_grad 를 끄는 방식.** lr 0 만 쓰면 고정 중에도 gradient 를 계산하고 Adam moment 가 쌓여 풀린 첫 걸음이 달라진다 (변이 p03 으로 구분됨). W 의 단위 (PPO iteration = `alg.update()` 한 번인지 optimizer step 한 번인지) 는 정하지 않았다. 넘겨받은 update 번호만 센다. **W · r 과 함께 단위도 등록해야 한다.**
6. **T5 · T7 은 시험 값 W 0 · r 1 을 쓴다** (gradient 경로 · 부모 보존을 보는 시험이라 고정 없이). 등록 값이 아니다.
7. **RunValidityGate 는 critic 입력 · value 외에 `add_nonfinite(name, t)` 로 return · advantage 등도 받는다.** 학습기와 아직 연결하지 않았다.

## 7. 미확인 · 하지 않은 것

- Isaac 접속 시험 (실제 collision mesh 의 평지 · 단차 · 빈 공간에서 `pos_w` · hit · 순서 · 갱신 시각 · 촘촘하지 않은 발판에 광선이 닿는 비율). T8 의 hit 은 IsaacLab 의 ray 시작 식을 쓰지만 교차는 높이장과 수직 광선이다.
- reset · 시점 (부분 reset 의 history · map · previous action · terminal · timeout bootstrap).
- 학습기 연결 (map 이 rollout 저장소 · 모든 minibatch 에 보존 · teacher 경로 제거 · 전체 update 뒤 저장 · 복원). `RunValidityGate` 를 rollout 에 거는 자리도 아직 없다.
- 0 초기화 동치의 GPU 확인.
- 실제 S2 지형에서 정상 miss · 고장이 얼마나 나오는지, 초기 gap value 편향.
- W · r · 단위 · 중단 기준 (A/B 결과 전 등록 대상) 과 smoke 지표 (부모 대비 action 차 · KL · latent cosine · expert 비율 · gradient norm · value 오차).
