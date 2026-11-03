"""Sequential EX-41 fixed push ladder; coordinator itself does not import Kit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

from foothold_s2.eval.ex41_push_ladder import (
    MAP_MODES, TERRAIN_CASES,
)
from foothold_s2.eval.ex41_gpu_priority import gpu0_priority

GPU0_UUID = "c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"


def wait_for_gpu0_python_idle(*, timeout_seconds: float = 1800, poll_seconds: float = 5) -> dict[str, Any]:
    """Wait for other Python/Kit GPU0 users to leave, without signaling them."""
    import psutil

    start = time.monotonic()
    checks = 0
    last_busy: list[dict[str, Any]] = []
    while time.monotonic() - start <= timeout_seconds:
        checks += 1
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name", "--format=csv,noheader"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"GPU0 admission query failed rc={result.returncode}")
        busy = []
        for raw in result.stdout.splitlines():
            fields = [field.strip() for field in raw.split(",", 2)]
            if len(fields) != 3 or fields[0].casefold().removeprefix("gpu-") != GPU0_UUID:
                continue
            try:
                pid = int(fields[1])
            except ValueError:
                busy.append({"pid": None, "process_name": fields[2], "state": "unknown_pid"})
                continue
            if pid == os.getpid():
                continue
            try:
                process = psutil.Process(pid)
                name = process.name()
                command = " ".join(process.cmdline())
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError) as exc:
                busy.append({"pid": pid, "process_name": fields[2],
                             "state": f"unknown:{type(exc).__name__}"})
                continue
            if "python" in name.casefold() or "kit" in name.casefold() or "isaac" in command.casefold():
                busy.append({"pid": pid, "process_name": name, "command": command[:500], "state": "busy"})
        # Some Isaac child processes are briefly absent from nvidia-smi while
        # initializing or between Kit stages. The C-layer shard command itself
        # is also the scheduler's unit owner, so wait for that process to yield.
        known_pids = {row.get("pid") for row in busy}
        for process in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                info = process.info
                pid = int(info["pid"])
                command = " ".join(info.get("cmdline") or [])
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError, TypeError, ValueError):
                continue
            low = command.casefold()
            if pid == os.getpid() or pid in known_pids:
                continue
            if ("c_layer_shard.py" in low and "--gpu 0" in low) or (
                    "record_c_layer.py" in low and "--device cuda:0" in low):
                busy.append({"pid": pid, "process_name": info.get("name"),
                             "command": command[:500], "state": "c_layer_unit_active"})
        last_busy = busy
        if not busy:
            return {"state": "idle", "gpu_uuid": GPU0_UUID, "checks": checks,
                    "waited_seconds": time.monotonic() - start,
                    "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "last_busy": last_busy}
        time.sleep(poll_seconds)
    raise TimeoutError(json.dumps({"state": "HOLD", "gpu_uuid": GPU0_UUID,
                                   "checks": checks, "last_busy": last_busy}, ensure_ascii=False))


def bundle_cases(*, include_stand: bool = True) -> list[dict[str, Any]]:
    cases = [{"terrain": terrain, "map_mode": mode, "command": "walk_0.5",
              "directions": "full", "envs": 3072}
             for terrain in TERRAIN_CASES for mode in MAP_MODES]
    if include_stand:
        cases.extend({"terrain": "flat", "map_mode": mode, "command": "stand",
                      "directions": "cardinal", "envs": 1536}
                     for mode in MAP_MODES)
    return cases


def build_argv(case: dict[str, Any], *, checkpoint: Path, out: Path,
               device: str, task: str, seed: int) -> list[str]:
    return [sys.executable, "-m", "foothold_s2.eval.eval_map_modes",
            "--task", task, "--checkpoint", str(checkpoint), "--out", str(out),
            "--envs", str(case["envs"]), "--steps", "350", "--modes", case["map_mode"],
            "--command-suite", "core", "--commands", "all", "--fixed-terrain", "--fixed-level", "0",
            "--eval-seed", str(seed), "--push-ladder", "--push-ladder-terrain", case["terrain"],
            "--push-ladder-map-mode", case["map_mode"], "--push-ladder-command", case["command"],
            "--push-ladder-directions", case["directions"], "--headless", "--device", device,
            "--kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache"]


def run_bundle(checkpoint: Path, out: Path, *, device: str, task: str,
               seed: int = 42, include_stand: bool = True,
               checkpoint_iteration: int = 0) -> dict[str, Any]:
    if device == "cuda:0":
        with gpu0_priority(job="EX-41-push-ladder-eval", iteration=checkpoint_iteration,
                           run=str(out.resolve())) as owners:
            admission = wait_for_gpu0_python_idle()
            return _run_bundle(checkpoint, out, device=device, task=task, seed=seed,
                               include_stand=include_stand, priority_owners=owners,
                               checkpoint_iteration=checkpoint_iteration,
                               gpu0_admission=admission)
    return _run_bundle(checkpoint, out, device=device, task=task, seed=seed,
                       include_stand=include_stand, priority_owners=[],
                       checkpoint_iteration=checkpoint_iteration, gpu0_admission=None)


def _run_bundle(checkpoint: Path, out: Path, *, device: str, task: str,
                seed: int, include_stand: bool, priority_owners: list[dict[str, Any]],
                checkpoint_iteration: int, gpu0_admission: dict[str, Any] | None) -> dict[str, Any]:
    checkpoint = checkpoint.resolve(strict=True)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"fresh or empty output directory required: {out}")
    out.mkdir(parents=True, exist_ok=True)
    parent_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    env = dict(os.environ)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env.update(PYTHONUTF8="1", PYTHONUNBUFFERED="1", PYTHONPATH=str(Path(__file__).resolve().parents[2]),
               CUDA_DEVICE_ORDER="PCI_BUS_ID", KMP_DUPLICATE_LIB_OK="TRUE", OMNI_KIT_ACCEPT_EULA="YES")
    rows = []
    start = time.monotonic()
    for index, case in enumerate(bundle_cases(include_stand=include_stand), 1):
        child_out = out / f"{index:02d}_{case['terrain']}_{case['map_mode']}_{case['command']}"
        argv = build_argv(case, checkpoint=checkpoint, out=child_out, device=device, task=task, seed=seed)
        log_path = child_out.with_suffix(".log")
        child_out.mkdir(parents=True, exist_ok=False)
        child_start = time.monotonic()
        with log_path.open("w", encoding="utf-8", newline="\n") as log:
            process = subprocess.run(argv, cwd=Path(__file__).resolve().parents[2], env=env,
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result_path = child_out / "push_ladder.json"
        row: dict[str, Any] = {**case, "argv": argv, "rc": process.returncode,
                               "seconds": time.monotonic() - child_start,
                               "log": str(log_path.resolve())}
        if process.returncode == 0 and result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            row.update(state="done", summary=result["summary"],
                       result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
                       arrays=result.get("arrays"))
        else:
            row.update(state="HOLD", reason="child rc nonzero or push_ladder.json missing")
        rows.append(row)
        doc = {"schema": "foothold-ex41-push-ladder-bundle/1", "state": "running",
               "checkpoint": str(checkpoint), "checkpoint_sha256": parent_sha,
               "checkpoint_iteration": checkpoint_iteration,
               "device": device, "seed": seed, "priority_markers": priority_owners,
               "gpu0_admission": gpu0_admission,
               "children": rows,
               "elapsed_s": time.monotonic() - start}
        temp = out / "push_ladder_bundle.json.tmp"
        temp.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temp, out / "push_ladder_bundle.json")
        if row["state"] != "done":
            break
    complete = len(rows) == len(bundle_cases(include_stand=include_stand)) and all(r["state"] == "done" for r in rows)
    doc.update(state="done" if complete else "HOLD", elapsed_s=time.monotonic() - start,
               expected_children=len(bundle_cases(include_stand=include_stand)))
    temp.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, out / "push_ladder_bundle.json")
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="cuda:1", choices=("cuda:0", "cuda:1"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--kit_args", default=None)
    parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint-iteration", type=int, default=0)
    parser.add_argument("--no-stand", action="store_true")
    args = parser.parse_args()
    result = run_bundle(Path(args.checkpoint), Path(args.out), device=args.device, task=args.task,
                        seed=args.seed, include_stand=not args.no_stand,
                        checkpoint_iteration=args.checkpoint_iteration)
    print(json.dumps({"state": result["state"], "children": len(result["children"]),
                      "elapsed_s": result["elapsed_s"]}, sort_keys=True), flush=True)
    return 0 if result["state"] == "done" else 5


if __name__ == "__main__":
    raise SystemExit(main())
