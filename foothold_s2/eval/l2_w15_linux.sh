#!/usr/bin/env bash
# L2 (LINUX-DAY-EXPERIMENT-ORDER): EX-38 m3001 W15 evaluation on ai-lx01, GPU0 (cuda:0 by default; L2_DEVICE=cuda:1 and L2_OUT=<new dir> select the other card / output root), same arguments as the Windows reference.
# usage: l2_w15_linux.sh print     print the launch command (nothing runs)
#        l2_w15_linux.sh run       evaluate (lead starts this; uses the GPU, Kit, OMNI_KIT_ACCEPT_EULA=YES)
#        l2_w15_linux.sh compare   w15_compare.py: (reference ex38/m3001 vs Linux) and (Windows cuda0 vs cuda1 width)
# Needs the machine env file sourced: set -a; . ~/mai/foothold-linux.env; set +a   (ISAAC311_PYTHON, FOOTHOLD_MACHINE_PROFILE, ISAAC_CACHE_ROOT, FOOTHOLD_BASH ...)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAB="${L2_LAB_ROOT:-/mnt/win-d/mai/data/foothold/s2_lab}"
RUNS="$LAB/basic_gait_runs"
CK="${L2_CHECKPOINT:-$RUNS/main/EX-38-basic-e1rew_20261029_123840_163180/model_3001.pt}"
CK_SHA=7ff575f356c27ab6280fa2e01dce40f806bbfdd89d4306ae63c827b3ff16706c
OUT="${L2_OUT:-$RUNS/eval_w15/ex38_linux}"
DEV="${L2_DEVICE:-cuda:0}"
case "$DEV" in cuda:0|cuda:1) ;; *) echo "L2_DEVICE must be cuda:0 or cuda:1 (got $DEV)" >&2; exit 2 ;; esac
REF_ROOT="$RUNS/eval_w15"
COMPARE="${W15_COMPARE:-$HOME/mai/wt/mai-os/ledger/tools/w15_compare.py}"
: "${ISAAC311_PYTHON:?ISAAC311_PYTHON is not set (source the machine env file)}"
CMD=(env OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONPATH="$ROOT" "$ISAAC311_PYTHON" -m foothold_s2.basic_gait_eval_chain_v3 --device "$DEV" --checkpoint "$CK" --out "$OUT")
case "${1:-print}" in
  print) printf '%q ' "${CMD[@]}"; echo ;;
  run)
    [ -f "$CK" ] || { echo "checkpoint missing: $CK" >&2; exit 2; }
    [ "$(sha256sum "$CK" | cut -d' ' -f1)" = "$CK_SHA" ] || { echo "checkpoint sha256 differs from 7ff575f3..." >&2; exit 2; }
    [ ! -e "$OUT" ] || { echo "output root already exists (the chain needs an unused one): $OUT" >&2; exit 2; }
    cd "$ROOT"
    "${CMD[@]}" ;;
  compare)
    REF="$(ls -d "$REF_ROOT"/ex38/m3001/attempt_*/map64/map_modes.json | head -1)"
    NEW="$(ls -d "$OUT"/m3001/attempt_*/map64/map_modes.json | head -1)"
    C0="$(ls -d "$REF_ROOT"/ex38_repeat/cuda0/m3001/attempt_*/map64/map_modes.json | head -1)"
    C1="$(ls -d "$REF_ROOT"/ex38_repeat/cuda1/m3001/attempt_*/map64/map_modes.json | head -1)"
    rc=0
    echo "== reference ex38/m3001 (Windows) vs Linux"; "$ISAAC311_PYTHON" "$COMPARE" "$REF" "$NEW" --json "$OUT/compare_ref_vs_linux.json" || rc=$?
    echo "== Windows width: cuda0 vs cuda1"; "$ISAAC311_PYTHON" "$COMPARE" "$C0" "$C1" --json "$OUT/compare_windows_cuda0_vs_cuda1.json" || true
    exit $rc ;;
  *) echo "usage: $0 print|run|compare" >&2; exit 2 ;;
esac
