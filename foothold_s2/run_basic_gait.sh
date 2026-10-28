#!/usr/bin/env bash
# Proposed parent/scratch pair. Default is receipt-only; lead starts live jobs after approval.
# END_BY=2026-10-30T08:00:00+09:00 SHARE=0.30 bash foothold_s2/run_basic_gait.sh parent cuda:0 <model_1500.pt>
# END_BY=... SHARE=0.30 bash foothold_s2/run_basic_gait.sh scratch cuda:1
set -euo pipefail

KIND="${1:?parent or scratch}"
DEV="${2:?cuda:0 or cuda:1}"
PARENT="${3:-}"
END_BY="${END_BY:?explicit ISO8601 deadline with timezone required}"
SHARE="${SHARE:-0.30}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
PY="$ENV/python.exe"
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE PYTHONUTF8=1
export PYTHONPATH="$ROOT"
cd "$ROOT"

OPTS=("$KIND" "$DEV" --end-by "$END_BY" --share "$SHARE")
if [ -n "$PARENT" ]; then OPTS+=(--parent "$PARENT"); fi
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs_gate/basic_gait_${KIND}_${STAMP}_$$"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$PY" -m foothold_s2.basic_gait_launch "${OPTS[@]}" > "$OUT/launch_receipt.json"
mapfile -t ARGS < <("$PY" -m foothold_s2.basic_gait_launch "${OPTS[@]}" --print-args | tr -d '\r')
for A in "${ARGS[@]}"; do
  case "$A" in ""|*$'\r'*) echo "invalid argv" >&2; exit 5;; esac
done
printf '%s\n' "${ARGS[@]}" > "$OUT/launch_args.txt"
echo "receipt=$OUT/launch_receipt.json"
if [ "${LIVE:-0}" != "1" ]; then echo "DRY: training not started"; exit 0; fi
[ -z "$(git status --short foothold_s2)" ] || { echo "refused: foothold_s2 dirty" >&2; exit 3; }
set +e
"$PY" foothold_s2/scripts/train_sb.py "${ARGS[@]}" > "$OUT/run.log" 2>&1
RC=$?
set -e
echo "rc=$RC" > "$OUT/rc.txt"
grep -q "TRAIN_START_STATUS done" "$OUT/run.log" || echo "TRAIN_START_STATUS done missing" >> "$OUT/rc.txt"
exit "$RC"
