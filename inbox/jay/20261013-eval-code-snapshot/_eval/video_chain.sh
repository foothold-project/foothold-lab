#!/usr/bin/env bash
# Replay videos on GPU 1 as soon as the full-record runs of each set exist (runs alongside chain_after_e2.sh).
set -u
cd "$(dirname "$0")"
until [ -f out/fr_m20499_offplat/cells.json ]; do sleep 30; done
bash run_videos.sh $(for it in 20000 20499; do for f in flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles offplat; do echo fr_m${it}_$f; done; done) || exit $?
until [ -f out/e2_m20499_offplat/cells.json ]; do sleep 30; done
bash run_videos.sh $(for it in 20000 20499; do for f in flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles offplat; do echo e2_m${it}_$f; done; done) || exit $?
echo "VIDEO CHAIN DONE $(date +%H:%M:%S)"
