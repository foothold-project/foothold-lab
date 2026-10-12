#!/usr/bin/env bash
# Kinematic replay videos of full-record CSVs (q_video.py). GPU 1 only (display GPU, renders). Each process goes
# through gpu_guard.py (200 ms, stop below 4 GiB free). Usage: bash run_videos.sh <full_tag> [<full_tag> ...]
# From 2026-10-12 14:45 PhysX runs on the CPU (SIMDEV, default cpu): the replay has no physics step and the GPU
# buffers of PhysX pushed GPU 1 below the floor on the band scene. The renderer stays on GPU 1.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
mkdir -p out/video
for tag in "$@"; do
  if [ -f "out/video/$tag/videos_report.json" ]; then echo "VIDEO $tag SKIP"; continue; fi
  t0=$(date +%s)
  "$PY" gpu_guard.py --gpu 1 --log "out/video/$tag.log" --summary "out/video/$tag.guard.json" -- "$PY" q_video.py --run_tag "$tag" --files all --sim_device "${SIMDEV:-cpu}"
  rc=$?
  echo "VIDEO $tag EXIT $rc $(( $(date +%s) - t0 ))s $(date +%H:%M:%S)"
  if [ "$rc" = "99" ]; then echo "STOP: guard stopped $tag"; exit 99; fi
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
done
echo "VIDEOS DONE"
