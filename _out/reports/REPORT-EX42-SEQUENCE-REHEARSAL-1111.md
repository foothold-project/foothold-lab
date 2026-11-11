(13:12) # EX-42 short stage rehearsal preflight

> 분류: 운영
> 작성: runner-lx · 2026-11-11 13:12 KST
> 근거: EX-42 fixed plan, approvals, train entry and stage launcher on d299d470
> 요지: E1F through E6b canary sequence is enumerated, but execution is fail-closed until the bounded stage-entry path exists
> 상태: 확인됨

Added `foothold_s2/scripts/ex42_kit_sequence_rehearsal.py` and its CPU test. It enumerates E1F, E2, E3, E4, E5, M, E6a and E6b with three updates per stage and two ranks (`cuda:0`, `cuda:1`), but `--execute` refuses to start Kit.

CPU preflight on the current tree reports all eight stages blocked. In `ex42_training_entry.py`, only stages with pinned parents enter `E_STAGE_SPECS`; `validate_ex42_stage_e_cli` accepts only exact approved stage lengths, and `train_start.py` has no bounded EX-42 stage rehearsal flag. The available `--ex42_speed_probe` is restricted to 20 or 50 updates and stage zero/E0, so using it for these later stages would require bypassing the current authorization and parent checks.

Verification: `isaac311/bin/python -m pytest foothold_s2/tests/test_ex42_kit_sequence_rehearsal_cpu.py -q -p no:cacheprovider` → 6 passed. Plan-only CLI lists all blockers and states `kit_started=false`, `training_started=false`. No Kit or GPU was started. A true sequential Kit rehearsal remains blocked until the stage transition path supports bounded rehearsal lengths and valid parent handoff for these stages.
