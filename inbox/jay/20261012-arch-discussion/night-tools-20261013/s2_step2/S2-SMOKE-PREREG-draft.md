> 분류: A/정책학습 · S2 smoke 사전 등록 초안
> 작성: Codex Worker · 2026-10-15
> 근거: README-s2-step1.md 8.2 · VERIFY-astra-17f2.md 5.1~5.3 · DESIGN-s2-ab-v1.md 6
> 요지: A/B 결과를 보기 전에 결정할 측정과 중단 규칙을 항목별 책임자와 함께 드러낸다
> 상태: 초안 · 팀장 결정과 ASTRA 검토 전 · 학습 승인 아님

# S2 smoke 사전 등록 초안

별표(*)는 결과를 보기 전에 정해야 하는 값이다. 아래 숫자는 운영 승인값이 아니다.

| 항목 | 필요한 값 | 제안 | 결정·확인 |
|---|---|---|---|
| 1 실행 무결성 | *지도 시점·reset·187 height와 187 mask·부모 초기 동치·고정 encoder 가중치/latent/grad/Adam 상태·실제 group LR·NaN/Inf 중단·RayCaster packet | CPU의 `RunValidityGate`와 S2 control 기록을 매 rollout 확인. 실제 collision mesh의 평지·단차·빈 공간을 Isaac 접속 시험에서 별도 확인 | lead 측정, ASTRA 관문 검토, 팀장 기동 결정 |
| 2 측정 일정 | *초기·중간·마지막 checkpoint 시각 또는 update 번호, 검사 빈도, 표본 수 | 고정된 일정표를 A/B에 동일 적용. 별도 schedule pilot이면 W 전후 49/50을 포함하는 안을 검토 | lead 시간당 iteration 실측, 팀장 확정, ASTRA 표본 검토 |
| 3 표현 진단 | *고정 관측 corpus와 같은 명령, latent cosine 하위 분위수·상황별 분포, expert weight의 sample entropy·평균 사용 entropy·8 weight 분포 | 평지·틈 접근·접촉·경계·다양한 명령을 나눈다. 단일 cosine 경계로 전환하지 않는다 | lead corpus와 지표 측정, ASTRA 해석 검토, 팀장 기준 확정 |
| 3 행동 진단 | *부모 대비 action KL 방향·12 관절 합/평균·std·corpus, 명령별 성공 정의와 표본·신뢰구간, clipping 전후 묶음별 gradient norm·group LR, gap value와 return 차이 | PPO old/current KL과 부모/current KL을 별도 기록. 평지 전진·횡이동·후진·회전·정지를 분리한다 | lead 측정 설계, 팀장 허용 퇴행 결정, ASTRA 판정 검토 |
| 4 두 군 공동 규칙 | *같은 부모·초기 공유 가중치·지도 encoder 시드·optimizer 선택·encoder_mode·W/r 해당 시·rollout/epoch/minibatch·학습 예산·지형/명령/보상/잡음·privileged critic | A/B는 같은 코드 경로로 실행하며 지도 값만 바꾼다. 어느 한 군이 실패 기준에 걸리면 같은 후보의 A/B를 함께 재검토한다 | 팀장 규칙 확정, lead 동일성 대조, ASTRA 독립 확인 |
| 5 전환과 재시작 | *pilot 시도 수, 실패 정의, 선택 이유, 새로운 규칙으로 재시작할 때 부모 checkpoint·optimizer·난수 초기화 규약 | 첫 지도 비교의 encoder_mode는 전 구간 고정을 검토하되 확정 전이다. W/r pilot은 별도 질문으로 분리한다. 실패한 pilot 가중치에서 한 군만 이어가지 않는다 | 팀장 결정, lead 이력 보존, ASTRA 비교 적합성 검토 |
| 6 평가 분리 | *pilot 학습/eval seed와 최종 평가 seed·칸·명령·checkpoint 선택 절차 | 최종 B−A를 보고 W/r이나 checkpoint를 다시 고르지 않는다. pilot 결과는 최종 독립 검증으로 재사용하지 않는다 | 팀장 묶음 동결, lead 실행, ASTRA 사전 검토 |

기능 smoke 통과는 장기 성능 승인과 다르다. `cosine=0.9` 또는 평지 `−10%p`를 자동 전환값으로 두지 않는다. 15% 지형 배정은 15% 실제 조우가 아니므로 gap·징검다리의 접근·통과·회피·추락·정체를 각각 기록한다. 실제 기준·비율·환경 수·iteration 수는 미결정이다.
