> 분류: A/정책학습 · 설계 초안 (ASTRA 검증 요청용)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-18 13:18
> 근거: 팀장 lead 창 직접 입력 (10/18 12:33 ~ 13:2x) · `RESEARCH-heightscan-architectures.md` · `REPORT-seokheon-ame2.md` · `inbox/jay/20261012-arch-discussion/PAPERS-architecture.md` · E1 코드 `C:/isaac/ext/go2_rl_robotlab` @28b4516 · S2 결과(`s2_lab/s2_step32_run/results_u2000/S2-AB-UPDATE2000.json`, `s2_lab/s2_step34_run/results_full/S2-AB-RESULT.json`)
> 요지: 출발선은 E1(MoE-CTS, 고유수용감각으로 teacher 의 지형 latent 를 짐작하는 보행 기본기). 여기에 MARG → AME-2 → START 를 쉬운 것부터 하나씩 붙인다. 오늘(00:00 까지) 은 1 단계: 구멍 표현을 바로잡고 MARG 식 지형 갈래를 붙여 gap 부터 푼다
> 상태: 초안 · 팀장 방향 확인됨 · ASTRA 검증 전 · GPU 실행 전

# 1 단계 설계: MoE-CTS 기본기 + MARG 식 지형 갈래

## 0. 팀장 방향 (lead 창 직접 입력 요지 · 원문은 lead 창 기록)

1. NVIDIA 이어 학습 계보(v2)는 더 잇지 않는다. 최종 발표에서 비교 기준으로만 쓴다.
2. 출발선은 MoE-CTS 구조다. E1 student 는 몸 상태 이력 0.2 초(45 × 10 step, 50 Hz)로 teacher 가 시뮬에서 높이 지도를 보고 만든 latent 를 짐작한다. 이것이 보행 기본기다.
3. 여기에 MARG · AME-2 · START 방식을 잘 붙이면 「우리만의 실험」 이 된다. 먼저 최종 목적(gap · 징검다리 등 험지 극복)에 도달하고, 차별점은 그다음.
4. 쉬운 것부터 차근차근. 석헌 님 지형 · 평가 세트는 지금 우리 기준으로 쓰지 않는다(성과가 나온 뒤에).
5. 오늘 00:00 까지 팀장이 비교해 볼 수 있는 결과를 낸다. 설계는 ASTRA 검증과 아이디어를 받는다.

## 1. 출발선 E1 의 사실 (코드 · 기록)

| 항목 | 값 | 근거 |
|---|---|---|
| 코드 | `go2_rl_robotlab` @28b4516, `ActorCriticMoECTS` · `moe_cts.py` · `on_policy_runner_cts.py` | `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py` |
| teacher encoder | privileged(critic obs 275 중 height scan 187 포함) → MLP [512, 256] → latent 32 | 같은 파일 96 ~ 100 행 · `PAPERS-architecture.md` 0 절 |
| student encoder | 몸 상태 이력 450 → MoE(expert 8) [512, 256, 128] → latent 32, L2 정규화 | 같은 파일 17 ~ 40 · 103 ~ 111 행 |
| actor | [latent 32, 현재 몸 상태 45] = 77 → 12 | 같은 파일 92 행 |
| 학습 | 8,192 env · 20,000 iteration · 약 23 시간 14 분 (초당 약 47,000 transition) | `logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192` · 조사 문서 7.7 |
| 학습 지형 | 8 종(flat · wave · slope up/down · rough_slope · stairs up/down · obstacles). gap · 징검다리 없음, 바닥 없는 칸 0 건 | `eval-g0/G0.md` |
| 구멍 표현 | teacher · critic 의 높이 지도는 Isaac Lab 기본 `height_scan`. 바닥 없는 칸 = -inf → clip -1 → × 2.5 = **-2.5 (벽)** | `G0.md` · S2 `result.json` critic `height_scan.func` |
| 약점 | gap 고리 생존 46/100 · 0.5 m/s 추종 0/100, 징검다리 · 저속 · 정지 명령 | `PAPERS-architecture.md` 0 절 |

## 2. 단계 지도 (쉬운 것부터)

| 단계 | 붙이는 것 | 푸는 지형 | 근거 논문 |
|---|---|---|---|
| **1 (오늘)** | 구멍 = +1 표현 · MARG 식 지형 갈래(높이 187 → MLP → 16) · 속도 · 접촉 추정 · 발 보상 | gap (바닥 없는 틈) | MARG · v2 의 구멍 표현 |
| 2 | 지형 수준 올리기 | 징검다리 · 평균대 | MARG 지형 6 종 |
| 3 | 지형 갈래를 attention 으로 교체 (몸 상태 latent 가 질문) | 같은 지형 + 일반화 | AME-2 (석헌 님 코드 참고) |
| 4 | D435i 깊이 → 지도 재구성 갈래 | 실기 센서 | START (코드 없음, DeepCode 를 우리 형태로 쓸지 super · pipeline 과 팀장이 논의) |

## 3. 1 단계 판 구성

| 판 | 무엇 | 왜 |
|---|---|---|
| E1 | 그대로 (학습 없음) | 바닥 기준 |
| **M0** | E1 에서 이어 학습. **구멍 = +1 을 teacher · critic 높이 지도에** 적용, 학습 지형에 바닥 없는 gap 추가, 발 보상 추가. actor 에는 지형을 주지 않음 (student 는 지금처럼 몸 상태만) | 「기본기(CTS)만으로」 gap 을 얼마나 배우나. teacher 가 구멍을 바르게 보게 된 효과 |
| **M1** | M0 + **MARG 식 지형 갈래**: 높이 187(구멍 +1) → MLP [128, 64, 16] → e^h 를 actor 입력에 더함 [latent 32, 몸 상태 45, e^h 16]. 추정 머리(속도 v̂ 3 · 발 접촉 ĉ 4)를 student latent 에서 회귀 | 「지형을 붙이면」 얼마나 더 되나 (M1 - M0) |

같게 둘 것: 출발 체크포인트 · 지형 · 보상 · 명령 범위 · 학습량(iteration 수) · PPO 설정 · 평가.

## 4. S2 에서 배운 것을 1 단계에 넣기

| S2 에서 본 문제 | 1 단계에서 |
|---|---|
| critic 은 구멍을 벽(-2.5), actor 지도는 +1 로 서로 달랐다 | teacher · critic · actor 지도 모두 같은 함수(`height_scan_with_gap`, offset 0.5 · miss +1 · clip [-1, 1]). 실행 전 세 곳 값이 같은지 시험 |
| 몸 상태 encoder 를 얼렸다 | 얼리지 않는다. 대신 E1 가중치 이탈을 막는 장치(아래)를 둔다 |
| 첫 갱신 KL 40 (lr 0.001, 설계는 0.00017) | 부모 마지막 lr 에서 시작, 첫 수십 iteration warm-up, 갱신 1 KL 상한을 관문으로 |
| 학습 명령 ±0.5, 평가 1.0 m/s | E1 끝의 명령 범위 · curriculum 상태를 이어받는다. 평가 명령은 학습 범위 안 |
| 1,024 env · 자체 학습기라 느림 | 표준 runner(`on_policy_runner_cts.py`) · 8,192 env |
| 지도 갈래를 0 에서 붙이고 짧게 | M1 의 e^h 투영은 0 으로 시작(E1 행동 보존), 학습량은 아래 7 절 |
| gap 학습 폭 0.10 ~ 0.25 m | MARG Single-Gap 수준 1 · 4 · 8 = 10 · 40 · 60 cm 로 curriculum |

## 5. 보상 · 지형 · 보행 감시

- 보상: E1 15 항 그대로 + MARG 발 3 항 (feet air time Σ(t_air - 0.5) 1.0 · feet stumble -1.0 · feet center -0.01 의 MARG 정의, 우리 구현 `feet_center_any9_v1` 은 CPU 시험만 있어 Kit 확인 필요). 가중치는 MARG Table I 출발.
- 지형: E1 8 종 + 바닥 없는 gap (Isaac Lab `mesh gap_terrain`, 폭 0.10 → 0.60 m). gap 비율 30 % 안팎(ASTRA 의견 요청). 징검다리는 2 단계.
- 보행 감시: 석헌 님 결과에서 「바운딩 계열이 gap 을 더 잘 건넜다」. 그래서 성공률과 함께 걸음 모양(두 발 지지 중 대각 비율 · 네 발 비행 비율)을 같은 평가에서 잰다. 바운딩 억제 보상은 1 단계에 넣지 않고 재기만 한다(ASTRA 의견 요청).

## 6. 평가 · 판정 (결과 전 등록)

- 평가: 등록 60 사례 중 gap 20 · 평지 10 (기존 S2 평가 도구, 명령은 학습 범위 안 값으로) + 걸음 모양. E1 · M0 · M1 같은 사례 · 같은 시드.
- 판정: gap 에서 (M1 - E1) · (M0 - E1) · (M1 - M0) 의 Tango 95 % 짝 구간. 하한 > 0 이고 평균 차 ≥ 10 %p 면 「나아짐」. 평지는 퇴행 감시.
- 덤: M1 에서 지형 갈래를 끈 평가(지도 0) 로 E1 수준 보행으로 물러나는지 (만들어 둔 지도 지우기 도구 재사용).

## 7. 시간 · GPU (추정)

| 시각 | 일 |
|---|---|
| ~14:30 | ASTRA 검증 · 아이디어 |
| ~16:30 | 코드(작업자 sol): 구멍 +1 세 곳, M1 지형 갈래 · 추정 머리, 발 보상, gap 지형 · curriculum, 이어 학습 상태 이어받기, 걸음 모양 측정 |
| 16:30 ~ 16:45 | 짧은 실제 확인 (10 iteration) |
| 16:45 ~ 22:15 | 학습: M1 GPU 0, M0 GPU 1 동시 (각 약 5 시간 · 같은 iteration 수로 끊음. GPU 1 은 화면용이라 느릴 수 있음) |
| 22:15 ~ 23:40 | 평가 · 영상 |
| ~24:00 | 페이지 · 보고 |

5 시간 · 8,192 env 면 E1 처리량 기준 약 4,000 iteration (E1 의 약 1/5, 추정). 결과는 「같은 예산에서의 추세」 다.

## 8. ASTRA 에게 묻는 것

1. 지형 갈래를 어디에 붙일까: (가) actor 입력에 e^h 를 더하기 (MARG 식, 이 안) (나) student encoder 입력에 높이를 넣어 latent 자체가 지형을 담게 하기 (다) 둘 다. CTS 의 「student latent ≈ teacher latent」 구조를 해치지 않는 쪽은?
2. teacher 높이 지도를 +1 표현으로 바꾸면 E1 teacher latent 의 뜻이 바뀐다. E1 학습 지형에는 바닥 없는 칸이 0 건이라 기존 지형에서는 같은 값이지만, 이어 학습 첫 구간의 위험과 대책은?
3. 얼리지 않고 이어 학습할 때 E1 기본기를 지키는 장치: lr · warm-up · KL 상한 · 행동 분포 정규화(E1 대비 KL) 중 무엇을 어떤 값으로?
4. M0 · M1 두 판을 GPU 0 · 1 에 나눠 동시에 돌려도 되나(같은 RTX 5080, GPU 1 은 화면용). 같은 iteration 에서 끊는 것으로 충분한가?
5. gap 비율 · 폭 curriculum · 발 보상 가중치 출발값.
6. 걸음 모양: 1 단계에서 재기만 할지, 바운딩 억제 항을 처음부터 넣을지.
7. 이 설계에서 빠진 위험 · 더 나은 아이디어 (비판적으로).

## 9. 미확인

- E1 끝의 명령 범위 · curriculum 실제 값 (코드 · 기록에서 다시 잴 것)
- `feet_center_any9_v1` 의 Kit 안 동작
- GPU 1 동시 학습 처리량
- 바닥 없는 gap 에서 E1 critic 의 value (지금은 벽으로 읽음)
