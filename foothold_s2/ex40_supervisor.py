"""CPU-safe state machine used by the EX-40 supervised start-script copy.

This module observes child completion, verifies the next checkpoint, requires
segment evaluation consumption, and records the decision. It never kills a
process and its default command only writes a local decision receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

from foothold_s2.ex40_continue import (consecutive_failure_action,
                                       newest_verified_checkpoint, source_decision)


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def transition(*, run: Path, rc: int | None, shell_finished: bool,
               process_alive: bool | None, score_state: str,
               ledger: dict | None = None, arm: str = "B") -> tuple[dict, dict]:
    ledger = dict(ledger or {"format": "ex40-supervisor-ledger/1", "attempts": []})
    if ledger.get("format") != "ex40-supervisor-ledger/1" or not isinstance(ledger.get("attempts"), list):
        raise ValueError("EX-40 supervisor ledger malformed")
    decision = source_decision(run=run, shell_finished=shell_finished,
                               process_alive=process_alive, arm=arm)
    if decision["state"].startswith("waiting_"):
        return {"action": "wait", "source": decision, "reason": "child exit state is not known"}, ledger
    if decision["state"] == "already_complete":
        if score_state != "consumed":
            return {"action": "wait_for_segment_evaluation", "source": decision,
                    "reason": "final segment has not been consumed by score watcher"}, ledger
        ledger["terminal"] = {"state": "done", "source": decision, "evaluation": score_state}
        return {"action": "complete", "source": decision}, ledger
    if decision["state"] != "ready_to_continue":
        return {"action": "hold", "source": decision}, ledger
    status_path = run / "train_start_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    failed = status.get("state") == "failed" or rc not in (0, None)
    row = {"state": "failed" if failed else "segment_saved", "rc": rc,
           "status": status.get("state"), "iteration": status.get("iter"),
           "run_dir": str(run.resolve()),
           "checkpoint": decision.get("checkpoint"),
           "checkpoint_sha256": decision.get("checkpoint_sha256"),
           "evaluation_state": score_state}
    attempts = list(ledger["attempts"])
    identity = (row["run_dir"], row["checkpoint_sha256"], row["checkpoint"])
    for index, previous in enumerate(attempts):
        previous_identity = (previous.get("run_dir"), previous.get("checkpoint_sha256"),
                             previous.get("checkpoint"))
        if previous_identity != identity:
            continue
        previous["evaluation_state"] = score_state
        previous["status"] = row["status"]
        previous["rc"] = row["rc"]
        ledger["attempts"] = attempts
        if failed and consecutive_failure_action(attempts[:index], True) == "stop_after_three_failures":
            ledger["terminal"] = {"state": "stopped_after_three_failures"}
            return {"action": "stop_after_three_failures", "source": decision}, ledger
        if score_state != "consumed":
            return {"action": "wait_for_segment_evaluation", "source": decision,
                    "reason": "same segment checkpoint has not been consumed"}, ledger
        return {"action": "resume_from_verified_checkpoint", "source": decision,
                "failed_attempt": failed}, ledger
    attempts.append(row)
    ledger["attempts"] = attempts
    if failed and consecutive_failure_action(attempts[:-1], True) == "stop_after_three_failures":
        ledger["terminal"] = {"state": "stopped_after_three_failures"}
        return {"action": "stop_after_three_failures", "source": decision}, ledger
    if score_state != "consumed":
        return {"action": "wait_for_segment_evaluation", "source": decision,
                "reason": "new segment checkpoint has not been consumed"}, ledger
    return {"action": "resume_from_verified_checkpoint", "source": decision,
            "failed_attempt": failed}, ledger


def _run_dir_for_pid(log_root: Path, pid: int) -> Path:
    matches = []
    for manifest_path in log_root.rglob("manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if ((manifest.get("run") or {}).get("pid") == pid
                and (manifest.get("modes") or {}).get("contract") == "basic_gait_ex40"):
            matches.append(manifest_path.parent)
    if len(matches) != 1:
        raise ValueError(f"EX-40 child PID {pid} has {len(matches)} matching manifests")
    return matches[0]


def _latest_score_checkpoint(run: Path, config: Path) -> tuple[int, str] | None:
    """Return the newest committed stride checkpoint visible during training."""
    from foothold_s2.ex40_score_watch import _manifest_digest, _models, config as score_config

    cfg = score_config(config)
    try:
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
        completed = int((manifest.get("progress") or {}).get("completed_updates", 0))
    except (OSError, ValueError, TypeError):
        return None
    candidates = [(update, path) for update, path in _models(run, cfg)
                  if update < completed]
    if not candidates:
        return None
    update, _ = candidates[-1]
    digest = _manifest_digest(run, update)
    return (update, digest) if digest else None


def _watch_progress(out_root: Path) -> dict:
    """Small local snapshot used in the supervisor's segment receipt."""
    state_path = out_root / "watch_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8-sig")) if state_path.is_file() else {}
    reports = sorted((out_root / "stage_reports").glob("stage_*.json"))
    return {"scored_updates": sorted(int(key) for key in (state.get("done") or {})),
            "stage_report_receipts": [{"path": str(path),
                                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                       for path in reports]}


def _record_watch_event(path: Path, *, pid: int, run: Path, checkpoint: tuple[int, str],
                        score_state: str, progress: dict) -> None:
    """Append one idempotent observation per state transition for a segment."""
    update, digest = checkpoint
    try:
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
        segment_index = ((manifest.get("modes") or {}).get("continuous_resume") or {}).get("segment_index")
    except (OSError, ValueError):
        segment_index = None
    row = {"format": "ex40-supervisor-watch-event/1", "pid": pid,
           "run_dir": str(run.resolve()), "segment_index": segment_index,
           "checkpoint_iteration": update,
           "checkpoint_sha256": digest, "score_state": score_state,
           "progress": progress, "observed_at": datetime.now(timezone.utc).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        existing = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]
        identity = (pid, row["run_dir"], update, digest, score_state, progress)
        if existing and (existing[-1].get("pid"), existing[-1].get("run_dir"),
                         existing[-1].get("checkpoint_iteration"),
                         existing[-1].get("checkpoint_sha256"), existing[-1].get("score_state"),
                         existing[-1].get("progress")) == identity:
            return
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _score_until_checkpoint(run: Path, out_root: Path, score_dir: Path,
                            config: Path, table: Path, arm: str,
                            update: int, digest: str, max_calls: int = 40) -> str:
    """Consume every eligible score through the candidate before continuing."""
    from foothold_s2.curriculum.continuous import Plan
    from foothold_s2.ex40_score_watch import (_manifest_digest, _models, completion,
                                               config as score_config, stage_end_updates,
                                               stage_reports)

    cfg = score_config(config)
    first, stride = cfg["checkpoint_first"], cfg["checkpoint_stride"]
    if update < first:
        return "consumed"
    target_update = first + ((update - first) // stride) * stride
    available = [(n, path) for n, path in _models(run, cfg) if n <= target_update]
    if not available:
        return "pending"
    available_updates = {n for n, _ in available}
    target_digest = _manifest_digest(run, target_update)
    if target_digest is None:
        return "pending"
    if update == target_update and target_digest != digest:
        return "unknown"
    digest = target_digest
    boundaries = stage_end_updates(Plan(table, arm=arm), cfg)
    state_path = out_root / "watch_state.json"
    for _ in range(max_calls):
        state = json.loads(state_path.read_text(encoding="utf-8-sig")) if state_path.is_file() else None
        if state:
            if state.get("format") != "foothold-ex40-score-watch/1" or state.get("arm") != arm:
                return "unknown"
            for scored_update in sorted(available_updates):
                row = state.get("done", {}).get(str(scored_update))
                if row is None:
                    break
                checkpoint = run / f"model_{scored_update}.pt"
                pinned = _manifest_digest(run, scored_update)
                try:
                    actual = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
                except OSError:
                    return "unknown"
                if (not pinned or row.get("checkpoint_sha256") != pinned or actual != pinned
                        or row.get("state") not in ("PASS", "FAIL", "HOLD")):
                    return "unknown"
                if row["state"] == "HOLD":
                    return "pending"
            else:
                reports = stage_reports(run, out_root, config, table, arm,
                    telegram_sender=None, lab_feed=out_root / "lab_feed.json")
                required_reports = [n for n in boundaries if n <= target_update and n in available_updates]
                report_updates = {item.get("update") for item in reports.get("published", [])}
                if any(n not in report_updates for n in required_reports):
                    return "pending"
                if target_update == cfg["final_checkpoint_update"]:
                    finished = completion(run, out_root, config, table, arm, state)
                    if finished.get("state") == "done" and reports.get("state") == "done":
                        return "consumed"
                    return "pending"
                return "consumed"
        cmd = [sys.executable, "-m", "foothold_s2.ex40_score_watch",
               "--run-dir", str(run), "--out-root", str(out_root),
               "--score-dir", str(score_dir), "--config", str(config),
               "--table", str(table), "--arm", arm, "--once", "--no-telegram",
               "--lab-feed", str(out_root / "lab_feed.json")]
        proc = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1],
                              text=True, encoding="utf-8", capture_output=True, check=False)
        if proc.returncode:
            return "pending"
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return "unknown"
        if payload.get("evaluation", {}).get("state") == "idle":
            return "pending"
    return "pending"


def supervise(*, initial_args: list[str], launch_receipt: Path, log_root: Path,
              score_out: Path, score_dir: Path, expected_finish: str, end_by: str,
              arm: str, device: str, ledger_path: Path, max_segments: int = 100,
              poll_seconds: float | None = None, sleep=time.sleep) -> dict:
    """Run one segment at a time, evaluate its latest save, and prepare safe resume."""
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, config as score_config
    from foothold_s2.ex40_launch import TABLE

    args = list(initial_args)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig")) if ledger_path.is_file() else None
    if poll_seconds is None:
        poll_seconds = max(1.0, float(score_config(DEFAULT_CONFIG)["check_interval_seconds"]))
    if poll_seconds < 0:
        raise ValueError("supervisor poll interval cannot be negative")
    for _ in range(max_segments):
        child = subprocess.Popen([sys.executable, "foothold_s2/scripts/train_sb.py", *args],
                                 cwd=Path(__file__).resolve().parents[1])
        run = None
        last_consumed = None
        watch_events = score_out / "supervisor_score_events.jsonl"
        while True:
            rc = child.poll()
            if run is None:
                try:
                    run = _run_dir_for_pid(log_root, child.pid)
                except (OSError, ValueError):
                    pass
            if run is not None:
                visible = _latest_score_checkpoint(run, DEFAULT_CONFIG)
                if visible is not None and visible != last_consumed:
                    score_state_live = _score_until_checkpoint(run, score_out, score_dir,
                        DEFAULT_CONFIG, TABLE, arm, visible[0], visible[1])
                    _record_watch_event(watch_events, pid=child.pid, run=run,
                        checkpoint=visible, score_state=score_state_live,
                        progress=_watch_progress(score_out))
                    if score_state_live == "consumed":
                        last_consumed = visible
            if rc is not None:
                break
            sleep(poll_seconds)
        rc = child.wait()
        if run is None:
            run = _run_dir_for_pid(log_root, child.pid)
        status = json.loads((run / "train_start_status.json").read_text(encoding="utf-8-sig"))
        candidate = None
        if status.get("state") == "done" and status.get("iter") == 8000:
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
            final_sha = (manifest.get("checkpoints") or {}).get("model_8000.pt")
            if isinstance(final_sha, str) and (run / "model_8000.pt").is_file():
                candidate = {"completed_update": 8000, "checkpoint_sha256": final_sha}
        else:
            try:
                candidate = newest_verified_checkpoint(run, arm=arm)
            except (OSError, ValueError):
                pass
        score_state = (_score_until_checkpoint(run, score_out, score_dir, DEFAULT_CONFIG, TABLE, arm,
                                              candidate["completed_update"], candidate["checkpoint_sha256"])
                       if candidate else "unknown")
        action, ledger = transition(run=run, rc=rc, shell_finished=True,
                                    process_alive=False, score_state=score_state,
                                    ledger=ledger, arm=arm)
        _atomic_json(ledger_path, ledger)
        if action["action"] == "complete":
            return action
        if action["action"] != "resume_from_verified_checkpoint":
            return action
        source = action["source"]
        spec_dir = log_root / "supervisor-resume-specs"
        spec_path = spec_dir / f"resume_model_{source['completed_update']}.json"
        spec = {"source_receipt": str(launch_receipt.resolve()),
                "checkpoint": source["checkpoint"],
                "checkpoint_sha256": source["checkpoint_sha256"],
                "expected_finish": expected_finish}
        if spec_path.exists():
            if json.loads(spec_path.read_text(encoding="utf-8-sig")) != spec:
                return {"action": "hold", "reason": "resume spec path already contains different data"}
        else:
            _atomic_json(spec_path, spec)
        # Re-run the official launcher and prestart contract before resuming.
        gate = subprocess.run([sys.executable, "-m", "foothold_s2.ex40_launch",
            "--arm", arm, "--device", device, "--end-by", end_by,
            "--log-root", str(log_root), "--score-dir", str(score_dir),
            "--resume-spec", str(spec_path)], cwd=Path(__file__).resolve().parents[1],
            text=True, encoding="utf-8", capture_output=True, check=False)
        if gate.returncode:
            return {"action": "resume_prepared_but_launch_guard_closed",
                    "checkpoint": source.get("checkpoint"),
                    "checkpoint_sha256": source.get("checkpoint_sha256"),
                    "guard": gate.stderr[-1000:]}
        row = json.loads(gate.stdout)
        args = row.get("argv")
        if not isinstance(args, list) or row.get("training_started") is not False:
            return {"action": "hold", "reason": "official resume receipt malformed"}
    return {"action": "hold", "reason": "maximum supervised segments reached"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--rc", type=int)
    parser.add_argument("--shell-finished", action="store_true")
    process = parser.add_mutually_exclusive_group()
    process.add_argument("--process-alive", dest="process_alive", action="store_true")
    process.add_argument("--process-dead", dest="process_alive", action="store_false")
    parser.set_defaults(process_alive=None)
    parser.add_argument("--score-state", choices=("consumed", "pending", "unknown"), default="unknown")
    parser.add_argument("--arm", choices=("A", "B"), default="B")
    parser.add_argument("--find-run-pid", type=int)
    parser.add_argument("--log-root", type=Path)
    parser.add_argument("--supervise", action="store_true")
    parser.add_argument("--args-file", type=Path)
    parser.add_argument("--launch-receipt", type=Path)
    parser.add_argument("--score-out", type=Path)
    parser.add_argument("--score-dir", type=Path)
    parser.add_argument("--expected-finish")
    parser.add_argument("--end-by")
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"))
    args = parser.parse_args(argv)
    if args.find_run_pid is not None:
        if args.log_root is None:
            parser.error("--find-run-pid requires --log-root")
        print(_run_dir_for_pid(args.log_root.resolve(strict=True), args.find_run_pid))
        return 0
    if args.supervise:
        required = (args.args_file, args.launch_receipt, args.log_root, args.score_out,
                    args.score_dir, args.expected_finish, args.end_by, args.device)
        if any(value is None for value in required):
            parser.error("--supervise requires args/receipt/log/score paths, expected finish, end-by and device")
        initial_args = args.args_file.read_text(encoding="utf-8-sig").splitlines()
        result = supervise(initial_args=initial_args, launch_receipt=args.launch_receipt.resolve(strict=True),
            log_root=args.log_root.resolve(), score_out=args.score_out.resolve(),
            score_dir=args.score_dir.resolve(), expected_finish=args.expected_finish,
            end_by=args.end_by, arm=args.arm, device=args.device,
            ledger_path=args.ledger.resolve())
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("action") in ("complete", "resume_prepared_but_launch_guard_closed") else 5
    ledger = json.loads(args.ledger.read_text(encoding="utf-8-sig")) if args.ledger.is_file() else None
    if args.run is None:
        parser.error("--run is required unless --supervise or --find-run-pid is used")
    action, ledger = transition(run=args.run.resolve(strict=True), rc=args.rc,
        shell_finished=args.shell_finished, process_alive=args.process_alive,
        score_state=args.score_state, ledger=ledger, arm=args.arm)
    _atomic_json(args.ledger, ledger)
    print(json.dumps({"decision": action, "ledger": str(args.ledger)}, ensure_ascii=False,
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
