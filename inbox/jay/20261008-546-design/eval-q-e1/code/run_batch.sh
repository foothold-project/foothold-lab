#!/usr/bin/env bash
# Q-E1 batch. Declared before launch (2026-10-11):
#   GPU 1 only: CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 (torch cuda:0 = UUID 315d098f = nvidia-smi 1)
#   one process per (checkpoint, family), 11 cells x 100 episodes = 1100 envs, eval seed 1000, difficulty 0.5
#   expected per run: out/<tag>/{meta.json,traj.npz,episodes.csv,cells.json}, about 2 min
#   skip a tag whose cells.json already exists (re-runnable without repeating finished runs)
#   first: zero-action known-answer run (flat,stairs_up, 10 episodes)
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
mkdir -p out

one() {  # tag, extra args...
  local tag=$1; shift
  if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP (exists)"; return; fi
  local t0=$(date +%s)
  "$PY" q_eval.py --headless --tag "$tag" "$@" > "out/$tag.log" 2>&1
  local rc=$?
  echo "RUN $tag EXIT $rc $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
}

one zero_kat --policy zero --checkpoint "$RUN/model_20000.pt" --families flat,stairs_up --episodes 10
for fam in flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles; do
  for it in 20000 20499; do
    one "m${it}_${fam}" --policy student --checkpoint "$RUN/model_${it}.pt" --families "$fam" --episodes 100
  done
done
echo "BATCH DONE"
