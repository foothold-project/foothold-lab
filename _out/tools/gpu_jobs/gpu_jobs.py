"""Read-only GPU job board and unit-boundary admission checks.

This tool never starts, signals, or kills a process. A lower-priority owner
must call ``gate`` before each new unit and yield after its current unit when
the answer is WAIT. Existing EX-35 and render owners retain their own gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from datetime import datetime, timezone

try:
    import psutil
except ImportError:  # Unknown liveness must not grant GPU access.
    psutil = None


PRIORITIES = {0: "승인된 학습", 1: "판정용 평가", 2: "진단·평가", 3: "시드 반복", 4: "영상 렌더"}
STATES = {"대기", "실행", "끝", "실패"}
WAIT_TOKENS = ("waiting_for_checkpoint", "checkpoint_wait", "waiting for checkpoint",
               "waiting for new checkpoint", "waiting for next checkpoint",
               "new checkpoint pending", "새 저장본 대기", "다음 저장본 대기",
               "저장본 대기", "새 체크포인트 대기", "다음 체크포인트 대기", "체크포인트 대기")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def validate(config: dict) -> list[dict]:
    jobs = config.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("jobs must be a list")
    seen = set()
    required = {"id", "priority", "gpu", "owner_session", "preemptible", "state",
                "started_at", "ended_at", "output_path"}
    for job in jobs:
        if not isinstance(job, dict) or not required.issubset(job):
            raise ValueError("job has missing required fields")
        if job["id"] in seen or not isinstance(job["id"], str):
            raise ValueError("duplicate or invalid job id")
        seen.add(job["id"])
        if type(job["priority"]) is not int or job["priority"] not in PRIORITIES:
            raise ValueError(f"invalid priority: {job['id']}")
        if type(job["gpu"]) is not int or job["gpu"] not in (0, 1):
            raise ValueError(f"invalid GPU: {job['id']}")
        if job["state"] not in STATES:
            raise ValueError(f"invalid state: {job['id']}")
        if not job.get("command") and not job.get("pid"):
            raise ValueError(f"command or pid required: {job['id']}")
        if type(job["preemptible"]) is not bool:
            raise ValueError(f"preemptible must be bool: {job['id']}")
    return jobs


def pid_state(job: dict) -> str:
    pid = job.get("pid")
    if not pid:
        return "no_pid"
    if psutil is None:
        return "unknown"
    try:
        process = psutil.Process(int(pid))
        expected = job.get("pid_create_time")
        if expected is not None and abs(process.create_time() - float(expected)) > 0.1:
            return "pid_reused"
        return "live" if process.is_running() else "gone"
    except psutil.NoSuchProcess:
        return "gone"
    except (psutil.AccessDenied, OSError, ValueError):
        return "unknown"


def marker_state(path: Path) -> dict:
    try:
        marker = read_json(path)
    except FileNotFoundError:
        return {"present": False, "reason": "absent"}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"present": True, "reason": f"unreadable:{type(exc).__name__}"}
    pids = []
    for key, value in marker.items():
        if key == "pid" or key.endswith("_pid") or key.endswith("_pids"):
            pids.extend(value if isinstance(value, list) else [value])
    pids = [p for p in pids if type(p) is int and p > 0]
    if not pids or psutil is None:
        return {"present": True, "reason": "unknown_owner", "pids": pids}
    states = [pid_state({"pid": p}) for p in pids]
    present = any(s != "gone" for s in states)
    return {"present": present, "reason": "live_or_unknown_pid" if present else "stale_pids",
            "pids": pids}


def chain_wait(path: Path) -> dict:
    try:
        last = next((line.strip() for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines())
                     if line.strip()), "")
    except OSError as exc:
        return {"waiting": False, "last": "", "error": type(exc).__name__}
    low = last.casefold()
    waiting = any(token in low for token in WAIT_TOKENS) or bool(
        re.search(r"대기.*(저장본|체크포인트)|(?:저장본|체크포인트).*대기", low))
    return {"waiting": waiting, "last": last}


def live_sources(config: dict) -> dict:
    sources = config.get("sources", {})
    marker = marker_state(Path(sources["priority_busy"]))
    chain = chain_wait(Path(sources["chain_log"]))
    try:
        render = read_json(Path(sources["render_state"]))
    except (OSError, ValueError, json.JSONDecodeError):
        render = {"state": "unknown", "pending": [], "current_job": None}
    return {"marker": marker, "chain": chain, "render": render}


def admission(config: dict, job_id: str, live: dict) -> tuple[bool, str]:
    jobs = validate(config)
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        raise ValueError(f"unknown job: {job_id}")
    if job["state"] != "대기":
        return False, f"not_waiting:{job['state']}"
    if not job.get("executable", True):
        return False, "unarmed_command"
    gpu, priority = job["gpu"], job["priority"]
    for higher in jobs:
        if higher["id"] == job_id or higher["gpu"] != gpu or higher["priority"] >= priority:
            continue
        if higher["state"] in ("끝", "실패"):
            continue
        if higher["state"] == "대기" and higher.get("executable", True):
            return False, f"higher_waiting:{higher['id']}"
        if higher["state"] == "실행":
            if higher["priority"] == 1 and not live["marker"]["present"] and live["chain"]["waiting"]:
                continue  # P1 waits for a checkpoint; lower work may fill the gap.
            return False, f"higher_active:{higher['id']}"
    if gpu == 1:
        if live["marker"]["present"] or not live["chain"]["waiting"]:
            return False, "p1_marker_or_chain_busy"
        render = live["render"]
        if priority < 4 and render.get("state") == "running":
            return False, "finish_current_render_item_then_yield"
    return True, "eligible_next_unit"


def status(config: dict, live: dict) -> str:
    jobs = validate(config)
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [f"GPU 작업 관리판 · {stamp}", "우선순위 P0 학습 > P1 판정 평가 > P2 진단 > P3 시드 반복 > P4 렌더"]
    for gpu in (0, 1):
        lines.append(f"GPU{gpu}")
        ordered = sorted((j for j in jobs if j["gpu"] == gpu), key=lambda j: (j["priority"], j["id"]))
        for job in ordered:
            pid = pid_state(job)
            label = f"P{job['priority']} {job['id']} · {job['state']}"
            if job.get("pid"):
                label += f" · PID {job['pid']} {pid}"
            if job["priority"] == 1:
                label += f" · marker={live['marker']['reason']} · chain_wait={live['chain']['waiting']}"
            if job["priority"] == 4:
                render = live["render"]
                label += f" · queue={render.get('state')} · current={render.get('current_job')}"
            if job["state"] == "대기":
                allowed, reason = admission(config, job["id"], live)
                label += f" · next={'GO' if allowed else 'WAIT'}:{reason}"
            lines.append("  " + label)
    lines.append("표는 관찰·다음 단위 진입 판단이다. 기존 프로세스를 선점하거나 새 작업을 기동하지 않는다.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("jobs.json"))
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    gate = sub.add_parser("gate")
    gate.add_argument("job_id")
    args = parser.parse_args(argv)
    config = read_json(args.config)
    live = live_sources(config)
    if args.action == "status":
        print(status(config, live))
        return 0
    allowed, reason = admission(config, args.job_id, live)
    print(json.dumps({"job": args.job_id, "admit_next_unit": allowed, "reason": reason}, ensure_ascii=False))
    return 0 if allowed else 3


if __name__ == "__main__":
    raise SystemExit(main())
