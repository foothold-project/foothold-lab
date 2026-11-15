#!/bin/bash
export CUDA_VISIBLE_DEVICES=-1 PYTHONDONTWRITEBYTECODE=1
P="C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe"
C="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/s2_step2"
L="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexw/leadS2"
export S2_MUT_TMPDIR="$L/mut_tmp"; mkdir -p "$S2_MUT_TMPDIR"
date '+START %H:%M:%S' > $L/progress.txt
"$P" -B -u "$C/run_all_s2_step2.py" > "$L/run_all_s2_step2.txt" 2>&1
echo "END run_all_s2_step2 rc=$? $(date +%H:%M:%S)" >> $L/progress.txt
echo ALLDONE >> $L/progress.txt
