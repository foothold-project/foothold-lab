#!/usr/bin/env bash
# D1-B harness checks and smoke (NOT the D1-B main evaluation). Declared before launch 2026-10-11
# (pre-check: GPU1 315d098f 4139 MiB used, pid 25916 on GPU1, E2 pid 173044 on GPU0; neither touched).
#   process : one Isaac process per call, 1200 envs (12 validation cells x 100 episode ids 1000..1099),
#             terrain 1 row x 6 columns: flat, gap010, gap020, gap030 (validation) + step010, gapwide060 (smoke only)
#   policy  : E1 model_20000 (teacher mean for the contract run, student / zero action in the smoke scenarios)
#   stages  : geom, g0, settle (1 s PD + 2 restores + 50-step replay), dyn (300 steps), fall (150), foot (50)
#   holdout : seed 22000 layout generated and geometry-checked on CPU only; no robot, no policy
#   guard   : start only if GPU1 free - 5600 MiB >= 4096 MiB; report the recorded peak. Cap 2 h in total.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
STAGES=${1:-geom,g0,settle,dyn,fall,foot}
TAG=${2:-d1b_harness}
f=$(nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}')
if [ $(( f - 5600 )) -lt 4096 ]; then echo "STOP: GPU1 free ${f} MiB"; exit 3; fi
t0=$(date +%s)
"$PY" d1b_harness.py --headless --checkpoint "$RUN/model_20000.pt" --stages "$STAGES" --tag "$TAG" ${EXTRA:-} > "out/$TAG.log" 2>&1
echo "D1B EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
