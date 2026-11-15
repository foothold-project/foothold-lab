"""Attended launch tool for the FIRST B plumbing run (ASTRA 17ae): arm A, synthetic_known_answer, N=32, 1 iteration.

  --rehearse  seal the request into a manifest, build the approval, run the B prelaunch (CPU static checks plus the real GPU 0
              identity / free VRAM / lease / USD lock probes) and stop. Starts no supervisor and no child.
  --live      the same, then run the B attended supervisor once, in the foreground, with an independent family observer
              before and after (s2_family_observer.py). Needs a consent file that quotes the team lead's own words.

Everything the team lead decides is a named constant below; everything else is read from the sealed request. The tool never
retries and never starts a second arm. Nothing here edits the frozen B bundle.
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
WORK = Path("C:/Users/AI-WS01/s2_lab")
B = WORK / "night-tools-20261013" / "s2_step8"          # frozen B bundle (copy of the repository's s2_step8 without evidence)
PY = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
LIST_SHA = "5175e4dfcabafe779b99dd23214cc37789e400498349339fd3b320d5e629fd11"
GPU0_UUID = "GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
GPU0_BUS = "41:00.0"
HOOK = "C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py"   # same file A3 pinned (b720063b...)
MAX_WALL_S = 600
DEADLINE_SLACK_S = 1500
MIN_FREE_VRAM = 6 * 1024 ** 3          # decided here, recorded in the manifest; the run's own minimum is measured and reported
RUNNING_FLOOR_VRAM = 2 * 1024 ** 3
VERDICT_DOCS = ("VERIFY-astra-17ae.md",)
GIB = 1024 ** 3


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def verify_bundle() -> int:
    lines = [l for l in (B / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    bad = []
    for line in lines:
        digest, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        if not (B / name).is_file() or sha(B / name) != digest:
            bad.append(name)
    if bad or sha(B / "SHA256SUMS.txt") != LIST_SHA:
        raise SystemExit("NO_GO: frozen B bundle differs: %s list_sha_ok=%s" % (bad[:5], sha(B / "SHA256SUMS.txt") == LIST_SHA))
    return len(lines)


def build(mode, attendee, consent):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run = WORK / "night-tools-20261013" / "s2_runs" / ("plumbA-%s-%s" % (mode, stamp))
    for sub in ("in", "ctl"):   # out/ and out/usd must NOT pre-exist: the B prelaunch refuses an existing output (output_or_STOP_exists)
        (run / sub).mkdir(parents=True, exist_ok=False)
    req = json.loads((B / "request_plumbing_A_first.json").read_text(encoding="utf-8"))
    now = time.time()
    deadline = now + DEADLINE_SLACK_S
    chain = "s2-plumbing-A-first-%s-%s" % (mode, stamp)
    m_path, a_path = run / "in" / "manifest.json", run / "in" / "approval.json"
    req.update(chain_id=chain, plumbing_pair={"pair_id": chain, "ordinal": 1}, deadline_epoch=deadline,
               min_free_vram_bytes=MIN_FREE_VRAM, running_floor_vram_bytes=RUNNING_FLOOR_VRAM, max_wall_s=MAX_WALL_S,
               approval_path=str(a_path), approval_by=attendee, prelaunch_report_path=str(run / "ctl" / "prelaunch.json"),
               status_path=str(run / "ctl" / "status.json"), log_path=str(run / "logs" / "child.log"),
               claim_root=str(run / "ctl" / "claim"), gpu_lease_root=str(run / "ctl" / "lease"),
               manifest_path=str(m_path))
    req["plan"].update(out_root=str(run / "out"), stop_file=str(run / "ctl" / "STOP"), deadline_epoch=deadline,
                       sensor_hook_path=HOOK)
    req_path = run / "in" / "request.json"
    req_path.write_text(json.dumps(req, indent=2, sort_keys=True), encoding="utf-8")
    sealed = subprocess.run([str(PY), "-B", str(B / "s2_train_manifest.py"), "--request", str(req_path), "--manifest", str(m_path)],
                            capture_output=True, text=True, cwd=str(B), timeout=120, encoding="utf-8", errors="replace")
    if sealed.returncode != 0:
        raise SystemExit("NO_GO: sealing the request failed: %s" % ((sealed.stderr or sealed.stdout).strip()[-300:]))
    manifest = json.loads(m_path.read_text(encoding="utf-8"))
    approval = {"status": "APPROVED", "scope": manifest["scope"], "chain_id": chain,
                "by": "lead freeze under ASTRA 17ae conditions (first B plumbing, A3.2 sequel); attendee=" + attendee,
                "approval_id": "plumbA-%s-%s" % (mode, stamp), "eula_accepted": True, "expires_epoch": deadline + 300,
                "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
                "permission_docs": {n: sha(WORK / n) for n in VERDICT_DOCS if (WORK / n).is_file()},
                "consent": consent}
    a_path.write_text(json.dumps(approval, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return run, manifest, m_path, a_path


def run_b(m_path, a_path, prelaunch):
    cmd = [str(PY), "-B", str(B / "s2_train_launch.py"), "--manifest", str(m_path), "--approval", str(a_path)]
    if prelaunch:
        cmd.append("--prelaunch")
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(B), timeout=300, encoding="utf-8", errors="replace")
    try:
        report = json.loads((p.stdout or "").strip().splitlines()[-1])
    except Exception:
        report = None
    return p.returncode, report, time.time() - t0, p.stderr


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--live", action="store_true")
    ap.add_argument("--attendee", default="")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--consent-file", type=Path, default=None)
    a = ap.parse_args()
    if a.live and (not a.attendee.strip() or a.confirm != "LAUNCH-ATTENDED"):
        raise SystemExit("NO_GO: --live needs --attendee NAME and --confirm LAUNCH-ATTENDED")
    consent = None
    if a.live:
        if a.consent_file is None or not a.consent_file.is_file():
            raise SystemExit("NO_GO: --live needs --consent-file (EULA, attendance and go for this one plumbing run, quoted)")
        consent = json.loads(a.consent_file.read_text(encoding="utf-8"))
        ok = all(isinstance(consent.get(k), str) and consent[k].strip() for k in ("by", "eula_accepted", "attending_until_end", "go_for_this_one_run", "quote"))
        if not ok or any(consent.get(k) != "yes" for k in ("eula_accepted", "attending_until_end", "go_for_this_one_run")) \
                or consent.get("scope") != "s2_plumbing_attended_one_shot_arm_A":
            raise SystemExit("NO_GO: consent file must say yes to EULA, attendance and go, with the quote and scope s2_plumbing_attended_one_shot_arm_A")
    mode = "live" if a.live else "rehearse"
    attendee = a.attendee.strip() if a.live else "none (rehearsal, no supervisor)"
    print("[1] frozen B bundle: %d files match, list sha ok" % verify_bundle(), flush=True)
    sys.path.insert(0, str(WORK / "night-tools-20261013" / "s2_step4a3"))
    from s2_stage0_resources_a2 import NvmlMeter
    meter = NvmlMeter()
    try:
        first = meter.probe(0)
    finally:
        meter.close()
    if first["uuid"] != GPU0_UUID or first["bus"] != GPU0_BUS:
        raise SystemExit("NO_GO: GPU 0 identity differs: %s" % first)
    print("[2] GPU 0 identity ok, free_vram_gib=%.2f" % (first["free_vram_bytes"] / GIB), flush=True)
    run, manifest, m_path, a_path = build(mode, attendee, consent)
    print("[3] sealed: %s\n    approval: %s\n    chain=%s deadline_epoch=%.0f" % (m_path, a_path, manifest["chain_id"], manifest["deadline_epoch"]), flush=True)
    observer = Path(__file__).resolve().parent / "s2_family_observer.py"
    if a.live:
        base = subprocess.run([str(PY), "-B", str(observer), "record", "--run", str(run), "--gpu-uuid", GPU0_UUID], capture_output=True,
                              text=True, timeout=180, encoding="utf-8", errors="replace")
        print("[3b] observer baseline rc=%s %s" % (base.returncode, (base.stdout or base.stderr).strip()[-160:]), flush=True)
        if base.returncode != 0:
            raise SystemExit("NO_GO: independent observer baseline failed; nothing started")
    rc, report, took, err = run_b(m_path, a_path, prelaunch=True)
    print("[4] prelaunch rc=%s took=%.1fs status=%s reason=%s" % (rc, took, (report or {}).get("status"), (report or {}).get("reason")), flush=True)
    if err.strip():
        print("    stderr tail:", err.strip()[-300:], flush=True)
    summary = {"mode": mode, "run": str(run), "prelaunch_rc": rc, "prelaunch_report": report,
               "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest()}
    (run / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if rc != 0 or not report or report.get("status") != "GO":
        print("NO_GO: not launching.", flush=True)
        return 42
    age = time.time() - report["checked_epoch"]
    print("    GO is %.1fs old (the supervisor accepts <= 60 s)" % age, flush=True)
    if a.rehearse:
        print("REHEARSAL DONE: prelaunch GO, supervisor NOT started.", flush=True)
        return 0 if age <= 60 else 43
    if age > 45:
        print("NO_GO: GO already %.1fs old, a fresh prelaunch is needed (nothing started)." % age, flush=True)
        return 44
    print("[5] STARTING B SUPERVISOR (attendee=%s). STOP file: %s" % (attendee, manifest["plan"]["stop_file"]), flush=True)
    t_start = time.time()
    env = {**os.environ, "OMNI_KIT_ACCEPT_EULA": "YES", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([str(PY), "-B", str(B / "s2_train_launch.py"), "--manifest", str(m_path), "--approval", str(a_path)],
                            cwd=str(B), env=env)
    print("    supervisor pid=%d" % proc.pid, flush=True)
    known = {}

    def note_pid(pid):
        try:
            import psutil
            known.setdefault(int(pid), psutil.Process(int(pid)).create_time())
        except Exception:
            pass
    note_pid(proc.pid)
    stop_sent = None
    status_path = Path(manifest["status_path"])
    try:
        while proc.poll() is None:
            for _ in range(10):
                time.sleep(1)
                try:
                    st = json.loads(status_path.read_text(encoding="utf-8"))
                    note_pid(st.get("pid"))
                    note_pid(st.get("child_pid"))
                except Exception:
                    st = {}
                if proc.poll() is not None:
                    break
            print("    t+%ds state=%s remaining_s=%s" % (time.time() - t_start, st.get("state"), st.get("remaining_s")), flush=True)
    except KeyboardInterrupt:
        Path(manifest["plan"]["stop_file"]).write_text("stop requested by attendee\n", encoding="utf-8")
        stop_sent = time.time()
        print("STOP written. Waiting for the supervisor (pid %d) to stop its own family..." % proc.pid, flush=True)
        while proc.poll() is None and time.time() - stop_sent < 90:
            time.sleep(2)
        if proc.poll() is None:
            print("Supervisor still alive after 90 s. Only if you confirm it is hung: taskkill /PID %d /T /F" % proc.pid, flush=True)
    rc2 = proc.poll()
    summary.update(supervisor_rc=rc2, elapsed_s=time.time() - t_start, stop_sent=stop_sent is not None)
    out = Path(manifest["plan"]["out_root"])
    summary["out_files"] = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())[:200] if out.exists() else []
    (run / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[6] supervisor rc=%s elapsed=%.0fs summary: %s" % (rc2, summary["elapsed_s"], run / "summary.json"), flush=True)
    if rc2 is not None:
        time.sleep(2)
        known_arg = ",".join("%d:%f" % (k, v) for k, v in known.items())
        ver = subprocess.run([str(PY), "-B", str(observer), "verify", "--run", str(run), "--gpu-uuid", GPU0_UUID, "--known-pids", known_arg],
                             capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
        print("[7] independent family observation rc=%s\n    %s" % (ver.returncode, (ver.stdout or ver.stderr).strip()[-400:]), flush=True)
        summary["family_observation_rc"] = ver.returncode
        (run / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
