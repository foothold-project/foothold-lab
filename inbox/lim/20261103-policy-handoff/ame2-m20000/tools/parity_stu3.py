"""Step 3 judge of the real-robot bundle (TU student + mapper), 3rd version: parity_stu2.py plus guards (Codex 430_55 P1, 430_55b P2-3 / P2-4).

parity_stu2.py takes the maximum of the differences with max(old, new): when a compared array holds NaN the new value is NaN and the old
maximum is kept, so NaN in exactly the frames that exceed the threshold makes the mapper look fine. It also loops over whatever length the
npz has. This version refuses to judge unless
  (1) the files are the fixed ones: sha256 of the npz, the checkpoint, agent.yaml, the two ONNX, the mapper TorchScript AND of the reference
      policy code actually imported (rsl_rl/models/AME2_models.py, read from the path of the imported module);
  (2) the recording is complete: the two terrains (flat = (rough, 0), stairs = (stair_up, 4)), one episode (0) without a reset, exactly 200
      consecutive policy steps, exactly 40 mapper frames at policy steps 0, 5, .. 195, the array shapes, the recording's task / seed /
      checkpoint / mapper fingerprints / step times / noise-off flags;
  (3) every compared array is finite: the recorded inputs and outputs, every output of the original models and of onnxruntime, and every
      difference, checked BEFORE it enters a maximum.
Everything else is parity_stu2.py: the ORIGINAL AME2GazeLSIOModel (strict load, eval, forward) and its as_jit twin vs onnxruntime CPU on the
bundle ONNX, one policy step at a time; the TorchScript mapper of the training loop vs onnxruntime CPU on the bundle mapper ONNX, every
recorded frame; the layout checks. Rule: a value passes when it is <= 1e-4 (fails only above); the mapper also needs 0 flipped rejection
decisions (logvar >= ln 15). Maxima and the verdict use float64 differences.

Output: the run needs a folder that does not exist yet and creates it itself (one run owns one folder). After a pass the four test-vector
files are written and read back first; the result file, which names them with their sha256, is written last (temporary name, then renamed).

The verdict stored in the bundle's parity.json (2026-11-27) was produced by parity_stu2.py, not by this file.

exit codes: 0 pass (vectors, then the result) | 3 a valid recording above the threshold (as parity_stu2.py) | 4 the content of the recording
or a compared array is not acceptable (no verdict) | 1 a file fingerprint is not the fixed one, or the output folder exists
usage: python parity_stu3.py <extract npz> <ckpt> <agent.yaml> <onnx> <mapper_jit> <mapper_onnx> <rsl dir> <new out dir> <name> [<result file name>]
"""
import hashlib
import json
import math
import os
import sys
import types

import numpy as np
import torch

TOL = 1e-4
REJ = math.log(15.0)
SHA = {"npz": "24bc73a38426606b26a9fba6b1bc485a0eeef2ef3c7ccb774ba66133d6441cdf",
       "ckpt": "34eba83771f7564f93c163afdfcbefa8620780c44b920e2edb0a1c9b49d42793", "agent": "696820297cfa5e1bd064f270e20201698702bb8b964912d30eb0438c41038f05",
       "onnx": "9349fd6c7af1afbf430f9a0a89678432b5dd6497ac2d5178868d3eb2b904fdb0", "mapper_jit": "52dd869b9fe5bc0ee1973138e72d56d66bee459626da36fed2e2efa716a0e060",
       "mapper_onnx": "8d726de016460f5c4911204116ff4828105c84e80e2bb4d8d71f58f0bb3274d8",
       "models_py": "d88276b1a9cac8c676828af7991f50c7515726245210f5f6c09ae34c4466d14d"}
TAGS = {"flat": ["rough", 0], "stairs": ["stair_up", 4]}
TASK, SEED = "Ame2-Go2-Gaze-Student-N9P12-Eval5", 42
N_STEPS, N_FRAMES, FRAME_PERIOD = 200, 40, 5
SHAPES = {"nmap": (N_STEPS, 29, 13, 4), "prop": (N_STEPS, 20, 42), "cmd": (N_STEPS, 4), "act": (N_STEPS, 12), "ang_vel_b": (N_STEPS, 3), "root_quat": (N_STEPS, 4),
          "q": (N_STEPS, 12), "q0": (N_STEPS, 12), "dq": (N_STEPS, 12), "dq0": (N_STEPS, 12), "last_action": (N_STEPS, 12), "act_raw": (N_STEPS, 12),
          "act_processed": (N_STEPS, 12), "frame_grid": (N_FRAMES, 66, 48), "frame_mean": (N_FRAMES, 66, 48), "frame_logvar": (N_FRAMES, 66, 48)}


class JudgeFail(Exception):
    """the content of the recording or a compared array is not acceptable: no verdict (exit code 4)"""

    def __init__(self, kind, msg):
        super().__init__(f"{kind}: {msg}")
        self.kind, self.msg = kind, msg


class FileMismatch(Exception):
    """a file is not the fixed one (exit code 1)"""


class Finite:
    """counts the arrays it has seen; raises at the first non-finite value"""

    def __init__(self):
        self.arrays = 0

    def __call__(self, name, a):
        a = np.asarray(a)
        self.arrays += 1
        if a.dtype.kind not in "fiu" or not bool(np.all(np.isfinite(a))):
            bad = int(a.size - np.isfinite(a).sum()) if a.dtype.kind == "f" else a.size
            raise JudgeFail("non_finite", f"{name}: {bad} non-finite values of {a.size}")
        return a

    def diff(self, name, a, b):
        """max |a - b| (float64) of two finite arrays of the same shape"""
        a, b = np.asarray(a), np.asarray(b)
        if a.shape != b.shape:
            raise JudgeFail("shape", f"{name}: {a.shape} vs {b.shape}")
        d = np.abs(self(name + " (left)", a).astype(np.float64) - self(name + " (right)", b).astype(np.float64))
        return float(self(name + " (difference)", d).max())


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_record(Z, meta):
    """The recording is the one this judge was fixed for and it is complete. Z: dict of the npz arrays. Returns the list of checks done."""
    done = []

    def need(ok, what):
        if not ok:
            raise JudgeFail("record", what)
        done.append(what)

    need(meta.get("args", {}).get("task") == TASK and int(meta.get("seed", -1)) == SEED, f"task {TASK}, seed {SEED}")
    need(meta.get("student428", {}).get("checkpoint_sha256") == SHA["ckpt"] and meta["student428"].get("mapper_sha256") == SHA["mapper_jit"],
         "the recording's checkpoint and mapper fingerprints are the bundle's")
    need(meta.get("end_complete") is True and all(meta.get("noise_none", {}).get(k) is True for k in ("student_prop_hist", "student_cmds", "neural_map")),
         "the recording ended complete, noise of the three student groups off")
    need((meta.get("step_dt"), meta.get("physics_dt"), meta.get("decimation"), meta.get("frame_period_steps")) == (0.02, 0.005, 4, FRAME_PERIOD),
         "step 0.02 s, physics 0.005 s x 4, mapper frame every 5 policy steps")
    need(sorted(meta.get("tags", {})) == sorted(TAGS), "exactly the two tags flat and stairs")
    for tag, cell in TAGS.items():
        t = meta["tags"][tag]
        need(list(t.get("cell", [])) == cell and t.get("episodes_in_rows") == [0] and t.get("policy_rows") == N_STEPS and t.get("frames") == N_FRAMES,
             f"{tag}: cell {cell}, episode 0 only, {N_STEPS} policy rows, {N_FRAMES} frames (meta)")
        for k, shp in SHAPES.items():
            key = f"{tag}_{k}"
            need(key in Z and tuple(Z[key].shape) == shp and Z[key].dtype == np.float32, f"{key}: float32 {shp}")
        c = np.asarray(Z[f"{tag}_counter"])
        need(c.shape == (N_STEPS,) and bool(np.all(np.diff(c) == 1)), f"{tag}: {N_STEPS} consecutive policy steps")
        need(np.asarray(Z[f"{tag}_ep"]).shape == (N_STEPS,) and bool(np.all(np.asarray(Z[f"{tag}_ep"]) == 0)), f"{tag}: every row in episode 0 (no reset)")
        need(np.array_equal(np.asarray(Z[f"{tag}_ep_len"]), np.arange(N_STEPS)), f"{tag}: episode steps 0 .. {N_STEPS - 1}")
        need(np.array_equal(np.asarray(Z[f"{tag}_act_counter"]), c), f"{tag}: one action row per policy step")
        fc = np.asarray(Z[f"{tag}_frame_counter"])
        need(fc.shape == (N_FRAMES,) and np.array_equal(fc - c[0], np.arange(0, N_STEPS, FRAME_PERIOD)),
             f"{tag}: {N_FRAMES} mapper frames at policy steps 0, {FRAME_PERIOD}, .. {N_STEPS - FRAME_PERIOD}")
    return done


def import_reference(rsl):
    """Import the reference policy class and check the fingerprint of the file the module was REALLY loaded from.
    Returns (class, record of the imported rsl_rl files: path inside the package -> sha256)."""
    sys.modules.setdefault("tensordict", types.SimpleNamespace(TensorDict=dict))
    if rsl not in sys.path:
        sys.path.insert(0, rsl)
    from rsl_rl.models.AME2_models import AME2GazeLSIOModel

    mod_file = sys.modules[AME2GazeLSIOModel.__module__].__file__
    got = sha256(mod_file)
    if got != SHA["models_py"]:
        raise FileMismatch(f"AME2_models.py sha256 is not the fixed one (imported file {os.path.basename(mod_file)}: {got[:12]})")
    files = {}
    for name, m in sorted(sys.modules.items()):
        f = getattr(m, "__file__", None)
        if (name == "rsl_rl" or name.startswith("rsl_rl.")) and f and os.path.isfile(f):
            files[name.replace(".", "/") + ("/__init__.py" if os.path.basename(f) == "__init__.py" else ".py")] = sha256(f)
    return AME2GazeLSIOModel, {"pinned": {"rsl_rl/models/AME2_models.py": got}, "imported_rsl_rl_files_recorded_not_pinned": files}


def load_models(ckpt, agent, onnx, mjit, monnx, rsl):
    AME2GazeLSIOModel, code = import_reference(rsl)
    import yaml
    import onnxruntime as ort

    torch.set_num_threads(4)
    cfg = yaml.safe_load(open(agent))["actor"]
    obs0 = {"neural_map": torch.zeros(1, 29, 13, 4), "student_prop_hist": torch.zeros(1, 20, 42), "student_cmds": torch.zeros(1, 4)}
    model = AME2GazeLSIOModel(obs0, {"actor": list(obs0)}, "actor", 12, **{k: v for k, v in cfg.items() if k != "class_name"})
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    load = model.load_state_dict(ck["actor_state_dict"], strict=True)
    model.eval()
    twin = model.as_jit().eval()
    jm = torch.jit.load(mjit, map_location="cpu").eval()
    so = ort.SessionOptions()
    so.intra_op_num_threads, so.inter_op_num_threads = 2, 1
    sess = ort.InferenceSession(onnx, so, providers=["CPUExecutionProvider"])
    msess = ort.InferenceSession(monnx, so, providers=["CPUExecutionProvider"])
    names = ([i.name for i in sess.get_inputs()], [o.name for o in sess.get_outputs()])
    assert names == (["neural_map", "prop_hist", "cmds"], ["actions", "attn_out", "global_feat"]), names
    return {"model": model, "twin": twin, "jm": jm, "sess": sess, "msess": msess, "load": load, "ort": ort.__version__, "reference_code": code}


def judge(Z, meta, mdl):
    """Z: dict of the npz arrays (already known to be the fixed recording, or a test input). Raises JudgeFail; returns (result, references)."""
    fin = Finite()
    record = check_record(Z, meta)
    q0 = np.array(meta["default_joint_pos"], np.float32)
    fin("default_joint_pos", q0)
    for tag in TAGS:  # every recorded array that is compared or fed, before any model runs
        for k in SHAPES:
            fin(f"{tag}_{k}", Z[f"{tag}_{k}"])
    model, twin, jm, sess, msess = (mdl[k] for k in ("model", "twin", "jm", "sess", "msess"))
    ON = ["actions", "attn_out", "global_feat"]
    res = {"tags": {}}
    refs = {}
    for tag in TAGS:
        M, H, C, ACT = (np.asarray(Z[f"{tag}_{k}"], np.float32) for k in ("nmap", "prop", "cmd", "act"))
        w = {"actions": 0.0, "attn_out": 0.0, "global_feat": 0.0}
        twin_d = gpu_d = cpu_gpu = mx = 0.0
        step_of_max, means, R = 0, [], []
        with torch.no_grad():
            for t in range(N_STEPS):
                tm, th, tc = torch.from_numpy(M[t:t + 1]), torch.from_numpy(H[t:t + 1]), torch.from_numpy(C[t:t + 1])
                ref = [x[0].numpy() for x in model({"neural_map": tm, "student_prop_hist": th, "student_cmds": tc}, return_latent=True)]
                tw = twin(tm, th, tc)[0][0].numpy()
                on = [o[0] for o in sess.run(ON, {"neural_map": M[t:t + 1], "prop_hist": H[t:t + 1], "cmds": C[t:t + 1]})]
                d = fin.diff(f"{tag} step {t} actions onnx vs torch", on[0], ref[0])
                if d > w["actions"]:
                    w["actions"], step_of_max = d, t
                means.append(float(np.abs(on[0].astype(np.float64) - ref[0].astype(np.float64)).mean()))  # float64, as the maxima
                w["attn_out"] = max(w["attn_out"], fin.diff(f"{tag} step {t} attn_out onnx vs torch", on[1], ref[1]))
                w["global_feat"] = max(w["global_feat"], fin.diff(f"{tag} step {t} global_feat onnx vs torch", on[2], ref[2]))
                twin_d = max(twin_d, fin.diff(f"{tag} step {t} actions twin vs torch", tw, ref[0]))
                gpu_d = max(gpu_d, fin.diff(f"{tag} step {t} actions onnx vs env", on[0], ACT[t]))
                cpu_gpu = max(cpu_gpu, fin.diff(f"{tag} step {t} actions torch vs env", ref[0], ACT[t]))
                mx = max(mx, float(np.abs(ref[0].astype(np.float64)).max()))
                R.append(ref)
        refs[tag] = R
        G, FM, FL = (np.asarray(Z[f"{tag}_{k}"], np.float32) for k in ("frame_grid", "frame_mean", "frame_logvar"))
        fs = [int(x - Z[f"{tag}_counter"][0]) for x in Z[f"{tag}_frame_counter"]]
        me = ml = mge = mgl = 0.0
        flips, over, worst, MREF = 0, [], None, []
        with torch.no_grad():
            for k in range(N_FRAMES):
                te, tl = (x[0, 0].numpy() for x in jm(torch.from_numpy(G[k:k + 1, None])))
                oe, ol = msess.run(["elevation", "logvar"], {"grid": G[k:k + 1, None]})
                de = fin.diff(f"{tag} frame {k} elevation onnx vs jit", oe[0, 0], te)
                dl = fin.diff(f"{tag} frame {k} logvar onnx vs jit", ol[0, 0], tl)
                if de > me:
                    i, j = np.unravel_index(int(np.abs(oe[0, 0].astype(np.float64) - te.astype(np.float64)).argmax()), te.shape)
                    worst = {"policy_step": fs[k], "frame_index": k, "cell_x_index": int(i), "cell_y_index": int(j), "elevation_diff_m": de}
                me, ml = max(me, de), max(ml, dl)
                mge = max(mge, fin.diff(f"{tag} frame {k} elevation jit vs env", te, FM[k]))
                mgl = max(mgl, fin.diff(f"{tag} frame {k} logvar jit vs env", tl, FL[k]))
                flips += int(((ol[0, 0] >= REJ) != (tl >= REJ)).sum())
                if de > TOL:
                    over.append(fs[k])
                MREF.append((te, tl))
        refs[tag + "_mapper"] = MREF
        res["tags"][tag] = {"cell": meta["tags"][tag]["cell"], "steps": N_STEPS, "resets_in_recording": 0,
                            "max_abs_action_onnx_vs_torch": w["actions"], "mean_abs_action_onnx_vs_torch": float(np.mean(means)), "step_of_max": step_of_max,
                            "max_abs_attn_out_onnx_vs_torch": w["attn_out"], "max_abs_global_feat_onnx_vs_torch": w["global_feat"],
                            "max_abs_action_torch_vs_jit_twin": twin_d, "max_abs_action_onnx_vs_env_gpu": gpu_d, "max_abs_action_torch_cpu_vs_env_gpu": cpu_gpu,
                            "max_abs_action": mx, "mapper_frames": N_FRAMES,
                            "mapper_max_abs_elevation_onnx_vs_jit": me, "mapper_max_abs_logvar_onnx_vs_jit": ml, "mapper_rejection_flips_ln15": flips,
                            "mapper_max_abs_elevation_jit_cpu_vs_env_gpu": mge, "mapper_max_abs_logvar_jit_cpu_vs_env_gpu": mgl,
                            "mapper_frames_elevation_above_threshold": len(over), "mapper_policy_steps_elevation_above_threshold": over,
                            "mapper_worst_elevation": worst}
    chk = {}
    for tag in TAGS:  # layout checks of parity_stu2.py, on arrays already known to be finite
        H = Z[f"{tag}_prop"]
        last = H[:, -1, :]
        qt = np.asarray(Z[f"{tag}_root_quat"], np.float64)
        w_, xyz = qt[:, :1], qt[:, 1:]
        v = np.broadcast_to(np.array([0.0, 0.0, -1.0]), xyz.shape)
        tt = 2.0 * np.cross(xyz, v)
        g = v - w_ * tt + np.cross(xyz, tt)
        c = {"prop_ang_vel_vs_state": fin.diff("ang_vel", last[:, 0:3], Z[f"{tag}_ang_vel_b"]),
             "prop_gravity_vs_state": fin.diff("gravity", last[:, 3:6], g),
             "prop_joint_pos_rel_vs_q_minus_q0": fin.diff("joint_pos", last[:, 6:18], Z[f"{tag}_q"] - Z[f"{tag}_q0"]),
             "q0_vs_default_joint_pos": fin.diff("q0", Z[f"{tag}_q0"], np.broadcast_to(q0[None], Z[f"{tag}_q0"].shape)),
             "prop_joint_vel_vs_dq": fin.diff("joint_vel", last[:, 18:30], Z[f"{tag}_dq"] - Z[f"{tag}_dq0"]),
             "prop_last_action_vs_clip50": fin.diff("last_action", last[:, 30:42], np.clip(Z[f"{tag}_last_action"], -50, 50)),
             "last_action_vs_previous_raw": fin.diff("previous raw", Z[f"{tag}_last_action"][1:], Z[f"{tag}_act_raw"][:-1]),
             "history_shift_max_abs": fin.diff("history shift", H[1:, :-1], H[:-1, 1:]),
             "first_row_history_rows_equal": fin.diff("first row", H[0], np.broadcast_to(H[0, -1:], H[0].shape)),
             "first_row_last_action_max_abs": float(np.abs(Z[f"{tag}_last_action"][0]).max()),
             "cmd_xy_norm_max": float(np.linalg.norm(Z[f"{tag}_cmd"][:, :2], axis=1).max()),
             "nmap_x_vs_grid": float(np.abs(Z[f"{tag}_nmap"][..., 0] - (-0.42 + 0.06 * np.arange(29, dtype=np.float32))[None, :, None]).max()),
             "nmap_y_vs_grid": float(np.abs(Z[f"{tag}_nmap"][..., 1] - (-0.36 + 0.06 * np.arange(13, dtype=np.float32))[None, None, :]).max()),
             "nmap_z_range": [float(Z[f"{tag}_nmap"][..., 2].min()), float(Z[f"{tag}_nmap"][..., 2].max())],
             "nmap_unc_range": [float(Z[f"{tag}_nmap"][..., 3].min()), float(Z[f"{tag}_nmap"][..., 3].max())],
             "processed_vs_default_plus_0p25_raw": fin.diff("processed", Z[f"{tag}_act_processed"], q0[None] + 0.25 * Z[f"{tag}_act_raw"]),
             "recorded_act_vs_action_raw": fin.diff("act vs raw", Z[f"{tag}_act"], Z[f"{tag}_act_raw"]),
             "frame_steps": [int(x - Z[f"{tag}_counter"][0]) for x in Z[f"{tag}_frame_counter"]][:8]}
        chk[tag] = c
    res["recording_checks"] = chk
    T = res["tags"]
    pol = max(max(T[t][k] for k in ("max_abs_action_onnx_vs_torch", "max_abs_attn_out_onnx_vs_torch", "max_abs_global_feat_onnx_vs_torch")) for t in T)
    mp = max(max(T[t]["mapper_max_abs_elevation_onnx_vs_jit"], T[t]["mapper_max_abs_logvar_onnx_vs_jit"]) for t in T)
    fl = sum(T[t]["mapper_rejection_flips_ln15"] for t in T)
    for name, v in (("policy maximum", pol), ("mapper maximum", mp)):
        if not math.isfinite(v):
            raise JudgeFail("non_finite", name)
    res.update({"max_abs_action_onnx_vs_torch": max(T[t]["max_abs_action_onnx_vs_torch"] for t in T), "max_abs_policy_outputs": pol,
                "max_abs_mapper_onnx_vs_jit": mp, "mapper_rejection_flips": fl, "threshold": TOL,
                "pass_policy": bool(pol <= TOL), "pass_mapper": bool(mp <= TOL and fl == 0)})
    res["pass"] = res["pass_policy"] and res["pass_mapper"]
    res["record_checks_done"] = record
    res["finite_checks"] = {"arrays_checked": fin.arrays, "non_finite_found": 0}
    return res, refs


def write_result(target, obj):
    """the result file appears complete or not at all: temporary name in the run's own folder, then renamed"""
    tmp = target + ".partial"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, target)


def write_vectors(OUT, NAME, Z, refs):
    """the four test-vector files of a pass (as parity_stu2.py); returns {file name: sha256} after reading each file back"""
    n = 20
    f32 = lambda a: [float(v) for v in np.asarray(a, np.float32).reshape(-1)]  # noqa: E731
    M, H, C = (np.asarray(Z[f"flat_{k}"], np.float32) for k in ("nmap", "prop", "cmd"))
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
    fs = [int(x - Z["flat_counter"][0]) for x in Z["flat_frame_counter"]]
    sel = [i for i, s in enumerate(fs) if s < n]
    G = np.asarray(Z["flat_frame_grid"], np.float32)
    tvm = {"format": f"{NAME}-mapper-test-vectors/1", "model": f"{NAME}_mapper", "onnx": {f"{NAME}_mapper.onnx": SHA["mapper_onnx"]}, "steps": n,
           "frames": len(sel), "tolerance": TOL, "state_feedback": False,
           "note": "the same 20 policy steps as test_vectors_flat20.json; a frame is fused when the range sensors give a new scan (every 5 policy steps); step = policy step of the frame",
           "inputs": [{"step": fs[i], "grid": f32(G[i])} for i in sel],
           "expected": [{"elevation": f32(refs["flat_mapper"][i][0]), "logvar": f32(refs["flat_mapper"][i][1])} for i in sel],
           "input_shapes": {"grid": [1, 1, 66, 48]}, "input_types": {"grid": "tensor(float)"}}
    json.dump(tvm, open(os.path.join(OUT, "test_vectors_flat20_mapper.json"), "w", encoding="utf-8", newline="\n"), separators=(",", ":"))
    np.savez(os.path.join(OUT, "test_vectors_flat20_mapper.npz"), step=np.array([fs[i] for i in sel]), grid=G[sel],
             elevation=np.stack([refs["flat_mapper"][i][0] for i in sel]).astype(np.float32), logvar=np.stack([refs["flat_mapper"][i][1] for i in sel]).astype(np.float32))
    names = ("test_vectors_flat20.json", "test_vectors_flat20.npz", "test_vectors_flat20_mapper.json", "test_vectors_flat20_mapper.npz")
    for fn in names:  # read back before the pass is finalised
        p = os.path.join(OUT, fn)
        if fn.endswith(".json"):
            json.load(open(p, encoding="utf-8"))
        else:
            with np.load(p) as zz:
                [zz[k].shape for k in zz.files]
    return {fn: sha256(os.path.join(OUT, fn)) for fn in names}


def main():
    EX, CKPT, AGENT, ONNX, MJIT, MONNX, RSL, OUT, NAME = sys.argv[1:10]
    result_name = sys.argv[10] if len(sys.argv) > 10 else "parity_stu3.json"
    for k, p in (("npz", EX), ("ckpt", CKPT), ("agent", AGENT), ("onnx", ONNX), ("mapper_jit", MJIT), ("mapper_onnx", MONNX)):
        if sha256(p) != SHA[k]:
            sys.exit(f"PARITY_STU_FAIL {k} sha256 is not the bundle's")
    try:
        import_reference(RSL)  # the fingerprint of the imported reference code, before anything is created
    except FileMismatch as e:
        sys.exit(f"PARITY_STU_FAIL {e}")
    if os.path.exists(OUT):
        sys.exit("PARITY_STU_FAIL the output folder exists: a run needs a folder of its own that does not exist yet")
    try:
        os.makedirs(OUT)  # fails if another run created it in between
    except FileExistsError:
        sys.exit("PARITY_STU_FAIL the output folder exists: a run needs a folder of its own that does not exist yet")
    target = os.path.join(OUT, result_name)
    mdl = load_models(CKPT, AGENT, ONNX, MJIT, MONNX, RSL)
    z = np.load(EX)
    Z = {k: z[k] for k in z.files if k != "meta_json"}
    meta = json.loads(str(z["meta_json"]))
    info = {"judge": {"file": "parity_stu3.py", "sha256": sha256(os.path.abspath(__file__)), "base": "parity_stu2.py",
                      "added": ["fixed files incl. the imported reference policy code (sha256)", "completeness checks of the recording", "finiteness of every compared array",
                                "a run-owned new output folder; vectors before the result file"]},
            "recording_npz_sha256": SHA["npz"], "reference_code": mdl["reference_code"]}
    try:
        res, refs = judge(Z, meta, mdl)
    except JudgeFail as e:
        write_result(target, {**info, "judged": False, "refused": {"kind": e.kind, "message": e.msg}})
        print(f"PARITY_STU_REFUSED {e}")
        sys.exit(4)
    res = {**info, "judged": True, **res}
    res["state_feedback"] = False
    res["state_note"] = "no recurrent state in either ONNX; the caller builds prop_hist (20 rows, oldest first) and the map"
    res["onnx"] = {"file": f"{NAME}.onnx", "source_file": os.path.basename(ONNX), "sha256": SHA["onnx"], "bytes": os.path.getsize(ONNX)}
    res["mapper_onnx"] = {"file": f"{NAME}_mapper.onnx", "source_file": os.path.basename(MONNX), "sha256": SHA["mapper_onnx"], "bytes": os.path.getsize(MONNX)}
    res["runtime"] = {"onnxruntime": mdl["ort"], "provider": "CPUExecutionProvider", "torch_reference": torch.__version__, "intra_op_threads": 2, "torch_threads": 4}
    res["checkpoint_sha256"] = SHA["ckpt"]
    res["mapper_jit_sha256"] = SHA["mapper_jit"]
    res["load_state_dict"] = {"strict": True, "missing": list(mdl["load"].missing_keys), "unexpected": list(mdl["load"].unexpected_keys)}
    res["recording"] = {k: meta[k] for k in ("rec_cells", "step_dt", "physics_dt", "decimation", "noise_none", "code", "torch", "tool_md5", "end_complete", "tags")}
    res["recording"]["args"] = {k: (os.path.basename(str(v)) if k in ("checkpoint", "mapper_jit", "teacher_jit") else v) for k, v in meta["args"].items()}
    print("PARITY", json.dumps({k: res[k] for k in ("max_abs_action_onnx_vs_torch", "max_abs_policy_outputs", "max_abs_mapper_onnx_vs_jit", "mapper_rejection_flips", "pass_policy", "pass_mapper")}))
    if not res["pass"]:
        res["test_vectors"] = None
        write_result(target, res)
        print("PARITY_STU_FAIL above the threshold: no test vectors written (step 3 stops)")
        sys.exit(3)
    res["test_vectors"] = write_vectors(OUT, NAME, Z, refs)  # the four files complete and read back; only then the pass result
    write_result(target, res)
    print("PARITY_STU_OK vectors written, then the result")


if __name__ == "__main__":
    main()
