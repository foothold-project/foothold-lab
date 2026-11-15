#!/usr/bin/env bash
# CPU dry only. No torchrun, Kit bootstrap, queue submission or training.
# Run from the PR worktree root. Uses the existing Linux profile, does not edit it.
set -euo pipefail
set -a
source /home/jay/mai/foothold-linux.env
set +a
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 WORLD_SIZE=2 RANK=0 LOCAL_RANK=0 \
  /home/jay/miniforge3/envs/isaac311/bin/python foothold_s2/scripts/train_start.py \
  --ex42_plan foothold_s2/curriculum/ex42-prep.yaml \
  --ex42_approvals foothold_s2/curriculum/ex42-approvals.yaml \
  --ex42_parent_manifest /mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/manifest.json \
  --ex42_log_dir /home/jay/mai/tmp/analyst-lx/terrain-manifest-1111/not-created-run \
  --ex42_queue_path /home/jay/mai/tmp/analyst-lx/terrain-manifest-1111/not-created-queue.json \
  --ex42_p1_score_argv_json '["unused-in-dry-preflight"]' \
  --ex42_source_ref origin/lead/linux-integration-1109 \
  --ex42_stage_e0_approved --ex42_stage_e0_dry_run \
  --ex42_terrain_manifest /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333/terrain_manifest.json \
  --ex42_terrain_mesh_dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333 \
  --task FootholdS2-Go2-S2-SB-v0 --device cuda:0 --num_envs 3072 --max_iterations 250 \
  --map_input reconstruction --headless --distributed
