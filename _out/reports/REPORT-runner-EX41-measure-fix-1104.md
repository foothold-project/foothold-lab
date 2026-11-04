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
- 알림 재전송 조사: 18:22 · 18:40 · 20:28 각 rehearsal run에서 c37a2f9c…가 재생성되어 별도 영수증의 Orca · Telegram 모두 sent였음; 실행 경로를 포함한 이벤트 ID와 rehearsal local_only를 유지하고 전달 계층 자체에서 EX41_ALLOW_EXTERNAL_ALERT_DELIVERY=1 없이는 기본·주입 sender 모두 억제하도록 보강, pytest 전역 기본값은 0; 답 아는 가짜 sender 호출 차단 포함 ops · P3 CPU 시험 32 passed (15.33s).

## P1 retry cap and stance-duration follow-up

- The rehearsal run `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_224727` used four technical failures at update 2. The watcher recorded attempts 1 through 4, wrote `shadow-score-watch/measurement_gaps/model_2_24354393a9fe.json` with `measurement_state=measurement_gap`, `remeasurements_used=3`, `result_eligible=false`, `score_path=null`, and `dr_action=leave_missing_for_dr_hold_missing_evidence`. No score or W72 evidence was produced for that checkpoint. The run configuration retains `pause_budget_updates=0` and `w72_evidence_allowed=false`.
- The short rehearsal had `stand_seconds=1.25` and `stand_skip_seconds=0.25`; production `ex40_score_config.json` remains `3.0` and `1.0`. `ex40_stand_eval.py` uses policy step `dt=0.02`, rounds seconds to integer steps, then rejects if resolved duration differs by more than `dt/2`. A CPU reproduction gives 1.25 seconds -> 62 steps -> 1.24 seconds, with floating difference `0.010000000000000009`, greater than the allowed `0.01`; 3.0 seconds -> 150 steps and is aligned. Therefore the observed missing `stand.json` is consistent with the rehearsal-only duration guard, not an operational duration setting. The environment setup log ending alone does not establish a different runtime exception.
- Rehearsal-only stance timing is now 62 policy steps (1.24 s) with 12 skipped steps (0.24 s), leaving 50 samples. Production settings and evaluation code are unchanged. CPU verification: `test_ex41_short_stage_rehearsal_cpu.py`, 12 passed in 8.57 s. Corrected timing still requires actual Kit confirmation that `stand.json` is emitted.
- The successful P1 receipt after the timing fix is pending. The retry-cap behavior is demonstrated in actual Kit, but one successful full P1 measurement has not yet been verified.

### Actual Kit confirmation

- The corrected rehearsal timing was run through `ex41_eval_once` at GPU1 with the real EX-41 `model_4.pt`, `--scope core`, and priority marker `D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1`. The completed bundle is `D:/mai-tmp/runner/ex41_p1_success_model4/eval_receipt.json`: state `done`, 97.297 seconds, all four child phases `map64`, `stand_eval_gt`, `stand_probe_prop_only`, and `stand_eval_pred` rc 0.
- `stand_eval_gt/stand.json` records `seconds=1.24`, `skip_seconds=0.24`, `dt=0.02`, `envs=64`, and `stand_raw.npz` SHA-256 `0aeaec3eb6a01cdd7d52b10b90e7deead6ef9c7c99bb13a5748bfac894c979a6`; raw shape is 62 by 64 and the post-skip window contains 50 rows. The score-watch collector produced `p1_score_receipt.json` at the same output root with `evaluation_state=complete`, `measurement_state=complete`, iteration 4, and checkpoint SHA `be28492737a5da7af2046b0d76f350dfa3b02bf057042a9d87c9b9c1ea824560`.
- Failure-injection evidence remains at `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261104_224727/shadow-score-watch/measurement_gaps/model_2_24354393a9fe.json`. Four injected technical failures produced a gap after exactly three remeasurements; the score was ineligible and absent, the gap action left evidence missing for the existing DR hold rule, and the watcher advanced to later checkpoints. The run used zero pause-budget updates and excluded rehearsal data from W72 evidence.
- Conclusion: the `stand.json` omission is explained by a rehearsal-only step-alignment rejection, not zero samples and not the operational default. The production values 3.0/1.0 align to 150/50 policy steps at 0.02 s; the rehearsal values are now 1.24/0.24, which align to 62/12 and were confirmed in Kit. The production-length Kit path was not separately run in this unit.
- Final CPU rerun after the timing change: `test_ex41_short_stage_rehearsal_cpu.py` plus `test_ex41_score_watch_cpu.py`, 43 passed in 23.69 s; `git diff --check` passed.
