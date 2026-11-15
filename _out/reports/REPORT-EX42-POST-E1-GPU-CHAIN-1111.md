(14:45) # EX-42 post-E1 ordered GPU chain

> 분류: 운영
> 작성: runner-lx · 2026-11-11 14:45 KST
> 근거: planner REVIEW-EX42-STAGE-CHECKLIST-REMEASURE-1111.md §2 rows 7, 8, 14, 19; current integration d299d470
> 요지: A single ordered post-E1 schedule is represented, while live dispatch remains fail-closed until the required producers and stage rehearsal entry are executable
> 상태: 확인됨

Added `foothold_s2/scripts/ex42_post_e1_gpu_chain.py`. It plans two waves of E1 P1 checkpoints (m250/m500 on GPU0/GPU1, then m750/m1000), the W09 E1-graduation flag baseline, five W08 repeats, E1F through E6b short Kit canaries, W14 before E2, and W19 before E3. Each stage depends on completion of its predecessor and the specified W14/W19 item.

The script is deliberately plan-only and does not write the live GPU queue. The CPU plan has no safe `argv` for these pending steps: no W09 flag-cell evaluator command, no W08 flag calibration producer/receipt contract, W14/W19 new-cell evaluators are absent, and the existing Kit rehearsal script fails closed because E1F onward lack pinned parent/entry validators and the train CLI has no bounded 2-3 update mode. Current report therefore sets `queue_mutated=false` and `gpu_idle_guarantee=false`; calling it a live no-gap chain would be inaccurate. The E1 checkpoint root must also be supplied from the actual graduated run, not guessed.

Verification: targeted CPU tests for both sequence planners → 8 passed. The plan-only CLI was run with an explicitly labeled placeholder E1 path; no GPU or Kit was started and no queue was changed.
