# EX-41 measurement retry and stage video queue integration
> Category: experiment record
> Author: Oh Heungjae, runner integration, 2026-11-04
> Evidence: task scope, scripter G11/P9 handoff at `inbox/jay/20261104-video/REPORT-ex41-stage-video-g11-p9.md`, source HEAD `3af5b2057fb138357e6ff656abaeb5d8e2194b24`, RULES-HUB R17/R20, FAILURE-LOG M02/M13
> Summary: Retry technical measurement failures and register independent stage evaluations and one-clip video jobs in the active GPU board queue.
> Status: CPU verified; actual Kit capture and lead scene review not confirmed

## Changes

- Technical evaluator failures or missing outputs retry the same checkpoint. Failed attempt receipts remain preserved and are separated from a judgement HOLD after a completed measurement.
- Stage-end work registers in the active dispatcher queue format `foothold-gpu-queue/1` at `D:/mai-tmp/gpu/queue.json`. `axis_v2`, `w78_v2`, and `push_ladder` are individual P2 evaluation items. A-push video is a separate P3 render item.
- The pinned scripter producer is `foothold_s2.eval.ex41_stage_video.stage_cases()` at HEAD `3af5b2057fb138357e6ff656abaeb5d8e2194b24`. It returns 51 one-clip jobs: W57 39 and W80 12. Runner registers each as a separate P3 render item, using the exact source-reported suite, case, and mode.
- Video output and per-job receipts use `D:/mai-tmp/runner/ex41_stage_video/model_<iteration>_<sha>`. Completion receipts verify checkpoint SHA, source HEAD, v3.4-D168, and the output video SHA. The result stays `captured_pending_lead_kit_scene_review` until lead scene review.
- The push250 watcher records measurement HOLDs and advances to the next interval. The a_push_video command is validated through its real argparse parser.

## Verification

- Answer-known CPU suite: `79 passed in 20.27s` using isaac311 and `D:/mai-tmp/runner/test-gpu-manager-rerun`. It registered 55 items through the real `gpu_jobs.py queue_cmd` into a temporary `foothold-gpu-queue/1` file. `git diff --check` and targeted `compileall` passed.
- The scripter G11/P9 consumer `--plan-only` ran with EX-41 `model_750.pt`, manifest SHA `575655db49e475e171c0a85a859ae4d261cac83814aee2a18be76d6711558e46`, W57 `fwd0.5`, and `eval_gt`. It returned `state=planned`, source HEAD `3af5b2057fb138357e6ff656abaeb5d8e2194b24`, and a 150-frame plan. This is plan-only evidence, not a Kit capture.
- The latest read-only GPU1 check showed no `PRIORITY_BUSY_GPU1` marker and no live P1 process among the previously reported PIDs. The active dispatcher queue had C76 item 151 in `실행`, priority 3 render; its recorder process PID 95772 was visible on GPU1. GPU1 memory was 8887 MiB of 16303 MiB. No runner capture was started while another render was active. Kit capture, full-frame review, and lead scene acceptance remain unconfirmed.
- The scripter report separately says Kit and lead scene review are pending at the P1 gate. No acceptance is inferred from plan-only results.
- D177 command-share change was not prepared. The live W72 `BOUNDS` and `BOOLS` have no command-share field, and `validate_change()` rejects unsupported leaves.
- Ruff is not installed in isaac311, so lint was not run.

## Modified files in this follow-up

- `foothold_s2/ex41_score_watch.py`
- `foothold_s2/tests/test_ex41_eval_schedule_cpu.py`
- `_out/reports/REPORT-runner-EX41-measure-fix-1104.md`

The initial implementation files are preserved in the preceding commit `a48ac12bb6e88c3ba546c61cc013433976ddb45a`.
- Alert 재발 원인 확인: 2026-11-04 18:22 · 18:40 예행과 20:28 재시도 폴더마다 c37a2f9c…가 새 행으로 생성되고 별도 영수증의 Orca · Telegram 모두 sent였음; 실패 이벤트 ID를 실행 폴더별로 나누고 rehearsal 실패는 local_only, pytest 기본 발송은 닫힘으로 변경함; ops · startup 통합 시험 55 passed, 앞선 ops · P3 묶음의 mirror 시험 1건은 단독 재현에서도 실패해 별도 기존 막음으로 남음.
