#!/usr/bin/env bash
# EX-25 (G0, 지도 없이 학습) model_1500 을 eval_map_modes 와 같은 조건으로 평가: 지도 없음 참조 열 (SONNET-X25). 학습 아님, 저장 없음.
# usage: run_eval_g0_reference.sh <cuda:N> [체크포인트=EX-25 model_1500.pt] [출력 폴더]
set -u
DEV="$1"
CK="${2:-C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s2_x23/2026-10-22_23-00-45_ex25-g0/model_1500.pt}"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${3:-$ROOT/logs/eval_g0_ex25_${STAMP}}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
sha256sum "$CK" > "$OUT/checkpoint_sha256.txt"
"$ENV/python.exe" -m foothold_s2.eval.eval_map_modes --task FootholdS2-Go2-S2-X23-v0 --modes none --checkpoint "$CK" --out "$OUT" --headless --device "$DEV" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
grep -q "MAPMODE_DONE" "$OUT/run.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
