"""C76 GPU0 P4 gate while EX-41 training is P0."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def admission(config: dict, job_id: str) -> dict:
    job = next((item for item in config["jobs"] if item["id"] == job_id), None)
    if job is None or job["gpu"] != 0 or job["priority"] != 4:
        raise ValueError("registered GPU0 P4 job required")
    paths = config["sources"]["gpu0_training_markers"]
    if not isinstance(paths, list) or len(paths) != 2 or any(not Path(p).is_absolute() for p in paths):
        raise ValueError("GPU0 P0 marker paths missing")
    active = [path for path in paths if Path(path).exists()]
    return {"job": job_id, "admit_next_unit": not active,
            "reason": "gpu0_p0_marker" if active else "gpu0_p0_absent",
            "active_markers": active}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("gate").add_argument("job_id")
    args = parser.parse_args()
    result = admission(json.loads(args.config.read_text(encoding="utf-8-sig")), args.job_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["admit_next_unit"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
