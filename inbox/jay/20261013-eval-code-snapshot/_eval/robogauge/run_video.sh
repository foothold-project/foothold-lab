#!/usr/bin/env bash
# Record one RoboGauge BasePipeline run as mp4 (single process, CPU physics, offscreen OpenGL render).
# Level terrains: the level pass/fail test itself (goal target_pos_velocity, spawn level_search).
# Flat: max_velocity goal (6 one-axis max commands, each followed by a hard stop).
# Usage: run_video.sh <label> <model> <terrain> <level|-> <friction> [seed]
set -euo pipefail
LABEL="$1"; MODEL="$2"; TERRAIN="$3"; LEVEL="$4"; FRIC="$5"; SEED="${6:-0}"
PY=C:/Users/AI-WS01/anaconda3/envs/robogauge/python.exe
HERE=C:/isaac/ext/go2_rl_robotlab/_eval/robogauge
OUT=C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge
export RG_LOGS_DIR="$OUT/video_runs"
export CUDA_VISIBLE_DEVICES=-1
export RG_RENDER_W=1280 RG_RENDER_H=720
mkdir -p "$OUT/videos" "$RG_LOGS_DIR"
if [ "$TERRAIN" = "flat" ]; then
  EXTRA=(--goals max_velocity)
  NAME="${LABEL}__flat_maxvel_F${FRIC}_s${SEED}"
else
  EXTRA=(--level "$LEVEL" --spawn-type level_search --goals target_pos_velocity)
  NAME="${LABEL}__${TERRAIN}_L${LEVEL}_F${FRIC}_s${SEED}"
fi
cd "$HERE"
T0=$(date +%s)
set +e
"$PY" rg_run.py --task-name "go2_lab.${TERRAIN}" --experiment-name "$NAME" --model-path "$MODEL" \
  --headless --save-video --friction "$FRIC" --seed "$SEED" "${EXTRA[@]}" > "$OUT/videos/${NAME}.log" 2>&1
RC=$?
set -e
RUN_DIR=$(ls -d "$RG_LOGS_DIR"/go2_lab_${TERRAIN}_${NAME}/*/ | tail -1)
MP4=$(ls "$RUN_DIR"videos/*.mp4 | head -1)
cp "$MP4" "$OUT/videos/${NAME}.mp4"
cp "$RUN_DIR"results.yaml "$OUT/videos/${NAME}.results.yaml"
echo "[video] $NAME rc=$RC wall_s=$(( $(date +%s)-T0 )) -> $OUT/videos/${NAME}.mp4"
