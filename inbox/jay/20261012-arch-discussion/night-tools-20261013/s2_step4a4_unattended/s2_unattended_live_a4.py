"""LIVE unattended freeze + launch of the stage-0 information-only collection (GPU 0).

NOT AUTHORIZED UNTIL AN ASTRA VERDICT CONTAINS THE MACHINE LINE BELOW. After ASTRA 17z (held) this
helper no longer accepts "a file that exists": the verdict file must contain, as one whole line,

    UNATTENDED_GO scope=gpu0_stage0_single a4_list=<sha256 of s2_step4a4_unattended/SHA256SUMS.txt> a3_list=<sha256 of s2_step4a3/SHA256SUMS.txt>

with both hashes equal to the bytes on disk right now, and every file of both lists must still match.
The matched line and the verdict file hash go into the approval (scope + decision_basis), which the
gate re-checks. Text such as "denied" or "held" in a verdict file can never satisfy this.

  python -B s2_unattended_live_a4.py --astra-verdict <file> --confirm UNATTENDED-GO --by "<who>"
Status:   python -B s2_unattended_live_a4.py --status <run_dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(WORK / "s2_step4a3_launch"))
sys.path.insert(0, str(HERE))
import s2_attended_launch_a3 as att  # noqa: E402
from s2_unattended_gate import APPROVAL_SCOPE  # noqa: E402

PY = att.PY
GO_RE = re.compile(r"^UNATTENDED_GO scope=gpu0_stage0_single a4_list=([0-9a-f]{64}) a3_list=([0-9a-f]{64})\s*$")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_list(directory: Path):
    sums = directory / "SHA256SUMS.txt"
    count = 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, name = line.split(None, 1)
        name = name.lstrip("*").strip()
        count += 1
        target = (directory / name).resolve()
        if not target.is_file() or sha(target) != digest:
            raise SystemExit("NO_GO: %s does not match %s" % (name, sums))
    return count


def find_go_line(verdict: Path):
    a4_list, a3_list = sha(HERE / "SHA256SUMS.txt"), sha(att.BUNDLE / "SHA256SUMS.txt")
    for line in verdict.read_text(encoding="utf-8").splitlines():
        m = GO_RE.match(line)
        if m and m.group(1) == a4_list and m.group(2) == a3_list:
            return line.strip()
    return None


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
    if a.confirm != "UNATTENDED-GO" or not a.by.strip() or not a.astra_verdict or not a.astra_verdict.is_file():
        raise SystemExit("NO_GO: needs --astra-verdict <existing file> --confirm UNATTENDED-GO --by <who>")
    print("[1] A4 list:", verify_list(HERE), "files ok; A3 list:", verify_list(att.BUNDLE), "files ok", flush=True)
    go_line = find_go_line(a.astra_verdict)
    if go_line is None:
        raise SystemExit("NO_GO: the verdict file has no UNATTENDED_GO line that matches the bytes on disk")
    print("[2] ASTRA machine line matched:", go_line, flush=True)
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
                 helper_hashes={"live": sha(__file__), "attended_builder": sha(att.__file__),
                                "a4_list": sha(HERE / "SHA256SUMS.txt"), "a3_list": sha(att.BUNDLE / "SHA256SUMS.txt")})
    outer["unattended"] = {
        "gate_path": str(gate), "gate_sha256": sha(gate), "watchdog_path": str(watchdog),
        "watchdog_sha256": sha(watchdog), "launcher_path": str(launcher), "launcher_sha256": sha(launcher),
        "bundle_dir": str(att.BUNDLE), "bundle_list_sha256": sha(att.BUNDLE / "SHA256SUMS.txt"),
        "watch_dir": str(run / "watch"), "ready_timeout_s": 30, "stale_after_s": 30, "startup_grace_s": 180,
        "poll_s": 1.0, "mono_budget_s": 1080, "hard_deadline_extra_s": 60, "monitor_stale_s": 15,
        "stop_grace_s": 30}
    approval = {"status": "APPROVED", "chain_id": outer["chain_id"], "scope": APPROVAL_SCOPE,
                "by": "%s under %s" % (a.by.strip(), a.astra_verdict.name),
                "decision_basis": {"verdict_file": a.astra_verdict.name, "verdict_sha256": sha(a.astra_verdict),
                                   "verdict_line": go_line},
                "manifest_sha256": hashlib.sha256(att.canonical(outer)).hexdigest(),
                "expires_epoch": outer["deadline_epoch"] + 300}
    mu, au = run / "in" / "manifest_u.json", run / "in" / "approval_u.json"
    mu.write_text(json.dumps(outer, ensure_ascii=False, indent=2), encoding="utf-8")
    au.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[3] frozen:", mu, "\n    deadline_epoch=%.0f" % outer["deadline_epoch"], flush=True)
    res = subprocess.run([str(PY), "-B", str(launcher), "--manifest", str(mu), "--approval", str(au)],
                         capture_output=True, text=True, timeout=180)
    print("[4] launcher rc=%s %s" % (res.returncode, res.stdout.strip()), flush=True)
    print("RUN_DIR", run, flush=True)
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
