#!/usr/bin/env bash
# EX-11 · EX-12 (SONNET-X11): 같은 env(S1 지형 · START 명령 · clean critic 664 · clip 17) 에서 est 처치만 다르다.
# usage: run_s2_x11.sh <zero|learned> <cuda:N> [추가 train_start 인자...]
#   zero    = EX-11: 지각은 돌고 actor 입력의 est 51 칸만 0 (agent.perception.est_mode=zero)
#   learned = EX-12: 지금 G0 와 같은 est 연결
# 3072 env · rollout 24 · seed 42 · 1501 회(model_1500 까지) · 500 회마다 저장 · map_input none. 실행 중에는 이 저장소의 소비 코드를 고치지 않는다(manifest 가 저장 때 감시).
set -u
MODE="$1"; DEV="$2"; shift 2
case "$MODE" in
  zero)    RUN="ex11-est-zero";    OVR="agent.perception.est_mode=zero" ;;
  learned) RUN="ex12-est-learned"; OVR="agent.perception.est_mode=learned" ;;
  *) echo "mode 는 zero 또는 learned"; exit 2 ;;
esac
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_x11_${RUN}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_start.py --task FootholdS2-Go2-S2-X11-v0 --headless --device "$DEV" \
    --num_envs 3072 --max_iterations 1501 --seed 42 --run_name "$RUN" --map_input none "$@" "$OVR" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
