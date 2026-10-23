> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (lead_tmp 기록) · 2026-10-23
> 근거: 팀장 이 창 직접 지시 · START v1 · PIE v3 · PLAN-B-START-TOPDOWN-1023
> 요지: 원문 주요 구성과 깊이·보행 동시 학습을 Go2에서 처음부터 구현한다.
> 상태: 준비안 · 구현·독립 검토 중 · 새 GPU 실행 없음

# EX-29 START-TD · 동시 학습 본류 준비안

## 가설

원문의TR-Net·I-E·PPO·AdaSmpl·발 가장자리 보상·지형 진행을 Go2에서 함께 학습하면 깊이 복원 지도만으로 보행하는 정책을 만들 수 있는가. EX-23 가중치에 계속 의존하지 않도록 scratch로 시작한다.

## 설정

[START v1](https://arxiv.org/html/2512.13153v1)+[PIE v3](https://arxiv.org/html/2408.13740v3) 기반 Go2 재구현. force_gt=False·learned·원문 sparse8×4m·START 명령·min 추종식·PIE 출처 DR·행동지연0~15ms. 종전53 혼합환경 DG3와 다른 실행 환경임을 기록한다. 논문 미기재값은 우리 선택으로 [실행안](../20261023-experiments/PLAN-B-START-TOPDOWN-1023.md) §3·4에 분리한다. 최대20,000update설정·Windows 약24h상한과 중간 검토, GPU1배정 제안.

## 결과

영상 없음 · 미확인. 구현·독립검토 중이며 아직 새학습이 없다. GT/pred 선택비율·복원오차·복원전용 보행을 각각 측정한다. p감소나GT조건 성공만으로 완성이라고 쓰지 않는다. checkpoint500/1000/1500와 이후1000회 또는3h에 영상·위상·관절·학습곡선과 지각 그림을 확인한다.

## 다음

깊이 기반 하위 보행 → 필요한 DR/지연·지형·열린 명령 검증 → HiPAN 연결이 본류다. 약24h에 완성하지 못하면 상태·optimizer·절대update·AdaSmpl·지형/RNG·실제DR를 보존하고 Linux에서 같은 실험의 새 구간으로 잇는다. 실패 시 GT warm-start나약한DR판으로 몰래 바꾸지 않는다. [실험 지도](EXP-MAP.md).
