# CMD-R morning evaluation driver v2 (lead, 2026-10-13 00:10; plan VERIFY-astra-7 section 2, fixes VERIFY-astra-8).
# GPU 1 only, no training.
#   evaluator : q_eval_cmdr.py = q_eval.py @717325a7 + --train_yaml for branch checkpoints (exact parent params/env.yaml,
#               bundle hashes recorded) + loaded-iter check.
#   pins      : sha256 of the evaluator, metrics, post, guard and the six robot_lab / rsl_rl source files the branch
#               bundle records. Taken at start, re-checked before every run (a change stops the driver, exit 4), written
#               into every run folder (driver_stamp.json). A run counts as done only if its stamp has the current pins
#               and it passes validate(): exit 0 and guard not stopped, cells/meta/episodes/traj parse with the expected
#               shape, args, checkpoint sha256 and loaded iter, GPU 1 UUID, checks_pre / checks_run within limits, finite.
#   models    : parent E1 model_20000, off/on model_22000 and model_24000. A checkpoint is ready when its size and mtime
#               stayed the same over two looks at least 120 s apart; its sha256 is pinned then and re-checked before
#               every run. The on arm also needs a SAME bundle comparison for this pair (cmdr_bundle_compare.py v2).
#   runs      : one family x one cell x 100 episodes (100 envs), student, difficulty 0.5, heading hold 0, centre start.
#               Tag cq_<model>_<family>_<cell>_<noise>_s<seed>.
#   order     : (A) flat 11 cells, noise on, seed 1000  (B) flat stop03 fwd01 fwd02, noise on, seeds 1001-1004
#               (ASTRA 8 3: seed list fixed before results)  (C) other 7 training families, noise on, seed 1000
#               (D) flat 11 cells noise off, seed 1000. The first ready job in this order runs next.
#   pairing   : per (family, cell, noise, seed) group every run is compared with the group's first valid run on the
#               recorded initial state / DR / terrain / layout / device fingerprints and traj[0]. A mismatch marks the
#               run pair_fail (kept on disk, excluded from tables).
#   waits     : starts after the UNSEEN driver (a python process whose argv has unseen_driver.py) has exited.
# Every run is under gpu_guard.py --gpu 1 --min_free_mib 4096. Deadline is checked before every run.
# v3 (00:25, VERIFY-astra-8b): expected cell order follows the evaluator's own order (q_eval ALL_CELLS), episode IDs /
# family / cell per CSV row, T from the cell durations, finite traj (hag may be NaN) and cmd_hist, non-empty fingerprint
# dicts, both bundle hashes + contract + comparator version for the on arm, pins and deadline before every try and
# again before stamping, positive-reaction diagnostics recorded as warnings (not invalid). Every run uses
# --physx_small_buffers (GPU 1 headroom; same for all five models); test 2b checks it is bitwise equal to the default
# buffers on the flat training terrain. q_eval.py is pinned only for the known-answer tests.
# v3.1 (04:30): Isaac Kit exited 0 after the AssertionError in test 3 (wrong train_yaml refused, exit 0). A Python
# traceback in the run log now counts as error 1 in guarded() and as invalid in validate(); test 3 also requires that
# no cells.json / traj.npz was written.
# v3.2 (05:00, VERIFY-astra-14 9.2): validate() also needs the run log with the evaluator's own completion line
# ("[Q-EVAL] done <tag> N <n> ") and finite run-time command errors (a NaN passed v3.1). On restart every reused run is
# validated again with these rules.
# v3.3 (10/13 09:58, VERIFY-astra-15 9.2 and 2(c) as the team lead confirmed it 01:10):
#   (1) --gpu 0|1 picks the device; validate() checks that GPU's UUID; gpu_guard watches that GPU.
#   (2) --plan base keeps the (A)-(D) job list. --order 24first moves the off24000 / on24000 jobs ahead of the others
#       (the final comparison is at 24000); inside each block the (A)-(D) order is unchanged.
#   (3) --plan remeasure: the n=100 screen at 24000 (on - off, seed 1000) over every family x cell x noise in the base
#       plan except the flat noise-on targets, which (B) already measures at n=500. A point estimate <= -5 pp queues
#       seeds 1001-1004 for off24000 and on24000 (n=500 with seed 1000). These groups never occur in the base plan,
#       so the two instances never share a pairing group. It reads the base instance's log, never writes it.
#   (4) attempt manifest: every run record carries an attempt id (gpu-pid-start) and the sha256 of meta.json /
#       cells.json / episodes.csv / traj.npz; the stamp keeps them, and a reused run must still match them. Stamps
#       from v3.2 have no hashes; they are re-validated and get hashes now.
#   (5) run-time command errors must lie in [0, 1e-6] (a negative max_abs passed v3.2, VERIFY-astra-15).
#   (6) the log is written atomically (tmp file + replace) so the other instance never reads half a file. Test
#       folders carry the GPU and the start time, so a restart does not overwrite earlier test evidence.
#   (7) at start every finished run with a good stamp is re-validated in one pass before any new run, so the
#       tables do not lose earlier runs while the restarted driver works through its order.
#   (8) GPU 0 is used only after the CMD-R training (branch_run.py) has exited.
# v3.4 (10/13 10:28, VERIFY-astra-16 6.1 / 6.2 / 8; v3.3 was never run):
#   (a) remeasure decides the screen and the end from ONE snapshot of the base log, and only ends when that snapshot
#       says ended / stopped AND no base writer process is alive (a restarted base keeps its old log on disk until
#       its re-validation pass is done, so an old "ended" must not end the remeasure). The last screen therefore
#       always sees the base's last pair (ASTRA 16 reproduced the v3.3 race on CPU).
#   (b) --log must differ from --base_log for remeasure; no second writer of the same log may be alive at start.
#   (c) at start, wait while a q_eval_cmdr.py run of one of this plan's own tags is still alive (an orphan of an
#       earlier driver), so one run folder never has two writers.
#   (d) GPU 0 only after an explicit end of the CMD-R pair: on-arm result.json, model_24000.pt, "NIGHT DONE" in the
#       night log, no branch_run.py, GPU 0 memory used < 3000 MiB, all true twice 60 s apart.
#   (e) the base keeps the previous log on disk until its re-validation pass has rebuilt the whole table, then writes
#       it at once (v3.3 wrote an empty matrix first). Stamps are written atomically; a broken or unreadable stamp
#       means "not reusable" (v3.3 crashed on it). Stamps from v3.3 on carry stamp_version and must carry hashes.
#   (f) every new run gets its own attempt id (driver attempt + job number); test folders carry seconds and pid.
#   (g) the end record says complete only when every planned job is valid (base) or every screen cell is measured
#       and every flagged group has both arms valid on seeds 1001-1004 (remeasure); otherwise the lists say what is
#       missing, invalid or not run. A failed start test writes stopped. The driver's own sha256 is in the log.
#   The main loops are functions so their control flow can be tested on CPU (test_v34.py).
# v3.5 (10/13 10:50, VERIFY-astra-16b 2 / 3; v3.4 was never run):
#   (h) every remeasure pass checks the deadline first; a base log that cannot be read is retried, but at the
#       deadline the driver stops and records the last good snapshot (time, hash) and why, complete = False.
#   (i) writer detection parses the other process's argv like argparse does (--log X, --log=X, unique prefixes) and
#       compares normalised absolute log paths (case, ./). Own instances also hold an OS lock on out/<log>.lock for
#       their whole life (a second v3.5 writer of the same log cannot start even if the process scan misses it).
#       Abbreviated options are refused for this script (allow_abbrev=False).
#   (j) the screen state is rebuilt from the current snapshot on every pass; cells that were present before and are
#       gone now are kept under "withdrawn" (time, base attempt, snapshot hash) and counted as unmeasured; queued
#       remeasure jobs of a cell that is no longer flagged are taken off the queue and listed under "dequeued" (runs
#       already done stay on disk and in the log). The end needs the same snapshot bytes twice in a row with no base
#       writer alive, and that snapshot fully screened and queued (an older v3.4 end record cannot end the remeasure).
#   (k) every way out (deadline, pins, checkpoint, test failure, refusal, exception) goes through one exit record:
#       stopped, exit code, pending / not_run, and the lists, written to the log; during the base re-validation pass
#       (old log still on disk) it goes to out/<log>.stopped.json instead, so the old table is kept.
#   (l) write_stamp retries a Windows sharing violation like save(); each guard retry is its own attempt: the earlier
#       try's log and guard summary are moved to out/attempts/ and the run record lists every try (k, rc, seconds).
#   (m) GPU 0 hand-over reads result.json: tag cmdr_s1042_on_u4000, cmdr on, final_state where = end and
#       label_next = 24000; the night log must have NIGHT DONE after "cmdr_s1042_on_u4000 EXIT 0"; model_24000.pt
#       has the checkpoint size; GPU memory used < 3000 MiB (3000 itself is refused).
# Usage: python cmdr_eval_driver_v35.py --gpu 1 --plan base --order 24first --until "2026-10-13 20:00"
#        python cmdr_eval_driver_v35.py --gpu 0 --plan remeasure --log cmdr_eval_driver_g0 --until "2026-10-13 20:00"
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
OUT = os.path.join(HERE, "out")
B = os.path.join(OUT, "branch")
E1 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
E2 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192"
E1_YAML = f"{E1}/params/env.yaml"
MODELS = {"p20000": (f"{E1}/model_20000.pt", 20000),
          "off22000": (f"{B}/cmdr_s1042_off_u4000/model_22000.pt", 22000),
          "off24000": (f"{B}/cmdr_s1042_off_u4000/model_24000.pt", 24000),
          "on22000": (f"{B}/cmdr_s1042_on_u4000/model_22000.pt", 22000),
          "on24000": (f"{B}/cmdr_s1042_on_u4000/model_24000.pt", 24000)}
CELLS = ["stop03", "fwd01", "fwd02", "stand", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
TARGETS = ["stop03", "fwd01", "fwd02"]
FAMILIES = ["flat", "obstacles", "rough_slope", "slope_up", "slope_down", "stairs_up", "stairs_down", "wave"]
EXT_SEEDS = [1001, 1002, 1003, 1004]
CKPT_BYTES = 26367183
PIN_FILES = ["q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py"]
# the evaluator keeps its own ALL_CELLS order whatever order --cells gives (q_eval_cmdr.py ALL_CELLS)
EVAL_ORDER = ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "fwd10", "back03", "left03", "right03", "yawL05", "yawR05"]
DUR_S = {"stand": 10.0, "stop03": 10.0}  # every other cell 20 s (q_eval_cmdr.py ALL_CELLS)
P0, DEADLINE = None, None


def in_eval_order(cells):
    return [c for c in EVAL_ORDER if c in cells]
ap = argparse.ArgumentParser(allow_abbrev=False)
ap.add_argument("--until", default="2026-10-13 14:00")
ap.add_argument("--gpu", type=int, choices=(0, 1), default=1)
ap.add_argument("--plan", choices=("base", "remeasure"), default="base")
ap.add_argument("--order", choices=("orig", "24first"), default="24first")
ap.add_argument("--log", default="cmdr_eval_driver", help="log name in out/ (no .json)")
ap.add_argument("--base_log", default="cmdr_eval_driver", help="the base instance's log, read by --plan remeasure")
args = ap.parse_args()
GPU = str(args.gpu)
GPU_UUID = {"0": "c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b", "1": "315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f"}[GPU]
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES=GPU, OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
LOGF = os.path.join(OUT, f"{args.log}.json")
BASEF = os.path.join(OUT, f"{args.base_log}.json")
VERSION = "3.5"
EXPERIMENT = "cmdr_s1042_pair_eval"
ATTEMPT = f"g{GPU}-{os.getpid()}-{time.strftime('%m%d%H%M%S')}"
JOBN = [0]
OUT_FILES = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
NIGHT_OUT = os.path.join(OUT, "branch", "night_20261012_cmdr.out")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": VERSION, "experiment": EXPERIMENT, "args": vars(args), "attempt": ATTEMPT,
       "pins": {}, "tests": {}, "runs": [], "skipped": [], "pair_fail": [], "ckpt": {}, "matrix": {}}
PENDING = [[]]   # the live job queue, for the exit record
TRIES = {}       # name -> list of guard tries (k, rc, seconds, archived log)
LOCK = [None]


def logpath(name):
    return os.path.normcase(os.path.abspath(os.path.join(OUT, f"{name}.json")))
PUBLISH = [args.plan == "remeasure"]  # base: the previous log stays on disk until the re-validation pass is done


def save(force=False):
    if not (PUBLISH[0] or force):
        return
    tmp = LOGF + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(LOG, f, ensure_ascii=False, indent=1)
    for _ in range(40):
        try:
            os.replace(tmp, LOGF)
            return
        except PermissionError:  # Windows: a reader holds the file open
            time.sleep(0.25)
    raise RuntimeError(f"could not replace {LOGF}")


def say(s):
    print(f"{time.strftime('%H:%M:%S')} {s}", flush=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pins():
    p = {f: sha(os.path.join(HERE, f)) for f in PIN_FILES}
    code = json.load(open(os.path.join(B, "cmdr_s1042_off_u4000", "bundle.json"), encoding="utf-8"))["meta"]["code"]["files_sha256"]
    for rel, recorded in code.items():
        now = sha(os.path.join(ROOT, rel))
        assert now == recorded, f"source {rel} differs from the branch bundle record"
        p[rel] = now
    return p


def outhash(tag):
    return {f: sha(os.path.join(OUT, tag, f)) for f in OUT_FILES}


def gpu_used_mib(g):
    r = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) == 2 and parts[0] == g:
            return int(parts[1])
    return None


def training_done():
    """'' when the CMD-R pair has explicitly ended, else what is still missing (VERIFY-astra-16 6.1)."""
    on = os.path.join(B, "cmdr_s1042_on_u4000")
    try:
        r = json.load(open(os.path.join(on, "result.json"), encoding="utf-8"))
    except FileNotFoundError:
        return "on arm has no result.json"
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "on arm result.json unreadable"
    a, f = r.get("meta", {}).get("args", {}), r.get("final_state", {})
    if a.get("tag") != "cmdr_s1042_on_u4000" or a.get("cmdr") != "on" or f.get("where") != "end" or f.get("label_next") != 24000:
        return f"on arm result.json is not the finished on arm (tag {a.get('tag')} cmdr {a.get('cmdr')} where {f.get('where')} label_next {f.get('label_next')})"
    ck = MODELS["on24000"][0]
    if not os.path.exists(ck):
        return "no model_24000.pt"
    if os.path.getsize(ck) != CKPT_BYTES:
        return f"model_24000.pt size {os.path.getsize(ck)}"
    try:
        night = open(NIGHT_OUT, encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        return "no night log"
    e = night.rfind("cmdr_s1042_on_u4000 EXIT 0")
    if e < 0 or "NIGHT DONE" not in night[e:]:
        return "night log has no NIGHT DONE after the on arm's EXIT 0"
    if training_running():
        return "branch_run.py still running"
    used = gpu_used_mib(GPU)
    if used is None or used >= 3000:
        return f"GPU {GPU} memory used {used} MiB"
    return ""


def other_log(argv):
    """the --log value another cmdr_eval_driver*.py process was started with, parsed the way argparse would
    (--log X, --log=X, a unique prefix of --log); None when absent (v3.2: always cmdr_eval_driver)."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--log", default="cmdr_eval_driver")
    p.add_argument("--base_log", default="cmdr_eval_driver")
    try:
        known, _ = p.parse_known_args(argv)
    except SystemExit:
        return None
    return known.log


def driver_writers(log_name, procs=None):
    """pids of other python processes running a cmdr_eval_driver*.py whose log resolves to the same file."""
    want = logpath(log_name)
    out = []
    for info in (procs if procs is not None else _procs()):
        c = info.get("cmdline") or []
        if info.get("pid") == os.getpid() or not (info.get("name") or "").lower().startswith("python"):
            continue
        k = next((i for i, x in enumerate(c) if os.path.basename(x).lower().startswith("cmdr_eval_driver") and x.lower().endswith(".py")), None)
        if k is None:
            continue
        lg = other_log(c[k + 1:])
        if lg is None or logpath(lg) == want:  # unparsable argv counts as a writer (refuse rather than guess)
            out.append(info.get("pid"))
    return out


def _procs():
    out = []
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            out.append(dict(pr.info))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


def lock_held(name):
    """True when another process holds out/<name>.lock (a live v3.5 driver writing that log)."""
    import msvcrt
    p = os.path.join(OUT, f"{name}.lock")
    if not os.path.exists(p):
        return False
    f = open(p, "a+b")
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return True
    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    f.close()
    return False


def take_lock():
    """hold an exclusive OS lock on out/<log>.lock for the life of this process (Windows msvcrt)."""
    import msvcrt
    f = open(os.path.join(OUT, f"{args.log}.lock"), "a+b")
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return False
    LOCK[0] = f
    return True


def live_runs(tags):
    """(pid, tag) of q_eval_cmdr.py runs (or their gpu_guard wrappers) alive with one of these tags."""
    out = []
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            c = pr.info["cmdline"] or []
            if any(os.path.basename(x) == "q_eval_cmdr.py" for x in c) and "--tag" in c:
                t = c[c.index("--tag") + 1]
                if t in tags:
                    out.append((pr.info["pid"], t))
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, IndexError):
            pass
    return out


def training_running():
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            c = pr.info["cmdline"] or []
            if (pr.info["name"] or "").lower().startswith("python") and any(os.path.basename(x) == "branch_run.py" for x in c):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def unseen_running():
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            c = pr.info["cmdline"] or []
            if (pr.info["name"] or "").lower().startswith("python") and any(os.path.basename(x) == "unseen_driver.py" for x in c):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


SEEN = {}


def ready(m):
    p, _ = MODELS[m]
    if not os.path.exists(p):
        return False
    st = os.stat(p)
    key = (st.st_size, st.st_mtime_ns)
    first = SEEN.setdefault(m, (key, time.time()))
    if first[0] != key:
        SEEN[m] = (key, time.time())
        return False
    if st.st_size != CKPT_BYTES or time.time() - first[1] < 120:
        return False
    if m.startswith("on"):
        rep = os.path.join(B, "cmdr_bundle_compare__cmdr_s1042_off_u4000__cmdr_s1042_on_u4000.json")
        if not os.path.exists(rep):
            return False
        r = json.load(open(rep, encoding="utf-8"))
        d = os.path.join(B, "cmdr_s1042_on_u4000")
        do = os.path.join(B, "cmdr_s1042_off_u4000")
        now = {"off_json": sha(os.path.join(do, "bundle.json")), "off_npz": sha(os.path.join(do, "bundle.npz")),
               "on_json": sha(os.path.join(d, "bundle.json")), "on_npz": sha(os.path.join(d, "bundle.npz"))}
        con = r.get("contract", {})
        if r.get("verdict") != "SAME" or r.get("bundle_sha256") != now or con.get("envs") != 8192 or con.get("updates") != 4000 \
                or con.get("gate") is not False or r.get("tool_sha256") != P0["cmdr_bundle_compare.py"]:
            LOG["ckpt"].setdefault(m, {})["blocked"] = "bundle comparison not SAME for the current on bundle"
            save()
            return False
    if "sha256" not in LOG["ckpt"].get(m, {}):
        LOG["ckpt"][m] = {"path": p, "sha256": sha(p), "pinned_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        save()
    return True


def py_traceback(name):
    """True if out/<name>.log holds a Python traceback. Isaac Kit can exit 0 after an uncaught exception (04:21 test 3:
    AssertionError in the log, exit 0), so the exit code alone does not tell a refused or crashed run from a good one.
    Checked on the 586 logs in out/ at 04:30: the 5 with a traceback are all failed runs, none of the others has one."""
    try:
        with open(os.path.join(OUT, f"{name}.log"), encoding="utf-8", errors="replace") as f:
            return "Traceback (most recent call last)" in f.read()
    except FileNotFoundError:
        return False


def log_done(tag, n):
    """'' if out/<tag>.log exists and holds the evaluator's own completion line for this tag and N, else the reason.
    v3.1 passed a missing or empty log (VERIFY-astra-14 9.2): py_traceback() is False when there is no log."""
    p = os.path.join(OUT, f"{tag}.log")
    if not os.path.exists(p):
        return "log missing"
    with open(p, encoding="utf-8", errors="replace") as f:
        s = f.read()
    if not s.strip():
        return "log empty"
    if f"[Q-EVAL] done {tag} N {n} " not in s:
        return "log has no completion line for this tag and N"
    return ""


def guarded(name, cmd, tries=4, wait_s=300):
    rc = None
    for k in range(1, tries + 1):
        if time.time() > DEADLINE:
            say(f"DEADLINE before {name}")
            LOG["stopped"] = "deadline"
            save()
            sys.exit(2)
        if pins() != P0:
            LOG["stopped"] = f"pins changed before {name}"
            save()
            say("PINS CHANGED: stop")
            sys.exit(4)
        kept = []
        for ext in (".log", ".guard.json"):  # an earlier try of this name keeps its evidence
            src = os.path.join(OUT, name + ext)
            if os.path.exists(src):
                os.makedirs(os.path.join(OUT, "attempts"), exist_ok=True)
                dst = os.path.join(OUT, "attempts", f"{name}{ext}.{time.strftime('%m%d%H%M%S', time.localtime(os.path.getmtime(src)))}.{os.getpid()}")
                os.replace(src, dst)
                kept.append(os.path.relpath(dst, OUT))
        t0 = time.time()
        rc = subprocess.run([PY, "gpu_guard.py", "--gpu", GPU, "--min_free_mib", "4096", "--log", f"out/{name}.log",
                             "--summary", f"out/{name}.guard.json", "--"] + cmd, cwd=HERE, env=ENV).returncode
        TRIES.setdefault(name, []).append({"try": k, "rc": rc, "s": round(time.time() - t0), "earlier_moved": kept})
        say(f"RUN {name} try {k} EXIT {rc} {time.time() - t0:.0f}s")
        if rc == 0 and py_traceback(name):
            say(f"  {name}: exit 0 but a Python Traceback is in the log; counted as error 1 (Isaac Kit exits 0 after an uncaught exception)")
            rc = 1
        if rc == 0:
            return 0, k
        if rc == 99:
            say(f"GUARD STOP {name}: free < 4096 MiB on GPU {GPU}, waiting {wait_s}s")
            time.sleep(wait_s)
        else:
            return rc, k  # a real error is not retried
    return rc, tries


def q(script, tag, model_path, fam, cells, episodes, noise, seed, train_yaml=None, small=True):
    cmd = [PY, script, "--headless", "--tag", tag, "--policy", "student", "--checkpoint", model_path,
           "--families", fam, "--cells", cells, "--episodes", str(episodes), "--eval_seed", str(seed)]
    if small:
        cmd.append("--physx_small_buffers")
    if noise:
        cmd.append("--obs_noise")
    if not model_path.startswith(E1):
        cmd += ["--train_yaml", train_yaml or E1_YAML]
    return cmd


PRE_ZERO = ["teacher_input_randomized_max_abs_action_change", "manual_student_path_vs_act_inference_max_abs",
            "height_block_vs_raycaster_recomputed_max_abs", "non_height_critic_unchanged_max_abs",
            "student_height_permuted_max_abs_action_change", "teacher_manual_vs_module_act_mean_max_abs",
            "teacher_identity_perm_vs_normal_max_abs"]
PRE_TRUE = ["critic_dims_sum_equals_width", "height_block_values_same_multiset"]
PRE_POS = ["policy_history_perturbed_max_abs_action_change", "single_obs_perturbed_max_abs_action_change",
           "teacher_height_permuted_max_abs_action_change"]


def validate(tag, ckpt_sha, it, fam, cells, episodes, noise, seed, branch, need_iter=True, small=True):
    """Return '' if the run folder is a complete, correct result for exactly this input, else the reason."""
    d = os.path.join(OUT, tag)
    try:
        g = json.load(open(os.path.join(OUT, f"{tag}.guard.json"), encoding="utf-8"))
        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
            return f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}"
        if py_traceback(tag):
            return "Python Traceback in log"
        why = log_done(tag, len(cells) * episodes)
        if why:
            return why
        m = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        c = json.load(open(os.path.join(d, "cells.json"), encoding="utf-8"))
        rows = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
        z = np.load(os.path.join(d, "traj.npz"))
        a = m["args"]
        n = len(cells) * episodes
        want = {"families": fam, "cells": ",".join(cells), "episodes": episodes, "eval_seed": seed, "obs_noise": noise,
                "difficulty": 0.5, "terrain_set": "train", "heading_hold": 0.0, "spawn_offset": "", "policy": "student"}
        for k, v in want.items():
            if a.get(k) != v:
                return f"arg {k}={a.get(k)!r} want {v!r}"
        if m.get("checkpoint_sha256") != ckpt_sha:
            return "checkpoint sha256"
        if need_iter and m.get("loaded_iter") != it:
            return f"loaded_iter {m.get('loaded_iter')}"
        if m.get("N") != n or [x["name"] for x in m["cells"]] != cells:
            return "N or cells"
        if m["devices"].get("torch_cuda0_uuid") != GPU_UUID:
            return "gpu uuid"
        pre, run = m["checks_pre"], m["checks_run"]
        for k in PRE_ZERO:
            if not abs(float(pre[k])) <= 1e-6:
                return f"checks_pre {k}={pre[k]}"
        for k in PRE_TRUE:
            if pre[k] is not True:
                return f"checks_pre {k}"
        # finite first: NaN > 1e-6 is False, so v3.1 passed a NaN command error (VERIFY-astra-14 9.2)
        cmd_err = [run["obs_single_cmd_vs_target_max_abs"], run["obs_history_latest_cmd_vs_target_max_abs"]]
        # v3.3: a max_abs is never negative; v3.2 passed -1 (VERIFY-astra-15)
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1e-6 for v in cmd_err) \
                or run["nonfinite_action_or_obs_count"] != 0:
            return f"checks_run {run}"
        if branch:
            s = m.get("train_yaml_source", {})
            if os.path.normcase(os.path.abspath(s.get("train_yaml", ""))) != os.path.normcase(os.path.abspath(E1_YAML)) \
                    or "bundle_json_sha256" not in s:
                return "train_yaml_source"
        if len(c) != len(cells) or any(x["n"] != episodes for x in c):
            return "cells.json n"
        if len(rows) != n:
            return f"episodes.csv rows {len(rows)}"
        for cl in cells:
            ids = sorted(int(r["episode"]) for r in rows if r["cell"] == cl and r["family"] == fam)
            if ids != list(range(episodes)):
                return f"episode ids for {cl}"
        if any(r["family"] != fam or r["cell"] not in cells for r in rows):
            return "episodes.csv family / cell"
        T = m["T_steps"]
        if T != int(round(max(DUR_S.get(c, 20.0) for c in cells) / 0.02)):
            return f"T_steps {T}"
        if z["traj"].shape != (T + 1, n, 12) or z["term"].shape != (T + 1, n):
            return f"traj shape {z['traj'].shape}"
        if not np.isfinite(z["traj"][..., :11]).all():  # channel 11 (height above ground) may be NaN on a ray miss
            return "traj non-finite"
        if z["cmd_hist"].shape != (T + 1, n, 3) or not np.isfinite(z["cmd_hist"]).all():
            return "cmd_hist"
        if "physx buffers reduced" not in " ".join(m.get("eval_changes", [])) and small:
            return "physx small buffers not applied"
        if isinstance(m.get("terrain_mesh"), str) or not m.get("terrain_mesh"):
            return "terrain mesh"
        for k in ("pairing_sha256", "pairing_sha256_ext"):
            v = m.get(k)
            if not isinstance(v, dict) or not v or not all(v.values()):
                return f"{k} empty"
    except Exception as ex:  # noqa: BLE001
        return f"unreadable: {type(ex).__name__}: {ex}"
    return ""


def diag_warns(tag):
    m = json.load(open(os.path.join(OUT, tag, "meta.json"), encoding="utf-8"))
    return [k for k in PRE_POS if not float(m["checks_pre"][k]) > 0]


def fingerprint(tag):
    d = os.path.join(OUT, tag)
    m = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    z = np.load(os.path.join(d, "traj.npz"))
    return {"pairing_sha256": m["pairing_sha256"], "pairing_sha256_ext": m["pairing_sha256_ext"], "terrain_mesh": m["terrain_mesh"],
            "terrain_origins_sha256": m["terrain_origins_sha256"], "env_origins": sha(os.path.join(d, "env_origins.npy")),
            "N": m["N"], "T": m["T_steps"], "cells": m["cells"], "obs_shapes": m["obs_shapes"], "eval_changes": m.get("eval_changes"),
            "uuid": m["devices"]["torch_cuda0_uuid"], "layout": {k: hashlib.sha256(np.ascontiguousarray(z[k]).tobytes()).hexdigest()
                                                                   for k in ("fam", "cel", "epi", "cmd_a", "cmd_b", "sw")},
            "traj0": hashlib.sha256(np.ascontiguousarray(z["traj"][0]).tobytes()).hexdigest()}


def old_stamp(tag):
    """the stamp as a dict; {} when missing, broken or unreadable (a cut write must not stop the driver)."""
    p = os.path.join(OUT, tag, "driver_stamp.json")
    try:
        st = json.load(open(p, encoding="utf-8"))
        return st if isinstance(st, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, PermissionError):
        return {}


def stamp_ok(tag, P):
    """The stamp has the current pins; a stamp from v3.3 on (stamp_version or hashes present) must carry the output
    hashes and they must still match. A v3.2 stamp (neither) is accepted here and validate() decides."""
    st = old_stamp(tag)
    if not st or st.get("pins") != P:
        return False
    if "stamp_version" in st or "out_sha256" in st:
        if not isinstance(st.get("out_sha256"), dict):
            return False
        try:
            return st["out_sha256"] == outhash(tag)
        except FileNotFoundError:
            return False
    return True


def write_stamp(tag, P, extra):
    p = os.path.join(OUT, tag, "driver_stamp.json")
    tmp = p + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"pins": P, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "stamp_version": VERSION, **extra}, f, indent=1)
    for _ in range(40):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:  # Windows: a reader holds the stamp open
            time.sleep(0.25)
    raise RuntimeError(f"could not replace {p}")


def tests(P):
    pin8 = hashlib.sha256(json.dumps(P, sort_keys=True).encode()).hexdigest()[:8] + f"_g{GPU}t{time.strftime('%H%M%S')}p{os.getpid()}"
    psha = LOG["ckpt"]["p20000"]["sha256"]
    # 1. smoke: parent, flat, 11 cells x 10 = 110 envs, validated like a real run
    t = f"cq_test_{pin8}_smoke"
    sc = in_eval_order(CELLS)
    rc, _ = guarded(t, q("q_eval_cmdr.py", t, MODELS["p20000"][0], "flat", ",".join(sc), 10, True, 1000))
    why = validate(t, psha, 20000, "flat", sc, 10, True, 1000, False) if rc == 0 else f"exit {rc}"
    LOG["tests"]["smoke"] = why or "ok"
    save()
    if why:
        return False
    # 2. known answer: q_eval.py vs q_eval_cmdr.py, same input; if different, q_eval.py vs q_eval.py tells
    #    non-determinism from a copy fault (ASTRA 8 2)
    LOG["tests"]["q_eval_py_sha256"] = sha(os.path.join(HERE, "q_eval.py"))
    a, b = f"cq_test_{pin8}_ka_orig", f"cq_test_{pin8}_ka_copy"
    for tag, script in ((a, "q_eval.py"), (b, "q_eval_cmdr.py")):
        rc, _ = guarded(tag, q(script, tag, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000))
        if rc != 0:
            LOG["tests"]["known_answer"] = f"{tag} exit {rc}"
            save()
            return False
    same = lambda x, y: (json.load(open(os.path.join(OUT, x, "cells.json"))) == json.load(open(os.path.join(OUT, y, "cells.json")))
                         and sha(os.path.join(OUT, x, "traj.npz")) == sha(os.path.join(OUT, y, "traj.npz")))
    ok = same(a, b)
    LOG["tests"]["known_answer"] = {"orig_vs_copy_same": ok}
    if not ok:
        a2 = f"cq_test_{pin8}_ka_orig2"
        guarded(a2, q("q_eval.py", a2, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000))
        LOG["tests"]["known_answer"]["orig_vs_orig_same"] = same(a, a2)
        save()
        return False
    save()
    # 2b. small PhysX buffers must not change the physics on the flat training terrain (copy, default buffers vs small)
    c2 = f"cq_test_{pin8}_ka_copy_default_buffers"
    rc, _ = guarded(c2, q("q_eval_cmdr.py", c2, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000, small=False))
    ok2 = rc == 0 and same(b, c2)
    LOG["tests"]["small_buffers_vs_default_same"] = ok2
    save()
    if not ok2:
        return False
    # 3. branch path must refuse a wrong train_yaml: another run's env.yaml, and a sibling file of the right folder
    g = f"{B}/gate_c1/model_20002.pt"
    gsha = sha(g)
    for name, bad in (("other_run", f"{E2}/params/env.yaml"), ("sibling", f"{E1}/params/agent.yaml")):
        t = f"cq_test_{pin8}_wrong_yaml_{name}"
        rc, _ = guarded(t, q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True, 1000, train_yaml=bad), tries=1)
        log = open(os.path.join(OUT, f"{t}.log"), encoding="utf-8", errors="replace").read()
        wrote = os.path.exists(os.path.join(OUT, t, "cells.json")) or os.path.exists(os.path.join(OUT, t, "traj.npz"))
        refused = rc != 0 and "AssertionError: train_yaml is not the parent run's" in log and not wrote
        LOG["tests"][f"wrong_yaml_{name}"] = {"exit": rc, "refused": refused, "wrote_result": wrote}
        save()
        if not refused:
            return False
    # 4. branch checkpoint passes and is read as iteration 20002 with the exact parent yaml and bundle hashes
    t = f"cq_test_{pin8}_branch_20002"
    rc, _ = guarded(t, q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True, 1000))
    why = validate(t, gsha, 20002, "flat", ["stop03"], 10, True, 1000, True) if rc == 0 else f"exit {rc}"
    LOG["tests"]["branch_pass"] = why or "ok"
    save()
    return not why


def jobs():
    out = []
    for m in MODELS:  # (A)
        for cell in CELLS:
            out.append((m, "flat", cell, True, 1000))
    for m in MODELS:  # (B)
        for s in EXT_SEEDS:
            for cell in TARGETS:
                out.append((m, "flat", cell, True, s))
    for fam in FAMILIES[1:]:  # (C)
        for m in MODELS:
            for cell in CELLS:
                out.append((m, fam, cell, True, 1000))
    for m in MODELS:  # (D)
        for cell in CELLS:
            out.append((m, "flat", cell, False, 1000))
    return out


def order24(js):
    first = ("off24000", "on24000")
    return [j for j in js if j[0] in first] + [j for j in js if j[0] not in first]


def main_pass(tag, cell):
    col = "span_q2_pass" if cell == "stop03" else ("span_q1a_pass" if cell in TARGETS else "span_q1_pass")
    rows = sorted(csv.DictReader(open(os.path.join(OUT, tag, "episodes.csv"), encoding="utf-8")), key=lambda r: int(r["episode"]))
    return [r[col] == "True" for r in rows]


def screen_universe():
    """the planned screen cells: every (family, cell, noise) of the base plan with seed 1000, minus the flat noise-on
    targets (measured at n=500 by (B))."""
    u = sorted({(fam, cell, noise) for (m, fam, cell, noise, seed) in jobs() if seed == 1000})
    return [k for k in u if not (k[0] == "flat" and k[2] and k[1] in TARGETS)]


def remeasure_tags():
    return {tagof(m, fam, cell, noise, s) for fam, cell, noise in screen_universe() for s in EXT_SEEDS for m in ("off24000", "on24000")}


def screen(valid):
    """n=100 screen at 24000: {(fam, cell, noise): (on passes - off passes, n)} for planned screen cells whose seed-1000
    runs are in `valid` for both arms. Episode i of off is paired with episode i of on (same seed, same layout)."""
    res = {}
    for fam, cell, noise in screen_universe():
                a, b = tagof("off24000", fam, cell, noise, 1000), tagof("on24000", fam, cell, noise, 1000)
                if a in valid and b in valid:
                    x, y = main_pass(a, cell), main_pass(b, cell)
                    assert len(x) == len(y) == 100, f"{a} {b} n"
                    res[(fam, cell, noise)] = (sum(y) - sum(x), len(x))
    return res


def flagged(dd, n):
    """2(c) screen: the on - off point estimate is -5 pp or lower (integer test, no float edge at exactly -5)."""
    return 100 * dd <= -5 * n


def read_base():
    """one snapshot of the base log, or None if it cannot be read right now."""
    try:
        d = json.load(open(BASEF, encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, PermissionError):
        return None


def base_final(snap, writers):
    """the snapshot is this experiment's final base record: this version, same experiment, ended or stopped, and no base writer
    alive (a restarting base keeps its old log until its re-validation pass is done)."""
    return (snap.get("version") == VERSION and snap.get("experiment") == EXPERIMENT and ("ended" in snap or "stopped" in snap)
            and not writers)


def tagof(m, fam, cell, noise, seed):
    return f"cq_{m}_{fam}_{cell}_{'on' if noise else 'off'}_s{seed}"


DEADLINE = time.mktime(time.strptime(args.until, "%Y-%m-%d %H:%M"))


def start():
    """checks before any run; sets P0. Exits (non-zero) instead of risking a second writer."""
    global P0
    if args.plan == "remeasure" and os.path.normcase(os.path.abspath(LOGF)) == os.path.normcase(os.path.abspath(BASEF)):
        say("--log must differ from --base_log for --plan remeasure")
        sys.exit(6)
    w = driver_writers(args.log)
    if w:
        say(f"another driver writes out/{args.log}.json (pids {w}): not starting")
        sys.exit(6)
    if not take_lock():
        say(f"out/{args.log}.lock is held by another process: not starting")
        sys.exit(6)
    P0 = pins()
    LOG["pins"] = P0
    LOG["code_sha256"] = {"driver": sha(os.path.abspath(__file__))}
    save()
    say(f"pins {len(P0)} files · q_eval_cmdr {P0['q_eval_cmdr.py'][:16]} · attempt {ATTEMPT}")
    mine = {tagof(*j) for j in jobs()} if args.plan == "base" else remeasure_tags()
    while unseen_running() or live_runs(mine):
        if time.time() > DEADLINE:
            say("deadline while waiting for the unseen driver or a live run of this plan")
            sys.exit(2)
        say(f"waiting: unseen {unseen_running()} · live runs of this plan {live_runs(mine)[:3]}")
        time.sleep(30)
    if GPU == "0":
        ok = 0
        while ok < 2:  # (d) two looks 60 s apart
            why = training_done()
            ok = ok + 1 if not why else 0
            if why:
                if time.time() > DEADLINE:
                    say(f"deadline while waiting for GPU 0: {why}")
                    sys.exit(2)
                say(f"GPU 0 not handed over yet: {why}")
            time.sleep(60)
    LOG[f"gpu{GPU}_from"] = time.strftime("%Y-%m-%d %H:%M:%S")
    say(f"GPU {GPU} is ours")
    while not all([ready(m) for m in MODELS][:1]):  # look at every model each pass, wait for the parent
        if time.time() > DEADLINE:
            sys.exit(2)
        time.sleep(30)


def run_tests():
    if not tests(P0):
        LOG["stopped"] = "start tests failed"
        save(force=True)
        say(f"TESTS FAILED {LOG['tests']}")
        sys.exit(3)
    say(f"tests passed {LOG['tests']}")


groups = {}


def process(pick, reuse_only=False):
    """Run (or reuse) one job and record it. reuse_only: return False without running if it cannot be reused."""
    m, fam, cell, noise, seed = pick
    tag = tagof(m, fam, cell, noise, seed)
    path, it = MODELS[m]
    if pins() != P0:
        LOG["stopped"] = "pins changed"
        save()
        say("PINS CHANGED: stop")
        sys.exit(4)
    if sha(path) != LOG["ckpt"][m]["sha256"]:
        LOG["stopped"] = f"checkpoint {m} changed after pinning"
        save()
        say(f"CHECKPOINT CHANGED {m}: stop")
        sys.exit(5)
    branch = not path.startswith(E1)
    prev = old_stamp(tag)
    if stamp_ok(tag, P0) and not validate(tag, LOG["ckpt"][m]["sha256"], it, fam, [cell], 100, noise, seed, branch):
        why, reused = "", True
        attempt = prev.get("attempt", "v3.2 or earlier")
    elif reuse_only:
        return False
    else:
        JOBN[0] += 1
        attempt = f"{ATTEMPT}-j{JOBN[0]}"
        rc, k = guarded(tag, q("q_eval_cmdr.py", tag, path, fam, cell, 100, noise, seed))
        why = validate(tag, LOG["ckpt"][m]["sha256"], it, fam, [cell], 100, noise, seed, branch) if rc == 0 else f"exit {rc}"
        reused = False
    if pins() != P0:
        LOG["stopped"] = f"pins changed during {tag}"
        save()
        say("PINS CHANGED: stop")
        sys.exit(4)
    rec = {"tag": tag, "valid": not why, "why": why, "reused": reused, "t": time.strftime("%H:%M:%S"), "attempt": attempt,
           "gpu": GPU, "tries": [] if reused else TRIES.pop(tag, [])}
    if not why:
        rec["out_sha256"] = outhash(tag)
        rec["diag_warns"] = diag_warns(tag)
        fp = fingerprint(tag)
        gk = (fam, cell, noise, seed)
        if gk not in groups:
            groups[gk] = (tag, fp)
        elif fp != groups[gk][1]:
            bad = sorted(k for k in fp if fp[k] != groups[gk][1].get(k))
            rec["pair_fail"] = {"against": groups[gk][0], "fields": bad}
            LOG["pair_fail"].append(tag)
        write_stamp(tag, P0, {"ckpt_sha256": LOG["ckpt"][m]["sha256"], "pair_ref": groups[gk][0], "attempt": attempt,
                              "out_sha256": rec["out_sha256"], "prev_stamp_t": prev.get("t")})
    else:
        LOG["skipped"].append(tag)
    LOG["runs"].append(rec)
    LOG["matrix"][tag] = "valid" if not why and "pair_fail" not in rec else ("pair_fail" if not why else "invalid")
    save()
    return True


def main_base():
    pending = PENDING[0]
    pending += order24(jobs()) if args.order == "24first" else jobs()
    for j in list(pending):  # one re-validation pass before any new run; nothing is written until it is done
        if ready(j[0]) and process(j, reuse_only=True):
            pending.remove(j)
    PUBLISH[0] = True
    LOG["revalidated"] = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "reused": len(LOG["runs"])}
    save()
    say(f"re-validation pass: {len(LOG['runs'])} reused · {len(pending)} pending")
    run_tests()
    while pending and time.time() < DEADLINE:
        pick = next((j for j in pending if ready(j[0])), None)
        if pick is None:
            time.sleep(60)
            continue
        pending.remove(pick)
        process(pick)
    want = [tagof(*j) for j in jobs()]
    LOG["ended"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG["not_run"] = [tagof(*j) for j in pending]
    LOG["not_valid"] = [t for t in want if LOG["matrix"].get(t) not in (None, "valid")]
    LOG["complete"] = all(LOG["matrix"].get(t) == "valid" for t in want)
    save()
    say(f"END complete={LOG['complete']} runs={len(LOG['runs'])} not_run={len(LOG['not_run'])} not_valid={len(LOG['not_valid'])}")


def read_base_raw():
    """(snapshot dict, sha256 of its bytes) or (None, reason)."""
    try:
        raw = open(BASEF, "rb").read()
    except (FileNotFoundError, PermissionError) as ex:
        return None, type(ex).__name__
    try:
        d = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        return None, type(ex).__name__
    return (d, hashlib.sha256(raw).hexdigest()) if isinstance(d, dict) else (None, "not a dict")


def main_remeasure(sleep=time.sleep):
    pending = PENDING[0]
    queued = set()
    LOG["screen"], LOG["screen_history"], LOG["withdrawn"], LOG["dequeued"] = {}, {}, {}, []
    last = {"snap": None, "hash": None, "t": None}
    prev_hash = None
    while True:
        if time.time() >= DEADLINE:  # (h) first, whatever the base log looks like
            LOG["stopped"] = "deadline"
            break
        snap, h = read_base_raw()
        if snap is None:
            LOG["base_read_fail"] = {"t": time.strftime("%H:%M:%S"), "why": h, "last_good": last["t"], "last_good_hash": last["hash"]}
            save()
            sleep(30)
            continue
        last = {"snap": snap, "hash": h, "t": time.strftime("%H:%M:%S")}
        writers = driver_writers(args.base_log) + (["lock"] if lock_held(args.base_log) else [])
        valid = {t for t, v in snap.get("matrix", {}).items() if v == "valid"} | {t for t, v in LOG["matrix"].items() if v == "valid"}
        sc = screen(valid)
        now = {}
        for (fam, cell, noise), (dd, n) in sorted(sc.items()):
            key = f"{fam}/{cell}/{'on' if noise else 'off'}"
            now[key] = {"on_minus_off_passes": dd, "n": n, "flag": flagged(dd, n)}
            LOG["screen_history"].setdefault(key, {"first_seen": time.strftime("%H:%M:%S"), "first": now[key]})
            if now[key]["flag"] and key not in queued:
                queued.add(key)
                say(f"SCREEN {key} {100 * dd / n:+.0f} pp -> seeds {EXT_SEEDS}")
                pending += [(m, fam, cell, noise, s_) for s_ in EXT_SEEDS for m in ("off24000", "on24000")]
        for key in list(LOG["screen"]):
            if key not in now and key not in LOG["withdrawn"]:  # (j) present before, gone from the current snapshot
                LOG["withdrawn"][key] = {"t": time.strftime("%H:%M:%S"), "base_attempt": snap.get("attempt"), "snapshot": h}
        for key in now:
            LOG["withdrawn"].pop(key, None)
        flagged_now = {k for k, v in now.items() if v["flag"]}
        for j in list(pending):
            key = f"{j[1]}/{j[2]}/{'on' if j[3] else 'off'}"
            if key not in flagged_now:
                pending.remove(j)
                queued.discard(key)
                LOG["dequeued"].append({"tag": tagof(*j), "key": key, "t": time.strftime("%H:%M:%S"), "snapshot": h})
        LOG["screen"] = now
        final = base_final(snap, writers) and h == prev_hash  # same bytes twice, no writer, screened above
        prev_hash = h
        LOG["base_seen"] = {"attempt": snap.get("attempt"), "version": snap.get("version"), "ended": snap.get("ended"),
                            "stopped": snap.get("stopped"), "complete": snap.get("complete"), "runs": len(snap.get("runs", [])),
                            "writers": writers, "snapshot": h, "final": final}
        save()
        pick = next((j for j in pending if ready(j[0])), None)
        if pick is None:
            if final:
                break
            sleep(60)
            continue
        pending.remove(pick)
        process(pick)
    snap = last["snap"]
    uni = [f"{f}/{c}/{'on' if n else 'off'}" for f, c, n in screen_universe()]
    unmeasured = [k for k in uni if k not in LOG["screen"]]
    flagged_keys = sorted(k for k, v in LOG["screen"].items() if v["flag"])
    group_missing = []
    for k in flagged_keys:
        fam, cell, nz = k.split("/")
        for sd in EXT_SEEDS:
            for m in ("off24000", "on24000"):
                t = tagof(m, fam, cell, nz == "on", sd)
                if LOG["matrix"].get(t) != "valid":
                    group_missing.append(t)
    LOG["ended"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG["not_run"] = [tagof(*j) for j in pending]
    LOG["screen_unmeasured"] = unmeasured
    LOG["flagged"] = flagged_keys
    LOG["remeasure_missing"] = group_missing
    LOG["last_good_base"] = {"t": last["t"], "snapshot": last["hash"]}
    LOG["complete"] = bool(snap and snap.get("complete") and not unmeasured and not group_missing and "stopped" not in LOG)
    save()
    say(f"END complete={LOG['complete']} flagged={len(flagged_keys)} unmeasured={len(unmeasured)} missing={len(group_missing)}")


def exit_record(code, why):
    """(k) one record for every way out; keeps the old base table during the re-validation pass."""
    LOG.setdefault("stopped", why)
    LOG["exit_code"] = code
    LOG["exited"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG["not_run"] = [tagof(*j) for j in PENDING[0]]
    LOG["not_valid"] = sorted(t for t, v in LOG["matrix"].items() if v != "valid")
    if PUBLISH[0]:
        save()
    else:
        with open(os.path.join(OUT, f"{args.log}.stopped.json"), "w", encoding="utf-8") as f:
            json.dump(LOG, f, ensure_ascii=False, indent=1)


def main():
    try:
        start()
        if args.plan == "base":
            main_base()
        else:
            run_tests()
            main_remeasure()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            exit_record(code, f"exit {code}")
        raise
    except BaseException as e:  # noqa: BLE001
        exit_record(1, f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
