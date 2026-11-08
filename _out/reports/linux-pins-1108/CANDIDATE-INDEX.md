> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst · 2026-11-08
> 근거: scan.py · 파일별 SHA256은 inventory.json
> 요지: 검색에 걸린 모든 파일과 물리 줄 번호. 결함 판정은 본 보고서
> 상태: 문자열 후보 목록 · 주석과 시험의 거짓 양성 포함

# Windows 종속 후보 파일 전체 목록

S는 고정 foothold_s2, O는 운영 tools, ML·MH는 메시지 도구다. 각 행의 runtime/config는 확장자·위치 분류이며 실행 도달성을 뜻하지 않는다. 모든 역슬래시는 넓게 검색했으므로 정규식·문자열 이스케이프도 포함한다.

| 파일 | 역할 | 일치 줄 | 검색 범주 |
|---|---|---|---|
| MH/TASK-super2-tool-ab-20261027.md | doc | 14 | drive, separator |
| MH/edit_agenda_0422.py | runtime/config | 14 | line_encoding, separator |
| MH/edit_agenda_0512.py | runtime/config | 6, 9, 13 | drive, line_encoding, separator |
| MH/edit_agenda_1019.py | runtime/config | 10, 17 | drive, line_encoding, separator |
| MH/edit_hub_0027.py | runtime/config | 9, 15, 19, 21 | drive, line_encoding, separator |
| MH/edit_hub_0045.py | runtime/config | 6, 8, 10, 15, 17 | drive, line_encoding, separator |
| MH/edit_hub_0118.py | runtime/config | 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 24, 31, 33 | drive, line_encoding, separator |
| MH/edit_hub_0125.py | runtime/config | 7, 26, 32, 35, 40, 55, 59 | drive, gpu, line_encoding, separator |
| MH/edit_hub_0216.py | runtime/config | 7, 9 | line_encoding, separator |
| MH/edit_hub_0352.py | runtime/config | 7, 9 | line_encoding, separator |
| MH/edit_hub_1006.py | runtime/config | 7, 9 | line_encoding, separator |
| MH/inbox_wait.py | runtime/config | 59 | separator |
| MH/msgs_0120.py | runtime/config | 2, 10 | drive, gpu |
| MH/msgs_0155.py | runtime/config | 2, 11, 12 | drive, gpu, separator |
| MH/msgs_0215.py | runtime/config | 2, 7 | drive, gpu |
| MH/orch_wait.py | runtime/config | 24 | separator |
| ML/inbox_wait.py | runtime/config | 37 | separator |
| O/ex41/boundary_report.py | runtime/config | 13 | drive |
| O/ex41/fixtures/fixture-done-missing.tsv | test | 2 | drive, separator |
| O/ex41/launch_ex41r.ps1 | runtime/config | 2, 7, 8, 13, 16, 19, 21, 22, 26, 27, 28 | drive, exe, gpu, permissions, shell, winenv_binary |
| O/ex41/lead_rounds.py | runtime/config | 20, 27, 28, 29, 30, 35, 64, 82, 83, 86, 94, 96, 117, 123 | drive, line_encoding, separator |
| O/ex41/lock_checkout.py | runtime/config | 31, 33, 39 | permissions |
| O/ex41/ops_check.py | runtime/config | 4, 23, 25, 26, 116, 118, 130, 164, 165, 168, 256, 271, 291, 319 | casefold, drive, separator |
| O/ex41/test_ops_check.py | test | 11, 12, 22, 23, 24, 26, 28, 125, 126, 127, 128, 143, 144, 154, 165, 166, 243, 244 | drive, line_encoding, msys, separator |
| O/ex41/tg_send.py | runtime/config | 17, 18, 23, 34, 38 | drive, line_encoding, separator, shell, winenv_binary |
| O/gpu_jobs/README-W28.md | doc | 15, 17, 18, 19, 20, 21, 24, 29, 31, 36 | drive, exe, gpu, shell |
| O/gpu_jobs/dispatch.py | runtime/config | 45, 55, 58, 59, 60, 64, 70, 78, 154, 223, 228, 229, 231, 233, 236, 237, 240, 244, 253, 290, 300, 310, 398, 740, 772, 779, 788, 792, 806, 807, 812, 1089, 1097, 1098, 1125, 1148, 1152, 1153, 1174, 1175, 1176, 1177, 1178, 1181, 1368, 1369, 1376, 1381, 1403, 1407, 1433, 1467, 1610 | casefold, drive, exe, line_encoding, lock, separator, shell, winapi |
| O/gpu_jobs/gpu_jobs.py | runtime/config | 18, 57 | line_encoding |
| O/gpu_jobs/jobs.json | runtime/config | 3, 5, 6, 7 | drive |
| O/gpu_jobs/queue_w28.py | runtime/config | 27, 30, 31, 32, 33, 34, 35, 36, 49, 50, 58, 66, 68, 69, 73, 79, 88, 176, 177, 179, 187, 191, 197, 202, 205, 208, 219, 252, 328, 329, 331, 403, 419, 426 | casefold, exe, gpu, line_encoding, lock, separator, winapi |
| O/gpu_jobs/test_dispatch.py | test | 14, 102, 117, 125, 133, 142, 145, 180, 187, 192, 193, 194, 195, 220, 245, 246, 273, 339, 377, 398, 410, 420, 422, 442, 461, 462, 519, 520, 521, 541, 542, 543, 544, 545, 547, 557, 558, 559, 571, 653, 720, 736, 830, 833, 933, 939 | drive, exe, gpu, msys, separator, winapi |
| O/gpu_jobs/test_queue_w28.py | test | 115, 123, 136, 140, 141, 142, 172, 173, 174, 176, 177, 180, 181, 187 | drive, exe, gpu, separator |
| O/gpu_jobs/video_finish_w28.py | runtime/config | 42, 43, 80 | line_encoding, separator |
| S/foothold_s2/HANDOFF-S1.md | doc | 39, 54, 60, 66, 71 | drive, gpu |
| S/foothold_s2/basic_gait_chain_plan.py | runtime/config | 14, 63 | drive, exe, separator |
| S/foothold_s2/basic_gait_eval_chain_v3.py | runtime/config | 53, 58, 113 | gpu, separator |
| S/foothold_s2/basic_gait_eval_once.py | runtime/config | 57, 61, 75, 81 | drive, exe, gpu, separator |
| S/foothold_s2/basic_gait_ex38_continue.py | runtime/config | 80, 88 | gpu, separator |
| S/foothold_s2/basic_gait_ex39.py | runtime/config | 65, 78 | gpu, separator |
| S/foothold_s2/basic_gait_extend_eval.py | runtime/config | 76, 122 | gpu |
| S/foothold_s2/basic_gait_extend_launch.py | runtime/config | 91, 115 | gpu, separator |
| S/foothold_s2/basic_gait_kit.py | runtime/config | 3 | drive |
| S/foothold_s2/basic_gait_launch.py | runtime/config | 21, 38, 158, 159 | drive, gpu, separator |
| S/foothold_s2/basic_gait_run.py | runtime/config | 43 | separator |
| S/foothold_s2/chain/chain.service | runtime/config | 12 | separator |
| S/foothold_s2/chain/chain_s1a_night.yaml | runtime/config | 11, 12, 13, 14, 16, 17 | drive, exe |
| S/foothold_s2/chain/runner.py | runtime/config | 7, 10, 26, 27, 28, 31, 32, 50, 89, 97, 99, 101, 110, 112, 134, 139, 177, 178, 179, 185, 186, 187, 285, 296, 322, 454, 461, 463, 665, 883, 885, 886 | drive, exe, gpu, permissions, separator, shell, winapi, winenv_binary |
| S/foothold_s2/chain/snapshot.py | runtime/config | 37 | separator |
| S/foothold_s2/chain/stamp.py | runtime/config | 25, 41, 46, 68 | line_encoding, separator |
| S/foothold_s2/chain/start.py | runtime/config | 5, 30, 34, 40, 42 | exe, permissions, separator, winapi |
| S/foothold_s2/chain/wrap.py | runtime/config | 18, 23, 28, 35 | separator, winenv_binary |
| S/foothold_s2/curriculum/continuous.py | runtime/config | 42, 53, 345, 592 | line_encoding, separator |
| S/foothold_s2/curriculum/ex40.yaml | runtime/config | 12 | drive |
| S/foothold_s2/curriculum/ex40_dr.py | runtime/config | 24 | drive |
| S/foothold_s2/curriculum/ex40_score_config.json | runtime/config | 4 | gpu |
| S/foothold_s2/curriculum/ex41-push-m6000-baseline.json | runtime/config | 75 | gpu |
| S/foothold_s2/curriculum/ex41.py | runtime/config | 77, 286, 410, 415 | line_encoding, separator |
| S/foothold_s2/curriculum/ex41_fixed.py | runtime/config | 82, 127, 158, 289, 322, 353 | line_encoding, separator |
| S/foothold_s2/curriculum/ex41_scoring.py | runtime/config | 32, 50, 120 | line_encoding, separator |
| S/foothold_s2/curriculum/ex42_manifest.py | runtime/config | 80, 89, 94, 95, 136, 186 | gpu |
| S/foothold_s2/curriculum/ex42_prep.py | runtime/config | 38, 140, 319, 412 | line_encoding, separator |
| S/foothold_s2/curriculum/ex42_runtime.py | runtime/config | 65, 104, 193 | gpu, line_encoding |
| S/foothold_s2/curriculum/w72.py | runtime/config | 67 | line_encoding |
| S/foothold_s2/deploy/export_ex40_w89.py | runtime/config | 107 | separator |
| S/foothold_s2/deploy/record_isaac.py | runtime/config | 4 | gpu |
| S/foothold_s2/deploy/verify_ex40_w89.py | runtime/config | 153 | separator |
| S/foothold_s2/diag_blowup.py | runtime/config | 3, 18 | drive, gpu |
| S/foothold_s2/eval/HANDOFF.md | doc | 12, 18, 33, 47, 51 | drive, gpu |
| S/foothold_s2/eval/a_push_video.py | runtime/config | 122, 130, 131, 158, 207, 238, 239, 264, 266, 416 | gpu, line_encoding, separator |
| S/foothold_s2/eval/adapters.py | runtime/config | 100, 265 | gpu |
| S/foothold_s2/eval/axis2_run.py | runtime/config | 62 | separator |
| S/foothold_s2/eval/baseline_b1500.sh | runtime/config | 11, 19 | drive, line_encoding, separator |
| S/foothold_s2/eval/c_layer_progress.py | runtime/config | 55, 56 | separator |
| S/foothold_s2/eval/c_layer_queue.py | runtime/config | 27, 36, 43, 45, 49, 50, 113, 114, 183, 184, 353, 553 | drive, gpu, line_encoding, separator |
| S/foothold_s2/eval/c_layer_segmentation.py | runtime/config | 63, 91 | separator |
| S/foothold_s2/eval/calf_band.py | runtime/config | 29, 135, 160 | casefold, separator |
| S/foothold_s2/eval/compare.py | runtime/config | 44, 50, 121, 125 | separator |
| S/foothold_s2/eval/compare_map_modes.py | runtime/config | 92, 115 | separator |
| S/foothold_s2/eval/diag_actdist.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/diag_cmd_response.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/diag_fbg.py | runtime/config | 3, 38 | gpu, winenv_binary |
| S/foothold_s2/eval/diag_fbg2.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/diag_feet.py | runtime/config | 3, 50, 53 | gpu, winenv_binary |
| S/foothold_s2/eval/diag_pd.py | runtime/config | 3, 40 | gpu, winenv_binary |
| S/foothold_s2/eval/diag_rewards.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/diag_s1a.py | runtime/config | 3, 52 | gpu, winenv_binary |
| S/foothold_s2/eval/diag_s2_adapter.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/diag_s2_faithful.py | runtime/config | 4 | gpu |
| S/foothold_s2/eval/diag_z_action.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/eval_map_modes.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/ex35_eval_chain.sh | runtime/config | 11, 12, 20, 22, 58, 59, 60, 63 | drive, exe, line_encoding, msys, separator, shell, winapi |
| S/foothold_s2/eval/ex35_eval_chain2.sh | runtime/config | 16, 17, 27, 29, 60, 73, 74, 75, 82, 85, 91, 110, 140 | drive, exe, line_encoding, msys, separator, shell, winapi |
| S/foothold_s2/eval/ex35_priority_marker.py | runtime/config | 16, 17, 21, 22, 45, 60, 64, 75 | drive, exe, gpu, separator, shell, winapi |
| S/foothold_s2/eval/ex35_terrain_report.py | runtime/config | 52 | separator |
| S/foothold_s2/eval/ex35_window_judge.py | runtime/config | 30, 31, 52, 709, 902 | drive, gpu, separator |
| S/foothold_s2/eval/ex40_stand_eval.py | runtime/config | 235 | separator |
| S/foothold_s2/eval/ex40_v3_recompose.py | runtime/config | 150 | separator |
| S/foothold_s2/eval/ex41_d48_gate.py | runtime/config | 35, 42 | casefold |
| S/foothold_s2/eval/ex41_gpu_priority.py | runtime/config | 42, 59, 71, 75, 203 | casefold, gpu, separator |
| S/foothold_s2/eval/ex41_push250_watch.py | runtime/config | 33, 34, 35, 36, 37, 38, 44, 45, 47, 53, 54, 68, 149, 154, 156, 177, 188, 189, 194, 197, 198, 200, 257, 261, 268, 370, 371, 372, 375, 386, 390 | casefold, exe, gpu, line_encoding, separator, winapi |
| S/foothold_s2/eval/ex41_push_ladder.py | runtime/config | 416 | separator |
| S/foothold_s2/eval/ex41_push_ladder_bundle.py | runtime/config | 53, 107, 134, 135, 136, 145, 148, 169, 181, 190 | gpu, line_encoding, separator, winapi |
| S/foothold_s2/eval/ex41_stage_video.py | runtime/config | 80, 90, 91, 225, 236, 237, 336 | casefold, gpu, line_encoding, separator |
| S/foothold_s2/eval/ex41_turn_receipt.py | runtime/config | 128, 138, 155 | gpu, separator |
| S/foothold_s2/eval/ex41_w78_merge.py | runtime/config | 79 | separator |
| S/foothold_s2/eval/ex41_w78_video_request.py | runtime/config | 21, 44, 68, 97 | line_encoding, separator |
| S/foothold_s2/eval/ex42_component_receipts.py | runtime/config | 34 | separator |
| S/foothold_s2/eval/ex42_terrain_evidence.py | runtime/config | 46 | line_encoding |
| S/foothold_s2/eval/ex42_video_delivery.py | runtime/config | 99 | line_encoding |
| S/foothold_s2/eval/ex42_video_sample.py | runtime/config | 19, 20, 38 | line_encoding, separator |
| S/foothold_s2/eval/ex42_w78_gate.py | runtime/config | 184 | line_encoding |
| S/foothold_s2/eval/judge_repro.py | runtime/config | 21, 22, 23, 24, 118, 128 | drive, line_encoding, separator |
| S/foothold_s2/eval/judge_stats.py | runtime/config | 276 | separator |
| S/foothold_s2/eval/limit_dwell.py | runtime/config | 88, 108 | separator |
| S/foothold_s2/eval/manifest.py | runtime/config | 36, 42, 100, 101, 108, 134, 145 | line_encoding, separator |
| S/foothold_s2/eval/map_error.py | runtime/config | 195 | separator |
| S/foothold_s2/eval/n21_dr_record.py | runtime/config | 99, 111 | line_encoding, separator |
| S/foothold_s2/eval/plan_c_layer.py | runtime/config | 55, 56, 129 | gpu |
| S/foothold_s2/eval/post_train_eval.sh | runtime/config | 20, 35 | line_encoding, separator |
| S/foothold_s2/eval/post_train_eval2.sh | runtime/config | 6, 27, 51 | exe, line_encoding, separator, shell, winapi |
| S/foothold_s2/eval/record_clip.py | runtime/config | 4, 7, 63, 93, 94, 95 | drive, gpu, winenv_binary |
| S/foothold_s2/eval/repro_check.py | runtime/config | 21, 25, 53 | drive, separator |
| S/foothold_s2/eval/run_eval.py | runtime/config | 9, 92, 222, 244, 252, 262 | gpu, winenv_binary |
| S/foothold_s2/eval/run_fwd_then_left.sh | runtime/config | 8, 10, 20 | drive, separator |
| S/foothold_s2/eval/run_g0b_eval.sh | runtime/config | 6, 17, 21 | permissions, separator |
| S/foothold_s2/eval/run_kit.sh | runtime/config | 3, 6, 7, 10, 15 | exe, gpu, msys, separator |
| S/foothold_s2/eval/run_sb_eval.sh | runtime/config | 8, 27, 32 | permissions, separator |
| S/foothold_s2/eval/run_sparse_eval.sh | runtime/config | 28 | separator |
| S/foothold_s2/eval/runtime.py | runtime/config | 136 | separator |
| S/foothold_s2/eval/s0_chain.py | runtime/config | 29, 31, 32, 44, 45, 47, 154, 182, 186, 194, 242 | drive, exe, separator, winapi |
| S/foothold_s2/eval/s0_tables.py | runtime/config | 95 | separator |
| S/foothold_s2/eval/seq_video.sh | runtime/config | 12, 13, 14, 15, 16 | drive, exe, gpu, msys, separator |
| S/foothold_s2/eval/smoke_sparse_start.sh | runtime/config | 10, 12 | separator |
| S/foothold_s2/eval/tests/test_axis3_starts.py | test | 152 | drive |
| S/foothold_s2/eval/tests/test_ex41_push250_cpu.py | test | 199, 202, 203, 207, 208, 210, 226, 233, 234, 235 | exe, gpu |
| S/foothold_s2/eval/tests/test_ex41_push_ladder_bundle_cpu.py | test | 14, 32, 34, 53, 55, 56, 60, 99, 110, 114, 128, 157, 160 | drive, exe, gpu, line_encoding, separator |
| S/foothold_s2/eval/tests/test_four_foot_start.py | test | 118, 119 | drive |
| S/foothold_s2/eval/tests/test_gate_judge.py | test | 79, 82, 83 | line_encoding, separator |
| S/foothold_s2/eval/tests/test_imports.py | test | 78, 83 | separator |
| S/foothold_s2/eval/tests/test_outputs.py | test | 8, 24 | separator |
| S/foothold_s2/eval/tests/test_s0_chain.py | test | 57, 58, 72 | casefold, exe, winenv_binary |
| S/foothold_s2/eval/tests/test_seq_video.py | test | 136 | drive, exe |
| S/foothold_s2/eval/tests/test_w78_video_consumer_cpu.py | test | 54, 55, 56, 57, 58, 59, 61, 62, 64, 118, 140, 144, 146, 151, 155, 157, 158, 159, 161, 162, 187, 210 | drive, exe, gpu, separator |
| S/foothold_s2/eval/turn_probe.py | runtime/config | 3 | gpu |
| S/foothold_s2/eval/turn_probe_logic.py | runtime/config | 34, 36 | line_encoding, separator |
| S/foothold_s2/eval/turn_probe_plan.py | runtime/config | 62 | casefold |
| S/foothold_s2/eval/video25/compose_25e_v2style10.py | runtime/config | 62, 65, 879 | drive, line_encoding, separator |
| S/foothold_s2/eval/video25/compose_25e_v2style9.py | runtime/config | 46, 49, 666 | drive, line_encoding, separator |
| S/foothold_s2/eval/video25/push_event_overlay.py | runtime/config | 127 | line_encoding |
| S/foothold_s2/eval/video25/record_25e_x28.py | runtime/config | 57, 72, 78, 640, 653, 682, 686, 704, 1269, 1270 | casefold, drive, separator |
| S/foothold_s2/eval/video25/record_25e_x30.py | runtime/config | 69, 84, 93, 701, 714, 743, 747, 765, 1344, 1345 | casefold, drive, separator |
| S/foothold_s2/eval/video25/record_25e_x31.py | runtime/config | 100, 115, 132, 141, 400, 792, 803, 816, 845, 849, 867, 1456, 1457 | casefold, drive, separator |
| S/foothold_s2/eval/video25/record_c_layer.py | runtime/config | 170, 185, 202, 211, 503, 1020, 1031, 1044, 1089, 1093, 1122, 1827 | casefold, drive, separator |
| S/foothold_s2/eval/video_combine_check.py | runtime/config | 36, 112 | drive, line_encoding |
| S/foothold_s2/eval/video_style.py | runtime/config | 107, 173, 306 | casefold, separator |
| S/foothold_s2/eval/w57_checkpoint_hash.py | runtime/config | 38 | separator |
| S/foothold_s2/eval/w78_video_consumer.py | runtime/config | 31, 32, 53, 70, 91, 125, 154, 165, 166, 186, 257, 258, 328, 372 | casefold, gpu, line_encoding, separator |
| S/foothold_s2/ex3031_smoke_contract.py | runtime/config | 16 | drive |
| S/foothold_s2/ex3031_window1_contract.py | runtime/config | 20, 21 | gpu |
| S/foothold_s2/ex3031_window2_contract.py | runtime/config | 19 | gpu |
| S/foothold_s2/ex35_launch.py | runtime/config | 133, 134 | line_encoding, separator |
| S/foothold_s2/ex39_kit_smoke.py | runtime/config | 26, 27, 28, 41, 91, 161, 162, 163, 164, 165, 200, 201, 204, 250, 251, 252, 253, 282, 283, 284 | casefold, drive, exe, gpu, line_encoding, separator |
| S/foothold_s2/ex39_smoke_args.py | runtime/config | 26 | line_encoding |
| S/foothold_s2/ex40_artifacts.py | runtime/config | 15, 66, 72, 82, 84 | casefold, line_encoding |
| S/foothold_s2/ex40_b13_probe.py | runtime/config | 23, 24, 40, 51, 56, 63, 64, 76, 80, 102, 109, 110, 111, 112, 113, 114, 128, 130, 150 | gpu, line_encoding, separator |
| S/foothold_s2/ex40_continue.py | runtime/config | 58, 65, 70, 212, 215, 237 | casefold, line_encoding, separator |
| S/foothold_s2/ex40_eval_once.py | runtime/config | 24, 31, 32, 34, 39, 60, 62, 68, 103, 122, 134 | drive, exe, gpu, separator, winapi |
| S/foothold_s2/ex40_kit_smoke.py | runtime/config | 104, 106, 367, 382, 395, 441 | casefold, line_encoding |
| S/foothold_s2/ex40_launch.py | runtime/config | 24, 40, 41, 108, 110, 136, 154, 169 | drive, gpu, line_encoding, separator |
| S/foothold_s2/ex40_score.py | runtime/config | 30, 32, 74, 115, 255 | gpu, line_encoding |
| S/foothold_s2/ex40_score_smoke.py | runtime/config | 14, 15, 16, 52 | line_encoding, separator |
| S/foothold_s2/ex40_score_watch.py | runtime/config | 27, 33, 58, 97, 115, 125, 145, 146, 151, 152, 155, 268, 313, 324, 371, 381, 411, 425, 430, 432, 435, 460, 476, 481, 506 | drive, gpu, line_encoding, separator, winapi |
| S/foothold_s2/ex40_stage_publish.py | runtime/config | 70, 84, 186, 200, 201, 207, 210, 269, 270, 273, 274, 275, 277 | line_encoding, separator, winapi |
| S/foothold_s2/ex40_stage_report.py | runtime/config | 36, 110, 254 | line_encoding, separator |
| S/foothold_s2/ex40_supervisor.py | runtime/config | 31, 75, 118, 135, 151, 164, 175, 183, 206, 232, 347, 368, 389, 396, 403, 425, 459, 462, 491, 538, 550, 561 | gpu, line_encoding, separator |
| S/foothold_s2/ex40_w57_retry.py | runtime/config | 24, 33, 39, 67, 78, 79, 80, 81, 86, 90, 124, 196 | gpu, line_encoding, separator, winapi |
| S/foothold_s2/ex41_eval_once.py | runtime/config | 63, 67, 74, 114, 123, 172, 192, 202, 335, 336, 337, 377, 391, 392, 426 | gpu, line_encoding, separator, winapi |
| S/foothold_s2/ex41_ops.py | runtime/config | 17, 78, 80, 121, 122, 224, 452, 454, 456 | line_encoding, separator |
| S/foothold_s2/ex41_score_watch.py | runtime/config | 34, 44, 165, 422, 424, 567, 569, 887, 1099, 1102, 1103, 1688 | gpu, line_encoding, separator |
| S/foothold_s2/ex41_start_preflight.py | runtime/config | 75, 85, 178, 179 | gpu, line_encoding, separator |
| S/foothold_s2/ex42_chain.py | runtime/config | 29, 30, 291, 364, 368, 401, 403 | line_encoding, separator |
| S/foothold_s2/ex42_gate_checks.py | runtime/config | 15, 69, 76, 82, 116, 144, 149, 263, 264 | casefold, line_encoding, permissions, separator |
| S/foothold_s2/ex42_score_watch.py | runtime/config | 17 | line_encoding |
| S/foothold_s2/experiment_registry.py | runtime/config | 12, 24, 25, 26, 34, 51, 52, 71, 79, 129, 142, 144 | gpu, line_encoding, separator |
| S/foothold_s2/launch_ex3031_window1.py | runtime/config | 6, 29, 31, 59, 60, 71, 86 | casefold, drive, exe, separator, winapi |
| S/foothold_s2/machine_profile.py | runtime/config | 12, 26, 38, 48, 52, 74, 75, 115, 116 | line_encoding, separator, winapi |
| S/foothold_s2/models/HANDOFF-RL.md | doc | 33 | line_encoding, separator |
| S/foothold_s2/prestart_check.py | runtime/config | 78, 79 | line_encoding, separator |
| S/foothold_s2/rewards/mgdp_rewards.md | doc | 11, 13 | separator |
| S/foothold_s2/rewards/nvidia_go2_rewards.py | runtime/config | 3, 6 | drive |
| S/foothold_s2/rewards/w86_runtime.py | runtime/config | 47, 193, 338, 372 | separator |
| S/foothold_s2/run_axis_v2.sh | runtime/config | 13, 17, 23, 24, 25, 30, 31, 32, 33, 34, 35, 37 | drive, exe, gpu, msys, separator |
| S/foothold_s2/run_basic_gait.sh | runtime/config | 3, 8, 15, 16, 17, 18, 19, 26, 35, 36, 37, 39, 41 | drive, exe, gpu, line_encoding, msys, separator |
| S/foothold_s2/run_basic_gait_extend.sh | runtime/config | 5, 12, 13, 14, 15, 16, 18, 33, 36 | drive, exe, gpu, line_encoding, msys, separator |
| S/foothold_s2/run_eval_g0_reference.sh | runtime/config | 6, 7, 8, 9, 18 | drive, exe, gpu, msys, separator |
| S/foothold_s2/run_eval_map_modes.sh | runtime/config | 6, 7, 8, 9, 18 | drive, exe, gpu, msys, separator |
| S/foothold_s2/run_eval_window1.sh | runtime/config | 9, 17 | drive, exe, msys |
| S/foothold_s2/run_ex3031_smoke.sh | runtime/config | 3, 6, 7, 8, 17, 23 | exe, gpu, msys, permissions, separator |
| S/foothold_s2/run_ex3031_window1.sh | runtime/config | 3, 6, 7, 8, 14 | exe, gpu, msys, separator |
| S/foothold_s2/run_ex3031_window2.sh | runtime/config | 3, 6, 7, 8, 14 | exe, gpu, msys, separator |
| S/foothold_s2/run_ex35.sh | runtime/config | 8, 9, 10, 20, 22, 26, 27, 29, 30, 32 | exe, gpu, line_encoding, msys, separator |
| S/foothold_s2/run_ex35_chained.sh | runtime/config | 4, 8, 9, 10, 11, 16, 20, 21, 32, 34, 38, 39, 41, 42, 54, 67, 81, 92, 98, 101 | drive, exe, gpu, line_encoding, msys, separator, shell, winapi |
| S/foothold_s2/run_ex38_continue.sh | runtime/config | 4, 10, 11, 12, 13, 14, 23 | exe, gpu, line_encoding, msys, separator |
| S/foothold_s2/run_ex39.sh | runtime/config | 5, 15, 16, 17, 18, 19, 41 | exe, gpu, line_encoding, msys, separator |
| S/foothold_s2/run_ex40.sh | runtime/config | 5, 12, 13, 14, 15, 16, 42 | exe, gpu, line_encoding, msys, separator |
| S/foothold_s2/run_ex40_b11.sh | runtime/config | 5, 12, 13, 14, 15, 16, 45, 59, 63, 64, 65, 66, 67, 68, 69 | drive, exe, gpu, line_encoding, msys, separator |
| S/foothold_s2/run_s1.sh | runtime/config | 3, 4, 9, 10, 11, 19 | exe, gpu, msys, separator |
| S/foothold_s2/run_s1_diag.sh | runtime/config | 3, 6, 7, 8, 16 | exe, gpu, msys, separator |
| S/foothold_s2/run_s1_v11.sh | runtime/config | 7, 9, 10, 11, 19 | exe, gpu, msys, separator |
| S/foothold_s2/run_s1b.sh | runtime/config | 10, 11, 12, 32 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_diag.sh | runtime/config | 6, 7, 8, 16 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x11.sh | runtime/config | 14, 15, 16, 24 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x13.sh | runtime/config | 14, 15, 16, 24 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x15.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x16.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x16n.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x17.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x18.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x19.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x20.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x21.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x22.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x23.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x24.sh | runtime/config | 8, 9, 10, 18 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x24a.sh | runtime/config | 7, 8, 9, 17 | exe, gpu, msys, separator |
| S/foothold_s2/run_s2_x26.sh | runtime/config | 7, 8, 9, 18 | exe, gpu, msys, separator |
| S/foothold_s2/run_sb.sh | runtime/config | 9, 10, 11, 29, 30, 31 | exe, gpu, msys, separator |
| S/foothold_s2/run_terrain_skill.sh | runtime/config | 13, 17, 23, 24, 25, 30, 31, 32, 33, 34, 35, 37 | drive, exe, gpu, msys, separator |
| S/foothold_s2/run_turn_probe.sh | runtime/config | 6, 9, 10, 11, 23 | drive, exe, gpu, msys, separator |
| S/foothold_s2/runners/action_stats.py | runtime/config | 56, 67, 83 | exe |
| S/foothold_s2/runners/devices.py | runtime/config | 4 | gpu |
| S/foothold_s2/runners/manifest.py | runtime/config | 22, 35, 95, 129, 224, 264, 265 | casefold, gpu, line_encoding, winapi |
| S/foothold_s2/runners/map_stats.py | runtime/config | 97 | separator |
| S/foothold_s2/runners/reward_split.py | runtime/config | 213, 266, 284, 298 | winenv_binary |
| S/foothold_s2/runners/sol23f_runner.py | runtime/config | 150 | separator |
| S/foothold_s2/runners/stage_transfer.py | runtime/config | 117 | casefold |
| S/foothold_s2/runners/start_runner.py | runtime/config | 437, 757, 879, 902, 1202, 1206, 1375 | casefold, gpu, separator |
| S/foothold_s2/scripts/compare_curves.py | runtime/config | 24 | line_encoding, separator |
| S/foothold_s2/scripts/ex41_resume.py | runtime/config | 65, 70, 344, 364, 414 | casefold, line_encoding, separator |
| S/foothold_s2/scripts/ex41_startup.py | runtime/config | 44, 65, 103, 121, 176, 181, 184, 244, 257, 298, 300, 390, 432, 500, 548, 553, 554, 610, 614, 615, 625, 626, 628, 632, 640, 641, 661, 677, 680, 749, 789, 857, 868, 892, 953, 1338, 1391, 1406, 1413, 1460 | casefold, drive_guard, gpu, line_encoding, separator, winapi |
| S/foothold_s2/scripts/ex42_env_probe.py | runtime/config | 3, 38, 46, 47, 56, 69, 184 | gpu, separator |
| S/foothold_s2/scripts/ex42_judgment_notice.py | runtime/config | 12, 16, 93 | separator |
| S/foothold_s2/scripts/ex42_kit_probe.py | runtime/config | 30, 40, 52, 58, 59, 133 | gpu, separator |
| S/foothold_s2/scripts/ex42_manifest_build.py | runtime/config | 24 | separator |
| S/foothold_s2/scripts/ex42_ops.py | runtime/config | 12, 92, 96, 137, 138 | gpu, separator |
| S/foothold_s2/scripts/ex42_training_entry.py | runtime/config | 26, 50, 52, 107, 113 | gpu, line_encoding, separator |
| S/foothold_s2/scripts/make_ex41_playlists.py | runtime/config | 12, 19, 32, 58 | drive, line_encoding, separator |
| S/foothold_s2/scripts/start_gate.py | runtime/config | 9, 137, 194 | drive, gpu, winenv_binary |
| S/foothold_s2/scripts/start_gate_restore_result_20261020_1142.json | historical-result | 4 | drive |
| S/foothold_s2/scripts/start_gate_restore_result_20261020_1313.json | historical-result | 4 | drive |
| S/foothold_s2/scripts/start_gate_result_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_gate_result_20261020_1141.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_gate_result_20261020_1313.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_measure_s2.py | runtime/config | 8, 34, 59 | drive, gpu, separator |
| S/foothold_s2/scripts/start_mem3_1536_mb256_a1_20261020.json | historical-result | 5, 41 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_mem3_1536_mb256_a2_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem3_1536_mb256_a3_20261020.json | historical-result | 5, 41 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_mem3_3072_mb128_a1_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem3_3072_mb128_a2_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem3_3072_mb128_a3_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem4_1536_mb128_a3_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem4_1536_mb256_a3_bf16_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem4_3072_mb128_a3_bf16_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem4_3072_mb256_a3_bf16_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem_1536_mb256_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem_3072_mb128_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem_3072_mb256_20261020.json | historical-result | 5, 40 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_mem_3072_mb64_20261020.json | historical-result | 5 | gpu |
| S/foothold_s2/scripts/start_mem_3072_mb768_20261020.json | historical-result | 5, 41 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_s2m_G0_3072_fp32_mb256_20261020.json | historical-result | 11, 12, 15, 27, 28, 40, 41, 43, 44 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_s2m_G1_1536_bf16kl_mb256_20261020.json | historical-result | 11, 12, 15, 27, 28, 40, 41, 43, 44 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_s2m_G1_3072_bf16kl_mb128_20261020.json | historical-result | 11, 12, 15, 27, 28, 40, 41, 43, 44 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_s2m_G1_3072_bf16kl_mb256_20261020.json | historical-result | 11, 12, 15, 27, 28, 40, 41, 43, 44 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_s2m_G1_3072_fp32_mb128_20261020.json | historical-result | 11, 12, 15, 27, 28, 40, 41, 43, 44 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_s2m_G1_3072_fp32_mb256_20261020.json | historical-result | 11, 12, 15, 27, 28, 40, 41, 43, 44, 55 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/start_s2m_G3_3072_bf16kl_mb256_20261020.json | historical-result | 11, 12, 15, 27, 28, 40, 41, 43, 44 | drive, gpu, line_encoding, separator |
| S/foothold_s2/scripts/train_ex3031_smoke.py | runtime/config | 3, 5, 27, 141 | casefold, drive, gpu |
| S/foothold_s2/scripts/train_ex3031_window1.py | runtime/config | 3, 26, 86 | casefold, drive, gpu |
| S/foothold_s2/scripts/train_ex3031_window2.py | runtime/config | 3, 27, 90 | casefold, drive, gpu |
| S/foothold_s2/scripts/train_sol23f_common.py | runtime/config | 24, 292 | drive, separator |
| S/foothold_s2/scripts/train_start.py | runtime/config | 8, 127, 163, 187, 322, 323, 394, 395, 409, 410, 623, 697, 782, 795, 1087, 1088, 1436, 1451 | casefold, gpu, line_encoding, separator |
| S/foothold_s2/scripts/train_v2_noscan.py | runtime/config | 26 | drive |
| S/foothold_s2/sol23f_contract.py | runtime/config | 125 | casefold |
| S/foothold_s2/tasks/probe_s1.py | runtime/config | 3 | gpu |
| S/foothold_s2/tasks/probe_s2_recon.py | runtime/config | 3 | gpu |
| S/foothold_s2/tasks/s2_x17_cfg.py | runtime/config | 3 | drive |
| S/foothold_s2/tasks/s2_x19_cfg.py | runtime/config | 3 | drive |
| S/foothold_s2/tasks/s2_x20_cfg.py | runtime/config | 3 | drive |
| S/foothold_s2/tasks/s2_x22_cfg.py | runtime/config | 3 | drive |
| S/foothold_s2/tasks/v2_noscan_cfg.py | runtime/config | 3 | drive |
| S/foothold_s2/terrains/sparse_terrains.py | runtime/config | 148 | separator |
| S/foothold_s2/tests/check_configclass_cpu.py | test | 14 | drive |
| S/foothold_s2/tests/ex41_authorization_fixture.py | test | 21, 22 | separator |
| S/foothold_s2/tests/ex41_runtime_fixture.py | test | 17, 62 | line_encoding, separator |
| S/foothold_s2/tests/ex42_runtime_install_day.py | test | 13 | gpu |
| S/foothold_s2/tests/fixtures/ex41_authorization.json | test | 9, 10 | drive |
| S/foothold_s2/tests/judge_expectations.py | test | 19, 20, 21, 215 | drive, line_encoding, separator |
| S/foothold_s2/tests/test_a_push_video_cpu.py | test | 19, 21, 149, 150, 151, 152 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_basic_gait_chain_cpu.py | test | 28, 32, 58, 72, 92, 98, 103, 104, 112 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_basic_gait_cpu.py | test | 21 | drive |
| S/foothold_s2/tests/test_basic_gait_ex38_cpu.py | test | 27, 88, 118 | gpu |
| S/foothold_s2/tests/test_basic_gait_extend_cpu.py | test | 66, 105, 107, 112, 118, 120, 138, 142, 166, 169, 173, 180 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_basic_gait_fast_cpu.py | test | 173, 174, 186, 188, 189, 190, 192, 193, 194, 195, 197, 205, 216, 221, 228, 231 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_basic_gait_launch_cpu.py | test | 13, 26, 27, 42, 48, 52, 54, 56, 62, 84, 85, 90 | drive, gpu |
| S/foothold_s2/tests/test_c_layer_headless.py | test | 15, 31, 52, 67, 71, 88, 94 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_c_layer_progress.py | test | 12, 13, 18, 19, 20, 21, 30 | separator |
| S/foothold_s2/tests/test_c_layer_queue.py | test | 44, 45, 47, 67, 144, 156, 157, 164, 166, 169, 171, 172, 177, 178, 179, 185, 187, 193, 197, 202, 212, 224, 225, 231, 233, 245, 281, 291 | casefold, exe, gpu, separator |
| S/foothold_s2/tests/test_calf_band_reward.py | test | 57 | drive |
| S/foothold_s2/tests/test_chain.py | test | 70, 194, 412, 416, 417, 418, 434, 447, 458, 459, 489, 494, 513, 524, 528, 576, 583, 593, 594, 607, 611, 621, 622, 623, 628, 629, 630, 643, 724, 746, 786 | drive, gpu, msys, separator |
| S/foothold_s2/tests/test_clip_actions.py | test | 17, 23 | separator |
| S/foothold_s2/tests/test_compare_curves.py | test | 29, 31, 40 | line_encoding, separator |
| S/foothold_s2/tests/test_compose_state_chip.py | test | 9 | drive |
| S/foothold_s2/tests/test_deploy.py | test | 23, 80 | drive, separator |
| S/foothold_s2/tests/test_eval_chain_v3_cpu.py | test | 12, 58 | drive, gpu |
| S/foothold_s2/tests/test_eval_g0_reference.py | test | 33, 93, 96 | drive, exe, line_encoding, separator |
| S/foothold_s2/tests/test_ex3031_smoke_contract.py | test | 51, 151 | drive, gpu |
| S/foothold_s2/tests/test_ex3031_window1.py | test | 46, 56, 69, 70, 74, 180, 182, 186, 195, 196, 200, 201, 204, 208, 216, 219, 227, 286 | drive, exe, gpu, line_encoding, separator, winapi |
| S/foothold_s2/tests/test_ex3031_window2.py | test | 21, 38, 45, 118, 119, 122 | drive, exe, gpu, line_encoding, separator |
| S/foothold_s2/tests/test_ex35_command.py | test | 187, 302, 319 | separator |
| S/foothold_s2/tests/test_ex35_gate.py | test | 14 | drive |
| S/foothold_s2/tests/test_ex35_launch.py | test | 10, 29, 33, 37, 40, 50, 55, 61, 86, 87, 94, 105, 107, 108, 109, 115, 132 | drive, gpu, line_encoding, separator |
| S/foothold_s2/tests/test_ex35_window_judge.py | test | 27, 104, 463, 649, 654, 668 | drive, gpu, separator |
| S/foothold_s2/tests/test_ex38_continue_cpu.py | test | 18, 59, 143, 146, 148, 150 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_ex39_cpu.py | test | 84, 85, 90, 249, 250, 276, 278 | drive, gpu |
| S/foothold_s2/tests/test_ex39_kit_smoke_cpu.py | test | 92, 94, 95, 105, 118, 119, 120, 145, 150, 155, 157, 159, 172, 179, 187, 197, 206 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_ex40_b11_all_fixes_cpu.py | test | 216, 248, 260, 295, 395, 425, 519, 525, 584, 585, 681, 775, 777, 785, 805, 887, 939, 978, 1020, 1021, 1022 | drive, gpu, separator |
| S/foothold_s2/tests/test_ex40_b13_probe_cpu.py | test | 37, 156, 165 | gpu, line_encoding, separator |
| S/foothold_s2/tests/test_ex40_dr_v8_cpu.py | test | 106, 253, 281, 305, 306, 307, 317 | drive, gpu, separator |
| S/foothold_s2/tests/test_ex40_kit_argv_cpu.py | test | 18, 75, 76, 79, 87, 90, 101 | drive, exe, gpu, separator |
| S/foothold_s2/tests/test_ex40_launch_smoke_cpu.py | test | 21, 28 | gpu, separator |
| S/foothold_s2/tests/test_ex40_no_window_stdio_cpu.py | test | 15, 25, 36, 53, 60, 77, 80, 102, 103, 104, 110 | line_encoding, separator, winapi |
| S/foothold_s2/tests/test_ex40_scorer_cpu.py | test | 29, 346, 428, 456, 476, 483, 487, 488, 492, 510, 558, 563 | separator |
| S/foothold_s2/tests/test_ex40_stage_publish_cpu.py | test | 49, 59 | line_encoding, separator |
| S/foothold_s2/tests/test_ex40_v4_cpu.py | test | 287, 288, 331, 333 | separator |
| S/foothold_s2/tests/test_ex40_v7_continue_cpu.py | test | 49, 50, 51, 52, 53, 54, 251, 252, 253, 272, 283 | drive, gpu |
| S/foothold_s2/tests/test_ex40_w57_retry_cpu.py | test | 31, 32, 35, 36, 80, 95, 256 | gpu, lock, separator, winapi |
| S/foothold_s2/tests/test_ex40_w71_cpu.py | test | 82, 89, 95, 108, 111, 118, 122, 126, 135, 136, 138, 152, 184, 189 | drive, exe, gpu, line_encoding, separator, winapi |
| S/foothold_s2/tests/test_ex41_b345.py | test | 83, 120 | separator |
| S/foothold_s2/tests/test_ex41_disk_guard_cpu.py | test | 45, 56, 57, 59, 61, 68, 75 | drive |
| S/foothold_s2/tests/test_ex41_eval_loader_cpu.py | test | 179 | separator |
| S/foothold_s2/tests/test_ex41_eval_schedule_cpu.py | test | 62, 90, 110, 111, 115, 122, 191, 208, 215, 219, 222, 223, 353, 422, 426, 474 | gpu, line_encoding, separator |
| S/foothold_s2/tests/test_ex41_fixed_cpu.py | test | 31, 341 | line_encoding, separator |
| S/foothold_s2/tests/test_ex41_gpu_priority_cpu.py | test | 19, 31, 39, 115 | drive |
| S/foothold_s2/tests/test_ex41_ops_cpu.py | test | 111, 112, 132 | separator |
| S/foothold_s2/tests/test_ex41_p3_cpu.py | test | 68, 69, 70 | casefold |
| S/foothold_s2/tests/test_ex41_resume_cpu.py | test | 146, 181, 207, 208, 209, 255, 259, 264, 282, 288, 466, 502, 503, 507, 514, 516, 541 | drive, separator |
| S/foothold_s2/tests/test_ex41_runtime_cpu.py | test | 141 | separator |
| S/foothold_s2/tests/test_ex41_score_names_cpu.py | test | 35 | separator |
| S/foothold_s2/tests/test_ex41_score_watch_cpu.py | test | 18, 91, 169, 170, 183, 263, 421, 433, 438, 559 | drive, gpu, separator, winapi |
| S/foothold_s2/tests/test_ex41_score_watch_launch_cpu.py | test | 15, 17 | separator |
| S/foothold_s2/tests/test_ex41_scoring_cpu.py | test | 12, 20, 48, 54 | drive, line_encoding |
| S/foothold_s2/tests/test_ex41_short_stage_rehearsal_cpu.py | test | 76, 77, 295, 349 | drive, gpu, line_encoding, separator |
| S/foothold_s2/tests/test_ex41_start_preflight_cpu.py | test | 33, 57, 63, 102, 105, 114 | gpu, separator |
| S/foothold_s2/tests/test_ex41_startup_integration_cpu.py | test | 103, 372, 391, 392, 416, 426, 428, 429, 430, 434, 443, 465, 474, 475, 478, 479, 480, 481, 482, 483, 502, 504, 505, 506, 511, 527, 532, 536, 541, 550, 567, 569, 570, 573, 575, 577, 579, 601, 618, 619, 620, 621, 622, 623, 624, 625, 626, 627, 628, 629, 630, 632, 670, 673, 681, 699, 707, 713, 835, 939, 940, 976, 994, 995, 1016, 1019 | drive, gpu, separator |
| S/foothold_s2/tests/test_ex41_symmetry_cpu.py | test | 9 | drive |
| S/foothold_s2/tests/test_ex41_turn_receipt_cpu.py | test | 31, 121 | drive, separator |
| S/foothold_s2/tests/test_ex41_u10_cpu.py | test | 64, 80 | separator |
| S/foothold_s2/tests/test_ex42_chain_cpu.py | test | 73, 109, 110, 111, 112, 213, 396, 397, 398, 399, 400, 401, 403, 432, 433 | gpu, separator |
| S/foothold_s2/tests/test_ex42_correct_guards_cpu.py | test | 126 | separator |
| S/foothold_s2/tests/test_ex42_env_probe_cpu.py | test | 16, 17, 24, 25, 26, 28 | drive, gpu |
| S/foothold_s2/tests/test_ex42_g11_w78_cpu.py | test | 105 | drive |
| S/foothold_s2/tests/test_ex42_g22_video_cpu.py | test | 29, 43 | separator |
| S/foothold_s2/tests/test_ex42_gate_checks_cpu.py | test | 25, 50, 53, 70, 87, 95, 98, 110, 121, 142, 161, 164, 228, 229, 238, 292 | exe, gpu, permissions, separator, winapi |
| S/foothold_s2/tests/test_ex42_ops_cpu.py | test | 154 | winenv_binary |
| S/foothold_s2/tests/test_ex42_prep_cpu.py | test | 85 | gpu |
| S/foothold_s2/tests/test_ex42_stage_zero_cpu.py | test | 28, 48, 63, 71, 85, 88, 220, 232 | drive, gpu |
| S/foothold_s2/tests/test_ex42_terrain_cpu.py | test | 76, 77, 78, 80 | drive, gpu |
| S/foothold_s2/tests/test_ex42_training_entry_cpu.py | test | 130, 133, 137, 138 | separator |
| S/foothold_s2/tests/test_experiment_registry_cpu.py | test | 27, 28, 43, 45, 83, 90, 92, 147, 148, 161, 163, 165, 170, 172, 173 | casefold, drive, gpu |
| S/foothold_s2/tests/test_fbg_margin.py | test | 49 | separator |
| S/foothold_s2/tests/test_fixed_terrain.py | test | 95 | line_encoding, separator |
| S/foothold_s2/tests/test_g0b_eval_prep.py | test | 12, 87, 91, 99 | drive, exe, line_encoding, separator |
| S/foothold_s2/tests/test_geometry_hash.py | test | 14 | drive |
| S/foothold_s2/tests/test_go2_model.py | test | 14, 15 | drive |
| S/foothold_s2/tests/test_judge_gate.py | test | 388 | separator |
| S/foothold_s2/tests/test_judge_stats.py | test | 233, 305 | drive, separator |
| S/foothold_s2/tests/test_kind_stats.py | test | 111, 126, 128, 130 | separator |
| S/foothold_s2/tests/test_kit_names.py | test | 4, 14, 145, 150 | drive, separator |
| S/foothold_s2/tests/test_limit_dwell.py | test | 91 | separator |
| S/foothold_s2/tests/test_machine_profile_cpu.py | test | 4, 20, 21, 22, 23, 24, 25, 26, 95, 105, 114 | drive, exe, separator, winenv_binary |
| S/foothold_s2/tests/test_map_error.py | test | 150 | separator |
| S/foothold_s2/tests/test_mapratio.py | test | 216 | separator |
| S/foothold_s2/tests/test_mapratio_revert.py | test | 134 | separator |
| S/foothold_s2/tests/test_n21_dr_record_cpu.py | test | 250, 252 | separator |
| S/foothold_s2/tests/test_plan_c_layer.py | test | 31, 33, 34, 36, 38, 40, 48 | drive, gpu, separator |
| S/foothold_s2/tests/test_probe_tiles.py | test | 53 | drive |
| S/foothold_s2/tests/test_runtime_environment_cpu.py | test | 19, 20, 21, 34, 41, 57, 61 | casefold, exe, separator |
| S/foothold_s2/tests/test_sb_eval_chain2.py | test | 14, 34, 42, 44, 51, 57, 58, 59, 61, 68, 77, 86, 93, 97, 98, 102, 104, 106, 141, 146, 174, 178 | casefold, drive, exe, gpu, line_encoding, separator, shell, winapi |
| S/foothold_s2/tests/test_sb_eval_prep.py | test | 15, 35, 52, 53, 74, 116, 146, 150, 168, 182, 192, 195, 203, 208, 224 | casefold, drive, exe, gpu, line_encoding, separator, winapi |
| S/foothold_s2/tests/test_sb_map_switch.py | test | 371, 393, 394, 397, 448, 449 | drive, exe, gpu, line_encoding, separator |
| S/foothold_s2/tests/test_stage_transfer.py | test | 24, 556 | drive, gpu |
| S/foothold_s2/tests/test_start_runner.py | test | 132, 133, 134, 135, 136, 137, 138, 140, 143 | gpu, separator |
| S/foothold_s2/tests/test_start_sensors.py | test | 41 | drive |
| S/foothold_s2/tests/test_turn_probe_plan.py | test | 82, 99, 102, 115, 161, 255, 260 | drive, exe, line_encoding, separator |
| S/foothold_s2/tests/test_unattended.py | test | 99, 101, 102, 105, 108, 117, 153 | lock, winapi |
| S/foothold_s2/tests/test_video_style.py | test | 12, 38 | drive, separator |
| S/foothold_s2/tests/test_w15_capture_plan.py | test | 13, 14, 27, 37, 61 | drive, gpu, separator |
| S/foothold_s2/tests/test_w19_extend.py | test | 13, 49, 59, 62, 66, 69, 76, 80, 82, 124, 137, 140, 150, 151, 153, 166, 175, 176, 180, 181, 188 | drive, gpu, line_encoding, separator |
| S/foothold_s2/tests/test_w55_continuous_cpu.py | test | 154, 175, 181, 205, 231, 237, 334, 343, 438, 439, 487, 502, 503, 507, 508, 548, 551 | drive, gpu, separator |
| S/foothold_s2/tests/test_w72_cpu.py | test | 28, 29, 34 | separator |
| S/foothold_s2/tests/test_window2_gate.py | test | 34, 95, 104, 105, 131, 132, 138, 139, 156, 240 | gpu, line_encoding, separator |
| S/foothold_s2/tests/test_window3_branch.py | test | 173 | drive |
| S/foothold_s2/tests/test_window3_prescription.py | test | 11, 23, 52, 69 | separator |
| S/foothold_s2/tests/test_world_frame.py | test | 275, 277 | separator |
| S/foothold_s2/tests/test_x11.py | test | 389 | separator |
| S/foothold_s2/tests/test_x11b.py | test | 331, 362, 365, 382, 388, 434, 439, 444, 462, 463, 480, 517, 525, 526, 528, 529, 532, 541, 542, 543, 544 | casefold, gpu, separator |
| S/foothold_s2/tests/test_x15.py | test | 54, 56, 57, 58 | drive, separator |
| S/foothold_s2/tests/test_x16n.py | test | 15, 16, 17, 84, 96 | drive, separator |
| S/foothold_s2/tests/test_x17.py | test | 19 | drive |
| S/foothold_s2/tests/test_x19.py | test | 14, 160 | casefold, drive |
| S/foothold_s2/tests/test_x21.py | test | 15, 16 | drive |
| S/foothold_s2/tests/test_x23.py | test | 20, 21, 275, 279 | drive, separator |
| S/foothold_s2/tests/test_x24b.py | test | 14, 15, 50, 54 | drive, separator |
| S/foothold_s2/train_s1.py | runtime/config | 3, 21 | drive, gpu |
| S/foothold_s2/w15_one_table.py | runtime/config | 49, 133 | line_encoding |
| S/foothold_s2/window2_criteria.py | runtime/config | 33 | line_encoding, separator |
| S/foothold_s2/window2_gate.py | runtime/config | 26, 27, 31, 132, 134, 182 | casefold, drive, exe, gpu, winapi |
| S/foothold_s2/window3_branch.py | runtime/config | 202 | separator |
| S/foothold_s2/window3_criteria.py | runtime/config | 49 | line_encoding, separator |
