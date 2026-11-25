"""Policy signature gate (lead 2026-11-26 00:26 / 00:29, team lead 00:25): a new reward-only branch (Classic target, AMP) must
leave the deployed policy byte-compatible with the parent. Compares a candidate checkpoint with a reference (E2b m250):

    actor / critic / std keys and shapes (model_state_dict), observation normalisation buffers (normalization_state),
    policy EMA shadow keys and shapes (policy_ema), perception network and its EMA (perception_state_dict, perception_ema),
    and the ONNX signature of the actor MLP (input / output names and shapes; obs size from actor.0.weight).

A discriminator or any other new network must live under its own top-level key; extra top-level keys are listed but do not
fail the gate. Exit 0 = same, 3 = differs (do not launch), 2 = unreadable input.

    python -m foothold_s2.tools.ex42_policy_signature_gate --ref <E2b model_250.pt> --cand <new model_N.pt> [--onnx-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch


def _shapes(obj, prefix=""):
    """Flatten nested dicts / lists to {path: shape}; plain leaves give their value, other objects their type name."""
    out = {}
    if isinstance(obj, torch.Tensor):
        out[prefix] = tuple(obj.shape)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_shapes(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(_shapes(v, f"{prefix}[{i}]"))
    elif isinstance(obj, (bool, int, float, str)) or obj is None:
        out[prefix] = repr(obj)          # flags such as actor_obs_enabled must match by value
    else:
        out[prefix] = type(obj).__name__
    return out


def section(ck: dict, name: str) -> dict:
    if name == "model_state_dict":
        sd = ck.get(name) or {}
        return {k: tuple(v.shape) for k, v in sd.items() if k.startswith(("actor.", "critic.", "std"))}
    if name in ("policy_ema", "perception_ema"):
        return _shapes((ck.get(name) or {}).get("shadow", {}), "shadow")
    return _shapes(ck.get(name, {}))


SECTIONS = ("model_state_dict", "normalization_state", "policy_ema", "perception_state_dict", "perception_ema")


def actor_onnx_signature(ck: dict, path: Path) -> dict:
    sd = ck["model_state_dict"]
    layers = sorted({int(k.split(".")[1]) for k in sd if k.startswith("actor.") and k.endswith(".weight")})
    mods = []
    for j, idx in enumerate(layers):
        w = sd[f"actor.{idx}.weight"]
        lin = torch.nn.Linear(w.shape[1], w.shape[0])
        lin.weight.data.copy_(w)
        lin.bias.data.copy_(sd[f"actor.{idx}.bias"])
        mods.append(lin)
        if j < len(layers) - 1:
            mods.append(torch.nn.ELU())
    net = torch.nn.Sequential(*mods).eval()
    obs_dim = sd[f"actor.{layers[0]}.weight"].shape[1]
    torch.onnx.export(net, torch.zeros(1, obs_dim), str(path), input_names=["obs"], output_names=["actions"],
                      dynamo=False, opset_version=17, dynamic_axes={"obs": {0: "batch"}, "actions": {0: "batch"}})
    import onnx

    model = onnx.load(str(path))

    def dims(v):
        return [d.dim_param or d.dim_value for d in v.type.tensor_type.shape.dim]

    return {"inputs": [(v.name, dims(v)) for v in model.graph.input],
            "outputs": [(v.name, dims(v)) for v in model.graph.output]}


def compare(ref: dict, cand: dict, onnx_dir: Path | None = None) -> dict:
    report = {"same": True, "sections": {}}
    for name in SECTIONS:
        a, b = section(ref, name), section(cand, name)
        diff = {"only_ref": sorted(set(a) - set(b)), "only_cand": sorted(set(b) - set(a)),
                "shape": sorted(k for k in set(a) & set(b) if a[k] != b[k])}
        n = sum(len(v) for v in diff.values())
        report["sections"][name] = {"keys_ref": len(a), "keys_cand": len(b), "diff": n, **({"detail": diff} if n else {})}
        report["same"] &= n == 0
    report["extra_top_level_in_cand"] = sorted(set(cand) - set(ref))
    report["missing_top_level_in_cand"] = sorted(set(ref) - set(cand))
    if report["missing_top_level_in_cand"]:
        report["same"] = False
    if onnx_dir is not None:
        onnx_dir.mkdir(parents=True, exist_ok=True)
        sa = actor_onnx_signature(ref, onnx_dir / "ref_actor.onnx")
        sb = actor_onnx_signature(cand, onnx_dir / "cand_actor.onnx")
        report["onnx"] = {"ref": sa, "cand": sb, "same": sa == sb}
        report["same"] &= sa == sb
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--cand", required=True)
    ap.add_argument("--onnx-dir")
    a = ap.parse_args(argv)
    try:
        ref = torch.load(a.ref, map_location="cpu", weights_only=False)
        cand = torch.load(a.cand, map_location="cpu", weights_only=False)
    except Exception as exc:  # unreadable input is not a pass
        print(f"EX42_POLICY_SIGNATURE_GATE unreadable: {exc}")
        return 2
    rep = compare(ref, cand, Path(a.onnx_dir) if a.onnx_dir else None)
    print(json.dumps(rep, ensure_ascii=False, default=str))
    print("EX42_POLICY_SIGNATURE_GATE %s" % ("same" if rep["same"] else "DIFFERS (do not launch)"))
    return 0 if rep["same"] else 3


if __name__ == "__main__":
    sys.exit(main())
