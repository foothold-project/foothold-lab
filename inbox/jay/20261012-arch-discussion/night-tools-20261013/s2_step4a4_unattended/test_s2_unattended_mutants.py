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
    ("watchdog_access_denied_midrun_is_ended", W, '        if state == "gone":', '        if state in ("gone", "denied"):',
     "watchdog", "W11 AccessDenied after start becomes blind exit 6 (never reported as ended by itself)"),
    ("watchdog_access_denied_start_not_blind", W, '    if start_state == "denied":', "    if False:", "watchdog",
     "W10 AccessDenied at start is BLIND exit 6"),
    ("watchdog_stale_rule_removed", W, "        elif ever_valid and m - last_progress_mono > stale_after_s:",
     "        elif False:", "watchdog", "W2 hung victim killed by stale heartbeat"),
    ("watchdog_survivors_not_force_killed", W, "                cp.kill()\n                forced.append(cpid)",
     "                forced.append(cpid)", "watchdog",
     "W15 descendant seen before the kill is reported and force-killed when it survives"),
    ("watchdog_identity_not_checked_at_start", W, '    if start_state != "match":', "    if False:", "watchdog",
     "W13 wrong creation time signals nothing"),
    ("watchdog_nan_args_accepted", W, "        if not finite_number(value) or not 0 < value < 1e6:\n            return label",
     "        if False:\n            return label", "watchdog", "W14a NaN stale is a bad argument and signals nothing"),
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
    ("gate_does_not_wait_for_ready", G, '            raise GateHold("watcher_not_ready:" + last)',
     '            return {"watchdog_pid": os.getpid(), "watchdog_create_time": psutil.Process().create_time()}',
     "gate", "G1 no READY file: gate exits 6 NOT_READY quickly"),
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
    ("gate_inner_stays_unattended", G, '    inner["observer_mode"] = "attended"', '    inner["observer_mode"] = "unattended"',
     "gate", "G4 inner manifest is attended-shaped and bound to the outer digest"),
    ("gate_inner_not_bound_to_outer", G, '    inner["unattended_origin_sha256"] = sha_of(outer)', '    inner["unattended_origin_sha256"] = ""',
     "gate", "G4 inner manifest is attended-shaped and bound to the outer digest"),
    ("gate_runs_after_no_go", G, '        if not isinstance(report, dict) or report.get("status") != "GO":', "        if False:",
     "gate", "G5 prelaunch NO_GO stops before run, rc 42"),
    ("watchdog_receipt_not_written", W,
     '    bounded_call(lambda: atomic_write(receipt_path, receipt), 10.0)\n    log(event="gate_killed", reason=reason, family_status=status)',
     '    log(event="gate_killed", reason=reason, family_status=status)', "watchdog", "W2 hung victim killed by stale heartbeat"),
    ("watchdog_ready_not_published", W, "    if not bounded_call(lambda: atomic_write(ready_path, ready), 10.0):", "    if False:", "watchdog",
     "W1 READY file carries chain, watchdog hash and gate identity"),
    ("watchdog_status_read_in_decision_thread", W, "        (hb, _hb_state, why, obs_mono), cycle_mono = worker.read()",
     "        hb, _hb_state, why = read_status(status_path, chain_id, now)\n        obs_mono, cycle_mono = m, m", "watchdog",
     "W23 hung status read: victim still killed within seconds (io_stalled or startup grace)"),
    ("watchdog_heartbeat_write_in_decision_thread", W, "        if worker is not None:\n            worker.post_beat(payload)\n        else:",
     "        if False:\n            worker.post_beat(payload)\n        else:", "watchdog",
     "W24 hung heartbeat write: victim still killed (io_stalled), receipt written"),
    ("watchdog_io_stall_rule_removed", W, "        elif m - cycle_mono > stale_after_s:", "        elif False:", "watchdog",
     "W24 hung heartbeat write: victim still killed (io_stalled), receipt written"),
    ("watchdog_unverified_family_reported_empty", W,
     '    elif remaining_unverified or not complete or family is None:\n        status = "unverified"',
     '    elif False:\n        status = "unverified"', "watchdog",
     "W18 descendant with unreadable creation time is never signalled, family is UNVERIFIED, exit 2"),
    ("watchdog_identity_denied_ignored", W, '        elif state == "denied":\n            unverified.append(pid)',
     '        elif state == "denied":\n            pass', "watchdog",
     "W19 identity AccessDenied after the snapshot: no signal, never 'family_empty', exit 2"),
    ("watchdog_forced_kill_without_reverify", W,
     '            if identity_state(cp, cct) == "match":  # re-verified immediately before the signal', "            if True:",
     "watchdog", "W25 pid taken over between classification and signal: identity re-verified, nothing signalled"),
    ("watchdog_unreadable_snapshot_is_empty", W,
     "    except (psutil.NoSuchProcess, psutil.AccessDenied):\n        return None, False",
     "    except (psutil.NoSuchProcess, psutil.AccessDenied):\n        return [], True", "watchdog",
     "W20 unreadable descendant listing is UNVERIFIED (not empty), exit 2"),
    ("watchdog_unknown_creation_time_descendant_signalled", W,
     "        if ct is None:\n            unverified.append(pid)\n            continue",
     "        if ct is None:\n            alive.append((pid, ct))\n            continue", "watchdog",
     "W18 descendant with unreadable creation time is never signalled, family is UNVERIFIED, exit 2"),
    ("watchdog_snapshot_incomplete_not_flagged", W, "            rows.append((child.pid, None))\n            complete = False",
     "            rows.append((child.pid, None))", "watchdog",
     "W18 descendant with unreadable creation time is never signalled, family is UNVERIFIED, exit 2"),
    ("gate_watch_dir_unchecked", G,
     '    if Path(watch_dir).resolve() != Path(block["watch_dir"]).resolve():\n        raise GateHold("watch_dir_differs_from_approved")',
     '    if False:\n        raise GateHold("watch_dir_differs_from_approved")', "gate",
     "G2 CLI watch dir differs from the approved watch dir -> HOLD_CONTRACT, no work"),
    ("gate_final_bound_unchecked", G, '    if not final_bound_ok(outer, block):\n        raise GateHold("final_deadline_margin")',
     '    if False:\n        raise GateHold("final_deadline_margin")', "gate", ROW % ("final deadline margin", "final_deadline_margin")),
    ("gate_approval_scope_basis_unchecked", G, '        raise GateHold("approval_scope_or_basis")', "        pass", "gate",
     ROW % ("approval wrong scope", "approval_scope_or_basis")),
    ("gate_argv_unchecked", G,
     '    if len(argv) != len(expected) or any(_norm(a) != _norm(b) for a, b in zip(argv, expected)):\n        return "ready_watchdog_argv_mismatch"',
     '    if False:\n        return "ready_watchdog_argv_mismatch"', "gate",
     "G3 watchdog command line with a different program is refused (ready_watchdog_argv_mismatch), no work"),
    ("gate_monitor_chain_unchecked", G, '        return (isinstance(hb, dict) and hb.get("chain_id") == r["chain_id"]',
     "        return (isinstance(hb, dict) and True", "gate",
     "G10 heartbeat of another chain is never progress -> STOP, rc 71 with watcher_heartbeat_stale"),
    ("gate_monitor_pids_unchecked", G,
     '                and hb.get("watchdog_pid") == r["watchdog_pid"] and hb.get("gate_pid") == r["gate_pid"]',
     "                and True", "gate",
     "G11 heartbeat from another watcher pid is never progress -> STOP, rc 71 with watcher_heartbeat_stale"),
    ("gate_monitor_creation_time_unchecked", G, '                and abs(hb["watchdog_create_time"] - r["watchdog_create_time"]) <= 0.05',
     "                and True", "gate",
     "G15 foreign watcher creation time is never progress -> STOP, rc 71 with watcher_heartbeat_stale"),
    ("gate_monitor_seq_type_unchecked", G, '                and type(hb.get("seq")) is int and hb["seq"] > 0 and isinstance(hb.get("state"), str))',
     '                and isinstance(hb.get("seq"), (int, float)) and hb["seq"] > 0 and isinstance(hb.get("state"), str))', "gate",
     "G14 non-integer seq is never progress -> STOP, rc 71 with watcher_heartbeat_stale"),
    ("gate_monitor_seq_monotonic_unchecked", G, '            if hb["seq"] > self.last_seq:', '            if hb["seq"] != self.last_seq:', "gate",
     "G13 non-monotonic seq (2,3,2,3,...) stops being progress -> STOP, rc 71 with watcher_heartbeat_stale"),
    ("gate_monitor_state_unchecked", G, '            if hb["state"] != "WATCHING":', "            if False:", "gate",
     "G8 watcher reporting BLIND -> STOP, rc 71 with watcher_state_BLIND"),
    ("launcher_accepts_ready_file_as_success", L, '            if ready_seen and Path(outer["status_path"]).is_file():',
     "            if ready_seen:", "process", "P11 gate refuses after READY (NO_GO): launcher waits for it, exit 5, LAUNCH_ABORTED"),
    ("launcher_kills_by_pid_lookup", L, '        proc.kill()\n        proc.wait(timeout=10)\n        return "killed"',
     '        psutil.Process(proc.pid).kill()\n        return "killed"', "process",
     "P10 cleanup kills through the held handle only, never by pid lookup; decoy with that pid untouched"),
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
