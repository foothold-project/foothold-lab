#!/usr/bin/env bash
# ASTRA 4 part B. Declared before launch 2026-10-11 (pre-check: GPU1 315d098f, 4066 MiB used, pid 25916 on GPU1,
# E2 train pid 173044 on GPU0; neither is touched):
#   stage fp    : pairing confirmation. stairs_up Q-E1 main config (11 cells x 100 = 1100 envs) with
#                 student / teacher / teacher-perm x 20000 / 20499 = 6 runs, --fingerprint_only (stop before the rollout).
#                 Shows the extended DR fingerprint equals across S, T, Tp and both checkpoints, and links it to
#                 the old 4 hashes of the existing runs.
#   stage probe : one noise-on student run (wave, 20000, 1100 envs) to measure the peak GPU use.
#   stage rest  : noise-on student for wave, slope_up, slope_down, rough_slope, stairs_down, obstacles (centre start,
#                 11 cells x 100) and the band-start run (7 rough x 4 cells x 100) for both checkpoints.
#                 = 12 + 2 runs, other settings identical to the Q-E1 main runs. ~25 min.
#   guard       : before each run GPU1 free minus expected use (5.3 GB, band 6.4 GB) must stay >= 4 GiB;
#                 after each run stop if its recorded peak left < 4 GiB free. Cap 2 h.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
free1() { nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}'; }
one() {  # tag expected_MiB args...
  local tag=$1 need=$2; shift 2
  if [ -f "out/$tag/cells.json" ] || [ -f "out/$tag/meta.json" -a "${FP:-0}" = "1" ]; then echo "RUN $tag SKIP"; return 0; fi
  local f=$(free1)
  if [ $(( f - need )) -lt 4096 ]; then echo "STOP before $tag: GPU1 free ${f} MiB - expected ${need} < 4096"; exit 3; fi
  local t0=$(date +%s)
  "$PY" q_eval.py --headless --tag "$tag" "$@" > "out/$tag.log" 2>&1
  local rc=$?
  local peakfree=$("$PY" -c "import json;m=json.load(open('out/$tag/meta.json'));g=lambda s:int(s[1].split(',')[2].split()[0]);print(16303-max(g(m[k]) for k in ('smi_start','smi_after_env','smi_mid','smi_end') if m.get(k)))" 2>/dev/null || echo NA)
  echo "RUN $tag EXIT $rc $(( $(date +%s) - t0 ))s peak_free_MiB=$peakfree $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
  if [ "$peakfree" != "NA" ] && [ "$peakfree" -lt 4096 ]; then echo "STOP after $tag: peak free ${peakfree} MiB < 4096"; exit 5; fi
}
OFF="--families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles --cells stand,stop03,yawL05,yawR05 --spawn_offset stand=2.5,yaw=2.5,stop=1.75"
case "${1:-}" in
  fp)
    export FP=1
    for it in 20000 20499; do
      one "fp_m${it}_stairs_up" 5400 --fingerprint_only --policy student --checkpoint "$RUN/model_${it}.pt" --families stairs_up --episodes 100
      one "fp_t${it}_stairs_up" 5400 --fingerprint_only --policy teacher --checkpoint "$RUN/model_${it}.pt" --families stairs_up --episodes 100
      one "fp_tp${it}_stairs_up" 5400 --fingerprint_only --policy teacher --height_perm_seed 2026 --checkpoint "$RUN/model_${it}.pt" --families stairs_up --episodes 100
    done
    echo "FP DONE";;
  probe)
    one m20000_noise_wave 5400 --policy student --checkpoint "$RUN/model_20000.pt" --families wave --episodes 100 --obs_noise
    echo "PROBE DONE";;
  rest)
    for it in 20000 20499; do
      for fam in wave slope_up slope_down rough_slope stairs_down obstacles; do
        one "m${it}_noise_${fam}" 5400 --policy student --checkpoint "$RUN/model_${it}.pt" --families "$fam" --episodes 100 --obs_noise
      done
      one "m${it}_noise_offplat" 6500 --policy student --checkpoint "$RUN/model_${it}.pt" $OFF --episodes 100 --obs_noise
    done
    echo "REST DONE";;
  *) echo "usage: run_noise6.sh fp|probe|rest"; exit 2;;
esac
