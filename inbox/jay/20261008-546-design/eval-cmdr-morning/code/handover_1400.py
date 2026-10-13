"""14:00 hand-over freeze (lead 10/13, VERIFY-astra-16d 6 / 16f 5). Reads the live eval tree, writes only out/handover_<stamp>/.
Exit 0 only when: no process of the old drivers (given pids) or their descendants is alive, no Isaac-like python is alive,
the copies re-hash equal to the originals, and pins / checkpoints agree across the two logs and the files now.
Usage: python handover_1400.py <pid of v3.2 base> <pid of v3.6 g0>"""
import hashlib
import json
import os
import shutil
import sys
import time

import psutil

EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
OUT = os.path.join(EV, "out")
ROOT = os.path.dirname(EV)
B = os.path.join(OUT, "branch")
PIN_FILES = ["q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py"]
RUN_FILES = ["meta.json", "cells.json", "episodes.csv", "traj.npz", "driver_stamp.json"]
LOGS = ["cmdr_eval_driver", "cmdr_eval_driver_g0"]
ISAAC = {"q_eval.py", "q_eval_cmdr.py", "gpu_guard.py", "branch_run.py", "unseen_driver.py", "train.py", "play.py"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pins_now():
    p = {f: sha(os.path.join(EV, f)) for f in PIN_FILES}
    code = json.load(open(os.path.join(B, "cmdr_s1042_off_u4000", "bundle.json"), encoding="utf-8"))["meta"]["code"]["files_sha256"]
    for rel, rec in code.items():
        p[rel] = sha(os.path.join(ROOT, rel))
        assert p[rel] == rec, rel
    return p


problems = []
old = [int(x) for x in sys.argv[1:]]
snap = []  # one snapshot; ancestry is walked inside it (pr.parents() per process took minutes and missed short-lived children)
pm = psutil._ppid_map()  # one call (asking each process for ppid took 55 s a scan here)
for pr in psutil.process_iter(["pid", "name", "cmdline"]):
    try:
        d = dict(pr.info)
    except psutil.NoSuchProcess:
        continue
    d["ppid"] = pm.get(d["pid"])
    try:
        d["create_time"] = pr.create_time() if (d.get("name") or "").lower().startswith(("python", "kit")) else None
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        d["create_time"] = None
    snap.append(d)
by = {p["pid"]: p for p in snap}


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
for info in snap:
    if info["pid"] in old:
        alive.append(("old driver", info["pid"]))
        continue
    if descends_from_old(info):
        alive.append(("descendant of an old driver", info["pid"]))
        continue
    n = (info["name"] or "").lower()
    c = info["cmdline"]
    if n.startswith("python"):
        if c is None:
            alive.append(("python with unreadable argv", info["pid"]))
        elif "--headless" in c or any(os.path.basename(x).lower() in ISAAC or os.path.basename(x).lower().startswith("cmdr_eval_driver") for x in c):
            alive.append(("isaac-like python", info["pid"], " ".join(os.path.basename(x) for x in c[:3])))
    elif n.startswith("kit"):
        alive.append(("kit", info["pid"]))
if alive:
    problems.append({"alive": alive})

stamp = time.strftime("%Y%m%d_%H%M%S")
H = os.path.join(os.environ.get("HANDOVER_ROOT", OUT), f"handover_{stamp}")  # HANDOVER_ROOT: dry run elsewhere
os.makedirs(H)
copies = {}
for name in LOGS:
    for ext in (".json", ".out", ".attempt.json"):
        src = os.path.join(OUT, name + ext)
        if os.path.exists(src):
            dst = os.path.join(H, name + ext)
            shutil.copy2(src, dst)
            copies[name + ext] = sha(src)
logs = {name: json.load(open(os.path.join(H, name + ".json"), encoding="utf-8")) for name in LOGS}

man = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "old_pids": old, "runs": {}, "ckpt": {}, "pins_now": pins_now()}
tags = sorted({r["tag"] for d in logs.values() for r in d.get("runs", [])})
for t in tags:
    e = {}
    for f in RUN_FILES:
        p = os.path.join(OUT, t, f)
        e[f] = sha(p) if os.path.exists(p) else None
    for ext in (".log", ".guard.json"):
        p = os.path.join(OUT, t + ext)
        e[ext] = sha(p) if os.path.exists(p) else None
    sp = os.path.join(OUT, t, "driver_stamp.json")
    if os.path.exists(sp):  # VERIFY-astra-16g 4: the stamp as it was before v3.7 re-validates and rewrites it
        os.makedirs(os.path.join(H, "stamps"), exist_ok=True)
        shutil.copy2(sp, os.path.join(H, "stamps", t + ".json"))
        if sha(os.path.join(H, "stamps", t + ".json")) != e["driver_stamp.json"]:
            problems.append({"stamp copy differs": t})
    man["runs"][t] = e
for name, d in logs.items():
    for m, c in d.get("ckpt", {}).items():
        now = sha(c["path"]) if os.path.exists(c["path"]) else None
        man["ckpt"].setdefault(m, {"path": c["path"], "now": now})[name] = c.get("sha256")
        if c.get("sha256") != now:
            problems.append({"ckpt": m, "log": name, "logged": c.get("sha256"), "now": now})
    if d.get("pins") != man["pins_now"]:
        problems.append({"pins differ": name, "files": sorted(k for k in set(d.get("pins", {})) | set(man["pins_now"])
                                                              if d.get("pins", {}).get(k) != man["pins_now"].get(k))})
for f, h in copies.items():
    if sha(os.path.join(H, f)) != h:
        problems.append({"copy differs": f})
man["copies_sha256"] = copies
man["problems"] = problems
json.dump(man, open(os.path.join(H, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
missing = sum(1 for e in man["runs"].values() if any(v is None for v in e.values()))
print(json.dumps({"dir": os.path.relpath(H, EV), "runs": len(tags), "runs_with_a_missing_file": missing, "ckpt": len(man["ckpt"]),
                  "manifest_sha256": sha(os.path.join(H, "manifest.json")), "problems": problems}, ensure_ascii=False, indent=1))
sys.exit(1 if problems else 0)
