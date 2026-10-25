#!/usr/bin/env bash
# SONNET-X25g: S-B(EX-33 p 0.5 · EX-34 p 0.1) 저장본 하나를 지도 켬(eval_gt) · 가림(probe_prop_only) 두 모드로, B1500 · G0-B 와 같은 조건에서 잰다. 체크포인트를 읽기만 한다. 학습 아님.
# GPU 를 쓰므로 lead 가 시킨 뒤에만 돌린다. 학습이 도는 같은 GPU 에서는 돌리지 않는다(S-B 약 12.3 GB + 평가 약 4.5 GB 가 16.3 GB 를 넘어 페이징).
# usage: [TASK=...] [MODES="eval_gt probe_prop_only"] run_sb_eval.sh <cuda:N> <model_*.pt> <출력 폴더>   (기본: S-B task, 지도 켬 · 가림 두 모드)
#   1) <out>/turn16_<모드> (기본 eval_gt , probe_prop_only) : 16 env 회전 여섯 경우(--cases all) + 전진 걸음 (칸 해시 7f49a1e9, impl-t5 w3p1 판과 같은 조건). 끄려면 FORWARD_GAITS_FLAG= (빈 값)
#   2) <out>/map64 : 64 env 고정 칸 평가, 두 모드를 한 실행에서(300 step, --fixed-terrain, 칸 해시 c3884d68)
# 스크립트 위치에서 저장소를 찾으므로 어디서 불러도 된다(cd 에 기대지 않음). Start-Process 에 이 파일 경로를 직접 넘겨도 된다.
set -u
DEV="$1"; CK="$2"; OUT="$3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KIT="$ROOT/foothold_s2/eval/run_kit.sh"
TASK="${TASK:-FootholdS2-Go2-S2-SB-v0}"                    # B1500 을 같은 꼴로 재려면 TASK=FootholdS2-Go2-S2-23f-B-v0
MODES="${MODES:-eval_gt probe_prop_only}"                  # 공백으로 구분. 배포 모드까지 보려면 MODES="eval_gt probe_prop_only eval_pred"
GAITS="${FORWARD_GAITS_FLAG---forward-gaits}"
mkdir -p "$OUT"
git -C "$ROOT" rev-parse HEAD > "$OUT/git_head.txt"
git -C "$ROOT" status --short > "$OUT/git_status.txt"
sha256sum "$CK" > "$OUT/checkpoint_sha256.txt"
: > "$OUT/rc.txt"
for MODE in $MODES; do
  MODULE=foothold_s2.eval.turn_probe DEVICE="$DEV" bash "$KIT" "$OUT/turn16_$MODE" \
    --task "$TASK" --checkpoint "$CK" --envs 16 --map-mode "$MODE" --fixed-terrain --cases all $GAITS < /dev/null
  echo "turn16_$MODE rc=$?" >> "$OUT/rc.txt"
  grep -q "TURNPROBE_DONE" "$OUT/turn16_$MODE/run.log" || echo "turn16_$MODE: DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
done
MODULE=foothold_s2.eval.eval_map_modes DEVICE="$DEV" bash "$KIT" "$OUT/map64" \
  --task "$TASK" --checkpoint "$CK" --envs 64 --steps 300 --modes "${MODES// /,}" --fixed-terrain < /dev/null
echo "map64 rc=$?" >> "$OUT/rc.txt"
[ -f "$OUT/map64/map_modes.json" ] || echo "map64: map_modes.json 없음" >> "$OUT/rc.txt"
