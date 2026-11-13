# EX-42 새 종류 env 의 명령 묶음 (kind_task) 을 표집기에 넣는 설계

> 분류: 설계 초안 (구현은 sonnet-code-lx)
> 작성: planner-lx · 2026-11-13 10:08
> 근거: lead-lx 10:04 의뢰 · 정본 CURRICULUM-GATES §E.3 「새 종류 과제 묶음 kind_task」 행 (395 행) · §E.4 YAML 표 498 행 · 예 576 행 · 코드 `commands/ex42_shares.py` (통합 6da1f1cc 읽음)
> 요지: 정본은 새로 여는 종류의 env 에 「전진 1.0 + 깃발」 만 주라고 하는데, 지금 표집기는 그 env 에 13 칸 자유 명령 (후진 · 옆 · 제자리 회전 포함) 을 준다. plan 칸과 표집 한 곳을 맞춘다.
> 상태: 초안 · E2 기동 전에 필요 (E1F 에는 연속 밖 env 가 없어 영향 없음)

## 1. 지금 어떻게 도나 (읽음)

- 정본 395 행: 새 종류 env 의 명령 = `command_set: [forward_1.0, flag]` 와 `command_weights` (기본 0.63 : 0.37 · **가정**). 정지 · 후진 · 옆 · 회전은 E5 전에 그 종류에 배정하지 않는다. 까닭: 「범위 밖 명령을 따라 실패」 를 「명령을 못 따름」 과 섞지 않으려고.
- plan: `stages[].terrain.kind_task.<family>.<kind>` 에는 `push: on/off` 만 있다. `command_set` · `command_weights` 칸이 없다 (정본 498 행의 칸이 plan 에 안 들어옴).
- 코드: `CommandShares.on_reset` 은 연속 지형 열이 아니면 깃발을 끄고 `env_stage` 를 0 으로 둔다. 몫 계약도 그렇게 적혀 있다 (`other_columns: unchanged_source_stage`). 그래서 그 env 는 stage 0 의 13 칸 몫으로 자유 명령을 뽑는다.
- `command_set` 을 읽는 함수 둘 (`ex42_boundary_rules.extend_kind_commands` · `command_counts`) 은 있지만 학습 쪽에서 부르는 곳이 없다.
- 깃발 좌표는 준비돼 있다: 합친 메시의 열마다 깃발 표가 있고 (`terrains/ex42_flags.py` 의 `MeshFlagProvider` · PR #657 병합), 듬성 칸의 깃발은 발판 위에 놓인다 (정본 395 행).

E2 에서 생기는 일: `stepping_stones_low` 5 % (약 307 env) 가 징검다리 위에서 후진 · 옆걸음 · 제자리 회전 명령을 받는다.

## 2. 바꾸는 것

### plan

여는 종류마다 그 단계의 `terrain.kind_task.<family>.<kind>` 에 두 칸을 더한다 (push 옆).

```yaml
kind_task:
  A:
    stepping_stones_low: {push: off, command_set: [forward_1.0, flag], command_weights: {forward_1.0: 0.63, flag: 0.37}}
```

- 값은 정본 576 행의 예 그대로다. 0.63 : 0.37 은 「부모의 전진 · 깃발 몫 0.17 : 0.10 을 다시 나눈 값」 이고 정본이 **가정** 으로 적어 둔 것이다 (승인 칸에 들어갈 값인지 lead 확인).
- 연속 7 종에는 넣지 않는다 (그 열은 행의 `shares` 가 정한다).

### 읽기 (`ex42_shares.read_contract`)

- 그 단계의 `exposure_at_<단계>.positive` 에서 연속이 아닌 열린 종류를 모으고, 종류마다 `command_set` · `command_weights` 를 읽어 계약에 `kind_commands: {(family, kind): {...}}` 로 싣는다.
- 거절: 열린 연속 밖 종류에 두 칸이 없음 · 키가 서로 다름 · 음수 · 합이 1 이 아님 (오차 1e-9) · 집합에 `forward_1.0` · `flag` 밖의 이름 (E5 의 C 경계가 `extend_kind_commands` 로 늘리기 전까지).
- `other_columns` 는 `kind_task_command_set` 으로 바꾼다. 연속도 아니고 `kind_task` 명령 칸도 없는 열에 노출이 있으면 거절한다 (조용히 자유 명령으로 떨어지지 않게).

### 표집 (`CommandShares`)

- `attach`: 종류 묶음마다 stage 를 하나 더 만든다. `shares = {forward: 1.0}` · `ranges.forward_vx = (1.0, 1.0)` · heading 몫 0 · 회전 덧붙임 없음. `runtime.plan.stages = [stage0, free_stage, kind_stage…]`.
- `on_reset`: 열이 종류 묶음에 속한 env 는 `command_weights['flag']` 확률로 깃발 env, 아니면 그 종류의 stage 번호를 `env_stage` 에 준다. 연속 열의 뽑기 순서는 그대로 두고 종류 열의 뽑기를 그 뒤에 한다 (연속 env 의 난수 흐름이 안 바뀌게).
- 이렇게 하면 회차 명령 검사가 따로 고칠 것 없이 맞는다: 종류 env 의 전진은 그 stage 의 칸 범위 (정확히 1.0) 로, 깃발 env 는 깃발 정의역으로 본다 (#763).
- 지형 레벨도 그대로 맞는다: 깃발 env 는 깃발 규칙, 전진 env 는 이동 거리 규칙 (#762).

### 기록

- `command_shares_<회차>_rank<r>.json` 의 집계에 종류 묶음을 따로 둔다 (연속 · 종류별 · 전체). 정본은 분모를 둘 다 적으라고 한다 (`record_both_denominators`).

## 3. 고칠 곳

| 파일 | 내용 |
|---|---|
| `curriculum/ex42-prep.yaml` | E2 ~ E6b · M 행의 여는 종류에 `command_set` · `command_weights` (plan sha 바뀜) |
| `commands/ex42_shares.py` | `read_contract` · `CommandShares.attach` · `on_reset` · 집계 |
| `scripts/ex42_training_entry.py` | `env_stage` 가 2 이상일 수 있는 자리 (stage 수를 2 로 가정한 곳이 있는지 확인) |
| 정본 §E.4 | 498 행의 칸 경로에 family 단계를 넣음 (`kind_task.<family>.<kind>`) |
| 시험 | 아래 |

## 4. 시험 (실제 plan 행으로)

1. E2 행 · 3072 env: `stepping_stones_low` 열의 env 는 명령이 (1.0, 0, 0) 이거나 깃발 env 다. 후진 · 옆 · 회전 · 정지가 0 건.
2. 그 열에서 깃발 비율이 0.37 둘레 (env 수에 맞는 허용 폭).
3. 연속 열 env 의 명령과 깃발 배정이 고치기 전과 같은 값 (같은 시드).
4. 열린 종류에 칸이 없으면 기동 전에 거절.
5. 실제 명령 term 으로 기동 reset 두 번 + 몇백 걸음: 회차 명령 검사 위반 0 (`test_ex42_flag_command_contract_cpu.py` 의 방식).
6. `command_shares` 기록에 종류 묶음의 수가 따로 나온다.

## 5. 안 정한 것

- 0.63 : 0.37 을 그대로 쓸지 (정본의 가정).
- 완료 판정 (`tile_end_reach`) 과의 연결은 평가 쪽 일이다 (이 문서 범위 밖).
- E1F 는 고칠 것이 없다 (`exposure_at_E1F` = 연속 100 %).
- 통합의 다른 열린 PR 에 같은 일이 이미 있는지는 보지 않았다.
