"""Attended one-shot launcher for the S2 stage-0 information-only collection (A3 bundle).

Lives OUTSIDE the frozen bundle (the bundle bytes are what ASTRA 17y verified). It only does what
17y section 2 describes: freeze manifest + approval from measured values, run the prelaunch check,
and (live mode only) run the supervisor in the foreground of the attendee's terminal.

  --rehearse                    freeze + validate + real prelaunch, never starts the supervisor
  --live --attendee NAME --confirm LAUNCH-ATTENDED
                                same, then the supervisor, with a status line every 10 s

Run with the Isaac interpreter and -B:
  C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B s2_attended_launch_a3.py --rehearse
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WORK = HERE.parent
BUNDLE = WORK / "s2_step4a3"
sys.path.insert(0, str(BUNDLE))

from s2_known_scene_a2 import answer_sha256  # noqa: E402
from s2_stage0_contract_a2 import REQUIRED_BUNDLE, required_args, sha  # noqa: E402
from s2_stage0_prelaunch import competing_isaac_processes  # noqa: E402
from s2_stage0_resources_a2 import NvmlMeter  # noqa: E402
from s2_zero_supervisor import canonical  # noqa: E402

PY = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
GPU0_UUID = "GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
GPU0_BUS = "41:00.0"
PARENT = Path("C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt")
PARENT_SHA = "c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"
HOOK = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py")
ISOLATE = Path("C:/isaac/ext/go2_rl_robotlab/_eval/usd_isolate_run_v3.py")
ISOLATE_SHA = "30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb"
LIST_SHA = "dc6cc314918320020b6eadc580bbce12072e021493b7bf2292506165329ae9f2"
ASSET = ("https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/"
         "IsaacLab/Robots/Unitree/Go2/go2.usd")
VERDICT_DOC = WORK.parent / "VERIFY-astra-17y.md"
MAX_WALL_S = 900
DEADLINE_SLACK_S = 1500
GIB = 1024 ** 3


def verify_frozen_bundle():
    sums = BUNDLE / "SHA256SUMS.txt"
    if hashlib.sha256(sums.read_bytes()).hexdigest() != LIST_SHA:
        raise SystemExit("NO_GO: SHA256SUMS.txt differs from the list ASTRA 17y verified")
    bad = []
    count = 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip().replace("\r", "")
        if not line:
            continue
        digest, name = line.split(None, 1)
        name = name.lstrip("*").strip()
        count += 1
        path = BUNDLE / name
        if not path.is_file() or sha(path) != digest:
            bad.append(name)
    if count != 47 or bad:
        raise SystemExit("NO_GO: bundle hash check %d files, bad=%s" % (count, bad))
    return count


def gpu_compute_apps():
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,gpu_uuid",
                          "--format=csv,noheader"], capture_output=True, text=True, timeout=30).stdout
    rows = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            rows.append({"pid": parts[0], "name": parts[1], "gpu_uuid": parts[2]})
    return rows


def build(mode: str, attendee: str):
    now = time.time()
    tag = "%s-%s" % (mode, time.strftime("%Y%m%d-%H%M%S", time.localtime(now)))
    run = WORK / "s2_runs" / tag
    in_dir, ctl = run / "in", run / "ctl"
    for d in (in_dir, ctl):
        d.mkdir(parents=True, exist_ok=False)
    criteria = in_dir / "criteria.json"
    criteria.write_text(json.dumps(dict(xy_tolerance_m=.002, z_tolerance_m=.002, boundary_exclusion_m=.005,
                                        steps=256, warmup_steps=16)), encoding="utf-8")
    deadline = now + DEADLINE_SLACK_S
    manifest = {
        "contract_version": "a2", "chain_id": "s2-stage0-a3-" + tag, "attempt": "one",
        "purpose": "stage0_information_only", "max_launches": 1, "retry_count": 0,
        "observer_mode": "attended", "reservation_confirmed": True,
        "attendee": attendee, "permission_doc": str(VERDICT_DOC.name),
        "permission_doc_sha256": sha(VERDICT_DOC),
        "python_path": str(PY), "python_sha256": sha(PY),
        "diag_path": str(BUNDLE / "s2_connect_diag_17v.py"), "diag_sha256": sha(BUNDLE / "s2_connect_diag_17v.py"),
        "criteria_path": str(criteria), "criteria_sha256": sha(criteria),
        "parent_path": str(PARENT), "parent_sha256": PARENT_SHA,
        "out_root": str(run / "out"), "claim_root": str(ctl / "claims"),
        "status_path": str(ctl / "status.json"), "stop_path": str(ctl / "STOP"),
        "lease_root": str(ctl / "lease"), "usd_root": str(run / "usd"),
        "usd_lock_path": "C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock",
        "log_path": str(run / "logs" / "child.log"), "prelaunch_report_path": str(ctl / "prelaunch.json"),
        "gpu_uuid": GPU0_UUID, "gpu_index": 0, "gpu_bus_id": GPU0_BUS,
        "min_free_vram_bytes": 8 * GIB, "running_floor_vram_bytes": 2 * GIB,
        "min_free_disk_bytes": 2 * GIB, "max_disk_bytes": GIB,
        "asset_path": ASSET, "asset_ref_sha256": hashlib.sha256(ASSET.encode()).hexdigest(),
        "hook_source_path": str(HOOK), "hook_source_sha256": sha(HOOK),
        "scene_answer_sha256": answer_sha256(),
        "code_hashes": {name: sha(BUNDLE / name) for name in REQUIRED_BUNDLE},
        "isolate_path": str(ISOLATE), "isolate_sha256": ISOLATE_SHA,
        "expect_conversions": "0",
        "diag_options": {"seed": 42, "num_envs": 8, "steps": 256, "gap_proportion": .25,
                         "stones_proportion": .25, "step_height_m": .2, "step_width_m": .3,
                         "geometry_tolerance_m": .002},
        "deadline_epoch": deadline, "max_wall_s": MAX_WALL_S,
    }
    manifest["diag_args"] = required_args(manifest)
    approval = {"status": "APPROVED", "chain_id": manifest["chain_id"],
                "by": "lead freeze under ASTRA 17y conditional permission; attendee=" + attendee,
                "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
                "expires_epoch": deadline + 300}
    mpath, apath = in_dir / "manifest.json", in_dir / "approval.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    apath.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
    # re-read what was written: the digest must be reproducible from the file the scripts will read
    reread = json.loads(mpath.read_text(encoding="utf-8"))
    if hashlib.sha256(canonical(reread)).hexdigest() != approval["manifest_sha256"]:
        raise SystemExit("NO_GO: manifest digest changes after write")
    return run, ctl, manifest, mpath, apath


def run_prelaunch(mpath, apath):
    t0 = time.time()
    res = subprocess.run([str(PY), "-B", str(BUNDLE / "s2_stage0_prelaunch.py"),
                          "--manifest", str(mpath), "--approval", str(apath)],
                         capture_output=True, text=True, timeout=180, cwd=str(BUNDLE))
    took = time.time() - t0
    report = None
    for line in reversed(res.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            report = json.loads(line)
            break
    return res.returncode, report, took, res.stderr[-600:]


def status_line(path):
    try:
        s = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "status: (not readable yet)"
    dev = s.get("device") or {}
    free = dev.get("free_vram_bytes")
    return "status: state=%s update=%s remaining_s=%s free_vram_gib=%s output_mib=%s" % (
        s.get("state"), s.get("update"),
        None if s.get("remaining_s") is None else round(s["remaining_s"]),
        None if free is None else round(free / GIB, 2),
        None if s.get("output_bytes") is None else round(s["output_bytes"] / 1048576, 1))


def free_vram_bytes(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("device", {}).get("free_vram_bytes")
    except (OSError, ValueError, AttributeError):
        return None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--live", action="store_true")
    ap.add_argument("--attendee", default="")
    ap.add_argument("--confirm", default="")
    a = ap.parse_args()
    if a.live and (not a.attendee.strip() or a.confirm != "LAUNCH-ATTENDED"):
        raise SystemExit("NO_GO: --live needs --attendee NAME and --confirm LAUNCH-ATTENDED")
    mode = "live" if a.live else "rehearse"
    attendee = a.attendee.strip() if a.live else "none (rehearsal, supervisor is never started)"
    print("[1] frozen bundle:", verify_frozen_bundle(), "files match, list sha ok", flush=True)
    meter = NvmlMeter()
    try:
        first = meter.probe(0)
    finally:
        meter.close()
    if first["uuid"] != GPU0_UUID or first["bus"] != GPU0_BUS:
        raise SystemExit("NO_GO: GPU 0 identity differs: %s" % first)
    apps = [r for r in gpu_compute_apps() if r["gpu_uuid"] == GPU0_UUID
            and any(k in r["name"].lower() for k in ("python", "kit", "isaac"))]
    other = competing_isaac_processes()
    if apps or other:
        raise SystemExit("NO_GO: competing compute/Isaac process: %s %s" % (apps, other))
    print("[2] GPU 0 identity ok, free_vram_gib=%.2f, no competing process" % (first["free_vram_bytes"] / GIB), flush=True)
    run, ctl, manifest, mpath, apath = build(mode, attendee)
    print("[3] frozen:", mpath, "\n    approval:", apath, "\n    deadline_epoch=%.0f max_wall_s=%d" % (
        manifest["deadline_epoch"], manifest["max_wall_s"]), flush=True)
    rc, report, took, err = run_prelaunch(mpath, apath)
    print("[4] prelaunch rc=%s took=%.1fs status=%s reason=%s" % (rc, took, (report or {}).get("status"),
                                                                 (report or {}).get("reason")), flush=True)
    if err.strip():
        print("    stderr tail:", err.strip()[-300:], flush=True)
    summary = {"mode": mode, "run": str(run), "prelaunch_rc": rc, "prelaunch_report": report,
               "prelaunch_seconds": took, "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest()}
    if rc != 0 or not report or report.get("status") != "GO":
        (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("NO_GO: not launching.", flush=True)
        return 42
    age = time.time() - report["checked_epoch"]
    print("    GO is %.1fs old (supervisor accepts <= 60 s)" % age, flush=True)
    if a.rehearse:
        (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("REHEARSAL DONE: prelaunch GO, supervisor NOT started.", flush=True)
        return 0 if age <= 60 else 43
    if age > 45:
        (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("NO_GO: GO already %.1fs old, a fresh prelaunch is needed (nothing started)." % age, flush=True)
        return 44
    print("[5] STARTING SUPERVISOR (attendee=%s). STOP file: %s" % (attendee, manifest["stop_path"]), flush=True)
    t_start = time.time()
    # 14:03 attempt one died in 2 s: Kit asks for the EULA on stdin ("input(): lost sys.stdin"). Every working
    # Isaac launcher in this repo sets these two variables; the A3 supervisor passes its own environment on.
    env = {**os.environ, "OMNI_KIT_ACCEPT_EULA": "YES", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([str(PY), "-B", str(BUNDLE / "s2_zero_supervisor.py"),
                             "--manifest", str(mpath), "--approval", str(apath)], cwd=str(BUNDLE), env=env)
    print("    supervisor pid=%d" % proc.pid, flush=True)
    stop_sent = None
    min_free = None
    try:
        while proc.poll() is None:
            for _ in range(10):
                time.sleep(1)
                value = free_vram_bytes(manifest["status_path"])
                if isinstance(value, int) and (min_free is None or value < min_free):
                    min_free = value
                if proc.poll() is not None:
                    break
            print("    t+%ds %s min_free_vram_gib_so_far=%s" % (
                time.time() - t_start, status_line(manifest["status_path"]),
                None if min_free is None else round(min_free / GIB, 2)), flush=True)
    except KeyboardInterrupt:
        Path(manifest["stop_path"]).write_text("stop requested by attendee\n", encoding="utf-8")
        stop_sent = time.time()
        print("STOP written. Waiting for the supervisor (pid %d) to stop its own family..." % proc.pid, flush=True)
        while proc.poll() is None and time.time() - stop_sent < 90:
            time.sleep(2)
        if proc.poll() is None:
            print("Supervisor still alive after 90 s. Only if you confirm it is hung: taskkill /PID %d /T /F" % proc.pid,
                  flush=True)
    rc2 = proc.poll()
    summary.update(supervisor_rc=rc2, elapsed_s=time.time() - t_start, stop_sent=stop_sent is not None,
                   min_free_vram_bytes_seen_every_second=min_free,
                   final_status=status_line(manifest["status_path"]))
    out = Path(manifest["out_root"])
    summary["out_files"] = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())[:200] if out.exists() else []
    (run / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[6] supervisor rc=%s elapsed=%.0fs\n    %s\n    summary: %s" % (
        rc2, summary["elapsed_s"], summary["final_status"], run / "summary.json"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
