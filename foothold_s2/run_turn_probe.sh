#!/usr/bin/env bash
# 우회전 probe (SONNET-X25 T5): 체크포인트를 읽기만 한다. 학습 아님. GPU 를 쓰므로 lead 가 시킨 뒤에만 돌린다.
# usage: run_turn_probe.sh <cuda:N> [체크포인트=B model_1500.pt] [출력 폴더] [task=B] [map-mode=eval_pred]     G0(EX-25): ... FootholdS2-Go2-S2-X23-v0 none
set -u
DEV="$1"
CK="${2:-C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt}"
TASK="${4:-FootholdS2-Go2-S2-23f-B-v0}"
MODE="${5:-eval_pred}"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
FIXED="${FIXED_TERRAIN_FLAG---fixed-terrain}"      # 기본: 고정 지형 칸 사용. 끄려면 FIXED_TERRAIN_FLAG= (빈 값)
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${3:-$ROOT/logs/turn_probe_${STAMP}}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
sha256sum "$CK" > "$OUT/checkpoint_sha256.txt"
"$ENV/python.exe" -m foothold_s2.eval.turn_probe --task "$TASK" --map-mode "$MODE" --checkpoint "$CK" --out "$OUT" $FIXED --headless --device "$DEV" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
grep -q "TURNPROBE_DONE" "$OUT/run.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
