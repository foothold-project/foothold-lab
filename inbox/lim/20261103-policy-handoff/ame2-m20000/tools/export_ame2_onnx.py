"""Export an AME-2 student (TU or rule-map) to ONNX for the robot (onnxruntime 1.18.1 on the Orin, CPU) and check it.

Model: rsl_rl.models.AME2_models.AME2GazeLSIOModel (x4code copy be7e6545 = the pod's student copy) built with the run's own params/agent.yaml
actor block, loaded with actor_state_dict of the given checkpoint (sha256 checked), eval(). The deployment twin _TorchAME2GazeLSIOModel
(model.as_jit(): the same layers, hard integer crop, mha_math when traced) is exported with torch.onnx.export (TorchScript exporter, opset 17).
Inputs : neural_map (1, 29, 13, 4) float32 | prop_hist (1, 20, 42) float32, oldest first | cmds (1, 4) float32.
Outputs: actions (1, 12) | attn_out (1, 96) | global_feat (1, 64).
Checks on N random-but-plausible inputs: original model forward(obs) (the sim evaluation path, stochastic_output False) vs the twin vs
onnxruntime. Writes <out>/ame2_<arm>.onnx, <out>/ame2_<arm>.json (shapes, names, sha256s, max differences).
usage: py -3 export_ame2_onnx.py <tu|pass> <checkpoint> <agent.yaml> <out dir> [--n 2000]"""
import hashlib
import json
import os
import sys
import types

import numpy as np
import torch

H = os.path.dirname(os.path.abspath(__file__))
RSL = os.path.normpath(os.path.join(H, "..", "..", "docs", "stage1_logs", "req428", "x4code", "rsl", "rsl_rl"))
CKPT_SHA = {"tu": "34eba83771f7564f93c163afdfcbefa8620780c44b920e2edb0a1c9b49d42793",
            "pass": "cda5c3e686054fb814e25a516a227e26404904c0d708ec8266b20fb2347a858e"}
MODELS_MD5 = "be7e6545"
# the actor block the student was trained with (params/agent.yaml of both runs, Codex 430_1 / 430_2), fixed here independently of the yaml:
# a wrong crop in the yaml would build the original and the exported model the same wrong way, so the two would still agree
ACTOR_CONTRACT = {"class_name": "rsl_rl.models.AME2_models:AME2GazeLSIOModel", "num_heads": 32, "crop_x": 12, "crop_y": 10, "roi_coef": 0.01,
                  "roi_margin": 0.45, "stochastic": True, "init_noise_std": 1.0, "noise_std_type": "log"}
N_MIN = 200
OUT_SHAPES = {"actions": (1, 12), "attn_out": (1, 96), "global_feat": (1, 64)}
TOL = 1e-4   # max |ONNX - original| of every output (the team's START rule: 1e-4)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build(arm, ckpt, agent_yaml):
    if "tensordict" not in sys.modules:   # the model file imports TensorDict for type hints only; a dict is enough here
        sys.modules["tensordict"] = types.SimpleNamespace(TensorDict=dict)
    sys.path.insert(0, RSL)
    mp = os.path.join(RSL, "rsl_rl", "models", "AME2_models.py")
    if hashlib.md5(open(mp, "rb").read()).hexdigest()[:8] != MODELS_MD5:
        raise SystemExit("EXPORT_AME2_ONNX_FAIL AME2_models.py is not the student copy")
    from rsl_rl.models.AME2_models import AME2GazeLSIOModel
    import yaml
    cfg = yaml.safe_load(open(agent_yaml))["actor"]
    if cfg != ACTOR_CONTRACT:
        raise SystemExit(f"EXPORT_AME2_ONNX_FAIL the actor block of {agent_yaml} is not the training contract: {cfg}")
    if sha256(ckpt) != CKPT_SHA[arm]:
        raise SystemExit(f"EXPORT_AME2_ONNX_FAIL {ckpt} is not the approved {arm} checkpoint")
    obs = {"neural_map": torch.zeros(1, 29, 13, 4), "student_prop_hist": torch.zeros(1, 20, 42), "student_cmds": torch.zeros(1, 4)}
    kw = {k: v for k, v in cfg.items() if k != "class_name"}
    model = AME2GazeLSIOModel(obs, {"actor": list(obs)}, "actor", 12, **kw)
    sd = torch.load(ckpt, map_location="cpu", weights_only=False)["actor_state_dict"]
    missing, unexpected = model.load_state_dict(sd, strict=True), None
    model.eval()
    return model, cfg


def plausible(rng, n):
    """Inputs in the ranges the robot produces: map heights around 0.27 +- 0.6, encoded variance in [-1.8, 0.85], x / y the fixed cell centres;
    history rows like a walking robot; commands with |d| <= 2 and a unit (sin, cos)."""
    xs = -0.42 + 0.06 * np.arange(29)
    ys = -0.36 + 0.06 * np.arange(13)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    m = np.zeros((n, 29, 13, 4), np.float32)
    m[..., 0], m[..., 1] = gx, gy
    step = rng.uniform(-0.3, 0.3, (n, 1, 1)) * (gx[None] > rng.uniform(0, 1.2, (n, 1, 1)))
    m[..., 2] = np.clip(0.27 + step + rng.normal(0, 0.02, (n, 29, 13)), -1.5, 1.5)
    m[..., 3] = np.where(rng.random((n, 29, 13)) < 0.2, 0.5 * np.log(2.0) + 0.5, 0.5 * np.log(np.clip(rng.uniform(0.002, 0.05, (n, 29, 13)), 0.01, 2)) + 0.5)
    h = np.zeros((n, 20, 42), np.float32)
    h[..., 0:3] = rng.normal(0, 0.5, (n, 20, 3))
    g = rng.normal(0, 0.1, (n, 20, 3)) + np.array([0, 0, -1.0])
    h[..., 3:6] = g / np.linalg.norm(g, axis=-1, keepdims=True)
    h[..., 6:18] = rng.normal(0, 0.3, (n, 20, 12))
    h[..., 18:30] = rng.normal(0, 3.0, (n, 20, 12))
    h[..., 30:42] = np.clip(rng.normal(0, 3.0, (n, 20, 12)), -50, 50)
    ang = rng.uniform(-np.pi, np.pi, n)
    r = rng.uniform(0, 2.0, n)
    e = rng.uniform(-np.pi, np.pi, n)
    c = np.stack([r * np.cos(ang), r * np.sin(ang), np.sin(e), np.cos(e)], -1).astype(np.float32)
    return m.astype(np.float32), h, c


def main():
    arm, ckpt, agent_yaml, out = sys.argv[1:5]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 2000
    if n < N_MIN:
        raise SystemExit(f"EXPORT_AME2_ONNX_FAIL --n {n} < {N_MIN}")
    os.makedirs(out, exist_ok=True)
    torch.manual_seed(0)
    model, cfg = build(arm, ckpt, agent_yaml)
    twin = model.as_jit().eval()
    final = os.path.join(out, f"ame2_{arm}.onnx")
    path = final + ".tmp"   # only a file that passed every check replaces the approved one
    ex = (torch.zeros(1, 29, 13, 4), torch.zeros(1, 20, 42), torch.zeros(1, 4))
    torch.onnx.export(twin, ex, path, input_names=["neural_map", "prop_hist", "cmds"], output_names=["actions", "attn_out", "global_feat"],
                      opset_version=17, do_constant_folding=True, dynamo=False)
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads, so.inter_op_num_threads = 2, 1
    sess = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(1)
    m, h, c = plausible(rng, n)
    names = [o.name for o in sess.get_outputs()]
    if names != list(OUT_SHAPES) or [i.name for i in sess.get_inputs()] != ["neural_map", "prop_hist", "cmds"]:
        raise SystemExit(f"EXPORT_AME2_ONNX_FAIL input / output names {[i.name for i in sess.get_inputs()]} / {names}")
    worst = {"twin_vs_model": 0.0, "onnx_vs_model": 0.0, "onnx_vs_twin": 0.0, "onnx_vs_model_attn_out": 0.0, "onnx_vs_model_global_feat": 0.0}
    bad = []
    with torch.no_grad():
        for i in range(n):
            tm, th, tc = torch.from_numpy(m[i:i + 1]), torch.from_numpy(h[i:i + 1]), torch.from_numpy(c[i:i + 1])
            a_model, at_model, gf_model = (t.numpy() for t in model({"neural_map": tm, "student_prop_hist": th, "student_cmds": tc}, return_latent=True))
            a_twin = twin(tm, th, tc)[0].numpy()
            outs = dict(zip(names, sess.run(names, {"neural_map": m[i:i + 1], "prop_hist": h[i:i + 1], "cmds": c[i:i + 1]})))
            for k, shp in OUT_SHAPES.items():
                if outs[k].shape != shp or outs[k].dtype != np.float32 or not np.all(np.isfinite(outs[k])):
                    bad.append(f"sample {i} output {k} shape {outs[k].shape} dtype {outs[k].dtype} finite {bool(np.all(np.isfinite(outs[k])))}")
            for nm_, v in (("model actions", a_model), ("model attn_out", at_model), ("model global_feat", gf_model), ("twin actions", a_twin)):
                if not np.all(np.isfinite(v)):
                    bad.append(f"sample {i} non-finite torch output {nm_}")
            if bad:
                break
            a_onnx = outs["actions"]
            worst["twin_vs_model"] = max(worst["twin_vs_model"], float(np.abs(a_twin - a_model).max()))
            worst["onnx_vs_model"] = max(worst["onnx_vs_model"], float(np.abs(a_onnx - a_model).max()))
            worst["onnx_vs_twin"] = max(worst["onnx_vs_twin"], float(np.abs(a_onnx - a_twin).max()))
            worst["onnx_vs_model_attn_out"] = max(worst["onnx_vs_model_attn_out"], float(np.abs(outs["attn_out"] - at_model).max()))
            worst["onnx_vs_model_global_feat"] = max(worst["onnx_vs_model_global_feat"], float(np.abs(outs["global_feat"] - gf_model).max()))
    ok = not bad and worst["twin_vs_model"] == 0.0 and all(v < TOL for k, v in worst.items() if k != "twin_vs_model")
    del sess
    if not ok:
        os.remove(path)
        print("bad:", bad[:5], "worst:", worst)
        raise SystemExit("EXPORT_AME2_ONNX_FAIL (nothing written)")
    meta = {"arm": arm, "checkpoint_sha256": CKPT_SHA[arm], "agent_yaml_sha256": sha256(agent_yaml), "agent_actor": cfg, "onnx": os.path.basename(final), "onnx_sha256": sha256(path),
            "opset": 17, "inputs": {"neural_map": [1, 29, 13, 4], "prop_hist": [1, 20, 42], "cmds": [1, 4]},
            "outputs": {"actions": [1, 12], "attn_out": [1, 96], "global_feat": [1, 64]}, "crop": [cfg["crop_x"], cfg["crop_y"]],
            "checked_inputs": n, "max_abs_action_difference": worst, "torch": torch.__version__, "onnxruntime": ort.__version__,
            "export_tool": "v3", "export_tool_md5": hashlib.md5(open(__file__, "rb").read()).hexdigest(),
            "publish_tool_md5": hashlib.md5(open(os.path.join(H, "bundle_publish.py"), "rb").read()).hexdigest()}
    from bundle_publish import publish
    vdir = publish(out, f"ame2_{arm}", {os.path.basename(final): path}, meta)
    print("published", vdir)
    print(json.dumps({k: meta[k] for k in ("arm", "onnx_sha256", "checked_inputs", "max_abs_action_difference")}, indent=1))
    print("EXPORT_AME2_ONNX_OK")


if __name__ == "__main__":
    main()
