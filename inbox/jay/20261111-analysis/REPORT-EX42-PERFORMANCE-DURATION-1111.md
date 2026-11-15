# EX-42 첫 점검 · 기본 상한 · HOLD 연장 분리

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: verifier-lx · 2026-11-11
> 근거: CG v0.16 §E.1 186~195행 · §E.4 435~437행, lead 15:50 정정 · 16:00 소유 범위 · 16:05 E1 연장 미승인
> 요지: 전 단계 첫 점검 250, 기본 상한은 정본 값, HOLD 연장은 별도 횟수로 등록한다
> 상태: CPU 한정 확인됨. 기동 소비자 수정 및 실제 자동 이어 가기 확인은 sonnet 범위

제 범위 CPU 120 passed. 통합 실행 준비는 아직 미완료다. `e_stage_table`이 첫 점검 250을 총 실행 상한으로 읽어 E1 entry 시험 4개가 실패한다. 이 실패를 기대값 변경으로 숨기지 않았고 run으로 sonnet에 넘겼다. handoff · launcher · train_start는 이번 PR에서 고치지 않았다.

## 정본과 변경

읽은 정본은 `/home/jay/mai/wt/foothold-lab/fable-25a/inbox/jay/20261026-experiments/CURRICULUM-GATES.md`, 그 사본 HEAD `368d03e2061b505fc72ad73e9cd2527a766e7738`이다. §E.1 표는 최소 체류가 아닌 **최대 회차**이고 §E.4는 첫 점검 최소를 250으로 정의한다. 성과 판정의 두 창 조건은 바꾸지 않는다. 250회를 채웠다는 이유만으로 PASS로 만들지 않는다.

| 단계 | minimum_updates | maximum_updates | extension_updates | extension_max_count |
|---|---:|---:|---:|---:|
| E0 | 250 | 250 | 0 | 0 |
| E1 | 250 | 1000 | 500 | 2 |
| E1F | 250 | 750 | 500 | 1 |
| E2 | 250 | 1500 | 500 | 2 |
| E3 | 250 | 3000 | 1000 | 2 |
| E4 | 250 | 2000 | 1000 | 2 |
| E5 | 250 | 1500 | 500 | 2 |
| M | 250 | 500 | 500 | 1 |
| E6a | 250 | 1000 | 500 | 1 |
| E6b | 250 | 2000 | 1000 | 2 |

- `ex42_prep.py` 일반 승인 검사 및 초안 생성은 scope.maximum_updates를 표의 **maximum_updates**와 대조한다. E1 전용 검사도 min250/max1000으로 읽는다.
- E1F 승인 칸 scope750은 유지하고 첫 점검250을 명시했다. `approval_sha256`을 실제 파일 바이트로 재고정했다.
- materialize의 예산 예약은 첫 점검250이 아니라 **기본 상한 전체**다. 전체 예산의 뜻과 이미 쓴 회차는 기존처럼 호출자가 명시한다.
- materialize가 발행하는 연장 계약은 `judgment=HOLD`, `after_updates=기본 상한`, `increment_updates`, `max_count`, `maximum_updates=기본 상한+증분×횟수`를 갖는다. E1F는 750 도달 뒤 +500 한 번, 총1250까지다. 표에 연장 숫자가 있다는 것과 실행 승인은 다르다.
- E1의 extension_authorized=false는 그대로다. 16:05 확인에 따라 10:48 승인 밖인 E1 연장을 이번 PR에서 열지 않았다. M은 기존처럼 disabled이며 조건부 갈래 선택을 바꾸지 않는다.
- 실행 중인 E1의 옛 source plan(min1000/max2000)은 고치지 않는다. materialize는 새 승인 template의 회차 기준으로 종료 자격을 확인하되, gate는 계속 실제 source plan SHA와 대조한다. 부모·측정값·두 창 PASS 검증도 그대로 한다. source template의 기본 상한과 승인 scope 불일치도 거절한다.
- 기본 상한을 넘긴 source exit는 그 source plan에 핀된 승인 파일과 완전한 연장 계약이 있을 때만 허용한다. 파일이 없거나 SHA가 다르면 연장 상한을 인정하지 않는다.

## 검증

원출력과 재현 스크립트: `/home/jay/mai/tmp/verifier-lx/duration-1111/`.

| 답 아는 입력 / 제거본 | 결과 |
|---|---|
| 수정 전 정본 10행 · E1 250 PASS | 11 failed, 4 passed. 잘못된 최소 체류 때문에 조기 종료 거절 재현 |
| 새 계약 · materialize · 표 승인 · 미래 승인 · E1 핀 · prep 6개 파일 | `120 passed in 30.22s`, `final.log` |
| 옛 source plan min1000을 보존한 E1 m250 PASS | 새 E1F min250/scope750 발행, 누적 부모13500, 원 source 파일 바이트 불변 |
| 연장 시작250 · 횟수2 · PASS 연장 · 총1750 변이 | E1F 승인 검사 거절 |
| source 승인 SHA가 다름 | 총1250 연장 상한 인정하지 않음, 기본750만 |
| 승인 scope를 minimum으로 되돌림 | 1 failed |
| source의 옛 minimum을 그대로 적용 | 1 failed |
| E1F min을 다시750으로 | 1 failed |
| 연장 횟수 곱셈 제거 | 처음 시험에서 생존하여 보강. 보강 뒤 6 failed, 4 passed |
| 마지막 변수명 정리 뒤 계약·materialize 재실행 | `51 passed in 19.36s`, `post-rename.log` |
| 변경 Python pyflakes | 0 |

새 계약 시험은 18개다. 정본 숫자를 테스트에 직접 적었으며 구현에서 기대값을 가져오지 않았다. 제거본은 자기 scratch 사본에서만 만들었다. 운영 파일·실행 E1·GPU·Kit은 만지지 않았다.

## 소비자 연결에서 남은 것

1. `scripts/ex42_training_entry.py:e_stage_table`의 `updates=row.minimum_updates`는 총 실행 한도와 분리해야 한다. 새 표를 적용한 뒤 E1 entry의 CLI·부모 로드·runtime·table 네 시험이 실패했다(`green.log`). 이번 PR은 해당 시험 기대값을250으로 낮추지 않았다.
2. 통합4efda640의 handoff는 모든 단계 경계를 읽는다. 다만 `_continue_decision`은 scope 기본 상한에서 notify하고, launcher도 기본 실행 한도 밖 segment_end를 거절한다. HOLD에 한해 등록 연장을 적용하고, 실제 연장 경계마다 다시 판정하는 소비는 sonnet 소유다. 이 PR의 계약 검사 통과를 실제 자동 연장 완성으로 읽으면 안 된다.
3. 실제 실행 E1은 기존 고정 코드·plan을 사용한다. 본 PR만 병합해서 이미 도는 프로세스의 판정 시각이 바뀌었다고 주장하지 않는다. 다음 경계의 별도 운영 연결은 담당자가 확인해야 한다.

새 승인 파일 SHA256: `7e9f72da0e708a36f3b44c3560414f5d77fc33fedb1129ccc4ac99c76473c98d`.
새 prep SHA256: `84dc2dfdcd2f3eeadfc984d96ba320f12019c2663bd29fa635de2ff6fb5526cc`.
Refs #555.
