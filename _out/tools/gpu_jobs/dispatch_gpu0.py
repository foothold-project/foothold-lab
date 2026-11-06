"""GPU0 dispatcher entry point for EX-41 stage video after training ends.

Uses the live dispatcher's queue and lock, but keeps GPU0 status and logs apart.
Never starts training and never kills a process. Lead starts this after 22:00.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

SOURCE = Path("D:/mai-wt/foothold-lab/lead-dispatch-measure/_out/tools/gpu_jobs/dispatch.py")
SOURCE_SHA256 = "51ce32dc1c23ad431e8a14a587da68c8e44bc2af31613bf3a581f6adad122bd0"
QUEUE = "D:/mai-tmp/gpu/queue.json"
TRAIN_MARKER = "D:/mai-tmp/gpu/TRAINING_BUSY_GPU0"


def configure():
    if "CUDA_VISIBLE_DEVICES" in os.environ:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must be unset for physical GPU0 ordinal")
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("live dispatcher source SHA changed; recheck GPU0 adapter")
    spec = importlib.util.spec_from_file_location("gpu_jobs_live_dispatch", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if module.LIVE["queue"] != QUEUE or module.LIVE["train_marker"] != TRAIN_MARKER:
        raise RuntimeError("live queue or training marker contract changed")
    # The original runwrap child writes a result under this shared directory.
    # Distinct item IDs make sharing safe; separate status/logs avoid two writers.
    results = module.DISPATCH["results"]
    module.DISPATCH.update({
        "gpu": 0,
        "results": results,
        "state": "D:/mai-tmp/gpu/dispatch_gpu0_state.json",
        "logs": "D:/mai-tmp/gpu/logs_gpu0",
        "idle_log": "D:/mai-tmp/gpu/idle_gpu0.jsonl",
        "p1_markers": [TRAIN_MARKER],
        "p1_attempt_globs": [],
    })
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="configuration readback only, no dispatch")
    parser.add_argument("--once", action="store_true", help="one dispatcher cycle after lead approval")
    args = parser.parse_args(argv)
    module = configure()
    if args.check:
        print(json.dumps({"gpu": module.DISPATCH["gpu"], "queue": QUEUE,
                          "queue_lock": QUEUE + ".lock", "train_marker": TRAIN_MARKER,
                          "train_marker_state": module.marker_state(Path(TRAIN_MARKER)),
                          "state": module.DISPATCH["state"], "results": module.DISPATCH["results"],
                          "source_sha256": SOURCE_SHA256}, ensure_ascii=False, sort_keys=True))
        return 0
    return module.dispatch_loop(once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
