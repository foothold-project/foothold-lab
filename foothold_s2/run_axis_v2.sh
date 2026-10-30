#!/usr/bin/env bash
# W57 CPU-prepared Kit entry. The lead runs this only after inspecting the frozen code.
# usage: bash foothold_s2/run_axis_v2.sh <checkpoint> <fresh-output-dir> <cuda:N> <envs> <level> <steps>
set -euo pipefail

CK="${1:?checkpoint required}"
OUT="${2:?fresh output directory required}"
DEV="${3:?cuda:N required}"
ENVS="${4:?env count required}"
LEVEL="${5:?fixed level required}"
STEPS="${6:?control steps required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311

[ -f "$CK" ] || { echo "checkpoint missing: $CK" >&2; exit 3; }
[ ! -e "$OUT" ] || { echo "output already exists: $OUT" >&2; exit 3; }
[[ "$DEV" =~ ^cuda:[01]$ ]] || { echo "device must be cuda:0 or cuda:1" >&2; exit 3; }
[[ "$ENVS" =~ ^[1-9][0-9]*$ && "$LEVEL" =~ ^[0-9]$ && "$STEPS" =~ ^[1-9][0-9]*$ ]] || exit 3
[ "$STEPS" -ge 4 ] || exit 3
cd "$ROOT"
[ -z "$(git status --short -- foothold_s2)" ] || { echo "evaluation code is dirty" >&2; exit 3; }

export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" PYTHONPATH="$ROOT" OMNI_KIT_ACCEPT_EULA=YES
export CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE PYTHONUTF8=1
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
sha256sum "$CK" > "$OUT/checkpoint_sha256.txt"
rc=0
"$ENV/python.exe" -m foothold_s2.eval.eval_map_modes \
    --task FootholdS2-Go2-S2-SB-v0 --checkpoint "$CK" --out "$OUT" \
    --axis-v2 --modes eval_gt,eval_pred,probe_prop_only \
    --fixed-terrain --fixed-level "$LEVEL" --terrain-set default \
    --envs "$ENVS" --steps "$STEPS" --headless --device "$DEV" \
    --kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache \
    > "$OUT/run.log" 2>&1 || rc=$?
printf 'child_rc=%s\n' "$rc" > "$OUT/rc.txt"
[ "$rc" -eq 0 ] && [ -f "$OUT/axis_v2.json" ] && grep -q 'AXIS_V2_DONE' "$OUT/run.log" || {
    echo "W57 receipt missing or child failed" >&2
    exit 5
}
sha256sum "$OUT/axis_v2.json" > "$OUT/result_sha256.txt"
echo "W57 output: $OUT/axis_v2.json"
