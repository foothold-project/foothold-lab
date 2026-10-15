"""Mutation check for the unattended watchdog v2, gate and launcher.

A mutant is CAUGHT only if (1) the same test group passes (exit 0, no FAIL) on the unmodified copy
first and (2) the mutant's FIRST 'FAIL <label>' line equals the wanted label. An exception without
a FAIL label, a different first label, or a pass is NOT_CAUGHT. Mutants are made in a temp copy.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
ENV = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1",
       "S2_A3_DIR": os.environ.get("S2_A3_DIR", str(HERE.parent / "s2_step4a3"))}

W, G, L = "s2_watchdog_v2.py", "s2_unattended_gate.py", "s2_unattended_launch.py"
ROW = "G2 contract row '%s' -> HOLD_CONTRACT %s, no work"
G3 = "G3 READY with wrong %s is refused (%s), no work"

# (name, file, old, new, group, wanted first FAIL label)
MUTANTS = [
    ("watchdog_mono_deadline_removed", W, '        elif m >= deadline_mono:\n            reason = "mono_deadline"',
     '        elif False:\n            reason = "mono_deadline"', "watchdog",
     "W4 monotonic budget kills when the wall clock never advances"),
    ("watchdog_wall_deadline_removed", W, '        if now >= hard_deadline_epoch:\n            reason = "hard_deadline"',
     '        if False:\n            reason = "hard_deadline"', "watchdog",
     "W3b a forward wall-clock jump past the absolute deadline triggers hard_deadline"),
    ("watchdog_future_heartbeat_accepted", W, '    if hb > now + FUTURE_SLACK_S:\n        return None, state, "hb_future"',
     '    if False:\n        return None, state, "hb_future"', "watchdog",
     "W5 future-dated heartbeat is rejected and the victim is killed after the startup grace"),
    ("watchdog_nan_heartbeat_accepted", W, '    if not finite_number(hb):\n        return None, state, "hb_not_finite_number"',
     '    if False:\n        return None, state, "hb_not_finite_number"', "watchdog",
     "W6 NaN heartbeat is rejected and the victim is killed after the startup grace"),
    ("watchdog_chain_not_checked", W, '    if data.get("chain_id") != chain_id:\n        return None, state, "chain_mismatch"',
     '    if False:\n        return None, state, "chain_mismatch"', "watchdog",
     "W7 other chain heartbeat is rejected and the victim is killed after the startup grace"),
    ("watchdog_bool_heartbeat_accepted", W, "    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)",
     "    return isinstance(x, (int, float)) and math.isfinite(x)", "watchdog",
     "W8b bool heartbeat is rejected and the victim is killed after the startup grace"),
    ("watchdog_log_failure_blocks_kill", W,
     "            os.fsync(stream.fileno())\n        return True\n    except Exception:\n        return False",
     "            os.fsync(stream.fileno())\n        return True\n    except Exception:\n        raise", "watchdog",
     "W9 unwritable log does not block the kill"),
    ("watchdog_access_denied_midrun_is_ended", W, '        if state == "gone":', '        if state in ("gone", "denied"):',
     "watchdog", "W11 AccessDenied after start becomes blind exit 6 (never reported as ended by itself)"),
    ("watchdog_access_denied_start_not_blind", W, '    if start_state == "denied":', "    if False:", "watchdog",
     "W10 AccessDenied at start is BLIND exit 6"),
    ("watchdog_receipt_not_written", W, '    atomic_write(receipt_path, receipt)\n    safe_log(log_path, event="gate_killed"',
     '    safe_log(log_path, event="gate_killed"', "watchdog", "W2 hung victim killed by stale heartbeat"),
    ("watchdog_stale_rule_removed", W, "        elif ever_valid and m - last_progress_mono > stale_after_s:",
     "        elif False:", "watchdog", "W2 hung victim killed by stale heartbeat"),
    ("watchdog_survivors_not_force_killed", W, "                cp.kill()\n                forced.append(cpid)",
     "                forced.append(cpid)", "watchdog",
     "W15 descendant seen before the kill is reported and force-killed when it survives"),
    ("watchdog_identity_not_checked_at_start", W, '    if start_state != "match":', "    if False:", "watchdog",
     "W13 wrong creation time signals nothing"),
    ("watchdog_nan_args_accepted", W, "        if not finite_number(value) or not 0 < value < 1e6:\n            return label",
     "        if False:\n            return label", "watchdog", "W14a NaN stale is a bad argument and signals nothing"),
    ("watchdog_ready_not_published", W, "    if not atomic_write(ready_path, ready):", "    if False:", "watchdog",
     "W1 READY file carries chain, watchdog hash and gate identity"),
    ("gate_observer_mode_unchecked", G, '    if outer.get("observer_mode") != "unattended":', "    if False:", "gate",
     ROW % ("observer attended", "observer_mode_not_unattended")),
    ("gate_contract_version_unchecked", G, '    if outer.get("contract_version") != "a4u":', "    if False:", "gate",
     ROW % ("contract version", "contract_version")),
    ("gate_approval_digest_unchecked", G, '    if approval.get("manifest_sha256") != sha_of(outer):\n        raise GateHold("approval_digest")',
     '    if False:\n        raise GateHold("approval_digest")', "gate", ROW % ("approval digest", "approval_digest")),
    ("gate_expiry_unchecked", G, "    if not finite_number(exp) or not finite_number(deadline) or exp <= now or deadline > exp:",
     "    if not finite_number(exp) or not finite_number(deadline):", "gate", ROW % ("approval expired", "approval_expired")),
    ("gate_gate_hash_unchecked", G,
     '    if Path(gate_file).resolve() != Path(block["gate_path"]).resolve() or file_sha256(gate_file) != block["gate_sha256"]:',
     "    if False:", "gate", ROW % ("gate hash", "gate_file_hash")),
    ("gate_watchdog_hash_unchecked", G,
     '    if Path(watchdog_file).resolve() != wd.resolve() or not wd.is_file() or file_sha256(wd) != block["watchdog_sha256"]:',
     "    if False:", "gate", ROW % ("watchdog hash", "watchdog_file_hash")),
    ("gate_bundle_list_unchecked", G, '    verify_bundle_list(Path(block["bundle_dir"]), block["bundle_list_sha256"])',
     "    pass", "gate", ROW % ("bundle list hash", "bundle_list_hash")),
    ("gate_ready_gate_pid_unchecked", G, '    if ready.get("gate_pid") != own_pid or not finite_number(',
     "    if False and not finite_number(", "gate", G3 % ("gate pid", "ready_gate_identity")),
    ("gate_ready_watchdog_hash_unchecked", G, '    if ready.get("watchdog_sha256") != block["watchdog_sha256"]:', "    if False:",
     "gate", G3 % ("watchdog hash", "ready_watchdog_hash")),
    ("gate_ready_params_unchecked", G, '        if not finite_number(ready.get(key)) or abs(ready[key] - want) > 1e-6:',
     "        if False:", "gate", G3 % ("hard deadline", "ready_param_hard_deadline_epoch")),
    ("gate_ready_freshness_unchecked", G,
     '    if not finite_number(ready.get("epoch")) or abs(now - ready["epoch"]) > block["ready_timeout_s"] + 30:',
     "    if False:", "gate", G3 % ("old file", "ready_not_fresh")),
    ("gate_ready_watchdog_identity_unchecked", G, '        if identity_state(wproc, wct) != "match":', "        if False:",
     "gate", G3 % ("watchdog ct wrong", "ready_watchdog_not_alive")),
    ("gate_ready_program_unchecked", G, "    if _norm(watchdog_file) not in _norm(cmdline):", "    if False:", "gate",
     "G3 READY from a process that is not running the watchdog program is refused"),
    ("gate_does_not_wait_for_ready", G, '            raise GateHold("watcher_not_ready:" + last)',
     '            return {"watchdog_pid": os.getpid(), "watchdog_create_time": psutil.Process().create_time()}',
     "gate", "G1 no READY file: gate exits 6 NOT_READY quickly"),
    ("gate_monitor_not_started", G, "    monitor.start()", "    pass", "gate",
     "G6 watcher death during the run -> STOP file, supervisor stopped, rc 71 WATCHER_LOST"),
    ("gate_monitor_check_disabled", G,
     '    def check(self):\n        try:\n            wproc = self.process_factory(self.ready["watchdog_pid"])',
     '    def check(self):\n        return None\n        try:\n            wproc = self.process_factory(self.ready["watchdog_pid"])', "gate",
     "G6 watcher death during the run -> STOP file, supervisor stopped, rc 71 WATCHER_LOST"),
    ("gate_monitor_does_not_write_stop", G,
     r'                    self.stop_path.write_text("watcher problem: %s\n" % problem, encoding="utf-8")',
     "                    pass", "gate",
     "G6 watcher death during the run -> STOP file, supervisor stopped, rc 71 WATCHER_LOST"),
    ("gate_monitor_no_hard_exit", G, "                    self.die(70)", "                    pass", "gate",
     "G6 supervisor ignoring STOP -> hard exit hook called with 70 after the grace"),
    ("gate_monitor_stale_unchecked", G, "        if self.mono() - self.last_change > self.stale_s:", "        if False:", "gate",
     "G7 watcher alive but heartbeat frozen -> STOP, rc 71 with watcher_heartbeat_stale"),
    ("gate_monitor_bad_state_ignored", G, "            if hb.get(\"state\") in BAD_WATCHER_STATES:", "            if False:", "gate",
     "G8 watcher reporting BLIND -> STOP, rc 71 with watcher_state_BLIND"),
    ("gate_inner_stays_unattended", G, '    inner["observer_mode"] = "attended"', '    inner["observer_mode"] = "unattended"',
     "gate", "G4 inner manifest is attended-shaped and bound to the outer digest"),
    ("gate_inner_not_bound_to_outer", G, '    inner["unattended_origin_sha256"] = sha_of(outer)', '    inner["unattended_origin_sha256"] = ""',
     "gate", "G4 inner manifest is attended-shaped and bound to the outer digest"),
    ("gate_runs_after_no_go", G, '        if not isinstance(report, dict) or report.get("status") != "GO":', "        if False:",
     "gate", "G5 prelaunch NO_GO stops before run, rc 42"),
    ("launcher_watchdog_hash_unchecked", L, '        if file_sha256(watchdog_path) != block["watchdog_sha256"]:', "        if False:",
     "process", "P6 hash mismatch against the manifest: exit 4, nothing started, no watch dir"),
    ("launcher_existing_watch_dir_accepted", L, "        if watch_dir.exists():", "        if False:", "process",
     "P7 existing watch dir: exit 4, nothing started"),
    ("launcher_no_cleanup_on_abort", L, '    if proc is None:\n        return "not_started"', '    return "skipped"', "process",
     "P5 the gate it created is gone and no GPU-side marker exists"),
]


def first_fail(text):
    for line in text.splitlines():
        if line.startswith("FAIL "):
            return line[5:].strip()
    return None


def run_group(directory: Path, group: str):
    res = subprocess.run([PY, "-B", str(directory / "test_s2_unattended.py"), "--group", group], capture_output=True,
                         text=True, timeout=900, env=ENV, cwd=str(directory))
    return res.returncode, res.stdout + res.stderr


def main():
    only = sys.argv[1:]
    out = {}
    baselines = {}
    for group in ("watchdog", "gate", "process"):
        if only and not any(m[4] == group for m in MUTANTS if m[0] in only):
            continue
        rc, text = run_group(HERE, group)
        baselines[group] = (rc == 0 and first_fail(text) is None and "SUMMARY ALL PASS" in text)
        print("BASELINE %s: %s (%d PASS lines)" % (group, "ok" if baselines[group] else "NOT OK",
                                                   sum(1 for l in text.splitlines() if l.startswith("PASS "))), flush=True)
    for name, fname, old, new, group, want in MUTANTS:
        if only and name not in only:
            continue
        tmp = Path(tempfile.mkdtemp(prefix="s2u_mut_"))
        copy = tmp / "d"
        shutil.copytree(HERE, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        src = copy / fname
        text = src.read_text(encoding="utf-8")
        if text.count(old) != 1:
            out[name] = {"status": "ANCHOR_NOT_UNIQUE", "count": text.count(old)}
            print("ANCHOR_NOT_UNIQUE", name, text.count(old), flush=True)
            continue
        src.write_text(text.replace(old, new), encoding="utf-8")
        t0 = time.time()
        rc, log = run_group(copy, group)
        got = first_fail(log)
        caught = baselines.get(group, False) and rc != 0 and got == want
        out[name] = {"status": "CAUGHT" if caught else "NOT_CAUGHT", "group": group, "mutant_rc": rc,
                     "first_fail": got, "want": want, "seconds": round(time.time() - t0, 1)}
        print("%-44s %s  first_fail=%r" % (name, out[name]["status"], got if not caught else "(= want)"), flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
    caught = sum(1 for v in out.values() if v["status"] == "CAUGHT")
    print("SUMMARY mutants caught %d/%d" % (caught, len(out)), flush=True)
    result_path = HERE / "mutants_result.json"
    merged = json.loads(result_path.read_text(encoding="utf-8")) if only and result_path.is_file() else {}
    merged.update(out)
    result_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print("MERGED TOTAL caught %d/%d" % (sum(1 for v in merged.values() if v["status"] == "CAUGHT"), len(merged)), flush=True)
    return 0 if caught == len(out) and out else 1


if __name__ == "__main__":
    sys.exit(main())
