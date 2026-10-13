"""The 11:38 shared-USD run vs its v3.7 re-collection (lead 10/13, TASK-astra-16h step 7, VERIFY-astra-16h 4.4 / 16i 7).
Read only. Four separate answers, never folded into one:
  output_content_equal  cells.json values, every traj.npz array (dtype / shape / values), episodes.csv rows
  inputs_equal          the meta fields that describe input and checks, env_origins.npy bytes, the checkpoint hash
  new_run_valid         the new run's log has the evaluator's completion line, no Traceback, no robot root reference
                        failure; its stamp is a v3.7 stamp with a real job id; the base log's last record of the tag is
                        valid, not reused, with that attempt and the stamp's output hashes
  comparison_ready      inputs_equal and new_run_valid
The old run is the preserved folder (out/attempts/<tag>.dir.*) whose stamp has the held stamp hash (out/cmdr_post_hold.json),
not simply the first folder by name. Results:
  not ready                       -> "same-condition comparison on hold" (exit 2)
  ready, outputs equal            -> "no difference found in the recorded outputs compared" (exit 0); not proof the asset was intact
  ready, outputs differ           -> "recorded outputs differ, cause unknown" (exit 1); not proof of collision damage
  a file read changed meanwhile   -> "inputs changed while comparing" (exit 3); nothing concluded (16j 5.2)
Neither result releases the hold; that needs an explicit release record in the hold list (16i 3 / 7)."""
import csv
import glob
import hashlib
import io
import json
import os
import re
import sys

import numpy as np

OUT = os.environ.get("COMPARE_OUT", "C:/isaac/ext/go2_rl_robotlab/_eval/out")
TAG = sys.argv[1] if len(sys.argv) > 1 else "cq_on24000_flat_stand_on_s1000"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


HOLDP = os.path.join(OUT, "cmdr_post_hold.json")
HOLD_RAW = open(HOLDP, "rb").read() if os.path.exists(HOLDP) else None  # parsed from these bytes; compared again at the end
hold = json.loads(HOLD_RAW.decode("utf-8")).get(TAG, {}) if HOLD_RAW is not None else {}
held_stamp = hold.get("stamp_sha256")
old = [d for d in sorted(glob.glob(os.path.join(OUT, "attempts", f"{TAG}.dir.*"))) if sha(os.path.join(d, "driver_stamp.json")) == held_stamp]
new = os.path.join(OUT, TAG)
OUT4 = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
FIVE = OUT4 + ("env_origins.npy",)
res = {"tag": TAG, "held_stamp": held_stamp, "old": [os.path.relpath(d, OUT) for d in old], "new": os.path.relpath(new, OUT)}
missing_new = [f for f in FIVE + ("driver_stamp.json",) if not os.path.exists(os.path.join(new, f))]
if len(old) != 1 or missing_new:  # 16j 5.2: a run still being written is "not ready", not read half-way
    res["result"] = "not ready: " + ("the held run is not found among preserved folders" if len(old) != 1 else f"new run incomplete {missing_new}")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(2)
o = old[0]
HAND = hold.get("handover")
# 16j 5.2: every file read below is hashed first and again at the end; a change in between gives exit 3 (run again).
# A before/after check, not an atomic snapshot: a change that is undone before the end is not seen.
LOGP, BASEP = os.path.join(OUT, f"{TAG}.log"), os.path.join(OUT, "cmdr_eval_driver.json")
READ = [os.path.join(d, f) for d in (o, new) for f in FIVE + ("driver_stamp.json",)] + [LOGP] + ([os.path.join(OUT, HAND, "manifest.json")] if HAND else [])
FP0 = {p_: sha(p_) for p_ in READ}
m_ = TAG.split("_")[1]


def base_view(b):
    """the part of the live base log this comparison relies on (the file itself is rewritten after every run)"""
    return {"rec": next((r for r in reversed(b.get("runs", [])) if isinstance(r, dict) and r.get("tag") == TAG), {}),
            "matrix": b.get("matrix", {}).get(TAG), "pair_fail": TAG in b.get("pair_fail", []), "pins": b.get("pins"),
            "ckpt": b.get("ckpt", {}).get(m_)}


# 16j 5.2: the preserved original must be the very bytes the hand-over froze (not only the stamp)
man_run = json.load(open(os.path.join(OUT, HAND, "manifest.json"), encoding="utf-8"))["runs"].get(TAG, {}) if HAND else {}
res["old_equals_handover"] = bool(man_run) and all(sha(os.path.join(o, f)) == man_run.get(f) for f in FIVE)

# outputs
eq = {"cells.json": json.load(open(os.path.join(o, "cells.json"))) == json.load(open(os.path.join(new, "cells.json")))}
zo, zn = np.load(os.path.join(o, "traj.npz")), np.load(os.path.join(new, "traj.npz"))
arr = {}
for k in sorted(set(zo.files) | set(zn.files)):
    if k not in zo.files or k not in zn.files:
        arr[k] = "missing on one side"
        continue
    x, y = zo[k], zn[k]
    if x.dtype != y.dtype or x.shape != y.shape:
        arr[k] = f"dtype/shape {x.dtype}{x.shape} vs {y.dtype}{y.shape}"
    elif np.array_equal(x, y, equal_nan=x.dtype.kind == "f"):
        arr[k] = "equal"
    else:
        arr[k] = f"values differ (max abs {np.nanmax(np.abs(x.astype(np.float64) - y.astype(np.float64))) if x.dtype.kind in 'fiu' else '?'})"
eq["traj.npz arrays"] = arr
ro = list(csv.DictReader(io.StringIO(open(os.path.join(o, "episodes.csv"), encoding="utf-8").read())))
rn = list(csv.DictReader(io.StringIO(open(os.path.join(new, "episodes.csv"), encoding="utf-8").read())))
eq["episodes.csv"] = ro == rn
eq["bytes (cells, traj, episodes)"] = [sha(os.path.join(o, f)) == sha(os.path.join(new, f)) for f in ("cells.json", "traj.npz", "episodes.csv")]
res["outputs"] = eq
res["output_content_equal"] = eq["cells.json"] and eq["episodes.csv"] and all(v == "equal" for v in arr.values())

# inputs
mo = json.load(open(os.path.join(o, "meta.json"), encoding="utf-8"))
mn = json.load(open(os.path.join(new, "meta.json"), encoding="utf-8"))
keys = ["args", "checks_pre", "checks_run", "N", "T_steps", "checkpoint_sha256", "loaded_iter", "pairing_sha256", "pairing_sha256_ext", "terrain_mesh"]
inp = {k: mo.get(k) == mn.get(k) for k in keys}
inp["env_origins.npy bytes"] = sha(os.path.join(o, "env_origins.npy")) == sha(os.path.join(new, "env_origins.npy")) is not None
res["inputs"] = inp
res["inputs_equal"] = all(inp.values())

# the new run
lo = open(os.path.join(OUT, f"{TAG}.log"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(OUT, f"{TAG}.log")) else ""
st = json.load(open(os.path.join(new, "driver_stamp.json"), encoding="utf-8")) if os.path.exists(os.path.join(new, "driver_stamp.json")) else {}
base = json.load(open(os.path.join(OUT, "cmdr_eval_driver.json"), encoding="utf-8"))
rec = next((r for r in reversed(base.get("runs", [])) if isinstance(r, dict) and r.get("tag") == TAG), {})
now4 = {f: sha(os.path.join(new, f)) for f in OUT4}
BV0 = base_view(base)
nv = {"completion line": f"[Q-EVAL] done {TAG} N 100 " in lo,
      # 16j 5.2: the bytes on disk are the bytes the stamp and the record vouch for, all four keys present
      "four output hashes = stamp = record": isinstance(st.get("out_sha256"), dict) and sorted(st["out_sha256"]) == sorted(OUT4)
      and st["out_sha256"] == now4 and rec.get("out_sha256") == now4,
      "owner matrix valid, no pair failure": base.get("matrix", {}).get(TAG) == "valid" and "pair_fail" not in rec and TAG not in base.get("pair_fail", []),
      "stamp pins and checkpoint = the log's": st.get("pins") == base.get("pins")
      and st.get("ckpt_sha256") == (base.get("ckpt", {}).get(m_, {}) or {}).get("sha256"),
      "no Traceback": "Traceback (most recent call last)" not in lo,
      "no root reference failure": "</World/envs/env_0/Robot>: Unresolved reference" not in lo,
      "stamp v3.7 with a real job id": st.get("stamp_version") == "3.7" and bool(re.fullmatch(r"g[01]-\d+-\d{10}-j\d+", str(st.get("attempt", "")))),
      "base record valid, measured (not reused), same attempt and hashes": bool(rec) and rec.get("valid") is True and rec.get("reused") is False
      and rec.get("attempt") == st.get("attempt") and rec.get("out_sha256") == st.get("out_sha256")}
res["new_run"] = nv
res["new_run_valid"] = all(nv.values())
res["new_attempt"] = st.get("attempt")  # 16k 4: what a release record must name (aggregator v9 checks both)
res["new_out_sha256"] = now4
res["comparison_ready"] = res["inputs_equal"] and res["new_run_valid"] and res["old_equals_handover"]
if os.environ.get("COMPARE_TEST_TOUCH"):
    with open(os.environ["COMPARE_TEST_TOUCH"], "ab") as fh:
        fh.write(b" ")
changed = [os.path.relpath(p_, OUT) for p_ in READ if sha(p_) != FP0[p_]]
if FP0[os.path.join(o, "driver_stamp.json")] != held_stamp:
    changed.append("the preserved stamp is no longer the held one")
if (open(HOLDP, "rb").read() if os.path.exists(HOLDP) else None) != HOLD_RAW:
    changed.append("cmdr_post_hold.json")
if base_view(json.load(open(BASEP, encoding="utf-8"))) != BV0:
    changed.append("cmdr_eval_driver.json (this tag's record, matrix, pins or checkpoint)")
if changed:
    res["changed_while_reading"] = changed
    res["result"] = "inputs changed while comparing: nothing concluded, run again"
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(3)
if not res["comparison_ready"]:
    res["result"] = "same-condition comparison on hold (inputs differ or the new run is not shown valid)"
    code = 2
elif res["output_content_equal"]:
    res["result"] = "no difference found in the recorded outputs compared (not proof that the robot asset was intact)"
    code = 0
else:
    res["result"] = "recorded outputs differ, cause unknown (not proof of collision damage): isolate, re-collect again, compare"
    code = 1
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(code)
