#!/usr/bin/env bash
# Resumes the replay videos after the guard stop of 14:34 (fr_m20000_offplat): PhysX on the CPU, renderer on GPU 1.
# Tags whose videos_report.json exists are skipped by run_videos.sh.
set -u
cd "$(dirname "$0")"
bash run_videos.sh $(for it in 20000 20499; do for f in flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles offplat; do echo fr_m${it}_$f; done; done) || exit $?
until [ -f out/e2_m20499_offplat/cells.json ]; do sleep 30; done
bash run_videos.sh $(for it in 20000 20499; do for f in flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles offplat; do echo e2_m${it}_$f; done; done) || exit $?
echo "VIDEO CHAIN DONE $(date +%H:%M:%S)"
