#!/usr/bin/env bash
# S2-G0 진단 판 (lead 10/21: G0-open · G0-start, 3072 env, 시드 42, 1501 회). usage: run_s2_diag.sh <open|start> <cuda:N> [추가 train_start 인자...]
#   rl 의 train_start.py(지도 입력 none = G0)를 그대로 쓴다. 이어 학습은 train_start.py 의 --resume_from 규칙을 따른다.
set -u
V="$1"; DEV="$2"; shift 2
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_diag_G0-${V}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_start.py --task "FootholdS2-Go2-S2-diag-G0-${V}-v0" --headless --device "$DEV" \
    --num_envs 3072 --max_iterations 1501 --seed 42 --run_name "diag-G0-${V}" --map_input none "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
