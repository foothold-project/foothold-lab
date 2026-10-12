# Check that every 20000 run has a 20499 partner with identical initial states, DR samples
# and terrain mesh (pairing), and that both used the same settings except the checkpoint.
# Writes out/Q-E1-pairs.json.

import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
res = {}
for m in sorted(glob.glob(os.path.join(OUT, "*m20000*", "meta.json"))):
    ta = os.path.basename(os.path.dirname(m))
    tb = ta.replace("m20000", "m20499")
    pb = os.path.join(OUT, tb, "meta.json")
    if not os.path.exists(pb):
        res[ta] = "partner missing"
        continue
    a = json.load(open(m, encoding="utf-8"))
    b = json.load(open(pb, encoding="utf-8"))
    args_a = {k: v for k, v in a["args"].items() if k not in ("checkpoint", "tag")}
    args_b = {k: v for k, v in b["args"].items() if k not in ("checkpoint", "tag")}
    res[ta] = {
        "partner": tb,
        "pairing_equal": a["pairing_sha256"] == b["pairing_sha256"],
        "mesh_equal": a["terrain_mesh"] == b["terrain_mesh"],
        "args_equal_except_ckpt": args_a == args_b,
        "ckpts": [os.path.basename(a["args"]["checkpoint"]), os.path.basename(b["args"]["checkpoint"])],
    }
with open(os.path.join(OUT, "Q-E1-pairs.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, indent=1)
bad = {k: v for k, v in res.items() if not isinstance(v, dict) or not all(
    (v["pairing_equal"], v["mesh_equal"], v["args_equal_except_ckpt"]))}
print("pairs:", len(res), "not ok:", json.dumps(bad, indent=1))
