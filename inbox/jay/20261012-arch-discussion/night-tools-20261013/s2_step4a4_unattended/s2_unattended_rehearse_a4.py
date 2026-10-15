"""Rehearse the unattended chain on the real machine WITHOUT starting Isaac.

Builds a real unattended outer manifest (same values as the attended GPU 0 freeze), starts the
production launcher and watchdog, and uses gate_harness_real_prelaunch.py as the gate: contract,
READY handshake and the REAL A3 prelaunch run; the run function returns HOLD and starts nothing.
Needs the ASCII lab copy next to this file: ../s2_step4a3 (frozen bundle) and ../s2_step4a3_launch.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(WORK / "s2_step4a3_launch"))
import s2_attended_launch_a3 as att  # noqa: E402

PY = att.PY


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    print("[1] frozen A3 bundle:", att.verify_frozen_bundle(), "files ok", flush=True)
    run, ctl, manifest, _m, _a = att.build("urehearse", "none (unattended rehearsal, no Isaac)")
    gate = HERE / "gate_harness_real_prelaunch.py"
    watchdog, launcher = HERE / "s2_watchdog_v2.py", HERE / "s2_unattended_launch.py"
    outer = dict(manifest)
    outer.update(contract_version="a4u", observer_mode="unattended", deadline_epoch=time.time() + 1600)
    outer["unattended"] = {
        "gate_path": str(gate), "gate_sha256": sha(gate), "watchdog_path": str(watchdog),
        "watchdog_sha256": sha(watchdog), "launcher_path": str(launcher), "launcher_sha256": sha(launcher),
        "bundle_dir": str(att.BUNDLE), "bundle_list_sha256": sha(att.BUNDLE / "SHA256SUMS.txt"),
        "watch_dir": str(run / "watch"), "ready_timeout_s": 30, "stale_after_s": 30, "startup_grace_s": 180,
        "poll_s": 1.0, "mono_budget_s": 1020, "hard_deadline_extra_s": 60, "monitor_stale_s": 15,
        "stop_grace_s": 30}
    approval = {"status": "APPROVED", "chain_id": outer["chain_id"], "by": "lead rehearsal (no Isaac)",
                "manifest_sha256": hashlib.sha256(att.canonical(outer)).hexdigest(),
                "expires_epoch": outer["deadline_epoch"] + 300}
    mu, au = run / "in" / "manifest_u.json", run / "in" / "approval_u.json"
    mu.write_text(json.dumps(outer, ensure_ascii=False, indent=2), encoding="utf-8")
    au.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[2] frozen unattended pair:", mu, flush=True)
    t0 = time.time()
    res = subprocess.run([str(PY), "-B", str(launcher), "--manifest", str(mu), "--approval", str(au)],
                         capture_output=True, text=True, timeout=120)
    print("[3] launcher rc=%s out=%s took=%.1fs" % (res.returncode, res.stdout.strip(), time.time() - t0), flush=True)
    watch = run / "watch"
    result = None
    end = time.time() + 90
    while time.time() < end:
        if (watch / "gate_result.json").is_file():
            result = json.loads((watch / "gate_result.json").read_text(encoding="utf-8"))
            break
        time.sleep(0.5)
    print("[4] gate_result:", json.dumps(result, ensure_ascii=False)[:700], flush=True)
    rec = json.loads((watch / "launch_record.json").read_text(encoding="utf-8")) if (watch / "launch_record.json").is_file() else {}
    time.sleep(3)
    left = []
    for key in ("gate", "watchdog"):
        pid, ct = rec.get(key + "_pid"), rec.get(key + "_create_time")
        try:
            p = psutil.Process(pid)
            if abs(p.create_time() - ct) <= 0.05 and p.is_running():
                left.append(key)
        except (psutil.NoSuchProcess, TypeError):
            pass
    wlog = (watch / "watchdog.log").read_text(encoding="utf-8") if (watch / "watchdog.log").is_file() else ""
    events = [json.loads(x)["event"] for x in wlog.splitlines()]
    verdict = {"launch_rc": res.returncode, "gate_state": (result or {}).get("state"),
               "inner_outcome_reasons": ((result or {}).get("verdict") or {}).get("reasons"),
               "prelaunch_report": (result or {}).get("report"),
               "watchdog_events": events, "processes_left": left, "run_dir": str(run)}
    (run / "rehearsal_summary.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[5] summary:", json.dumps(verdict, ensure_ascii=False), flush=True)
    ok = (res.returncode == 0 and (result or {}).get("state") == "DONE" and not left
          and "watched_ended_by_itself" in events and not (watch / "kill_receipt.json").exists())
    print("REHEARSAL", "OK" if ok else "NOT OK", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
