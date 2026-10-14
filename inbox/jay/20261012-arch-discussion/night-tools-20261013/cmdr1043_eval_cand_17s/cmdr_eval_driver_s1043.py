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
#       A v3.3-v3.6 stamp with attempt "v3.2 or earlier" (a v3.2 run those versions re-validated) is legacy-origin
#       revalidated, a stamp with a real job id is hashed-at-collection, anything else "origin unknown" (16h 3.2).
#   (v2) VERIFY-astra-16h 3.1: a lock participant is a process (or a descendant of one) running THIS file, compared by
#       real path (a relative script path resolved against the process's cwd); a same-named copy in another folder has
#       its own out/isaac_convert.lock and is foreign. A python process with an empty argv is unknown (foreign).
#       Limit: a scan cannot stop a non-participant that starts right after it, and an Isaac app with an unknown
#       script name and no --headless is not recognised; while two v3.7 drivers collect, no other session starts Isaac.
# Usage: python cmdr_eval_driver_v37.py --gpu 1 --plan base --order 24first --until "2026-10-13 20:00"
#        python cmdr_eval_driver_v37.py --gpu 0 --plan remeasure --log cmdr_eval_driver_g0 --until "2026-10-13 20:00"
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
import psutil

from s1043_manifest import UNDECIDED, assert_isolated, canonical_hash, check_inputs, inside, launch_errors, load

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ROOT = None  # populated from the registered deployment root below
CELLS = ["stop03", "fwd01", "fwd02", "stand", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
TARGETS = ["stop03", "fwd01", "fwd02"]
FAMILIES = ["flat", "obstacles", "rough_slope", "slope_up", "slope_down", "stairs_up", "stairs_down", "wave"]
EXT_SEEDS = [1001, 1002, 1003, 1004]
CKPT_BYTES = 26367183
PIN_FILES = ["q_eval_cmdr.py", "q_eval.py", "q_metrics.py", "q_post.py", "gpu_guard.py",
             "isaac_slot_v3.py", "usd_isolate_run_v3.py"]
# the evaluator keeps its own ALL_CELLS order whatever order --cells gives (q_eval_cmdr.py ALL_CELLS)
EVAL_ORDER = ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "fwd10", "back03", "left03", "right03", "yawL05", "yawR05"]
DUR_S = {"stand": 10.0, "stop03": 10.0}  # every other cell 20 s (q_eval_cmdr.py ALL_CELLS)
P0, DEADLINE = None, None
ATTEMPT_START = time.time()
CHILD_LAUNCHES = [0]
TREE_ABORT = [None]


def in_eval_order(cells):
    return [c for c in EVAL_ORDER if c in cells]
ap = argparse.ArgumentParser(allow_abbrev=False)
ap.add_argument("--manifest", required=True)
ap.add_argument("--expect_self_sha", required=True)
ap.add_argument("--approved_digest")
ap.add_argument("--gpu", type=int, choices=(0, 1))
ap.add_argument("--plan", choices=("A", "B", "remeasure"), default="A")
ap.add_argument("--cpu_plan", action="store_true", help="print registered A jobs without launching a child")
ap.add_argument("--order", choices=("orig", "24first"), default="24first")
ap.add_argument("--log", default="s1043A_base", help="log name in registered data root")
ap.add_argument("--base_log", default="s1043A_base")
args = ap.parse_args()
MANIFEST = load(args.manifest)
CONTRACT = MANIFEST["contract"]
ROOT = str(Path(CONTRACT["deployment"]["source_eval"]).parent)
OUT = CONTRACT["paths"]["data"]
B = os.path.dirname(os.path.dirname(CONTRACT["inputs"][CONTRACT["branches"]["off"]["result"]]["path"]))
E1 = os.path.dirname(CONTRACT["parent"]["path"])
E1_YAML = CONTRACT["inputs"]["parent_env_yaml"]["path"]
MODELS = {"p20000": (CONTRACT["parent"]["path"], 20000)}
for _arm in ("off", "on"):
    for _it in (22000, 24000):
        _name = CONTRACT["branches"][_arm][f"model_{_it}"]
        MODELS[f"{_arm}{_it}"] = (CONTRACT["inputs"][_name]["path"], _it)
GPU = str(args.gpu if args.gpu is not None else CONTRACT["device"]["gpu_index"])
GPU_UUID = str(CONTRACT["device"]["gpu_uuid"]).removeprefix("GPU-")
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES=str(MANIFEST["execution"].get("CUDA_VISIBLE_DEVICES", UNDECIDED)), OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
LOGF = os.path.join(OUT, f"{args.log}.json")
BASEF = os.path.join(OUT, f"{args.base_log}.json")
VERSION = "1043-A1"
EXPERIMENT = CONTRACT["experiment"]
ATTEMPT = MANIFEST["execution"].get("attempt", UNDECIDED)
JOBN = [0]
OUT_FILES = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": VERSION, "experiment": EXPERIMENT, "args": vars(args), "attempt": ATTEMPT,
       "approval_id": MANIFEST["execution"].get("approval_id", UNDECIDED),
       "approval_sha256": MANIFEST["execution"].get("approval_sha256", UNDECIDED),
       "contract_sha256": MANIFEST["contract_sha256"], "stage": MANIFEST["execution"].get("stage", "UNDECIDED"),
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
    p = {}
    for name, rec in CONTRACT["inputs"].items():
        if name.startswith(("source_", "config_")):
            now = sha(rec["path"])
            assert now == rec["sha256"], f"registered code changed: {name}"
            p[name.removeprefix("source_").removeprefix("config_")] = now
    for filename in ("s1043_manifest.py", "cmdr_bundle_compare_s1043.py",
                     "cmdr_eval_driver_s1043.py", "cmdr_post_s1043.py", "frozen_exec_s1043.py"):
        path = os.path.join(HERE, filename)
        p[filename] = sha(path)
    p["manifest_s1043.json"] = sha(args.manifest)
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
    """Both 1043 branches and their registered end evidence must still match."""
    errors = check_inputs(MANIFEST)
    if errors:
        return "; ".join(errors[:5])
    try:
        rep = json.load(open(CONTRACT["paths"]["compare_report"], encoding="utf-8"))
        if rep.get("verdict") != "SAME" or rep.get("contract_sha256") != MANIFEST["contract_sha256"]:
            return "1043 bundle comparison not SAME for registered contract"
        expected = {f"{arm}_{fn}": CONTRACT["inputs"][CONTRACT["branches"][arm]["bundle_json" if fn == "bundle.json" else "bundle_npz"]]["sha256"]
                    for arm in ("off", "on") for fn in ("bundle.json", "bundle.npz")}
        if rep.get("bundle_sha256") != expected:
            return "1043 bundle comparison bytes mismatch"
    except (OSError, ValueError, KeyError, TypeError):
        return "1043 bundle comparison unreadable"
    if training_running():
        return "branch_run.py still running"
    return ""


def other_log(argv):
    """the --log value another cmdr_eval_driver*.py process was started with, parsed the way argparse would
    (--log X, --log=X, a unique prefix of --log); None when absent (v3.2: always cmdr_eval_driver)."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--log", default="s1043A_base")
    p.add_argument("--base_log", default="s1043A_base")
    try:
        known, _ = p.parse_known_args(argv)
    except SystemExit:
        return None
    return known.log


def other_manifest(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--manifest")
    try:
        known, _ = parser.parse_known_args(argv)
    except SystemExit:
        return None
    return known.manifest


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
        manifest_path = other_manifest(c[k + 1:])
        if not manifest_path:
            out.append(info.get("pid"))
            continue
        try:
            other_m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            if other_m.get("contract_sha256") != canonical_hash(other_m["contract"]):
                raise ValueError("other writer manifest hash")
            assert_isolated(other_m)
            other_root = other_m["contract"]["paths"]["data"]
        except (ValueError, IndexError, OSError, KeyError):
            out.append(info.get("pid"))
            continue
        other_path = os.path.normcase(os.path.realpath(os.path.join(other_root, f"{lg}.json"))) if lg else None
        if lg is None or other_path == os.path.normcase(os.path.realpath(want)):
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


def claim_approval():
    """Reserve a single start under write_root. mkdir is the atomic race gate.

    A crash after reservation leaves the approval spent. No second process may
    interpret a partial claim as unused budget.
    """
    e = MANIFEST["execution"]
    if e["log_name"] != args.log or e["attempt"] != ATTEMPT:
        raise RuntimeError("approval attempt or log mismatch")
    root = Path(CONTRACT["deployment"]["write_root"]) / "approval_ledger"
    root.mkdir(parents=True, exist_ok=True)
    claim_dir = root / e["approval_id"]
    if not inside(claim_dir, CONTRACT["deployment"]["write_root"]):
        raise RuntimeError("approval ledger outside write root")
    try:
        claim_dir.mkdir()
    except FileExistsError as ex:
        raise RuntimeError("approval already used") from ex
    claim = {"approval_id": e["approval_id"], "approval_sha256": e["approval_sha256"],
             "attempt": ATTEMPT, "log_name": args.log, "log_path": LOGF,
             "risk_limit": e["risk_limit"], "pid": os.getpid(),
             "claimed_at": time.time(), "restart_scope": e["restart_scope"]}
    tmp = claim_dir / f"claim.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(claim, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, claim_dir / "claim.json")
    return claim_dir / "claim.json"


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
    input_name = "parent_model" if m == "p20000" else CONTRACT["branches"][m[:3] if m.startswith("off") else "on"][f"model_{m[-5:]}"]
    if sha(p) != CONTRACT["inputs"][input_name]["sha256"]:
        LOG["ckpt"].setdefault(m, {})["blocked"] = "registered checkpoint hash mismatch"
        save()
        return False
    if m != "p20000" and training_done():
        LOG["ckpt"].setdefault(m, {})["blocked"] = "both 1043 branches or comparison incomplete"
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


PARTICIPANT = "cmdr_eval_driver_s1043.py"
# 16h 3.1: a participant is this very file (same real path, so the same HERE/out/isaac_convert.lock), not any copy with
# the same name in another folder, which would hold a different lock.
SELF_PATH = os.path.normcase(os.path.realpath(os.path.abspath(__file__)))
CONVERT_LOCK = "isaac_convert.lock"
CONVERT_DONE = "[INFO]: Time taken for scene creation"
ROOT_REF = "</World/envs/env_0/Robot>: Unresolved reference"
USD_RE = re.compile(r"((?:[A-Za-z]:[/\\]|/)[^@\s\"']*?[/\\]IsaacLab[/\\]usd_\d{8}_\d{6}_\d+)")


def usd_key(path):
    return os.path.normcase(os.path.normpath(path)).casefold()
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
        d["ppid"], d["create_time"], d["cwd"] = (pm.get(d["pid"]) if pm is not None else None), None, None
        if n.startswith("python") or n.startswith("kit"):
            try:
                d["create_time"] = pr.create_time()
                if pm is None:
                    d["ppid"] = pr.ppid()
                if any(os.path.basename(x).lower() == PARTICIPANT for x in (d.get("cmdline") or [])):
                    d["cwd"] = pr.cwd()  # to resolve a relative script path (16h 3.1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        out.append(d)
    return out


def _is_participant(p):
    """True only when the process runs this same driver file (real path equal to SELF_PATH). A relative script path
    is resolved against the process's cwd; when that cannot be read the process is not trusted."""
    for x in (p.get("cmdline") or []):
        if os.path.basename(x).lower() != PARTICIPANT:
            continue
        if not os.path.isabs(x) and not p.get("cwd"):
            return False
        return os.path.normcase(os.path.realpath(os.path.join(p.get("cwd") or "", x))) == SELF_PATH
    return False


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
        if not c:  # None (cannot read) or [] (16h 3.1: an empty argv is not proof of an unrelated python)
            out.append(f"unknown:{p['pid']}")
            continue
        if not _isaac_like(c):
            continue
        cur, seen, part = p, set(), False
        while cur is not None and cur["pid"] not in seen:
            seen.add(cur["pid"])
            if _is_participant(cur):
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
    if time.time() - ATTEMPT_START > MANIFEST["execution"]["risk_limit"]["max_wall_s"]:
        LOG["stopped"] = f"risk wall limit before {where}"
        save()
        sys.exit(2)
    if stop_requested():
        LOG["stopped"] = f"stop file before {where}"
        save()
        say(f"STOP FILE before {where}")
        sys.exit(7)
    problems = launch_errors(MANIFEST, approved_digest=args.approved_digest)
    if problems:
        LOG["stopped"] = f"contract or input changed before {where}: {problems[:3]}"
        save()
        say(f"FROZEN INPUT before {where}: {problems[:3]}")
        sys.exit(4)
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


def release_run_lease(f):
    import msvcrt
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    f.close()


def wait_child_tree(p, poll_s=0.05, observer=None, *, wall_deadline=None,
                    stop_check=None, terminate_grace_s=0.5):
    """Watch the owned tree and retain the lease through confirmed termination.

    deadline_epoch only bars a start. wall_deadline is a force limit on this
    attempt. A PID is signalled only when its creation time still matches the
    descendant we observed; inaccessible descendants keep the lease held.
    """
    try:
        born = psutil.Process(p.pid).create_time()
    except psutil.NoSuchProcess:
        born = None
    known = {p.pid: born}
    abort_reason = None
    terminate_at = None
    sent_terminate = set()
    while True:
        p.poll()
        pm_fn = getattr(psutil, "_ppid_map", None)
        pm = pm_fn() if pm_fn else {x.info["pid"]: x.info["ppid"] for x in psutil.process_iter(["pid", "ppid"])}
        for pid, ppid in pm.items():
            if ppid in known and pid not in known:
                try:
                    child_born = psutil.Process(pid).create_time()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    child_born = None
                if known[ppid] is None or child_born is None or child_born >= known[ppid]:
                    known[pid] = child_born
        live = []
        for pid, born in known.items():
            if pid == p.pid and p.poll() is not None:
                continue
            try:
                proc = psutil.Process(pid)
                if (born is None or abs(proc.create_time() - born) < 0.01) and proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    live.append(pid)
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                if pid != p.pid:
                    live.append(pid)  # unknown child state must not release the lease
        if observer is not None:
            observer(dict(known), list(live))
        if not live:
            actual_rc = p.wait()
            if abort_reason is None and wall_deadline is not None and time.time() >= wall_deadline:
                abort_reason = "wall_limit"
                TREE_ABORT[0] = abort_reason
            return {"wall_limit": 124, "stop_file": 125}.get(abort_reason, actual_rc)
        if abort_reason is None:
            if stop_check is not None and stop_check():
                abort_reason = "stop_file"
            elif wall_deadline is not None and time.time() >= wall_deadline:
                abort_reason = "wall_limit"
            if abort_reason:
                TREE_ABORT[0] = abort_reason
                terminate_at = time.time()
        if abort_reason:
            force = time.time() - terminate_at >= terminate_grace_s
            for pid in reversed(live):
                try:
                    proc = psutil.Process(pid)
                    born_at = known[pid]
                    if born_at is None or abs(proc.create_time() - born_at) >= 0.01:
                        continue  # PID ownership uncertain: hold the lease, do not signal it
                    if force:
                        proc.kill()
                    elif pid not in sent_terminate:
                        proc.terminate()
                        sent_terminate.add(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        time.sleep(poll_s)


def run_lease(where, ck=None, sleep=time.sleep):
    """Separate global Isaac lease, held until the slot child tree has exited."""
    import msvcrt
    path = CONTRACT["paths"]["run_lease"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    while True:
        gate(where, ck)
        f = open(path, "a+b")
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            sleep(2)
            continue
        foreign = foreign_isaac()
        if foreign:
            release_run_lease(f)
            raise RuntimeError(f"unregistered or unknown Isaac process: {foreign[:8]}")
        return f


def gpu_preflight():
    """Read physical index, UUID and free memory immediately before an Isaac child."""
    result = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError("GPU probe failed")
    rows = [list(map(str.strip, line.split(","))) for line in result.stdout.splitlines()]
    row = next((r for r in rows if len(r) == 3 and r[0] == GPU), None)
    if row is None or row[1].removeprefix("GPU-") != GPU_UUID:
        raise RuntimeError("physical GPU index or UUID mismatch")
    if int(row[2]) < CONTRACT["device"]["min_free_mib"]:
        raise RuntimeError(f"GPU free {row[2]} MiB below floor")
    if ENV.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or ENV.get("CUDA_VISIBLE_DEVICES") != GPU:
        raise RuntimeError("child CUDA environment mismatch")
    return {"gpu_index": GPU, "uuid": row[1], "free_mib": int(row[2])}


def _log_text(name):
    try:
        with open(os.path.join(OUT, f"{name}.log"), encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def root_ref_failed(name):
    return ROOT_REF in _log_text(name)


def usd_dirs_of(name):
    return sorted({usd_key(m.group(1)) for m in USD_RE.finditer(_log_text(name))})


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
                    USD_IDX[rel] = (key, frozenset(usd_key(m.group(1)) for m in USD_RE.finditer(fh.read())))
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
    dirs = sorted({usd_key(m.group(1)) for x in L for m in USD_RE.finditer(x)})
    if len(dirs) != 1:
        return f"USD folders named in the log: {len(dirs)}"
    mk = next((i for i, x in enumerate(L) if CONVERT_DONE in x), None)
    if mk is None:
        return "no scene-creation line"
    if any(USD_RE.search(x) or IMPORTER in x for x in L[mk + 1:]):
        return "USD conversion output after the scene-creation line"
    others = sorted(r for r in usd_index().get(dirs[0], ()) if r != f"{tag}.log")
    if others:
        return f"USD temp folder {dirs[0]} shared with {others[:3]}"
    return ""


def _free(p):
    """p, or p.1, p.2 ...: earlier evidence is never replaced (two tries of one name can end within the same second)."""
    q_, i_ = p, 0
    while os.path.exists(q_):
        i_ += 1
        q_ = f"{p}.{i_}"
    return q_


def _origin_of(prev, reused):
    """(o2) where a run's output hashes come from. A new run: hashed-at-collection. A reused run keeps an explicit origin;
    without one, a stamp with no stamp_version is v3.2; a v3.3-v3.6 stamp that carries attempt "v3.2 or earlier" is a
    v3.2 run those versions re-validated (16h 3.2); a stamp whose attempt is a real job id (g<gpu>-<pid>-<start>-j<n>)
    was hashed when it was measured; anything else is "origin unknown"."""
    if not reused:
        return "hashed-at-collection"
    if prev.get("origin"):
        return prev["origin"]
    if "stamp_version" not in prev or prev.get("attempt") == "v3.2 or earlier":
        return "legacy-origin revalidated"
    if re.fullmatch(r"g[01]-\d+-\d{10}-j\d+", str(prev.get("attempt", ""))):
        return "hashed-at-collection"
    return "origin unknown"


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
    tries = min(tries, MANIFEST["execution"]["risk_limit"]["max_retries_per_run"] + 1)
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
        lease = run_lease(f"{name} try {k}", ck)
        p = None
        t0 = time.time()
        try:
            gate(f"{name} try {k} lease held", ck)
            preflight = gpu_preflight()
            attempt_name = f"{ATTEMPT}-{name}-try{k}"
            usd_root = os.path.join(CONTRACT["paths"]["work"], "usd", attempt_name)
            log_file = os.path.join(OUT, name + ".log")
            guard_file = os.path.join(OUT, name + ".guard.json")
            slot_file = os.path.join(OUT, name + ".slot.json")
            for target in (usd_root, log_file, guard_file, slot_file):
                if not inside(target):
                    raise RuntimeError(f"write path outside codexE: {target}")
            source_eval = CONTRACT["deployment"]["source_eval"]
            isolated = [PY, CONTRACT["inputs"]["source_usd_isolate_run_v3.py"]["path"]] + cmd[1:]
            guard = [PY, CONTRACT["inputs"]["source_gpu_guard.py"]["path"], "--gpu", GPU,
                     "--min_free_mib", str(CONTRACT["device"]["min_free_mib"]),
                     "--log", log_file, "--summary", guard_file, "--"] + isolated
            frozen = [PY, os.path.join(HERE, "frozen_exec_s1043.py"), "--manifest", args.manifest,
                      "--approved_digest", args.approved_digest,
                      "--checkpoint_label", ck or "p20000", "--expect_self_sha",
                      MANIFEST["execution"]["candidate_hashes"]["frozen_exec_s1043.py"], "--"] + guard
            scan = [OUT, B, os.path.join(source_eval, "out"), os.path.join(source_eval, "out_branch"),
                    os.path.join(source_eval, "out_uncr"), os.path.join(source_eval, "out_uncr_v6"),
                    os.path.join(source_eval, "out_ce12", "native"), os.path.join(source_eval, "out_rand")]
            slot_cmd = [PY, CONTRACT["inputs"]["source_isaac_slot_v3.py"]["path"], "--watch_log", log_file,
                        "--record", slot_file, "--usd_root", usd_root, "--attempt", attempt_name,
                        "--lock", CONTRACT["paths"]["convert_lock"],
                        "--registry", CONTRACT["paths"]["registry"],
                        "--scan_dirs", ",".join(scan), "--stop_file", CONTRACT["paths"]["stop"],
                        "--deadline", str(DEADLINE), "--expect_conversions", CONTRACT["device"]["expect_conversions"],
                        "--"] + frozen
            os.makedirs(OUT, exist_ok=True)
            os.makedirs(os.path.dirname(CONTRACT["paths"]["registry"]), exist_ok=True)
            os.makedirs(usd_root, exist_ok=False)
            gate(f"{name} try {k} launch", ck)
            if CHILD_LAUNCHES[0] >= MANIFEST["execution"]["risk_limit"]["max_child_launches"]:
                raise RuntimeError("risk child launch limit")
            CHILD_LAUNCHES[0] += 1
            p = POPEN(slot_cmd, cwd=source_eval, env=ENV)
            policy = MANIFEST["execution"]["termination_policy"]
            rc = wait_child_tree(
                p, wall_deadline=ATTEMPT_START + MANIFEST["execution"]["risk_limit"]["max_wall_s"],
                stop_check=stop_requested, terminate_grace_s=policy["terminate_grace_s"])
        finally:
            if p is not None:
                wait_child_tree(p)
            release_run_lease(lease)
        try:
            slot_record = json.load(open(slot_file, encoding="utf-8"))
        except (OSError, ValueError):
            slot_record = {"slot_rc": rc, "state_at_release": "missing slot record"}
        tr = {"try": k, "rc": rc, "s": round(time.time() - t0), "earlier_moved": kept,
              "abort_reason": TREE_ABORT[0], "partial_result": "held" if TREE_ABORT[0] else None,
              "slot": {"state": slot_record.get("state_at_release"), "held_s": slot_record.get("hold_s"),
                       "rc": slot_record.get("slot_rc")}, "gpu_preflight": preflight, "usd_dir": usd_dirs_of(name)}
        TRIES.setdefault(name, []).append(tr)
        if TREE_ABORT[0]:
            LOG["stopped"] = TREE_ABORT[0]
            save()
            TREE_ABORT[0] = None
        say(f"RUN {name} try {k} EXIT {rc} {time.time() - t0:.0f}s · slot {tr['slot']} · usd {tr['usd_dir']}")
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
    cmd = [PY, CONTRACT["inputs"][f"source_{script}"]["path"], "--headless", "--tag", tag, "--policy", "student",
           "--checkpoint", model_path, "--outdir", OUT, "--families", fam, "--cells", cells,
           "--episodes", str(episodes), "--eval_seed", str(seed), "--difficulty", "0.5",
           "--terrain_set", "train", "--heading_hold", "0", "--spawn_offset", ""]
    if small:
        cmd.append("--physx_small_buffers")
    if noise:
        cmd.append("--obs_noise")
    if os.path.normcase(os.path.abspath(model_path)) != os.path.normcase(os.path.abspath(MODELS["p20000"][0])):
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
        if str(g.get("gpu_index")) != GPU or str(g.get("gpu_uuid", "")).removeprefix("GPU-") != GPU_UUID:
            return "guard physical GPU identity"
        slot = json.load(open(os.path.join(OUT, f"{tag}.slot.json"), encoding="utf-8"))
        if (slot.get("slot_rc") != 0 or slot.get("registry") != CONTRACT["paths"]["registry"] or
                slot.get("lock") != CONTRACT["paths"]["convert_lock"] or
                slot.get("expect_conversions") != CONTRACT["device"]["expect_conversions"] or
                not inside(slot.get("usd_root", ""))):
            return "slot v3 registry, lock, USD root or exit"
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
                "difficulty": 0.5, "terrain_set": "train", "heading_hold": 0.0, "spawn_offset": "", "policy": "student",
                "outdir": OUT}
        for k, v in want.items():
            if a.get(k) != v:
                return f"arg {k}={a.get(k)!r} want {v!r}"
        if m.get("checkpoint_sha256") != ckpt_sha:
            return "checkpoint sha256"
        # The pinned original q_eval.py omits loaded_iter. An explicitly
        # recorded but wrong iteration is still an error for either evaluator.
        if (need_iter or "loaded_iter" in m) and m.get("loaded_iter") != it:
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
            arm = next((arm for arm in ("off", "on") if ckpt_sha in
                        (CONTRACT["inputs"][CONTRACT["branches"][arm][f"model_{it}"]]["sha256"],)), None)
            if arm is None or s["bundle_json_sha256"] != CONTRACT["inputs"][CONTRACT["branches"][arm]["bundle_json"]]["sha256"] \
                    or s.get("bundle_npz_sha256") != CONTRACT["inputs"][CONTRACT["branches"][arm]["bundle_npz"]]["sha256"]:
                return "branch bundle differs from registration"
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
        if CONTRACT["evaluation"].get("mae_missing_policy") != "invalidate_entire_run":
            return "MAE policy undecided"
        for row in rows:
            for axis in ("vx", "vy", "wz"):
                try:
                    if not math.isfinite(float(row[f"mae_{axis}"])):
                        return f"nonfinite mae_{axis}: invalid run"
                except (ValueError, KeyError, TypeError):
                    return f"missing mae_{axis}: invalid run"
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
    """Reuse only a prior new 1043 collection under this exact contract and pins."""
    st = old_stamp(tag)
    if (not st or st.get("pins") != P or st.get("stamp_version") != VERSION or
            st.get("experiment") != EXPERIMENT or st.get("contract_sha256") != MANIFEST["contract_sha256"] or
            st.get("stage") != "A" or st.get("origin") != "hashed-at-collection" or not st.get("attempt")):
        return False
    if not isinstance(st.get("out_sha256"), dict):
        return False
    try:
        return st["out_sha256"] == outhash(tag)
    except FileNotFoundError:
        return False


def write_stamp(tag, P, extra):
    p = os.path.join(OUT, tag, "driver_stamp.json")
    tmp = p + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"pins": P, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "stamp_version": VERSION,
                   "experiment": EXPERIMENT, "contract_sha256": MANIFEST["contract_sha256"], "stage": "A", **extra}, f, indent=1)
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
    rc, _ = guarded(t, q("q_eval_cmdr.py", t, MODELS["p20000"][0], "flat", ",".join(sc), 10, True, 1000), ck="p20000")
    why = validate(t, psha, 20000, "flat", sc, 10, True, 1000, False) if rc == 0 else f"exit {rc}"
    LOG["tests"]["smoke"] = why or "ok"
    save()
    if why:
        return False
    # 2. known answer: q_eval.py vs q_eval_cmdr.py, same input; if different, q_eval.py vs q_eval.py tells
    #    non-determinism from a copy fault (ASTRA 8 2)
    LOG["tests"]["q_eval_py_sha256"] = sha(CONTRACT["inputs"]["source_q_eval.py"]["path"])
    a, b = f"cq_test_{pin8}_ka_orig", f"cq_test_{pin8}_ka_copy"
    for tag, script in ((a, "q_eval.py"), (b, "q_eval_cmdr.py")):
        rc, _ = guarded(tag, q(script, tag, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000), ck="p20000")
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
        guarded(a2, q("q_eval.py", a2, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000), ck="p20000")
        LOG["tests"]["known_answer"]["orig_vs_orig_same"] = same(a, a2)
        save()
        return False
    save()
    # 2b. small PhysX buffers must not change the physics on the flat training terrain (copy, default buffers vs small)
    c2 = f"cq_test_{pin8}_ka_copy_default_buffers"
    rc, _ = guarded(c2, q("q_eval_cmdr.py", c2, MODELS["p20000"][0], "flat", "stop03", 100, True, 1000, small=False), ck="p20000")
    ok2 = rc == 0 and same(b, c2)
    LOG["tests"]["small_buffers_vs_default_same"] = ok2
    save()
    if not ok2:
        return False
    # 3. branch path must refuse a wrong train_yaml: another run's env.yaml, and a sibling file of the right folder
    g = MODELS["off24000"][0]
    gsha = sha(g)
    other_yaml = CONTRACT["startup_tests"]["other_run_yaml"]
    for name, bad in (("other_run", other_yaml), ("sibling", CONTRACT["inputs"]["parent_agent_yaml"]["path"])):
        t = f"cq_test_{pin8}_wrong_yaml_{name}"
        rc, _ = guarded(t, q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True, 1000, train_yaml=bad), tries=1, ck="off24000")
        log = open(os.path.join(OUT, f"{t}.log"), encoding="utf-8", errors="replace").read()
        wrote = os.path.exists(os.path.join(OUT, t, "cells.json")) or os.path.exists(os.path.join(OUT, t, "traj.npz"))
        refused = rc != 0 and "AssertionError: train_yaml is not the parent run's" in log and not wrote
        LOG["tests"][f"wrong_yaml_{name}"] = {"exit": rc, "refused": refused, "wrote_result": wrote}
        save()
        if not refused:
            return False
    # 4. registered 1043 off and on checkpoints pass with the exact parent yaml and bundle hashes
    t = f"cq_test_{pin8}_branch_off24000"
    rc, _ = guarded(t, q("q_eval_cmdr.py", t, g, "flat", "stop03", 10, True, 1000), ck="off24000")
    why = validate(t, gsha, 24000, "flat", ["stop03"], 10, True, 1000, True) if rc == 0 else f"exit {rc}"
    LOG["tests"]["branch_off_pass"] = why or "ok"
    save()
    if why:
        return False
    t_on = f"cq_test_{pin8}_branch_on24000"
    rc, _ = guarded(t_on, q("q_eval_cmdr.py", t_on, MODELS["on24000"][0], "flat", "stop03", 10, True, 1000), ck="on24000")
    why = validate(t_on, sha(MODELS["on24000"][0]), 24000, "flat", ["stop03"], 10, True, 1000, True) if rc == 0 else f"exit {rc}"
    if not why and fingerprint(t) != fingerprint(t_on):
        why = "1043 off/on startup fingerprint mismatch"
    LOG["tests"]["branch_on_pass"] = why or "ok"
    save()
    return not why


def jobs():
    """First release owns exactly the 45 registered A jobs."""
    return [(m, fam, cell, noise == "on", seed) for m, fam, cell, noise, seed in CONTRACT["plan"]["A"]]


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
    u = sorted({(fam, cell, noise == "on") for (m, fam, cell, noise, seed) in CONTRACT["plan"]["base"] if seed == 1000})
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
    return os.path.exists(CONTRACT["paths"]["stop"])


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


DEADLINE = (float(MANIFEST["execution"]["deadline_epoch"])
            if isinstance(MANIFEST["execution"].get("deadline_epoch"), (int, float)) else 0.0)


def start():
    """checks before any run; sets P0. Exits (non-zero) instead of risking a second writer."""
    global P0
    if args.plan != "A":
        say("B and remeasure are disabled in this candidate")
        sys.exit(8)
    w = driver_writers(args.log)
    if w:
        say(f"another driver writes out/{args.log}.json (pids {w}): not starting")
        sys.exit(6)
    if not take_lock():
        say(f"out/{args.log}.lock is held by another process: not starting")
        sys.exit(6)
    claim_approval()
    OWNED[0] = True
    if args.plan == "remeasure":
        PUBLISH[0] = True
    set_attempt("revalidating")
    P0 = pins()
    LOG["pins"] = P0
    LOG["code_sha256"] = {"driver": sha(os.path.abspath(__file__))}
    save()
    say(f"pins {len(P0)} files · q_eval_cmdr {P0['q_eval_cmdr.py'][:16]} · attempt {ATTEMPT}")
    mine = {tagof(*j) for j in jobs()}
    while unseen_running() or live_runs(mine):
        if time.time() > DEADLINE:
            say("deadline while waiting for the unseen driver or a live run of this plan")
            sys.exit(2)
        say(f"waiting: unseen {unseen_running()} · live runs of this plan {live_runs(mine)[:3]}")
        time.sleep(30)
    ok = 0
    while ok < 2:  # both branches and their bytes stable at two observations
        why = training_done()
        ok = ok + 1 if not why else 0
        if why:
            if time.time() > DEADLINE:
                say(f"deadline while waiting for registered 1043 pair: {why}")
                sys.exit(2)
            say(f"1043 pair not handed over yet: {why}")
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
    branch = m != "p20000"
    prev = old_stamp(tag)
    moved = None
    sp_ = os.path.join(OUT, tag, "driver_stamp.json")
    prev_sha = sha(sp_) if os.path.exists(sp_) else None  # (o2) the stamp this run had before, kept by hash
    if stamp_ok(tag, P0) and not validate(tag, LOG["ckpt"][m]["sha256"], it, fam, [cell], 100, noise, seed, branch):
        why, reused = "", True
        attempt = prev["attempt"]
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
    origin = {"origin": _origin_of(prev, reused)} if not reused else {
        "origin": _origin_of(prev, reused),
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


def diagnostic_record(key, item, tag, rc, tries, why):
    """Use one evidence shape for base, repeat, held and failed runs."""
    tr = TRIES.get(tag, [{}])[-1]
    d = Path(OUT) / tag
    rec = {"tag": tag, "evaluator": item["evaluator"], "small_buffers": item["small"],
           "status": "failed" if rc else ("held" if why else "valid"), "why": why or None,
           "rc": rc, "tries": tries, "try_records": TRIES.get(tag, []),
           "wall_s": tr.get("s"), "preflight": tr.get("gpu_preflight"),
           "max_used_mib": None, "min_free_mib": None,
           "guard_peak_scope": "whole_device_not_job_dedicated",
           "guard_exit": None, "guard_stopped": None,
           "cells_sha256": None, "traj_sha256": None, "fingerprint": None,
           "terrain_mesh": None, "terrain_origins_sha256": None, "pairing_sha256": None,
           "reset": CONTRACT["evaluation"]["reset"], "reset_meta": None,
           "episode_args": None, "inputs_sha256": {k: v["sha256"] for k, v in CONTRACT["inputs"].items()}}
    try:
        guard_record = json.loads((Path(OUT) / f"{tag}.guard.json").read_text(encoding="utf-8"))
        rec.update(max_used_mib=guard_record.get("max_used_mib"), min_free_mib=guard_record.get("min_free_mib"),
                   guard_exit=guard_record.get("exit_code"), guard_stopped=guard_record.get("stopped_by_guard"))
    except (OSError, ValueError):
        pass
    try:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        rec.update(terrain_mesh=meta.get("terrain_mesh"),
                   terrain_origins_sha256=meta.get("terrain_origins_sha256"),
                   pairing_sha256=meta.get("pairing_sha256"), reset_meta=meta.get("eval_changes"),
                   episode_args={k: meta.get("args", {}).get(k) for k in
                                 ("families", "cells", "episodes", "eval_seed", "spawn_offset", "physx_small_buffers")})
        if (d / "cells.json").is_file():
            rec["cells_sha256"] = sha(d / "cells.json")
        if (d / "traj.npz").is_file():
            rec["traj_sha256"] = sha(d / "traj.npz")
        if not why:
            rec["fingerprint"] = fingerprint(tag)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return rec


def diagnostic_compare_pair(left, right):
    semantic = json.loads((left / "cells.json").read_text(encoding="utf-8")) == json.loads((right / "cells.json").read_text(encoding="utf-8"))
    json_sha = sha(left / "cells.json") == sha(right / "cells.json")
    traj_sha = sha(left / "traj.npz") == sha(right / "traj.npz")
    reason = ("equal" if semantic and json_sha and traj_sha else
              "byte_only_json" if semantic and traj_sha and not json_sha else
              "semantic_mismatch" if not semantic else "trajectory_bytes_mismatch")
    return {"semantic_equal": semantic, "json_sha_equal": json_sha,
            "traj_sha_equal": traj_sha, "reason_code": reason}


def main_diagnostic():
    """Three parent-only measurements, then stop. No A job is scheduled here."""
    if MANIFEST["execution"]["stage"] != "diagnostic":
        raise RuntimeError("diagnostic approval required")
    PUBLISH[0] = True
    set_attempt("running")
    spec = CONTRACT["diagnostic"]
    pin8 = hashlib.sha256(json.dumps(P0, sort_keys=True).encode()).hexdigest()[:8] + f"_g{GPU}t{time.strftime('%H%M%S')}p{os.getpid()}"
    report = {"schema": "s1043-diagnostic-1", "status": "running", "stage": "diagnostic",
              "contract_sha256": MANIFEST["contract_sha256"], "attempt": ATTEMPT,
              "code_sha256": {k: v for k, v in P0.items() if k.endswith(".py")},
              "inputs_sha256": {k: v["sha256"] for k, v in CONTRACT["inputs"].items()},
              "device": {"physical_index": CONTRACT["device"]["gpu_index"],
                         "logical_index": CONTRACT["device"]["child_logical_cuda"],
                         "uuid": CONTRACT["device"]["gpu_uuid"],
                         "CUDA_VISIBLE_DEVICES": MANIFEST["execution"]["CUDA_VISIBLE_DEVICES"]},
              "reset": CONTRACT["evaluation"]["reset"], "terrain": CONTRACT["evaluation"]["terrain"],
              "episodes": spec["episodes"], "runs": {}, "comparisons": {}, "A_started": False,
              "comparison_pass_rule_decision": MANIFEST["execution"].get("comparison_pass_rule", UNDECIDED),
              "applied_comparison_rule": "semantic_and_json_bytes_and_traj_bytes",
              "guard_peak_scope": "whole_device_not_job_dedicated"}
    path = Path(CONTRACT["paths"]["reports"]) / f"diagnostic_{ATTEMPT}.json"
    def publish():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        LOG["diagnostic_report"] = str(path)
        save()
    publish()
    run_order = ["orig", "small", "default"]
    for key in run_order:
        item = spec["runs"][key]
        tag = f"{spec['tag_prefix']}{pin8}_{key}"
        cmd = q(item["evaluator"], tag, MODELS["p20000"][0], spec["family"], spec["cell"],
                spec["episodes"], True, spec["eval_seed"], small=item["small"])
        rc, tries = guarded(tag, cmd, ck="p20000")
        why = validate(tag, LOG["ckpt"]["p20000"]["sha256"], 20000, spec["family"],
                       [spec["cell"]], spec["episodes"], True, spec["eval_seed"], False,
                        need_iter=item["evaluator"] != "q_eval.py", small=item["small"]) if rc == 0 else f"exit {rc}"
        report["runs"][key] = diagnostic_record(key, item, tag, rc, tries, why)
        publish()
        if why:
            break
    if all(report["runs"].get(k, {}).get("status") == "valid" for k in run_order):
        def compare_pair(left, right):
            a, b = report["runs"][left]["tag"], report["runs"][right]["tag"]
            da, db = Path(OUT) / a, Path(OUT) / b
            return diagnostic_compare_pair(da, db)
        report["comparisons"] = {"orig_vs_small": compare_pair("orig", "small"),
                                 "small_vs_default": compare_pair("small", "default")}
        matched = all(v["semantic_equal"] and v["json_sha_equal"] and v["traj_sha_equal"]
                      for v in report["comparisons"].values())
        if not matched and MANIFEST["execution"]["diagnostic_repeat_original"]:
            item = spec["runs"]["orig_repeat"]
            tag = f"{spec['tag_prefix']}{pin8}_orig_repeat"
            rc, tries = guarded(tag, q(item["evaluator"], tag, MODELS["p20000"][0], spec["family"],
                                   spec["cell"], spec["episodes"], True, spec["eval_seed"], small=item["small"]), ck="p20000")
            why = validate(tag, LOG["ckpt"]["p20000"]["sha256"], 20000, spec["family"], [spec["cell"]],
                            spec["episodes"], True, spec["eval_seed"], False,
                            need_iter=item["evaluator"] != "q_eval.py", small=item["small"]) if rc == 0 else f"exit {rc}"
            report["runs"]["orig_repeat"] = diagnostic_record("orig_repeat", item, tag, rc, tries, why)
            if not why:
                report["comparisons"]["orig_vs_repeat"] = compare_pair("orig", "orig_repeat")
        report["status"] = "completed" if matched else "held_mismatch"
    else:
        report["status"] = "held_incomplete"
    report["not_run"] = [k for k in run_order if k not in report["runs"]]
    report["held_runs"] = [k for k, v in report["runs"].items() if v["status"] == "held"]
    report["failed_runs"] = [k for k, v in report["runs"].items() if v["status"] == "failed"]
    report["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    publish()
    LOG["ended"] = report["completed_at"]
    LOG["end_kind"] = report["status"]
    LOG["complete"] = report["status"] == "completed"
    LOG["exit_code"] = 0 if LOG["complete"] else 3
    save()
    set_attempt("ended" if LOG["complete"] else "stopped")
    say(f"DIAGNOSTIC {report['status']} · A not started · report {path}")
    if not LOG["complete"]:
        sys.exit(3)


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
    print("sys.executable", sys.executable)
    print("candidate.__file__", __file__)
    print("candidate.sha256", sha(__file__))
    if (sha(__file__) != args.expect_self_sha or
            os.path.normcase(os.path.abspath(__file__)) != os.path.normcase(os.path.join(CONTRACT["deployment"]["candidate_dir"], "cmdr_eval_driver_s1043.py")) or
            os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(os.path.abspath(CONTRACT["runtime"]["python"]))):
        say("환경 불일치")
        sys.exit(3)
    print("ISOLATION", assert_isolated(MANIFEST))
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", args.log):
        say("unsafe log name")
        sys.exit(3)
    if args.plan != "A":
        say("B and remeasure disabled in first release")
        sys.exit(8)
    if MANIFEST["execution"].get("stage") == "diagnostic" and args.log == "s1043A_base" and not args.cpu_plan:
        say("diagnostic needs its own explicit --log")
        sys.exit(4)
    if args.gpu is not None and args.gpu != CONTRACT["device"]["gpu_index"] and not args.cpu_plan:
        say("CLI GPU differs from registered physical GPU")
        sys.exit(4)
    if args.cpu_plan:
        if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
            say("CPU plan requires CUDA_VISIBLE_DEVICES=-1")
            sys.exit(3)
        structural = check_inputs(MANIFEST, require_files=False)
        if structural:
            say(f"registered plan rejected: {structural[:5]}")
            sys.exit(4)
        plan = {"experiment": EXPERIMENT, "stage": MANIFEST["execution"].get("stage", "A"), "contract_sha256": MANIFEST["contract_sha256"],
                "A_count": len(jobs()), "A_tags": [tagof(*j) for j in jobs()],
                "B_remaining": len(CONTRACT["plan"]["B_remaining"]), "B_enabled": False,
                "write_paths": CONTRACT["paths"]}
        print(json.dumps(plan, ensure_ascii=False))
        return
    problems = launch_errors(MANIFEST, approved_digest=args.approved_digest)
    if problems:
        say(f"launch blocked: {problems[:8]}")
        sys.exit(4)
    os.makedirs(OUT, exist_ok=True)
    try:
        start()
        if MANIFEST["execution"]["stage"] == "diagnostic":
            main_diagnostic()
        else:
            main_base()
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
