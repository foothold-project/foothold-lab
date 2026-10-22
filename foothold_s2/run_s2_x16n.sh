#!/usr/bin/env bash
# EX-16 (SONNET-X16b): EX-11 환경 그대로 + 보상만 NVIDIA Go2 rough 보상 세트로 통째 교체. 501 회(model_500 까지) · 100 회마다 저장 (300 · 500 에서 걸음 위상 확인 뒤 판단).
# usage: run_s2_x16n.sh <cuda:N> [추가 train_start 인자...]    (3072 env · seed 42 · run 이름 ex16-nvgo2 · est zero 는 agent cfg)
# 실행 중에는 이 저장소의 소비 코드를 고치지 않는다(manifest 가 저장 때 감시).
set -u
DEV="$1"; shift 1
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_x16n_ex16-nvgo2_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_start.py --task FootholdS2-Go2-S2-X16n-v0 --headless --device "$DEV" \
    --num_envs 3072 --max_iterations 501 --seed 42 --run_name ex16-nvgo2 --map_input none "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
