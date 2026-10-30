#!/usr/bin/env bash
# M02 execution copy. The original run_ex40.sh remains untouched.
set -euo pipefail
ARM="${1:?A or B}"
DEV="${2:?cuda:0 or cuda:1}"
END_BY="${3:?ISO8601 deadline with timezone}"
LOG_ROOT="${4:?absolute isolated log root}"
SCORE_DIR="${5:?absolute score directory}"
KIND="${6:?smoke, main or resume}"
RESUME_SPEC="${7:-}"
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
  resume)
    if [[ -z "$RESUME_SPEC" || ! -f "$RESUME_SPEC" ]]; then
      echo 'resume needs a readable seventh argument: resume spec JSON' >&2; exit 2
    fi
    ;;
  *) echo 'kind must be smoke, main, or resume' >&2; exit 2 ;;
esac
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$LOG_ROOT/receipts/ex40_b11/${ARM}_${KIND}_${STAMP}_$$"
mkdir -p "$OUT"
if [[ "$KIND" == "resume" ]]; then
  RESUME_OPTS=(--resume-spec "$RESUME_SPEC" --arm "$ARM" --device "$DEV" --end-by "$END_BY" --log-root "$LOG_ROOT" --score-dir "$SCORE_DIR")
  "$PY" -m foothold_s2.ex40_launch "${RESUME_OPTS[@]}" > "$OUT/launch_receipt.json"
  "$PY" -m foothold_s2.ex40_launch "${RESUME_OPTS[@]}" --print-args > "$OUT/launch_args.txt"
else
  "$PY" -m foothold_s2.ex40_launch "${OPTS[@]}" > "$OUT/launch_receipt.json"
  "$PY" -m foothold_s2.ex40_launch "${OPTS[@]}" --print-args > "$OUT/launch_args.txt"
fi
"$PY" -m foothold_s2.prestart_check --args-file "$OUT/launch_args.txt" > "$OUT/prestart.json"
git rev-parse HEAD > "$OUT/git_head.txt"
echo "receipt=$OUT/launch_receipt.json"
if [[ "${LIVE:-0}" != "1" ]]; then echo 'DRY: training not started'; exit 0; fi
if [[ "$KIND" == "smoke" ]]; then
  mapfile -t ARGS < <(tr -d '\r' < "$OUT/launch_args.txt")
  set +e
  "$PY" foothold_s2/scripts/train_sb.py "${ARGS[@]}" > "$OUT/run.log" 2>&1
  RC=$?
  set -e
  echo "rc=$RC" > "$OUT/rc.txt"
  "$PY" -m foothold_s2.ex40_kit_smoke --receipt "$OUT/launch_receipt.json" --run-log "$OUT/run.log" --rc "$RC" > "$OUT/kit_check.json"
  exit "$RC"
fi
if [[ -z "${EX40_EXPECTED_FINISH:-}" ]]; then
  echo 'EX40_EXPECTED_FINISH is required for supervised main/resume after a measured throughput estimate' >&2
  exit 2
fi
if [[ "$KIND" == "resume" ]]; then
  SUPERVISOR_SOURCE_RECEIPT="$($PY -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig"))["resume_source_receipt"])' "$OUT/launch_receipt.json")"
else
  SUPERVISOR_SOURCE_RECEIPT="$OUT/launch_receipt.json"
fi
"$PY" -m foothold_s2.ex40_supervisor --supervise --arm "$ARM" --device "$DEV" \
  --args-file "$OUT/launch_args.txt" --launch-receipt "$SUPERVISOR_SOURCE_RECEIPT" \
  --log-root "$LOG_ROOT" --score-out "$LOG_ROOT/score-watch" --score-dir "$SCORE_DIR" \
  --expected-finish "$EX40_EXPECTED_FINISH" --end-by "$END_BY" \
  --ledger "$LOG_ROOT/supervisor-ledger.json" > "$OUT/supervisor_result.json"
cat "$OUT/supervisor_result.json"
