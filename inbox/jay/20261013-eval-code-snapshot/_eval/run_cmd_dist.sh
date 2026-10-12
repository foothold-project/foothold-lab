#!/usr/bin/env bash
# A. Training command distribution (no training). Declared before launch 2026-10-11
# (pre-check: GPU1 315d098f about 4.1 GB used, pid 25916 on GPU1, E2 pid 173044 on GPU0; neither touched).
#   test   : known-answer config (fixed command 0.3/0/0.5, resample 1 s), 1024 envs, 60 + 300 steps, E1 model_20000
#   pre20k : unchanged Go2EnvCfg, env counter = iter 19000 x 24, E1 model_19500, 4096 envs, 300 warm-up + 1500 steps
#   post20k: same, counter = iter 20000 x 24 (code applies the 1.0 range itself), E1 model_20499
#   actions: runner.alg.act (training sampling, teacher 75 % / student 25 %), no update
#   guard  : GPU1 free - need (test 3.5 GB, runs 7.5 GB) >= 4 GiB before each run. Cap 2 h with task B.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
mkdir -p out/cmd_dist
free1() { nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}'; }
one() {  # tag need_MiB args...
  local tag=$1 need=$2; shift 2
  local f; f=$(free1)
  if [ $(( f - need )) -lt 4096 ]; then echo "STOP before $tag: GPU1 free ${f} MiB"; exit 3; fi
  local t0; t0=$(date +%s)
  "$PY" cmd_dist.py --headless --tag "$tag" "$@" > "out/cmd_dist/$tag.log" 2>&1
  echo "CMD $tag EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
}
WHICH=${1:-all}
if [ "$WHICH" = test ] || [ "$WHICH" = all ]; then
  one test 3500 --checkpoint "$RUN/model_20000.pt" --iter 20000 --num_envs 1024 --warmup 60 --steps 300 --test
fi
if [ "$WHICH" = runs ] || [ "$WHICH" = all ]; then
  one pre20k 7500 --checkpoint "$RUN/model_19500.pt" --iter 19000
  one post20k 7500 --checkpoint "$RUN/model_20499.pt" --iter 20000
fi
