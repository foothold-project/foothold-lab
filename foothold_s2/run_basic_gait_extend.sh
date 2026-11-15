#!/usr/bin/env bash
# Receipt first. LIVE=1 is required to start training after EX-36 completes.
set -euo pipefail
ARM="${1:?A or B}"
DEV="${2:?cuda:0 or cuda:1}"
PARENT="${3:?completed EX-36 checkpoint}"
PARENT_SHA="${4:?full SHA256 of completed checkpoint}"
ADDITIONAL="${5:?additional update count}"
END_BY="${END_BY:?timezone-aware deadline required}"
BASIC_LOG_ROOT="${BASIC_LOG_ROOT:?absolute log root required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
PY="$ENV/python.exe"
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE PYTHONUTF8=1
export PYTHONPATH="$ROOT"
cd "$ROOT"
OPTS=(--arm "$ARM" --device "$DEV" --parent "$PARENT" --parent-sha256 "$PARENT_SHA" \
      --additional-updates "$ADDITIONAL" --end-by "$END_BY" --log-root "$BASIC_LOG_ROOT")
if [ -n "${STOP_FILE:-}" ]; then OPTS+=(--stop-file "$STOP_FILE"); fi
if [ "${FAST_GT_ONLY:-0}" = "1" ]; then OPTS+=(--fast-gt-only); fi
if [ -n "${BASIC_FEET_REG_WEIGHT:-}" ]; then OPTS+=(--basic-feet-regulation-weight "$BASIC_FEET_REG_WEIGHT"); fi
if [ -n "${BASIC_TRACK_ANG_WEIGHT:-}" ]; then OPTS+=(--basic-track-ang-weight "$BASIC_TRACK_ANG_WEIGHT"); fi
if [ -n "${BASIC_TRACK_LIN_WEIGHT:-}" ]; then OPTS+=(--basic-track-lin-weight "$BASIC_TRACK_LIN_WEIGHT"); fi
if [ -n "${BASIC_JOINT_ACC_WEIGHT:-}" ]; then OPTS+=(--basic-joint-acc-weight "$BASIC_JOINT_ACC_WEIGHT"); fi
if [ -n "${BASIC_HIP_POS_WEIGHT:-}" ]; then OPTS+=(--basic-hip-pos-weight "$BASIC_HIP_POS_WEIGHT"); fi
if [ "${BASIC_LIN_VEL_Z_SCHEDULE:-0}" = "1" ]; then OPTS+=(--basic-lin-vel-z-schedule); fi
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BASIC_LOG_ROOT/receipts/extend/EX-36${ARM}_${STAMP}_$$"
mkdir -p "$OUT"
"$PY" -m foothold_s2.basic_gait_extend_launch "${OPTS[@]}" > "$OUT/launch_receipt.json"
"$PY" -m foothold_s2.basic_gait_extend_launch "${OPTS[@]}" --print-args > "$OUT/launch_args.txt"
mapfile -t ARGS < <(tr -d '\r' < "$OUT/launch_args.txt")
"$PY" -m foothold_s2.prestart_check --args-file "$OUT/launch_args.txt" > "$OUT/prestart.json"
[ "${#ARGS[@]}" -gt 20 ] || { echo "refused: incomplete training argv" >&2; exit 5; }
[ "$(printf '%s\n' "${ARGS[@]}" | grep -Fxc -- '--kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache')" = "1" ] || { echo "refused: Kit cache argument missing or duplicated" >&2; exit 5; }
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
echo "receipt=$OUT/launch_receipt.json"
if [ "${LIVE:-0}" != "1" ]; then echo "DRY: training not started"; exit 0; fi
[ -z "$(git status --short foothold_s2)" ] || { echo "refused: foothold_s2 dirty" >&2; exit 3; }
set +e
"$PY" foothold_s2/scripts/train_sb.py "${ARGS[@]}" > "$OUT/run.log" 2>&1
RC=$?
set -e
echo "rc=$RC" > "$OUT/rc.txt"
exit "$RC"
