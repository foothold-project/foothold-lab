"""Convert the synthetic A fixture to v10's legacy input grammar for logic comparison."""
import argparse
import json
from pathlib import Path
import shutil

from s1043_manifest import ROOT

ap = argparse.ArgumentParser()
ap.add_argument("--fixture", required=True)
a = ap.parse_args()
base = ROOT / "fixture_synth" / a.fixture
src = base / "data"
dst = base / "v10_data"
if dst.exists():
    raise SystemExit("v10 reference exists")
dst.mkdir()
(base / "v10_reports").mkdir()
new = json.loads((src / "s1043A_base.json").read_text(encoding="utf-8"))
pins = {k: new["pins"][k] for k in ("q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py")}
for tag in new["matrix"]:
    shutil.copytree(src / tag, dst / tag)
    st = json.loads((dst / tag / "driver_stamp.json").read_text(encoding="utf-8"))
    (dst / tag / "driver_stamp.json").write_text(json.dumps({"pins": pins, "ckpt_sha256": st["ckpt_sha256"]}), encoding="utf-8")
old = {"version": "3.2", "pins": pins, "ckpt": new["ckpt"], "matrix": new["matrix"],
       "runs": new["runs"], "ended": "fixture", "pair_fail": [], "skipped": []}
(dst / "cmdr_eval_driver.json").write_text(json.dumps(old), encoding="utf-8")
print(dst)
