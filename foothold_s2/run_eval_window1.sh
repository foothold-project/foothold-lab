#!/usr/bin/env bash
# 창 1 이 끝난 뒤(EX-30 · EX-31 model_1750) 쓸 평가 (SONNET-X25 후속): 부모 B1500 과 두 자식을 같은 조건(같은 env · seed · DR 끔 · 세 지도 모드 · 명령 넷)으로 차례로 돌리고 표를 만든다.
# usage: run_eval_window1.sh <cuda:N> <EX-30 실행 폴더> <EX-31 실행 폴더> [출력 폴더]      GPU 한 장에서 한 번에 하나씩(합쳐 약 12분, 추정)
set -u
DEV="$1"; D30="$2"; D31="$3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${4:-$ROOT/logs/eval_window1_${STAMP}}"
PARENT="C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt"
for f in "$D30/model_1750.pt" "$D31/model_1750.pt" "$PARENT"; do [ -f "$f" ] || { echo "없음: $f" >&2; exit 1; }; done
mkdir -p "$OUT"
cd "$ROOT"
bash foothold_s2/run_eval_map_modes.sh "$DEV" "$PARENT" "$OUT/parent_b1500"
bash foothold_s2/run_eval_map_modes.sh "$DEV" "$D30/model_1750.pt" "$OUT/ex30_1750"
bash foothold_s2/run_eval_map_modes.sh "$DEV" "$D31/model_1750.pt" "$OUT/ex31_1750"
for n in parent_b1500 ex30_1750 ex31_1750; do cat "$OUT/$n/rc.txt"; grep -c MAPMODE_DONE "$OUT/$n/run.log"; done > "$OUT/summary_rc.txt"
/c/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.eval.compare_map_modes "$OUT/parent_b1500/map_modes.json" "$OUT/ex30_1750/map_modes.json" "$OUT/ex31_1750/map_modes.json" > "$OUT/table.md"
cat "$OUT/table.md"
