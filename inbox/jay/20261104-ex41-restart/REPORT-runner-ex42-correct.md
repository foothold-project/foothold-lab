# REPORT-runner-ex42-correct
> 분류: C/운영
> 작성: 오흥재 · 2026-11-05
> 근거: EX41R-INCIDENTS.md I03/I05/I06/I09/I11/I13/I17/I20, EX41-RELAUNCH-GATE.md, 팀장 추가 I24
> 요지: 반복된 EX-41 운영 실수를 시작·평가·큐 경계에서 막고 EX-42 W78 을 분할 재개 가능하게 연결
> 상태: CPU 확인, GPU/Kit 및 45분 실측 미실행

작업 사본: `D:/mai-wt/foothold-lab/runner-ex42-correct`
기준: `81f92f99` (`ex41-measure-fix` 계열)

| 항목 | 구조적 장치 | 답을 아는 입력 시험 | 수정 전 코드에서의 실패 동작 (source replay) |
|---|---|---|---|
| I03 | 250회 숫자 진행 보고는 orchestration 에만 전달 | `test_periodic_numeric_report_is_orchestration_only`: orchestration 1회, Telegram 0회 | 이전 `deliver_pending_alerts` 의 채널 목록은 두 발송기를 모두 호출해 Telegram 에도 숫자 보고를 보냄 |
| I05 | 예행 감시기는 정해진 예행 체크포인트가 끝나면 종료 | `test_rehearsal_watcher_exits_after_scheduled_scores_without_final_request`, `test_score_watch_argv_enables_rehearsal_exit_only_for_rehearsal_manifest` | 이전 종료 전 예행 판정이 없어 최종 요청 없이 watcher 가 polling 상태로 남는 경로가 있었음. 종료 경로는 기존 `81f92f99` 에서 이미 구현되어 회귀 시험으로 유지 |
| I06 | 예행 stage-end 큐를 run 폴더의 `rehearsal-queue/queue.json` 으로 격리 | `test_rehearsal_p2_p3_jobs_register_in_real_dispatch_queue_as_approval_gated`: 운영 큐 불변, 예행 큐만 등록 | 이전 경로는 `EX41_GPU_JOBS_QUEUE` 또는 운영 `D:/mai-tmp/gpu/queue.json` 을 사용 |
| I09 | manifest 에 `model_N.pt` 와 SHA 가 있으면 progress 가 N 에 도달한 시점에 평가 시작 | `test_i09_manifest_model_name_and_sha_is_ready_without_n_plus_one` | 이전 조건 `completed_updates < N+1` 은 저장본 `model_N.pt` 가 있어도 progress=N 에서 digest 대신 `None` 반환 |
| I11 | GPU1 idle 확인 전 P1 표식을 잡지 않고, 대기는 300초로 제한 | `test_i11_push_watcher_waits_outside_marker_then_claims_idle_gpu`, `test_i11_busy_gpu_timeout_never_claims_marker` | 이전 루프는 표식을 먼저 잡고 GPU idle 을 기다려 다른 P1 을 막을 수 있었고 대기 상한은 6시간 |
| I13 | 기존 push250 결과가 회차·체크포인트 SHA 와 일치하고 terminal 상태일 때만 건너뜀 | `test_i13_restart_skips_matching_terminal_result_and_advances`, `test_i13_wrong_result_identity_is_not_silently_skipped` | 이전 코드는 결과 파일이 있으면 `duplicate_prevented` 를 기록하고 rc 5 로 멈춰 이후 회차로 진행하지 않음 |
| I17 | Kit 시작 전 pyflakes 로 시작·감시 핵심 파일의 undefined name 을 검사 | `test_i17_pyflakes_guard_rejects_undefined_name_and_accepts_launch_sources`: 정의 안 된 이름을 넣으면 preflight 거절 | 이전 `train_start.py` 는 undefined-name 사전 검사가 없어 잘못된 이름이 실행 중에야 드러날 수 있었음 |
| I20 | 예행 boundary 와 approvals 를 별도 파일로 강제하고 운영 boundary 지정은 거절 | `test_i20_rehearsal_plan_uses_separate_committed_boundary_and_approval_files`, `test_i20_explicit_production_boundary_is_rejected_for_rehearsal` | 이전 함수는 boundary 경로만 바꾸고 approvals 는 운영 파일을 계속 읽을 수 있었음 |
| I24 | W78 을 3 map mode × 10 terrain cell, 총 30개 P2 항목으로 나눔. 각 항목은 8개 L2/L5 × 각도 조합을 저장하며 SHA·seed·cell·mode 가 맞는 partial 만 이어 읽음. 마지막 merge 는 dispatcher 의 `(priority,id)` 순서상 모든 W78 항목 뒤에 놓임 | `test_w78_mode_case_work_unit_and_resume_contract`, `test_w78_merge_requires_all_30_units_and_builds_canonical_240_grid`, `test_stage_end_queue_items_are_independent_and_prioritized` | 이전에는 W78 240 조합이 단일 `--scope w78_v2` 자식 하나에 묶여 P1 이 그 작업 전체가 끝날 때까지 기다릴 수 있었음 |

I24 의 단위는 한 mode 와 한 case 로 구성되어 각각 8/240 조합입니다. 요청된 45분 상한에 대해 실제 GPU/Kit 시간은 재지 않았고 단위별 강제 timeout 도 두지 않았으므로 시간 보장은 미확인입니다. 각 단위의 partial 재개와 canonical 240 조합 병합은 CPU fixture 로 확인했습니다. Dispatcher 의 동일 우선순위 ID 정렬을 직접 대조해 merge ID 를 `w78-zz-merge` 로 지정했습니다.

검증 명령은 `isaac311/python.exe -m pytest -q -p no:cacheprovider --basetemp=D:/mai-tmp/runner/ex42-correct-final3` 이며 I03/I05/I06/I09/I11/I13/I17/I20/I24 관련 시험 묶음 결과는 `137 passed in 47.90s` 입니다. GPU/Kit/실제 큐 기동은 하지 않았습니다.

수정 전 실패 동작은 각 파일의 기준 소스(`81f92f99`, I05 는 `3ec57aa9` 이전 경로)에서 조건문과 호출 경로를 대조한 source replay 입니다. 이것은 별도 구판 pytest 실행 로그가 아니라 결함 동작을 요약한 것입니다. 고정된 운영 프로세스, 운영 큐, EX-41 실행 사본에는 접근하거나 변경하지 않았습니다.
