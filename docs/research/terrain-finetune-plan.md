# 실패 지형 파인튜닝 실행 계획: 레시피 병렬, 혼합 단일 런

> 분류: 계획
> 작성: 오흥재 · 2026-08-22
> 근거: 실측
> 요지: 일반화 벤치마크 실패 5종을 이어 학습으로 메우는 계획.
> 상태: 확정

> 작성 2026-08-22 (WS) · 입력: 일반화 벤치마크 v2 (실패 5종·모드 지도) + 문헌 조사 (하단 출처)
> 답하는 질문 (팀장 8/22): "팀원별로 지형을 나눠 병렬 강화학습하는 게 의미가 있는가? RL은 순차로 쌓아야 하지 않나?"
> 공식 Go2 rough cfg를 먼저 읽는 장은 [험지 학습 커리큘럼](go2-rough-training.md).

![레시피 병렬 계획 흐름도](../assets/visual/finetune-plan-flow.svg)

## 0. 원리 두 줄

1. **체크포인트를 나눠 만들면 합칠 방법이 없다.** 각자 파인튜닝한 정책 2개의 가중치 병합은 RL에서 성립하지 않는다. 그리고 단일 지형만으로 파인튜닝하면 기존 rough 성능이 무너진다 (catastrophic forgetting, ICML 2024에서 메커니즘 규명).
2. **그렇다고 순차도 아니다.** RL의 표준은 "A 끝내고 B"가 아니라 **혼합 동시 학습**: 한 런의 수천 개 병렬 환경이 서로 다른 지형 위에서 동시에 하나의 정책을 업데이트한다. Isaac Lab terrain generator가 바로 그 장치이고, **실패 4종(gap·rails·stepping_stones·pit)의 지형 cfg는 전부 Isaac Lab에 내장**되어 있다 (`MeshGapTerrainCfg`·`MeshRailsTerrainCfg`·`MeshPitTerrainCfg`·`HfSteppingStonesTerrainCfg`).

따라서 병렬로 나누는 것은 **학습이 아니라 연구(레시피 찾기)**이고, 최종 학습은 언제나 **혼합 단일 런 1개**다.

## 1주차: 진단 (5인 병렬)

각자 자기 지형 하나를 소유한다. 작업 단위:

**지형 배정 (2026-08-27)**. 실패는 5종이고 팀은 5인이라 한 사람이 한 지형을 맡는다.

| 지형 | 실패 모드 | 담당 |
|---|---|---|
| `gap` | 낙상 (평균 3.2초에 몸통 접촉) | (미정) |
| `rails` | 낙상 우세 | (미정) |
| `stepping_stones` | 전진 불능 | (미정) |
| `pit` | 전진 불능 | (미정) |
| `floating_ring` | 전진 불능 | (미정) |

담당은 팀에서 정한다. 정해지면 각자 이슈를 만들고 `A/정책학습` 을 고른다.


1. 자기 지형 **단독** sub-terrain cfg로 기준선 정책을 50에피소드 평가 (v2 하네스 그대로)
2. 실패 영상을 보고 분류: 어디서 넘어지나 / 왜 멈추나 (v2 실측 출발점: gap·rails·stones = 낙상 우세, pit = 순수 전진불능)
3. 관측 점검: height scan이 그 지형의 위험(구멍·레일)을 실제로 보는가 (스캔 격자 0.1m 간격 vs 지형 특징 크기 대조)
4. 자기 지형의 **난이도 파라미터 지도** 작성: gap 폭, 레일 높이, 디딤돌 간격을 3~4단계로 나눠 각 단계 성공률 측정 → "어디까지는 되고 어디부터 안 되나"

산출물: 지형 진단 1장 (실패 모드 + 난이도 경계 + 관측 판정)

## 2주차: 레시피 탐색 (5인 병렬)

1. 학습 cfg: **기존 rough 혼합 0.6 + 자기 지형 0.4** (신규 지형 단독 금지: 혼합이 곧 망각 방지 rehearsal)
2. 기준선 체크포인트에서 **resume** 파인튜닝, 학습률 하향 (1e-3 → 1e-4 급), 커리큘럼은 낮은 난이도부터
3. 바꿔볼 것 (한 번에 하나): 지형 비율 / 난이도 범위 / 보상 가중치 (pit는 전진 보상 쪽, 낙상형은 발 배치·접촉 페널티 쪽) / 에피소드 길이
4. **모든 런에서 rough 회귀 지표 필수 계측** (기존 지형 성공률이 떨어지면 즉시 표시: forgetting 감시)
5. 실험 대장에 기록: cfg·커밋·결과 CSV·텐서보드 링크

산출물: 지형별 **레시피 1장** (작동한 비율·난이도 시작점·보상 변경·하이퍼파라미터)

## 3주차: 통합 (단일 런)

1. 레시피 5장을 합쳐 전체 혼합 cfg 구성: 예) rough 계열 합계 0.5 + 신규 5종 각 0.1
2. resume 런과 scratch 런을 1개씩 병행해 비교
3. 특정 지형이 뒤처지면 그 지형의 proportion 상향 (비율이 곧 커리큘럼 압력)

## 4주차: 마감

전 지형(기존 rough + 신규 10종) 재벤치마크 → 최종 성능표. **ablation 표** (단독 파인튜닝 vs 혼합의 rough 붕괴 비교)는 forgetting을 눈으로 보여주는 발표 소재가 된다.

## 특권 관측(teacher-student)은 필요 없다

그 기법은 "시뮬에선 보이지만 실기 센서로는 안 보이는" 관측 격차 때문에만 존재한다 (Lee et al. 2020, RMA). 우리 정책은 실기에 배포하지 않고, height scan은 이미 관측에 들어 있으므로 불필요한 복잡도다.

## 출처

[Rudin et al., Learning to Walk in Minutes](https://arxiv.org/abs/2109.11978) (혼합 지형 커리큘럼 원조) · [legged_gym terrain_proportions](https://github.com/leggedrobotics/legged_gym) · [Isaac Lab terrains API](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.terrains.html) (4종 cfg 내장) · [Wołczyk et al., ICML 2024](https://arxiv.org/abs/2402.02868) (RL 파인튜닝 망각) · [Robot Parkour Learning](https://arxiv.org/abs/2309.05665) (specialist 병렬→증류, 스트레치 옵션) · [Lee et al., Science Robotics 2020](https://www.science.org/doi/10.1126/scirobotics.abc5986) (특권 관측)
