"""CPU tests for unseen_driver_cmdr.py v3 on synthetic run folders (lead 10/13 evening · ASTRA 17b 2.4 / 2.5 counterexamples kept).
UNCR_SCRIPT may point at a mutated copy. No Isaac. Exit 1 when any check fails."""
import csv
import importlib.util
import json
import os
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("UNCR_SCRIPT", os.path.join(HERE, "unseen_driver_cmdr.py"))
fails = []


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:200], "want", repr(want)[:120])
    if not ok:
        fails.append(name)


def load(root):
    os.environ["UNCR_ROOT"] = root
    spec = importlib.util.spec_from_file_location(f"uncr_{os.path.basename(root)}", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CK_SHA = {}


def fake_run(U, m, fam, cell, mutate=None):
    tag = U.tag_of(m, fam, cell)
    d = os.path.join(U.ROOT, tag)
    os.makedirs(d, exist_ok=True)
    spec = U.MODELS[m]
    if spec["ckpt"] not in CK_SHA:
        CK_SHA[spec["ckpt"]] = U.sha(spec["ckpt"])
    meta = {"args": {"terrain_set": "unseen10", "families": fam, "cells": cell, "episodes": 100, "eval_seed": 1000, "obs_noise": False,
                     "full_record": False, "policy": "student", "difficulty": 0.5, "checkpoint": spec["ckpt"], "outdir": U.ROOT},
            "checkpoint_sha256": CK_SHA[spec["ckpt"]], "loaded_iter": spec["iter"], "N": 100,
            "train_yaml_source": {"train_yaml": spec["yaml"]} if spec["yaml"] else None,
            "checks_run": {"nonfinite_action_or_obs_count": 0, "obs_single_cmd_vs_target_max_abs": 0.0, "obs_history_latest_cmd_vs_target_max_abs": 0.0},
            "checks_pre": {"manual_student_path_vs_act_inference_max_abs": 0.0, "teacher_input_randomized_max_abs_action_change": 0.0},
            "obstacle_zone_m": {fam: [0.75, 4.0, "x"]},
            "terrain_mesh": {"sha256": "mesh-" + fam}, "terrain_origins_sha256": "orig-" + fam,
            "pairing_sha256": {"init_root_pose": "p1", "body_masses": "p2"}, "pairing_sha256_ext": {"com": "c1", "material": "m1"}}
    if mutate:
        mutate(meta, d)
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"))
    json.dump([{"n": 100}], open(os.path.join(d, "cells.json"), "w"))
    with open(os.path.join(d, "episodes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["episode", "env", "family", "cell", "survived", "fall_t"])
        for e in range(100):
            w.writerow([e, e, fam, cell, "True", ""])
    if not os.path.exists(os.path.join(d, "traj.npz")):
        tr = np.zeros((50, 100, 3), np.float32)
        tr[:, :, 0] = np.linspace(0, 5, 50)[:, None]
        np.savez(os.path.join(d, "traj.npz"), traj=tr)
    if not os.path.exists(os.path.join(d, "env_origins.npy")):
        np.save(os.path.join(d, "env_origins.npy"), np.zeros((100, 3), np.float32))
    open(os.path.join(U.ROOT, f"{tag}.log"), "w").write(f"[Q-EVAL] done {tag} N 100 rollout_s 1\n")
    json.dump({"exit_code": 0, "stopped_by_guard": False}, open(os.path.join(U.ROOT, f"{tag}.guard.json"), "w"))
    att = f"A-{tag}-try1"
    json.dump({"attempt": att, "slot_rc": 0, "child_rc": 0, "state_at_release": "scene_built", "usd_final": ["x"], "usd_outside_root": [],
               "conflicts": {}, "cmd": ["py", "usd_isolate_run.py", "q_eval_cmdr.py"]}, open(os.path.join(U.ROOT, f"{tag}.slot.json"), "w"))
    json.dump({"attempt": att, "out_sha256": U.outhash(tag), "code_sha256": U.code_sha()}, open(os.path.join(d, "driver_stamp.json"), "w"))


def diag_all(U, mut=None):
    for fam, cell in U.DIAG:
        for m in ("par", "off", "on"):
            fake_run(U, m, fam, cell, (mut or {}).get((m, fam, cell)))


tmps = []
try:
    def new(case):
        t = tempfile.mkdtemp(prefix=f"uncr_{case}_", dir=HERE)
        tmps.append(t)
        return load(t)

    U = new("d1")
    diag_all(U)
    U.stage_post(set(U.DIAG))
    g = json.load(open(os.path.join(U.ROOT, "diag_gate.json")))
    check("D1 all diag runs valid and paired: post complete 7, gate ok, no failures",
          (U.LOG["stages"]["post"]["complete"], g["diag_runs_valid"], g["diag_pair_ok"], U.LOG["failures"]), (7, True, True, []))

    U = new("d2")
    diag_all(U, {("on", "gap", "fwd05"): lambda meta, d: meta["pairing_sha256_ext"].update(com="DIFFERENT")})
    U.stage_post(set(U.DIAG))
    rows = list(csv.DictReader(open(os.path.join(U.ROOT, "UNCR-cells.csv"))))
    r = [x for x in rows if x["terrain"] == "gap" and x["cell"] == "fwd05"][0]
    g = json.load(open(os.path.join(U.ROOT, "diag_gate.json")))
    check("D2 (17b 2.4) on's DR fingerprint differs: that cell pair_ok False with the key named, gate not passed",
          (r["pair_ok"], "pairing_sha256_ext.com" in r["pair_diff"], g["diag_pair_ok"]), ("False", True, False))

    U = new("d3")
    diag_all(U, {("on", "wave", "fwd05"): lambda meta, d: meta["checks_run"].update(nonfinite_action_or_obs_count=10)})
    U.stage_post(set(U.DIAG))
    check("D3 (17b 2.4) nonfinite count 10: that run invalid, post reports the requested cell incomplete, failure recorded",
          (U.validate_run("on", "wave", "fwd05", U.tag_of("on", "wave", "fwd05")) != "", U.LOG["stages"]["post"]["requested_incomplete"], bool(U.LOG["failures"])),
          (True, ["wave/fwd05"], True))

    U = new("d4")

    def broken(meta, d):
        open(os.path.join(d, "traj.npz"), "w").write("broken")
    diag_all(U, {("par", "rails", "fwd05"): broken})
    check("D4 (17b 2.4) a broken traj.npz: invalid at validation, not later", U.validate_run("par", "rails", "fwd05", U.tag_of("par", "rails", "fwd05")) != "", True)

    U = new("d5")
    U.stage_post(set(U.DIAG))
    check("D5 (17b 2.5) post on an empty root: requested cells incomplete is a failure (exit path 1), all 32 manifest rows kept (7 diag + 25 more full cells)",
          (len(U.LOG["stages"]["post"]["requested_incomplete"]), bool(U.LOG["failures"]), U.LOG["stages"]["post"]["rows"]), (7, True, 32))

    U = new("d6")
    sys.argv = ["x", "--stages", "full"]
    try:
        U.main()
    except SystemExit as e:
        code = e.code
    check("D6 full without a passed diag gate: not started, exit 1", (code, any(f["stage"] == "full" for f in U.LOG["failures"]), len(U.LOG["runs"])), (1, True, 0))

    U = new("d7")
    diag_all(U)
    tag = U.tag_of("par", "gap", "fwd05")
    st = json.load(open(os.path.join(U.ROOT, tag, "driver_stamp.json")))
    st["code_sha256"]["q_eval_cmdr.py"] = "0" * 64
    json.dump(st, open(os.path.join(U.ROOT, tag, "driver_stamp.json"), "w"))
    check("D7 (17b 2.5) a stamp made with other evaluator code is not reusable", U.reusable("par", "gap", "fwd05", tag), False)

    U = new("d8")
    diag_all(U)
    tag = U.tag_of("off", "gap", "back03")
    U.keep_attempt(tag)
    moved = [x for x in os.listdir(os.path.join(U.ROOT, "attempts"))]
    check("D8 (17b 2.5) a retry moves the earlier result folder with its log, guard and slot record",
          (os.path.exists(os.path.join(U.ROOT, tag)), len(moved), sorted(os.listdir(os.path.join(U.ROOT, "attempts", moved[0]))) if moved else []),
          (False, 1, sorted([tag, f"{tag}.guard.json", f"{tag}.log", f"{tag}.slot.json"])))

    U = new("d9")
    diag_all(U, {("par", "pit", "fwd05"): None})
    diag_all(U, {("on", "gap", "back03"): lambda meta, d: meta["checks_pre"].update(manual_student_path_vs_act_inference_max_abs=0.01)})
    check("D9 checks_pre: student path differs from act_inference: invalid", U.validate_run("on", "gap", "back03", U.tag_of("on", "gap", "back03")) != "", True)
finally:
    for t in tmps:
        shutil.rmtree(t, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
