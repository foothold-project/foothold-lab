# EX-42 후보 A · 연속 상한 L5 → L9 를 실행 경로에 넣는 정본 변경안과 설정 diff 초안

> 분류: 제안 (정본 변경안 + 설정 diff 초안 · 팀장 결정 전 준비 · 기동 금지)
> 작성: planner-lx · 2026-11-12 10:37
> 근거: lead 11/12 10:21 카드 · 원장 `decisions.tsv` 11/06 22:3x · 22:5x · 23:2x · 11/07 16:3x · 17:2x · 11/08 19:0x · 22:5x · 11/11 13:07 · 19:38 · 정본 CURRICULUM-GATES v0.17e (`feature/fable-25a-jay` 66efd331) · 통합 d237d904 코드 · E1 실행 둘의 `params` (읽기 전용)
> 요지: 정본은 E1 을 「연속 상한 5 → 9 · 경계마다 +1」 로 적지만 실행 경로는 상한 5 를 다섯 자리에 박아 두었다. 그래서 끝난 E1 과 재학습 E1 은 2,000 회를 상한 5 로 돌았다. 이 문서는 정본에 더할 문장과 prep 설정 diff 를 내고, 고쳐야 할 코드 자리와 담당을 적는다. 메시는 바꾸지 않는다.
> 상태: 구현 포함 (11:32 갱신 · lead 11:05 지시 · 팀장 11:28 재시작안 승인은 lead 전달) · 0 절이 지금 PR 의 내용이고 1 절부터는 10:37 초안 그대로다 (초안의 start 5 · hold 키는 0 절로 대체)

## 0. 이 PR 에 구현된 것 (lead 11/12 11:05 · 고침 a~d)

| 고침 | 자리 | 내용 |
|---|---|---|
| a | `terrains/ex42_exposure.py` `raise_continuous_cap` · `scripts/ex42_training_entry.py` `prepare_e0_env_cfg` · `ex42_exposure_receipt.py` `recompute_from_plan` | 단계 행의 `terrain.continuous_level_cap {start, step_per_boundary, end}` 로 구간 상한 = min(start + step × 지난 경계 수, end). 연속 규칙의 열별 상한을 그 값으로 덮고 contract 에 `continuous_level_cap` 으로 적는다. plan 은 구간 사이에 안 바뀐다 (plan SHA 그대로 이어 받기) |
| b | `scripts/ex42_training_entry.py` `EX42StageZeroRuntime` | 승급 상한 리터럴 5 세 곳을 contract 의 구간 상한으로 (`_ex41_terrain.level_cap` · `effective` · `state_dict`). 이어 받기는 「저장된 상한 ≤ 지금 상한」 을 받는다 (5 미만 · 더 큰 값 · 정책 다름은 거절) |
| c | `scripts/ex42_stage_launcher.py` | 새 출발 (`next_stage`) 에도 `EX42_AUTO_SEGMENT_END` 가 있으면 `--ex42_segment_end` 로 넘긴다. 쓴 뒤 자식 환경에서 지워 뒤 기동이 물려받지 않게 한다 |
| d | `curriculum/ex41-fixed5000.yaml` · `curriculum/ex41.py` 두 줄 · prep `stage_zero.source.normalized_sha256` | 실험 가지 `sonnet-code/ex42-e1-slip-b379-1111` 67d2506d 의 `foot_slip` −0.15 네 줄을 통합 위로 |
| 설정 | `curriculum/ex42-prep.yaml` | E1 `continuous_level_cap {start 6, step_per_boundary 1, end 9}` · `exposure_at_E1` 연속 상한 6 · E1F 물려받는 상한 허용 5~9 |

- 운영 규칙 (코드 아님): 유지표가 HOLD 면 다음 구간을 띄우지 않는다. 주의: 자동 이어 가기 (`ex42_stage_handoff.py:41~80`) 는 유지표와 무관하게 다음 구간을 띄우므로, 이 규칙을 지키려면 자동 정책을 끄거나 구간을 손으로 띄워야 한다.
- 부모: m13250 (prep `stages[E1].parent` · 승인 `scope.parent_sha256` 그대로). m13000 은 핀만 바꿔서는 안 된다 (E1 부모 검사가 E0 실행을 요구).
- 띄우는 꼴: 첫 구간은 `EX42_AUTO_ACTION=next_stage` + `EX42_AUTO_SEGMENT_END=250`, 다음 구간은 `continue` + 그 경계 저장본 + 구간 끝 500 · 750 · 1,000. 구간 상한은 6 · 7 · 8 · 9.
- 병합 뒤 할 것: prep 과 `ex41-fixed5000.yaml` 이 바뀌어 plan SHA 와 0 단계 원본 SHA 가 바뀐다. 승인 칸 재고정 (verifier) · 20 회 실기동에서 로그 `EX42_E0_EXPOSURE` 의 `level_caps` 와 `_ex41_terrain.level_cap` 이 같은지 (runner).
- 미확인: E1F 넘김 때 `read_applied_cap` (`ex42_stage_materialize.py:170~204`) 이 구간마다 다른 상한이 적힌 로그를 받는지. `foot_slip` 네 줄은 E1 뿐 아니라 그 원본을 읽는 뒤 단계 전체에 적용된다.

## 1. 지금 상태 (통합 d237d904 · 실측 · 코드)

상한 5 가 박힌 자리.

| 자리 | 값 | 하는 일 |
|---|---|---|
| `foothold_s2/curriculum/ex41.py:780` | `initial_level_cap != 5` 면 거절 | 환경 설정에 상한을 넣는 문 |
| `foothold_s2/scripts/ex41_startup.py:1132` | `initial_level_cap=5` | 위 함수에 넘기는 값 |
| `foothold_s2/scripts/ex42_training_entry.py:1071 · 1094 · 1249` | `{"policy": "performance", "level_cap": 5}` | 실행 중 승급 상한 (`ex41.py:822` `capped_moves`) 과 저장본 상태 |
| `foothold_s2/curriculum/ex42-prep.yaml` E1 `exposure_at_E1.positive[0].level_cap` | 5 | 열마다 자르는 상한 (`terrains/ex42_exposure.py:302~347` `apply_exposure`) |
| 같은 파일 E1F `inherited_stage_templates[0].allowed_values` | 5 · 6 | E1 끝 상한을 물려받을 때 허용 값 |

- 상한은 두 겹이다. ① 승급 판단의 상한 (`_ex41_terrain.level_cap`) ② 열마다 레벨을 자르는 상한 (`level_caps`). 한쪽만 올리면 다른 쪽이 5 에서 막는다.
- 메시는 이미 10 줄 (L0~L9) 이다 (`env.yaml` `num_rows 10` · 메시 88197b3a · **실측**). 상한을 올려도 메시 SHA 는 그대로다.
- 치수: 계단 한 단은 레벨 식 0.05 → 0.23 m (`terrains/rough_go2_cfg.py:21` **코드**). L5 0.149 m · L9 0.221 m (analyst 6b8739a7 **읽기**). L6 부터 D44 의 한 단 0.16 m 가 학습 범위 안쪽이다.
- 실행 기록: 끝난 E1 (`ex42_main_20261111_114505`) 과 재학습 (`ex42_main_20261112_013611`) 의 경계 넷 (250 · 500 · 750 · 1,000) 모두 상한 5. 레벨 평균 4.88~4.93 (**실측**).
- 기계 대조 (가지 `feature/planner-ex42-canon-params-check-1112` 9adfe7ed): 두 실행과 prep 모두 `E1.continuous_level_cap` 이 FAIL 이다.

## 2. 정본 변경안 (v0.17f 로 넣을 문장)

새 판정 문장은 만들지 않았다. 원장 문장과 정본 §E.3.1 의 기존 HOLD 를 E1 행에 이어 붙인 것이다.

| 자리 | 지금 문장 (v0.17e) | 더할 문장 | 근거 |
|---|---|---|---|
| §E.2 E1 「레벨」 | 상한 5 → 9 · 경계마다 +1 · 성과 승급 | 적용: 구간의 상한 = 5 + 올린 횟수 (9 에서 멈춤). 올림은 250 회 경계에서 한 번에 +1 이고 승급 상한과 열별 상한을 함께 올린다. 경계마다 그때의 상한을 기록한다 (`stage_config` 의 상한 칸과 `EX42_E0_EXPOSURE` `level_caps`) | 원장 11/06 22:3x · 23:2x |
| §E.2 E1 「승급 문턱」 | 한 경계에서 통과로 보는 창 수는 원장에 숫자가 없다 | 경계에서 유지표 (§E.3.1) 가 HOLD 가 아니면 올린다. HOLD 인 경계는 올리지 않고 `level_cap_hold` 로 기록한다. 유지가 회복된 경계에서 다시 +1 한다. 새 어려운 칸 (D44 여섯 칸 · L6~L9 고정 칸) 의 미달은 멈춤 사유가 아니다. 학습은 어느 쪽이든 계속한다 | 원장 11/06 23:2x · 11/07 16:3x · 17:2x · 정본 §E.3.1 「fail → HOLD」 |
| §E.2 E1 「바꾸는 축 하나」 | `terrain.continuous_level_cap` 5 → 9 (L+ · 경계마다 +1) | E1 의 경계는 모두 L+ 한 축이다. 설정 칸은 prep E1 `terrain.continuous_level_cap` {start · step_per_boundary · end · hold_when · hold_event} | 정본 D163 · 이 PR |
| §E.2 E1F 「레벨」 | E1 끝 상한 그대로 (5~9) | 변경 없음. prep 허용 값을 5~9 로 맞춘다 | v0.17b |
| §E.4 `stages[].terrain.continuous_level_cap` | int · 5 · L+ 경계에서만 +1 | 꼴을 map 으로: `start` · `step_per_boundary` · `end` · `hold_when` · `hold_event` | 이 PR |

「유지 칸이 크게 떨어질 때」 의 숫자는 원장에 없다. 그래서 정본에 이미 있는 유지표 HOLD (생존 26 칸 ≥ 기준 − 3 등 · §E.3.1) 를 그대로 쓴다. 다른 문턱을 원하면 6 절에서 정한다.

## 3. 설정 diff 초안 (이 PR 의 `ex42-prep.yaml`)

```yaml
# stages[id=E1].terrain
continuous_level_cap:
  start: 5
  step_per_boundary: 1
  end: 9
  hold_when: retention_table_hold
  hold_event: level_cap_hold
exposure_at_E1:            # 그대로 · level_cap 5 는 시작 값
  ...
# stages[id=E1F].authorization_contract.inherited_stage_templates[0]
allowed_values: [5, 6, 7, 8, 9]     # 앞 값 [5, 6]
```

- 이 PR 은 칸을 등록만 한다. 읽는 코드가 없으므로 병합해도 실행은 그대로 상한 5 다.
- prep 이 바뀌면 plan SHA 가 바뀐다. 승인 칸 재고정은 verifier 몫이다 (#737 때와 같다).

## 4. 고칠 코드 자리 (planner 는 고치지 않음 · 담당 제안)

| 할 일 | 자리 | 담당 제안 |
|---|---|---|
| 상한 5 고정 문을 「단계 행의 상한」 으로 바꾼다 | `ex41.py:780` · `ex41_startup.py:1132` | sonnet-code |
| 실행 중 승급 상한 · 저장본 상태를 단계 행에서 읽는다 | `ex42_training_entry.py:1071 · 1094 · 1249` | sonnet-code |
| 구간 재개 때 상한 = 앞 구간 상한 + 1 (유지표 HOLD 면 그대로) 을 계산해 두 겹에 넣는다 | 경계 멈춤 → 재개 경로 (#643 `--ex42_segment_end` · `--ex42_resume_from`) · `apply_exposure` 호출부 (`ex42_training_entry.py:290`) | sonnet-code |
| 경계 기록에 그 구간의 상한을 남기고 올리지 않은 경계는 `level_cap_hold` 를 남긴다 | `ex42_application.jsonl` | sonnet-code |
| E1F 가 물려받는 상한 읽기가 5~9 를 받는지 | `ex42_stage_materialize.py:170~204 · 358` | verifier |
| 대조 검사 표의 `hold_event` 를 `level_cap_hold` 로 등록 | `curriculum/ex42-canon-claims.yaml` | planner (A 승인 뒤) |

## 5. 검증 · 실패 감지 · 멈춤 규칙

| 무엇을 | 어떻게 | 통과 |
|---|---|---|
| 실행 전 | `ex42_canon_params_check.py --plan` | `E1.continuous_level_cap` PASS (이 PR 의 prep 에서 PASS · 통합 prep 에서 FAIL) |
| 20 회 실기동 점검 | 로그 `EX42_E0_EXPOSURE` 의 `level_caps` 와 `_ex41_terrain.level_cap` | 두 값이 같고 구간 상한과 같다 |
| 경계마다 | `ex42_canon_params_check.py --run-dir` | 상한이 한 칸씩 오르거나 `level_cap_hold` 기록이 있다 |
| 효과 | `map_switch.jsonl` `terrain_level_mean` · 고정 칸 L6 · L9 생존 · 유지표 | 레벨 평균이 5 를 넘는다. 넘지 않으면 「상한은 올랐으나 정책이 못 오름」 으로 보고한다 (실패가 아니라 관찰) |
| 멈춤 | 유지표 HOLD | 그 경계는 올리지 않는다. 학습은 계속한다. 두 경계 연속 HOLD 면 lead + analyst 판단 (원장 11/07 17:2x) |

미측: 상한을 올린 뒤 회차 속도 · 메모리 변화 (없을 것으로 보지만 재지 않았다 · 20 회 점검에서 runner 가 잰다).

## 6. 정할 것 (권고 포함)

1. 첫 올림 시점.
   - (가) 5 로 시작해 250 회 경계부터 올린다: 구간 상한 5 · 6 · 7 · 8, 끝에서 9 가 되어 E1F 가 9 로 시작한다.
   - (나) 6 으로 시작한다: 구간 상한 6 · 7 · 8 · 9. E1 안에서 L9 를 250 회 배운다.
   - 권고: (나). 상한 5 구간은 이미 2,250 회 돌았고 레벨 평균이 4.90 에서 평평하다. lead 11/12 02:00 결정 「단계 시작 블록 = 앞 단계 끝 + 진입 축 하나」 와도 같은 꼴이다. (나) 로 정하면 이 PR 의 `start` 를 6 으로 바꾼다. 초안은 정본 문장 「5 → 9」 그대로인 (가) 다.
2. 이미 끝난 E1 뒤에 어디서 올리나.
   - (ㄱ) 승인된 E1 연장 +500 × 2 (원장 11/11 19:38 ④) 를 올림 구간으로 쓴다. 1,000 회 = 경계 넷이라 9 까지 닿는다. 조건: 그 연장은 「관문 HOLD 로 상한에 닿을 때만」 이다.
   - (ㄴ) E1 을 새로 1,000 회 돈다 (예산 20,000 에서 1,000 더 씀).
   - (ㄷ) E1 은 지금 결과로 닫고 E1F 부터 경계마다 이어 올린다 (대조 문서 `EX42-V017A-PREP-CODE-DIFF-1112.md` §4). 이 경우 E1F · E2 의 「한 경계 한 축」 과 부딪혀 축 순서를 다시 등록해야 한다.
   - 권고: (ㄱ). 새 예산 결정이 필요 없고 E1 안에서 닫힌다. 재학습 E1 의 관문 결과가 HOLD 가 아니면 (ㄴ) 이다. 재학습 관문 결과는 planner 가 확인하지 않았다 (**미확인**).

## 7. 안 한 것 · 손대지 않은 것

- 코드 수정 0 · GPU · Kit 실행 0 · 정본 본문 수정 0 (v0.17f 는 결정 뒤에 쓴다).
- 「크게 떨어질 때」 를 유지표 HOLD 로 읽은 것은 planner 의 해석이다. 원장에 숫자가 없다.
- 상한을 올린 구간에서 D44 수치가 실제로 덜 출렁이는지는 재지 않았다. 단 아홉 연속 · 좁은 꼭대기 도착은 A 로 생기지 않는다 (후보 B).
