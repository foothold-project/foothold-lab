"""Bounded EX-42 M1 through M4 throughput probe launcher for Linux.

No GPU work occurs without --execute. Each child uses the existing
--ex42_speed_probe 20/50-update path and its normal checkpoint writer.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time


PARENT_SHA256 = "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613"
FIRST_UPDATE_TIMEOUT_S = 300
STAGE_TIMEOUT_S = 5400
ITERATION = re.compile(r"Learning iteration\s+(\d+)\s*/\s*(\d+)")
SPECS = (
    ("M1", 1, 3072, 20),
    ("M2", 2, 1536, 20),
    ("M3", 2, 3072, 20),
    ("M4_single_a", 1, 3072, 50),
    ("M4_single_b", 1, 3072, 50),
    ("M4_dual", 2, 1536, 50),
)
MODULES = ("torch", "rsl_rl", "isaaclab", "isaacsim", "foothold_s2")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stage_command(python: Path, source: Path, source_ref: str, parent_manifest: Path,
                  queue: Path, out: Path, updates: int, envs: int, ranks: int) -> list[str]:
    score = [str(python), "-m", "foothold_s2.eval.eval_map_modes",
             "--task", "FootholdS2-Go2-S2-SB-v0",
             "--checkpoint", str(out / "model_{iteration}.pt"),
             "--out", str(out / "p1" / "score_{iteration}"),
             "--device", "cuda:1", "--envs", "64", "--steps", "300",
             "--modes", "eval_gt,eval_pred,probe_prop_only", "--headless"]
    command = [
        str(python), str(source / "foothold_s2/scripts/train_start.py"),
        "--task=FootholdS2-Go2-S2-SB-v0", "--device=cuda:0",
        f"--num_envs={envs}", f"--max_iterations={updates}", "--headless",
        f"--ex42_plan={source / 'foothold_s2/curriculum/ex42-prep.yaml'}",
        f"--ex42_approvals={source / 'foothold_s2/curriculum/ex42-approvals.yaml'}",
        f"--ex42_parent_manifest={parent_manifest}",
        f"--ex42_queue_path={queue}",
        f"--ex42_dispatch_path={source / '_out/tools/gpu_jobs/dispatch.py'}",
        f"--ex42_p1_score_argv_json={json.dumps(score, separators=(',', ':'))}",
        f"--ex42_source_ref={source_ref}", f"--ex42_log_dir={out}",
        "--ex42_stage_zero_approved", "--ex42_speed_probe",
    ]
    if ranks == 2:
        command.append("--distributed")
    return command


def check_modules(python: Path, source: Path) -> dict[str, bool]:
    code = ("import importlib.util,json;"
            f"names={MODULES!r};"
            "print(json.dumps({name: bool(importlib.util.find_spec(name)) for name in names}))")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([str(python), "-c", code], cwd=source, env=env,
                            capture_output=True, text=True, timeout=30, check=True)
    found = json.loads(result.stdout)
    if not all(found.values()):
        raise ValueError("missing training module: " + ",".join(k for k, v in found.items() if not v))
    return found


def validate_parent(manifest: Path) -> dict[str, str]:
    if not manifest.is_file():
        raise FileNotFoundError(f"parent manifest missing: {manifest}")
    checkpoint = manifest.parent / "model_6000.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"parent model_6000.pt missing beside manifest: {manifest}")
    actual = sha256_file(checkpoint)
    if actual != PARENT_SHA256:
        raise ValueError(f"parent SHA mismatch: {actual}")
    return {"manifest": str(manifest.resolve()), "checkpoint": str(checkpoint.resolve()),
            "sha256": actual}


def verify_launch(source: Path, source_ref: str, python: Path, manifest: Path,
                  queue: Path) -> dict:
    from foothold_s2.ex42_gate_checks import audit_ex42_launch_source

    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID":
        raise ValueError("CUDA_DEVICE_ORDER=PCI_BUS_ID required")
    if os.environ.get("OMNI_KIT_ACCEPT_EULA") != "YES":
        raise ValueError("OMNI_KIT_ACCEPT_EULA=YES required")
    if not python.is_file() or not queue.parent.is_dir():
        raise ValueError("configured Python or GPU queue directory missing")
    parent = validate_parent(manifest)
    modules = check_modules(python, source)
    locked = audit_ex42_launch_source(source, remote_ref=source_ref)
    return {"parent": parent, "modules": modules, "source": locked}


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def first_iteration_seen(log: Path) -> bool:
    if not log.is_file():
        return False
    return bool(ITERATION.search(log.read_text(encoding="utf-8", errors="replace")))


def stop_owned(processes: list[subprocess.Popen], grace_s: float = 10.0) -> None:
    """Stop only child groups created by this launcher, never an external PID."""
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + grace_s
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


def wait_for_first_iteration(processes: list[subprocess.Popen], rank0_log: Path,
                             timeout_s: float = FIRST_UPDATE_TIMEOUT_S,
                             *, clock=time.monotonic, pause=time.sleep) -> str:
    start = clock()
    while clock() - start < timeout_s:
        if first_iteration_seen(rank0_log):
            return "first_update"
        if all(process.poll() is not None for process in processes):
            return "exited_before_first_update"
        pause(1)
    return "first_update_timeout"


def wait_for_completion(processes: list[subprocess.Popen], timeout_s: float = STAGE_TIMEOUT_S,
                        *, clock=time.monotonic, pause=time.sleep) -> bool:
    start = clock()
    while clock() - start < timeout_s:
        if all(process.poll() is not None for process in processes):
            return True
        pause(1)
    return False


def sample_gpu(smi: str, out: Path, stop: threading.Event, interval_s: float = 1.0) -> None:
    query = [smi, "--query-gpu=index,uuid,utilization.gpu,memory.used",
             "--format=csv,noheader,nounits"]
    with out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("utc", "index", "uuid", "utilization_pct", "memory_mib"))
        while not stop.is_set():
            try:
                sample = subprocess.run(query, capture_output=True, text=True, timeout=5, check=True)
                for line in sample.stdout.splitlines():
                    cells = [cell.strip() for cell in line.split(",")]
                    if len(cells) == 4:
                        writer.writerow((utc_now(), *cells))
            except (OSError, subprocess.SubprocessError):
                writer.writerow((utc_now(), "sample_failed", "", "", ""))
            stream.flush()
            stop.wait(interval_s)


def write_json(path: Path, obj: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _rank_env(rank: int, ranks: int, port: int, tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({"MASTER_ADDR": "127.0.0.1", "MASTER_PORT": str(port),
                "WORLD_SIZE": str(ranks), "RANK": str(rank), "LOCAL_RANK": str(rank),
                "TMPDIR": str(tmp), "TEMP": str(tmp), "TMP": str(tmp),
                "PYTHONUNBUFFERED": "1"})
    env.pop("CUDA_VISIBLE_DEVICES", None)
    return env


def preflight_stages(root: Path, *, python: Path, source: Path, source_ref: str,
                     parent_manifest: Path, queue: Path) -> list[dict]:
    """Run the real train_start CPU exit before any AppLauncher child is started."""
    folder = root / "preflight"
    folder.mkdir()
    tmp = folder / "tmp"
    tmp.mkdir()
    receipts = []
    for name, ranks, envs, updates in SPECS:
        command = stage_command(python, source, source_ref, parent_manifest, queue,
                                root / name / "run", updates, envs, ranks)
        for rank in range(ranks):
            env = _rank_env(rank, ranks, 1, tmp)
            result = subprocess.run(
                [*command, "--ex42_stage_zero_dry_run"], cwd=root, env=env,
                capture_output=True, text=True, timeout=180)
            log = folder / f"{name}.rank{rank}.log"
            log.write_text(result.stdout + result.stderr, encoding="utf-8")
            passed = result.returncode == 0 and "EX42_STAGE_ZERO_PREFLIGHT " in result.stdout
            receipt = {"name": name, "rank": rank, "rc": result.returncode,
                       "passed": passed, "log": str(log)}
            receipts.append(receipt)
            if not passed:
                write_json(folder / "receipt.json", {"state": "failed", "rows": receipts})
                raise ValueError(f"EX-42 CPU preflight failed for {name} rank {rank}: {log}")
    write_json(folder / "receipt.json", {"state": "passed", "rows": receipts})
    return receipts


def run_stage(name: str, ranks: int, envs: int, updates: int, *, root: Path,
              python: Path, source: Path, source_ref: str, parent_manifest: Path,
              queue: Path, smi: str, stagger_s: float) -> dict:
    stage = root / name
    stage.mkdir(exist_ok=False)
    tmp = stage / "tmp"
    tmp.mkdir()
    out = stage / "run"
    command = stage_command(python, source, source_ref, parent_manifest, queue, out,
                            updates, envs, ranks)
    port = available_port()
    processes: list[subprocess.Popen] = []
    streams = []
    stop = threading.Event()
    gpu_thread = threading.Thread(target=sample_gpu, args=(smi, stage / "gpu.csv", stop),
                                  daemon=True)
    started = utc_now()
    state = "starting"
    error = None
    try:
        gpu_thread.start()
        for rank in range(ranks):
            log = stage / ("train.log" if rank == 0 else f"train.rank{rank}.log")
            stream = log.open("w", encoding="utf-8")
            streams.append(stream)
            process = subprocess.Popen(command, cwd=root, env=_rank_env(rank, ranks, port, tmp),
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            processes.append(process)
            if rank + 1 < ranks:
                time.sleep(stagger_s)
                if process.poll() is not None:
                    state = "rank0_exited_before_rank1"
                    break
        if state == "starting":
            state = wait_for_first_iteration(processes, stage / "train.log")
            if state == "first_update":
                if wait_for_completion(processes):
                    for process in processes:
                        process.wait()
                    state = "exited"
                else:
                    state = "stage_timeout"
                    stop_owned(processes)
            else:
                stop_owned(processes)
    except Exception as exc:
        state = "launch_error"
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if any(process.poll() is None for process in processes):
            stop_owned(processes)
        stop.set()
        if gpu_thread.is_alive():
            gpu_thread.join(timeout=6)
        for stream in streams:
            stream.close()
    rcs = [process.returncode for process in processes]
    rank1_private = (tmp / f"ex42_probe_rank1_{out.name}") if ranks == 2 else None
    # The rank-1 private path is a sibling of the shared run, never a child of it.
    rank1_shared = 0 if rank1_private is None or not rank1_private.is_relative_to(out) else None
    record = {"name": name, "state": state, "started_utc": started, "ended_utc": utc_now(),
              "ranks": ranks, "envs_per_rank": envs, "updates_requested": updates,
              "returncodes": rcs, "first_update_seen": first_iteration_seen(stage / "train.log"),
              "traceback_count": sum(p.read_text(encoding="utf-8", errors="replace").count("Traceback")
                                     for p in stage.glob("train*.log")),
              "shared_run": str(out), "rank1_private": str(rank1_private) if rank1_private else None,
              "rank1_shared_path_count": rank1_shared,
              "rank1_private_file_count": (sum(p.is_file() for p in rank1_private.rglob("*"))
                                           if rank1_private and rank1_private.exists() else 0),
              "gpu_csv": str(stage / "gpu.csv"), "command": command,
              "master_port": port, "error": error}
    write_json(stage / "stage.json", record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Explicitly launch GPU training probes")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-ref", default="origin/scripter/m-launch-1110")
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(os.environ.get("ISAAC311_PYTHON", "")))
    parser.add_argument("--queue", type=Path, default=Path(os.environ.get("GPU_JOBS_QUEUE", "")))
    parser.add_argument("--smi", default="nvidia-smi")
    parser.add_argument("--stagger-s", type=float, default=10.0)
    args = parser.parse_args(argv)
    source = args.source_root.resolve()
    plan = [{"name": name, "ranks": ranks, "envs_per_rank": envs,
             "updates": updates} for name, ranks, envs, updates in SPECS]
    if not args.execute:
        print(json.dumps({"state": "dry_run_only", "source": str(source),
                          "parent_manifest": str(args.parent_manifest),
                          "out_root": str(args.out_root), "stages": plan}, indent=2))
        return 0
    if args.out_root.exists():
        raise ValueError(f"output root already exists: {args.out_root}")
    proof = verify_launch(source, args.source_ref, args.python, args.parent_manifest, args.queue)
    if not shutil.which(args.smi) and not Path(args.smi).is_file():
        raise FileNotFoundError(f"nvidia-smi missing: {args.smi}")
    args.out_root.mkdir(parents=True)
    write_json(args.out_root / "preflight.json", proof)
    preflight_stages(args.out_root, python=args.python, source=source,
                     source_ref=args.source_ref, parent_manifest=args.parent_manifest,
                     queue=args.queue)
    failures = 0
    for name, ranks, envs, updates in SPECS:
        result = run_stage(name, ranks, envs, updates, root=args.out_root,
                           python=args.python, source=source, source_ref=args.source_ref,
                           parent_manifest=args.parent_manifest, queue=args.queue,
                           smi=args.smi, stagger_s=args.stagger_s)
        from foothold_s2.scripts.ex42_m_table import write_table
        summary = write_table(args.out_root)
        if (result["state"] != "exited" or any(rc != 0 for rc in result["returncodes"])
                or result["traceback_count"] or not result["first_update_seen"]
                or next(row for row in summary["rows"] if row["stage"] == name)["status"] != "complete"):
            failures += 1
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
