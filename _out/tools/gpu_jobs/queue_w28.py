"""One durable queue for short GPU units and CPU composition units.

An operator starts one ``serve`` process per GPU. Registration alone then
supplies work. A unit already running is never interrupted; priority is
rechecked before the next unit. This file does not grant experiment approval.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Callable
from uuid import uuid4


STATES = {"waiting", "running", "done", "failed", "hold"}
KINDS = {"training", "judge", "diagnostic", "repeat", "capture", "compose"}
PRIORITY = {"training": 0, "judge": 1, "diagnostic": 2, "repeat": 3,
            "capture": 4, "compose": 4}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@contextmanager
def locked(path: Path):
    """Cross-process lock; crash releases the OS lock, not a stale claim file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def read(path: Path) -> dict:
    if not path.exists():
        return {"schema": "foothold-gpu-unit-queue-v1", "jobs": []}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if value.get("schema") != "foothold-gpu-unit-queue-v1" or not isinstance(value.get("jobs"), list):
        raise ValueError("queue schema or jobs invalid")
    return value


def publish(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def validate(job: dict) -> dict:
    if not isinstance(job, dict):
        raise ValueError("job must be an object")
    for key in ("id", "kind", "owner", "authorization_ref", "output", "cwd"):
        if not isinstance(job.get(key), str) or not job[key].strip():
            raise ValueError(f"missing or empty {key}")
    if job["kind"] not in KINDS:
        raise ValueError("unknown kind")
    if job.get("priority") != PRIORITY[job["kind"]]:
        raise ValueError("priority must match kind")
    gpu = job.get("gpu")
    if gpu not in (0, 1, None) or (gpu is None) != (job["kind"] == "compose"):
        raise ValueError("GPU 0/1 required except CPU composition")
    if gpu is not None and (not isinstance(job.get("gpu_uuid"), str)
                            or not job["gpu_uuid"].startswith("GPU-")):
        raise ValueError("GPU job needs a pinned gpu_uuid")
    argv = job.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        raise ValueError("argv must be a nonempty string array")
    if not isinstance(job.get("units"), list) or not job["units"]:
        raise ValueError("units must be nonempty")
    if job.get("ready_file") is not None and not isinstance(job["ready_file"], str):
        raise ValueError("ready_file must be a path")
    seen = set()
    for unit in job["units"]:
        if not isinstance(unit, dict) or not isinstance(unit.get("id"), str) or not unit["id"]:
            raise ValueError("unit id missing")
        if unit["id"] in seen:
            raise ValueError("duplicate unit")
        seen.add(unit["id"])
        if not isinstance(unit.get("args", []), list) or not all(isinstance(a, str) for a in unit.get("args", [])):
            raise ValueError("unit args invalid")
        verifier = unit.get("verify_argv")
        if job["kind"] in ("capture", "compose") and not verifier:
            raise ValueError("capture/compose needs verify_argv")
        if verifier is not None and (not isinstance(verifier, list) or not verifier or
                                     not all(isinstance(a, str) and a for a in verifier)):
            raise ValueError("verify_argv invalid")
        check_device_arguments(job, unit)
    return job


def check_device_arguments(job: dict, unit: dict) -> None:
    """Require the Isaac/CUDA device ordinal to equal the registered GPU."""
    launch = [*job["argv"], *unit.get("args", [])]
    verify = unit.get("verify_argv") or []
    gpu = job["gpu"]
    for command in (launch, verify):
        for i, token in enumerate(command):
            if token.startswith(("--device=", "--gpu-id=", "--gpu-index=",
                                 "--rendering_device=", "--renderer-gpu-id=")):
                raise ValueError("inline device flags are not part of the pinned GPU contract")
            if token.startswith("cuda:") and token != f"cuda:{gpu}":
                raise ValueError("device ordinal conflicts with pinned GPU UUID")
            if token in ("--gpu-index", "--rendering_device", "--renderer-gpu-id"):
                raise ValueError("unverified physical renderer GPU flag")
            if token in ("--device", "--gpu-id"):
                if i + 1 >= len(command):
                    raise ValueError("device flag has no value")
                expected = f"cuda:{gpu}" if token == "--device" else str(gpu)
                if gpu is None or command[i + 1] != expected:
                    raise ValueError("device flag conflicts with pinned GPU UUID or CPU lane")
    if gpu is not None and sum(launch[i:i + 2] == ["--device", f"cuda:{gpu}"]
                               for i in range(len(launch) - 1)) != 1:
        raise ValueError("GPU launch needs exactly one registered --device cuda:N")
    if gpu is None and any(token.startswith("cuda:") for token in (*launch, *verify)):
        raise ValueError("CPU composition cannot select CUDA")


def register(queue_path: Path, spec: dict) -> dict:
    spec = validate(spec)
    with locked(queue_path.with_suffix(".lock")):
        queue = read(queue_path)
        if any(j["id"] == spec["id"] for j in queue["jobs"]):
            raise ValueError("duplicate job id")
        job = {**spec, "state": "waiting", "registered_at": now(), "started_at": None,
               "ended_at": None, "next_unit": 0, "results": [], "claim": None}
        queue["jobs"].append(job)
        publish(queue_path, queue)
        return job


def probe_gpu(gpu: int) -> tuple[bool, str]:
    cmd = ["nvidia-smi", "--id", str(gpu), "--query-compute-apps=pid",
           "--format=csv,noheader,nounits"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, type(exc).__name__
    if result.returncode:
        return False, "nvidia_smi_failed"
    return (not bool(result.stdout.strip()), "gpu_idle" if not result.stdout.strip() else "gpu_busy")


def external_clear(job: dict, sources: dict) -> tuple[bool, str]:
    """Older P1 chain and renderer remain independent until their owners migrate."""
    if job["gpu"] != 1 or job["priority"] <= 1:
        return True, "no_external_gate"
    marker = sources.get("priority_busy")
    if marker:
        from gpu_jobs import marker_state
        observed = marker_state(Path(marker))
        if observed["present"]:
            return False, "priority_busy_marker:" + observed["reason"]
    chain = sources.get("chain_log")
    if chain:
        try:
            last = next((s for s in reversed(Path(chain).read_text(encoding="utf-8").splitlines()) if s.strip()), "")
        except OSError:
            return False, "chain_state_unknown"
        if not any(token in last.casefold() for token in ("waiting_for_checkpoint", "checkpoint_wait", "저장본 대기", "체크포인트 대기")):
            return False, "chain_not_waiting"
    return True, "external_clear"


def choose(queue: dict, gpu: int | None) -> dict | None:
    runnable = [j for j in queue["jobs"] if j["gpu"] == gpu and j["state"] == "waiting"
                and (not j.get("ready_file") or Path(j["ready_file"]).is_file())]
    return min(runnable, key=lambda j: (j["priority"], j["registered_at"], j["id"])) if runnable else None


def claim_one(queue_path: Path, gpu: int | None, idle: Callable[[int], tuple[bool, str]] = probe_gpu,
              sources: dict | None = None) -> tuple[dict | None, str]:
    with locked(queue_path.with_suffix(".lock")):
        queue = read(queue_path)
        if any(c["gpu"] == gpu for c in queue.get("legacy_claims", [])):
            return None, "legacy_renderer_claim_requires_review"
        if any(j["gpu"] == gpu and j["state"] == "running" for j in queue["jobs"]):
            return None, "existing_claim_requires_review"
        job = choose(queue, gpu)
        if job is None:
            return None, "no_waiting_job"
        clear, reason = external_clear(job, sources or {})
        if not clear:
            return None, reason
        if gpu is not None:
            clear, reason = idle(gpu)
            if not clear:
                return None, reason
        job["state"] = "running"
        job["claim"] = {"pid": os.getpid(), "at": now(), "unit": job["units"][job["next_unit"]]["id"]}
        if job["started_at"] is None:
            job["started_at"] = now()
        publish(queue_path, queue)
        return json.loads(json.dumps(job)), "claimed"


def legacy_claim(queue_path: Path, gpu: int, job_id: str) -> tuple[str | None, str]:
    """Reserve a unit for the old renderer under the same queue lock."""
    with locked(queue_path.with_suffix(".lock")):
        queue = read(queue_path)
        if any(j["gpu"] == gpu and j["state"] == "running" for j in queue["jobs"]):
            return None, "new_queue_claimed"
        if any(c["gpu"] == gpu for c in queue.get("legacy_claims", [])):
            return None, "legacy_renderer_claimed"
        token = uuid4().hex
        queue.setdefault("legacy_claims", []).append({
            "gpu": gpu, "job_id": job_id, "pid": os.getpid(), "token": token, "at": now()})
        publish(queue_path, queue)
        return token, "legacy_claimed"


def legacy_release(queue_path: Path, token: str) -> None:
    with locked(queue_path.with_suffix(".lock")):
        queue = read(queue_path)
        claims = queue.get("legacy_claims", [])
        matched = [c for c in claims if c["token"] == token and c["pid"] == os.getpid()]
        if len(matched) != 1:
            raise ValueError("legacy claim missing or not owned")
        queue["legacy_claims"] = [c for c in claims if c is not matched[0]]
        publish(queue_path, queue)


def pinned_gpu_uuid(gpu: int) -> str:
    result = subprocess.run(["nvidia-smi", "--id", str(gpu), "--query-gpu=uuid",
                             "--format=csv,noheader,nounits"], capture_output=True,
                            text=True, timeout=10, check=False)
    if result.returncode or len(result.stdout.splitlines()) != 1:
        raise RuntimeError("gpu_uuid_probe_failed")
    return result.stdout.strip()


def execute(job: dict, unit: dict, uuid_probe=pinned_gpu_uuid) -> tuple[int, str]:
    validate(job)
    argv = [*job["argv"], *unit.get("args", [])]
    child_env = os.environ.copy()
    child_env.pop("CUDA_VISIBLE_DEVICES", None)
    child_env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    if job["gpu"] is None:
        child_env["CUDA_VISIBLE_DEVICES"] = ""
    else:
        if uuid_probe(job["gpu"]) != job["gpu_uuid"]:
            raise RuntimeError("registered_gpu_uuid_mismatch")
    output = Path(job["output"])
    output.mkdir(parents=True, exist_ok=True)
    log = output / f"{job['id']}.{unit['id']}.log"
    with log.open("ab") as stream:
        result = subprocess.run(argv, cwd=job["cwd"], env=child_env,
                                stdout=stream, stderr=subprocess.STDOUT,
                                check=False)
        if result.returncode == 0 and unit.get("verify_argv"):
            result = subprocess.run(unit["verify_argv"], cwd=job["cwd"], env=child_env,
                                    stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
    return result.returncode, str(log)


def finish_unit(queue_path: Path, job_id: str, unit_id: str, rc: int, log: str,
                check: Callable[[dict, dict], tuple[bool, str]] | None = None) -> str:
    with locked(queue_path.with_suffix(".lock")):
        queue = read(queue_path)
        job = next(j for j in queue["jobs"] if j["id"] == job_id)
        claim = job.get("claim")
        if job["state"] != "running" or not isinstance(claim, dict) or claim.get("pid") != os.getpid() or claim.get("unit") != unit_id:
            raise ValueError("claim mismatch")
        unit = job["units"][job["next_unit"]]
        if unit["id"] != unit_id:
            raise ValueError("unit order mismatch")
        passed, detail = (check(job, unit) if rc == 0 and check else (rc == 0, "exit_code"))
        job["results"].append({"unit": unit_id, "rc": rc, "passed": passed, "detail": detail,
                               "log": log, "ended_at": now()})
        job["claim"] = None
        if not passed:
            job["state"] = "failed"
            job["ended_at"] = now()
        else:
            job["next_unit"] += 1
            if job["next_unit"] == len(job["units"]):
                job["state"] = "done"
                job["ended_at"] = now()
            else:
                job["state"] = "waiting"
        publish(queue_path, queue)
        return job["state"]


def one(queue_path: Path, gpu: int | None, idle=probe_gpu, sources: dict | None = None,
        executor=execute, check=None) -> tuple[str, str]:
    job, reason = claim_one(queue_path, gpu, idle, sources)
    if job is None:
        return "waiting", reason
    unit = job["units"][job["next_unit"]]
    try:
        rc, log = executor(job, unit)
    except Exception as exc:
        rc, log = 1, f"executor_exception:{type(exc).__name__}:{exc}"
    state = finish_unit(queue_path, job["id"], unit["id"], rc, log, check)
    return state, job["id"] + "/" + unit["id"]


def screen(queue: dict) -> str:
    lines = ["GPU 작업 단일 등록부 · " + now()]
    for gpu in (0, 1, None):
        label = "CPU 합성" if gpu is None else f"GPU{gpu}"
        lines.append(label)
        for claim in queue.get("legacy_claims", []):
            if claim["gpu"] == gpu:
                lines.append(f"  legacy-renderer {claim['job_id']} running pid={claim['pid']}")
        for job in sorted((j for j in queue["jobs"] if j["gpu"] == gpu),
                          key=lambda j: (j["priority"], j["registered_at"])):
            lines.append(f"  P{job['priority']} {job['id']} {job['state']} {job['next_unit']}/{len(job['units'])} {job['owner']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("spec", type=Path)
    sub.add_parser("status")
    run = sub.add_parser("serve")
    run.add_argument("--gpu", choices=("0", "1", "cpu"), required=True)
    run.add_argument("--poll-s", type=float, default=10)
    run.add_argument("--sources", type=Path)
    args = parser.parse_args(argv)
    if args.action == "register":
        job = register(args.queue, json.loads(args.spec.read_text(encoding="utf-8-sig")))
        print(job["id"])
        return 0
    if args.action == "status":
        print(screen(read(args.queue)))
        return 0
    gpu = None if args.gpu == "cpu" else int(args.gpu)
    sources = json.loads(args.sources.read_text(encoding="utf-8-sig")) if args.sources else {}
    while True:
        state, detail = one(args.queue, gpu, sources=sources)
        print(json.dumps({"state": state, "detail": detail, "at": now()}, ensure_ascii=False), flush=True)
        if state == "waiting":
            time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
