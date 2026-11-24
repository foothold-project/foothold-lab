"""Export one START step graph with a per-env map token mask (CPU only).

map_mask is float32 [batch, 1]: 0 includes map tokens, 1 masks them.
The other step inputs and all outputs match export_start_onnx.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
import torch.nn as nn

from foothold_s2.deploy import export_start_onnx as base
from foothold_s2.models.start_perception import Z_DIM, V_DIM, ZB_DIM, ZF_DIM


STEP_INPUTS = base.STEP_INPUTS + ("map_mask",)


class MaskedStepNet(nn.Module):
    """The trained StepNet path with a tensor mask that survives ONNX tracing."""

    def __init__(self, perc, actor, vx):
        super().__init__()
        self.p, self.actor, self.vx = perc, actor, vx

    def forward(self, o, hist, depth2, h_prop, h_terr, tick, first, pose, map_mask, flag_bearing3=None):
        keep = 1.0 - first
        h_prop2 = self.p.ie.prop_step(hist, h_prop * keep)
        h_terr0 = h_terr * keep
        h_new = self.p.trnet.step(depth2, h_prop2, h_terr0)
        h_terr2 = tick * h_new + (1.0 - tick) * h_terr0
        _rough, refined = self.p.trnet.decode(h_terr2)
        ie = self.p.ie
        prop = ie.prop_token(h_prop2).unsqueeze(1)
        maps = ie.map_cnn(refined.detach().unsqueeze(1)).flatten(2).transpose(1, 2) + ie.map_pos
        seq = torch.cat((prop, maps), dim=1)
        pad = torch.cat((torch.zeros_like(map_mask, dtype=torch.bool),
                         map_mask.bool().expand(-1, maps.shape[1])), dim=1)
        encoded = ie.attn(seq, src_key_padding_mask=pad)[:, 0]
        heads = ie.heads(encoded)
        mu, _logvar, v, zb, zf = torch.split(heads, [Z_DIM, Z_DIM, V_DIM, ZB_DIM, ZF_DIM], -1)
        est = torch.cat((mu, v, zf, zb), -1)
        from foothold_s2.runners.start_runner import correct_est_vx

        columns = (o, correct_est_vx(est, self.vx), pose)
        action = self.actor(torch.cat(columns + ((flag_bearing3,) if flag_bearing3 is not None else ()), -1))
        return action, h_prop2, h_terr2, refined, est


def export(checkpoint, out_dir, opset=17, *, vx_corr_on=None, vx_corr_b=None,
           vx_corr_band=None, vx_corr_ramp=None):
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} exists; refuse to overwrite an ONNX export")
    stage = out.with_name(out.name + ".partial")
    if stage.exists():
        raise FileExistsError(f"{stage} exists from an earlier export")
    spec = base.export(checkpoint, stage, opset, vx_corr_on=vx_corr_on, vx_corr_b=vx_corr_b,
                       vx_corr_band=vx_corr_band, vx_corr_ramp=vx_corr_ramp)
    perc, actor, _ = base.load(checkpoint)
    vx = base.vx_params(spec["vx_correction"]["on"], spec["vx_correction"]["b"],
                        spec["vx_correction"]["band"], spec["vx_correction"]["ramp"])
    net = MaskedStepNet(perc, actor, vx).eval()
    bprime = bool(spec.get("ex42_bprime", False))
    step_inputs = STEP_INPUTS + ((base.BPRIME_INPUT,) if bprime else ())
    dyn = {name: {0: "batch"} for name in step_inputs + base.STEP_OUTPUTS}
    inputs = base.example_inputs() + (torch.zeros(2, 1),) + ((torch.zeros(2, 3),) if bprime else ())
    with torch.inference_mode():
        torch.onnx.export(net, inputs, stage / "start_step.onnx", input_names=list(step_inputs),
                          output_names=list(base.STEP_OUTPUTS), dynamic_axes=dyn,
                          opset_version=opset, dynamo=False)
    spec["format"] = "foothold-start-onnx/2"
    map_entry = {"name": "map_mask", "shape": ["batch", 1], "dtype": "float32",
                 "what": "0 = map tokens attend; 1 = mask all 128 map tokens in the I-E attention; constant within an episode"}
    spec["step_inputs"].insert(-1 if bprime else len(spec["step_inputs"]), map_entry)
    spec["map_mask"] = {"on": 0.0, "off": 1.0,
                        "rule": "masks attention keys, not the reconstructed map; refined_map remains available in either mode"}
    spec["files"]["start_step.onnx"] = hashlib.sha256((stage / "start_step.onnx").read_bytes()).hexdigest()
    (stage / "start_onnx.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
    stage.rename(out)
    return spec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--vx-corr", choices=("on", "off"))
    ap.add_argument("--vx-corr-b", type=float)
    ap.add_argument("--vx-corr-band", type=float)
    ap.add_argument("--vx-corr-ramp", type=float)
    a = ap.parse_args(argv)
    spec = export(a.checkpoint, a.out, a.opset,
                  vx_corr_on=None if a.vx_corr is None else a.vx_corr == "on",
                  vx_corr_b=a.vx_corr_b, vx_corr_band=a.vx_corr_band,
                  vx_corr_ramp=a.vx_corr_ramp)
    print(json.dumps({k: spec[k] for k in ("checkpoint_sha256", "perception_source", "files", "map_mask")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
