#!/usr/bin/env bash
# Onset sweep through the project launcher run_kit.sh (EULA · conda PATH · PCI_BUS_ID).
# usage: sweep.sh <cuda:N> <list file>
set -u
DEV="$1"; LIST="$2"
HERE=/c/mai/wt/foothold-lab/impl-t5/logs/onset_sweep
KIT=/c/mai/wt/foothold-lab/impl-t5/foothold_s2/eval/run_kit.sh
ST="$HERE/status_${DEV/:/}.log"
while IFS="|" read -r tag ckpt; do ckpt="${ckpt%$''}"
  [ -z "$tag" ] && continue
  out="$HERE/$tag"
  if [ -f "$out/map_modes.json" ]; then echo "SKIP $tag" >> "$ST"; continue; fi
  rm -rf "$out"
  echo "$(date +%H:%M:%S) START $tag" >> "$ST"
  MODULE=foothold_s2.eval.eval_map_modes DEVICE="$DEV" bash "$KIT" "$out" \
    --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint "$ckpt" --envs 64 --steps 300 \
    --modes eval_gt,eval_pred --fixed-terrain < /dev/null
  rc=$?
  echo "$(date +%H:%M:%S) END $tag rc=$rc json=$([ -f "$out/map_modes.json" ] && echo yes || echo no)" >> "$ST"
done < "$HERE/$LIST"
echo "$(date +%H:%M:%S) ALLDONE" >> "$ST"
