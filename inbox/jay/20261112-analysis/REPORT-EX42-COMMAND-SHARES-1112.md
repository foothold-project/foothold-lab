> 분류: A/정책학습
> 작성: verifier-lx · 2026-11-12
> 근거: lead 01:5x · 02:09 의뢰, CG E.2 E3, prep command_allocation, 실제 MixedVelocityCommand CPU 실행
> 요지: E1F 이후 등록된 연속 지형 명령 몫을 실제 표본에 연결하고 두 분모의 rank별 소비를 기록
> 상태: CPU 검증 · Kit 미실측 · planner 단계별 벡터 등록과 경계 C 적용은 별도

# EX-42 command shares 소비

기존에는 모든 EX-42 단계가 T0_prime의 자유 명령 13칸만 읽었다. E1F에 이미 등록된 flag 0.10도 사용되지 않았다. 이 변경은 E1F 이후 `stages[].shares`의 정확한 14개 키, 합 1, 유한 확률을 시작 전 검사한다. E0/E1/0단계의 명령 경로와 난수 추출은 유지한다.

| 소비 자리 | 변경 |
|---|---|
| ex42_training_entry.validate_ex42_stage_e_cli | shares가 없으면 dry/Kit 이전 거절. 기본 0으로 대체하지 않음 |
| train_start → make_ex42_stage_zero_plan_view | 기동 prep와 실제 stage_id를 전달. 기존 보상/source stage는 그대로 |
| commands/ex42_shares.configure_env | 모든 env에 FlagState 저장 공간 확보. 다른 깃발 allocator와 충돌하면 거절 |
| Runtime.on_reset → CommandShares.reset | E0 kind_task.continuous와 실제 메시 열을 대조한 연속 지형 env에서만 flag 확률 추출. 나머지 열은 기존 source-stage 명령 유지 |
| mixed_core.resample_stage | 자유 에피소드의 13칸을 각 share/(1-flag)로 정규화하여 기존 계산에 전달 |
| MixedVelocityCommand flag 재추출 | 기존 깃발 좌표/flag_resample 경로 사용. 실제 flag 표본 수도 집계 |
| flush_consumption | 두 rank 모두 update 종료 후 rank별 영수증. rank0 전용 on_checkpoint에 의존하지 않음 |

## 원자료 계약

`command_shares_<iteration>_rank<N>.json`:
- `configured.shares`: prep가 정한 전체 몫. `mode_selection=episode_reset`.
- `cumulative.reset_modes`: 에피소드 reset의 free/flag 배정 횟수.
- `cumulative.samples`: 실제 명령 재추출 13칸+flag 횟수.
- `cumulative.steps`: 실제 pre-step 소비 횟수.
- 각 집계의 `all`, `continuous`에는 `counts`, `total`, `fractions`. 분모 0이면 null이며 0%로 위장하지 않는다.
- `rank`, `world_size`, `plan_sha256`, `stage_id`, `iteration`, `count_origin_update`.
- rank별 누적은 같은 origin에서 차분한다. 재개 시 각 rank가 새 집계 구간을 시작한다. 공유 checkpoint의 rank0 관측치를 rank1 관측치로 복사하지 않는다. 명령 난수 복원은 기존 command_rng 경로 그대로다.
- 기록 시점은 rank0 모델 저장 전이므로 production 영수증의 `checkpoint=null`. 소비자는 **같은 run의 model/manifest SHA와 plan·stage·iteration을 대조해 묶어야 한다**. 이 파일 하나를 checkpoint의 바이트 증명으로 쓰면 안 된다.
- 임시 파일 fsync 뒤 os.link로 발행. 같은 이름을 덮어쓰지 않으며 기록 실패는 `EX42_COMMAND_SHARES_RECORD_FAILED`로 표시한다.

깃발 배정 확률과 step 시간 비율은 같다는 보장이 없다. 에피소드 길이 차이 때문에 reset/sample/step을 섞어 읽으면 안 된다. 아직 여기서는 별도 새 허용 오차나 성능 승급 관문을 만들지 않았다.

## CPU 검증

`/home/jay/mai/tmp/verifier-lx/command-shares-1112/`에 원출력을 보존했다.

- `red.log`: 새 소비 모듈이 없어 처음 실패.
- `final.log`: 새 16개 + 기존 stage-zero/E1/E1F/learned-cells 관련 회귀, **44 passed**.
- 실제 MixedVelocityCommand의 reset와 재추출을 호출했다. Isaac CommandTerm 기반 클래스만 CPU 대역이며, 난수·slot·flag state·Runtime·JSON 쓰기는 실제 코드다.
- 답을 아는 입력: 연속 지형 절반 / sparse 절반, flag .15와 나머지 reverse만 지정. 연속 지형만 flag가 되고 자유 표본은 모두 음의 vx, 전체 분모 flag 비율은 연속 분모의 절반. 실제 reset/sample/step 분모와 JSON 일치.
- 기존 E1F 실제 prep 벡터는 flag .10, 합1로 새 검사를 통과한다.
- NaN/Inf/음수/bool/1초과, 키 결측, 선언 결측 preflight, allocator 충돌, 다른 열로 재배정, 빈 분모, rank1 독립 파일, 덮어쓰기 거절, 난수 이어 받기를 검사했다.
- `mutants.json`: 결측 허용·전체 env에 flag 적용·flag 확률0·자유 몫 정규화 삭제·분모 바꿔치기 **5/5 검출**.
- `test_terrain_mark.py::test_runner_writes_the_mark_statistics_into_train_extra`는 변경하지 않은 start_runner.py의 과거 문자열을 찾는 기존 실패다. 이번 변경에 그 파일 수정 없음. 별도 `known-failure.log`, 정상 결과에 합산하지 않음.

## 현재 기동과 남은 경계

PID3290831의 고정 6b8762dd 사본은 이 변경을 자동으로 소비하지 않는다. lead 02:09 결정대로 그 판에서 E1F를 기동하면 안 된다. 재측정의 6b 소스·아홉 입력을 유지하면서, 검토/병합한 새 launch HEAD로 넘기는 다리는 별도 변경한다. 새 HEAD가 없으면 HOLD와 run 알림이어야 한다.

planner #737의 E3 시작 shares.flag는 .10, C 경계 목표가 .15다. 이 PR은 선택된 prep shares의 실제 소비를 구현한다. **C 경계 승인 후 목표 벡터를 materialize하는 연결은 축 순서 PR 후속**이며, 진입 D와 동시에 .15로 올리지 않는다. E2/E5/M/E6a/E6b 완전 벡터가 없는 현재 plan은 해당 단계 진입에서 명시 거절된다. 미정 대각 분할 등을 코드가 추측하지 않는다.

Kit에서의 FlagState/메시 좌표 상호작용, 두 GPU의 실측 몫은 미확인이다. 비연속 지형 전용 명령 정책을 이번 몫 수정으로 완성했다고 주장하지 않는다.
