#!/usr/bin/env bash
# Q-E1 heading-hold batch. Declared before launch (2026-10-11):
#   1) repro_m20000_flat: current q_eval.py, heading hold OFF, must equal out/m20000_flat bit for bit
#      (traj) and its recorded cmd_hist must equal the schedule reconstruction
#   2) LEAD_TEMP variant (not Q as written): lin cells only, wz_cmd = clip(0.5*wrap(heading0-heading), +-0.5)
#      groups A=flat,wave,slope_up,slope_down  B=rough_slope,stairs_up,stairs_down,obstacles, 7 cells x 100 = 2800 envs
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
one() {
  local tag=$1; shift
  if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP"; return; fi
  local t0=$(date +%s)
  "$PY" q_eval.py --headless --tag "$tag" "$@" > "out/$tag.log" 2>&1
  echo "RUN $tag EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
}
one repro_m20000_flat --policy student --checkpoint "$RUN/model_20000.pt" --families flat --episodes 100
LIN=fwd01,fwd02,fwd03,fwd05,back03,left03,right03
for it in 20000 20499; do
  one "m${it}_hh_A" --policy student --checkpoint "$RUN/model_${it}.pt" --families flat,wave,slope_up,slope_down --cells $LIN --episodes 100 --heading_hold 0.5 --heading_clip 0.5
  one "m${it}_hh_B" --policy student --checkpoint "$RUN/model_${it}.pt" --families rough_slope,stairs_up,stairs_down,obstacles --cells $LIN --episodes 100 --heading_hold 0.5 --heading_clip 0.5
done
echo "HH DONE"
