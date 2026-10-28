"""Sequential post-training W15 evaluation of EX-36 extension checkpoints.

Default is a CPU-only plan. --live needs an operator's authorization reference.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

from foothold_s2 import basic_gait_eval_once as once
from foothold_s2.basic_gait_extend_parent import PARENT_UPDATE


def planned_iterations(arm: str, final_iter: int) -> tuple[int, ...]:
    if arm not in PARENT_UPDATE or not PARENT_UPDATE[arm] < final_iter <= PARENT_UPDATE[arm] + 1500:
        raise ValueError("EX-36 extension final update outside the approved segment range")
    first = (PARENT_UPDATE[arm] // 250 + 1) * 250
    return tuple(range(first, final_iter + 1, 250))


def source_receipt(run_dir: Path, arm: str, final_iter: int, *, require_done: bool) -> dict:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    run = manifest.get("run") or {}
    modes = manifest.get("modes") or {}
    parent = (modes.get("resume_parent") or {}).get("basic_extend") or {}
    if (run.get("name") != f"EX-36{arm}-basic-extend-share30"
            or parent.get("arm") != arm or parent.get("completed_update") != PARENT_UPDATE[arm]
            or modes.get("basic_terrain_cfg_difference") is None
            or modes.get("seed") != 42 or modes.get("p_map_off") != 0.1):
        raise ValueError("evaluation source is not the pinned EX-36 basic-gait extension")
    if require_done:
        status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        if (status.get("state") != "done" or status.get("iter") != final_iter
                or (manifest.get("progress") or {}).get("completed_updates", 0) < final_iter + 1):
            raise ValueError("EX-36 extension has not finished the requested final update")
    return {"run_name": run["name"], "arm": arm, "parent": parent,
            "final_iter": final_iter, "run_dir": str(run_dir.resolve())}


def plan(run_dir: Path, out_root: Path, arm: str, final_iter: int, *, require_done: bool) -> dict:
    source = source_receipt(run_dir, arm, final_iter, require_done=require_done)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    recorded = manifest.get("checkpoints") or {}
    rows = []
    for iteration in planned_iterations(arm, final_iter):
        checkpoint = run_dir / f"model_{iteration}.pt"
        registered_sha = recorded.get(checkpoint.name)
        rows.append({"iteration": iteration, "checkpoint": str(checkpoint.resolve()),
                     "exists": checkpoint.is_file(), "manifest_sha256": registered_sha,
                     "out": str((out_root / f"m{iteration}").resolve())})
    return {"source": source, "jobs": rows,
            "all_checkpoints_present": all(r["exists"] for r in rows),
            "all_checkpoints_registered": all(isinstance(r["manifest_sha256"], str) and
                                               len(r["manifest_sha256"]) == 64 for r in rows),
            "evaluation": "W15 extended 13 commands and 3 sequences, 64 map env, three modes + turn16"}


def _read_done(path: Path, checkpoint: Path, iteration: int) -> dict:
    row = json.loads(path.read_text(encoding="utf-8"))
    if row.get("checkpoint_sha256") != once.sha256_file(checkpoint) or row.get("iteration") != iteration:
        raise ValueError("W15 done marker checkpoint mismatch")
    verified = once.verify(Path(row["attempt_dir"]), checkpoint, iteration)
    if verified["checkpoint_sha256"] != row["checkpoint_sha256"]:
        raise ValueError("W15 done marker no longer verifies")
    return row


def run_chain(run_dir: Path, out_root: Path, arm: str, final_iter: int, device: str,
              authorization_ref: str, *, evaluator=once.run) -> list[dict]:
    if device not in ("cuda:0", "cuda:1") or not authorization_ref or authorization_ref.startswith("PENDING"):
        raise ValueError("explicit GPU device and evaluation authorization reference required")
    row = plan(run_dir, out_root, arm, final_iter, require_done=True)
    if not row["all_checkpoints_present"]:
        raise FileNotFoundError("one or more completed m250 checkpoints are absent")
    if not row["all_checkpoints_registered"]:
        raise ValueError("one or more m250 checkpoints lack a manifest SHA")
    outcomes = []
    for job in row["jobs"]:
        iteration = job["iteration"]
        checkpoint = Path(job["checkpoint"])
        if once.sha256_file(checkpoint) != job["manifest_sha256"]:
            raise ValueError("m250 checkpoint differs from training manifest SHA")
        unit = out_root / f"m{iteration}"
        marker = unit / ".done"
        if marker.is_file():
            outcomes.append(_read_done(marker, checkpoint, iteration))
            continue
        unit.mkdir(parents=True, exist_ok=True)
        attempt = unit / f"attempt_{time.time_ns()}"
        before = once.sha256_file(checkpoint)
        evaluator(device, checkpoint, iteration, attempt)
        verified = once.verify(attempt, checkpoint, iteration)
        if verified["checkpoint_sha256"] != before or once.sha256_file(checkpoint) != before:
            raise RuntimeError("checkpoint changed during W15 evaluation")
        done = {"iteration": iteration, "checkpoint": str(checkpoint.resolve()),
                "checkpoint_sha256": before, "attempt_dir": str(attempt.resolve()),
                "authorization_ref": authorization_ref,
                "verified_modes": verified["modes"], "verified_commands": verified["commands"],
                "verified_sequences": verified["sequences"], "envs": verified["terrain_tiles"]}
        tmp = unit / f".done.{os.getpid()}.{time.time_ns()}.tmp"
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump(done, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, marker)
        outcomes.append(done)
    return outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("A", "B"), required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--final-iter", type=int, required=True)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--authorization-ref")
    parser.add_argument("--live", action="store_true")
    a = parser.parse_args(argv)
    result = (run_chain(a.run_dir, a.out_root, a.arm, a.final_iter, a.device,
                        a.authorization_ref or "") if a.live else
              plan(a.run_dir, a.out_root, a.arm, a.final_iter, require_done=False))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
