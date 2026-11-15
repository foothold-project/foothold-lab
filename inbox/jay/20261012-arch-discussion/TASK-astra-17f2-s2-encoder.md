> 분류: A/정책학습 · ASTRA 의뢰 17f-2 · S2 encoder 고정 구간 W · 학습률 비 r 제안 검토
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 00:08
> 근거: VERIFY-astra-17d.md §6.3 · DESIGN-s2-ab-v1.md 6 절 · E1 `params/agent.yaml` (num_steps_per_env 24 · num_learning_epochs 5 · num_mini_batches 4 · learning_rate 0.001 · student_encoder_learning_rate 0.001) · `_eval/s2/s2_policy.py` (EncoderSchedule · make_optimizer) · 팀장 10/14 00:07 「제안사항도 같이 답변하고 ASTRA 에게 해당 제안이 맞는지 검토」
> 요지: W 의 단위는 PPO iteration, 값은 W 50 · r 0.1 을 제안한다. 단 이 값은 근거가 약하므로 A/B 전에 짧은 smoke 로 latent 변화를 재고, 미리 정한 기준을 넘으면 encoder 를 끝까지 고정 (r 0) 하는 대안으로 간다. 이 제안이 맞는지 판정해 달라
> 상태: 의뢰 (17f 다음 차례)

# ASTRA 17f-2 · S2 encoder 고정 구간과 학습률 비

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. lead 의 제안을 맞다고 가정하지 마십시오.

## 1. 정할 것

17d §6.3 이 「A/B 모두 처음 W 동안 student encoder 를 고정하고, 그 뒤 encoder 학습률을 actor 의 r 배로」 를 제안했고, 「정확한 고정 길이와 lr 비율은 근거가 없으니 확정 수치처럼 쓰지 말라」 고 했습니다. S2 코드 판 2 는 W · r 을 기본값 없는 필수 인자로 두었습니다. 단위도 정하지 않았습니다.

## 2. lead 제안 (모두 추정)

| 항목 | 제안 | 까닭 |
|---|---|---|
| W 의 단위 | **PPO iteration** (한 iteration = rollout 24 step × env 수 → 5 epoch × 4 minibatch = optimizer step 20 번) | 학습 예산 · 로그 · 부모 일정이 모두 iteration 단위. iteration 안의 optimizer step 수가 설정으로 고정이라 환산이 한 가지 |
| W | **50 iteration** (예산 2,000 의 2.5 % · optimizer step 1,000 번 · 약 5 초/iteration 이면 4 분 남짓) | 목적은 0 으로 시작한 지도 열 · actor 첫 층 · critic 이 「모방 없는 PPO」 와 새 희소 지형 분포에 먼저 맞추는 것. 너무 길면 A 와 B 의 차이가 encoder 를 못 쓰는 조건에서만 생김 |
| r | **0.1** (actor lr 약 1.7e-4 → encoder 약 1.7e-5) | 부모 encoder 는 재구성 · load balance 손실과 따로 학습률 1e-3 로 학습됐다. 이제 PPO gradient 만 받으므로, 사전학습된 부분을 머리보다 작은 학습률로 미세조정하는 관행에 맞춰 크게 줄인다 |
| 확인 (A/B 전) | A · B 각각 짧은 smoke (100 iteration) 에서 고정 관측 묶음의 부모 대비 latent cosine · action KL · expert 선택 entropy · encoder gradient norm · 평지 명령 통과를 잰다 | 17d §6.3 의 기록 항목 |
| 대안 (기준을 넘으면) | encoder 를 끝까지 고정 (r = 0). 지도 효과는 새 지도 열과 actor 만으로 본다 | 비교는 더 깨끗하지만, 희소 지형에서 몸 감각 표현까지 바꿀 여지를 두 군 모두에서 막는다 |
| 기준 (결과를 보기 전에 등록) | smoke 100 iteration 안에 고정 관측 묶음의 latent cosine 평균이 0.9 아래로 내려가거나, 평지 명령 통과가 부모보다 10 %p 넘게 떨어지면 대안으로 | 숫자 자체는 근거가 약함 (추정) |

## 3. 물음

1. W 의 단위를 PPO iteration 으로 하는 것이 맞나. optimizer step 이 나은 경우가 있나.
2. W 50 · r 0.1 이 이 물음 (같은 희소 지형 연습에서 지도 정보의 효과) 에 맞는 출발값인가. 더 나은 값이나 다른 방식 (예: 처음부터 끝까지 고정 · 단계적 해제 · anchor 손실) 이 있으면 근거와 함께.
3. 2 절의 확인 항목 · 기준 · 대안이 「결과를 보고 나서 고르는」 꼴이 되지 않게 충분히 미리 고정됐나.
4. 이 결정이 A/B 비교의 공정성 (두 군에 같은 규칙) 이나 「v2 대비 무엇을 얻었나」 설명에 미치는 영향.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17f2.md` 한 파일. 첫 줄은 한 문장 판정 (제안대로 · 고쳐서 · 다른 안).
- 표기: 확인됨 · 추정 · 미확인. 코드 · 파일 수정 · GPU · 학습 · 커밋은 하지 마십시오. em dash 를 쓰지 마십시오.
