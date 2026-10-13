"""Known-answer tests for compare_stand.py on a made-up out/ tree (lead 10/13, VERIFY-astra-16j 5.2). Exit 1 on any failure."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("COMPARE_SCRIPT", os.path.join(HERE, "compare_stand.py"))
TAG = "cq_on24000_flat_stand_on_s1000"
OUT4 = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
fails = []
ROOT = tempfile.mkdtemp(prefix="cst_", dir=HERE)


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:140], "want", repr(want)[:80])
    if not ok:
        fails.append(name)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run_folder(d):
    os.makedirs(d)
    json.dump({"args": {"x": 1}, "checks_pre": {}, "checks_run": {}, "N": 100, "T_steps": 500, "checkpoint_sha256": "C", "loaded_iter": 24000,
               "pairing_sha256": {"a": 1}, "pairing_sha256_ext": {"b": 1}, "terrain_mesh": {"t": 1}}, open(os.path.join(d, "meta.json"), "w"))
    json.dump([{"cell": "stand", "n": 100}], open(os.path.join(d, "cells.json"), "w"))
    open(os.path.join(d, "episodes.csv"), "w").write("episode,cell\n0,stand\n1,stand\n")
    np.savez(os.path.join(d, "traj.npz"), traj=np.zeros((3, 2, 12), np.float32))
    np.save(os.path.join(d, "env_origins.npy"), np.zeros((2, 3), np.float32))


def tree(name, mutate=None):
    out = os.path.join(ROOT, name)
    os.makedirs(out)
    old = os.path.join(out, "attempts", f"{TAG}.dir.1013113904.1")
    run_folder(old)
    json.dump({"pins": {"p": 1}, "ckpt_sha256": "C"}, open(os.path.join(old, "driver_stamp.json"), "w"))
    held = sha(os.path.join(old, "driver_stamp.json"))
    os.makedirs(os.path.join(out, "H"))
    json.dump({"runs": {TAG: {f: sha(os.path.join(old, f)) for f in OUT4 + ("env_origins.npy",)}}}, open(os.path.join(out, "H", "manifest.json"), "w"))
    json.dump({TAG: {"stamp_sha256": held, "why": "y", "handover": "H"}}, open(os.path.join(out, "cmdr_post_hold.json"), "w"))
    new = os.path.join(out, TAG)
    run_folder(new)
    h = {f: sha(os.path.join(new, f)) for f in OUT4}
    att = "g1-1-1013140618-j1"
    stamp = {"pins": {"p": 1}, "ckpt_sha256": "C", "stamp_version": "3.7", "attempt": att, "out_sha256": dict(h)}
    rec = {"tag": TAG, "valid": True, "reused": False, "attempt": att, "out_sha256": dict(h)}
    base = {"pins": {"p": 1}, "ckpt": {"on24000": {"sha256": "C"}}, "matrix": {TAG: "valid"}, "runs": [rec], "pair_fail": []}
    open(os.path.join(out, f"{TAG}.log"), "w").write(f"[Q-EVAL] done {TAG} N 100 rollout\n")
    if mutate:
        mutate(out, new, stamp, rec, base)
    json.dump(stamp, open(os.path.join(new, "driver_stamp.json"), "w"))
    json.dump(base, open(os.path.join(out, "cmdr_eval_driver.json"), "w"))
    r = subprocess.run([sys.executable, SCRIPT, TAG], capture_output=True, text=True, env=dict(os.environ, COMPARE_OUT=out), encoding="utf-8", errors="replace")
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        res = {"stderr": r.stderr[-300:]}
    return r.returncode, res


try:
    rc, res = tree("ok")
    check("S1 normal re-collection: ready, outputs equal, exit 0", (rc, res.get("comparison_ready"), res.get("output_content_equal")), (0, True, True))

    def zero_traj(out, new, stamp, rec, base):
        stamp["out_sha256"]["traj.npz"] = "0" * 64
        rec["out_sha256"]["traj.npz"] = "0" * 64
    rc, res = tree("zero", zero_traj)
    check("S2 (16j) record and stamp both claim another traj hash: not valid, on hold (exit 2)", (rc, res.get("new_run_valid")), (2, False))

    def drop_hashes(out, new, stamp, rec, base):
        stamp.pop("out_sha256")
        rec.pop("out_sha256")
    rc, res = tree("nohash", drop_hashes)
    check("S3 (16j) hashes missing on both sides (None == None): not valid", (rc, res.get("new_run_valid")), (2, False))

    def pair_fail(out, new, stamp, rec, base):
        rec["pair_fail"] = {"against": "x", "fields": ["traj0"]}
        base["matrix"][TAG] = "pair_fail"
    rc, res = tree("pair", pair_fail)
    check("S4 (16j) the new run failed pairing: not valid", (rc, res.get("new_run_valid")), (2, False))

    def old_changed(out, new, stamp, rec, base):
        open(os.path.join(out, "attempts", f"{TAG}.dir.1013113904.1", "episodes.csv"), "a").write("2,stand\n")
    rc, res = tree("oldchg", old_changed)
    check("S5 (16j) the preserved original no longer equals the hand-over bytes: on hold", (rc, res.get("old_equals_handover")), (2, False))

    def incomplete(out, new, stamp, rec, base):
        os.remove(os.path.join(new, "env_origins.npy"))
    rc, res = tree("inc", incomplete)
    check("S6 (16j) the new run is still incomplete: not ready, nothing compared", (rc, res.get("result", "")[:9]), (2, "not ready"))

    def reused(out, new, stamp, rec, base):
        rec["reused"] = True
    rc, res = tree("reused", reused)
    check("S7 a reused record is not a new measurement: not valid", (rc, res.get("new_run_valid")), (2, False))
finally:
    shutil.rmtree(ROOT, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
