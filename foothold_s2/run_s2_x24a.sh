#!/usr/bin/env bash
# EX-24a (SONNET-X24b): v2 그대로(Isaac-Velocity-V2b-Unitree-Go2-v0, 높이 스캔 포함)를 NVIDIA 사전학습 없이 처음부터. EX-24(스캔 뺌)와 짝.
# usage: run_s2_x24a.sh <cuda:N> [추가 train.py 인자...]    (4096 env · seed 42 · 301 회 · 50 회마다 저장 · run 이름 ex24a-v2-scan)
# resume 없음: --resume 을 주지 않으면 설치본 cli_args 가 agent.resume 을 False 로 쓴다(hydra agent.resume=false 도 같이 준다).
set -u
DEV="$1"; shift 1
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_x24a_ex24a-v2-scan_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_v2_noscan.py --task Isaac-Velocity-V2b-Unitree-Go2-v0 --headless --device "$DEV" \
    --num_envs 4096 --seed 42 --max_iterations 301 --run_name ex24a-v2-scan "$@" "agent.device=$DEV" agent.resume=false agent.save_interval=50 > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
