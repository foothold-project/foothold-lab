"""Build the D131 m6000 C-layer 216-cell plan without starting Kit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from foothold_s2.eval import c_layer_queue as queue
from foothold_s2.eval import fixed_terrain, video_style
from foothold_s2.terrains import columns


KINDS = {
    "continuous": ["pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
                   "hf_pyramid_slope", "hf_pyramid_slope_inv", "stage_stairs"],
    "sparse": ["stepping_stones_low", "stepping_stones_high", "balance_beams",
               "stepping_beams", "gaps"],
}
GEOMETRY_SEED = 20261026
CAPTURE_SEEDS = (42, 43, 44, 45)


def _head(source: Path) -> str:
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    clean = subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--"],
                           check=False)
    if len(head) != 40 or clean.returncode != 0:
        raise ValueError("C76 source worktree must have a clean pinned HEAD")
    return head


def assignments() -> dict[str, tuple[int, int]]:
    names = columns.column_types(columns.FULL, columns.FULL_COLS)
    sparse_ids = fixed_terrain.sparse_column_ids(names)
    result = {}
    for kind in KINDS["continuous"]:
        column = names.index(kind)
        result[kind] = (column, column)
    for kind in KINDS["sparse"]:
        index = next(i for i, col in enumerate(sparse_ids) if names[col] == kind)
        result[kind] = (index, sparse_ids[index])
    if set(result) != set(KINDS["continuous"] + KINDS["sparse"]):
        raise ValueError("C76 terrain assignment incomplete")
    return result


def build_plan(*, checkpoint: Path, source_root: Path, recorder: Path, composer: Path,
               python: Path, playlist_dir: Path, priority_markers: dict[str, Path],
               device: str, gpu_jobs_tool: Path, gpu_jobs_config: Path,
               first_success_only: bool = False) -> dict:
    if checkpoint.name != "model_6000.pt":
        raise ValueError("D131 C layer checkpoint must be model_6000.pt")
    if device not in ("cuda:0", "cuda:1") or not python.is_file():
        raise ValueError("explicit installed Python and cuda:0 or cuda:1 required")
    checkpoint = checkpoint.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    recorder = recorder.resolve(strict=True)
    composer = composer.resolve(strict=True)
    gpu_jobs_tool = gpu_jobs_tool.resolve(strict=True)
    gpu_jobs_config = gpu_jobs_config.resolve(strict=True)
    head = _head(source_root)
    source_recorder = source_root / "foothold_s2/eval/record_sol23f.py"
    if not source_recorder.is_file():
        raise ValueError("C76 source recorder missing")
    checkpoint_sha = queue.sha256(checkpoint)
    if not checkpoint_sha.startswith("d5e9ec40"):
        raise ValueError("D131 m6000 SHA prefix differs")
    layout = assignments()
    rows = []
    for kind, level, mode in queue.inventory(KINDS):
        env_id, col = layout[kind]
        label = video_style.capture_name("EX40", kind, level, env_id, 6000, segment=mode)
        terrain_set = "fixed64" if kind in KINDS["continuous"] else "sparse50"
        policy = {"experiment": "SB", "source_root": str(source_root),
                  "source_profile": "C76", "source_head": head,
                  "source_recorder_sha256": queue.sha256(source_recorder),
                  "selection_role": "c_layer", "terrain_set": terrain_set,
                  "fixed_terrain": True, "fixed_level": level, "geometry_seed": GEOMETRY_SEED,
                  "command": [1.0, 0.0, 0.0], "duration_s": 18.0,
                  "seed": "{seed}", "c_layer_reference": True, "hide_others": True,
                  "checkpoint_sha256": checkpoint_sha, "envs": 64,
                  "map_mode": mode, "env_id": env_id, "kind": kind, "col": col,
                  "start_yaw_rad": 0.0}
        argv = [str(python), str(recorder), "--policy", "{policy}",
                "--checkpoint", str(checkpoint), "--label", "{label}",
                "--scene", "rough" if terrain_set == "fixed64" else "sparse",
                "--mp4", "{mp4}", "--device", device,
                "--headless", "--enable_cameras", "--livestream", "0"]
        rows.append({"kind": kind, "level": level, "map_mode": mode,
                     "env_id": env_id, "label": label, "seeds": list(CAPTURE_SEEDS),
                     "policy": policy, "recorder_argv": argv})
    plan = {"status": "approved_canon", "decision": "D131", "canon_label": "EX40",
            "target_results": ["success"] if first_success_only else ["success", "fail"],
            "iteration": 6000, "kinds": KINDS, "checkpoint": str(checkpoint),
            "checkpoint_sha256": checkpoint_sha, "priority_markers": {
                key: str(value.resolve()) for key, value in priority_markers.items()},
            "recorder": str(recorder), "recorder_sha256": queue.sha256(recorder),
            "composer": str(composer), "composer_sha256": queue.sha256(composer),
            "queue": str(Path(queue.__file__).resolve()),
            "queue_sha256": queue.sha256(Path(queue.__file__).resolve()),
            "gpu_jobs_tool": str(gpu_jobs_tool), "gpu_jobs_tool_sha256": queue.sha256(gpu_jobs_tool),
            "gpu_jobs_config": str(gpu_jobs_config), "gpu_jobs_config_sha256": queue.sha256(gpu_jobs_config),
            "runtime_sources_sha256": {
                str(path): queue.sha256(path) for path in (
                    recorder.parent / "overlay_25e.py",
                    *(Path(queue.__file__).parent / name for name in
                      ("c_layer_segmentation.py", "c_layer_frame_audit.py", "video_rule.py")),
                )
            },
            "playlist_dir": str(playlist_dir.resolve()), "jobs": rows}
    if queue.validate_plan(plan)["ready"] != 216:
        raise AssertionError("C76 plan is not complete")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--recorder", type=Path, required=True)
    parser.add_argument("--composer", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--playlist-dir", type=Path, required=True)
    parser.add_argument("--training-marker", type=Path, required=True)
    parser.add_argument("--evaluation-marker", type=Path, required=True)
    parser.add_argument("--a-layer-marker", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--first-success-only", action="store_true",
                        help="first C-layer pass seeks one successful clip per cell")
    parser.add_argument("--gpu-jobs-tool", type=Path, required=True)
    parser.add_argument("--gpu-jobs-config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plan = build_plan(checkpoint=args.checkpoint, source_root=args.source_root,
                      recorder=args.recorder, composer=args.composer, python=args.python,
                      playlist_dir=args.playlist_dir, priority_markers={
                          "training": args.training_marker, "evaluation": args.evaluation_marker,
                      "a_layer": args.a_layer_marker}, device=args.device,
                      gpu_jobs_tool=args.gpu_jobs_tool, gpu_jobs_config=args.gpu_jobs_config,
                      first_success_only=args.first_success_only)
    if args.out.exists():
        raise ValueError("C76 plan.json already exists; preserve the original SHA")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"plan": str(args.out), "sha256": queue.sha256(args.out),
                      "cells": len(plan["jobs"]), "first_cell": queue._slot(plan["jobs"][0])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
