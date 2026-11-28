"""Step 3 of the real-robot bundle (TU student + mapper), auxiliary re-run of the REQUIRED test on the deployment onnxruntime (CPU only).

The stored verdict of step 3 is parity.json (written by parity_stu2.py with torch 2.12.0+cpu, 4 threads, onnxruntime 1.26.0): policy pass,
mapper fail, step 3 failed. This tool replays the SAME recorded npz (extract_stu.py: flat = (rough, 0) with the rough sub-terrain made flat,
stairs = (stair_up, 4); 200 policy steps and 40 mapper frames each) with the onnxruntime the caller's interpreter has (meant: 1.18.1, the
deployment version) and reports the same differences plus where the mapper exceeds the threshold. It does NOT write parity.json and does not
change the stored verdict; its output is an auxiliary record.

Compared, as in parity_stu2.py:
  * policy: the ORIGINAL AME2GazeLSIOModel (agent.yaml actor block, strict load of actor_state_dict, eval, forward(return_latent=True))
    vs onnxruntime CPU on the bundle ONNX, one step at a time on the recorded inputs (the 20-row history is a recorded input);
  * mapper: the TorchScript mapper of the training loop vs onnxruntime CPU on the bundle mapper ONNX, every recorded frame of the two tags.
Rule of the required test (parity_stu2.py:147-153): a value passes when it is <= 1e-4 (it fails only above), and the mapper also needs
0 flipped rejection decisions (logvar >= ln 15). Counts with ">= 1e-4" are given separately (the rule of the whole-record statistics).

usage: python rerun_ort1181.py <extract npz> <ckpt> <agent.yaml> <onnx> <mapper_jit> <mapper_onnx> <rsl dir> <out json> <torch threads,...>
"""
import hashlib
import json
import math
import os
import platform
import sys
import types

import numpy as np
import torch

EX, CKPT, AGENT, ONNX, MJIT, MONNX, RSL, OUT, THREADS = sys.argv[1:10]
TOL = 1e-4
REJ = math.log(15.0)
SHA = {"ckpt": "34eba83771f7564f93c163afdfcbefa8620780c44b920e2edb0a1c9b49d42793", "agent": "696820297cfa5e1bd064f270e20201698702bb8b964912d30eb0438c41038f05",
       "onnx": "9349fd6c7af1afbf430f9a0a89678432b5dd6497ac2d5178868d3eb2b904fdb0", "mapper_jit": "52dd869b9fe5bc0ee1973138e72d56d66bee459626da36fed2e2efa716a0e060",
       "mapper_onnx": "8d726de016460f5c4911204116ff4828105c84e80e2bb4d8d71f58f0bb3274d8"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


for k, p in (("ckpt", CKPT), ("agent", AGENT), ("onnx", ONNX), ("mapper_jit", MJIT), ("mapper_onnx", MONNX)):
    if sha256(p) != SHA[k]:
        sys.exit(f"RERUN_FAIL {k} sha256 is not the bundle's")
sys.modules.setdefault("tensordict", types.SimpleNamespace(TensorDict=dict))
sys.path.insert(0, RSL)
from rsl_rl.models.AME2_models import AME2GazeLSIOModel  # noqa: E402
import yaml  # noqa: E402
import onnxruntime as ort  # noqa: E402

cfg = yaml.safe_load(open(AGENT))["actor"]
obs0 = {"neural_map": torch.zeros(1, 29, 13, 4), "student_prop_hist": torch.zeros(1, 20, 42), "student_cmds": torch.zeros(1, 4)}
model = AME2GazeLSIOModel(obs0, {"actor": list(obs0)}, "actor", 12, **{k: v for k, v in cfg.items() if k != "class_name"})
ck = torch.load(CKPT, map_location="cpu", weights_only=False)
load = model.load_state_dict(ck["actor_state_dict"], strict=True)
model.eval()
jm = torch.jit.load(MJIT, map_location="cpu").eval()
so = ort.SessionOptions()
so.intra_op_num_threads, so.inter_op_num_threads = 2, 1
sess = ort.InferenceSession(ONNX, so, providers=["CPUExecutionProvider"])
msess = ort.InferenceSession(MONNX, so, providers=["CPUExecutionProvider"])
IN = [i.name for i in sess.get_inputs()]
ON = [o.name for o in sess.get_outputs()]
assert IN == ["neural_map", "prop_hist", "cmds"] and ON == ["actions", "attn_out", "global_feat"], (IN, ON)
z = np.load(EX)
meta = json.loads(str(z["meta_json"]))
runs = []
for nt in [int(x) for x in THREADS.split(",")]:
    torch.set_num_threads(nt)
    res = {"torch_threads": nt, "tags": {}}
    for tag in ("flat", "stairs"):
        M, H, C = z[f"{tag}_nmap"].astype(np.float32), z[f"{tag}_prop"].astype(np.float32), z[f"{tag}_cmd"].astype(np.float32)
        T = M.shape[0]
        w = {"actions": 0.0, "attn_out": 0.0, "global_feat": 0.0}
        step_of_max = 0
        with torch.no_grad():
            for t in range(T):
                tm, th, tc = torch.from_numpy(M[t:t + 1]), torch.from_numpy(H[t:t + 1]), torch.from_numpy(C[t:t + 1])
                ref = [x[0].numpy() for x in model({"neural_map": tm, "student_prop_hist": th, "student_cmds": tc}, return_latent=True)]
                on = [o[0] for o in sess.run(ON, {"neural_map": M[t:t + 1], "prop_hist": H[t:t + 1], "cmds": C[t:t + 1]})]
                d = float(np.abs(on[0] - ref[0]).max())
                if d > w["actions"]:
                    w["actions"], step_of_max = d, t
                w["attn_out"] = max(w["attn_out"], float(np.abs(on[1] - ref[1]).max()))
                w["global_feat"] = max(w["global_feat"], float(np.abs(on[2] - ref[2]).max()))
        G = z[f"{tag}_frame_grid"].astype(np.float32)
        fs = [int(x - z[f"{tag}_counter"][0]) for x in z[f"{tag}_frame_counter"]]
        me = ml = 0.0
        flips = 0
        over, ge, worst = [], [], None
        with torch.no_grad():
            for k in range(G.shape[0]):
                te, tl = (x[0, 0].numpy() for x in jm(torch.from_numpy(G[k:k + 1, None])))
                oe, ol = msess.run(["elevation", "logvar"], {"grid": G[k:k + 1, None]})
                de, dl = np.abs(oe[0, 0] - te), np.abs(ol[0, 0] - tl)
                if float(de.max()) > me:
                    i, j = np.unravel_index(int(de.argmax()), de.shape)
                    worst = {"policy_step": fs[k], "frame_index": k, "cell_x_index": int(i), "cell_y_index": int(j), "elevation_diff_m": float(de.max())}
                me, ml = max(me, float(de.max())), max(ml, float(dl.max()))
                flips += int(((ol[0, 0] >= REJ) != (tl >= REJ)).sum())
                if float(de.max()) > TOL:
                    over.append(fs[k])
                if max(float(de.max()), float(dl.max())) >= TOL:
                    ge.append(fs[k])
        ep = z[f"{tag}_ep"]
        res["tags"][tag] = {"cell": meta["tags"][tag]["cell"], "steps": int(T), "resets_in_recording": int((np.diff(ep) != 0).sum()),
                            "max_abs_action_onnx_vs_torch": w["actions"], "step_of_max": step_of_max,
                            "max_abs_attn_out_onnx_vs_torch": w["attn_out"], "max_abs_global_feat_onnx_vs_torch": w["global_feat"],
                            "mapper_frames": int(G.shape[0]), "mapper_frame_policy_steps_first8": fs[:8],
                            "mapper_max_abs_elevation_onnx_vs_jit": me, "mapper_max_abs_logvar_onnx_vs_jit": ml,
                            "mapper_rejection_flips_ln15": flips,
                            "mapper_frames_elevation_above_threshold": len(over), "mapper_policy_steps_elevation_above_threshold": over,
                            "mapper_frames_elevation_or_logvar_at_or_above_threshold": len(ge), "mapper_worst_elevation": worst}
        print(nt, tag, json.dumps(res["tags"][tag]), flush=True)
    pol = max(max(res["tags"][t][k] for k in ("max_abs_action_onnx_vs_torch", "max_abs_attn_out_onnx_vs_torch", "max_abs_global_feat_onnx_vs_torch")) for t in res["tags"])
    mp = max(max(res["tags"][t]["mapper_max_abs_elevation_onnx_vs_jit"], res["tags"][t]["mapper_max_abs_logvar_onnx_vs_jit"]) for t in res["tags"])
    fl = sum(res["tags"][t]["mapper_rejection_flips_ln15"] for t in res["tags"])
    res.update({"max_abs_policy_outputs": pol, "max_abs_mapper_onnx_vs_jit": mp, "mapper_rejection_flips": fl,
                "policy_within_threshold": bool(pol <= TOL), "mapper_within_threshold": bool(mp <= TOL and fl == 0)})
    runs.append(res)
out = {"what": "auxiliary re-run of the required flat / stairs 200-step test; it does not replace the stored verdict of parity.json",
       "threshold": TOL, "rule": "a value is within the threshold when it is <= 1e-4; the mapper also needs 0 flipped rejection decisions (logvar >= ln 15)",
       "runtime": {"onnxruntime": ort.__version__, "provider": "CPUExecutionProvider", "ort_graph_optimization": "default (ORT_ENABLE_ALL)",
                   "ort_intra_op_threads": 2, "ort_inter_op_threads": 1, "torch_reference": torch.__version__, "numpy": np.__version__,
                   "python": platform.python_version(), "machine": platform.machine(), "processor": platform.processor()},
       "inputs": {"recording_npz": {"name": os.path.basename(EX), "sha256": sha256(EX)},
                  "checkpoint_sha256": SHA["ckpt"], "agent_yaml_sha256": SHA["agent"], "onnx_sha256": SHA["onnx"],
                  "mapper_jit_sha256": SHA["mapper_jit"], "mapper_onnx_sha256": SHA["mapper_onnx"],
                  "AME2_models_py_sha256": sha256(os.path.join(RSL, "rsl_rl", "models", "AME2_models.py"))},
       "load_state_dict": {"strict": True, "missing": list(load.missing_keys), "unexpected": list(load.unexpected_keys)},
       "recording_torch": meta["torch"], "recording_code": meta["code"], "runs": runs}
json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
print("RERUN_DONE", os.path.basename(OUT))
