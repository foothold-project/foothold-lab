#!/bin/bash
export CUDA_VISIBLE_DEVICES=-1 PYTHONDONTWRITEBYTECODE=1
P="C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe"
C="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/cand"
L="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexw/leadE"
date '+START %H:%M:%S' > $L/progress.txt
run() { n="$1"; shift; date "+BEGIN $n %H:%M:%S" >> $L/progress.txt; "$P" -B "$C/$n.py" "$@" > "$L/$n.txt" 2>&1; echo "END $n rc=$? $(date +%H:%M:%S)" >> $L/progress.txt; }
run test_manifest
run test_stage1 --run-id lead1
run test_driver_cpu --run-id lead1
run test_full_inputs_copy --run-id lead1
run test_integration_s1043 --run-id lead1
echo ALLDONE >> $L/progress.txt
