#!/usr/bin/env bash
# EX-24 (SONNET-X23): v2 작업(V2b)에서 actor 높이 스캔만 뺀 대조판. v2 를 돌린 표준 rsl_rl 학습 스크립트(Isaac Lab train.py)를 그대로 쓴다.
# usage: run_s2_x24.sh <cuda:N> [추가 train.py 인자...]    (4096 env · seed 42 · 1501 회 · 50 회마다 저장 · run 이름 ex24-v2-noscan)
# resume 을 쓰지 않는다: v2 는 NVIDIA 사전학습에서 이어 학습했지만 스캔을 뺀 입력(48 칸)은 사전학습 actor(235 칸)를 읽을 수 없다(처음부터).
# agent.device 도 같은 GPU 로 맞춘다(설치본 train.py 는 --device 를 시뮬에만 적용한다).
set -u
DEV="$1"; shift 1
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_x24_ex24-v2-noscan_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_v2_noscan.py --task FootholdS2-Go2-S2-X24-v0 --headless --device "$DEV" \
    --num_envs 4096 --seed 42 --max_iterations 1501 --run_name ex24-v2-noscan "$@" "agent.device=$DEV" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
