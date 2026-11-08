#!/usr/bin/env bash
# lead 10/25: 16-env contact probe on a50/b50 m1550 (same as w3p2 probe16: --map-mode eval_pred --fixed-terrain --forward-gaits)
set -u
TAG="$1"; CK="$2"; DEV="$3"
OUT=/c/mai/wt/foothold-lab/impl-t5/logs/onset_sweep/probe_$TAG
MODULE=foothold_s2.eval.turn_probe DEVICE="$DEV" bash /c/mai/wt/foothold-lab/impl-t5/foothold_s2/eval/run_kit.sh "$OUT" \
  --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint "$CK" --envs 16 --map-mode eval_pred --fixed-terrain --forward-gaits < /dev/null
echo "$(date +%H:%M:%S) END $TAG rc=$? json=$([ -f $OUT/probe_result.json ] && echo yes || echo no)" >> /c/mai/wt/foothold-lab/impl-t5/logs/onset_sweep/probe_status.log
