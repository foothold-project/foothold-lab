"""Make a CPU-only A 45 fixture under codexE for CLI integration tests."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np

from s1043_manifest import ROOT, canonical_hash, load, sha256

ap = argparse.ArgumentParser()
ap.add_argument("--id", required=True)
args = ap.parse_args()
if not args.id.replace("_", "").isalnum():
    raise SystemExit("invalid fixture id")
base = ROOT / "fixture_synth" / args.id
if base.exists():
    raise SystemExit("fixture already exists")
data = base / "data"
reports = base / "reports"
data.mkdir(parents=True)
reports.mkdir()
orig = load(ROOT / "cand/manifest_s1043.json")
m = json.loads(json.dumps(orig))
c = m["contract"]
for key, original_path in list(c["paths"].items()):
    c["paths"][key] = str(base / key / Path(original_path).name) if key in (
        "registry", "convert_lock", "run_lease", "stop", "compare_report") else str(base / key)
c["device"]["gpu_index"] = 0
c["device"]["gpu_uuid"] = "fixture-uuid"
c["device"]["CUDA_VISIBLE_DEVICES"] = "-1"
m["contract_sha256"] = canonical_hash(c)
mp = base / "manifest.json"
mp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
pins = {k.removeprefix("source_").removeprefix("config_"): v["sha256"]
        for k, v in c["inputs"].items() if k.startswith(("source_", "config_"))}
for f in ("s1043_manifest.py", "cmdr_bundle_compare_s1043.py", "cmdr_eval_driver_s1043.py",
          "cmdr_post_s1043.py", "frozen_exec_s1043.py"):
    pins[f] = sha256(ROOT / "cand" / f)
pins["manifest_s1043.json"] = sha256(mp)
model_inputs = {"p20000": "parent_model", "off24000": "off_model_24000", "on24000": "on_model_24000"}
ckpt = {k: {"sha256": c["inputs"][v]["sha256"]} for k, v in model_inputs.items()}
traj = np.zeros((251, 100, 12), dtype=np.float32)
traj[:, :, 10] = -1
traj[:, :, 11] = 0.5
term = np.zeros((251, 100), dtype=np.bool_)
cmd_hist = np.zeros((251, 100, 3), dtype=np.float32)
z = io.BytesIO()
np.savez_compressed(z, traj=traj, term=term, cmd_hist=cmd_hist)
npz = z.getvalue()
cols = ("episode", "cell", "span_q2_pass", "span_q1a_pass", "span_q1_pass",
        "q2_pass", "q1a_pass", "q1_pass", "span_survived", "mae_vx", "mae_vy", "mae_wz")
runs = []
matrix = {}
for j in c["plan"]["A"]:
    model, fam, cell, noise, seed = j
    tag = f"cq_{model}_{fam}_{cell}_{noise}_s{seed}"
    run = data / tag
    run.mkdir()
    limit = {"p20000": 40, "off24000": 50, "on24000": 60}[model]
    ep = io.StringIO(newline="")
    writer = csv.DictWriter(ep, fieldnames=cols)
    writer.writeheader()
    for i in range(100):
        yes = str(i < limit)
        writer.writerow({**{x: yes for x in ("span_q2_pass", "span_q1a_pass", "span_q1_pass",
                                            "q2_pass", "q1a_pass", "q1_pass")},
                         "episode": i, "cell": cell, "span_survived": "True",
                         "mae_vx": 0.1, "mae_vy": 0.1, "mae_wz": 0.1})
    meta = {"args": {"tag": tag, "families": fam, "cells": cell, "obs_noise": True,
                     "eval_seed": seed, "episodes": 100, "outdir": str(data),
                     "checkpoint": c["inputs"][model_inputs[model]]["path"],
                     "policy": "student", "difficulty": 0.5, "terrain_set": "train",
                     "heading_hold": 0, "spawn_offset": "", "physx_small_buffers": True,
                     "physics_gpu": 0, "active_gpu": 0},
            "checkpoint_sha256": c["inputs"][model_inputs[model]]["sha256"],
            "devices": {"torch_cuda0_uuid": "fixture-uuid"},
            "pairing_sha256": {"init_root_pose": f"{fam}-{cell}-{seed}"},
            "pairing_sha256_ext": {"com": f"{fam}-{cell}-{seed}"},
            "terrain_mesh": "fixture", "terrain_origins_sha256": "fixture",
            "obs_shapes": {"policy": [100, 10]}, "eval_changes": ["fixture"]}
    (run / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (run / "cells.json").write_text(json.dumps({"cell": cell}), encoding="utf-8")
    (run / "episodes.csv").write_text(ep.getvalue(), encoding="utf-8")
    (run / "traj.npz").write_bytes(npz)
    hashes = {f: sha256(run / f) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz")}
    attempt = "fixture-collection-1"
    stamp = {"pins": pins, "stamp_version": "1043-A1", "experiment": c["experiment"],
             "contract_sha256": m["contract_sha256"], "stage": "A", "origin": "hashed-at-collection",
             "ckpt_sha256": ckpt[model]["sha256"], "attempt": attempt, "out_sha256": hashes}
    (run / "driver_stamp.json").write_text(json.dumps(stamp, ensure_ascii=False), encoding="utf-8")
    runs.append({"tag": tag, "valid": True, "attempt": attempt, "out_sha256": hashes})
    matrix[tag] = "valid"
log = {"version": "1043-A1", "experiment": c["experiment"], "contract_sha256": m["contract_sha256"],
       "stage": "A", "complete": True, "ended": "fixture", "end_kind": "complete", "attempt": "fixture-driver-1",
       "pins": pins, "ckpt": ckpt, "runs": runs, "matrix": matrix, "pair_fail": [], "skipped": [],
       "not_run": [], "not_valid": []}
(data / "s1043A_base.json").write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")
(data / "s1043A_base.attempt.json").write_text(json.dumps({"attempt": "fixture-driver-1", "state": "ended"}), encoding="utf-8")
print(base)
