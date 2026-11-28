"""Export the TU mapping model (the TorchScript mapper_tu_jit.pt of the REQ428 student, sha256 52dd869b9fe5...) to ONNX and check it.
Input grid (1, 1, 66, 48) float32 (max height per 4 cm cell relative to the base, empty = -3.0) -> (elevation, logvar), each (1, 1, 66, 48).
Checked on grids built like the robot builds them (ame2_map.local_grid from terrain-like clouds with empty regions, steps, gaps): the JIT
module vs onnxruntime, max |difference| of elevation and of logvar, and the decisions the fusion takes from them (logvar >= ln 15 rejection)
must agree. Writes <out>/mapper_tu.onnx and <out>/mapper_tu.json.
usage: python export_mapper_onnx.py <mapper_tu_jit.pt> <out dir> [--n 300]"""
import hashlib
import json
import math
import os
import sys

import numpy as np
import torch

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, "..", "apps", "agent"))
from foothold_agent.policy import ame2_map as M  # noqa: E402

JIT_SHA_FULL = "52dd869b9fe5bc0ee1973138e72d56d66bee459626da36fed2e2efa716a0e060"   # mapper_tu_jit.pt of the REQ428 student (evaluation runner pin 52dd869b9fe5)
JIT_SHA = "52dd869b9fe5"


def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def grids(rng, n):
    out = []
    for k in range(n):
        pose = (0.0, 0.0, 0.32, 0.0)
        a = rng.uniform(-1.0, 2.4, 4000)
        b = rng.uniform(-1.2, 1.2, 4000)
        kind = k % 4
        if kind == 0:   # stairs up
            z = -0.3 + 0.16 * np.floor(np.clip(a - 0.5, 0, None) / 0.3)
        elif kind == 1:   # gap
            z = np.where((a > 0.8) & (a < 1.3), -1.4, -0.3)
        elif kind == 2:   # boxes
            z = -0.3 + 0.2 * ((np.floor(a / 0.4) + np.floor(b / 0.4)) % 2)
        else:   # rough
            z = -0.3 + rng.normal(0, 0.03, a.size)
        keep = ~((a > 1.5) & (rng.random(a.size) < 0.7))   # sparse far away
        keep &= ~((np.abs(b) > 0.8) & (a < 0.2))           # body shadow
        pts = np.stack([a, b, z + rng.normal(0, 0.01, a.size)], -1).astype(np.float32)[keep]
        out.append(M.local_grid([(pts, np.ones(len(pts), bool))], pose))
    return np.stack(out)[:, None].astype(np.float32)


def main():
    jit_path, out = sys.argv[1], sys.argv[2]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 300
    if n < 100:
        raise SystemExit(f"EXPORT_MAPPER_ONNX_FAIL --n {n} < 100")
    if sha256(jit_path) != JIT_SHA_FULL:
        raise SystemExit("EXPORT_MAPPER_ONNX_FAIL not the student's TU mapper (full sha256)")
    os.makedirs(out, exist_ok=True)
    jm = torch.jit.load(jit_path, map_location="cpu").eval()
    final = os.path.join(out, "mapper_tu.onnx")
    path = final + ".tmp"
    torch.onnx.export(jm, (torch.full((1, 1, 66, 48), -3.0),), path, input_names=["grid"], output_names=["elevation", "logvar"],
                      opset_version=17, do_constant_folding=True, dynamo=False)
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads, so.inter_op_num_threads = 2, 1
    sess = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
    g = grids(np.random.default_rng(3), n)
    w_el = w_lv = 0.0
    rej_flip = 0
    bad = []
    with torch.no_grad():
        for i in range(n):
            te, tl = (t.numpy() for t in jm(torch.from_numpy(g[i:i + 1])))
            oe, ol = sess.run(["elevation", "logvar"], {"grid": g[i:i + 1]})
            for nm_, v in (("elevation", oe), ("logvar", ol), ("jit elevation", te), ("jit logvar", tl)):
                if v.shape != (1, 1, 66, 48) or v.dtype != np.float32 or not np.all(np.isfinite(v)):
                    bad.append(f"grid {i} {nm_} shape {v.shape} finite {bool(np.all(np.isfinite(v)))}")
            if bad:
                break
            w_el = max(w_el, float(np.abs(te - oe).max()))
            w_lv = max(w_lv, float(np.abs(tl - ol).max()))
            rej_flip += int(((tl >= math.log(15.0)) != (ol >= math.log(15.0))).sum())
    del sess
    if bad or not (w_el < 1e-4 and w_lv < 1e-4 and rej_flip == 0):
        os.remove(path)
        print("bad:", bad[:5], "elevation", w_el, "logvar", w_lv, "flips", rej_flip)
        raise SystemExit("EXPORT_MAPPER_ONNX_FAIL (nothing written)")
    meta = {"jit_sha256": sha256(jit_path), "onnx": "mapper_tu.onnx", "onnx_sha256": sha256(path), "opset": 17, "input": {"grid": [1, 1, 66, 48]},
            "outputs": {"elevation": [1, 1, 66, 48], "logvar": [1, 1, 66, 48]}, "checked_grids": n,
            "max_abs_difference": {"elevation": w_el, "logvar": w_lv}, "rejection_decision_flips": rej_flip, "onnxruntime": ort.__version__,
            "export_tool": "v3", "export_tool_md5": hashlib.md5(open(__file__, "rb").read()).hexdigest(),
            "publish_tool_md5": hashlib.md5(open(os.path.join(H, "bundle_publish.py"), "rb").read()).hexdigest()}
    from bundle_publish import publish
    vdir = publish(out, "mapper_tu", {"mapper_tu.onnx": path}, meta)
    print("published", vdir)
    print(json.dumps({k: meta[k] for k in ("onnx_sha256", "checked_grids", "max_abs_difference", "rejection_decision_flips")}, indent=1))
    print("EXPORT_MAPPER_ONNX_OK")


if __name__ == "__main__":
    main()
