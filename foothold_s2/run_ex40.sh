#!/usr/bin/env bash
# EX-40 CPU preflight by default. Only the lead sets LIVE=1 for Kit.
set -euo pipefail
ARM="${1:?A or B}"
DEV="${2:?cuda:0 or cuda:1}"
END_BY="${3:?ISO8601 deadline with timezone}"
LOG_ROOT="${4:?absolute isolated log root}"
SCORE_DIR="${5:?absolute score directory}"
KIND="${6:?smoke or main}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
PY="$ENV/python.exe"
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE PYTHONUTF8=1
export PYTHONPATH="$ROOT"
cd "$ROOT"
OPTS=(--arm "$ARM" --device "$DEV" --end-by "$END_BY" --log-root "$LOG_ROOT" --score-dir "$SCORE_DIR")
case "$KIND" in
  smoke) OPTS+=(--smoke) ;;
  main) ;;
  *) echo 'kind must be smoke or main' >&2; exit 2 ;;
esac
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$LOG_ROOT/receipts/ex40/${ARM}_${KIND}_${STAMP}_$$"
mkdir -p "$OUT"
"$PY" -m foothold_s2.ex40_launch "${OPTS[@]}" > "$OUT/launch_receipt.json"
"$PY" -m foothold_s2.ex40_launch "${OPTS[@]}" --print-args > "$OUT/launch_args.txt"
"$PY" -m foothold_s2.prestart_check --args-file "$OUT/launch_args.txt" > "$OUT/prestart.json"
mapfile -t ARGS < <(tr -d '\r' < "$OUT/launch_args.txt")
git rev-parse HEAD > "$OUT/git_head.txt"
echo "receipt=$OUT/launch_receipt.json"
if [ "${LIVE:-0}" != "1" ]; then echo 'DRY: training not started'; exit 0; fi
set +e
"$PY" foothold_s2/scripts/train_sb.py "${ARGS[@]}" > "$OUT/run.log" 2>&1
RC=$?
set -e
echo "rc=$RC" > "$OUT/rc.txt"
if [ "$KIND" = smoke ]; then
  "$PY" -m foothold_s2.ex40_kit_smoke --receipt "$OUT/launch_receipt.json" --run-log "$OUT/run.log" --rc "$RC" > "$OUT/kit_check.json"
fi
exit "$RC"
