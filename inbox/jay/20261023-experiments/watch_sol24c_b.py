"""Temporary CPU-only B progress watcher. Launching this process belongs to root."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Callable


BOUNDARIES = (100, 200, 500, 1000, 1500)
DEADLINE = "2026-10-24T22:30:00+09:00"
SCHEMA = "sol24c-b-watch/1"
STATE_SCHEMA = "sol24c-b-watch-state/1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(100):
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if attempt == 99:
                    raise
                time.sleep(0.01)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def exclusive_owner(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("watcher_already_running") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("watcher_already_running") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def epoch(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must have a timezone")
    return parsed.timestamp()


def validate_config(config: dict[str, Any]) -> float:
    if config.get("schema") != SCHEMA or config.get("deadline") != DEADLINE:
        raise ValueError("watcher schema/deadline mismatch")
    if config.get("run_name") != "ex28-b-main":
        raise ValueError("watcher is scoped to the B main run")
    if (config.get("target") != "term_d0d6549f-2da1-433c-9d05-58ce534224d7"
            or not isinstance(config.get("process_file"), str)
            or not isinstance(config.get("manifest_file"), str)):
        raise ValueError("target/source binding invalid")
    if not isinstance(config.get("state_file"), str):
        raise ValueError("runtime state path missing")
    source_paths = [Path(config[key]).resolve() for key in ("process_file", "manifest_file")]
    state_path = Path(config["state_file"]).resolve()
    if any(state_path == source or state_path.is_relative_to(source.parent) for source in source_paths):
        raise ValueError("runtime state must not be written into a source folder")
    if not Path(config.get("sender_python", "")).is_file():
        raise ValueError("sender Python missing")
    if not Path(config.get("sender_cwd", "")).is_dir():
        raise ValueError("sender working directory missing")
    if (type(config.get("target_updates")) is not int or config["target_updates"] != 1501
            or type(config.get("poll_s")) not in (int, float) or config["poll_s"] < 1
            or type(config.get("max_heartbeat_age_s")) not in (int, float)
            or config["max_heartbeat_age_s"] <= 0):
        raise ValueError("target updates or polling limits invalid")
    return epoch(DEADLINE)


def load_state(config: dict[str, Any]) -> dict[str, Any]:
    path = Path(config["state_file"])
    if not path.is_file():
        return {"schema": STATE_SCHEMA, "run_name": config["run_name"], "events": {},
                "last_seen_completed": 0, "run_started_at": None,
                "observation": None, "mismatch": [], "expired": False}
    state = read_json(path)
    if (state.get("schema") != STATE_SCHEMA or state.get("run_name") != config["run_name"]
            or not isinstance(state.get("events"), dict)):
        raise ValueError("watcher state does not match this run")
    return state


def save_state(config: dict[str, Any], state: dict[str, Any]) -> None:
    atomic_json(Path(config["state_file"]), state)


def inspect(config: dict[str, Any], state: dict[str, Any], now: float) -> tuple[int | None, dict | None]:
    """Return verified completed count and terminal process, or hold with reasons."""
    reasons = []
    process = None
    manifest = None
    try:
        process = read_json(Path(config["process_file"]))
    except (OSError, ValueError, json.JSONDecodeError):
        reasons.append("process_unreadable")
    try:
        manifest = read_json(Path(config["manifest_file"]))
    except (OSError, ValueError, json.JSONDecodeError):
        reasons.append("manifest_unreadable")
    completed = None
    if manifest is not None:
        progress = manifest.get("progress")
        run = manifest.get("run")
        value = progress.get("completed_updates") if isinstance(progress, dict) else None
        if (manifest.get("schema") != "foothold-manifest/1"
                or not isinstance(run, dict) or run.get("name") != config["run_name"]
                or type(value) is not int or not 0 <= value <= config["target_updates"]):
            reasons.append("manifest_contract_mismatch")
        else:
            completed = value
            if completed < state.get("last_seen_completed", 0):
                reasons.append("manifest_progress_regressed")
    terminal = None
    if process is not None:
        started = process.get("started_at")
        if not isinstance(started, str):
            reasons.append("process_start_missing")
        elif state.get("run_started_at") not in (None, started):
            reasons.append("process_identity_changed")
        else:
            state["run_started_at"] = started
        mode = process.get("state")
        if mode == "running":
            heartbeat = process.get("heartbeat_at")
            if not isinstance(heartbeat, str):
                reasons.append("supervisor_heartbeat_missing")
            else:
                try:
                    age = now - epoch(heartbeat)
                except ValueError:
                    reasons.append("supervisor_heartbeat_invalid")
                else:
                    if not -30 <= age <= config["max_heartbeat_age_s"]:
                        reasons.append("supervisor_heartbeat_stale_or_future")
            if type(process.get("child_pid")) is not int or process["child_pid"] <= 0:
                reasons.append("running_child_pid_missing")
        elif mode == "exited":
            if (type(process.get("returncode")) is not int
                    or not isinstance(process.get("ended_at"), str)):
                reasons.append("process_exit_incomplete")
            else:
                terminal = process
        elif mode == "supervisor_error":
            terminal = process
            reasons.append("supervisor_error_child_state_unverified")
        else:
            reasons.append("process_not_running_or_terminal")
    state["observation"] = {"epoch": now, "process_state": process.get("state") if process else None,
                            "heartbeat_at": process.get("heartbeat_at") if process else None,
                            "completed_updates": completed,
                            "returncode": process.get("returncode") if process else None}
    state["mismatch"] = reasons
    if reasons:
        return None, terminal
    state["last_seen_completed"] = max(state.get("last_seen_completed", 0), completed)
    return completed, terminal


def _event_text(config: dict[str, Any], event_id: str, completed: int | None,
                terminal: dict[str, Any] | None) -> str:
    prefix = f"SOL24c {config['run_name']}"
    if event_id.startswith("update_"):
        boundary = int(event_id.split("_", 1)[1])
        return (f"{prefix} 중간 분석 요청: 완료 갱신 {boundary} 경계 도달, "
                f"manifest completed_updates={completed}, 감독기 heartbeat 대조 완료, watcher event={event_id}.")
    if terminal is not None and terminal.get("state") == "exited":
        rc = terminal["returncode"]
        label = ("자연 종료" if completed is not None else "종료 관측, 진행 증거 미확인") if rc == 0 else "실패 종료"
        return (f"{prefix} {label}: child returncode={rc}, "
                f"manifest completed_updates={completed}, 목표={config['target_updates']}, "
                f"watcher event={event_id}. 자동 중단이나 재학습 명령 아님.")
    return (f"{prefix} 감독기 오류: child 상태 미확인, "
            f"manifest completed_updates={completed}, watcher event={event_id}. 확인 요청.")


def queue_events(config: dict[str, Any], state: dict[str, Any], completed: int | None,
                 terminal: dict | None, now: float) -> None:
    if completed is not None:
        for boundary in BOUNDARIES:
            if completed < boundary:
                continue
            key = f"update_{boundary}"
            state["events"].setdefault(key, {"status": "pending", "text": _event_text(
                config, key, completed, terminal), "created_epoch": now, "attempts": 0})
    if terminal is not None:
        key = "terminal"
        if terminal.get("state") == "supervisor_error" or terminal.get("returncode") != 0:
            key = "terminal_failure"
        else:
            key = "terminal_end"
        state["events"].setdefault(key, {"status": "pending", "text": _event_text(
            config, key, completed, terminal), "created_epoch": now, "attempts": 0})


def cli_sender(config: dict[str, Any], text: str) -> int:
    command = [config["sender_python"], "-m", "mai_resume", "send", "--to",
               config["target"], "--text", text, "--wait", "15"]
    result = subprocess.run(command, cwd=config["sender_cwd"], capture_output=True,
                            text=True, check=False, timeout=45)
    return result.returncode


def tick(config: dict[str, Any], state: dict[str, Any], now: float,
         sender: Callable[[str], int]) -> dict[str, Any]:
    """Persist intent before delivery; only rc 0 is sent and only rc 4 retries."""
    for event in state["events"].values():
        if event.get("status") == "sending":
            event["status"] = "uncertain"
            event["reason"] = "restart_after_send_intent"
    deadline = epoch(DEADLINE)
    if now >= deadline:
        state["expired"] = True
        save_state(config, state)
        return state
    completed, terminal = inspect(config, state, now)
    queue_events(config, state, completed, terminal, now)
    save_state(config, state)
    for key in [*(f"update_{n}" for n in BOUNDARIES), "terminal_end", "terminal_failure"]:
        if completed is None and key.startswith("update_"):
            continue
        if terminal is None and key.startswith("terminal_"):
            continue
        event = state["events"].get(key)
        if event is None or event.get("status") not in ("pending", "deferred"):
            continue
        event["status"] = "sending"
        event["attempts"] += 1
        event["last_attempt_epoch"] = now
        save_state(config, state)
        try:
            rc = sender(event["text"])
        except Exception as exc:
            event["status"] = "uncertain"
            event["reason"] = f"sender_exception:{type(exc).__name__}"
        else:
            event["last_exit_code"] = rc
            if rc == 0:
                event["status"] = "sent"
                event["sent_epoch"] = time.time()
            elif rc == 4:
                event["status"] = "deferred"
                event["reason"] = "target_input_busy"
            else:
                event["status"] = "uncertain"
                event["reason"] = f"sender_exit_{rc}"
        save_state(config, state)
        if event["status"] != "sent":
            break
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--once", action="store_true", help="one read and possible message, for root only")
    args = parser.parse_args(argv)
    config = read_json(args.config)
    deadline = validate_config(config)
    state_file = Path(config["state_file"])
    with exclusive_owner(state_file.with_suffix(state_file.suffix + ".owner.lock")):
        state = load_state(config)
        while True:
            now = time.time()
            tick(config, state, now, lambda text: cli_sender(config, text))
            if args.once or now >= deadline:
                return 0
            time.sleep(float(config["poll_s"]))


if __name__ == "__main__":
    raise SystemExit(main())
