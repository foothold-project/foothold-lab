"""14:00 hand-over freeze (lead 10/13, VERIFY-astra-16d 6 / 16f 5 / 16h 4). Reads the live eval tree; writes only
<root>/handover_<stamp>/ and, on success, moves the old stop requests (out/*.stop) into it.
Exit 0 and manifest status "complete" only when ALL of these hold:
  - no process of the old drivers (given pids) or their descendants, no Isaac-like or unreadable-argv python, no kit is
    alive, at the start AND again after everything was copied and hashed (16h 4.1: a writer that starts in between);
  - every run that a log marks valid has all its required files (result files incl. env_origins.npy, which the pairing
    fingerprint uses, stamp, .log, .guard.json); runs that are not valid only have their missing files recorded;
  - after the manifest is built, the ORIGINAL logs, every hashed run file, the checkpoints and the pins are hashed again
    and are unchanged (16h 4.1: the copies alone do not show the originals stayed put);
  - the log copies and stamp copies re-hash equal; pins and checkpoints agree across the two logs and the files now.
  - the hold list (out/cmdr_post_hold.json, with its release records) is copied, hashed and re-checked like the logs (16k 7.2);
  - both process scans are saved (scans.json): every process's pid, ppid, create_time and name, and for python the facts the
    rule uses (argv readable / non-empty, the exact --headless token, known script names), never argv values. The rule
    judges only these facts, so the saved record gives the same verdict (16k 6).
On success the two drivers' own stop requests (cmdr_eval_driver.stop · cmdr_eval_driver_g0.stop), if their bytes are those seen
at the start, are moved to <dir>/stop_requests/ (the new instance would otherwise stop at once, 16h 4.2). Any other .stop
(e.g. hud_follow.stop) and a stop that appeared or changed during the freeze stay where they are and are listed (16i 4).
Usage: python handover_1400.py <pid of v3.2 base> <pid of v3.6 g0>
Test settings (env): HANDOVER_EV (eval folder), HANDOVER_ROOT (where the folder is made), HANDOVER_FAKE_PROCS (a JSON file:
a list of process snapshots, one per scan), HANDOVER_TEST_TOUCH (a file appended to just before the final check)."""
import hashlib
import json
import os
import shutil
import sys
import time

import psutil

EV = os.environ.get("HANDOVER_EV", "C:/isaac/ext/go2_rl_robotlab/_eval")
OUT = os.path.join(EV, "out")
ROOT = os.path.dirname(EV)
B = os.path.join(OUT, "branch")
PIN_FILES = ["q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py"]
RUN_FILES = ["meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy", "driver_stamp.json"]
SIDE = [".log", ".guard.json"]
LOGS = ["cmdr_eval_driver", "cmdr_eval_driver_g0"]
ISAAC = {"q_eval.py", "q_eval_cmdr.py", "gpu_guard.py", "branch_run.py", "unseen_driver.py", "train.py", "play.py"}
FAKE = json.load(open(os.environ["HANDOVER_FAKE_PROCS"], encoding="utf-8")) if os.environ.get("HANDOVER_FAKE_PROCS") else None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_or_none(p):
    return sha(p) if os.path.exists(p) else None


def pins_now():
    p = {f: sha(os.path.join(EV, f)) for f in PIN_FILES}
    code = json.load(open(os.path.join(B, "cmdr_s1042_off_u4000", "bundle.json"), encoding="utf-8"))["meta"]["code"]["files_sha256"]
    for rel, rec in code.items():
        p[rel] = sha(os.path.join(ROOT, rel))
        assert p[rel] == rec, rel
    return p


def snapshot():
    """one process snapshot; ancestry is walked inside it (pr.parents() per process took minutes and missed children)."""
    if FAKE is not None:
        return FAKE.pop(0) if len(FAKE) > 1 else FAKE[0]
    pm_fn = getattr(psutil, "_ppid_map", None)
    pm = pm_fn() if pm_fn else None
    snap = []
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            d = dict(pr.info)
        except psutil.NoSuchProcess:
            continue
        d["ppid"] = pm.get(d["pid"]) if pm is not None else None
        try:
            if (d.get("name") or "").lower().startswith(("python", "kit")):
                d["create_time"] = pr.create_time()
                if pm is None:
                    d["ppid"] = pr.ppid()
            else:
                d["create_time"] = None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            d["create_time"] = None
        snap.append(d)
    return snap


def facts(p):
    """16k 6: the parts of one process row the rule uses, with no argv values (names of known scripts only)."""
    n = (p.get("name") or "").lower()
    d = {"pid": p.get("pid"), "ppid": p.get("ppid"), "create_time": p.get("create_time"), "name": p.get("name")}
    if n.startswith("python"):
        c = p.get("cmdline")
        d["argv_readable"] = c is not None
        d["argv_nonempty"] = bool(c)
        d["headless_exact"] = bool(c) and "--headless" in c  # the exact token; --headless=false is not it
        d["matched_scripts"] = sorted({os.path.basename(x).lower() for x in (c or [])
                                       if os.path.basename(x).lower() in ISAAC or os.path.basename(x).lower().startswith("cmdr_eval_driver")})
    return d


def judge(rows, old, me):
    """the freeze rule, applied to facts() rows: used on the live snapshot and again on the saved record (16k 6)."""
    by = {p["pid"]: p for p in rows}

    def descends_from_old(p):
        cur, seen = p, set()
        while cur is not None and cur["pid"] not in seen:
            seen.add(cur["pid"])
            par = by.get(cur.get("ppid"))
            if par is None or (par.get("create_time") or 0) > (cur.get("create_time") or 0):
                return cur.get("ppid") in old  # a parent that is gone: only its pid is left
            if par["pid"] in old:
                return True
            cur = par
        return False

    alive = []
    for info in rows:
        if info["pid"] == me:
            continue
        if info["pid"] in old:
            alive.append({"reason": "old driver", "pid": info["pid"]})
            continue
        if descends_from_old(info):
            alive.append({"reason": "descendant of an old driver", "pid": info["pid"]})
            continue
        n = (info.get("name") or "").lower()
        if n.startswith("python"):
            if not info.get("argv_nonempty"):
                alive.append({"reason": "python with unreadable or empty argv", "pid": info["pid"]})
            elif info.get("headless_exact") or info.get("matched_scripts"):
                alive.append({"reason": "isaac-like python", "pid": info["pid"], "headless": info.get("headless_exact"),
                              "scripts": info.get("matched_scripts")})
        elif n.startswith("kit"):
            alive.append({"reason": "kit", "pid": info["pid"]})
    return alive


def alive_in(snap, old):
    return judge([facts(p) for p in snap], old, os.getpid())


def scan_record(snap, old, t0):
    """16j 9.5 / 16k 6: every process (pid, ppid, create_time, name); python rows add the rule's facts, no argv values.
    The record is judged again from itself; rejudge_equal says whether that gives the live verdict."""
    rows = [facts(p) for p in snap]
    live = judge(rows, old, os.getpid())
    return {"t_start": t0, "t_end": time.strftime("%Y-%m-%d %H:%M:%S"), "scanner_pid": os.getpid(), "old_pids": old,
            "rule_sha256": sha(os.path.abspath(__file__)), "n_processes": len(rows), "processes": rows, "alive": live,
            "rejudge_equal": judge(json.loads(json.dumps(rows)), old, os.getpid()) == live}


TARGET_STOPS = [f"{n}.stop" for n in LOGS]


def main(old):
    problems = []
    stops0 = {f: sha(os.path.join(OUT, f)) for f in TARGET_STOPS if os.path.exists(os.path.join(OUT, f))}
    hold0 = sha_or_none(os.path.join(OUT, "cmdr_post_hold.json"))  # 16l 5.2: absent at the start is recorded too
    t0 = time.strftime("%Y-%m-%d %H:%M:%S")
    s0 = snapshot()
    scans = [scan_record(s0, old, t0)]
    a0 = scans[0]["alive"]
    if a0:
        problems.append({"alive at start": a0})
    stamp = time.strftime("%Y%m%d_%H%M%S")
    H = os.path.join(os.environ.get("HANDOVER_ROOT", OUT), f"handover_{stamp}")
    os.makedirs(H)
    copies = {}
    for name in LOGS:
        for ext in (".json", ".out", ".attempt.json"):
            src = os.path.join(OUT, name + ext)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(H, name + ext))
                copies[name + ext] = sha(src)
    # 16m 5: the drivers' stdout under the names the runs really wrote (cmdr_eval_driver_v37.out, ..._g0_v37.out), not only
    # <LOGS name>.out. Same place and key as the other copies, so the copy and end re-hash checks below cover them too.
    for f in sorted(os.listdir(OUT)):
        if f.startswith("cmdr_eval_driver") and f.endswith(".out") and f not in copies:
            shutil.copy2(os.path.join(OUT, f), os.path.join(H, f))
            copies[f] = sha(os.path.join(OUT, f))
    if os.path.exists(os.path.join(OUT, "cmdr_post_hold.json")):  # 16k 7.2: the hold list and its releases are part of the bundle
        shutil.copy2(os.path.join(OUT, "cmdr_post_hold.json"), os.path.join(H, "cmdr_post_hold.json"))
        copies["cmdr_post_hold.json"] = sha(os.path.join(OUT, "cmdr_post_hold.json"))
    # 16l 5.3: what a release depends on travels with the bundle: the held original's stamp and the release evidence
    deps = {}
    hold_copy = os.path.join(H, "cmdr_post_hold.json")
    try:
        hold_obj = json.loads(open(hold_copy, "rb").read().decode("utf-8")) if os.path.exists(hold_copy) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        hold_obj = None
        problems.append({"hold list unreadable": "cmdr_post_hold.json"})
    for t, e in (hold_obj or {}).items():
        if not isinstance(e, dict):
            problems.append({"hold entry not a record": t})
            continue
        src = os.path.join(OUT, e.get("handover") or "_no_handover_", "stamps", t + ".json")
        if sha_or_none(src) != e.get("stamp_sha256"):
            problems.append({"held original stamp not found by its hash": t})
        else:
            os.makedirs(os.path.join(H, "held_stamps"), exist_ok=True)
            shutil.copy2(src, os.path.join(H, "held_stamps", t + ".json"))
            deps[f"held_stamps/{t}.json"] = {"from": src, "sha256": e["stamp_sha256"]}
        rel = e.get("released")
        if isinstance(rel, dict) and rel.get("evidence"):
            if sha_or_none(rel["evidence"]) != rel.get("evidence_sha256"):
                problems.append({"release evidence missing or not the recorded bytes": t})
            else:
                os.makedirs(os.path.join(H, "evidence"), exist_ok=True)
                shutil.copy2(rel["evidence"], os.path.join(H, "evidence", t + ".json"))
                deps[f"evidence/{t}.json"] = {"from": rel["evidence"], "sha256": rel["evidence_sha256"]}
    for rel_p, d in deps.items():
        if sha_or_none(os.path.join(H, rel_p)) != d["sha256"]:
            problems.append({"dependency copy differs": rel_p})
    logs = {name: json.load(open(os.path.join(H, name + ".json"), encoding="utf-8")) for name in LOGS}
    valid = {t for d in logs.values() for t, v in d.get("matrix", {}).items() if v == "valid"}
    man = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "old_pids": old, "script_sha256": sha(os.path.abspath(__file__)),
           "runs": {}, "ckpt": {}, "pins_now": pins_now(), "valid_runs": len(valid)}
    tags = sorted({r["tag"] for d in logs.values() for r in d.get("runs", []) if isinstance(r, dict) and r.get("tag")} | valid)
    missing_valid = []
    for t in tags:
        e = {f: sha_or_none(os.path.join(OUT, t, f)) for f in RUN_FILES}
        e.update({ext: sha_or_none(os.path.join(OUT, t + ext)) for ext in SIDE})
        e["_valid_in_log"] = t in valid
        miss = [k for k, v in e.items() if v is None]
        if miss:
            e["_missing"] = miss
            if t in valid:
                missing_valid.append({"tag": t, "missing": miss})
        sp = os.path.join(OUT, t, "driver_stamp.json")
        if e["driver_stamp.json"]:  # 16g 4: the stamp as it was before v3.7 re-validates and rewrites it
            os.makedirs(os.path.join(H, "stamps"), exist_ok=True)
            shutil.copy2(sp, os.path.join(H, "stamps", t + ".json"))
            if sha(os.path.join(H, "stamps", t + ".json")) != e["driver_stamp.json"]:
                problems.append({"stamp copy differs": t})
        man["runs"][t] = e
    if missing_valid:
        problems.append({"valid runs with missing files": missing_valid})
    for name, d in logs.items():
        for m, c in d.get("ckpt", {}).items():
            now = sha_or_none(c["path"])
            man["ckpt"].setdefault(m, {"path": c["path"], "now": now})[name] = c.get("sha256")
            if c.get("sha256") != now:
                problems.append({"ckpt": m, "log": name, "logged": c.get("sha256"), "now": now})
        if d.get("pins") != man["pins_now"]:
            problems.append({"pins differ": name, "files": sorted(k for k in set(d.get("pins", {})) | set(man["pins_now"])
                                                                  if d.get("pins", {}).get(k) != man["pins_now"].get(k))})
    for f, h in copies.items():
        if sha(os.path.join(H, f)) != h:
            problems.append({"copy differs": f})
    if os.environ.get("HANDOVER_TEST_TOUCH"):
        with open(os.environ["HANDOVER_TEST_TOUCH"], "ab") as fh:
            fh.write(b" ")
    # 16h 4.1: the originals and the process list once more, after everything was hashed
    changed = [f for f, h in copies.items() if sha_or_none(os.path.join(OUT, f)) != h]
    if sha_or_none(os.path.join(OUT, "cmdr_post_hold.json")) != hold0 and "cmdr_post_hold.json" not in changed:
        changed.append("cmdr_post_hold.json (appeared, changed or disappeared)")
    changed += [f"release dependency {d['from']}" for d in deps.values() if sha_or_none(d["from"]) != d["sha256"]]
    for t, e in man["runs"].items():
        for f in RUN_FILES:
            if e[f] is not None and sha_or_none(os.path.join(OUT, t, f)) != e[f]:
                changed.append(f"{t}/{f}")
        for ext in SIDE:
            if e[ext] is not None and sha_or_none(os.path.join(OUT, t + ext)) != e[ext]:
                changed.append(t + ext)
    for m, c in man["ckpt"].items():
        if sha_or_none(c["path"]) != c["now"]:
            changed.append(f"checkpoint {m}")
    if pins_now() != man["pins_now"]:
        changed.append("pins")
    if changed:
        problems.append({"changed during the freeze": changed[:20], "n": len(changed)})
    t1 = time.strftime("%Y-%m-%d %H:%M:%S")
    s1 = snapshot()
    scans.append(scan_record(s1, old, t1))
    a1 = scans[1]["alive"]
    if not all(x["rejudge_equal"] for x in scans):
        problems.append({"saved scan does not reproduce the verdict": [x["t_start"] for x in scans if not x["rejudge_equal"]]})
    if a1:
        problems.append({"alive at the end": a1})
    json.dump(scans, open(os.path.join(H, "scans.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    man["scans_sha256"] = sha(os.path.join(H, "scans.json"))
    man["copies_sha256"] = copies
    man["release_deps"] = deps
    man["problems"] = problems
    man["status"] = "complete" if not problems else "failed"
    man["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    # 16i 4: only the two drivers' own stop requests, only the bytes seen at the start; any other .stop is listed, kept
    man["stop_requests_other_kept"] = sorted(f for f in os.listdir(OUT) if f.endswith(".stop") and f not in TARGET_STOPS)
    man["stop_requests_new_kept"] = sorted(f for f in TARGET_STOPS if os.path.exists(os.path.join(OUT, f)) and f not in stops0)
    if not problems:  # 16h 4.2: the old stop requests are fulfilled; keep them here so the new instances can start
        moved = []
        for f, h0 in sorted(stops0.items()):
            p = os.path.join(OUT, f)
            if sha_or_none(p) != h0:
                man.setdefault("stop_requests_changed_kept", []).append(f)
                continue
            os.makedirs(os.path.join(H, "stop_requests"), exist_ok=True)
            shutil.move(p, os.path.join(H, "stop_requests", f))
            moved.append(f)
        man["stop_requests_moved"] = moved
    json.dump(man, open(os.path.join(H, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"dir": H, "status": man["status"], "runs": len(tags), "valid": len(valid),
                      "not_valid_with_missing": sum(1 for e in man["runs"].values() if e.get("_missing") and not e["_valid_in_log"]),
                      "ckpt": len(man["ckpt"]), "stop_requests_moved": man.get("stop_requests_moved"), "stop_requests_other_kept": man.get("stop_requests_other_kept"),
                      "manifest_sha256": sha(os.path.join(H, "manifest.json")), "problems": problems}, ensure_ascii=False, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main([int(x) for x in sys.argv[1:]]))
