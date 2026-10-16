"""Independent family-cleanup observer (ASTRA 17ae section 5). Runs OUTSIDE the supervisor's Job Object, after the
supervisor has exited, and writes one observation file bound to an attempt, a time and the receipt hashes.

  python -B s2_family_observer.py record  --run <run dir> --gpu-uuid <GPU-...>   (before launch: baseline)
  python -B s2_family_observer.py verify  --run <run dir> --gpu-uuid <GPU-...>   (after the supervisor exited)

It never kills a process, never touches another owner's lock and never edits a receipt. What it cannot see it says is
UNKNOWN; UNKNOWN is a HOLD, not a PASS. NVML compute lists are often empty or unsupported on WDDM: that is recorded as
a limitation and is not turned into "compute 0 measured".
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
BUNDLE = Path(__file__).resolve().parent.parent / "bundle"
USD_LOCK = Path("C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock")
GAP_S = 4.0                     # two post observations this far apart
WATCH = ("kit.exe", "isaac-sim")
MARKERS = ("isaaclab", "isaac-sim", "kit.exe", "s2_connect_diag", "s2_train_entry", "usd_isolate", "s2_zero_supervisor",
           "s2_train_launch", "branch_run", "gpu_guard")


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def processes(run: Path):
    """Every process that could belong to this attempt: Isaac/Kit names, our tool markers, or the run directory in argv."""
    import psutil
    out, unreadable = [], 0
    run_text = str(run.resolve()).lower().replace("\\", "/")
    for p in psutil.process_iter(["pid", "name", "create_time", "exe", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            cmd = p.info["cmdline"]
            text = " ".join(cmd).lower().replace("\\", "/") if cmd else ""
            if cmd is None and name.startswith("python"):
                unreadable += 1
                continue
            if any(w in name for w in WATCH) or any(m in text for m in MARKERS) or run_text in text:
                out.append({"pid": p.info["pid"], "name": name, "create_time": round(float(p.info["create_time"]), 3),
                            "exe": p.info["exe"], "cmd_head": text[:200]})
        except Exception:
            unreadable += 1
    return out, unreadable


def nvml_compute(uuid: str):
    """NVML compute processes on the approved physical GPU, plus nvidia-smi as a second view; both with their limits."""
    res = {"nvml": None, "nvml_error": None, "smi": None, "limits": []}
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByUUID(uuid.encode() if isinstance(uuid, str) else uuid)
        procs = pynvml.nvmlDeviceGetComputeRunningProcesses(h)
        res["nvml"] = sorted(int(x.pid) for x in procs)
        res["limits"].append("an empty NVML list on WDDM can mean 'not reported', not 'none'")
    except Exception as ex:
        res["nvml_error"] = repr(ex)[:200]
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid,process_name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace").stdout
        res["smi"] = sorted({int(line.split(",")[0]) for line in out.splitlines()
                             if line.strip() and uuid.lower() in line.lower() and line.split(",")[0].strip().isdigit()})
    except Exception as ex:
        res["smi"] = None
        res["limits"].append("nvidia-smi failed: " + repr(ex)[:100])
    return res


def probe_locks(run: Path, uuid: str):
    """Briefly acquire the same lease and the common USD lock without blocking, then release at once."""
    sys.path.insert(0, str(BUNDLE))
    out = {}
    try:
        from s2_resource_lease import gpu_lease, usd_conversion_lock, LeaseHold
    except Exception as ex:
        return {"error": "import:" + repr(ex)[:150]}
    for label, make in (("gpu_lease", lambda: gpu_lease(run / "ctl" / "lease", uuid)),
                        ("usd_lock", lambda: usd_conversion_lock(USD_LOCK))):
        try:
            lease = make().acquire()
            lease.release(family_empty=True)
            out[label] = "acquired_and_released"
        except LeaseHold as ex:
            out[label] = "HELD:" + str(ex)
        except Exception as ex:
            out[label] = "ERROR:" + repr(ex)[:150]
    return out


def receipts(run: Path):
    keep = {}
    names = ["summary.json", "in/manifest.json", "in/approval.json", "in/job.json",
             "in/cases.json", "in/request.json", "ctl/prelaunch.json",
             "out/episodes.json", "out/foot_result.json"]
    names += [str(p.relative_to(run)).replace("\\", "/")
              for p in (run / "ctl" / "claims").glob("*/*.receipt.json")]
    for name in names:
        p = run / name
        if p.is_file():
            keep[name] = {"sha256": sha(p), "size": p.stat().st_size}
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for k in ("family_active_count", "supervisor_rc", "exit_code", "released", "family_empty", "pid", "child_pid"):
                    if k in data:
                        keep[name][k] = data[k]
            except Exception:
                pass
    return keep


def snapshot(run: Path, uuid: str, with_locks: bool):
    procs, unreadable = processes(run)
    return {"epoch": round(time.time(), 3), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "processes": procs, "process_list_unreadable_count": unreadable, "gpu": nvml_compute(uuid),
            "locks": probe_locks(run, uuid) if with_locks else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("record", "verify"))
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--gpu-uuid", required=True)
    ap.add_argument("--known-pids", default="", help="comma separated 'pid:create_time' of the supervisor and child, from the attempt")
    a = ap.parse_args(argv)
    run = a.run.resolve()
    out_file = run / ("family_baseline.json" if a.mode == "record" else "family_observation.json")
    if out_file.exists():
        print("REFUSED: %s already exists; one observation per attempt" % out_file)
        return 2
    if a.mode == "record":
        data = {"mode": "record", "run": str(run), "gpu_uuid": a.gpu_uuid, "snapshot": snapshot(run, a.gpu_uuid, with_locks=False)}
        out_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        print("recorded baseline: %d candidate processes, written %s" % (len(data["snapshot"]["processes"]), out_file))
        return 0
    base_file = run / "family_baseline.json"
    baseline = json.loads(base_file.read_text(encoding="utf-8")) if base_file.is_file() else None
    first = snapshot(run, a.gpu_uuid, with_locks=True)
    time.sleep(GAP_S)
    second = snapshot(run, a.gpu_uuid, with_locks=True)
    known = {}
    for item in [x for x in a.known_pids.split(",") if x.strip()]:
        pid, ct = item.split(":")
        known[int(pid)] = float(ct)
    base_ids = {(p["pid"], p["create_time"]) for p in (baseline["snapshot"]["processes"] if baseline else [])}
    reasons, unknown = [], []
    for label, snap in (("first", first), ("second", second)):
        new = [p for p in snap["processes"] if (p["pid"], p["create_time"]) not in base_ids and p["pid"] != os.getpid()]
        # an observer-owned tool process (this script) is excluded by pid; anything else new that matches is residual
        new = [p for p in new if "s2_family_observer" not in p["cmd_head"]]
        if new:
            reasons.append("os_residual_%s:%s" % (label, [(p["pid"], p["name"]) for p in new][:5]))
        for pid, ct in known.items():
            # asked directly by pid and creation time, whatever its command line looks like (a reused pid has another creation time)
            try:
                import psutil
                if psutil.pid_exists(pid) and abs(psutil.Process(pid).create_time() - ct) < 1.0:
                    reasons.append("known_attempt_process_still_alive_%s:%d" % (label, pid))
            except Exception as ex:
                unknown.append("known_pid_unreadable_%s:%d:%s" % (label, pid, repr(ex)[:60]))
        if snap["process_list_unreadable_count"]:
            unknown.append("process_list_unreadable_%s:%d" % (label, snap["process_list_unreadable_count"]))
        g = snap["gpu"]
        if g["nvml"] is None and g["smi"] is None:
            unknown.append("gpu_compute_list_unavailable_%s" % label)
        else:
            pids = set((g["nvml"] or [])) | set((g["smi"] or []))
            attempt_pids = set(known) | {p["pid"] for p in snap["processes"] if (p["pid"], p["create_time"]) not in base_ids}
            if pids & attempt_pids:
                reasons.append("gpu_pid_residual_%s:%s" % (label, sorted(pids & attempt_pids)))
        for lab, st in (snap["locks"] or {}).items():
            if st != "acquired_and_released":
                (reasons if str(st).startswith("HELD") else unknown).append("lock_%s_%s:%s" % (lab, label, st))
    rec = receipts(run)
    for name, r in rec.items():
        if r.get("family_active_count") not in (None, 0):
            reasons.append("receipt_family_not_zero:%s" % name)
    verdict = "PASS" if not reasons and not unknown else ("HOLD_UNKNOWN" if not reasons else "HOLD")
    data = {"mode": "verify", "run": str(run), "gpu_uuid": a.gpu_uuid, "gap_s": GAP_S, "known_pids": known,
            "baseline_sha256": sha(base_file) if baseline else None, "receipts": rec, "first": first, "second": second,
            "reasons": reasons, "unknown": unknown, "verdict": verdict,
            "limits": ["PASS means no residual OS process, no listed GPU compute pid of this attempt and both locks acquirable; "
                       "it does not prove NVML compute 0 on WDDM", "a process list the observer could not read is UNKNOWN, not none"]}
    out_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    print("family observation: %s (reasons=%s unknown=%s) written %s" % (verdict, reasons, unknown, out_file))
    return 0 if verdict == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
