#!/usr/bin/env bash
# S1-a 진단 학습 (4096 env, 시드 42). usage: run_s1_diag.sh <task 접미 D1> <cuda:N> [추가 train_s1 인자...]
# 예) bash foothold_s2/run_s1_diag.sh D1 cuda:0
set -u
V="$1"; DEV="$2"; shift 2
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s1a_diag_${V}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" -m foothold_s2.train_s1 --task "FootholdS2-Go2-S1a-diag-${V}-v0" --headless --device "$DEV" \
    --num_envs 4096 --seed 42 --run_name "S1a-diag-${V}" "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
