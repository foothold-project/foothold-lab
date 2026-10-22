#!/usr/bin/env bash
# EX-16 (SONNET-X16): EX-15(EX-11 + legged_gym A1 기저 묶음) + motion_trot -0.1 한 항.
# usage: run_s2_x16.sh <cuda:N> [추가 train_start 인자...]    (3072 env · seed 42 · 1501 회 · run 이름 ex16-lgA1-trot · est zero 는 agent cfg)
# 실행 중에는 이 저장소의 소비 코드를 고치지 않는다(manifest 가 저장 때 감시).
set -u
DEV="$1"; shift 1
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_x16_ex16-lgA1-trot_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_start.py --task FootholdS2-Go2-S2-X16-v0 --headless --device "$DEV" \
    --num_envs 3072 --max_iterations 1501 --seed 42 --run_name ex16-lgA1-trot --map_input none "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
