"""Move only the unfilmed GPU0 C-layer cells to the frozen GPU1 queue.

The registered 216-cell plan stays intact for the C76 validator. This wrapper
chooses the remaining cells, runs one frozen queue transaction at a time, and
checks the EX-41 P1 gate and training time before the next transaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

from foothold_s2.eval.recompose_c_layer_v34 import (
    EXPECTED_CHECKPOINT, canonical_sources, read_json, sha256, verify_new,
    write_playlist,
)
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, require_video_rule


BASELINE_S = 27.0
SLOWDOWN_LIMIT_S = BASELINE_S * 1.10
MAX_TECHNICAL_FAILURES = 3


def slot(row: dict) -> str:
    return f"{row['kind']}_L{row['level']}_{row['map_mode']}"


def create_manifest(old_plan: Path, old_out: Path, new_plan: Path, new_out: Path,
                    training_status: Path, target: Path) -> dict:
    if target.exists():
        raise ValueError("remaining-cell manifest already exists")
    previous = read_json(old_plan)
    new = read_json(new_plan)
    assigned = previous["execution_shard"]["assigned_cells"]
    if len(assigned) != 108 or len(set(assigned)) != 108:
        raise ValueError("GPU0 assigned inventory differs from 108 cells")
    sources = canonical_sources(old_out)
    done = {receipt["cell"]: (path, receipt) for path, _, receipt in sources}
    if len(done) != 27 or not set(done).issubset(assigned):
        raise ValueError("27 completed GPU0 cells are not a subset of assignment")
    remaining = [cell for cell in assigned if cell not in done]
    if len(remaining) != 81:
        raise ValueError("remaining GPU0 cells must be exactly 81")
    rows = {slot(row): row for row in new["jobs"]}
    if (len(rows) != 216 or new["target_results"] != ["success"]
            or new["checkpoint_sha256"] != EXPECTED_CHECKPOINT
            or any(row["recorder_argv"][row["recorder_argv"].index("--device") + 1]
                   != "cuda:1" for row in new["jobs"])):
        raise ValueError("new full plan is not the GPU1 first-success contract")
    if any(cell not in rows or len(rows[cell]["seeds"]) > 4 for cell in remaining):
        raise ValueError("remaining cell or seed contract differs")
    manifest = {
        "format": "foothold-c-layer-gpu1-remainder/1",
        "old_plan": str(old_plan.resolve()), "old_plan_sha256": sha256(old_plan),
        "old_out": str(old_out.resolve()),
        "completed_source_receipts": {cell: sha256(path) for cell, (path, _) in done.items()},
        "new_plan": str(new_plan.resolve()), "new_plan_sha256": sha256(new_plan),
        "new_out": str(new_out.resolve()),
        "training_status": str(training_status.resolve()),
        "baseline_update_s": BASELINE_S, "slowdown_limit_s": SLOWDOWN_LIMIT_S,
        "max_technical_failures": MAX_TECHNICAL_FAILURES,
        "remaining_cells": remaining,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_manifest(path: Path, wanted_sha256: str) -> tuple[dict, dict]:
    if sha256(path) != wanted_sha256:
        raise ValueError("remaining manifest SHA changed")
    manifest = read_json(path)
    if manifest.get("format") != "foothold-c-layer-gpu1-remainder/1":
        raise ValueError("remaining manifest format differs")
    old_plan, new_plan = Path(manifest["old_plan"]), Path(manifest["new_plan"])
    if (sha256(old_plan) != manifest["old_plan_sha256"]
            or sha256(new_plan) != manifest["new_plan_sha256"]):
        raise ValueError("source plan SHA changed")
    old_out = Path(manifest["old_out"])
    for cell, digest in manifest["completed_source_receipts"].items():
        if sha256(old_out / "receipts" / (cell + "_success.json")) != digest:
            raise ValueError("one of the 27 completed receipts changed")
    return manifest, read_json(new_plan)


def checked_success(out: Path, cell: str, plan: dict) -> Path | None:
    path = out / "receipts" / (cell + "_success.json")
    if not path.exists():
        return None
    receipt = read_json(path)
    video = Path(receipt["video"])
    if (receipt.get("format") != "foothold-c-layer-canonical/1"
            or receipt.get("canonical") is not True or receipt.get("cell") != cell
            or receipt.get("own_result") != "success"
            or receipt.get("checkpoint_sha256") != EXPECTED_CHECKPOINT
            or receipt.get("video_rule_version") != VIDEO_RULE_VERSION
            or receipt.get("composer_sha256") != plan["composer_sha256"]
            or video.parent != out or sha256(video) != receipt["video_sha256"]):
        raise ValueError("new canonical success receipt differs")
    attempt = Path(receipt["attempt_dir"])
    styled = read_json(attempt / "styled.json")
    require_video_rule(styled, composer_sha256=plan["composer_sha256"])
    audit = read_json(attempt / "styled_frame_audit.json")
    if audit.get("pass") is not True or audit.get("frames") != 450:
        raise ValueError("new canonical styled audit HOLD")
    return video


def technical_failures(out: Path, cell: str) -> tuple[int, bool]:
    root = out / "attempts" / cell
    failures = 0
    incomplete = False
    if root.exists():
        for attempt in root.iterdir():
            if not attempt.is_dir() or not attempt.name.isdecimal():
                continue
            closed = attempt / "closed.json"
            if not closed.is_file():
                incomplete = True
                continue
            if read_json(closed).get("state") == "failed":
                if not (attempt / "failure.json").is_file():
                    raise ValueError("closed technical failure lacks receipt")
                failures += 1
    return failures, incomplete


def gate(plan: dict) -> dict:
    tool = Path(plan["gpu_jobs_tool"])
    command = [plan["jobs"][0]["recorder_argv"][0], str(tool),
               "--config", plan["gpu_jobs_config"], "gate", "c-layer"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 3):
        raise ValueError("GPU1 P4 gate failed: " + result.stderr[-500:])
    state = json.loads(result.stdout)
    if state.get("admit_next_unit") is not (result.returncode == 0):
        raise ValueError("GPU1 P4 gate result differs from exit code")
    return state


def train_sample(path: Path) -> dict | None:
    try:
        # The runner writes this JSON every ten updates, not every update.
        if time.time() - path.stat().st_mtime > 600:
            return None
        row = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if row.get("state") != "running" or type(row.get("iter")) is not int:
        return None
    value = row.get("iter_s")
    if type(value) not in (int, float) or not 0 < float(value) < 300:
        return None
    try:
        if not psutil.Process(int(row["pid"])).is_running():
            return None
    except (KeyError, TypeError, ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
        return None
    return {"iter": row["iter"], "iter_s": float(value), "time": row.get("time"),
            "pid": row.get("pid")}


def exceeds_slowdown(samples: list[dict]) -> bool:
    return any(row["update_s"] > SLOWDOWN_LIMIT_S for row in samples)


class TrainingMonitor:
    """Read actual per-update TensorBoard wall times without touching training."""

    def __init__(self, log_dir: Path) -> None:
        self.events = EventAccumulator(str(log_dir), size_guidance={"scalars": 0})
        self.events.Reload()
        self.tag = "Perf/total_fps"
        if self.tag not in self.events.Tags()["scalars"]:
            raise ValueError("EX-41 TensorBoard has no per-update Perf/total_fps")
        scalars = self.events.Scalars(self.tag)
        if len(scalars) < 6:
            raise ValueError("EX-41 needs five measured baseline update intervals")
        self.last_step = scalars[-1].step
        self.last_time = scalars[-1].wall_time
        self.baseline = [scalars[i].wall_time - scalars[i - 1].wall_time
                         for i in range(-5, 0)]
        if any(not 0 < value < 300 for value in self.baseline):
            raise ValueError("EX-41 baseline TensorBoard intervals invalid")

    def poll(self) -> list[dict]:
        self.events.Reload()
        rows = []
        for item in self.events.Scalars(self.tag):
            if item.step <= self.last_step:
                continue
            elapsed = float(item.wall_time - self.last_time)
            if not 0 < elapsed < 300:
                raise ValueError("EX-41 per-update TensorBoard interval invalid")
            rows.append({"iter": item.step, "update_s": elapsed,
                         "wall_time": item.wall_time})
            self.last_step, self.last_time = item.step, item.wall_time
        return rows


def publish_combined(manifest: dict, plan: dict) -> dict:
    """Publish only audited v3.4 sources, including the previous CPU recomposition."""
    roots = (Path("D:/mai-tmp/c_layer_m6000_phase1_v2/out"),
             Path(manifest["old_out"]))
    composer_sha = plan["composer_sha256"]
    videos = []
    for root in roots:
        for _, capture, old in canonical_sources(root):
            video = root.parent / "out_v34" / Path(old["video"]).name
            verify_new(video, capture, composer_sha)
            videos.append(video)
    out = Path(manifest["new_out"])
    for cell in manifest["remaining_cells"]:
        video = checked_success(out, cell, plan)
        if video is not None:
            videos.append(video)
    if len({path.name for path in videos}) != len(videos):
        raise ValueError("D48 name overlaps between C-layer shards")
    playlist = Path("C:/Users/AI-WS01/s2_lab/_playlists/EX40-C-m06000-all.m3u8")
    old = playlist.with_name("EX40-C-m06000-all_v32.m3u8")
    if not old.is_file():
        raise ValueError("preserved v3.2 playlist is missing")
    write_playlist(videos, playlist)
    return {"path": str(playlist), "count": len(videos), "sha256": sha256(playlist)}


def run_next(manifest_path: Path, wanted_sha256: str) -> dict:
    manifest, plan = load_manifest(manifest_path, wanted_sha256)
    out = Path(manifest["new_out"])
    stop = out.parent / "SLOWDOWN_HOLD.json"
    if stop.exists():
        return {"state": "ex41_slowdown_hold", "evidence": str(stop)}
    admitted = gate(plan)
    if not admitted["admit_next_unit"]:
        return {"state": "yielded_to_ex41_p1", "gate": admitted}
    rows = {slot(row): row for row in plan["jobs"]}
    for cell in manifest["remaining_cells"]:
        if checked_success(out, cell, plan) is not None:
            continue
        failures, incomplete = technical_failures(out, cell)
        if incomplete:
            return {"state": "incomplete_attempt_hold", "cell": cell}
        if failures >= MAX_TECHNICAL_FAILURES:
            continue
        attempt_root = out / "attempts" / cell
        attempted = (sum(path.is_dir() and path.name.isdecimal()
                         for path in attempt_root.iterdir()) if attempt_root.exists() else 0)
        if attempted >= len(rows[cell]["seeds"]):
            # Four validated policy failures are an exhausted cell, not a new run.
            continue
        status_path = Path(manifest["training_status"])
        before = train_sample(status_path)
        if before is None:
            return {"state": "training_status_hold", "cell": cell}
        monitor = TrainingMonitor(status_path.parent)
        queue = Path(plan["queue"])
        python = plan["jobs"][0]["recorder_argv"][0]
        command = [python, str(queue), str(manifest["new_plan"]), "--out", str(out),
                   "--run-one", "--only-cell", cell]
        env = dict(os.environ)
        tmp = out.parent / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        env["TMP"] = env["TEMP"] = str(tmp)
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        env.pop("CUDA_VISIBLE_DEVICES", None)
        env["PYTHONPATH"] = os.pathsep.join([str(queue.parents[2]), env.get("PYTHONPATH", "")])
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace", env=env)
        samples = []
        monitor_error = None
        while process.poll() is None:
            time.sleep(2)
            if monitor_error is None:
                try:
                    samples.extend(monitor.poll())
                except (OSError, ValueError) as exc:
                    monitor_error = str(exc)
        stdout, stderr = process.communicate()
        if monitor_error is None:
            try:
                samples.extend(monitor.poll())
            except (OSError, ValueError) as exc:
                monitor_error = str(exc)
        if process.returncode:
            raise ValueError("frozen queue exited %d: %s" % (process.returncode, stderr[-500:]))
        event = json.loads(stdout)
        evidence = {"format": "foothold-c-layer-gpu1-run-one/1", "cell": cell,
                    "queue_event": event, "before": before,
                    "baseline_tensorboard_update_s": monitor.baseline, "during": samples,
                    "slowdown_limit_s": SLOWDOWN_LIMIT_S,
                    "slowdown": exceeds_slowdown(samples)}
        events = out.parent / "events"
        events.mkdir(parents=True, exist_ok=True)
        event_path = events / (cell + "_" + str(int(time.time())) + ".json")
        evidence["evidence_path"] = str(event_path)
        if event.get("event") == "captured":
            checked_success(out, cell, plan)
            evidence["playlist"] = publish_combined(manifest, plan)
        if monitor_error is not None:
            evidence["monitor_error"] = monitor_error
            evidence["state"] = "training_monitor_hold"
            event_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            return evidence
        if not samples:
            evidence["state"] = "training_status_hold"
            event_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            return evidence
        if evidence["slowdown"]:
            stop.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            evidence["state"] = "ex41_slowdown_hold"
            event_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            return evidence
        evidence["state"] = event.get("state", "unknown")
        event_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        return evidence
    return {"state": "remaining_complete_or_technical_hold", "cells": len(manifest["remaining_cells"])}


def run_remaining(manifest_path: Path, wanted_sha256: str, pause_s: int = 30,
                  run_one=run_next, sleep=time.sleep) -> dict:
    """Keep the P4 queue alive, yielding between cells to the EX-41 P1 marker."""
    manifest, _ = load_manifest(manifest_path, wanted_sha256)
    root = Path(manifest["new_out"]).parent
    lock = root / "gpu1_remainder.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "started": time.time()}))
    ledger = root / "gpu1_remainder_loop.jsonl"
    held = 0
    try:
        while True:
            if (root / "OPERATOR_STOP").exists():
                return {"state": "operator_stop", "ledger": str(ledger)}
            try:
                result = run_one(manifest_path, wanted_sha256)
            except Exception as exc:
                result = {"state": "queue_error_hold", "error": repr(exc)}
            with ledger.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"at": time.time(), **result}, ensure_ascii=False) + "\n")
            state = result["state"]
            if state in ("ex41_slowdown_hold", "training_monitor_hold", "queue_error_hold",
                         "incomplete_attempt_hold", "remaining_complete_or_technical_hold"):
                return {**result, "ledger": str(ledger)}
            if state in ("yielded_to_ex41_p1", "training_status_hold"):
                held += 1
                if state == "training_status_hold" and held >= 20:
                    return {"state": "training_status_hold", "ledger": str(ledger)}
                sleep(pause_s)
                continue
            held = 0
    finally:
        lock.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("make")
    for name in ("old-plan", "old-out", "new-plan", "new-out", "training-status", "out"):
        make.add_argument("--" + name, type=Path, required=True)
    run = sub.add_parser("run-next")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--manifest-sha256", required=True)
    loop = sub.add_parser("run-remaining")
    loop.add_argument("--manifest", type=Path, required=True)
    loop.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    if args.command == "make":
        result = create_manifest(args.old_plan, args.old_out, args.new_plan,
                                 args.new_out, args.training_status, args.out)
        print(json.dumps({"manifest": str(args.out), "sha256": sha256(args.out),
                          "completed": len(result["completed_source_receipts"]),
                          "remaining": len(result["remaining_cells"]),
                          "first": result["remaining_cells"][0]}))
    elif args.command == "run-next":
        print(json.dumps(run_next(args.manifest, args.manifest_sha256), ensure_ascii=False))
    else:
        print(json.dumps(run_remaining(args.manifest, args.manifest_sha256), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
