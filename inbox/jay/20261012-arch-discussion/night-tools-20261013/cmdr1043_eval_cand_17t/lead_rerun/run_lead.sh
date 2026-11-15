#!/bin/bash
export CUDA_VISIBLE_DEVICES=-1 PYTHONDONTWRITEBYTECODE=1
P="C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe"
C="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/cand"
L="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexw/leadE4"
date '+START %H:%M:%S' > $L/progress.txt
"$P" -B -u "$C/run_all_17t.py" > "$L/run_all_17t.txt" 2>&1
echo "END run_all_17t rc=$? $(date +%H:%M:%S)" >> $L/progress.txt
echo ALLDONE >> $L/progress.txt
