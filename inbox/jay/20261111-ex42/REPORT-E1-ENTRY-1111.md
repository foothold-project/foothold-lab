# EX-42 E1 진입 준비: E0 와의 차이표 · CPU 사전검사 · 단계 이어 가기 설계

> 분류: A/학습 길 · EX-42 단계 진입
> 작성: sonnet-code-lx · 2026-11-11 (lead-lx 10:30 지시)
> 근거: CG 정본 69e5ac6b CURRICULUM-GATES.md EX-42 절 · ex42-prep.yaml · 통합 4cc326c7 · PR #630 (55100109) · E0 실행 ex42_main_20261111_072218 확인서
> 요지: E1 코드 길은 CPU 에서 막음 0 까지 닫았고, 실제 Kit 기동과 승인 칸 · 부모 핀은 lead 몫이다. 단계 이어 가기는 경계 평가를 지도 모드별로 두 장에 나누는 안을 낸다.
> 상태: CPU 확인됨 · Kit 미실행 · 이어 가기 설계는 안(코드 미작성)

## ① E1 이 E0 와 다른 점

E0 는 「지형만 EX-42 합친 메시로 바꾼다」 가 유일한 축이다. E1 은 같은 메시에서 이어 학습하며 거울 (D174 critic mirror) 을 켠다.

| 항목 | E0 | E1 (첫 구간) | 읽은 곳 |
|---|---|---|---|
| 부모 | m13000 (0 단계 학습본) | E0 m250 (누적 13250) · 판 sha 680c820b…779e | prep 부모 핀 (E1 핀은 lead 가 E0 재판정 통과 뒤 확인) |
| 학습 길이 | 250 회 고정 | 첫 구간 1000 회 · 계획 최소 1000 · 최대 2000 · 연장 +500 씩 두 번 | CG EX-42 절 · prep |
| 지형 노출 | A 연속 열 100 % · 상한 5 | 같음 (A 연속 100 % · 상한 5) | prep exposure_at_E0 · exposure_at_E1 |
| 레벨 상한 | 5 | 5. 6 으로 올리는 것은 L+ 경계에서 L5 창 통과 (52/64 와 60/64 를 두 번) 뒤에만 | CG 축 규칙 |
| 같은 메시 부모 배치 복원 | 해당 없음 (부모가 다른 메시) | 켬 (`same_mesh`) | restore_parent_placement |
| critic mirror (D174) | 끔 | 시작 때 켬. 증명서가 커밋된 계획 · 승인 바이트와 같아야 받음 | `_valid_ex42_mirror_approval` |
| 유지 · D44 칸 | 없음 | 있음 | prep |
| 명령 · DR | E0 와 같음 | 변경 없음 | prep |
| P1 간격 | 250 (= 단계 길이, 끝에서 한 번) | 1000 | `p1_interval` (train_start.py:623) |
| 승인 칸 | stage_e0_authorization | stage_e1_authorization (새 칸, 비어 있으면 닫힘) | ex42-approvals.yaml |

lead 몫 (이 세션이 건드리지 않음): 승인 칸 채우기, 계획 해시 다시 박기 (prep 편집이 해시를 바꿈), E1 부모 핀 확정, 캡 5 와 7 종 구성의 planner 확인.

## ② CPU 사전검사 결과

- 실제 E0 m250 체크포인트, 실제 사슬, 실제 runner 의 거울 스위치까지 시험으로 닫음 (test_ex42_e1_entry_cpu.py 9건). 임시 승인 사본에 시험용 E1 칸을 넣어 train_start 를 CPU 로 끝까지 훑음.
- 통합 4cc326c7 과 같은 기준에서 실패하던 시험 (eval_chain_v3, Windows 경로) 은 변경 전후 같음을 확인.
- 미확인 (Kit 필요): 실제 gym.make · 첫 reset · 두 rank, 거울을 켠 첫 update, strict 상태 불러오기, E0 수리 (#626 · #627) 의 실제 기동.

## ③ 단계 이어 가기 설계 (안)

목표 사슬: 학습 끝 → 경계 평가를 두 장에 나눠 병렬 → 관문 → 다음 단계 시작.

### 지금 코드가 하는 일

- `ex42_chain.py:254` `on_checkpoint_saved`: `p1_interval` 의 배수 회차에서만 평가를 대기열에 넣음. E 단계는 간격 = 단계 길이라 끝에서 한 번.
- 평가는 `ex42_eval_once.py` 의 `commands()` (19행) 가 한 장에서 map64 → stand 3 종 → axis_v2 를 순서대로 돌림. `run()` (147행) 이 확인서를 만듦. 모드 · 묶음을 고르는 옵션은 없음.
- E0 m250 실측 (한 장, cuda:1, 확인서 steps): map64 497 s · stand 각 15 s (3 종) · axis_v2 340 s. 합계 약 14.5 분 (08:52:29 → 09:07:13).
- 학습 중에는 두 장이 각 약 13.8 GB 라 같은 장에서 평가를 겹쳐 돌릴 수 없음 (lead 지적). 평가 자체의 GPU 메모리는 미확인.

### 안

1. 학습 종료 (E1 은 1000 회 끝). 학습이 두 장을 놓은 뒤에 평가를 시작한다 (겹치지 않음).
2. 경계 평가를 모드별로 갈라 cuda:0 과 cuda:1 에 병렬로 둔다. map64 와 axis_v2 는 이미 `--modes eval_gt,probe_prop_only,eval_pred` 를 받으므로 모드 부분집합을 `commands()` 에 인자로 노출하면 된다 (새 옵션 `modes=`, 기본 전부).
   - 장 A: eval_gt 의 map64 + axis_v2 + stand_eval_gt. 장 B: eval_pred + probe_prop_only 의 같은 묶음. 모드 수가 3 이라 정확히 반분은 아니고, 위 실측으로 보면 모드당 map64 약 166 s · axis_v2 약 113 s 로 어림하면 한 장 약 7 분 안팎 (추정, 미실측).
3. 합치는 단계: 두 장의 산출물을 한 확인서로 합쳐 기존 `measure` · `p1_score_from_measure` 로 점수를 낸다. 이미 있는 `--score-existing` (ex42_eval_once.py:235 · 261) 경로가 「이미 만든 산출물에서 점수만」 이므로 합치기의 바탕으로 쓴다. 합친 확인서에 두 장의 장치 · 모드 · 체크포인트 sha 를 모두 기록한다.
4. 관문: 계획의 승격 창 (64 × 2 창, 52/60 기준) 을 합친 점수에서 읽는다. 통과 · 보류 · 실패는 기존 판정 코드를 그대로 쓴다.
5. 다음 단계 시작: 통과일 때만 부모 = 이번 단계 마지막 저장본으로 다음 단계 시작 명령을 만든다.

### 막아야 할 것 (lead 결정 필요)

- CG D146 「EX-42 자동 기동 없음 · 졸업 판정 뒤 묻기」 와 `ex42-approvals.yaml` 의 `automatic_launch_allowed: false` 가 있어서, 5 번의 자동 시작은 지금 규칙으로는 막힌다. 단계마다 승인 칸 (E1F, E2 …) 을 lead 가 미리 채워 두고 사슬은 「그 칸이 있을 때만」 이어 가는 방식을 제안한다. 규칙 자체를 바꾸는 것은 팀장 결정이다.
- 합치기 단계가 한쪽 장의 결측을 조용히 넘기면 안 된다. 결측 모드가 있으면 점수 대신 「불완전」 로 멈춤.
- 두 장 병렬 평가의 확인서 장치 칸 (`registered_evaluation_device`) 이 한 장 전제로 쓰이는지 코드에서 아직 다 훑지 않았다 (미확인). 구현 때 먼저 훑는다.

### 코드 자리 요약

| 할 일 | 자리 |
|---|---|
| 평가 대기열 진입 조건 | ex42_chain.py:254 `on_checkpoint_saved` · :350 `register_checkpoint_p1` |
| 모드 부분집합 옵션 | ex42_eval_once.py:19 `commands` · :147 `run` |
| 두 장 분배 · 합치기 | 새 함수 (ex42_eval_once.py 옆) · `--score-existing` 재사용 |
| 관문 판정 | 기존 판정 코드 (ex42_gate_checks.py) |
| 다음 단계 시작 | ex42_training_entry.py · 승인 칸 검사 · lead 승인 칸 필요 |

## 안 한 것

- 이어 가기 코드는 쓰지 않음 (설계만). 승인 파일 · 해시 핀 · GPU · Kit 는 건드리지 않음. PR 병합 없음.
