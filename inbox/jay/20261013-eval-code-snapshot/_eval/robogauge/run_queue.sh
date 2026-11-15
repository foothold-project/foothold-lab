#!/usr/bin/env bash
# Serial queue: one StressPipeline at a time, 8 worker processes (lead request 2026-10-12 23:35,
# training on GPU 0 shares this CPU). Known-answer references run first.
set -uo pipefail
HERE=C:/isaac/ext/go2_rl_robotlab/_eval/robogauge
JIT=C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/jit
NPROC=8
QUEUE=(
  "ref_sym_v5.1_52k_0.6953|C:/isaac/checkpoints/robogauge/go2_rl_robotlab/go2_moe_cts_symmetry_v5.1_52k_0.6953_20260703/exported/policy.pt"
  "ref_176k_0.6984|C:/isaac/ext/go2_rl_robotlab/deploy/pre_train/go2/go2_moe_cts_176k_0.6984.pt"
  "e1_model_20000|$JIT/e1_model_20000.pt"
  "e2_model_20000|$JIT/e2_model_20000.pt"
  "e1_model_20499|$JIT/e1_model_20499.pt"
  "e2_model_20499|$JIT/e2_model_20499.pt"
)
for item in "${QUEUE[@]}"; do
  label="${item%%|*}"
  model="${item#*|}"
  if [ -f "C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/STOP_QUEUE" ]; then
    echo "[queue] STOP_QUEUE found, stopping before $label"
    break
  fi
  bash "$HERE/run_stress.sh" "$label" "$model" "$NPROC"
done
echo "[queue] done $(date '+%F %T')"
