#!/usr/bin/env bash
# G0 GPU probe. Declared before launch 2026-10-11 (pre-check: GPU1 315d098f 3963 MiB used, pid 25916 on GPU1,
# E2 pid 173044 on GPU0; neither touched): one process, 1000 teleported robots, no physics step, no policy.
#   8 training terrains + eval-only gap and stepping_stones columns (10 x 10 tiles, difficulty 0..1 by row),
#   0.5 m pose grid on every tile + two lines through the 25 m border and 10 m beyond. ~33k poses x 187 rays.
#   guard: start only if GPU1 free - 5.4 GB >= 4 GiB; report the recorded peak. Cap 1 h.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
f=$(nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}')
if [ $(( f - 5400 )) -lt 4096 ]; then echo "STOP: GPU1 free ${f} MiB"; exit 3; fi
t0=$(date +%s)
"$PY" g0_probe.py --headless > out/g0_probe.log 2>&1
echo "G0 EXIT $? $(( $(date +%s) - t0 ))s $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
