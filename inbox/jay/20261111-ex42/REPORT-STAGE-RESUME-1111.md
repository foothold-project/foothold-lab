# EX-42 E1 경계마다 멈춤 · 평가 · 이어 학습

> 분류: A/학습 길 · 단계 이어 가기
> 작성: sonnet-code-lx · 2026-11-11 (lead-lx 11:51 팀장 결정)
> 근거: train_start.py · ex42_training_entry.py · ex42_stage_handoff.py · 실제 E0 m250 (optimizer · 지각 · AdaSmpl · RNG · env_state · 커리큘럼) · #634 병합 · #640 · #638
> 요지: E1 은 250 마다 학습을 멈추고, 평가 뒤 PASS 면 다음 단계 아니면 같은 실행 폴더에서 그 저장본을 이어 학습한다. 코드와 CPU 시험은 닫았고 Kit 이어 받기는 미확인이다.
> 상태: CPU 확인됨 (실제 train_start 드라이런 포함) · Kit 미실행

## 흐름

1. 구간 1: E1 새 시작, `--ex42_segment_end=250`. 학습이 250 에서 멈추고 (곡선 상태는 stage 1000 그대로, finished 아님) 저장본 model_250.pt 가 대기열 평가 (학습 끝난 뒤 두 장 분배, #634) 로 들어간다.
2. 평가 꼬리 (`ex42_eval_once._hand_off`): 판정이 PASS 이고 단계 최소 회차 (E1 1000) 이상이며 다음 단계에 승인 칸이 있으면 다음 단계 launcher (#640). 그 밖에는 E1 이 같은 실행 폴더에서 이어 간다.
3. 이어 가기: launcher 가 환경 `EX42_AUTO_ACTION=continue`, `EX42_AUTO_RESUME_CHECKPOINT`, `EX42_AUTO_SEGMENT_END` 를 받는다. 같은 인자에 `--ex42_resume_from=<model_N.pt> --ex42_segment_end=<다음 경계>` 만 더해 train_start 를 다시 띄운다 (`--ex42_log_dir` 는 같은 폴더).
4. 250 → 500 → 750 → 1000. 1000 에서 PASS 아니면 한도 도달 알림 (연장은 승인 칸이 false).

이어 가기 허용 조건 (모두): 승인 정책 approved_stage_only · E1 칸의 scope 한도 · 연장 false · 평가된 저장본이 manifest 의 마지막 저장이고 sha 가 평가 영수증과 같음. 하나라도 틀리면 알림만.

## 코드 자리

| 자리 | 내용 |
|---|---|
| `ex42_training_entry.validate_ex42_stage_zero_resume` | 단계 · 부모 누적 회차 · 구간 끝을 인자로 (기본은 단계 0 그대로). E1 저장본 누적 13250 + 회차 |
| `ex42_training_entry.validate_ex42_segment_end` | 구간 끝은 승인 칸 경계 (250 배수) · 시작 회차 뒤 · 단계 한도 안. E0 는 250 만 |
| `run_ex42_stage_e0_entry` · `validate_ex42_stage_e_cli` | E1 만 이어 받기 허용, 같은 실행 폴더 (manifest 있어야), 새 시작은 폴더가 새것이어야 |
| `train_start.py` | `--ex42_segment_end`, E 단계 이어 받기 검증, 누적 원점은 검증 증명에서 (하드코딩 12000 제거), 구간 길이 = 끝 - 원점, E1 은 load 전에 mirror 를 켬 |
| `start_runner.load` | E1 저장본의 D174 grant 가 W72 영수증이 아니라서 이어 받으면 mirror 가 조용히 꺼지던 것 수리 (저장 grant 또는 지금 검사한 grant 로 유지) |
| `ex42_stage_handoff.decide_next_stage` | launch / continue / notify 결정 |

## 시험 (CPU)

- test_ex42_stage_resume_cpu.py 16건: 실제 E0 m250 내용에 E1 단계 칸만 바꾼 저장본으로 이어 받기 검증, 각 핀 하나씩 거절, 마지막 저장 아님 거절, 구간 끝 경계 검사, load 가 mirror 를 유지.
- test_ex42_stage_continue_cpu.py: 250 · 500 · 750 에서 이어 감, 한도에서 끝, 승인 꺼짐 · 넓어짐 · 칸 없음 · 저장본 불일치는 알림, launcher 환경.
- 돌연변이 5 (load 의 ex42 grant 허용 제거 · 지금 grant 허용 제거 · 단계 id 검사 제거 · 구간 끝 범위 검사 제거 · 경계 배수 검사 제거) 모두 걸림.
- 실제 `train_start.py` E1 드라이런 (CPU, Kit 안 띄움): `--ex42_stage_e1_dry_run --ex42_resume_from ... --ex42_segment_end=500` 이 승인 · 이어 받기 검증 · 구간까지 통과 (누적 13500 -> 13501, 요청 250 회).

## lead 가 Kit 에서 확인할 것 (짧게)

E1 이 아직 한 번도 안 돌았으므로 이어 받기 대상 저장본이 없다. 실제 순서로 확인한다.

```
# 구간 1 (새 시작). 기존 E1 기동 인자에 구간 끝만 더한다. OUT 은 그 실행 폴더.
... --ex42_stage_e1_approved --ex42_log_dir="$OUT" --ex42_segment_end=250
# 250 에서 멈추고 model_250.pt 가 생기면, 같은 인자에 아래를 더해 구간 2 (이어 가기)
... --ex42_stage_e1_approved --ex42_log_dir="$OUT" --ex42_resume_from="$OUT/model_250.pt" --ex42_segment_end=500
```

보는 줄: `EX42_STAGE_E1_RESUME_PREFLIGHT` (원점 250 · 첫 회차 251 · 누적 13501), `EX42_SELF_RESUME_READBACK`, `EX42_SELF_RESUME_ROOT_XY_READBACK` (outside_reset_bounds_count 0), 첫 update 줄, mirror 가 켜져 있는지 (`ex41_critic_mirror`), manifest `ex42_resume_segments` 에 구간 추가. CPU 사전확인은 같은 인자에 `--ex42_stage_e1_dry_run` 을 더하면 된다 (이어 받기 검증까지 내고 종료).

## 미확인 · 안 한 것

- Kit: 이어 받기 실제 복원 (optimizer · env_state · RNG · 지형 복원 · 첫 update), 구간 1 이 250 에서 정상 종료되며 마지막 저장과 평가 대기열 등록, 두 장 분산에서의 이어 받기.
- 평가 판정: #631 은 E0 만 PASS/FAIL 을 낸다. E1 은 항상 HOLD 라서 지금은 1000 까지 계속 이어 가고 끝에서 한도 알림이다 (E1 승격 관문 판정은 별도).
- 계획 · 승인 파일이 경계 사이에 다시 고정되면 (해시 변경) 저장본의 계획 해시와 달라 이어 받기가 거절된다 (의도된 닫힘). 같은 계획으로 이어 가야 한다.
- 실제 launcher 셸은 만들지 않음 (lead 몫). 알림 송신기도 없음.
- 최소 회차 전 PASS 는 이어 간다 (E1 은 1000 이 최소). 규칙을 다르게 하려면 정하면 된다.
