#!/usr/bin/env bash
# EX-13 · EX-14 (SONNET-X13): 기준은 EX-11(est 0 · S1 지형 7 종 · START 명령 · clean critic 664 · clip 17 · 3072 env · rollout 24 · seed 42 · 1501 회 · 500 회마다 저장).
# usage: run_s2_x13.sh <x13|x14> <cuda:N> [추가 train_start 인자...]
#   x13 = EX-13: feet_air_time +1.0 · motion_trot -0.1 · stand_still -0.1 · only_positive_rewards (MGDP 묶음 넷)
#   x14 = EX-14: feet_air_time +1.0 하나만
# 실행 중에는 이 저장소의 소비 코드를 고치지 않는다(manifest 가 저장 때 감시).
set -u
MODE="$1"; DEV="$2"; shift 2
case "$MODE" in
  x13) TASK="FootholdS2-Go2-S2-X13-v0"; RUN="ex13-mgdp4" ;;
  x14) TASK="FootholdS2-Go2-S2-X14-v0"; RUN="ex14-airtime" ;;
  *) echo "mode 는 x13 또는 x14"; exit 2 ;;
esac
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_x13_${RUN}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_start.py --task "$TASK" --headless --device "$DEV" \
    --num_envs 3072 --max_iterations 1501 --seed 42 --run_name "$RUN" --map_input none "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
