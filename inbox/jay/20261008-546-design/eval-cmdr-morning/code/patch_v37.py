"""cmdr_eval_driver_v36.py -> cmdr_eval_driver_v37.py (lead 10/13, VERIFY-astra-16f 3.1 / 3.2 / 3.3 / 4). Anchors exactly once."""
import sys

s = open(sys.argv[1], encoding="utf-8").read()


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"anchor count {n}: {old[:80]!r}"
    s = s.replace(old, new)


rep('''# Usage: python cmdr_eval_driver_v36.py --gpu 1 --plan base --order 24first --until "2026-10-13 20:00"
#        python cmdr_eval_driver_v36.py --gpu 0 --plan remeasure --log cmdr_eval_driver_g0 --until "2026-10-13 20:00"''',
    '''# v3.7 (10/13 12:42, VERIFY-astra-16f 3.1 / 3.2 / 3.3 / 4; (t) and (u) are replaced):
#   (v) USD conversion slot. Start spacing did not remove the cause: the converter names the folder by the second and a
#       random number fixed per eval seed (973 logs at 12:20: seed 1000 -> 7028, 1001 -> 960, 1002 -> 8535,
#       1003 -> 8148, 1004 -> 6899), creates it with exist_ok=True and has no lock, and the delay from start to
#       conversion is not bounded. Now a child is launched only while this driver holds the OS lock
#       out/isaac_convert.lock, and the lock is held until the child's log has the line Isaac Lab prints after the
#       scene (robot USD included) is built, "[INFO]: Time taken for scene creation", or the child has exited. In 941
#       of the 943 logs in out/ with a USD folder that line comes after every URDF importer line and every USD path
#       line (the two others are gate_*.log of another script); the first USD path line is NOT a done signal (it
#       comes while the importer still works on the rear feet). No launch while a foreign Isaac process is alive:
#       a cmdr_eval_driver that is not v3.7, an unseen / training launcher, a python process running an Isaac script
#       or with --headless that does not descend from a v3.7 driver, kit, or a python process whose argv cannot be
#       read. The process list asks every process only for name and argv; parent ids come from one call and create
#       times only from python / kit processes (ppid per process took 55 s a scan on this machine). The evaluator and
#       the converter are not changed (usd_dir is not set, so Python's random is consumed
#       exactly as before and the known-answer comparison stays valid).
#   (w) deadline, stop file, pins and the job's checkpoint are checked before every try, on every pass of the slot
#       wait and once more with the slot held right before the child starts. Nothing is launched after one of them
#       fires; the active job and the queue go to the exit record (stop file: exit 7, deadline: exit 2, both
#       end_kind incomplete; attempt file stopped).
#   (x) a log with the robot root reference failure ("</World/envs/env_0/Robot>: Unresolved reference") is retried
#       whatever the exit code and whether or not there is a Traceback; it is recorded as "root reference unresolved
#       (USD temp folder collision suspected)", not as a proven collision. When the tries run out the run is an
#       infrastructure failure (infra_fail on the try and in LOG["infra_fail"]), never a policy result.
#   (y) validate() also needs: no root reference failure, exactly one USD folder named in the log, the scene-creation
#       line, no importer / USD path line after it, and no other log in out/ or out/attempts/ naming the same USD
#       folder. A run that shared its folder (11:38: cq_on24000_flat_stand_on_s1000 with the v3.5 start test 2b) is
#       therefore not reused and is measured again.
#   (z) a run measured again keeps its earlier result folder (stamp included) under out/attempts/<tag>.dir.<mtime>.<pid>.
#       Moved files and folders never replace earlier ones under out/attempts/ (a numbered suffix when the name is taken;
#       v3.6 could overwrite a try's log when two tries of one name ended within the same second).
#   (o2) every stamp and run record says where its output hashes come from (VERIFY-astra-16g 4): origin
#       "hashed-at-collection" (measured by v3.3+ with hashes) or "legacy-origin revalidated" (a v3.2 run whose hashes
#       are first taken at this re-validation; they fix the bytes from now on, not before). A reused stamp also keeps
#       prev_stamp_sha256, revalidated_by (this attempt) and revalidated_at; the origin is never upgraded later.
# Usage: python cmdr_eval_driver_v37.py --gpu 1 --plan base --order 24first --until "2026-10-13 20:00"
#        python cmdr_eval_driver_v37.py --gpu 0 --plan remeasure --log cmdr_eval_driver_g0 --until "2026-10-13 20:00"''')

rep('''import math
import os
''', '''import math
import os
import re
''')
rep('VERSION = "3.6"', 'VERSION = "3.7"')

i = s.index("SPACING_S = 30\n")
j = s.index("def q(script, tag, model_path,")
assert s.count("SPACING_S = 30\n") == 1 and s.count("def q(script, tag, model_path,") == 1
NEW = r'''PARTICIPANT = "cmdr_eval_driver_v37.py"
CONVERT_LOCK = "isaac_convert.lock"
CONVERT_DONE = "[INFO]: Time taken for scene creation"
ROOT_REF = "</World/envs/env_0/Robot>: Unresolved reference"
USD_RE = re.compile(r"IsaacLab.usd_(\d{8}_\d{6}_\d+)")
IMPORTER = "isaacsim.asset.importer.urdf"
ISAAC_SCRIPTS = {"q_eval.py", "q_eval_cmdr.py", "gpu_guard.py", "branch_run.py", "unseen_driver.py", "train.py", "play.py"}
POPEN = subprocess.Popen


def _procs_tree():
    """one snapshot: name and argv of every process, parent ids from one system call, create time only for python and kit
    processes. Asking every process for ppid through process_iter took 55 s on this machine (12:50); _ppid_map() 0.05 s."""
    pm_fn = getattr(psutil, "_ppid_map", None)
    pm = pm_fn() if pm_fn else None
    out = []
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            d = dict(pr.info)
        except psutil.NoSuchProcess:
            continue
        n = (d.get("name") or "").lower()
        d["ppid"], d["create_time"] = (pm.get(d["pid"]) if pm is not None else None), None
        if n.startswith("python") or n.startswith("kit"):
            try:
                d["create_time"] = pr.create_time()
                if pm is None:
                    d["ppid"] = pr.ppid()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        out.append(d)
    return out


def _isaac_like(c):
    b = [os.path.basename(x).lower() for x in c]
    return "--headless" in c or any(x in ISAAC_SCRIPTS for x in b) or any(x.startswith("cmdr_eval_driver") and x.endswith(".py") for x in b)


def foreign_isaac(procs=None):
    """(v) Isaac-related processes that do not take part in the conversion slot: pids, or 'unknown:<pid>' for a python
    process whose argv cannot be read. A process takes part when it is a v3.7 driver or descends from one (parent links
    are trusted only when the parent was created no later than the child, so a reused pid is not a parent)."""
    procs = procs if procs is not None else _procs_tree()
    by = {p["pid"]: p for p in procs}
    out = []
    for p in procs:
        name = (p.get("name") or "").lower()
        if p["pid"] == os.getpid():
            continue
        if name.startswith("kit") or name.startswith("isaac-sim"):
            out.append(p["pid"])
            continue
        if not name.startswith("python"):
            continue
        c = p.get("cmdline")
        if c is None:
            out.append(f"unknown:{p['pid']}")
            continue
        if not _isaac_like(c):
            continue
        cur, seen, part = p, set(), False
        while cur is not None and cur["pid"] not in seen:
            seen.add(cur["pid"])
            if any(os.path.basename(x).lower() == PARTICIPANT for x in (cur.get("cmdline") or [])):
                part = True
                break
            par = by.get(cur.get("ppid"))
            if par is None or par.get("create_time") is None or cur.get("create_time") is None \
                    or par["create_time"] > cur["create_time"]:
                break
            cur = par
        if not part:
            out.append(p["pid"])
    return out


def gate(where, ck=None):
    """(w) deadline, stop file, pins and the job's checkpoint; exits before anything is launched (VERIFY-astra-16f 3.2)."""
    if time.time() > DEADLINE:
        LOG["stopped"] = f"deadline before {where}"
        save()
        say(f"DEADLINE before {where}")
        sys.exit(2)
    if stop_requested():
        LOG["stopped"] = f"stop file before {where}"
        save()
        say(f"STOP FILE before {where}")
        sys.exit(7)
    if pins() != P0:
        LOG["stopped"] = f"pins changed before {where}"
        save()
        say("PINS CHANGED: stop")
        sys.exit(4)
    if ck is not None and sha(MODELS[ck][0]) != LOG["ckpt"][ck]["sha256"]:
        LOG["stopped"] = f"checkpoint {ck} changed before {where}"
        save()
        say(f"CHECKPOINT CHANGED {ck}: stop")
        sys.exit(5)


def convert_slot(where, ck=None, sleep=time.sleep):
    """(v) returns the open, locked out/isaac_convert.lock once no foreign Isaac process is alive; gate() on every pass."""
    import msvcrt
    note = None
    while True:
        gate(where, ck)
        f = open(os.path.join(OUT, CONVERT_LOCK), "a+b")
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            sleep(2)
            continue
        fo = foreign_isaac()
        if not fo:
            return f
        release_slot(f)
        if note is None or time.time() - note >= 300:
            note = time.time()
            LOG["slot_wait"] = {"t": time.strftime("%H:%M:%S"), "where": where, "foreign": fo[:8]}
            save()
            say(f"SLOT WAIT {where}: foreign Isaac processes {fo[:4]}")
        sleep(5)


def release_slot(f):
    import msvcrt
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    f.close()


def hold_until_converted(name, p, sleep=time.sleep):
    """(v) ('marker' | 'exit', seconds): wait until the child's log has the scene-creation line or the child has exited."""
    t0 = time.time()
    lp = os.path.join(OUT, f"{name}.log")
    while True:
        if p.poll() is not None:
            return "exit", round(time.time() - t0, 1)
        try:
            with open(lp, encoding="utf-8", errors="replace") as fh:
                if CONVERT_DONE in fh.read():
                    return "marker", round(time.time() - t0, 1)
        except FileNotFoundError:
            pass
        sleep(1)


def _log_text(name):
    try:
        with open(os.path.join(OUT, f"{name}.log"), encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def root_ref_failed(name):
    return ROOT_REF in _log_text(name)


def usd_dirs_of(name):
    return sorted({m.group(1) for m in USD_RE.finditer(_log_text(name))})


USD_IDX = {}


def usd_index():
    """(y) USD folder -> the log files in out/ (*.log) and out/attempts/ (*.log.*) that name it. A file is read again
    only when its size or mtime changed."""
    import glob
    seen = set()
    for f in glob.glob(os.path.join(OUT, "*.log")) + glob.glob(os.path.join(OUT, "attempts", "*.log.*")):
        rel = os.path.relpath(f, OUT).replace("\\", "/")
        try:
            st = os.stat(f)
        except FileNotFoundError:
            continue
        seen.add(rel)
        key = (st.st_mtime_ns, st.st_size)
        if rel not in USD_IDX or USD_IDX[rel][0] != key:
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    USD_IDX[rel] = (key, frozenset(m.group(1) for m in USD_RE.finditer(fh.read())))
            except FileNotFoundError:
                continue
    for rel in list(USD_IDX):
        if rel not in seen:
            del USD_IDX[rel]
    out = {}
    for rel, (_, ds) in USD_IDX.items():
        for d in ds:
            out.setdefault(d, set()).add(rel)
    return out


def usd_check(tag):
    """(y) '' when the run's robot asset came from its own, finished USD folder as far as the log can tell, else why."""
    L = _log_text(tag).splitlines()
    if any(ROOT_REF in x for x in L):
        return "robot root reference unresolved (infrastructure; USD temp folder collision suspected)"
    dirs = sorted({m.group(1) for x in L for m in USD_RE.finditer(x)})
    if len(dirs) != 1:
        return f"USD folders named in the log: {len(dirs)}"
    mk = next((i for i, x in enumerate(L) if CONVERT_DONE in x), None)
    if mk is None:
        return "no scene-creation line"
    if any(USD_RE.search(x) or IMPORTER in x for x in L[mk + 1:]):
        return "USD conversion output after the scene-creation line"
    others = sorted(r for r in usd_index().get(dirs[0], ()) if r != f"{tag}.log")
    if others:
        return f"USD temp folder usd_{dirs[0]} shared with {others[:3]}"
    return ""


def _free(p):
    """p, or p.1, p.2 ...: earlier evidence is never replaced (two tries of one name can end within the same second)."""
    q_, i_ = p, 0
    while os.path.exists(q_):
        i_ += 1
        q_ = f"{p}.{i_}"
    return q_


def preserve_result(tag):
    """(z) the earlier result folder of a run measured again goes to out/attempts/ (stamp included)."""
    d = os.path.join(OUT, tag)
    if not os.path.isdir(d):
        return None
    os.makedirs(os.path.join(OUT, "attempts"), exist_ok=True)
    dst = _free(os.path.join(OUT, "attempts", f"{tag}.dir.{time.strftime('%m%d%H%M%S', time.localtime(os.path.getmtime(d)))}.{os.getpid()}"))
    os.replace(d, dst)
    return os.path.relpath(dst, OUT).replace("\\", "/")


def guarded(name, cmd, tries=4, wait_s=300, ck=None):
    rc = None
    for k in range(1, tries + 1):
        gate(f"{name} try {k}", ck)
        kept = []
        for ext in (".log", ".guard.json"):  # an earlier try of this name keeps its evidence
            src = os.path.join(OUT, name + ext)
            if os.path.exists(src):
                os.makedirs(os.path.join(OUT, "attempts"), exist_ok=True)
                dst = _free(os.path.join(OUT, "attempts", f"{name}{ext}.{time.strftime('%m%d%H%M%S', time.localtime(os.path.getmtime(src)))}.{os.getpid()}"))
                os.replace(src, dst)
                kept.append(os.path.relpath(dst, OUT))
        lk = convert_slot(f"{name} try {k}", ck)
        try:
            gate(f"{name} try {k} launch", ck)  # with the slot held, right before the child starts
            t0 = time.time()
            p = POPEN([PY, "gpu_guard.py", "--gpu", GPU, "--min_free_mib", "4096", "--log", f"out/{name}.log",
                       "--summary", f"out/{name}.guard.json", "--"] + cmd, cwd=HERE, env=ENV)
            rel = hold_until_converted(name, p)
        finally:
            release_slot(lk)
        rc = p.wait()
        tr = {"try": k, "rc": rc, "s": round(time.time() - t0), "earlier_moved": kept,
              "slot": {"released_by": rel[0], "held_s": rel[1]}, "usd_dir": usd_dirs_of(name)}
        TRIES.setdefault(name, []).append(tr)
        say(f"RUN {name} try {k} EXIT {rc} {time.time() - t0:.0f}s · slot {rel[0]} {rel[1]}s · usd {tr['usd_dir']}")
        if rc == 0 and py_traceback(name):
            say(f"  {name}: exit 0 but a Python Traceback is in the log; counted as error 1 (Isaac Kit exits 0 after an uncaught exception)")
            rc = 1
        if rc != 99 and root_ref_failed(name):  # (x) whatever the exit code and with or without a Traceback
            tr["root_ref_unresolved"] = True
            if k < tries:
                say(f"ROBOT ROOT REFERENCE UNRESOLVED {name} (USD temp folder collision suspected, not proven): retry")
                continue
            tr["infra_fail"] = True
            LOG.setdefault("infra_fail", []).append(name)
            say(f"ROBOT ROOT REFERENCE UNRESOLVED {name}: tries used up, infrastructure failure")
            return (rc or 1), k
        if rc == 0:
            return 0, k
        if rc == 99:
            say(f"GUARD STOP {name}: free < 4096 MiB on GPU {GPU}, waiting {wait_s}s")
            time.sleep(wait_s)
        else:
            return rc, k  # a real error is not retried
    return rc, tries


'''
s = s[:i] + NEW + s[j:]

rep('''        why = log_done(tag, len(cells) * episodes)
        if why:
            return why
''', '''        why = log_done(tag, len(cells) * episodes)
        if why:
            return why
        why = usd_check(tag)  # (y)
        if why:
            return why
''')

rep('''    prev = old_stamp(tag)
''', '''    prev = old_stamp(tag)
    moved = None
    sp_ = os.path.join(OUT, tag, "driver_stamp.json")
    prev_sha = sha(sp_) if os.path.exists(sp_) else None  # (o2) the stamp this run had before, kept by hash
''')
rep('''                              "out_sha256": rec["out_sha256"], "prev_stamp_t": prev.get("t")})''',
    '''                              "out_sha256": rec["out_sha256"], "prev_stamp_t": prev.get("t"), **origin})''')
rep('''        ACTIVE[0].update(attempt=attempt, stage="run")
        rc, k = guarded(tag, q("q_eval_cmdr.py", tag, path, fam, cell, 100, noise, seed))''',
    '''        ACTIVE[0].update(attempt=attempt, stage="run")
        moved = preserve_result(tag)  # (z)
        rc, k = guarded(tag, q("q_eval_cmdr.py", tag, path, fam, cell, 100, noise, seed), ck=m)''')
rep('''           "gpu": GPU, "tries": [] if reused else list(TRIES.get(tag, []))}''',
    '''           "gpu": GPU, "tries": [] if reused else list(TRIES.get(tag, [])), "usd_dir": usd_dirs_of(tag)}
    # (o2) where the output hashes come from (VERIFY-astra-16g 4): measured by this driver family with hashes from the
    # start, or a v3.2 run whose hashes are first taken now when it is re-validated. Never upgraded on a later reuse.
    origin = {"origin": "hashed-at-collection"} if not reused else {
        "origin": prev.get("origin") or ("legacy-origin revalidated" if "stamp_version" not in prev else "hashed-at-collection"),
        "prev_stamp_sha256": prev_sha, "revalidated_by": ATTEMPT, "revalidated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    rec["origin"] = origin["origin"]
    if moved:
        rec["earlier_result_moved"] = moved
    if any(t.get("infra_fail") for t in rec["tries"]):
        rec["infra_fail"] = True''')

rep('''    LOG["exit_code"] = code
    LOG["end_kind"] = "error"''', '''    LOG["exit_code"] = code
    LOG["end_kind"] = "incomplete" if code in (2, 7) else "error"  # (w) deadline / stop file before a launch''')

open(sys.argv[2], "w", encoding="utf-8").write(s)
print("ok", len(s))
