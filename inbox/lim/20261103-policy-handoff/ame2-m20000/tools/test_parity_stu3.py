"""Tests of the fixed step 3 judge parity_stu3.py (CPU only). The models are the bundle's real ones; the inputs are the real recording and
copies of it changed in memory. Files the tests write go into a new folder of this run only (never a reused name) and are removed at the end.

Cases (what must happen):
  real                        the real recording: judged, policy within the threshold, mapper above it (the stored verdict of step 3)
  codex_nan_three_stair_frames  Codex 430_55 counterexample: the three stairs frames that exceed the threshold (policy steps 130, 155, 170) set to
                              NaN. The aggregation of parity_stu2.py (max(old, new), a NaN is skipped) then lets the mapper pass: shown under
                              "old_aggregation", and that it DOES pass there is itself a condition of this test. parity_stu3.py must refuse (non_finite).
  nan_in_policy_input / inf_in_recorded_mapper_output / nan_in_onnx_mapper_elevation / nan_in_onnx_mapper_logvar / nan_in_onnx_policy_actions /
  nan_in_onnx_policy_attn_out / nan_in_onnx_policy_global_feat      must refuse (non_finite)
  truncated_100_steps / missing_frame / second_episode_label / wrong_terrain_tag / frame_at_wrong_step   must refuse (record)
  vector_writer               the test-vector writer of the pass path, run on the real recording's references in the run's own folder: four files, read back
  changed_file_through_main   the counterexample written to a file and given to the command line: exit code 1 at the sha256 of the recording, no output folder
  existing_output_folder_through_main   the command line with an output folder that exists: exit code 1, nothing written into it
  changed_reference_code_through_main   the command line with a copy of the rsl_rl folder whose AME2_models.py has one more line: exit code 1 at its sha256
usage: python test_parity_stu3.py <extract npz> <ckpt> <agent.yaml> <onnx> <mapper_jit> <mapper_onnx> <rsl dir> <scratch dir> <out json>
"""
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parity_stu3 as J  # noqa: E402

EX, CKPT, AGENT, ONNX, MJIT, MONNX, RSL, SCRATCH, OUT = sys.argv[1:10]
for k, p in (("npz", EX), ("ckpt", CKPT), ("agent", AGENT), ("onnx", ONNX), ("mapper_jit", MJIT), ("mapper_onnx", MONNX)):
    if J.sha256(p) != J.SHA[k]:
        sys.exit(f"TEST_FAIL {k} sha256 is not the bundle's")
mdl = J.load_models(CKPT, AGENT, ONNX, MJIT, MONNX, RSL)
z = np.load(EX)
Z0 = {k: z[k] for k in z.files if k != "meta_json"}
meta0 = json.loads(str(z["meta_json"]))
os.makedirs(SCRATCH, exist_ok=True)
TMP = tempfile.mkdtemp(prefix="stu3_test_", dir=SCRATCH)  # a new folder of this run only


def fresh():
    return {k: v.copy() for k, v in Z0.items()}, copy.deepcopy(meta0)


class NanAt:
    """an onnxruntime session one of whose outputs is NaN at one call"""

    def __init__(self, sess, call, output):
        self.sess, self.call, self.output, self.n = sess, call, output, 0

    def run(self, names, feed):
        out = self.sess.run(names, feed)
        if self.n == self.call:
            out[self.output] = np.full_like(out[self.output], np.nan)
        self.n += 1
        return out


def old_aggregation(Z):
    """the mapper part of parity_stu2.py (lines 92-104, 148-152) on the stairs tag: what the stored judge would have concluded"""
    G = Z["stairs_frame_grid"].astype(np.float32)
    me = ml = 0.0
    flips = 0
    with torch.no_grad():
        for k in range(G.shape[0]):
            te, tl = (x[0, 0].numpy() for x in mdl["jm"](torch.from_numpy(G[k:k + 1, None])))
            oe, ol = mdl["msess"].run(["elevation", "logvar"], {"grid": G[k:k + 1, None]})
            me, ml = max(me, float(np.abs(oe[0, 0] - te).max())), max(ml, float(np.abs(ol[0, 0] - tl).max()))
            flips += int(((ol[0, 0] >= J.REJ) != (tl >= J.REJ)).sum())
    return {"max_abs_elevation": me, "max_abs_logvar": ml, "rejection_flips": flips, "mapper_would_pass": bool(max(me, ml) <= J.TOL and flips == 0)}


REFS = {}


def run(name, expect, Z, meta, mdl_=None, extra=None, also=True):
    try:
        res, refs = J.judge(Z, meta, mdl_ or mdl)
        if name == "real":
            REFS.update(refs)
        got = {"judged": True, "pass_policy": res["pass_policy"], "pass_mapper": res["pass_mapper"], "pass": res["pass"],
               "max_abs_policy_outputs": res["max_abs_policy_outputs"], "max_abs_mapper_onnx_vs_jit": res["max_abs_mapper_onnx_vs_jit"],
               "stairs_steps_above": res["tags"]["stairs"]["mapper_policy_steps_elevation_above_threshold"],
               "arrays_checked": res["finite_checks"]["arrays_checked"], "record_checks_done": len(res["record_checks_done"])}
        kind = "judged"
    except J.JudgeFail as e:
        got, kind = {"judged": False, "refused": e.kind, "message": e.msg[:160]}, e.kind
    ok = kind == expect and (expect != "judged" or (got["pass_policy"], got["pass_mapper"], got["pass"]) == (True, False, False)) and bool(also)
    row = {"case": name, "expected": expect, "got": got, "as_expected": bool(ok)}
    if extra:
        row.update(extra)
    print(json.dumps(row)[:400], flush=True)
    return row


def cli(name, expect_text, npz, rsl, out_dir, must_not_exist=None, must_stay_empty=None):
    p = subprocess.run([sys.executable, os.path.join(HERE, "parity_stu3.py"), npz, CKPT, AGENT, ONNX, MJIT, MONNX, rsl, out_dir, "test"], capture_output=True, text=True)
    lines = (p.stdout + p.stderr).strip().splitlines()
    msg = lines[-1] if lines else ""
    ok = p.returncode == 1 and expect_text in msg
    if must_not_exist:
        ok = ok and not os.path.exists(must_not_exist)
    if must_stay_empty:
        ok = ok and os.listdir(must_stay_empty) == []
    row = {"case": name, "expected": f"exit code 1, message with '{expect_text}'", "got": {"exit_code": p.returncode, "last_line": msg[:160]}, "as_expected": bool(ok)}
    print(json.dumps(row), flush=True)
    return row


rows = []
Z, m = fresh()
rows.append(run("real", "judged", Z, m))
Z, m = fresh()
frames = [s // J.FRAME_PERIOD for s in (130, 155, 170)]
Z["stairs_frame_grid"][frames] = np.nan
old = old_aggregation(Z)
rows.append(run("codex_nan_three_stair_frames", "non_finite", Z, m, extra={"nan_frames": frames, "old_aggregation": old,
                                                                         "condition": "refused by parity_stu3.py AND the old aggregation lets the mapper pass"},
                also=old["mapper_would_pass"]))
Z, m = fresh()
Z["flat_prop"][10, 0, 0] = np.nan
rows.append(run("nan_in_policy_input", "non_finite", Z, m))
Z, m = fresh()
Z["stairs_frame_mean"][0, 0, 0] = np.inf
rows.append(run("inf_in_recorded_mapper_output", "non_finite", Z, m))
for name, key, call, output in (("nan_in_onnx_mapper_elevation", "msess", 5, 0), ("nan_in_onnx_mapper_logvar", "msess", 6, 1),
                                ("nan_in_onnx_policy_actions", "sess", 7, 0), ("nan_in_onnx_policy_attn_out", "sess", 8, 1),
                                ("nan_in_onnx_policy_global_feat", "sess", 9, 2)):
    Z, m = fresh()
    rows.append(run(name, "non_finite", Z, m, mdl_={**mdl, key: NanAt(mdl[key], call, output)}))
Z, m = fresh()
for k in list(Z):
    if k.startswith(("flat_", "stairs_")):
        Z[k] = Z[k][:20] if "_frame_" in k else Z[k][:100]
rows.append(run("truncated_100_steps", "record", Z, m))
Z, m = fresh()
for k in ("stairs_frame_counter", "stairs_frame_grid", "stairs_frame_mean", "stairs_frame_logvar"):
    Z[k] = np.delete(Z[k], 31, axis=0)
rows.append(run("missing_frame", "record", Z, m))
Z, m = fresh()
Z["flat_ep"][150:] = 1
rows.append(run("second_episode_label", "record", Z, m))
Z, m = fresh()
m["tags"]["stairs"]["cell"] = ["stair_down", 4]
rows.append(run("wrong_terrain_tag", "record", Z, m))
Z, m = fresh()
Z["stairs_frame_counter"][31] += 1
rows.append(run("frame_at_wrong_step", "record", Z, m))
# the test-vector writer of the pass path (the real recording never reaches it): run it on the references of the real case
vdir = os.path.join(TMP, "vectors")
os.makedirs(vdir)
try:
    written = J.write_vectors(vdir, "test", Z0, REFS)
    tv = json.load(open(os.path.join(vdir, "test_vectors_flat20.json"), encoding="utf-8"))
    with np.load(os.path.join(vdir, "test_vectors_flat20_mapper.npz")) as tvm:  # closed again before the folder is removed
        mapper_frames, mapper_steps = int(tvm["grid"].shape[0]), [int(x) for x in tvm["step"]]
    got = {"files": sorted(written), "policy_steps": tv["steps"], "policy_inputs": sorted(tv["inputs"][0]), "mapper_frames": mapper_frames,
           "mapper_frame_steps": mapper_steps}
    ok = (len(written) == 4 and tv["steps"] == 20 and len(tv["inputs"]) == 20 and got["policy_inputs"] == ["cmds", "neural_map", "prop_hist"]
          and got["mapper_frame_steps"] == [0, 5, 10, 15] and all(len(v) == 64 for v in written.values()))
except Exception as e:  # noqa: BLE001
    got, ok = {"error": repr(e)[:200]}, False
rows.append({"case": "vector_writer", "expected": "four files written and read back (20 policy steps, 4 mapper frames at steps 0, 5, 10, 15)", "got": got, "as_expected": bool(ok)})
print(json.dumps(rows[-1])[:400], flush=True)
# through the command line: a changed recording file, an existing output folder, a changed reference code file
Z, m = fresh()
Z["stairs_frame_grid"][frames] = np.nan
bad_npz = os.path.join(TMP, "counterexample_nan.npz")
np.savez_compressed(bad_npz, meta_json=np.array(json.dumps(meta0)), **Z)
rows.append(cli("changed_file_through_main", "npz sha256", bad_npz, RSL, os.path.join(TMP, "out_changed"), must_not_exist=os.path.join(TMP, "out_changed")))
exists = os.path.join(TMP, "out_exists")
os.makedirs(exists)
rows.append(cli("existing_output_folder_through_main", "output folder exists", EX, RSL, exists, must_stay_empty=exists))
rsl_mod = os.path.join(TMP, "rsl_changed")
shutil.copytree(RSL, rsl_mod, ignore=shutil.ignore_patterns("__pycache__"))
with open(os.path.join(rsl_mod, "rsl_rl", "models", "AME2_models.py"), "ab") as f:
    f.write(b"\n# one more line\n")
rows.append(cli("changed_reference_code_through_main", "AME2_models.py sha256", EX, rsl_mod, os.path.join(TMP, "out_code"), must_not_exist=os.path.join(TMP, "out_code")))
shutil.rmtree(TMP)
hole = rows[1]["old_aggregation"]["mapper_would_pass"]
all_ok = bool(all(r["as_expected"] for r in rows) and hole)
out = {"what": "tests of tools/parity_stu3.py; the models are the bundle's, the inputs the real recording and changed copies",
       "judge_sha256": J.sha256(os.path.abspath(J.__file__)), "reference_code": mdl["reference_code"]["pinned"],
       "runtime": {"onnxruntime": mdl["ort"], "torch": torch.__version__, "torch_threads": 4},
       "success_condition": "every case as expected AND the old aggregation lets the counterexample pass",
       "old_aggregation_lets_the_counterexample_pass": bool(hole), "cases": rows, "all_as_expected": all_ok,
       "threshold": J.TOL, "ln15": math.log(15.0)}
json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
print("TEST_DONE", all_ok, "cases", len(rows), "old aggregation passes the counterexample:", hole)
sys.exit(0 if all_ok else 2)
