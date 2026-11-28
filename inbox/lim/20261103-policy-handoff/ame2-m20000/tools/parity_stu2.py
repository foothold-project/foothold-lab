"""Step 3 of the real-robot bundle (TU student + mapper): same-output check on the recorded student evaluation env (CPU only).
Input: the npz of extract_stu.py (tags flat = (rough, 0) with the rough sub-terrain made flat, stairs = (stair_up, 4); 200 policy steps each).
  * policy: the ORIGINAL AME2GazeLSIOModel (agent.yaml actor block, strict load of actor_state_dict, eval, forward = the evaluation path)
    vs onnxruntime CPU on the bundle ONNX (batch 1), plus the original as_jit twin; no recurrent state (the 20-step history is an input);
  * mapper: the TorchScript mapper of the training loop vs onnxruntime CPU on the bundle mapper ONNX, every recorded frame of the tags;
  * layout checks of the recorded observation against the recorded robot state.
Threshold 1e-4 on every output (actions, attn_out, global_feat, mapper elevation, mapper logvar) and no flip of the fusion rejection
(logvar >= ln 15). Writes parity.json; ONLY IF everything passes, also the test vectors (policy: test_vectors_flat20.json / .npz, mapper:
test_vectors_flat20_mapper.json / .npz). Exit 3 if not passed (the instruction: stop when above the threshold).
usage: python parity_stu2.py <extract npz> <ckpt> <agent.yaml> <onnx> <mapper_jit> <mapper_onnx> <rsl dir> <out dir> <name>"""
import hashlib
import json
import math
import os
import sys
import types

import numpy as np
import torch

EX, CKPT, AGENT, ONNX, MJIT, MONNX, RSL, OUT, NAME = sys.argv[1:10]
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
        sys.exit(f"PARITY_STU_FAIL {k} sha256 is not the bundle's")
os.makedirs(OUT, exist_ok=True)
torch.set_num_threads(4)
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
twin = model.as_jit().eval()
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
q0 = np.array(meta["default_joint_pos"], np.float32)
res = {"tags": {}}
refs = {}
for tag in ("flat", "stairs"):
    M, H, C = z[f"{tag}_nmap"].astype(np.float32), z[f"{tag}_prop"].astype(np.float32), z[f"{tag}_cmd"].astype(np.float32)
    T = M.shape[0]
    w = {"actions": 0.0, "attn_out": 0.0, "global_feat": 0.0}
    twin_d = gpu_d = cpu_gpu = mx = 0.0
    step_of_max, means, R = 0, [], []
    with torch.no_grad():
        for t in range(T):
            tm, th, tc = torch.from_numpy(M[t:t + 1]), torch.from_numpy(H[t:t + 1]), torch.from_numpy(C[t:t + 1])
            ref = [x[0].numpy() for x in model({"neural_map": tm, "student_prop_hist": th, "student_cmds": tc}, return_latent=True)]
            tw = twin(tm, th, tc)[0][0].numpy()
            on = [o[0] for o in sess.run(ON, {"neural_map": M[t:t + 1], "prop_hist": H[t:t + 1], "cmds": C[t:t + 1]})]
            d = float(np.abs(on[0] - ref[0]).max())
            if d > w["actions"]:
                w["actions"], step_of_max = d, t
            means.append(float(np.abs(on[0] - ref[0]).mean()))
            w["attn_out"] = max(w["attn_out"], float(np.abs(on[1] - ref[1]).max()))
            w["global_feat"] = max(w["global_feat"], float(np.abs(on[2] - ref[2]).max()))
            twin_d = max(twin_d, float(np.abs(tw - ref[0]).max()))
            gpu_d = max(gpu_d, float(np.abs(on[0] - z[f"{tag}_act"][t]).max()))
            cpu_gpu = max(cpu_gpu, float(np.abs(ref[0] - z[f"{tag}_act"][t]).max()))
            mx = max(mx, float(np.abs(ref[0]).max()))
            R.append(ref)
    refs[tag] = R
    G = z[f"{tag}_frame_grid"].astype(np.float32)
    me = ml = mge = mgl = 0.0
    flips = 0
    MREF = []
    with torch.no_grad():
        for k in range(G.shape[0]):
            te, tl = (x[0, 0].numpy() for x in jm(torch.from_numpy(G[k:k + 1, None])))
            oe, ol = msess.run(["elevation", "logvar"], {"grid": G[k:k + 1, None]})
            me, ml = max(me, float(np.abs(oe[0, 0] - te).max())), max(ml, float(np.abs(ol[0, 0] - tl).max()))
            mge = max(mge, float(np.abs(te - z[f"{tag}_frame_mean"][k]).max()))
            mgl = max(mgl, float(np.abs(tl - z[f"{tag}_frame_logvar"][k]).max()))
            flips += int(((ol[0, 0] >= REJ) != (tl >= REJ)).sum())
            MREF.append((te, tl))
    refs[tag + "_mapper"] = MREF
    ep = z[f"{tag}_ep"]
    res["tags"][tag] = {"cell": meta["tags"][tag]["cell"], "steps": int(T), "resets_in_recording": int((np.diff(ep) != 0).sum()),
                        "max_abs_action_onnx_vs_torch": w["actions"], "mean_abs_action_onnx_vs_torch": float(np.mean(means)), "step_of_max": step_of_max,
                        "max_abs_attn_out_onnx_vs_torch": w["attn_out"], "max_abs_global_feat_onnx_vs_torch": w["global_feat"],
                        "max_abs_action_torch_vs_jit_twin": twin_d, "max_abs_action_onnx_vs_env_gpu": gpu_d, "max_abs_action_torch_cpu_vs_env_gpu": cpu_gpu,
                        "max_abs_action": mx, "mapper_frames": int(G.shape[0]),
                        "mapper_max_abs_elevation_onnx_vs_jit": me, "mapper_max_abs_logvar_onnx_vs_jit": ml, "mapper_rejection_flips_ln15": flips,
                        "mapper_max_abs_elevation_jit_cpu_vs_env_gpu": mge, "mapper_max_abs_logvar_jit_cpu_vs_env_gpu": mgl}
    print(tag, json.dumps(res["tags"][tag]), flush=True)

# layout checks (both tags)
chk = {}
for tag in ("flat", "stairs"):
    H = z[f"{tag}_prop"]
    last = H[:, -1, :]
    qt = z[f"{tag}_root_quat"].astype(np.float64)
    w_, xyz = qt[:, :1], qt[:, 1:]
    v = np.broadcast_to(np.array([0.0, 0.0, -1.0]), xyz.shape)
    tt = 2.0 * np.cross(xyz, v)
    g = v - w_ * tt + np.cross(xyz, tt)
    same = z[f"{tag}_ep"][1:] == z[f"{tag}_ep"][:-1]
    c = {"prop_ang_vel_vs_state": float(np.abs(last[:, 0:3] - z[f"{tag}_ang_vel_b"]).max()),
         "prop_gravity_vs_state": float(np.abs(last[:, 3:6] - g).max()),
         "prop_joint_pos_rel_vs_q_minus_q0": float(np.abs(last[:, 6:18] - (z[f"{tag}_q"] - z[f"{tag}_q0"])).max()),
         "q0_vs_default_joint_pos": float(np.abs(z[f"{tag}_q0"] - q0[None]).max()),
         "prop_joint_vel_vs_dq": float(np.abs(last[:, 18:30] - (z[f"{tag}_dq"] - z[f"{tag}_dq0"])).max()),
         "prop_last_action_vs_clip50": float(np.abs(last[:, 30:42] - np.clip(z[f"{tag}_last_action"], -50, 50)).max()),
         "last_action_vs_previous_raw": float(np.abs(z[f"{tag}_last_action"][1:] - z[f"{tag}_act_raw"][:-1])[same].max()) if same.any() else None,
         "history_shift_max_abs": float(np.abs(H[1:, :-1] - H[:-1, 1:])[same].max()) if same.any() else None,
         "first_row_history_rows_equal": float(np.abs(H[0] - H[0, -1:]).max()),
         "first_row_last_action_max_abs": float(np.abs(z[f"{tag}_last_action"][0]).max()),
         "cmd_xy_norm_max": float(np.linalg.norm(z[f"{tag}_cmd"][:, :2], axis=1).max()),
         "nmap_x_vs_grid": float(np.abs(z[f"{tag}_nmap"][..., 0] - (-0.42 + 0.06 * np.arange(29, dtype=np.float32))[None, :, None]).max()),
         "nmap_y_vs_grid": float(np.abs(z[f"{tag}_nmap"][..., 1] - (-0.36 + 0.06 * np.arange(13, dtype=np.float32))[None, None, :]).max()),
         "nmap_z_range": [float(z[f"{tag}_nmap"][..., 2].min()), float(z[f"{tag}_nmap"][..., 2].max())],
         "nmap_unc_range": [float(z[f"{tag}_nmap"][..., 3].min()), float(z[f"{tag}_nmap"][..., 3].max())],
         "processed_vs_default_plus_0p25_raw": float(np.abs(z[f"{tag}_act_processed"] - (q0[None] + 0.25 * z[f"{tag}_act_raw"])).max()),
         "recorded_act_vs_action_raw": float(np.abs(z[f"{tag}_act"] - z[f"{tag}_act_raw"]).max()),
         "frame_steps": [int(x - z[f"{tag}_counter"][0]) for x in z[f"{tag}_frame_counter"]][:8]}
    chk[tag] = c
res["recording_checks"] = chk
pol = max(max(res["tags"][t][k] for k in ("max_abs_action_onnx_vs_torch", "max_abs_attn_out_onnx_vs_torch", "max_abs_global_feat_onnx_vs_torch")) for t in res["tags"])
mp = max(max(res["tags"][t]["mapper_max_abs_elevation_onnx_vs_jit"], res["tags"][t]["mapper_max_abs_logvar_onnx_vs_jit"]) for t in res["tags"])
fl = sum(res["tags"][t]["mapper_rejection_flips_ln15"] for t in res["tags"])
res.update({"max_abs_action_onnx_vs_torch": max(res["tags"][t]["max_abs_action_onnx_vs_torch"] for t in res["tags"]), "max_abs_policy_outputs": pol,
            "max_abs_mapper_onnx_vs_jit": mp, "mapper_rejection_flips": fl, "threshold": TOL,
            "pass_policy": bool(pol <= TOL), "pass_mapper": bool(mp <= TOL and fl == 0)})
res["pass"] = res["pass_policy"] and res["pass_mapper"]
res["state_feedback"] = False
res["state_note"] = "no recurrent state in either ONNX; the caller builds prop_hist (20 rows, oldest first) and the map"
res["onnx"] = {"file": f"{NAME}.onnx", "source_file": os.path.basename(ONNX), "sha256": SHA["onnx"], "bytes": os.path.getsize(ONNX)}
res["mapper_onnx"] = {"file": f"{NAME}_mapper.onnx", "source_file": os.path.basename(MONNX), "sha256": SHA["mapper_onnx"], "bytes": os.path.getsize(MONNX)}
res["runtime"] = {"onnxruntime": ort.__version__, "provider": "CPUExecutionProvider", "torch_reference": torch.__version__, "intra_op_threads": 2}
res["checkpoint_sha256"] = SHA["ckpt"]
res["mapper_jit_sha256"] = SHA["mapper_jit"]
res["load_state_dict"] = {"strict": True, "missing": list(load.missing_keys), "unexpected": list(load.unexpected_keys)}
res["recording"] = {k: meta[k] for k in ("args", "rec_cells", "step_dt", "physics_dt", "decimation", "noise_none", "code", "torch", "tool_md5", "end_complete", "tags")}
json.dump(res, open(os.path.join(OUT, "parity.json"), "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
print("PARITY", json.dumps({k: res[k] for k in ("max_abs_action_onnx_vs_torch", "max_abs_policy_outputs", "max_abs_mapper_onnx_vs_jit", "mapper_rejection_flips", "pass_policy", "pass_mapper")}))
if not res["pass"]:
    print("PARITY_STU_FAIL above the threshold: no test vectors written (step 3 stops)")
    sys.exit(3)
# test vectors (only after a pass)
n = 20
f32 = lambda a: [float(v) for v in np.asarray(a, np.float32).reshape(-1)]
M, H, C = z["flat_nmap"].astype(np.float32), z["flat_prop"].astype(np.float32), z["flat_cmd"].astype(np.float32)
tv = {"format": f"{NAME}-test-vectors/1", "model": NAME, "checkpoint_sha256": SHA["ckpt"], "onnx": {f"{NAME}.onnx": SHA["onnx"]},
      "map_mode": "reconstruction", "steps": n, "tolerance": TOL, "state_feedback": False,
      "inputs": [{"neural_map": f32(M[k]), "prop_hist": f32(H[k]), "cmds": f32(C[k])} for k in range(n)],
      "expected": [{"actions": f32(refs["flat"][k][0]), "attn_out": f32(refs["flat"][k][1]), "global_feat": f32(refs["flat"][k][2])} for k in range(n)],
      "input_shapes": {"neural_map": [1, 29, 13, 4], "prop_hist": [1, 20, 42], "cmds": [1, 4]},
      "input_types": {"neural_map": "tensor(float)", "prop_hist": "tensor(float)", "cmds": "tensor(float)"}}
json.dump(tv, open(os.path.join(OUT, "test_vectors_flat20.json"), "w", encoding="utf-8", newline="\n"), separators=(",", ":"))
np.savez(os.path.join(OUT, "test_vectors_flat20.npz"), neural_map=M[:n], prop_hist=H[:n], cmds=C[:n],
         actions=np.stack([refs["flat"][k][0] for k in range(n)]).astype(np.float32), attn_out=np.stack([refs["flat"][k][1] for k in range(n)]).astype(np.float32),
         global_feat=np.stack([refs["flat"][k][2] for k in range(n)]).astype(np.float32))
fs = [int(x - z["flat_counter"][0]) for x in z["flat_frame_counter"]]
sel = [i for i, s in enumerate(fs) if s < n]
G = z["flat_frame_grid"].astype(np.float32)
tvm = {"format": f"{NAME}-mapper-test-vectors/1", "model": f"{NAME}_mapper", "onnx": {f"{NAME}_mapper.onnx": SHA["mapper_onnx"]}, "steps": n,
       "frames": len(sel), "tolerance": TOL, "state_feedback": False,
       "note": "the same 20 policy steps as test_vectors_flat20.json; a frame is fused when the range sensors give a new scan (every 5 policy steps); step = policy step of the frame",
       "inputs": [{"step": fs[i], "grid": f32(G[i])} for i in sel],
       "expected": [{"elevation": f32(refs["flat_mapper"][i][0]), "logvar": f32(refs["flat_mapper"][i][1])} for i in sel],
       "input_shapes": {"grid": [1, 1, 66, 48]}, "input_types": {"grid": "tensor(float)"}}
json.dump(tvm, open(os.path.join(OUT, "test_vectors_flat20_mapper.json"), "w", encoding="utf-8", newline="\n"), separators=(",", ":"))
np.savez(os.path.join(OUT, "test_vectors_flat20_mapper.npz"), step=np.array([fs[i] for i in sel]), grid=G[sel],
         elevation=np.stack([refs["flat_mapper"][i][0] for i in sel]).astype(np.float32), logvar=np.stack([refs["flat_mapper"][i][1] for i in sel]).astype(np.float32))
print("PARITY_STU_OK vectors written")
