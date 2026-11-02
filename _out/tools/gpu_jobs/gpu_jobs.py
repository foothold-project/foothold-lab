"""Read-only P4 admission gate for EX-41 evaluation and video jobs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


def marker_state(path: Path) -> dict:
    if not path.exists():
        return {"state": "absent", "blocks": False}
    try:
        marker = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(marker, dict) or not isinstance(marker.get("job"), str):
            raise ValueError("job missing")
        pid, created = marker["pid"], marker["process_create_time"]
        if type(pid) is not int or pid <= 0 or type(created) not in (int, float):
            raise ValueError("invalid process identity")
        if not isinstance(marker["started_at"], str) or type(marker["iteration"]) is not int:
            raise ValueError("invalid start or iteration")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"state": "unknown", "blocks": True, "reason": type(exc).__name__}
    if psutil is None:
        return {"state": "unknown", "blocks": True, "reason": "psutil_unavailable"}
    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - float(created)) > 0.1 or not process.is_running():
            return {"state": "stale", "blocks": False, "pid": pid}
    except psutil.NoSuchProcess:
        return {"state": "stale", "blocks": False, "pid": pid}
    except (psutil.AccessDenied, OSError, ValueError) as exc:
        return {"state": "unknown", "blocks": True, "reason": type(exc).__name__}
    return {"state": "active", "blocks": True, "pid": pid, "job": marker["job"]}


def admission(config: dict, job_id: str) -> dict:
    job = next((item for item in config["jobs"] if item["id"] == job_id), None)
    if job is None or job["priority"] != 4 or job["gpu"] != 1:
        raise ValueError("registered GPU1 P4 job required")
    marker = marker_state(Path(config["sources"]["ex41_p1_marker"]))
    return {"job": job_id, "admit_next_unit": not marker["blocks"],
            "reason": "ex41_p1_" + marker["state"], "marker": marker}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("jobs.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("gate").add_argument("job_id")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    if args.command == "status":
        print(json.dumps({"jobs": config["jobs"],
                          "ex41_p1": marker_state(Path(config["sources"]["ex41_p1_marker"]))}, ensure_ascii=False))
        return 0
    result = admission(config, args.job_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["admit_next_unit"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
