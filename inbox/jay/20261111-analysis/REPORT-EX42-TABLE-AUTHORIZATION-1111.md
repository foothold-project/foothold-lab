> 분류: 구현 · 승인 검사 CPU 검증
> 작성: verifier-lx · 2026-11-11
> 근거: lead 12:08 · 12:25 의뢰 · planner DRAFT-EX42-APPROVAL-CELLS-E2-E6B-1111 §2~10 및 §6b · CG 69e5ac6b E.1/E.2
> 요지: 단계 표 기반 승인 검사와 미승인 초안 생성, E2 초안 여섯 항목 추가
> 상태: 승인 파서 범위 막음 0 · CPU 134 통과 · 팀장 승인 전 병합 금지 · 뒤 단계 기동 가능 판정 아님

# 단계 표 기반 승인 검사

`ex42_prep.py:247`의 `authorization_validators(plan)`은 계획의 stages 행에서 callable을 만든다. 호출은 `validators[stage_id](approval_path, parent_sha256)`다. E0/E1은 과거 특수 증거 검사를 내부에서 보존한다. E1F 이후는 `validate_stage_authorization` 하나가 표의 기본 회차(`minimum_updates`), 선행 단계, 필수 SHA/문자열/bool, 허용 축과 고정값을 읽는다. `ex42_auto_authorization.py`의 단계 ID별 등록과 선행 단계 상수를 없앴다. 정본 단계 목록을 검사하는 `EX42Plan.load` 자체는 그대로다.

승인 파일의 범위가 선택 행과 다르거나, 빈 증거, 미승인, 비활성 단계, 재고정되지 않은 파일이면 거절한다. 기본 회차만 허용하며 연장과 뒤 단계 허가는 false다. `draft_stage_authorization`은 같은 표에서 승인 false, 결정·부모·필수 증거 null인 칸을 생성한다. 초안 계약으로 승인자·approved·scope를 덮어쓸 수 없다.

| 단계 | 기본 회차 | 선행 관문 | 현재 상태 |
|---|---:|---|---|
| E2 | 1500 | E1F | 승인 false · 필수 증거 빈 칸 |
| E3 | 3000 | E2 | 승인 false · 초안 |
| E4 | 2000 | E3 | 승인 false · 초안 |
| E5 | 1500 | E4 | 승인 false · 초안 |
| M | 500 | 미정 | 승인 false · enabled false · source_stage_ids 비움 |
| E6a | 1000 | E5 | 승인 false · M 통과로 E5 졸업 대체 불가 |
| E6b | 2000 | E6a | 승인 false · Q12 결정 등 빈 칸 |

숫자는 CG의 기본 회차와 기존 prep 행에서 왔다. 연장 포함 maximum_updates를 기동 허가에 복사하지 않는다. planner §6b 대조로 M을 E5 다음 선형 단계로 만들지 않았다. M의 출발·복귀 단계, 예산 포함 여부, 복귀 창 계수, 소진 뒤 처리와 복귀 영수증은 미정으로 보존했다. E6a에는 E5 PASS가 필수이고 M 경유는 추가 계보 증거가 필요하다. 이 계보 소비는 아직 pending이다.

## E2 초안 여섯 항목

`ex42-approvals.yaml:158`에 다음을 추가했다. 전부 미승인 초안이며 운영 소비 완료 주장이 아니다.

| 항목 | 기록 |
|---|---|
| kind_cell_evaluator | pending |
| stage_judgment_policy | pending |
| exposure_delta | A stepping_stones_low, 0→0.05, L0, 연속 몫에서 공여 |
| 이름 대응 | prep start_stones_l0 ↔ mesh stepping_stones_low |
| exit_gate | last_support_0.5s · forward+flag_all · 성공52/64 · 생존60/64 · 두 창 · learned_cells32(가정) · 교환 학습/유지표 |
| 평가 칸 | L0 전진1.0 gt/pred 판정, off 기록 · 깃발 L0 한 개 기록 |

`terrain_change: none`은 planner 12:28 답에 따라 메시 치수 변경 없음이며, 노출 변화는 별도 exposure_delta다. 5%를 정수 env 수로 고정하지 않았다. 실제 env 배분은 노출 소비자가 한다. `critic_mirror`는 E2 이후 null이며 승인 시 bool로 채워야 통과한다. E1의 D174를 모든 뒤 단계 true 승인으로 확대하지 않는다.

## 검증

- CUDA 숨김, isaac311, 지정 CPU 9개 파일: **134 passed in 15.59s**.
- 기본 회차를 시험 사본에서 3000→3250으로 바꾸면 옛 3000 승인은 거절하고 일치하는 범위만 통과한다. 3250은 250 간격에 맞춘 시험 전용 값이다.
- 등록표가 실제 단계 목록에서 생성됨, 미승인 단계가 E1F 승인을 상속하지 않음, disabled M 거절, 초안에 승인 주입 거절, 누락 SHA/축/부모 거절을 확인했다.
- 제거본 6종: 실제 E1F 몫 대조 1 FAIL, 승인자 2 FAIL, M0~M3 2 FAIL, DR 2 FAIL, E0/E1만 남긴 등록표 15 FAIL, scope 대조 2 FAIL. 원본 소스는 바꾸지 않고 별도 프로세스 메모리에서만 제거했다.
- 원출력: `/home/jay/mai/tmp/verifier-lx/table-authorization-1111/cpu-final.log`, `mutations.py`, `mutations.json`, `mut-*.log`.
- 초기 시험 입력 3100이 250으로 나누어지지 않아 실패하여 3250으로 고쳤다. 최종 명령의 존재하지 않는 시험 파일명도 정정한 뒤 위 9파일 결과를 얻었다.

## 승인 재고정과 범위

기존 stage0/E0/E1/E1F 승인 객체, automatic 정책, DR 객체는 PR644와 값 대조 일치. 추가한 미승인 초안을 포함한 승인 SHA는 `6f2c7fc3cd92fe51531e6602d41c93904ab57e2b4c43720a09bd8355d1ff6a84`, 계획 SHA는 `b088cf6496b49b2e49de71c6c8f3643dcc22d9c8c7f9a1df4106a9754fb77b42`다.

돌고 있는 E1 고정 사본 `/home/jay/mai/wt/foothold-lab/ex42-launch-b379eb98`은 쓰지 않았다. 12:30 되읽기 plan SHA는 이전과 같은 `e542961d9c65a588ae893b81a8d07d39cd66ca068f2f118410c3e2d1d7a2d982`다.

E1F 이후 `entry_gate_adapter: pending`은 그대로다. 채운 승인만으로 공통 39칸 PASS를 단계 고유 관문 대신 쓸 수 없다. 실제 train/runtime/parent manifest 일반화·노출 소비는 sonnet, 단계별 판정 정책은 scripter 범위다. 이 PR은 승인 파서와 초안이며 GPU 기동 허가가 아니다. E1F 노출 문자열의 실행 꼴 변경은 별도 작은 PR에서 진행한다. 팀장 승인 전 이 초안 PR을 병합하지 않는다. Refs #555.
