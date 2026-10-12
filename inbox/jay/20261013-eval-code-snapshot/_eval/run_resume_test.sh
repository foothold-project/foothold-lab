#!/usr/bin/env bash
# B. Resume fidelity test. Declared before launch 2026-10-11
# (pre-check: GPU1 315d098f about 4.2 GB used, pid 25916 on GPU1, E2 pid 173044 on GPU0; neither touched).
#   what   : four NEW small training runs of RobotLab-Go2-v0 with the repository's train.py (unchanged, run through
#            resume_probe.py which only adds state dumps), 1024 envs, seed 42, GPU 1, save_interval 33
#              cont   : 0 -> 200 iterations (--max_iterations 200)
#              split1 : 0 -> 100 (--max_iterations 100)
#              split2 : --resume from split1 model_99.pt, --max_iterations 100
#              fix2   : same as split2 with RESUME_FIX=1 (candidate fix applied in the probe, not in the repository)
#   where  : logs under _eval/out/resume_test/logs/rsl_rl/go2_moe_cts/ (cwd), E1 / E2 folders untouched
#   time   : about 5 + 3 + 3 + 3 min (estimate), guard GPU1 free - 5 GB >= 4 GiB before each run. Cap 2 h with task A.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
EVAL=$(pwd)
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
mkdir -p out/resume_test
cd out/resume_test
ROOT=logs/rsl_rl/go2_moe_cts
free1() { nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}'; }
one() {  # name args...
  local name=$1; shift
  local f; f=$(free1)
  if [ $(( f - 5000 )) -lt 4096 ]; then echo "STOP before $name: GPU1 free ${f} MiB"; exit 3; fi
  local t0; t0=$(date +%s)
  "$PY" "$EVAL/resume_probe.py" --task RobotLab-Go2-v0 --headless --num_envs 1024 --seed 42 --run_name "$name" "$@" agent.save_interval=33 > "$name.out" 2>&1
  echo "RT $name EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
}
WHICH=${1:-all}
if [ "$WHICH" = all ] || [ "$WHICH" = cont ]; then one rt_cont --max_iterations 200; fi
if [ "$WHICH" = all ] || [ "$WHICH" = split ]; then
  one rt_split1 --max_iterations 100
  S1=$(ls -d $ROOT/*_rt_split1 | tail -1 | xargs basename)
  one rt_split2 --max_iterations 100 --resume --load_run "$S1" --checkpoint 'model_99.pt$'
  export RESUME_FIX=1; one rt_fix2 --max_iterations 100 --resume --load_run "$S1" --checkpoint 'model_99.pt$'; unset RESUME_FIX
fi
