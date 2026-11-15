#!/usr/bin/env bash
# Q-E1 off-platform batch. Declared before launch (2026-10-11):
#   same GPU 1 settings as run_batch.sh; 7 rough families x 4 in-place cells x 100 = 2800 envs per run
#   start offset along +x (LEAD_TEMP): stand 2.5 m, yaw 2.5 m, stop 1.75 m from tile centre, ground z from ray hits
#   expected meta.spawn_base_above_footprint_max_m min >= ~0.3 (no spawn inside terrain)
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
for it in 20000 20499; do
  tag="m${it}_offplat"
  if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP"; continue; fi
  t0=$(date +%s)
  "$PY" q_eval.py --headless --tag "$tag" --policy student --checkpoint "$RUN/model_${it}.pt" \
    --families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles \
    --cells stand,stop03,yawL05,yawR05 --episodes 100 --spawn_offset stand=2.5,yaw=2.5,stop=1.75 > "out/$tag.log" 2>&1
  echo "RUN $tag EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
done
echo "OFFPLAT DONE"
