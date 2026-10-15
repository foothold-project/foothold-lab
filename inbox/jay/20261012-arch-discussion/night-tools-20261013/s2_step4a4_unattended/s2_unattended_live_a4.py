"""LIVE unattended freeze + launch of the stage-0 information-only collection (GPU 0). NOT YET AUTHORIZED.

Refuses to run unless an ASTRA verdict file that permits the unattended chain exists and the
operator passes its path and the exact confirm token. The launcher exits after READY; the gate and
the independent watchdog keep running without this terminal, the Claude session or Orca.

  python -B s2_unattended_live_a4.py --astra-verdict <VERIFY-astra-17z.md> --confirm UNATTENDED-GO-17Z --by "<who>"
Status:   python -B s2_unattended_live_a4.py --status <run_dir>
"""
from __future__ import annotations

import argparse
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


def alive(pid, ct):
    try:
        p = psutil.Process(pid)
        return abs(p.create_time() - ct) <= 0.05 and p.is_running()
    except (psutil.NoSuchProcess, TypeError):
        return False


def status(run_dir: Path):
    watch = run_dir / "watch"
    out = {"run_dir": str(run_dir)}
    for name in ("launch_record.json", "gate_result.json", "kill_receipt.json", "watchdog_hb.json"):
        p = watch / name
        out[name] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    rec = out["launch_record.json"] or {}
    out["gate_alive"] = alive(rec.get("gate_pid"), rec.get("gate_create_time"))
    out["watchdog_alive"] = alive(rec.get("watchdog_pid"), rec.get("watchdog_create_time"))
    sp = run_dir / "ctl" / "status.json"
    out["supervisor_status"] = json.loads(sp.read_text(encoding="utf-8")) if sp.is_file() else None
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--astra-verdict", type=Path)
    ap.add_argument("--confirm", default="")
    ap.add_argument("--by", default="")
    ap.add_argument("--status", type=Path)
    a = ap.parse_args()
    if a.status:
        return status(a.status)
    if a.confirm != "UNATTENDED-GO-17Z" or not a.by.strip() or not a.astra_verdict or not a.astra_verdict.is_file():
        raise SystemExit("NO_GO: needs --astra-verdict <existing file> --confirm UNATTENDED-GO-17Z --by <who>")
    print("[1] frozen A3 bundle:", att.verify_frozen_bundle(), "files ok", flush=True)
    meter = att.NvmlMeter()
    try:
        first = meter.probe(0)
    finally:
        meter.close()
    if first["uuid"] != att.GPU0_UUID or first["bus"] != att.GPU0_BUS:
        raise SystemExit("NO_GO: GPU 0 identity differs: %s" % first)
    apps = [r for r in att.gpu_compute_apps() if r["gpu_uuid"] == att.GPU0_UUID
            and any(k in r["name"].lower() for k in ("python", "kit", "isaac"))]
    other = att.competing_isaac_processes()
    if apps or other:
        raise SystemExit("NO_GO: competing compute/Isaac process: %s %s" % (apps, other))
    run, ctl, manifest, _m, _a = att.build("ulive", "unattended; approved by " + a.by.strip())
    gate, watchdog, launcher = HERE / "s2_unattended_gate.py", HERE / "s2_watchdog_v2.py", HERE / "s2_unattended_launch.py"
    outer = dict(manifest)
    outer.update(contract_version="a4u", observer_mode="unattended", deadline_epoch=time.time() + 1600,
                 unattended_permission_doc=a.astra_verdict.name, unattended_permission_sha256=sha(a.astra_verdict))
    outer["unattended"] = {
        "gate_path": str(gate), "gate_sha256": sha(gate), "watchdog_path": str(watchdog),
        "watchdog_sha256": sha(watchdog), "launcher_path": str(launcher), "launcher_sha256": sha(launcher),
        "bundle_dir": str(att.BUNDLE), "bundle_list_sha256": sha(att.BUNDLE / "SHA256SUMS.txt"),
        "watch_dir": str(run / "watch"), "ready_timeout_s": 30, "stale_after_s": 30, "startup_grace_s": 180,
        "poll_s": 1.0, "mono_budget_s": 1020, "hard_deadline_extra_s": 60, "monitor_stale_s": 15,
        "stop_grace_s": 30}
    approval = {"status": "APPROVED", "chain_id": outer["chain_id"],
                "by": "%s under %s" % (a.by.strip(), a.astra_verdict.name),
                "manifest_sha256": hashlib.sha256(att.canonical(outer)).hexdigest(),
                "expires_epoch": outer["deadline_epoch"] + 300}
    mu, au = run / "in" / "manifest_u.json", run / "in" / "approval_u.json"
    mu.write_text(json.dumps(outer, ensure_ascii=False, indent=2), encoding="utf-8")
    au.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[2] frozen:", mu, "\n    deadline_epoch=%.0f" % outer["deadline_epoch"], flush=True)
    res = subprocess.run([str(PY), "-B", str(launcher), "--manifest", str(mu), "--approval", str(au)],
                         capture_output=True, text=True, timeout=120)
    print("[3] launcher rc=%s %s" % (res.returncode, res.stdout.strip()), flush=True)
    print("RUN_DIR", run, flush=True)
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
