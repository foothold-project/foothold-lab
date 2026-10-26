#!/usr/bin/env bash
# SONNET-X26i: 듬성 지형(gaps · stepping stones high/low · balance beams · stepping beams) 고정 칸 평가. 64 env 를 듬성 5 종 열(23..47)에 고정하고 레벨 0 · 1 · 2 · 6 을 각각, 지도 켬(eval_gt) · 가림(probe_prop_only) 두 모드로 잰다 = 예행 8 건.
# 체크포인트를 읽기만 한다. GPU 를 쓰므로 lead 가 시킨 뒤에만 돌린다. 학습이 도는 같은 GPU 에서는 돌리지 않는다.
# usage: [TASK=...] [LEVELS="0 1 2 6"] [MODES="eval_gt,probe_prop_only"] run_sparse_eval.sh <cuda:N> <model_*.pt> <출력 폴더>
#   TASK 기본 FootholdS2-Go2-S2-23f-B-v0 (B1500). S-B 면 TASK=FootholdS2-Go2-S2-SB-v0
#   출력: <out>/L<레벨>/map_modes.json (칸 해시는 json 의 fixed_terrain.assignment_sha256), <out>/rc.txt
set -u
DEV="$1"; CK="$2"; OUT="$3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KIT="$ROOT/foothold_s2/eval/run_kit.sh"
TASK="${TASK:-FootholdS2-Go2-S2-23f-B-v0}"
LEVELS="${LEVELS:-0 1 2 6}"
MODES="${MODES:-eval_gt,probe_prop_only}"
mkdir -p "$OUT"
git -C "$ROOT" rev-parse HEAD > "$OUT/git_head.txt"
git -C "$ROOT" status --short > "$OUT/git_status.txt"
sha256sum "$CK" > "$OUT/checkpoint_sha256.txt"
: > "$OUT/rc.txt"
for LV in $LEVELS; do
  MODULE=foothold_s2.eval.eval_map_modes DEVICE="$DEV" bash "$KIT" "$OUT/L$LV" \
    --task "$TASK" --checkpoint "$CK" --envs 64 --steps 300 --modes "$MODES" --fixed-terrain --fixed-level "$LV" --terrain-set sparse50 < /dev/null
  echo "L$LV rc=$?" >> "$OUT/rc.txt"
  [ -f "$OUT/L$LV/map_modes.json" ] || echo "L$LV: map_modes.json 없음" >> "$OUT/rc.txt"
done
