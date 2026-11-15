#!/usr/bin/env bash
# Linux baseline (lead-lx 11/10): EX-41 P1 periodic evaluation + score for m12000 (cuda:0) and m13000 (cuda:1).
# usage: linux_baseline_1110.sh print                 print both launch commands (nothing runs)
#        linux_baseline_1110.sh prep                  copy the pinned m6000 push-ladder bundle under $MAI_TMP_ROOT (sha256 checked)
#        linux_baseline_1110.sh run                   m12000 on cuda:0, then m13000 on cuda:1 after BASELINE_STAGGER seconds (90); waits for both
#        linux_baseline_1110.sh run-one m12000|m13000 one checkpoint on its own card
#        linux_baseline_1110.sh compare               m12000 Linux vs Windows score, table only (no verdict)
# Needs the machine env sourced: set -a; . ~/mai/foothold-linux.env; set +a   (ISAAC311_PYTHON, FOOTHOLD_MACHINE_PROFILE, MAI_TMP_ROOT ...). Uses the GPU only in run / run-one.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAB="${BASELINE_LAB_ROOT:-/mnt/win-d/mai/data/foothold/s2_lab}"
NAME="${BASELINE_NAME:-linux-baseline-1110}"
STAGGER="${BASELINE_STAGGER:-90}"
EX41="$LAB/ex41_main_20261104_235522"
EX42="$LAB/ex42_main_20261108_123914"
CK12="${BASELINE_CK_M12000:-$EX41/main/EX-41-B-main_20261104_235522/model_6000.pt}"
SHA12=1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613
CK13="${BASELINE_CK_M13000:-$EX42/main/EX-42-B-stagezero_20261108_123914/model_1000.pt}"
SHA13=20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768
OUT12="$EX41/eval/$NAME/m12000"
OUT13="$EX42/eval/$NAME/m13000"
WIN_SCORE="$EX41/eval/scores/score_6000_1c6af6319c82.json"
WIN_EVAL="$EX41/eval/score-watch/model_6000_1c6af6319c82/evaluation"
PUSH_REL=runner/ex41_push_ladder_m6000_20261103_161418/push_ladder_bundle.json
PUSH_SHA=12ea9beafcb97bfc41a76c95c1c830f686c3d2c93783612dee1b627315add08a
: "${ISAAC311_PYTHON:?ISAAC311_PYTHON is not set (source the machine env file)}"

cmd() {  # name checkpoint sha out device
  printf '%q ' env OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONPATH="$ROOT" "$ISAAC311_PYTHON" -m foothold_s2.ex41_linux_baseline \
    --checkpoint "$2" --expected-sha256 "$3" --out-root "$4" --device "$5" --execute; echo
}
prep() {
  : "${MAI_TMP_ROOT:?MAI_TMP_ROOT is not set}"
  local dst="$MAI_TMP_ROOT/$PUSH_REL" src="/mnt/win-d/mai/tmp/$PUSH_REL"
  if [ -f "$dst" ] && [ "$(sha256sum "$dst" | cut -d' ' -f1)" = "$PUSH_SHA" ]; then echo "push bundle present: $dst"; return 0; fi
  [ -f "$src" ] && [ "$(sha256sum "$src" | cut -d' ' -f1)" = "$PUSH_SHA" ] || { echo "push bundle source missing or sha differs: $src" >&2; exit 2; }
  mkdir -p "$(dirname "$dst")"; cp "$src" "$dst"
  [ "$(sha256sum "$dst" | cut -d' ' -f1)" = "$PUSH_SHA" ] || { echo "copy sha differs: $dst" >&2; exit 2; }
  echo "push bundle copied: $dst"
}
check() {  # checkpoint sha out
  [ -f "$1" ] || { echo "checkpoint missing: $1" >&2; exit 2; }
  [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ] || { echo "checkpoint sha256 differs from ${2:0:8}...: $1" >&2; exit 2; }
  [ ! -e "$3" ] || { echo "output already exists (the evaluation needs an unused one): $3" >&2; exit 2; }
}
one() {
  case "$1" in
    m12000) check "$CK12" "$SHA12" "$OUT12"; mkdir -p "$(dirname "$OUT12")"; cd "$ROOT"; eval "$(cmd m12000 "$CK12" "$SHA12" "$OUT12" cuda:0)" ;;
    m13000) check "$CK13" "$SHA13" "$OUT13"; mkdir -p "$(dirname "$OUT13")"; cd "$ROOT"; eval "$(cmd m13000 "$CK13" "$SHA13" "$OUT13" cuda:1)" ;;
    *) echo "unknown checkpoint: $1" >&2; exit 2 ;;
  esac
}
case "${1:-print}" in
  print) cmd m12000 "$CK12" "$SHA12" "$OUT12" cuda:0; echo "# then after ${STAGGER}s:"; cmd m13000 "$CK13" "$SHA13" "$OUT13" cuda:1 ;;
  prep) prep ;;
  run-one) prep; one "${2:?m12000|m13000}" ;;
  run)
    prep; check "$CK12" "$SHA12" "$OUT12"; check "$CK13" "$SHA13" "$OUT13"
    one m12000 & p12=$!
    sleep "$STAGGER"
    one m13000 & p13=$!
    rc=0; wait "$p12" || rc=$?; r13=0; wait "$p13" || r13=$?
    echo "m12000 rc=$rc m13000 rc=$r13"; [ "$rc" -eq 0 ] && exit "$r13"; exit "$rc" ;;
  compare)
    cd "$ROOT"
    PYTHONPATH="$ROOT" "$ISAAC311_PYTHON" -m foothold_s2.eval.ex41_baseline_compare --windows-score "$WIN_SCORE" --windows-eval "$WIN_EVAL" \
      --linux-root "$OUT12" --json "$OUT12/compare_vs_windows.json" ;;
  *) echo "usage: $0 print|prep|run|run-one m12000|m13000|compare" >&2; exit 2 ;;
esac
