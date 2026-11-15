#!/usr/bin/env bash
# E1 full-record re-runs and the E2 evaluation list. Declared 2026-10-12 (lead decision: evaluate E2, no training).
#   GPU    : $GPU (0 after E2 has finished; never while E2 runs). Every run goes through gpu_guard.py
#            (200 ms NVML sampling, the run is stopped if free memory < 4096 MiB; the sampler ends with the run).
#   stages : e1fr  E1 model_20000 / model_20499, Q main noise off (8 families + band), --full_record.
#                  Must reproduce the stored GPU 1 runs (traj compared bitwise afterwards).
#            e2q   E2 model_20000 / model_20499, Q main noise off with --full_record, then noise on
#            e2c   E2 capability curve: 5000 10000 15000 19500 noise on, 19500 noise off
#            e2d1  E2 D1-A: teacher normal and height permutation 2026, 20000 / 20499, Q main + band, noise off
#            e2qd  E2 difficulty 0.2 / 0.5 / 0.8 x noise on / off, seed 2000, groups A / B / band, 20000 / 20499
#   all settings are the q_eval.py defaults used for E1 (seed 1000, difficulty 0.5, 100 episodes); no training
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
E2=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192
GPU=${GPU:-0}
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$GPU OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
FAMS="flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles"
OFF="--families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles --cells stand,stop03,yawL05,yawR05 --spawn_offset stand=2.5,yaw=2.5,stop=1.75"
A=flat,wave,slope_up,slope_down
B=rough_slope,stairs_up,stairs_down,obstacles
one() {  # tag args...
  local tag=$1; shift
  if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP"; return 0; fi
  local t0=$(date +%s)
  "$PY" gpu_guard.py --gpu "$GPU" --log "out/$tag.log" --summary "out/$tag.guard.json" -- "$PY" q_eval.py --headless --tag "$tag" "$@"
  local rc=$?
  echo "RUN $tag GPU$GPU EXIT $rc $(( $(date +%s) - t0 ))s $(date +%H:%M:%S)"
  if [ "$rc" = "99" ]; then echo "STOP: guard stopped $tag (free < 4 GiB)"; exit 99; fi
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
}
qmain() {  # prefix ckpt_dir it noise(on|off) extra...
  local pre=$1 dir=$2 it=$3 nn=$4; shift 4
  local nf="" mid=""
  if [ "$nn" = on ]; then nf="--obs_noise"; mid="noise_"; fi
  for fam in $FAMS; do one "${pre}m${it}_${mid}${fam}" --policy student --checkpoint "$dir/model_${it}.pt" --families "$fam" --episodes 100 $nf "$@"; done
  one "${pre}m${it}_${mid}offplat" --policy student --checkpoint "$dir/model_${it}.pt" $OFF --episodes 100 $nf "$@"
}
case "${1:-}" in
  e1fr) for it in 20000 20499; do qmain fr_ "$E1" $it off --full_record; done; echo "E1FR DONE";;
  e2q)  for it in 20000 20499; do qmain e2_ "$E2" $it off --full_record; done
        for it in 20000 20499; do qmain e2_ "$E2" $it on; done; echo "E2Q DONE";;
  e2c)  for it in 19500 15000 10000 5000; do qmain e2_ "$E2" $it on; done; qmain e2_ "$E2" 19500 off; echo "E2C DONE";;
  e2d1) for it in 20000 20499; do
          for fam in $FAMS; do
            one "e2_t${it}_${fam}" --policy teacher --checkpoint "$E2/model_${it}.pt" --families "$fam" --episodes 100
            one "e2_tp${it}_${fam}" --policy teacher --height_perm_seed 2026 --checkpoint "$E2/model_${it}.pt" --families "$fam" --episodes 100
          done
          one "e2_t${it}_offplat" --policy teacher --checkpoint "$E2/model_${it}.pt" $OFF --episodes 100
          one "e2_tp${it}_offplat" --policy teacher --height_perm_seed 2026 --checkpoint "$E2/model_${it}.pt" $OFF --episodes 100
        done; echo "E2D1 DONE";;
  e2qd) for nn in on off; do nf=""; [ "$nn" = on ] && nf="--obs_noise"
          for dd in 02 05 08; do d="0.${dd:1:1}"
            for it in 20000 20499; do
              one "e2_qd${dd}_${nn}_m${it}_A" --policy student --checkpoint "$E2/model_${it}.pt" --families $A --episodes 100 --difficulty $d --eval_seed 2000 $nf
              one "e2_qd${dd}_${nn}_m${it}_B" --policy student --checkpoint "$E2/model_${it}.pt" --families $B --episodes 100 --difficulty $d --eval_seed 2000 $nf
              one "e2_qd${dd}_${nn}_m${it}_band" --policy student --checkpoint "$E2/model_${it}.pt" $OFF --episodes 100 --difficulty $d --eval_seed 2000 $nf
            done; done; done; echo "E2QD DONE";;
  *) echo "usage: GPU=0 bash run_e2.sh e1fr|e2q|e2c|e2d1|e2qd"; exit 2;;
esac
