#!/usr/bin/env bash
# Branch runner gates and CMD-R rollout test (no experiment training). Declared before launch 2026-10-11
# (pre-check: GPU1 315d098f about 4.1 GB used, pid 25916 on GPU1, E2 pid 173044 on GPU0; neither touched).
#   refuse : branch_run.py without --gate and without BRANCH_CONTRACT_CONFIRMED must exit 4 (checked first, no GPU)
#   a      : parent = resume_test continuous run model_99.pt (fake L=99), seed 1042, 1024 envs, 3 updates
#   b      : parent = E1 model_20000.pt (read only), seed 1042, 1024 envs, 1 update
#   c      : A/A, parent E1 model_20000, seed 1042, 1024 envs, 2 updates, run twice
#   cmdr   : parent E1 model_20000, seed 1042, 4096 envs, rollout only 1500 steps (30 s), adapter off then on
#   guard  : GPU1 free - expected (1024 training 6.5 GB, 4096 rollout 7.5 GB) >= 4 GiB before each run. Cap 2 h.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
RT=$(ls -d ../out/resume_test/logs/rsl_rl/go2_moe_cts/*_rt_cont | tail -1)
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
unset BRANCH_CONTRACT_CONFIRMED
mkdir -p ../out/branch
free1() { nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}'; }
one() {  # tag need args...
  local tag=$1 need=$2; shift 2
  if [ -f "../out/branch/$tag/result.json" ]; then echo "RUN $tag SKIP"; return 0; fi
  local f=$(free1)
  if [ $(( f - need )) -lt 4096 ]; then echo "STOP before $tag: GPU1 free ${f} MiB"; exit 3; fi
  local t0=$(date +%s)
  "$PY" branch_run.py --headless --tag "$tag" "$@" > "../out/branch/$tag.log" 2>&1
  local rc=$?
  echo "RUN $tag EXIT $rc $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
}
case "${1:-all}" in
  refuse)
    "$PY" branch_run.py --tag refuse_test --parent "$E1/model_20000.pt" --seed 1042 --num_envs 1024 --updates 1; echo "refuse exit $?"
    "$PY" branch_run.py --tag refuse_test --parent "$E1/model_20000.pt" --seed 1042 --num_envs 1024 --updates 4 --gate; echo "gate-limit exit $?";;
  a) one gate_a 6500 --parent "$RT/model_99.pt" --seed 1042 --num_envs 1024 --updates 3 --gate;;
  a2) one gate_a2 6500 --parent "$RT/model_99.pt" --seed 1042 --num_envs 1024 --updates 3 --gate;;
  b) one gate_b 6500 --parent "$E1/model_20000.pt" --seed 1042 --num_envs 1024 --updates 1 --gate;;
  c) one gate_c1 6500 --parent "$E1/model_20000.pt" --seed 1042 --num_envs 1024 --updates 2 --gate
     one gate_c2 6500 --parent "$E1/model_20000.pt" --seed 1042 --num_envs 1024 --updates 2 --gate;;
  cmdr) one cmdr_off 7500 --parent "$E1/model_20000.pt" --seed 1042 --num_envs 4096 --rollout_steps 1500 --cmdr off --gate
        one cmdr_on 7500 --parent "$E1/model_20000.pt" --seed 1042 --num_envs 4096 --rollout_steps 1500 --cmdr on --gate;;
  *) echo "usage: run_gates.sh refuse|a|b|c|cmdr"; exit 2;;
esac
