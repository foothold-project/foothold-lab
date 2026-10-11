#!/usr/bin/env bash
# Q-E1 observation-noise sensitivity. Declared before launch (2026-10-11):
#   same as the main runs but --obs_noise (training observation noise kept on policy and single_obs)
#   flat and stairs_up, 11 cells x 100, both checkpoints. Starts only after run_expand.sh printed EXPAND DONE.
set -u
cd "$(dirname "$0")"
until grep -q "EXPAND DONE" out/expand_batch.log 2>/dev/null; do sleep 10; done
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
for fam in flat stairs_up; do
  for it in 20000 20499; do
    tag="m${it}_noise_${fam}"
    if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP"; continue; fi
    t0=$(date +%s)
    "$PY" q_eval.py --headless --tag "$tag" --policy student --checkpoint "$RUN/model_${it}.pt" --families "$fam" --episodes 100 --obs_noise > "out/$tag.log" 2>&1
    echo "RUN $tag EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  done
done
echo "NOISE DONE"
