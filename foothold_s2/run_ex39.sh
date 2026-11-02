#!/usr/bin/env bash
# Receipt and CPU preflight only by default. The lead alone sets LIVE=1.
set -euo pipefail
ARM="${1:?A or B}"
DEV="${2:?cuda:0 or cuda:1}"
PARENT="${3:?completed EX-38 model_3001.pt}"
PARENT_SHA="${4:?full SHA256 of completed EX-38 checkpoint}"
END_BY="${END_BY:?explicit timezone-aware upper deadline required}"
BASIC_LOG_ROOT="${BASIC_LOG_ROOT:?explicit absolute output root required}"
UPDATES="${EX39_UPDATES:-1500}"
LEVELS="${EX39_LEVELS:-3}"
KIT_SMOKE_UPDATES="${EX39_KIT_SMOKE_UPDATES:-}"
REQUIRE_KIT_SMOKE="${EX39_REQUIRE_KIT_SMOKE:-0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
PY="$ENV/python.exe"
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE PYTHONUTF8=1
export PYTHONPATH="$ROOT"
cd "$ROOT"
OPTS=(--arm "$ARM" --device "$DEV" --parent "$PARENT" --parent-sha256 "$PARENT_SHA" --end-by "$END_BY" --log-root "$BASIC_LOG_ROOT" --updates "$UPDATES" --levels "$LEVELS")
if [ -n "$KIT_SMOKE_UPDATES" ]; then OPTS+=(--kit-smoke-updates "$KIT_SMOKE_UPDATES"); fi
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BASIC_LOG_ROOT/receipts/ex39/${ARM}_${STAMP}_$$"
mkdir -p "$OUT"
"$PY" -m foothold_s2.basic_gait_ex39 "${OPTS[@]}" > "$OUT/launch_receipt.json"
"$PY" -m foothold_s2.basic_gait_ex39 "${OPTS[@]}" --print-args > "$OUT/launch_args.txt"
if [ "$REQUIRE_KIT_SMOKE" = "1" ]; then
  if [ "$KIT_SMOKE_UPDATES" != "2" ]; then
    echo 'EX-39 smoke requested but EX39_KIT_SMOKE_UPDATES is not 2' > "$OUT/smoke_preflight_fail.txt"
    echo "smoke preflight failed: $OUT/smoke_preflight_fail.txt" >&2
    exit 5
  fi
  if ! "$PY" -m foothold_s2.ex39_smoke_args "$OUT/launch_args.txt" > "$OUT/smoke_args_checked.json" 2> "$OUT/smoke_args_error.txt"; then
    echo 'EX-39 smoke argv mismatch before training child' > "$OUT/smoke_preflight_fail.txt"
    echo "smoke preflight failed: $OUT/smoke_preflight_fail.txt" >&2
    exit 5
  fi
fi
"$PY" -m foothold_s2.prestart_check --args-file "$OUT/launch_args.txt" > "$OUT/prestart.json"
mapfile -t ARGS < <(tr -d '\r' < "$OUT/launch_args.txt")
git rev-parse HEAD > "$OUT/git_head.txt"
echo "receipt=$OUT/launch_receipt.json"
if [ "${LIVE:-0}" != "1" ]; then echo "DRY: training not started"; exit 0; fi
set +e
"$PY" foothold_s2/scripts/train_sb.py "${ARGS[@]}" > "$OUT/run.log" 2>&1
RC=$?
set -e
echo "rc=$RC" > "$OUT/rc.txt"
exit "$RC"
