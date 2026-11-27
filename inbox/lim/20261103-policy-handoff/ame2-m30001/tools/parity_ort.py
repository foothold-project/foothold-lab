"""AME-2 app handoff (2026-11-03), step 3b: ONNX (onnxruntime CPU) on the recorded env inputs vs the original PyTorch.

  python -I parity_ort.py <onnx> <dir with ref_flat.npz, ref_stairs.npz, ref_info.json, rec_meta.json> <out dir>
Writes <out>/parity.json and <out>/test_vectors_flat20.npz (first 20 flat steps). Threshold 1e-4 on action.
"""

import hashlib
import json
import os
import sys

import numpy as np
import onnxruntime as ort

ONNX, REF, OUT = sys.argv[1:4]
TH = 1e-4


def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


so = ort.SessionOptions()
s = ort.InferenceSession(ONNX, sess_options=so, providers=["CPUExecutionProvider"])
meta = json.load(open(os.path.join(REF, "rec_meta.json")))
refinfo = json.load(open(os.path.join(REF, "ref_info.json")))
res = {"tags": {}}
worst = 0.0
for tag in ("flat", "stairs"):
    z = np.load(os.path.join(REF, f"ref_{tag}.npz"))
    P, M = z["prop"].astype(np.float32), z["mapping"].astype(np.float32)
    A, R, LG, OF = [], [], [], []
    for t in range(P.shape[0]):
        a, r, lg, off = s.run(["action", "gaze_r", "gaze_logits", "gaze_offset"], {"prop": P[t : t + 1], "mapping": M[t : t + 1]})
        A.append(a[0])
        R.append(r[0])
        LG.append(lg[0])
        OF.append(off[0])
    A, R, LG, OF = np.stack(A), np.stack(R), np.stack(LG), np.stack(OF)
    d = np.abs(A - z["action_torch"])
    worst = max(worst, float(d.max()))
    res["tags"][tag] = {
        "steps": int(P.shape[0]),
        "resets_in_recording": int(z["done"].sum()),
        "max_abs_action_onnx_vs_torch": float(d.max()),
        "mean_abs_action_onnx_vs_torch": float(d.mean()),
        "step_of_max": int(d.max(axis=1).argmax()),
        "max_abs_gaze_r_onnx_vs_torch": float(np.abs(R - z["gaze_r_torch"]).max()),
        "max_abs_gaze_logits_onnx_vs_torch": float(np.abs(LG - z["gaze_logits_torch"]).max()),
        "gaze_offset_steps_differing": int((np.abs(OF - z["gaze_offset_torch"]).max(axis=1) > 0).sum()),
        "max_abs_action_onnx_vs_env_gpu": float(np.abs(A - z["action"]).max()),
        "max_abs_action_torch_cpu_vs_env_gpu": refinfo[tag]["max_abs_torch_cpu_vs_env_gpu"],
        "max_abs_action_torch_vs_jit_twin": refinfo[tag]["max_abs_torch_vs_jit_twin"],
        "max_abs_action": float(np.abs(z["action_torch"]).max()),
    }
    if tag == "flat":
        n = 20
        np.savez(
            os.path.join(OUT, "test_vectors_flat20.npz"),
            prop=P[:n], mapping=M[:n], action=z["action_torch"][:n].astype(np.float32), gaze_r=z["gaze_r_torch"][:n].astype(np.float32),
            gaze_logits=z["gaze_logits_torch"][:n].astype(np.float32), gaze_offset=z["gaze_offset_torch"][:n].astype(np.float32),
            action_onnx_cpu=A[:n].astype(np.float32), action_env_gpu=z["action"][:n].astype(np.float32),
            target_q=z["target_q"][:n].astype(np.float32), done=z["done"][:n],
            readme=np.array(
                "AME-2 teacher X7C (average of the last five checkpoints 13000 .. 14999 of the x7 run, 30,001 updates counted; the teacher the REQ428 students were distilled from) (sha256 " + meta["checkpoint_sha256"] + "). 20 consecutive control steps (50 Hz) on a flat tile, "
                "recorded from the training env (observation noise off). Inputs: prop [20,49], mapping [20,29,13,3] (float32), fed one step "
                "at a time as [1,49] / [1,29,13,3]. Answer: action [20,12] = original PyTorch forward on CPU float32 (deterministic mean); "
                "gaze_r [20,2] = sigmoid gaze location; gaze_logits [20,2] = gaze head output before the sigmoid; gaze_offset [20,2] = "
                "integer crop corner (ox over x 0..17, oy over y 0..3) as float32. action_onnx_cpu = onnxruntime CPU output of the bundle ONNX (" + os.path.basename(ONNX) + "); action_env_gpu = what "
                "the policy produced inside the env on the GPU (TF32/kernel differences, not the parity reference). target_q = joint "
                "targets after the env's action term (default + 0.25 * action). Joint order: FL_hip, FR_hip, RL_hip, RR_hip, FL_thigh, "
                "FR_thigh, RL_thigh, RR_thigh, FL_calf, FR_calf, RL_calf, RR_calf. Compare your output to action with max abs diff <= 1e-4."
            ),
        )
res["max_abs_action_onnx_vs_torch"] = worst
res["threshold"] = TH
res["pass"] = bool(worst <= TH)
res["onnx"] = {"file": os.path.basename(ONNX), "sha256": sha256(ONNX), "bytes": os.path.getsize(ONNX)}
res["runtime"] = {"onnxruntime": ort.__version__, "provider": "CPUExecutionProvider", "torch_reference": refinfo.get("torch")}
res["checkpoint_sha256"] = meta["checkpoint_sha256"]
res["recording"] = {k: meta[k] for k in ("task", "steps", "step_dt", "physics_dt", "decimation", "terrain_columns", "terrain_levels",
                                          "changes_from_training_cfg", "checks", "resets_in_recording", "code_id")}
res["default_pose_test"] = {k: v for k, v in meta["default_pose_test"].items() if "names" not in k}
with open(os.path.join(OUT, "parity.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f, indent=1, ensure_ascii=False)
print("PARITY", json.dumps({"max": worst, "pass": res["pass"], "flat": res["tags"]["flat"]["max_abs_action_onnx_vs_torch"],
                            "stairs": res["tags"]["stairs"]["max_abs_action_onnx_vs_torch"]}))
if not res["pass"]:
    print("PARITY_FAIL")
    sys.exit(3)
print("PARITY_OK")
