"""Unattended gate: the one process the OS-level watcher watches.

Written by lead 2026-10-15 for ASTRA review. It reuses the frozen A3 stage-0 prelaunch and
supervisor UNCHANGED: after the unattended contract is verified and the independent watchdog has
published a matching READY, the gate derives an inner (attended-shaped) manifest + approval whose
digests bind back to the outer ones, then calls prelaunch and run_zero in-process. No GPU work
starts before READY. A thread in this process checks that the watcher stays alive and writing; if
it does not, the gate writes the STOP file and hard-exits if the supervisor does not stop.

Exit codes: 0 verdict PASS; 42 not PASS / NO_GO; 5 contract hold; 6 watcher not ready (no GPU
work); 43 unexpected exception; 71 watcher lost during the run; 70 hard exit by the monitor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

import psutil

FINAL_DEADLINE_EPOCH = 1792206000
APPROVAL_SCOPE = "unattended_stage0_information_only"
FINAL_MARGIN_S = 30.0
REQUIRED_BLOCK = ("gate_path", "gate_sha256", "watchdog_path", "watchdog_sha256", "launcher_path",
                  "launcher_sha256", "bundle_dir", "bundle_list_sha256", "watch_dir", "ready_timeout_s",
                  "stale_after_s", "startup_grace_s", "poll_s", "mono_budget_s", "hard_deadline_extra_s",
                  "monitor_stale_s", "stop_grace_s")


class GateHold(RuntimeError):
    pass


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha_of(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def atomic_write(path, value) -> bool:
    try:
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(value, sort_keys=True, allow_nan=False, default=str), encoding="utf-8")
        for _ in range(50):
            try:
                os.replace(tmp, target)
                return True
            except PermissionError:
                time.sleep(0.01)
    except Exception:
        pass
    return False


def verify_bundle_list(bundle_dir: Path, expected_list_sha256: str):
    sums = bundle_dir / "SHA256SUMS.txt"
    if not sums.is_file() or file_sha256(sums) != expected_list_sha256:
        raise GateHold("bundle_list_hash")
    count = 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip().replace("\r", "")
        if not line:
            continue
        digest, name = line.split(None, 1)
        name = name.lstrip("*").strip()
        count += 1
        target = bundle_dir / name
        if not target.is_file() or file_sha256(target) != digest:
            raise GateHold("bundle_file_hash_" + name)
    if count == 0:
        raise GateHold("bundle_list_empty")


def check_contract(outer, approval, now: float, *, gate_file: Path, watchdog_file: Path, watch_dir: Path):
    if not isinstance(outer, dict) or not isinstance(approval, dict):
        raise GateHold("not_objects")
    if outer.get("contract_version") != "a4u":
        raise GateHold("contract_version")
    if outer.get("observer_mode") != "unattended":
        raise GateHold("observer_mode_not_unattended")
    block = outer.get("unattended")
    if not isinstance(block, dict) or any(k not in block or block[k] in (None, "", "UNDECIDED") for k in REQUIRED_BLOCK):
        raise GateHold("unattended_block_missing")
    if approval.get("status") != "APPROVED" or approval.get("chain_id") != outer.get("chain_id") or not approval.get("by"):
        raise GateHold("approval_missing")
    if approval.get("manifest_sha256") != sha_of(outer):
        raise GateHold("approval_digest")
    basis = approval.get("decision_basis")
    if approval.get("scope") != APPROVAL_SCOPE or not isinstance(basis, dict) or not basis.get("verdict_file") \
            or not isinstance(basis.get("verdict_sha256"), str) or len(basis["verdict_sha256"]) != 64 \
            or not basis.get("verdict_line"):
        raise GateHold("approval_scope_or_basis")
    exp = approval.get("expires_epoch")
    deadline = outer.get("deadline_epoch")
    if not finite_number(exp) or not finite_number(deadline) or exp <= now or deadline > exp:
        raise GateHold("approval_expired")
    if not now < deadline <= FINAL_DEADLINE_EPOCH:
        raise GateHold("deadline")
    max_wall = outer.get("max_wall_s")
    if not finite_number(max_wall) or not 0 < max_wall <= 3600 or deadline - now < max_wall + 30:
        raise GateHold("deadline_or_wall_budget")
    bounds = (("ready_timeout_s", 1, 120), ("stale_after_s", 3, 120), ("startup_grace_s", 10, 600),
              ("poll_s", 0.1, 5), ("hard_deadline_extra_s", 10, 300), ("stop_grace_s", 5, 120),
              ("monitor_stale_s", 3, 60), ("mono_budget_s", max_wall + 30, max_wall + 900))
    for key, lo, hi in bounds:
        if not finite_number(block[key]) or not lo <= block[key] <= hi:
            raise GateHold("block_value_" + key)
    if Path(gate_file).resolve() != Path(block["gate_path"]).resolve() or file_sha256(gate_file) != block["gate_sha256"]:
        raise GateHold("gate_file_hash")
    wd = Path(block["watchdog_path"])
    if Path(watchdog_file).resolve() != wd.resolve() or not wd.is_file() or file_sha256(wd) != block["watchdog_sha256"]:
        raise GateHold("watchdog_file_hash")
    launcher = Path(block["launcher_path"])
    if not launcher.is_file() or file_sha256(launcher) != block["launcher_sha256"]:
        raise GateHold("launcher_file_hash")
    if Path(watch_dir).resolve() != Path(block["watch_dir"]).resolve():
        raise GateHold("watch_dir_differs_from_approved")
    if not final_bound_ok(outer, block):
        raise GateHold("final_deadline_margin")
    verify_bundle_list(Path(block["bundle_dir"]), block["bundle_list_sha256"])
    return block


def expected_watchdog_argv(outer, block, *, gate_pid, gate_create_time):
    """The exact command line the launcher gives the watchdog. The launcher builds it from this
    function and the gate compares the running watchdog's real command line against it."""
    hard = float(outer["deadline_epoch"]) + float(block["hard_deadline_extra_s"])
    watch = str(block["watch_dir"])
    return [str(outer["python_path"]), "-B", str(block["watchdog_path"]), "--pid", str(gate_pid),
            "--create-time", repr(float(gate_create_time)), "--chain-id", str(outer["chain_id"]),
            "--status-path", str(outer["status_path"]), "--watch-dir", watch,
            "--hard-deadline-epoch", repr(hard), "--mono-budget-s", repr(float(block["mono_budget_s"])),
            "--stale-after-s", repr(float(block["stale_after_s"])),
            "--startup-grace-s", repr(float(block["startup_grace_s"])),
            "--poll-s", repr(float(block["poll_s"])), "--log", str(Path(watch) / "watchdog.log")]


def final_bound_ok(outer, block) -> bool:
    """The latest moment anything of this run can still be alive (hard deadline + stop grace + margin)
    must itself be before the final deadline; the margin is taken off the front, not extended."""
    return (outer["deadline_epoch"] + block["hard_deadline_extra_s"] + block["stop_grace_s"]
            + FINAL_MARGIN_S <= FINAL_DEADLINE_EPOCH)


def derive_inner(outer, approval):
    inner = dict(outer)
    inner["observer_mode"] = "attended"
    inner["contract_version"] = "a2"
    inner["unattended_origin_sha256"] = sha_of(outer)
    inner_approval = {"status": "APPROVED", "chain_id": outer["chain_id"],
                      "by": "gate-derived from: " + str(approval["by"]),
                      "manifest_sha256": sha_of(inner), "expires_epoch": approval["expires_epoch"],
                      "origin_approval_sha256": sha_of(approval)}
    return inner, inner_approval


def identity_state(proc, expected_create_time, tolerance=0.05) -> str:
    try:
        return "match" if abs(proc.create_time() - expected_create_time) <= tolerance else "mismatch"
    except psutil.NoSuchProcess:
        return "gone"
    except psutil.AccessDenied:
        return "denied"


def _norm(path) -> str:
    return str(path).replace("\\", "/").lower()


def check_ready(ready, outer, block, *, own_pid, own_create_time, now, process_factory):
    if not isinstance(ready, dict):
        return "ready_not_object"
    expected_hard = outer["deadline_epoch"] + block["hard_deadline_extra_s"]
    if ready.get("chain_id") != outer["chain_id"] or ready.get("state") != "READY":
        return "ready_chain_or_state"
    if ready.get("gate_pid") != own_pid or not finite_number(ready.get("gate_create_time")) or \
            abs(ready["gate_create_time"] - own_create_time) > 0.05:
        return "ready_gate_identity"
    if ready.get("watchdog_sha256") != block["watchdog_sha256"]:
        return "ready_watchdog_hash"
    for key, want in (("hard_deadline_epoch", expected_hard), ("mono_budget_s", block["mono_budget_s"]),
                      ("stale_after_s", block["stale_after_s"]), ("startup_grace_s", block["startup_grace_s"])):
        if not finite_number(ready.get(key)) or abs(ready[key] - want) > 1e-6:
            return "ready_param_" + key
    if not finite_number(ready.get("epoch")) or abs(now - ready["epoch"]) > block["ready_timeout_s"] + 30:
        return "ready_not_fresh"
    wpid, wct = ready.get("watchdog_pid"), ready.get("watchdog_create_time")
    if not isinstance(wpid, int) or not finite_number(wct):
        return "ready_watchdog_identity_fields"
    try:
        wproc = process_factory(wpid)
        if identity_state(wproc, wct) != "match":
            return "ready_watchdog_not_alive"
        argv = wproc.cmdline()
    except psutil.NoSuchProcess:
        return "ready_watchdog_not_alive"
    except psutil.AccessDenied:
        return "ready_watchdog_unreadable"
    expected = expected_watchdog_argv(outer, block, gate_pid=own_pid, gate_create_time=ready["gate_create_time"])
    if len(argv) != len(expected) or any(_norm(a) != _norm(b) for a, b in zip(argv, expected)):
        return "ready_watchdog_argv_mismatch"
    return None


def wait_ready(outer, block, *, watch_dir: Path, own_pid: int, now, mono, sleep, process_factory):
    own_ct = process_factory(own_pid).create_time()
    stop_at = mono() + block["ready_timeout_s"]
    last = "no_ready_file"
    while True:
        try:
            ready = json.loads((watch_dir / "ready.json").read_text(encoding="utf-8"))
            problem = check_ready(ready, outer, block, own_pid=own_pid, own_create_time=own_ct, now=now(),
                                  process_factory=process_factory)
            if problem is None:
                return ready
            last = problem
        except (OSError, ValueError):
            last = "ready_unreadable"
        if mono() >= stop_at:
            raise GateHold("watcher_not_ready:" + last)
        sleep(0.2)


class WatcherMonitor(threading.Thread):
    """Checks the watcher while the supervisor runs. Problem -> STOP file; grace -> hard exit."""

    def __init__(self, *, ready, watch_dir: Path, stop_path: Path, stale_s: float, stop_grace_s: float,
                 process_factory=psutil.Process, mono=time.monotonic, die=os._exit, poll_s=1.0):
        super().__init__(daemon=True)
        self.ready, self.watch_dir, self.stop_path = ready, Path(watch_dir), Path(stop_path)
        self.stale_s, self.stop_grace_s, self.process_factory = stale_s, stop_grace_s, process_factory
        self.mono, self.die, self.poll_s = mono, die, poll_s
        self.halt = threading.Event()
        self.problem = None
        self.last_seq, self.last_change = ready.get("seq", 0), mono()

    def valid_heartbeat(self, hb) -> bool:
        """Only a heartbeat of THIS chain from THIS watcher, with an integer seq, counts as input."""
        r = self.ready
        return (isinstance(hb, dict) and hb.get("chain_id") == r["chain_id"]
                and hb.get("watchdog_pid") == r["watchdog_pid"] and hb.get("gate_pid") == r["gate_pid"]
                and finite_number(hb.get("watchdog_create_time"))
                and abs(hb["watchdog_create_time"] - r["watchdog_create_time"]) <= 0.05
                and type(hb.get("seq")) is int and hb["seq"] > 0 and isinstance(hb.get("state"), str))

    def check(self):
        try:
            wproc = self.process_factory(self.ready["watchdog_pid"])
        except psutil.NoSuchProcess:
            return "watcher_gone"
        except psutil.AccessDenied:
            return "watcher_blind"
        state = identity_state(wproc, self.ready["watchdog_create_time"])
        if state != "match":
            return "watcher_" + state
        try:
            hb = json.loads((self.watch_dir / "watchdog_hb.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            hb = None
        if self.valid_heartbeat(hb):
            if hb["state"] != "WATCHING":
                return "watcher_state_" + str(hb["state"])
            if hb["seq"] > self.last_seq:
                self.last_seq, self.last_change = hb["seq"], self.mono()
        if self.mono() - self.last_change > self.stale_s:
            return "watcher_heartbeat_stale"
        return None

    def run(self):
        while not self.halt.is_set():
            problem = self.check()
            if problem:
                self.problem = problem
                try:
                    self.stop_path.write_text("watcher problem: %s\n" % problem, encoding="utf-8")
                except Exception:
                    pass
                end = self.mono() + self.stop_grace_s
                while not self.halt.is_set() and self.mono() < end:
                    self.halt.wait(0.2)
                if not self.halt.is_set():
                    self.die(70)
                return
            self.halt.wait(self.poll_s)


def run_gate(outer, approval, *, watch_dir, gate_file, watchdog_file, prelaunch_fn, run_fn,
             now=time.time, mono=time.monotonic, sleep=time.sleep, die=os._exit,
             process_factory=psutil.Process, own_pid=None, monitor_poll_s=1.0):
    watch_dir = Path(watch_dir)
    own_pid = own_pid or os.getpid()
    result = {"state": "START", "chain_id": outer.get("chain_id") if isinstance(outer, dict) else None,
              "started_epoch": now(), "gate_pid": own_pid}

    def finish(state, code, **extra):
        result.update(state=state, exit_code=code, ended_epoch=now(), **extra)
        atomic_write(watch_dir / "gate_result.json", result)
        return code

    try:
        block = check_contract(outer, approval, now(), gate_file=Path(gate_file), watchdog_file=Path(watchdog_file),
                               watch_dir=watch_dir)
    except GateHold as ex:
        return finish("HOLD_CONTRACT", 5, reason=str(ex))
    except Exception as ex:
        return finish("HOLD_CONTRACT", 5, reason="exception:" + repr(ex))
    try:
        ready = wait_ready(outer, block, watch_dir=watch_dir, own_pid=own_pid,
                           now=now, mono=mono, sleep=sleep, process_factory=process_factory)
    except GateHold as ex:
        return finish("NOT_READY", 6, reason=str(ex))
    result["ready_seen_epoch"] = now()
    inner, inner_approval = derive_inner(outer, approval)
    monitor = WatcherMonitor(ready=ready, watch_dir=watch_dir, stop_path=Path(inner["stop_path"]),
                             stale_s=block["monitor_stale_s"], stop_grace_s=block["stop_grace_s"],
                             process_factory=process_factory, mono=mono, die=die, poll_s=monitor_poll_s)
    monitor.start()
    outcome = None
    try:
        report = prelaunch_fn(inner, inner_approval)
        if not isinstance(report, dict) or report.get("status") != "GO":
            outcome = ("NO_GO", 42, {"report": report})
        else:
            verdict = run_fn(inner, inner_approval)
            outcome = ("DONE", 0 if isinstance(verdict, dict) and verdict.get("verdict") == "PASS" else 42,
                       {"verdict": verdict})
    except Exception as ex:
        outcome = ("EXCEPTION", 43, {"error": repr(ex)})
    finally:
        monitor.halt.set()
        monitor.join(5)
    state, code, extra = outcome
    if monitor.problem:
        return finish("WATCHER_LOST", 71, watcher_problem=monitor.problem, inner_outcome=state, **extra)
    return finish(state, code, **extra)


def _real_functions(bundle_dir: Path):
    def prelaunch(manifest, approval):
        sys.path.insert(0, str(bundle_dir))
        from s2_stage0_prelaunch import prelaunch as real
        return real(manifest, approval)

    def run(manifest, approval):
        sys.path.insert(0, str(bundle_dir))
        from s2_zero_supervisor import run_zero
        return run_zero(manifest, approval)

    return prelaunch, run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--approval", type=Path, required=True)
    ap.add_argument("--watch-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    outer = json.loads(a.manifest.read_text(encoding="utf-8"))
    approval = json.loads(a.approval.read_text(encoding="utf-8"))
    block = outer.get("unattended") if isinstance(outer, dict) else None
    bundle = Path(block["bundle_dir"]) if isinstance(block, dict) and block.get("bundle_dir") else Path(".")
    prelaunch_fn, run_fn = _real_functions(bundle)
    watchdog_file = Path(block["watchdog_path"]) if isinstance(block, dict) and block.get("watchdog_path") else Path("")
    code = run_gate(outer, approval, watch_dir=a.watch_dir, gate_file=Path(__file__).resolve(),
                    watchdog_file=watchdog_file, prelaunch_fn=prelaunch_fn, run_fn=run_fn)
    print(json.dumps({"gate_exit": code}), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
