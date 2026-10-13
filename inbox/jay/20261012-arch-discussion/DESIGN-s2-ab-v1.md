> 분류: A/정책학습 · S2 설계 초안 · 「이상적 지도 입력 비교」 A/B 의 정책 구조 · 입력 경로 · CPU 시험
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:14
> 근거: VERIFY-astra-11.md §2.1 · §2.2 · §2.4 · VERIFY-astra-17.md §1.2 · §3.1 · §3.2 · §3.3 · §4 · DESIGN-topdown-20261013.md §7 · s2-terrain-probe/PROBE-sparse-terrain.md · `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py` 86 ~ 247 행 · E1 `params/agent.yaml` · `params/env.yaml` (height_scanner · height_scan)
> 요지: A · B 는 같은 부모 (E1 20000) 의 student 경로에 작은 지도 encoder 를 0 으로 시작하는 열로 붙이고, PPO 만으로 학습한다 (모방 없음). A 는 높이와 유효성 mask 를 모두 상수로, B 는 시뮬의 이상적 높이와 mask 를 준다. 오늘 밤에는 학습하지 않고, 입력 의미 · 0 초기화 동치 · 첫 갱신 뒤 gradient 경로를 CPU 로 시험하는 코드까지만 만든다
> 상태: 초안 · ASTRA 17d 검증 전 · 학습 · Isaac 실행 없음

# S2 「이상적 지도 입력 비교」 A/B · 설계 초안 v1

표기: **확인됨** = 코드 · 설정을 열어 대조함 · **추정** = 설계 판단 · **미확인** = 재지 않음.

## 1. 답하는 물음 (ASTRA 17 §1.2 그대로)

「같은 희소 지형 연습에서 지도 정보가 통과 · 명령 준수를 얼마나 바꾸나」 하나. 연습 효과 자체 · 연습과 지도의 상호작용 · CTS 모방 유지 여부 · 센서 정책의 배포 가능성은 답하지 않는다. B 의 actor 는 시뮬 충돌 지형에서 얻은 완전한 높이를 보므로 이름은 「이상적 지도 입력 비교」 다.

## 2. 지금 부모의 구조 (확인됨)

| 부분 | 값 | 근거 |
|---|---|---|
| student encoder | `StudentMoEEncoder` · 입력 450 (45 × 이력 10) · 은닉 512 · 256 · 256 · expert 8 · 출력 latent 32 · L2Norm | agent.yaml 34 ~ 44 · `actor_critic_moe_cts.py` 103 |
| actor | MLP 입력 `latent 32 + single_obs 45 = 77` · 은닉 512 · 256 · 128 · 출력 12 · std 는 scalar 매개변수 | 같은 파일 91 · 116 · 155 |
| critic | MLP 입력 `latent 32 + critic obs` · 은닉 512 · 256 · 128 · critic obs 에 높이 187 (scale 2.5 · clip) 포함 | 92 · 131 · env.yaml 높이 항 |
| 학습 때 student 경로 | `act(is_teacher=False)` 는 encoder 를 `torch.no_grad()` 로 부름. encoder 는 따로 재구성 손실로 학습 | 210 ~ 224 |
| 정규화 | actor · critic 모두 끔 | agent.yaml 23 ~ 24 |
| 높이 스캔 | RayCaster · base 에 붙음 · 위로 20 m 에서 쏨 · yaw 정렬 · grid 1.6 × 1.0 m · 0.1 m · ordering xy → 187 | env.yaml 446 ~ 480 |

## 3. A/B 정책 구조 (추정 · 검증 요청)

```
지도 입력 m = [height 187, mask 187]          (A: 상수 · B: 시뮬 이상적 값)
z_map = MapEncoder(m)                          (작은 MLP 374 → 128 → 64 · ELU)
actor 입력 = [latent 32, single_obs 45, z_map 64]   (새 64 열의 actor 첫 층 가중치는 0 으로 시작)
```

- **부모 복사:** encoder · actor 의 기존 가중치 · std · critic 은 E1 20000 에서 그대로 읽는다. actor 첫 층만 입력 77 → 141 로 늘리고, 늘어난 64 열의 가중치를 0 으로 둔다. 그래서 초기 action 은 지도 입력과 상관없이 부모와 같아야 한다 (시험 S2-T3).
- **모방 제거:** A · B 모두 student 경로만으로 행동하고 PPO 손실만 쓴다. encoder 의 `no_grad` 를 풀어 PPO gradient 가 encoder 까지 간다. teacher encoder 와 재구성 손실은 쓰지 않는다. 모방이 나빠서가 아니라 경로를 단순하게 하려는 것이다 (ASTRA 11 §2.3).
- **critic:** 부모 critic 을 그대로 쓴다 (critic obs 에 높이 187 이 이미 있음). A · B 같은 critic.
- **A 의 상수:** height 와 mask 를 모두 상수로 (height 0 · mask 0). mask 만 실제 값을 주면 A 가 구멍을 본다 (ASTRA 11 §2.2).
- **B 의 의미:** height_b = (센서 높이 − 맞은 점 높이 − 0.5) 를 clip [−1, 1]. mask = 1 이면 그 광선이 지형에 맞았고 그 높이가 몸 아래 1 m 안. 안 맞은 광선 (inf · nan) · 너무 깊은 곳은 mask 0 · height 1 (「깊음」 쪽). 「시뮬 광선이 안 맞음」 · 「실제 낮은 땅」 을 mask 로 가른다. 센서 미관측 (실기) 은 이 단계에서 만들지 않는다 (S5).
- **명령 처리:** 부모와 같은 명령 처리 (CMD-R off). 팀장의 「규약 교정」 결정이 나면 A · B 를 같이 바꾼다 (ASTRA 17 §3.3 「등록한 명령 처리 조건 아래의 지도 효과」).
- **optimizer:** 새 Adam 으로 시작 (부모 Adam 상태는 차원이 달라 그대로 못 씀). 학습률은 부모 마지막 값. 두 군 같게.
- **지형:** S2 입문 분포는 실제 생성 지형부터 잰 뒤 정한다 (PROBE-sparse-terrain). 15 % 배정이 15 % 조우가 아니므로 접근 · 통과 · 회피 · 추락 · 정체 횟수를 기록한다.

## 4. 오늘 밤 만드는 것 (CPU · 학습 없음)

`_eval/s2/` 안:

| 파일 | 하는 일 |
|---|---|
| `s2_map_obs.py` | RayCaster 자료 (센서 위치 · 맞은 점) → height · mask (3 절 의미). A 상수 생성 |
| `s2_policy.py` | E1 20000 을 CPU 로 읽어 3 절 구조를 만드는 함수 · A/B 모드 · 부모 대비 열 확장 |
| `test_s2.py` | 아래 시험 |
| `mutate_s2.py` | 시험을 믿기 위한 돌연변이 |

| 시험 | 알려진 답 |
|---|---|
| T1 평지 | 센서 0.4 m · 맞은 점 0 → height −0.1 · mask 1 (187 칸 모두) |
| T2 단차 · 구멍 | 앞쪽 절반이 +0.1 m 단 → 그 칸만 height −0.2 · 구멍 (inf) → mask 0 · height 1 · 깊이 2 m → mask 0 |
| T3 광선 순서 | grid xy 순서에서 0 · 16 · 17 · 93 · 186 번 광선의 몸체 좌표가 Isaac Lab `grid_pattern` 과 같음 (그 함수를 CPU 로 불러 대조) |
| T4 0 초기화 동치 | 무작위 지도 · 무작위 이력에서 B · A 의 action 이 부모 `act_inference` 와 비트 동일 |
| T5 gradient 경로 | 첫 갱신 전: 새 열 가중치에는 gradient 가 있고 map encoder 에는 0 (자연스러움). 한 번 갱신한 뒤: B 의 map encoder gradient 가 0 이 아님. A 는 입력이 상수라 encoder 첫 층 가중치 gradient 가 0 (bias 는 아님) |
| T6 A 의 정보 차단 | A 에서 실제 지형을 바꿔도 policy 입력 · action 이 바뀌지 않음 |
| T7 부모 보존 | 부모 체크포인트 파일 해시가 시험 전후 같음 · 부모 state_dict 키 · 값이 복사본과 같음 |

## 5. ASTRA 17d 에 묻는 것

1. 3 절 구조 (0 초기화 열 · 모방 제거 · 부모 critic 유지 · 새 Adam) 가 「같은 출발점」 조건을 채우나. 부모 동작이 보존되지 않는 길이 있나.
2. B 의 height · mask 의미 (특히 「안 맞음」 과 「깊음」 을 같은 mask 0 으로 두는 것) 가 희소 지형 물음에 맞나.
3. encoder 의 `no_grad` 를 풀면 부모 latent 분포가 처음 몇 갱신에 무너질 위험이 있나. 막는다면 무엇으로 (encoder 학습률을 낮춤 · 몇 갱신 고정 등) 하고, 그것을 A · B 에 같게 두면 되나.
4. 4 절 시험이 입력 경로 검증으로 충분한가. 빠진 것.
