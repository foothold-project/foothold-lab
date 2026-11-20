#!/usr/bin/env bash
# New E2 v1 boundary evaluation by MAP GAIN (sonnet-code-lx 11/20 · planner DESIGN-E2-V1-1120.md v1.1 section 4). Reuses the map-gain frame of 11/20:
# one eval child per (kind, speed, seed, run) on a GPU, then ex42_v1_mapgain_boundary.py judges and writes ladder_outcomes_list.json.
#   usage: ex42_v1_boundary_eval.sh --checkpoint <model_N.pt> --iter N --caps A/gaps=1,A/balance_beams=1,C/box=5 --out <eval/scores/mN> [--gpus 0,1] [--lanes-per-gpu 2] [--print]
# Inputs per (kind, speed, seed): main run = right map + reconstructed map + map off; flat run; 20 cm shifted run (5 inputs, 64 envs, 300 steps).
# --print only lists the runs. Evaluation only: no training, no run folder is touched except --out.
set -u
CK=""; IT=""; CAPS=""; OUT=""; GPUS="0,1"; LPG=2; PRINT=0; SEEDS="42 43 44"
MESH=${V1_MESH:-/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv}            # gap and beam kinds
MESH_BOX=${V1_MESH_BOX:-/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1118_edge/seed42_E0_c333_flags_E2_1111_v2_edge}   # C/box (the 11/20 tables)
while [ $# -gt 0 ]; do case "$1" in
  --checkpoint) CK=$2; shift 2;; --iter) IT=$2; shift 2;; --caps) CAPS=$2; shift 2;; --out) OUT=$2; shift 2;;
  --gpus) GPUS=$2; shift 2;; --lanes-per-gpu) LPG=$2; shift 2;; --seeds) SEEDS=$2; shift 2;; --print) PRINT=1; shift;; *) echo "unknown $1" >&2; exit 2;; esac; done
[ -n "$CK" ] && [ -n "$IT" ] && [ -n "$CAPS" ] && [ -n "$OUT" ] || { sed -n 2,7p "$0"; exit 2; }
[ -f "$CK" ] || { echo "no checkpoint $CK" >&2; exit 3; }
HERE=$(cd "$(dirname "$0")/.." && pwd); SRC=$(dirname "$HERE")
PY=${ISAAC_PY:-/home/jay/miniforge3/envs/isaac311/bin/python}
CHILD=$HERE/tools/ex42_v1_child_map.py
RUNS=$OUT/mapgain_runs; mkdir -p "$RUNS"
IFS=, read -ra GL <<< "$GPUS"; NL=$(( ${#GL[@]} * LPG ))
JOBS=(); i=0
for item in ${CAPS//,/ }; do
  KIND=${item%=*}; LV=${item#*=}; FAM=${KIND%/*}; NAME=${KIND#*/}; MS=$MESH; [ "$NAME" = box ] && MS=$MESH_BOX
  for V in 0.7 1.0; do for S in $SEEDS; do for run in main flat shift20; do
    case $run in main) SW=none; MD=eval_gt,eval_pred,probe_prop_only;; flat) SW=flat; MD=eval_gt;; shift20) SW=cm20; MD=eval_gt;; esac
    JOBS+=("$((i % NL))|${FAM}_${NAME}_L${LV}_v${V}_s${S}_${run}|$FAM|$NAME|$LV|$V|$S|$SW|$MD|$MS"); i=$((i+1))
  done; done; done
done
if [ $PRINT = 1 ]; then printf '%s\n' "${JOBS[@]}"; echo "jobs ${#JOBS[@]} lanes $NL"; exit 0; fi
set -a; . ~/mai/foothold-linux.env >/dev/null 2>&1; set +a
KIT="--headless --kit_args=--/UJITSO/datastore/localCachePath=/home/jay/mai/cache/isaacsim-5.1/DerivedDataCache"
one() {   # lane|tag|fam|name|level|speed|seed|swap|modes|mesh
  IFS='|' read -r lane tag fam name lv V S SW MD MS <<< "$1"
  local gpu=${GL[$((lane % ${#GL[@]}))]} D=$RUNS/$tag
  [ -f "$D/DONE" ] && return 0
  mkdir -p "$D"
  local nm cases; nm=$(echo "$MD" | tr ',' '\n' | wc -l); cases=$(for _ in $(seq "$nm"); do printf '%s/0/0;' "$V"; done); cases=${cases%;}
  (
    export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=$gpu CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$SRC
    [ "$SW" = none ] || export MAPSWAP=$SW
    cd "$SRC" && EST_SAVE_O=0 PROBE_CASES="$cases" PROBE_EXTRA="$D/extra" timeout -s KILL 1500 "$PY" -B "$CHILD" \
      --task FootholdS2-Go2-S2-SB-v0 --checkpoint "$CK" --envs 64 --steps 300 --modes "$MD" --command-suite core --commands fwd0.5 \
      --fixed-terrain --fixed-level "$lv" --mesh-dir "$MS" --ex42-kind-family "$fam" --ex42-kind-name "$name" --eval-seed "$S" --out "$D" --device cuda:0 $KIT \
      2> "$D/stderr.log" < /dev/null | grep -a -v getMaterialFromInternalFaceIndex > "$D/stdout.log"
    rc=${PIPESTATUS[0]}; ok=0; [ "$rc" = 0 ] && ! grep -aq Traceback "$D/stderr.log" "$D/stdout.log" && ok=1
    if [ "$SW" != none ] && [ $ok = 1 ]; then   # flat / shift20: the swap must really have happened (swapped_calls > 0), else the run is a failure
      grep -a MAPPROBE "$D/stdout.log" | tail -1 | grep -aEq 'swapped_calls[^0-9]+[1-9][0-9]*' || ok=0
    fi
    [ $ok = 1 ] && touch "$D/DONE"
    echo "$(date +%H:%M:%S) $tag lane=$lane gpu=$gpu rc=$rc tb=$(cat "$D"/std*.log | grep -ac Traceback) $(grep -a MAPPROBE "$D/stdout.log" | tail -1)" >> "$OUT/mapgain_eval.log"
  )
}
for lane in $(seq 0 $((NL-1))); do
  ( for j in "${JOBS[@]}"; do [ "${j%%|*}" = "$lane" ] && one "$j"; done ) &
done
wait
bad=0; for j in "${JOBS[@]}"; do IFS='|' read -r _ tag _ <<< "$j"; [ -f "$RUNS/$tag/DONE" ] || { echo "missing DONE $tag" >&2; bad=$((bad+1)); }; done
[ $bad = 0 ] || { echo "$bad runs missing, not judging" >&2; exit 4; }
exec "$PY" -I -B -c "import sys;sys.path.insert(0,'$SRC');from foothold_s2.tools.ex42_v1_mapgain_boundary import main;raise SystemExit(main(sys.argv[1:]))" \
  --root "$RUNS" --kinds "$CAPS" --mesh-dir "$MESH" --mesh-dir-box "$MESH_BOX" --boundary $(( IT / 250 )) --out "$OUT" --checkpoint "$CK" ${V1_EARLIER:+--earlier "$V1_EARLIER"}   # without V1_EARLIER the judge finds the nearest earlier m<N>/ladder_outcomes_list.json next to --out
