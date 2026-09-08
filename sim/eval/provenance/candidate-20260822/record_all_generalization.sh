#!/bin/bash

set -e

cd /workspace/isaaclab

CHECKPOINT="/workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt"

for ENV_ID in {0..9}
do
    ./isaaclab.sh -p \
    scripts/reinforcement_learning/rsl_rl/record_generalization.py \
      --task Isaac-Velocity-Unseen-Unitree-Go2-v0 \
      --checkpoint "${CHECKPOINT}" \
      --record_env "${ENV_ID}" \
      --video_length 300 \
      --command_vx 0.5 \
      --seed 42 \
      --headless
done

find /workspace/isaaclab/generalization_videos \
  -type f -name "*.mp4" \
  -print
