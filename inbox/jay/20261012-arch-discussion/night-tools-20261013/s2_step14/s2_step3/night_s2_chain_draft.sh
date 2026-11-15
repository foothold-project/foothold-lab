#!/usr/bin/env bash
# S2 chain review draft. This file is inert until reviewed and replaced.
echo 'STOP: S2 chain draft is not approved for launch' >&2
exit 99

# Proposed calls below are unreachable. All decisions are explicit inputs.
set -euo pipefail
: "${S2_MANIFEST:?approved frozen manifest required}"
: "${S2_APPROVAL_JSON:?approval JSON required}"
: "${S2_PYTHON:?pinned Python required}"
: "${S2_EVAL_ROOT:?read-only tool root required}"
: "${S2_OUT_ROOT:?isolated output required}"
: "${S2_STOP_FILE:?STOP path required}"
: "${S2_DEADLINE_EPOCH:?deadline required}"
: "${S2_GPU_INDEX:?physical GPU required}"
: "${S2_MIN_FREE_MIB:?guard floor required}"
: "${S2_SHARED_CONVERT_LOCK:?shared conversion lock required}"
: "${S2_SHARED_REGISTRY:?shared registry required}"
: "${S2_EXPECT_CONVERSIONS:?conversion decision required}"
: "${S2_PARENT:?parent checkpoint required}"
: "${S2_AGENT_YAML:?parent config required}"
: "${S2_CONNECT_ARGS:?reviewed explicit connection args required}"
: "${S2_TRAIN_ARGS:?reviewed explicit training args required}"
: "${S2_RECORD_CONNECT:?stage 0 record path required}"
: "${S2_RECORD_SMOKE:?stage 1 record path required}"
: "${S2_RECORD_SHORT_AB:?stage 2 record path required}"
HERE=$(cd "$(dirname "$0")" && pwd)
test ! -e "$S2_STOP_FILE" || exit 7
test "$(date +%s)" -lt "$S2_DEADLINE_EPOCH" || exit 7
case "$S2_OUT_ROOT" in "$S2_EVAL_ROOT"|"$S2_EVAL_ROOT"/*) exit 7;; esac
mkdir -p "$S2_OUT_ROOT"
mkdir "$S2_OUT_ROOT/_single_chain_lease" || exit 8
trap 'rmdir "$S2_OUT_ROOT/_single_chain_lease"' EXIT
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES="$S2_GPU_INDEX"

# Each branch_run/ce12 style launch goes slot v3 -> guard -> USD isolation.
# A reviewed replacement must parse the explicit argument files and construct
# argv arrays; this inert draft deliberately contains no shell eval expansion.
launch_one() {
  local attempt="$1" log="$2" entry="$3"
  "$S2_PYTHON" "$S2_EVAL_ROOT/isaac_slot_v3.py" \
    --watch_log "$log" --record "$S2_OUT_ROOT/$attempt.slot.json" \
    --attempt "$attempt" --usd_root "$S2_OUT_ROOT/_usd/$attempt" \
    --lock "$S2_SHARED_CONVERT_LOCK" --registry "$S2_SHARED_REGISTRY" \
    --scan_dirs "$S2_OUT_ROOT" --stop_file "$S2_STOP_FILE" \
    --deadline "$S2_DEADLINE_EPOCH" --expect_conversions "$S2_EXPECT_CONVERSIONS" -- \
  "$S2_PYTHON" "$S2_EVAL_ROOT/gpu_guard.py" --gpu "$S2_GPU_INDEX" \
    --min_free_mib "$S2_MIN_FREE_MIB" --log "$log" \
    --summary "$S2_OUT_ROOT/$attempt.guard.json" -- \
  "$S2_PYTHON" "$S2_EVAL_ROOT/usd_isolate_run_v3.py" "$entry" --headless
}

for stage in connect smoke short_ab; do
  test ! -e "$S2_STOP_FILE" || exit 7
  test "$(date +%s)" -lt "$S2_DEADLINE_EPOCH" || exit 7
  case "$stage" in
    connect) entry="$HERE/s2_connect_diag.py"; record="$S2_RECORD_CONNECT";;
    smoke) entry="$HERE/s2_train_entry.py"; record="$S2_RECORD_SMOKE";;
    short_ab) entry="$HERE/s2_train_entry.py"; record="$S2_RECORD_SHORT_AB";;
  esac
  # Reviewed replacement: pass every required CLI value as a quoted argv item,
  # claim stage once, then launch connect or A and B sequentially. No next arm
  # or stage after any nonzero rc, traceback or result validation hold.
  test -f "$record" || exit 9
  "$S2_PYTHON" "$HERE/s2_stage_gate.py" --manifest "$S2_MANIFEST" \
    --stage "$stage" --record "$record" --now_epoch "$(date +%s)" || exit 10
done
