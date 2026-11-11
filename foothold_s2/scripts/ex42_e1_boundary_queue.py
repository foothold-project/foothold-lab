"""Prepare, but never register, the ordered E1 P1 boundary queue after E1 ends."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import stat
import subprocess
from typing import Any, Callable

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval.ex42_d44_cells import contract as d44_contract
from foothold_s2.ex42_eval_once import manifest_checkpoint_sha
from foothold_s2.ex42_gate_checks import checkpoint_ready
from foothold_s2.machine_profile import machine_path


BOUNDARIES = (250, 500, 750, 1000)
DEVICES = ("cuda:0", "cuda:1", "cuda:0", "cuda:1")


def build_queue_plan(*, repo: str | Path, e1_run: str | Path, plan_path: str | Path,
                     approvals_path: str | Path, e1_ended: bool,
                     mesh_check: Callable[[str | Path], dict[str, Any]] | None = None,
                     require_clean: bool = False, python_path: str | Path | None = None,
                     queue_path: str | Path | None = None,
                     mesh_root_path: str | Path | None = None,
                     landing_mesh_check: Callable[[str | Path], dict[str, Any]] | None = None,
                     require_locked: bool = False) -> dict[str, Any]:
    repo = Path(repo).resolve(strict=True)
    run = Path(e1_run).resolve(strict=True)
    plan_path = Path(plan_path).resolve(strict=True)
    approvals_path = Path(approvals_path).resolve(strict=True)
    if e1_ended is not True:
        raise ValueError("queue preparation requires explicit confirmation that E1 has ended")
    if require_clean:
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
        if status.strip():
            raise ValueError("fixed source checkout must be clean before queue preparation")
    if require_locked:
        protected = (repo, repo / "foothold_s2/scripts/ex42_eval_once.py",
                     repo / "foothold_s2/curriculum/ex42-prep.yaml",
                     repo / "_out/tools/gpu_jobs/dispatch.py")
        if any(path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
               for path in protected):
            raise ValueError("fixed checkout is not locked read-only")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    plan = EX42Plan.load(plan_path)
    if "E1" not in plan.runtime_stage_ids:
        raise ValueError("E1 is absent from the pinned EX-42 plan")
    from foothold_s2.curriculum.ex42_runtime import read_approved_dr_schedule
    read_approved_dr_schedule(approvals_path, plan.runtime_stage_ids)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    completed = (manifest.get("progress") or {}).get("completed_updates")
    if type(completed) is not int or completed < 1000:
        raise ValueError("E1 ended checkpoint manifest must publish at least 1000 completed updates")

    landing = d44_contract(plan.document)
    terrain_source = plan.document["assumptions_pending_lead"]["terrain_manifest_measurements"]
    terrain_source = terrain_source.get("value") if isinstance(terrain_source, dict) else None
    if not isinstance(terrain_source, dict):
        raise ValueError("EX-42 measured E0 mesh source contract is missing")
    source_parts = Path(terrain_source.get("source", "")).parts
    if (len(source_parts) < 3 or source_parts[0] != "s2_lab"
            or source_parts[-1] != "aggregate_measurements.json"):
        raise ValueError("EX-42 E0 mesh source must be the registered s2_lab aggregate path")
    mesh_root = Path(mesh_root_path) if mesh_root_path is not None else machine_path("s2_lab_root")
    mesh_dir = mesh_root.joinpath(*source_parts[1:-1])
    expected_mesh_sha = terrain_source.get("mesh_sha256")
    if not isinstance(expected_mesh_sha, str) or len(expected_mesh_sha) != 64:
        raise ValueError("EX-42 E0 combined mesh SHA is not pinned")
    if mesh_check is None:
        from foothold_s2.eval.ex42_mesh_eval import preflight
        mesh = preflight(mesh_dir)
    else:
        mesh = mesh_check(mesh_dir)
    if mesh.get("mesh_sha256") != expected_mesh_sha:
        raise ValueError("E1 P1 combined mesh does not match the pinned E0 terrain SHA")
    if landing_mesh_check is None:
        from foothold_s2.eval.ex42_eval_tile_mesh import source_tile
        landing_manifest, _ = source_tile(landing["source_mesh_dir"])
        landing_mesh = {"mesh_sha256": landing_manifest["mesh_sha256"]}
    else:
        landing_mesh = landing_mesh_check(landing["source_mesh_dir"])
    if landing_mesh.get("mesh_sha256") != landing["source_mesh_sha256"]:
        raise ValueError("E1 D44 landing tile does not match its separate pinned mesh SHA")

    python = str(Path(python_path).resolve(strict=True) if python_path is not None
                 else machine_path("conda_python").resolve(strict=True))
    dispatcher = repo / "_out/tools/gpu_jobs/dispatch.py"
    if not dispatcher.is_file():
        raise ValueError("fixed checkout does not contain the GPU dispatcher")
    queue = str(Path(queue_path).resolve() if queue_path is not None else machine_path("gpu_queue"))
    jobs = []
    for index, iteration in enumerate(BOUNDARIES):
        checkpoint = run / f"model_{iteration}.pt"
        sha, actual_iteration = manifest_checkpoint_sha(checkpoint)
        if actual_iteration != iteration or not checkpoint_ready(
                manifest, iteration=iteration, checkpoint_exists=True, checkpoint_sha256=sha):
            raise ValueError(f"E1 m{iteration} checkpoint is not published with its manifest SHA")
        output = run / "eval" / "scores" / f"m{iteration}"
        marker = run / "eval" / "queue-markers" / f"E1-{head[:12]}-m{iteration}.done.json"
        if output.exists() or marker.exists():
            raise ValueError(f"E1 m{iteration} output or completion marker already exists")
        eval_argv = [python, "-m", "foothold_s2.ex42_eval_once",
                     "--checkpoint", str(checkpoint), "--sha-from-manifest",
                     "--out", str(output), "--device", DEVICES[index],
                     "--eval-seed", "42", "--mesh-dir", str(mesh_dir),
                     "--expected-mesh-sha256", expected_mesh_sha,
                     "--p1-plan", str(plan_path), "--p1-approvals", str(approvals_path),
                     "--p1-stage-id", "E1", "--execute"]
        wrapper_argv = [python, "-m", "foothold_s2.scripts.ex42_p1_queue_item",
                        "--iteration", str(iteration), "--marker", str(marker),
                        "--eval-argv-json", json.dumps(eval_argv, separators=(",", ":"))]
        predecessors = [] if index == 0 else [jobs[-1]["marker"]]
        queue_args = [python, str(dispatcher), "queue", "add", "--queue", queue,
                      "--title", f"EX-42 E1 P1 m{iteration} D44 six cases",
                      "--priority", "1", "--gpu", str(index % 2), "--owner", "runner",
                      "--cond", f"E1 ended · manifest SHA verified · after m{BOUNDARIES[index - 1]} success" if index else
                      "E1 ended · manifest SHA verified",
                      "--kind", "eval", "--cwd", str(repo), "--argv-json",
                      json.dumps(wrapper_argv, separators=(",", ":")), "--done-file", str(marker)]
        for predecessor in predecessors:
            queue_args.extend(("--wait-present", predecessor))
        jobs.append({"id": f"E1-P1-m{iteration}", "iteration": iteration, "checkpoint": str(checkpoint),
                     "checkpoint_sha256": sha, "device": DEVICES[index], "gpu": index % 2,
                     "priority": 1, "kind": "eval", "output": str(output), "marker": str(marker),
                     "wait_present": predecessors, "d44_judge_cases": list(landing["judge_cases"]),
                     "d44_record_cases": list(landing["record_cases"]), "eval_argv": eval_argv,
                     "wrapper_argv": wrapper_argv, "queue_add_argv": queue_args,
                     "queue_add_shell": shlex.join(queue_args)})

    return {"format": "foothold-ex42-e1-p1-queue-preparation/1", "source_head": head,
            "plan_sha256": plan.sha256,
            "approvals_sha256": hashlib.sha256(approvals_path.read_bytes()).hexdigest(),
            "e1_run": str(run), "e1_manifest_completed_updates": completed,
            "mesh_dir": str(mesh_dir), "mesh_sha256": mesh["mesh_sha256"],
            "d44_landing_mesh_dir": landing["source_mesh_dir"],
            "d44_landing_mesh_sha256": landing["source_mesh_sha256"],
            "queue": queue, "queue_mutated": False, "kit_started": False,
            "training_started": False, "registration_allowed_after_fixed_checkout": True,
            "cancel_targets": [{"id": 4, "reason": "superseded by exact ex42_eval_once E1 P1 + D44 chain; lead cancels"}],
            "jobs": jobs}


def main(argv=None) -> int:
    repo_default = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=repo_default)
    parser.add_argument("--e1-run", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=repo_default / "foothold_s2/curriculum/ex42-prep.yaml")
    parser.add_argument("--approvals", type=Path, default=repo_default / "foothold_s2/curriculum/ex42-approvals.yaml")
    parser.add_argument("--e1-ended", action="store_true", help="required assertion; registration is still not performed")
    parser.add_argument("--out-json", type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_queue_plan(repo=args.repo, e1_run=args.e1_run,
                                  plan_path=args.plan, approvals_path=args.approvals,
                                  e1_ended=args.e1_ended, require_clean=True, require_locked=True)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"state": "blocked", "reason": str(exc), "queue_mutated": False,
                          "kit_started": False, "training_started": False}, ensure_ascii=False))
        return 2
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
