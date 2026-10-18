# M1의 MARG 추정기 이식 계획

> 분류: 계획
> 작성: sol · 2026-10-18
> 근거: [MARG 원문 §II-B, §IV-A](https://arxiv.org/html/2509.20036) · Step1 b6 CPU 코드
> 요지: M1에 속도·접촉 7열 추정기를 붙일 때 필요한 경로와 정답 관측의 한계를 정리한다
> 상태: 계획 · 코드 미작성 · Kit 미확인

`확인됨`: 아래 정답 열 범위는 b6의 `CriticCfg` 항목 순서와 275열 폭을 대조한 값이다.

MARG 원문은 과거 몸 관측에서 선속도 3열과 발 접촉 4열을 예측하고, 정책 손실과 두 MSE를 동시에 학습한다. 논문에 적힌 추정기 폭은 `[258,128,7]`, elevation 폭은 `[128,64,16]`, 활성화는 ReLU다. 현재 M1은 10×45=450열 이력과 ELU 지도 MLP를 쓰므로, 단순히 첫 층 숫자만 258로 바꾸면 입력 계약이 깨진다. **258열을 만들 과거 관측 항목과 시간 배치를 먼저 확정해야 한다.** 논문 본문은 그 258열의 상세 packing을 명시하지 않는다. 이를 확정하기 전에는 완전한 MARG 재현이라고 부르지 않는다.

| 바꿀 곳 | 작업 |
|---|---|
| `actor_critic_moe_cts.py` | M1만 187→128 ReLU→64 ReLU→16 지도 갈래로 변경. 258→128 ReLU→7 추정기를 추가하고 추정 7열을 actor에 연결하여 입력 77+16+7=100열. E1 actor 첫 77열은 복사, 새 23열은 0. teacher, student, inference가 같은 M1 actor 경로를 사용한다. |
| `moe_cts.py`, `rollout_storage_cts.py` | 추정기의 현재 이력 입력과 동시점 정답 7열을 rollout에 보존하고, PPO 재계산에서 정책 gradient와 두 MSE를 함께 반영한다. 추정기 파라미터는 PPO optimizer에 등록한다. 지도·추정기 학습률과 MSE 계수는 설정값으로 고정한다. |
| `step1_resume.py`, 큐, 평가 loader | 새 구조·입력 packing·정답 threshold·MSE 계수를 metadata에 고정하고 옛 M1 checkpoint 재개를 거절한다. 평가에서 추정 정답은 정책 입력에 넣지 않는다. |
| CPU 시험 | 258열의 원본 항목 대조, 이력 reset, 정답 동시점성, 첫 E1 행동 일치, teacher/student/inference 및 PPO 재계산 일치, 추정기 gradient와 두 MSE, 재개 거절, 전체 회귀. |

정답 열은 b6의 **critic 275열 기준 0부터 세는 반열림 구간**으로 확인했다. `base_lin_vel`은 `critic[:,0:3]`이고 관측 scale 2.0이므로 물리 단위 선속도 정답은 `/2`다 (`env_cfg.py:168-172`). `contact_force`는 `critic[:,72:88]`의 16열이며 scale 0.001이다 (`env_cfg.py:218-223`, `observations.py:41-49`). 앞 네 열 `72:76`은 네 발의 **이력 최대 힘**이다. 이것을 임계값으로 이진화하면 현재 시점 접촉 정답이라고 보장할 수 없다. 접촉 정답은 같은 step의 `contact_forces.data.net_forces_w`에서 발 이름 순서와 힘 임계값을 고정해 새 특권 term 4열로 내거나, 기존 16열의 최신 시점 위치를 설치된 센서의 history 순서로 검증한 뒤 써야 한다. threshold와 발 순서는 CPU 알려진 입력으로 먼저 고정한다.

입력 packing과 접촉 정답을 정한 뒤 CPU 구현·회귀는 **약 6~9시간**, 실제 Kit에서 한 update와 평가 1건 대조는 **추가 1~2시간 추정**이다. GPU 실행 시간과 성능 변화는 미측정이다.
