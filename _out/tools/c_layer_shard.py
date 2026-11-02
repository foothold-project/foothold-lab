"""Run one assigned C76 cell with the immutable 5027e4ad queue.

The underlying queue still validates its full 216-cell registration. This
wrapper narrows which cell may be passed through --only-cell for each GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slot(row: dict) -> str:
    return f"{row['kind']}_L{row['level']}_{row['map_mode']}"


def inspect_plan(path: Path, gpu: int, out: Path) -> tuple[dict, list[str]]:
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = plan["jobs"]
    all_slots = [slot(row) for row in rows]
    if len(all_slots) != 216 or len(set(all_slots)) != 216:
        raise ValueError("full immutable C76 inventory must contain 216 unique cells")
    expected = all_slots[:108] if gpu == 1 else all_slots[108:]
    shard = plan.get("execution_shard") or {}
    if (shard.get("schema") != "c-layer-phase1-shard/1"
            or shard.get("gpu") != gpu or shard.get("assigned_cells") != expected
            or shard.get("output") != str(out.resolve())):
        raise ValueError("GPU shard is missing or assigned cells differ")
    runner = Path(shard.get("runner", ""))
    if not runner.is_file() or sha256(runner) != shard.get("runner_sha256"):
        raise ValueError("GPU shard runner SHA differs")
    for row in rows:
        argv = row["recorder_argv"]
        if argv[argv.index("--device") + 1] != f"cuda:{gpu}":
            raise ValueError("recorder GPU differs from shard")
    queue = Path(plan["queue"])
    if sha256(queue) != plan["queue_sha256"]:
        raise ValueError("frozen queue SHA differs")
    return plan, expected


def temporary_env(gpu: int, parent: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if parent is None else parent)
    temp = Path(f"D:/mai-tmp/c_layer_gpu{gpu}/tmp")
    temp.mkdir(parents=True, exist_ok=True)
    env["TMP"] = env["TEMP"] = str(temp)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    env.pop("CUDA_VISIBLE_DEVICES", None)
    return env


def priority_hold(plan: dict, gpu: int) -> str | None:
    shard = plan["execution_shard"]
    for marker in shard["priority_markers"]:
        if Path(marker).exists():
            return marker
    if gpu == 0 and not shard["priority_markers"]:
        raise ValueError("GPU0 P0 training marker is required")
    return None


def completed_receipt(path: Path, cell: str, checkpoint_sha256: str) -> bool:
    if not path.exists():
        return False
    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    video = Path(receipt.get("video", ""))
    if (receipt.get("format") != "foothold-c-layer-canonical/1"
            or receipt.get("canonical") is not True or receipt.get("cell") != cell
            or receipt.get("own_result") != "success"
            or receipt.get("checkpoint_sha256") != checkpoint_sha256
            or not video.is_file() or sha256(video) != receipt.get("video_sha256")):
        raise ValueError("existing shard receipt is incomplete or corrupted")
    return True


def technical_hold(out: Path, cell: str, *, limit: int = 3) -> dict | None:
    """Hold a cell after closed technical failures, without spending seed budget."""
    root = out / "attempts" / cell
    if not root.exists():
        return None
    attempts = sorted(path for path in root.iterdir() if path.is_dir() and path.name.isdecimal())
    failures = []
    validated = 0
    for attempt in attempts:
        closed_path = attempt / "closed.json"
        if not closed_path.is_file():
            return None  # An incomplete attempt is a queue HOLD, never a retryable failure.
        closed = json.loads(closed_path.read_text(encoding="utf-8-sig"))
        if closed.get("state") == "validated":
            validated += 1
        if closed.get("state") == "failed":
            failure_path = attempt / "failure.json"
            if not failure_path.is_file():
                raise ValueError("closed technical failure has no failure receipt")
            failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
            if failure.get("cell") != cell or failure.get("ordinal") != int(attempt.name):
                raise ValueError("technical failure receipt differs from attempt")
            failures.append(str(failure_path))
    if len(failures) < limit:
        return None
    return {"state": "cell_technical_hold", "cell": cell,
            "technical_failures": len(failures), "seed_budget_spent": validated,
            "failure_receipts": failures}


def record_hold(out: Path, hold: dict) -> None:
    destination = out / "shard_holds" / (hold["cell"] + ".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(hold, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


def run_one(path: Path, out: Path, gpu: int, *, check_only: bool = False) -> dict:
    plan, assigned = inspect_plan(path, gpu, out)
    env = temporary_env(gpu)
    queue = Path(plan["queue"])
    env["PYTHONPATH"] = os.pathsep.join([str(queue.parents[2]), env.get("PYTHONPATH", "")])
    python = Path(plan["jobs"][0]["recorder_argv"][0])
    validated = subprocess.run([str(python), str(queue), str(path), "--out", str(out)], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", env=env, check=False)
    if validated.returncode:
        raise ValueError("frozen queue rejected shard plan: " + validated.stderr[-500:])
    summary = json.loads(validated.stdout)
    if summary.get("expected") != 216 or summary.get("ready") != 216:
        raise ValueError("frozen queue did not validate all registered cells")
    if check_only:
        return {"state": "checked", "gpu": gpu, "assigned": len(assigned),
                "first": assigned[0], "last": assigned[-1], "queue_sha256": sha256(queue)}
    held = []
    for cell in assigned:
        hold = priority_hold(plan, gpu)
        if hold is not None:
            return {"state": "yielded_to_training_or_evaluation", "marker": hold, "next": cell}
        receipt = out / "receipts" / (cell + "_success.json")
        if completed_receipt(receipt, cell, plan["checkpoint_sha256"]):
            continue
        cell_hold = technical_hold(out, cell)
        if cell_hold is not None:
            record_hold(out, cell_hold)
            held.append(cell_hold)
            continue
        command = [str(python), str(queue), str(path), "--out", str(out),
                   "--run-one", "--only-cell", cell]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", env=env, check=False)
        if result.returncode:
            raise ValueError("frozen queue failed: " + result.stderr[-500:])
        event = json.loads(result.stdout)
        if event.get("state") == "only_cell_closed":
            continue
        cell_hold = technical_hold(out, cell)
        if cell_hold is not None:
            record_hold(out, cell_hold)
            held.append(cell_hold)
            continue
        return {"state": event.get("state", "queue_event_unknown"),
                "gpu": gpu, "cell": cell, "queue_event": event, "held": held}
    return {"state": "assigned_cells_with_holds" if held else "assigned_cells_complete",
            "gpu": gpu, "assigned": len(assigned), "held": held}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--gpu", type=int, choices=(0, 1), required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    result = run_one(args.plan, args.out.resolve(), args.gpu, check_only=args.check_only)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
