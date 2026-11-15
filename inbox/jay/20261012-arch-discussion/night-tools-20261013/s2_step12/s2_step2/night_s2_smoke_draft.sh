#!/usr/bin/env bash
# S2 review draft. This file is intentionally inert. Lead must supply an Isaac
# training entry, validate actual paths, review gates, then issue a new script.
echo 'STOP: S2 smoke draft is not an approved launch script' >&2
exit 99

# Proposed chain below is unreachable. No numerical policy decisions default.
set -euo pipefail
: "${S2_APPROVAL_JSON:?approval JSON required}"
: "${S2_PLAN_SHA256:?frozen plan hash required}"
: "${S2_ENV_SHA256:?environment config hash required}"
: "${S2_CODE_SHA256:?candidate code hash required}"
: "${S2_DEADLINE_EPOCH:?deadline required}"
: "${S2_GPU_INDEX:?physical GPU index required}"
: "${S2_MIN_FREE_MIB:?GPU preflight floor required}"
: "${S2_OUT_ROOT:?isolated output required}"
: "${S2_TRAIN_ENTRY:?reviewed Isaac training entry required}"
: "${S2_PYTHON:?pinned Python required}"
: "${S2_STOP_FILE:?STOP path required}"
: "${S2_SHARED_CONVERT_LOCK:?shared conversion lock required}"
: "${S2_SHARED_REGISTRY:?shared conversion registry required}"
: "${S2_EXPECT_CONVERSIONS:?conversion count decision required}"
: "${S2_PARENT_CKPT:?parent checkpoint required}"
: "${S2_SEED:?training seed required}"
: "${S2_NUM_ENVS:?environment count required}"
: "${S2_UPDATES:?smoke update count required}"
: "${S2_ROLLOUT_STEPS:?rollout length required}"
: "${S2_EPOCHS:?PPO epochs required}"
: "${S2_MINIBATCHES:?PPO minibatches required}"
: "${S2_ENCODER_MODE:?encoder mode required}"
HERE=$(cd "$(dirname "$0")" && pwd)
EVAL_ROOT=${S2_EVAL_ROOT:?read-only evaluator tool root required}
S2_ENCODER_ARGS=()
if [ "$S2_ENCODER_MODE" = schedule ]; then
  : "${S2_FREEZE_UPDATES:?schedule W required}"
  : "${S2_ENCODER_LR_RATIO:?schedule r required}"
  S2_ENCODER_ARGS=(--freeze_updates "$S2_FREEZE_UPDATES" --encoder_lr_ratio "$S2_ENCODER_LR_RATIO")
fi
test ! -e "$S2_STOP_FILE" || { echo 'STOP file present' >&2; exit 7; }
"$S2_PYTHON" "$HERE/s2_launch_gate.py" --approval "$S2_APPROVAL_JSON" \
  --plan-sha256 "$S2_PLAN_SHA256" --env-sha256 "$S2_ENV_SHA256" \
  --code-sha256 "$S2_CODE_SHA256" --deadline "$S2_DEADLINE_EPOCH"
test "$(date +%s)" -lt "$S2_DEADLINE_EPOCH" || { echo 'deadline passed' >&2; exit 7; }
case "$S2_OUT_ROOT" in
  "$EVAL_ROOT"|"$EVAL_ROOT"/*) echo 'output must be outside read-only evaluator tree' >&2; exit 7;;
esac
mkdir -p "$S2_OUT_ROOT"
mkdir "$S2_OUT_ROOT/_single_run_lease" || { echo 'another S2 run owns lease' >&2; exit 8; }
trap 'rmdir "$S2_OUT_ROOT/_single_run_lease"' EXIT
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES="$S2_GPU_INDEX"
for arm in A B; do
  test ! -e "$S2_STOP_FILE" || exit 7
  test "$(date +%s)" -lt "$S2_DEADLINE_EPOCH" || exit 7
  attempt="s2-${arm}-$(date +%Y%m%d%H%M%S)-$$"
  log="$S2_OUT_ROOT/$attempt.log"
  "$S2_PYTHON" "$EVAL_ROOT/isaac_slot_v3.py" \
    --watch_log "$log" --record "$S2_OUT_ROOT/$attempt.slot.json" \
    --attempt "$attempt" --usd_root "$S2_OUT_ROOT/_usd/$attempt" \
    --lock "$S2_SHARED_CONVERT_LOCK" --registry "$S2_SHARED_REGISTRY" \
    --scan_dirs "$S2_OUT_ROOT" --stop_file "$S2_STOP_FILE" --deadline "$S2_DEADLINE_EPOCH" \
    --expect_conversions "$S2_EXPECT_CONVERSIONS" -- \
  "$S2_PYTHON" "$EVAL_ROOT/gpu_guard.py" --gpu "$S2_GPU_INDEX" \
    --min_free_mib "$S2_MIN_FREE_MIB" --log "$log" --summary "$S2_OUT_ROOT/$attempt.guard.json" -- \
  "$S2_PYTHON" "$EVAL_ROOT/usd_isolate_run_v3.py" "$S2_TRAIN_ENTRY" --headless \
    --arm "$arm" --parent "$S2_PARENT_CKPT" --seed "$S2_SEED" \
    --num_envs "$S2_NUM_ENVS" --updates "$S2_UPDATES" \
    --rollout_steps "$S2_ROLLOUT_STEPS" --epochs "$S2_EPOCHS" \
    --minibatches "$S2_MINIBATCHES" --encoder_mode "$S2_ENCODER_MODE" "${S2_ENCODER_ARGS[@]}" \
    --approval "$S2_APPROVAL_JSON" --attempt "$attempt"
  # Release from this arm only after the real validator checks attempt, start time,
  # exit code, artifact hashes and the registered rollout/step counts.
done
