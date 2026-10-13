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
# v3.6 (10/13 11:38, VERIFY-astra-16d 2.1 - 2.5; v3.5 ran only as the GPU 0 remeasure from 10:55):
#   (n) ownership: nothing is written to out/<log>.json, out/<log>.stopped.json or out/<log>.attempt.json before this
#       process holds out/<log>.lock. A refused start writes only out/attempts/<log>.<attempt>.refused.json (16d 2.1).
#   (o) attempt file: the owner of a log keeps out/<log>.attempt.json = {attempt, state, t} with state
#       revalidating -> running -> ended | stopped. The remeasure ends only when the attempt file says ended or stopped,
#       the base snapshot carries that same attempt, no writer is alive or unknown, and the same snapshot bytes were read
#       twice in a row with no writer; a read failure or a writer resets the count. An old finished log under a new
#       attempt (one that died while re-validating) never ends the remeasure (16d 2.2).
#   (p) active job: the job taken off the queue is recorded (tag, attempt, stage) before anything else, and its guard
#       tries leave TRIES only after the run record is saved; the exit record lists active / pending / not_valid and
#       complete = False (16d 2.3).
#   (q) a python process whose argv cannot be read counts as an unknown writer: the start is refused and the remeasure
#       does not take the base as final (16d 2.4).
#   (r) every end, normal or not, writes end_kind (complete / incomplete / error), exit_code and the lists (16d 2.5).
#   (s) a stop file out/<log>.stop ends the driver cleanly at the next job boundary (for hand-over without killing).
#   (t) Isaac start spacing. Isaac Lab converts the robot URDF into /tmp/IsaacLab/usd_<YYYYmmdd_HHMMSS>_<random>, and
#       the "random" part is the same in every run because the evaluator seeds Python's random first (7028 in every log).
#       Two Isaac processes that convert in the same second share one folder; at 11:38:28 the GPU 0 start test 2b lost
#       that race (robot reference unresolved, traceback) while a GPU 1 run converted in the same folder. Before every
#       launch the driver now waits, under an OS lock shared by v3.6 drivers (out/isaac_start.lock), until no
#       q_eval_cmdr.py process of any driver (v3.2 included) started in the last 30 s and no v3.6 launch was recorded in
#       the last 30 s (out/isaac_start.json), then records its own launch.
#   (u) a run that ends with the collision signature ("</World/envs/env_0/Robot>: Unresolved reference") is retried
#       (its log is kept under out/attempts/ like any try) instead of being recorded as an evaluation failure.
# v3.7 (10/13 12:42, VERIFY-astra-16f 3.1 / 3.2 / 3.3 / 4; (t) and (u) are replaced):
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
#        python cmdr_eval_driver_v37.py --gpu 0 --plan remeasure --log cmdr_eval_driver_g0 --until "2026-10-13 20:00"
import argparse
import csv
import hashlib
import json
import math
import os
import re
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
VERSION = "3.7"
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
PUBLISH = [False]  # set once this process owns the log (remeasure: right after the lock; base: after the re-validation pass)
OWNED = [False]
ACTIVE = [None]  # the job taken off the queue: {"tag", "attempt", "stage"}
ATTF = os.path.join(OUT, f"{args.log}.attempt.json")


def set_attempt(state):
    """the owner's attempt file: {attempt, state, t}; written atomically, only by the lock holder."""
    if not OWNED[0]:
        return
    p = os.path.join(OUT, f"{args.log}.attempt.json")
    tmp = p + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"attempt": ATTEMPT, "state": state, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "version": VERSION}, f)
    os.replace(tmp, p)


def save(force=False):
    if not OWNED[0]:  # 16d 2.1: never write the shared log without holding its lock
        return
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
        if info.get("pid") == os.getpid() or not (info.get("name") or "").lower().startswith("python"):
            continue
        if info.get("cmdline") is None:  # 16d 2.4: unreadable argv is unknown, not "no writer"
            out.append(f"unknown:{info.get('pid')}")
            continue
        c = info.get("cmdline") or []
        k = next((i for i, x in enumerate(c) if os.path.basename(x).lower().startswith("cmdr_eval_driver") and x.lower().endswith(".py")), None)
        if k is None:
            continue
        lg = other_log(c[k + 1:])
        if lg is None or logpath(lg) == want:  # unparsable argv counts as a writer (refuse rather than guess)
            out.append(info.get("pid"))
    return out


def _procs():
    out = []
    for pr in psutil.process_iter(["pid", "name", "cmdline"]):  # AccessDenied on cmdline gives cmdline None (unknown)
        try:
            out.append(dict(pr.info))
        except psutil.NoSuchProcess:
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


PARTICIPANT = "cmdr_eval_driver_v37.py"
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
        why = usd_check(tag)  # (y)
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


def stop_requested():
    return os.path.exists(os.path.join(OUT, f"{args.log}.stop"))


def read_attempt(name):
    try:
        d = json.load(open(os.path.join(OUT, f"{name}.attempt.json"), encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, PermissionError):
        return None


def base_final(snap, writers):
    """the snapshot is this experiment's final base record: this version, same experiment, ended or stopped, and no base writer
    alive (a restarting base keeps its old log until its re-validation pass is done)."""
    att = read_attempt(args.base_log)  # 16d 2.2: the end must belong to the base attempt that owns the log now
    return (snap.get("version") == VERSION and snap.get("experiment") == EXPERIMENT and ("ended" in snap or "stopped" in snap)
            and not writers and att is not None and att.get("state") in ("ended", "stopped") and att.get("attempt") == snap.get("attempt"))


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
    OWNED[0] = True
    if args.plan == "remeasure":
        PUBLISH[0] = True
    set_attempt("revalidating" if args.plan == "base" else "running")
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
    ACTIVE[0] = {"tag": tag, "stage": "checks", "t": time.strftime("%H:%M:%S")}
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
    moved = None
    sp_ = os.path.join(OUT, tag, "driver_stamp.json")
    prev_sha = sha(sp_) if os.path.exists(sp_) else None  # (o2) the stamp this run had before, kept by hash
    if stamp_ok(tag, P0) and not validate(tag, LOG["ckpt"][m]["sha256"], it, fam, [cell], 100, noise, seed, branch):
        why, reused = "", True
        attempt = prev.get("attempt", "v3.2 or earlier")
    elif reuse_only:
        ACTIVE[0] = None
        return False
    else:
        JOBN[0] += 1
        attempt = f"{ATTEMPT}-j{JOBN[0]}"
        ACTIVE[0].update(attempt=attempt, stage="run")
        moved = preserve_result(tag)  # (z)
        rc, k = guarded(tag, q("q_eval_cmdr.py", tag, path, fam, cell, 100, noise, seed), ck=m)
        why = validate(tag, LOG["ckpt"][m]["sha256"], it, fam, [cell], 100, noise, seed, branch) if rc == 0 else f"exit {rc}"
        reused = False
    if pins() != P0:
        LOG["stopped"] = f"pins changed during {tag}"
        save()
        say("PINS CHANGED: stop")
        sys.exit(4)
    rec = {"tag": tag, "valid": not why, "why": why, "reused": reused, "t": time.strftime("%H:%M:%S"), "attempt": attempt,
           "gpu": GPU, "tries": [] if reused else list(TRIES.get(tag, [])), "usd_dir": usd_dirs_of(tag)}
    # (o2) where the output hashes come from (VERIFY-astra-16g 4): measured by this driver family with hashes from the
    # start, or a v3.2 run whose hashes are first taken now when it is re-validated. Never upgraded on a later reuse.
    origin = {"origin": "hashed-at-collection"} if not reused else {
        "origin": prev.get("origin") or ("legacy-origin revalidated" if "stamp_version" not in prev else "hashed-at-collection"),
        "prev_stamp_sha256": prev_sha, "revalidated_by": ATTEMPT, "revalidated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    rec["origin"] = origin["origin"]
    if moved:
        rec["earlier_result_moved"] = moved
    if any(t.get("infra_fail") for t in rec["tries"]):
        rec["infra_fail"] = True
    ACTIVE[0]["stage"] = "record"
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
                              "out_sha256": rec["out_sha256"], "prev_stamp_t": prev.get("t"), **origin})
    else:
        LOG["skipped"].append(tag)
    LOG["runs"].append(rec)
    LOG["matrix"][tag] = "valid" if not why and "pair_fail" not in rec else ("pair_fail" if not why else "invalid")
    save()
    TRIES.pop(tag, None)  # only after the record is saved (16d 2.3)
    ACTIVE[0] = None
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
    set_attempt("running")
    while pending and time.time() < DEADLINE and not stop_requested():
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
    if pending:
        LOG["stopped"] = "stop file" if stop_requested() else "deadline"
    LOG["end_kind"], LOG["exit_code"] = ("complete" if LOG["complete"] else "incomplete"), 0
    save()
    set_attempt("ended" if LOG["complete"] else "stopped")
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
        if stop_requested():
            LOG["stopped"] = "stop file"
            break
        snap, h = read_base_raw()
        if snap is None:
            prev_hash = None  # 16d 2.2: a failed read breaks the run of stable reads
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
        prev_hash = None if writers else h  # a read with a writer alive does not count as a stable read
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
    LOG["end_kind"], LOG["exit_code"] = ("complete" if LOG["complete"] else "incomplete"), 0
    save()
    set_attempt("ended" if LOG["complete"] else "stopped")
    say(f"END complete={LOG['complete']} flagged={len(flagged_keys)} unmeasured={len(unmeasured)} missing={len(group_missing)}")


def exit_record(code, why):
    """(k)(p)(r) one record for every way out. Without the lock nothing shared is touched (16d 2.1): a refused start
    writes out/attempts/<log>.<attempt>.refused.json only. The owner keeps the old base table during the re-validation
    pass (out/<log>.stopped.json beside it) and marks its attempt file stopped."""
    LOG.setdefault("stopped", why)
    LOG["exit_code"] = code
    LOG["end_kind"] = "incomplete" if code in (2, 7) else "error"  # (w) deadline / stop file before a launch
    LOG["complete"] = False
    LOG["exited"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG["active"] = ACTIVE[0]
    LOG["active_tries"] = TRIES.get(ACTIVE[0]["tag"], []) if ACTIVE[0] else []
    LOG["not_run"] = [tagof(*j) for j in PENDING[0]]
    LOG["not_valid"] = sorted(t for t, v in LOG["matrix"].items() if v != "valid")
    if not OWNED[0]:
        d = os.path.join(OUT, "attempts")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{args.log}.{ATTEMPT}.refused.json"), "w", encoding="utf-8") as f:
            json.dump({k: LOG[k] for k in ("started", "version", "attempt", "args", "stopped", "exit_code", "exited")}, f, ensure_ascii=False, indent=1)
        return
    if PUBLISH[0]:
        save()
    else:
        with open(os.path.join(OUT, f"{args.log}.stopped.json"), "w", encoding="utf-8") as f:
            json.dump(LOG, f, ensure_ascii=False, indent=1)
    set_attempt("stopped")


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
