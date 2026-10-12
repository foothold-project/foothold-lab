#!/usr/bin/env bash
# D1-B main evaluation runner. NOT RUN in the harness task. Starts only after the lead confirms the D1-B contract:
#   D1B_CONTRACT_CONFIRMED=<reference to the lead's confirmation> bash run_d1b_main.sh model_20000
# Protocol (D1B-harness.md 5): one process per condition, identical pre-start sequence (env build, manifest DR,
# 1 s PD settle, one restore), so the start state including PhysX contact state is identical across conditions.
#   conditions : legacy-normal, legacy-perm2026, g0plus-normal, g0plus-perm2026 (teacher mean), student (control)
#   cells      : flat / gap 0.10 / 0.20 / 0.30 x body direction 0 / 45 / 90 deg, 100 episode ids 1000..1099, 20 s
#   guard      : GPU1 only; free - 5600 MiB >= 4096 MiB before each process; pid 25916 and GPU0 untouched
#   expected   : about 2 min per process (estimate from the harness dyn stage), 10 min per checkpoint
set -u
cd "$(dirname "$0")"
if [ -z "${D1B_CONTRACT_CONFIRMED:-}" ]; then echo "REFUSED: D1-B contract not confirmed by the lead"; exit 4; fi
CK=${1:?checkpoint name, e.g. model_20000}
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
TAG=D1B-gap-v1_E1-s42-${CK}
echo "contract: ${D1B_CONTRACT_CONFIRMED}" > "out/${TAG}.contract.txt"
for C in legacy-normal legacy-perm2026 g0plus-normal g0plus-perm2026 student; do
  f=$(nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}')
  if [ $(( f - 5600 )) -lt 4096 ]; then echo "STOP: GPU1 free ${f} MiB"; exit 3; fi
  t0=$(date +%s)
  "$PY" d1b_harness.py --headless --checkpoint "$RUN/${CK}.pt" --stages main --layout main --cond "$C" --tag "$TAG" > "out/${TAG}_${C}.log" 2>&1
  echo "D1B-MAIN $C EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
done
"$PY" d1b_pair_check.py "out/${TAG}"
