#!/usr/bin/env bash
# SONNET-X25e: G0-B(map_input none) 저장본을 B1500 과 같은 잣대로 잰다. 체크포인트를 읽기만 한다. 학습 아님. GPU 를 쓰므로 lead 가 시킨 뒤에만 돌린다.
# usage: run_g0b_eval.sh <cuda:N> <model_*.pt> <출력 폴더>
#   1) <out>/turn16 : 16 env 회전 여섯 경우(--cases all) + 전진 걸음 0.5 · 1.0 (impl-t5 w3p1 판과 같은 조건: eval 고정 지형, 16 env). 끄려면 FORWARD_GAITS_FLAG= (빈 값)
#   2) <out>/map64  : 64 env 고정 칸 평가(onset_sweep/sweep.sh 와 같은 조건: 300 step, --fixed-terrain). 지도 없는 체크포인트는 모드 none 하나뿐이다(eval_gt · eval_pred 는 코드가 거절한다)
# 스크립트 위치에서 저장소를 찾으므로 어디서 불러도 된다(cd 에 기대지 않음). Start-Process 에 이 파일 경로를 직접 넘겨도 된다.
set -u
DEV="$1"; CK="$2"; OUT="$3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KIT="$ROOT/foothold_s2/eval/run_kit.sh"
TASK=FootholdS2-Go2-S2-G0B-v0
GAITS="${FORWARD_GAITS_FLAG---forward-gaits}"
mkdir -p "$OUT"
git -C "$ROOT" rev-parse HEAD > "$OUT/git_head.txt"
git -C "$ROOT" status --short > "$OUT/git_status.txt"
sha256sum "$CK" > "$OUT/checkpoint_sha256.txt"
MODULE=foothold_s2.eval.turn_probe DEVICE="$DEV" bash "$KIT" "$OUT/turn16" \
  --task "$TASK" --checkpoint "$CK" --envs 16 --map-mode none --fixed-terrain --cases all $GAITS < /dev/null
echo "turn16 rc=$?" > "$OUT/rc.txt"
grep -q "TURNPROBE_DONE" "$OUT/turn16/run.log" || echo "turn16: DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
MODULE=foothold_s2.eval.eval_map_modes DEVICE="$DEV" bash "$KIT" "$OUT/map64" \
  --task "$TASK" --checkpoint "$CK" --envs 64 --steps 300 --modes none --fixed-terrain < /dev/null
echo "map64 rc=$?" >> "$OUT/rc.txt"
[ -f "$OUT/map64/map_modes.json" ] || echo "map64: map_modes.json 없음" >> "$OUT/rc.txt"
