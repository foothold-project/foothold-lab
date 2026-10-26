#!/usr/bin/env bash
# SONNET-X26r: 듬성 평가 Kit 짧은 확인(GPU 는 lead 가 준 뒤에만). 레벨 0 · 모드 하나 · 명령 하나 · STEPS 50. 끝나면 map_modes.json 과 npz 의 start_support 가 64 개인지 본다.
# usage: [TASK=...] [MODES=eval_gt] smoke_sparse_start.sh <cuda:N> <model_*.pt> <출력 폴더>
set -u
DEV="$1"; CK="$2"; OUT="$3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASK="${TASK:-FootholdS2-Go2-S2-23f-B-v0}"
[ -z "$(git -C "$ROOT" status --short -- foothold_s2)" ] || { echo "거절: foothold_s2 더러움"; exit 3; }
mkdir -p "$OUT"
MODULE=foothold_s2.eval.eval_map_modes DEVICE="$DEV" bash "$ROOT/foothold_s2/eval/run_kit.sh" "$OUT" \
  --task "$TASK" --checkpoint "$CK" --envs 64 --steps 50 --modes "${MODES:-eval_gt}" --commands fwd1.0 --fixed-terrain --fixed-level 0 --terrain-set sparse50 < /dev/null
PYTHONPATH="$ROOT" PYTHONUTF8=1 python "$ROOT/foothold_s2/eval/smoke_sparse_check.py" "$OUT"
