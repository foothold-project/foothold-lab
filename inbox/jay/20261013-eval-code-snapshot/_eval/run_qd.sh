#!/usr/bin/env bash
# QD-E1: low / mid / high difficulty. Declared before launch 2026-10-11 16:12
# (pre-check: GPU1 315d098f 3975 MiB used, pid 25916 on GPU1, E2 pid 173044 on GPU0; neither touched).
#   difficulty : 0.2 · 0.5 · 0.8, the same fixed value for every terrain column (rows all at that value)
#   seed       : 2000 for the terrain generator AND the env RNG (DR, start poses). New evaluation-only mesh,
#                different from Q-E1 (seed 1000). Holdout candidate: not used for any tuning.
#   policy     : deployed student (act_inference), E1 model_20000 and model_20499
#   cells      : Q-E1 main 11 cells x 8 training terrains, tile-centre start, 100 episodes, run as two groups
#                A = flat,wave,slope_up,slope_down  B = rough_slope,stairs_up,stairs_down,obstacles (4400 envs each)
#                + band start (wave, slope_up, slope_down, rough_slope, stairs_up, stairs_down, obstacles x
#                stand, stop03, yawL05, yawR05 x 100; offsets stand/yaw 2.5 m, stop 1.75 m)
#   noise      : ON first (training observation noise, ASTRA proposed main condition), then OFF if budget allows
#   rules      : q_post computes the Q-E1 current definition and the ASTRA proposals (span 51/11 samples, low-speed (a))
#   pairing    : extended fingerprint in meta.json; checked between the two checkpoints afterwards
#   guard      : before each run GPU1 free minus expected use (7.0 GB groups, 6.4 GB band) must stay >= 4 GiB,
#                stop after a run whose recorded peak left < 4 GiB. Budget 7200 s from the probe start:
#                a run is skipped (and listed) if elapsed + its expected time would exceed the budget.
#   stages     : probe (qd02_on_m20000_A, measure the peak) then rest
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
BUDGET=7200
T0FILE=out/qd_t0.txt
free1() { nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}'; }
A=flat,wave,slope_up,slope_down
B=rough_slope,stairs_up,stairs_down,obstacles
BAND="--families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles --cells stand,stop03,yawL05,yawR05 --spawn_offset stand=2.5,yaw=2.5,stop=1.75"
one() {  # tag need_MiB expect_s args...
  local tag=$1 need=$2 exp=$3; shift 3
  if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP"; return 0; fi
  local now=$(date +%s) t0=$(cat $T0FILE)
  if [ $(( now - t0 + exp )) -gt $BUDGET ]; then echo "BUDGET LEFT-OUT $tag"; return 0; fi
  local f=$(free1)
  if [ $(( f - need )) -lt 4096 ]; then echo "STOP before $tag: GPU1 free ${f} MiB - expected ${need} < 4096"; exit 3; fi
  "$PY" q_eval.py --headless --tag "$tag" "$@" > "out/$tag.log" 2>&1
  local rc=$?
  local pf=$("$PY" -c "import json;m=json.load(open('out/$tag/meta.json'));g=lambda s:int(s[1].split(',')[2].split()[0]);print(16303-max(g(m[k]) for k in ('smi_start','smi_after_env','smi_mid','smi_end') if m.get(k)))" 2>/dev/null || echo NA)
  echo "RUN $tag EXIT $rc $(( $(date +%s) - now ))s elapsed=$(( $(date +%s) - t0 ))s peak_free_MiB=$pf $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
  if [ "$pf" != "NA" ] && [ "$pf" -lt 4096 ]; then echo "STOP after $tag: peak free ${pf} MiB < 4096"; exit 5; fi
}
combo() {  # dd noise_flag noise_name it
  local dd=$1 nf=$2 nn=$3 it=$4 d="0.${1:1:1}"
  one "qd${dd}_${nn}_m${it}_A" 7000 130 --policy student --checkpoint "$RUN/model_${it}.pt" --families $A --episodes 100 --difficulty $d --eval_seed 2000 $nf
  one "qd${dd}_${nn}_m${it}_B" 7000 130 --policy student --checkpoint "$RUN/model_${it}.pt" --families $B --episodes 100 --difficulty $d --eval_seed 2000 $nf
  one "qd${dd}_${nn}_m${it}_band" 6500 130 --policy student --checkpoint "$RUN/model_${it}.pt" $BAND --episodes 100 --difficulty $d --eval_seed 2000 $nf
}
case "${1:-}" in
  probe)
    date +%s > $T0FILE
    one qd02_on_m20000_A 7000 130 --policy student --checkpoint "$RUN/model_20000.pt" --families $A --episodes 100 --difficulty 0.2 --eval_seed 2000 --obs_noise
    echo "PROBE DONE";;
  rest)
    for dd in 02 05 08; do for it in 20000 20499; do combo $dd --obs_noise on $it; done; done
    echo "NOISE ON DONE"
    for dd in 05 02 08; do for it in 20000 20499; do combo $dd "" off $it; done; done
    echo "QD DONE";;
  *) echo "usage: run_qd.sh probe|rest"; exit 2;;
esac
