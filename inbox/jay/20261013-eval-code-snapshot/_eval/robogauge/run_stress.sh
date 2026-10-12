#!/usr/bin/env bash
# Run the RoboGauge StressPipeline with exactly the arguments the RoboGauge server uses
# for a training-time submission (robogauge/scripts/server.py default_args_list, v1.1.9),
# task name go2_lab (what go2_rl_robotlab's OnPolicyRunnerCTS submits).
# Usage: run_stress.sh <label> <jit_model_path> [num_processes]
set -euo pipefail
LABEL="$1"
MODEL="$2"
NPROC="${3:-28}"
PY=C:/Users/AI-WS01/anaconda3/envs/robogauge/python.exe
HERE=C:/isaac/ext/go2_rl_robotlab/_eval/robogauge
OUT=C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/stress
mkdir -p "$OUT"
export RG_LOGS_DIR="$OUT"
export CUDA_VISIBLE_DEVICES=-1
LOG="$OUT/${LABEL}.console.log"
T0=$(date +%s)
echo "[run_stress] label=$LABEL model=$MODEL nproc=$NPROC start=$(date '+%F %T')" | tee "$LOG"
cd "$HERE"
set +e
"$PY" rg_run.py \
    --stress-benchmark \
    --stress-terrain-names flat wave slope_fd slope_bd stairs_fd stairs_bd obstacle \
    --seeds 0 1 2 \
    --search-seeds 0 1 2 3 4 \
    --frictions 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 \
    --compress-logs \
    --headless \
    --model-path "$MODEL" \
    --task-name go2_lab \
    --experiment-name "$LABEL" \
    --num-processes "$NPROC" >> "$LOG" 2>&1
RC=$?
set -e
T1=$(date +%s)
echo "[run_stress] label=$LABEL rc=$RC end=$(date '+%F %T') wall_s=$((T1-T0))" | tee -a "$LOG"
echo "$LABEL,$MODEL,$NPROC,$((T1-T0))" >> "$OUT/walltimes.csv"
