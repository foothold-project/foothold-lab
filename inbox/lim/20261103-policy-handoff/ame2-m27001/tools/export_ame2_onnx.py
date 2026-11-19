"""AME-2 app handoff (2026-11-03), step 2: export the teacher actor to ONNX by wrapping its ORIGINAL forward.

No layer is rebuilt: the actor is constructed exactly as rsl_rl's PPO.construct_algorithm does
(actor_class(obs, obs_groups, "actor", num_actions, **agent.actor), algorithms/ppo.py:629-645) from the
run's params/agent.yaml, loaded strictly from the checkpoint's actor_state_dict, and the export module
only calls AME2GazeModel.forward (deterministic mean, stochastic_output=False) and returns the gaze
location r = sigmoid(gaze logits) that get_latent stores in _last_gaze_r (AME2_models.py:602-603).

  /workspace/isaaclab/_isaac_sim/python.sh export_ame2_onnx.py <ame2_spd> <run_dir> <ckpt name> <out_dir>
"""

import hashlib
import json
import os
import sys

B, RUN, CKN, OUT = sys.argv[1:5]
sys.path.insert(0, os.path.join(B, "rsl_rl"))

import numpy as np
import onnx
import torch
import yaml

from rsl_rl.models.AME2_models import AME2GazeModel


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Ame2DemoExport(torch.nn.Module):
    """(prop [1,49], mapping [1,29,13,3]) -> (action [1,12], gaze_r [1,2], gaze_logits [1,2], gaze_offset [1,2]) through the
    original forward. The diagnostics are taken from the original computation, not recomputed: gaze_logits = output of the
    original gaze_head (forward hook), gaze_offset = (ox, oy) returned by the original _crop_window inside _ste_crop
    (AME2_models.py:530-536, 555), cast to float32."""

    def __init__(self, model: AME2GazeModel):
        super().__init__()
        self.model = model
        self._cap = {}
        model.gaze_head.register_forward_hook(lambda m, i, o: self._cap.__setitem__("logits", o))
        orig = model._crop_window

        def crop_window(cx, cy, L, W):
            ox, oy = orig(cx, cy, L, W)
            self._cap["offset"] = (ox, oy)
            return ox, oy

        model._crop_window = crop_window

    def forward(self, prop: torch.Tensor, mapping: torch.Tensor):
        self._cap.clear()
        action = self.model({"teacher_prop": prop, "teacher_mapping": mapping})
        ox, oy = self._cap["offset"]
        offset = torch.stack([ox, oy], dim=1).to(torch.float32)
        return action, self.model._last_gaze_r, self._cap["logits"], offset


def build(agent):
    actor_cfg = dict(agent["actor"])
    cls = actor_cfg.pop("class_name")
    assert cls == "AME2GazeModel", cls
    obs = {"teacher_mapping": torch.zeros(1, 29, 13, 3), "teacher_prop": torch.zeros(1, 49)}
    return AME2GazeModel(obs, agent["obs_groups"], "actor", 12, **actor_cfg)


def main():
    os.makedirs(OUT, exist_ok=True)
    ckp = os.path.join(RUN, CKN)
    with open(os.path.join(RUN, "params", "agent.yaml")) as f:
        agent = yaml.safe_load(f)
    model = build(agent)
    ck = torch.load(ckp, map_location="cpu", weights_only=False)
    res = model.load_state_dict(ck["actor_state_dict"], strict=True)
    model.eval()
    assert model.distribution is None
    jit_twin = model.as_jit().eval()  # before the export wrapper adds its hook
    wrap = Ame2DemoExport(model).eval()

    # synthetic inputs (sanity only; the parity check uses recorded env inputs)
    g = torch.Generator().manual_seed(0)
    gx = torch.arange(-0.84, 0.84 + 1e-5, 0.06) + 0.42
    gy = torch.arange(-0.36, 0.36 + 1e-5, 0.06)
    X, Y = torch.meshgrid(gx, gy, indexing="ij")
    cases = []
    flat = torch.stack([X, Y, torch.zeros_like(X)], -1).unsqueeze(0)
    p0 = torch.zeros(1, 49)
    p0[0, 8] = -1.0
    p0[0, 45:49] = torch.tensor([1.0, 0.0, 0.0, 1.0])
    cases.append((p0, flat))
    for k in range(7):
        p = torch.randn(1, 49, generator=g) * 0.5
        p[0, 45:47] = torch.rand(1, 2, generator=g) * 2.0 - 1.0
        a = torch.rand(1, generator=g) * 6.2832
        p[0, 47], p[0, 48] = torch.sin(a), torch.cos(a)
        z = (torch.rand(1, 29, 13, generator=g) - 0.5) * 0.6
        cases.append((p, torch.stack([X.unsqueeze(0), Y.unsqueeze(0), z], -1)))
    P = torch.cat([c[0] for c in cases])
    M = torch.cat([c[1] for c in cases])
    with torch.inference_mode():
        ref_a, ref_r, ref_l, ref_o = [], [], [], []
        for i in range(P.shape[0]):
            a, r, lg, off = wrap(P[i : i + 1], M[i : i + 1])
            ref_a.append(a)
            ref_r.append(r)
            ref_l.append(lg)
            ref_o.append(off)
        ref_a, ref_r, ref_l, ref_o = torch.cat(ref_a), torch.cat(ref_r), torch.cat(ref_l), torch.cat(ref_o)
        tw = [jit_twin.forward_with_gaze(P[i : i + 1], M[i : i + 1]) for i in range(P.shape[0])]
        jit_a = torch.cat([t[0] for t in tw])
        jit_mu = torch.cat([t[3] for t in tw])
        batch_a = model({"teacher_prop": P, "teacher_mapping": M})

    onnx_path = os.path.join(OUT, "ame2-demo.onnx")
    with torch.no_grad():
        torch.onnx.export(
            wrap, (P[:1], M[:1]), onnx_path, input_names=["prop", "mapping"], output_names=["action", "gaze_r", "gaze_logits", "gaze_offset"],
            opset_version=17, do_constant_folding=True, dynamo=False,
        )
    m = onnx.load(onnx_path)
    onnx.checker.check_model(m, full_check=True)
    ops = {}
    for nd in m.graph.node:
        ops[nd.op_type] = ops.get(nd.op_type, 0) + 1
    io = {
        "inputs": [(i.name, [d.dim_value for d in i.type.tensor_type.shape.dim], i.type.tensor_type.elem_type) for i in m.graph.input],
        "outputs": [(o.name, [d.dim_value for d in o.type.tensor_type.shape.dim], o.type.tensor_type.elem_type) for o in m.graph.output],
    }
    np.savez(os.path.join(OUT, "synthetic_ref.npz"), prop=P.numpy(), mapping=M.numpy(), action_torch=ref_a.numpy(), gaze_r_torch=ref_r.numpy(), gaze_logits_torch=ref_l.numpy(), gaze_offset_torch=ref_o.numpy(),
             action_jit_twin=jit_a.numpy(), action_torch_batch=batch_a.numpy())
    info = {
        "checkpoint": ckp, "checkpoint_sha256": sha256(ckp), "agent_yaml_sha256": sha256(os.path.join(RUN, "params", "agent.yaml")),
        "models_py_sha256": sha256(os.path.join(B, "rsl_rl", "rsl_rl", "models", "AME2_models.py")),
        "torch": torch.__version__, "onnx": onnx.__version__, "opset": [(o.domain, o.version) for o in m.opset_import],
        "ir_version": m.ir_version, "producer": f"{m.producer_name} {m.producer_version}",
        "load_state_dict": str(res), "actor_cfg": agent["actor"], "obs_groups_actor": agent["obs_groups"]["actor"],
        "onnx_path": onnx_path, "onnx_sha256": sha256(onnx_path), "onnx_bytes": os.path.getsize(onnx_path),
        "nodes": len(m.graph.node), "ops": ops, "io": io, "checker": "check_model full_check passed",
        "synthetic_cases": int(P.shape[0]),
        "max_abs_wrap_vs_jit_twin": float((ref_a - jit_a).abs().max()),
        "max_abs_wrap_vs_batch8": float((ref_a - batch_a).abs().max()),
        "max_abs_gaze_logits_hook_vs_jit_twin_mu": float((ref_l - jit_mu).abs().max()),
        "max_abs_sigmoid_logits_vs_gaze_r": float((torch.sigmoid(ref_l) - ref_r).abs().max()),
        "log_std": ck["actor_state_dict"]["log_std"].tolist(),
    }
    with open(os.path.join(OUT, "export_info.json"), "w") as f:
        json.dump(info, f, indent=1)
    print("EXPORT_INFO", json.dumps({k: info[k] for k in ("onnx_sha256", "onnx_bytes", "nodes", "opset", "max_abs_wrap_vs_jit_twin", "max_abs_wrap_vs_batch8", "max_abs_gaze_logits_hook_vs_jit_twin_mu", "max_abs_sigmoid_logits_vs_gaze_r", "load_state_dict")}))
    print("EXPORT_DONE", onnx_path)


if __name__ == "__main__":
    main()
