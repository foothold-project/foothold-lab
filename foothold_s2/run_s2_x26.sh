#!/usr/bin/env bash
# EX-26 · EX-27 (SONNET-X26): START 구조 G0 + EX-23 환경. EX-26 = 토크 벌점 -2e-4 하나만 · EX-27 = NVIDIA 보상 세트(진단 대조).
# usage: run_s2_x26.sh <x26|x27> <cuda:N> [추가 train_start 인자...]   (3072 env · seed 42 · 1001 회)
set -u
V="$1"; DEV="$2"; shift 2
case "$V" in x26) TASK=FootholdS2-Go2-S2-X26-v0; RUN=ex26-g0-torque ;; x27) TASK=FootholdS2-Go2-S2-X27-v0; RUN=ex27-g0-nvrew ;; *) echo "x26 또는 x27"; exit 2 ;; esac
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_${V}_${RUN}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_start_x26.py --task "$TASK" --headless --device "$DEV" --num_envs 3072 --max_iterations 1001 --seed 42 --run_name "$RUN" --map_input none "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
