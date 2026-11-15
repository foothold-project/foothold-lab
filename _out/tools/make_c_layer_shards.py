"""Split a full immutable C76 registration into two disjoint execution lists."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil


GPU0_MARKERS = ["C:/Users/AI-WS01/s2_lab/c_layer_m6000/priority/TRAINING_BUSY",
                "D:/mai-tmp/gpu/TRAINING_BUSY_GPU0"]
GPU1_MARKERS = ["D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slot(row: dict) -> str:
    return f"{row['kind']}_L{row['level']}_{row['map_mode']}"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def build(base: dict, outdir: Path, gpu1_out: Path, gpu0_out: Path,
          gpu0_gate_source: Path, shard_source: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    slots = [slot(row) for row in base["jobs"]]
    if len(slots) != 216 or len(set(slots)) != 216:
        raise ValueError("base plan is not the full 216-cell inventory")
    gate = outdir / "gpu0_gate.py"
    wrapper = outdir / "c_layer_shard.py"
    shutil.copyfile(gpu0_gate_source, gate)
    shutil.copyfile(shard_source, wrapper)
    config = {
        "schema": "foothold-gpu-jobs-v2",
        "sources": {"ex41_p1_marker": "D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1",
                    "gpu0_training_markers": GPU0_MARKERS},
        "jobs": [{"id": "c-layer", "priority": 4, "gpu": 0,
                  "owner_session": "scripter", "preemptible": True,
                  "state": "waiting", "output_path": str(gpu0_out.resolve())}],
    }
    config_path = outdir / "gpu0_jobs.json"
    write_json(config_path, config)
    paths = {}
    for gpu, output in ((1, gpu1_out), (0, gpu0_out)):
        plan = copy.deepcopy(base)
        assigned = slots[:108] if gpu == 1 else slots[108:]
        for row in plan["jobs"]:
            argv = row["recorder_argv"]
            argv[argv.index("--device") + 1] = f"cuda:{gpu}"
        plan["execution_shard"] = {
            "schema": "c-layer-phase1-shard/1", "gpu": gpu,
            "assigned_cells": assigned, "output": str(output.resolve()),
            "priority_markers": GPU1_MARKERS if gpu == 1 else GPU0_MARKERS,
            "runner": str(wrapper), "runner_sha256": sha256(wrapper),
        }
        plan["priority_markers"]["training"] = (
            GPU1_MARKERS[0] if gpu == 1 else GPU0_MARKERS[0])
        if gpu == 0:
            plan["gpu_jobs_tool"] = str(gate)
            plan["gpu_jobs_tool_sha256"] = sha256(gate)
            plan["gpu_jobs_config"] = str(config_path)
            plan["gpu_jobs_config_sha256"] = sha256(config_path)
        path = outdir / f"phase1_gpu{gpu}.json"
        write_json(path, plan)
        paths[f"gpu{gpu}"] = {"path": str(path), "sha256": sha256(path),
                               "assigned": len(assigned), "first": assigned[0],
                               "last": assigned[-1], "out": str(output.resolve())}
    if set(slots[:108]) & set(slots[108:]) or set(slots[:108]) | set(slots[108:]) != set(slots):
        raise AssertionError("shards overlap or omit cells")
    return {"schema": "c-layer-phase1-shard-manifest/1", "plans": paths,
            "gpu0_gate_sha256": sha256(gate), "runner_sha256": sha256(wrapper),
            "union_cells": 216, "intersection_cells": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--gpu1-out", type=Path, required=True)
    parser.add_argument("--gpu0-out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = build(json.loads(args.base.read_text(encoding="utf-8-sig")),
                   args.outdir, args.gpu1_out, args.gpu0_out,
                   root / "c_layer_gpu0_gate.py", root / "c_layer_shard.py")
    write_json(args.outdir / "shard_manifest.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
