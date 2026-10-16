# S2 고정 체크포인트 평가 설계
> 분류: A/평가
> 작성: Codex · 2026-10-16
> 근거: ASTRA 17af 4절 · S2Runner.save · S2 정책과 지도 어댑터 · q_eval_cmdr.py · cmdr_eval_driver_s1043.py 정적 대조
> 요지: S2 A/B의 같은 평가 case를 사전에 봉인하고, 체크포인트 적재와 지도 입력 및 짝 결과의 경계를 정의한다.
> 상태: CPU 설계와 정책 forward만 검증 · Kit case 실행 미구현

## 체크포인트와 정책 접점

`S2Runner.save`의 형식은 `s2-17v-checkpoint-only`이다. 최상위 키는 `format`, `mode`, `plan`, `plan_sha256`, `env_config_sha256`, `policy`, `s2_control`, `optimizer`, `rng`, `resume_supported`, `discarded_transitions`, `encounter_states`이고 배관 저장본에만 `plumbing_meta`가 추가된다. `resume_supported=false`이므로 평가기는 환경 재개나 optimizer 복원을 시도하지 않는다. `policy`는 S2의 `state_dict`이고 각 텐서의 키, shape, dtype을 새 S2 정책과 일대일로 확인한 뒤 `strict=True`로 읽는다. 부모 E1은 정책 구조를 짓기 위한 읽기 전용 입력이다. 현재 CPU 로더는 S2 체크포인트 기대 SHA를 역직렬화 전에 검사한다. Kit 평가기는 부모와 agent.yaml의 기대 SHA도 적재 전에 확인하도록 별도 구현해야 한다. 전체 텐서 목록은 CPU 시험 산출물 `s2_eval_ckpt_schema.json`에 둔다.

기존 `q_eval_cmdr.py:308~325`는 `OnPolicyRunnerCTS`를 만들고 부모 형식 `model_N.pt`를 `runner.load()`로 읽은 뒤 `get_inference_policy`를 호출한다. `:393~394`의 관측은 `policy`, `single_obs`, `critic`이며 `:602~608`은 이 관측으로 student 함수를 호출한다. S2는 여기에 `map [N,374]`를 추가하고 `act_inference(obs)`가 결정적 평균 행동, `evaluate(obs)`가 value를 낸다. A도 actor map은 0 상수지만 critic의 기존 height_scan은 받는다. B의 actor map은 현재 step의 RayCaster 위치와 187 hit으로 `training_map`을 실행해 만든다. 정상 miss, 손상 ray, 센서 갱신 및 reset packet 계약을 훈련과 동일하게 적용해야 한다. 학습 checkpoint를 기존 `runner.load`에 이름만 바꿔 넣는 경로는 호환되지 않는다.

| 기존 접점 | S2에 필요한 변경 | 예상 범위 |
|---|---|---|
| 드라이버 `q():1044~1062` | S2 전용 평가기 경로, 두 checkpoint SHA, 부모 SHA, case 목록 SHA, arm과 지도 입력 계약을 명시적으로 전달 | 새 평가 job 구성과 인자 검증, 약 40~80줄 제안 |
| 평가기 `:308~325` | `s2_eval_cpu.strict_load`와 같은 정책 state 검증을 Kit의 명시 장치에서 수행. `model_N.pt` 숫자 및 E1 runner 가정 제거 | S2 전용 로더 약 60~100줄 제안 |
| 평가기 `:393~394`, `:602~621` | A/B 모두 동일 observation packet을 검증. A 상수 map, B RayCaster map을 action 직전에 주입. `act_inference`만 호출 | map bridge, freshness 및 reset 검사 약 100~180줄 제안 |
| 평가기 `:333~386`, `:560~650` | 봉인된 case의 지형, reset, 명령, 마찰, 종료 전 상태를 기록하고 동일 case를 두 팔에 적용 | case 실행과 episode 기록 약 150~250줄 제안 |
| 드라이버 `validate():1067~1175`, 기존 post | S2 형식과 짝 case, 누락, 비교 분모, 해시 및 종료 경계 검증. CMD-R의 1043 체크포인트 판정은 재사용하지 않음 | S2 전용 검증 및 집계 약 120~200줄 제안 |

줄 수는 구현 전 추정이다. 이 판에는 Kit case 실행 코드를 만들지 않았다. 특히 기존 q 평가기의 `loaded_iter`와 `model_N.pt` 일치, teacher 경로 및 사전 `checks_pre` 항목은 S2에 그대로 적용할 수 없다.

## case 목록 계약

한 case의 ID와 해시는 실행 전에 고정한다. 필수 필드는 다음과 같다.

| 묶음 | case에 봉인할 필드 |
|---|---|
| 지형 | `terrain_family`, generator 또는 USD 소스 SHA, 실제 mesh 지문, 지형 seed, 난이도와 tile 좌표, gap 또는 stone 기하, 마찰 및 물리 설정 |
| 시작 | 평가 seed, 원점과 초기 root pose 및 yaw, 관절 기본 pose, 초기 속도, reset 무작위화 범위와 실제 표본 |
| 임무 | 명령 시간열, 명령 좌표계, 시작선, 접근선, 종료선, 장애물 ID, episode ID, 제어 dt, 시간 상한 |
| 사건 | 성공, 추락, 정체, 회피, 시간 초과, 진행 중, 미상의 상호 배타 규칙, reset 전 마지막 물리 상태를 읽는 시점 |
| 정책 | arm, checkpoint와 E1 부모 SHA, encoder 및 map 계약, observation 순서, deterministic 추론, dtype과 장치 |
| 실행 | case 목록 SHA, 평가기 코드 SHA, 환경 cfg SHA, GPU 및 Kit/Isaac 버전, 실행 시작 및 종료 영수증 |

평가 seed 목록은 학습 seed 목록과 서로소로 두고 봉인 전 확인한다. 같은 seed만으로 같은 초기 상태라고 주장하지 않는다. A/B 각각의 실제 mesh 지문과 초기 pose, 명령 및 마찰을 case별로 대조한다. 한쪽에서 생성된 case가 누락되거나 다른 mesh라면 해당 짝은 비교 분모에 넣지 않고 누락 이유를 공개한다. 단순 성공률 외에 짝별 A/B 성공 여부와 성공 차이, 추락 및 정체 결과를 남긴다. A/B의 추론은 첫 판에 `act_inference`의 deterministic 평균으로 고정 제안한다. 확률 추론을 택한다면 행동 RNG와 반복 횟수를 별도로 봉인해야 하며 이번 CPU 시험의 결론을 이월하지 않는다.

평가 지형은 목표인 gap과 stepping stones를 각각 별도 층으로 두고 flat 및 기존 능력 퇴행을 볼 장애물/경사/계단 중 사전 지정 대조층을 둔다. 학습 중 case의 지형 seed와 겹치지 않는지 확인한다. 목표 두 층의 B−A 차이와 가중 평균을 보고할 수 있지만, 가중치, 분모, 짝 차이의 구간 추정법을 결과 전 봉인해야 한다. 두 독립 Wilson 구간을 빼서 짝 차이 구간으로 쓰지 않는다. 한 학습 seed의 여러 episode는 학습 seed 변동을 나타내지 않는다.

case 수는 이 문서에서 정하지 않는다. 선택지는 목표 지형별 10, 20, 30개 이상의 짝 case이며, 10개는 탐색용으로 불확실성이 크고 20개 이상은 시간 및 독립 seed 비용이 커진다. lead가 GPU 시간, checkpoint 수, 목표 차이와 허용 구간 폭을 보고 결과를 보기 전에 층별 수와 총량을 봉인해야 한다. case 실행 전에는 `comparison_ready=false`, `performance_verified=false`다.

## CPU에 닫힌 부분과 남은 일

`s2_eval_cpu.py`는 SHA 확인, 정책 텐서 키와 shape/dtype 대조, strict load, 알려진 A/B 지도 입력, 훈련 정책과 적재 정책의 action/value 1회 forward 동치를 제공한다. 이는 Kit 평가의 입력 계약 일부만 확인한다. 아직 실제 case 목록, 센서 packet, mesh 동등성, reset 직전 종결 상태, 사건 집계, 짝 결과와 결측 분모는 측정하지 않았다. 별도 승인된 감독 경로와 S2 전용 Kit 평가기가 필요하다.
