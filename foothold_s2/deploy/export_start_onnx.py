"""START policy (perception + actor) to ONNX for the real Go2 (lead 2026-11-22 09:10 / 09:12 · option 1: one graph, recurrent state as inputs
and outputs; and an actor-only file beside it as the fallback). CPU only. Reads a training checkpoint model_N.pt or model_N_ema.pt.

What runs on the robot each 50 Hz step (the evaluation / deployment path: eval/adapters.py S2Policy, deterministic, reconstructed map):
  outside the graph (the robot side keeps these; written into the json): the proprioceptive history ring (10 x 45, newest first), the depth
  frame ring (10 Hz: every 5th step; a delay of depth_delay_ticks frames; 2 frames go in), the step counter since reset (first step fills the
  history and the frames with the current values), the two GRU states (zeroed on reset) and the depth preprocessing (60 x 60, 0..1).
  inside the graph (StepNet): prop GRU step -> on a depth tick the TR-Net step -> rough 32 x 16 -> U-Net -> refined map -> I-E estimate
  (z mean 16 · v 3 · zf 16 · zb 16 = est 51) -> the vx correction of the actor input (start_runner.correct_est_vx, v29-14: column 16 only;
  part of the policy: training and evaluation pass every actor input through it) -> actor (o 45 + est_in 51 + pose 2 = 98) -> action mean 12.
  The correction values come from the checkpoint's vx_corr entry (written by training since lead 10:36); a checkpoint without it needs
  all of --vx-corr on|off, --vx-corr-b, --vx-corr-band, --vx-corr-ramp (never a hidden default, lead 10:32); given arguments must match the
  entry; the ramp is the code constant VX_CORR_RAMP (another value is refused). The est output is the perception estimate before it.
The graph follows StartPerception._advance with use_gt false and no map switch-off (the robot has no ground-truth map); tick and first are
0/1 float inputs (the blend tick * new + (1 - tick) * old is exact for 0/1).

  python -m foothold_s2.deploy.export_start_onnx --checkpoint <model_N.pt> --out <folder> --vx-corr on --vx-corr-b 0.009 --vx-corr-band 0.3 --vx-corr-ramp 0.05
writes <folder>/start_step.onnx, start_actor.onnx, start_onnx.json (input / output names, shapes, order, the ring rules, checkpoint sha256).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
import torch.nn as nn

from foothold_s2.models.start_perception import (ACTOR_IN, DEPTH_FRAMES, DEPTH_HW, EST_DIM, HIST_LEN, MAP_X, MAP_Y, OBS_DIM, PerceptionCfg,
                                                 StartPerception)

POSE_DIM = 2
ACTION_DIM = 12
STEP_INPUTS = ("o", "hist", "depth2", "h_prop", "h_terr", "tick", "first", "pose")
STEP_OUTPUTS = ("action", "h_prop_out", "h_terr_out", "refined_map", "est")
BPRIME_INPUT = "flag_bearing3"


def load(checkpoint) -> tuple[StartPerception, nn.Sequential, dict]:
    """(perception, actor, info) from a checkpoint, the same weights the evaluation adapter uses (perception_ema when the file has it)."""
    from foothold_s2.runners import perception_ema as pema
    sd = torch.load(checkpoint, map_location="cpu", weights_only=False)
    saved = sd.get("perception_cfg") or {}
    if saved.get("map_input", "none") != "reconstruction":
        raise ValueError("export needs a reconstruction-map checkpoint")
    if sd.get("ex41_pose_commands") is not True:
        raise ValueError("export expects the 98-input actor (pose commands)")
    bprime = sd.get("ex42_bprime", False)
    if type(bprime) is not bool:
        raise ValueError("checkpoint ex42_bprime must be bool")
    turn_rad = None
    if bprime:
        from foothold_s2.commands.ex42_bprime import validate_turn_rad
        turn_rad = validate_turn_rad(sd.get("ex42_bprime_turn_rad", 0.25))
    perc = StartPerception(PerceptionCfg(map_input="reconstruction", force_gt=bool(saved.get("force_gt", False)),
                                         depth_delay_ticks=int(saved.get("depth_delay_ticks", 1))))
    state, why = sd["perception_state_dict"], "online"
    if sd.get("perception_ema") is not None:
        ema, why2 = pema.ema_state_dict(sd["perception_state_dict"], sd["perception_ema"])
        if ema is not None:
            state, why = ema, "ema"
    perc.load_state_dict(state)
    m = sd["model_state_dict"]
    layers, i = [], 0
    while f"actor.{i}.weight" in m:
        w = m[f"actor.{i}.weight"]
        lin = nn.Linear(w.shape[1], w.shape[0]); lin.weight.data.copy_(w); lin.bias.data.copy_(m[f"actor.{i}.bias"])
        layers.append(lin)
        if f"actor.{i + 2}.weight" in m:
            layers.append(nn.ELU())
        i += 2
    actor = nn.Sequential(*layers)
    actor_inputs = ACTOR_IN + POSE_DIM + (3 if bprime else 0)
    if actor[0].in_features != actor_inputs or actor[-1].out_features != ACTION_DIM:
        raise ValueError(f"actor shape {actor[0].in_features} -> {actor[-1].out_features} is not {actor_inputs} -> 12")
    perc.eval(); actor.eval()
    info = {"perception_source": why, "iter": sd.get("iter"), "depth_delay_ticks": perc.cfg.depth_delay_ticks,
            "depth_tick": perc.cfg.depth_tick}
    if bprime:
        info.update(ex42_bprime=True, ex42_bprime_turn_rad=turn_rad)
    return perc, actor, info


def vx_params(on, b, band, ramp) -> tuple:
    """The (on, b, band) tuple of start_runner.correct_est_vx, checked; every value must be given (no default)."""
    from foothold_s2.runners import start_runner as sr
    if on not in (True, False) or b is None or band is None or ramp is None:
        raise ValueError("the vx correction needs on, b, band and ramp given explicitly")
    if float(ramp) != sr.VX_CORR_RAMP:
        raise ValueError(f"vx correction ramp {ramp} differs from the code constant {sr.VX_CORR_RAMP}")
    if not (abs(float(b)) <= 0.05 and float(band) > 0):
        raise ValueError("vx correction b must be within +-0.05 and band > 0")
    return (bool(on), float(b), float(band))


class StepNet(nn.Module):
    def __init__(self, perc: StartPerception, actor: nn.Sequential, vx: tuple):
        super().__init__()
        self.p, self.actor, self.vx = perc, actor, vx

    def forward(self, o, hist, depth2, h_prop, h_terr, tick, first, pose, flag_bearing3=None):
        keep = 1.0 - first
        h_prop2 = self.p.ie.prop_step(hist, h_prop * keep)
        h_terr0 = h_terr * keep
        h_new = self.p.trnet.step(depth2, h_prop2, h_terr0)
        h_terr2 = tick * h_new + (1.0 - tick) * h_terr0
        _rough, refined = self.p.trnet.decode(h_terr2)
        e = self.p.ie.estimate(h_prop2, refined)
        est = torch.cat([e["mu"], e["v"], e["zf"], e["zb"]], -1)
        from foothold_s2.runners.start_runner import correct_est_vx
        columns = [o, correct_est_vx(est, self.vx), pose]
        if flag_bearing3 is not None:
            columns.append(flag_bearing3)
        action = self.actor(torch.cat(columns, -1))
        return action, h_prop2, h_terr2, refined, est


def example_inputs(b: int = 2):
    return (torch.zeros(b, OBS_DIM), torch.zeros(b, HIST_LEN, OBS_DIM), torch.zeros(b, DEPTH_FRAMES, DEPTH_HW, DEPTH_HW),
            torch.zeros(b, 128), torch.zeros(b, 128), torch.ones(b, 1), torch.ones(b, 1), torch.zeros(b, POSE_DIM))


def checkpoint_vx(checkpoint, on=None, b=None, band=None, ramp=None) -> tuple:
    """The vx values to export: the checkpoint's vx_corr entry when it has one (given arguments must then match it), else the arguments
    (all four required: lead 10:32 / 10:36, no hidden default)."""
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False).get("vx_corr")
    given = [x is not None for x in (on, b, band, ramp)]
    if saved is None:
        return (on, b, band, ramp), "arguments"
    rec = (bool(saved["on"]), float(saved["b"]), float(saved["band"]), float(saved["ramp"]))
    if any(given) and (not all(given) or (bool(on), float(b), float(band), float(ramp)) != rec):
        raise ValueError(f"vx arguments {(on, b, band, ramp)} differ from the checkpoint vx_corr {rec}")
    return rec, "checkpoint"


def export(checkpoint, out_dir, opset: int = 17, *, vx_corr_on=None, vx_corr_b=None, vx_corr_band=None, vx_corr_ramp=None) -> dict:
    (vx_corr_on, vx_corr_b, vx_corr_band, vx_corr_ramp), vx_source = checkpoint_vx(checkpoint, vx_corr_on, vx_corr_b, vx_corr_band, vx_corr_ramp)
    vx = vx_params(vx_corr_on, vx_corr_b, vx_corr_band, vx_corr_ramp)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    perc, actor, info = load(checkpoint)
    net = StepNet(perc, actor, vx).eval()
    step_inputs = STEP_INPUTS + ((BPRIME_INPUT,) if info.get("ex42_bprime") else ())
    dyn = {n: {0: "batch"} for n in step_inputs + STEP_OUTPUTS}
    inputs = example_inputs() + ((torch.zeros(2, 3),) if info.get("ex42_bprime") else ())
    with torch.no_grad():
        torch.onnx.export(net, inputs, out / "start_step.onnx", input_names=list(step_inputs), output_names=list(STEP_OUTPUTS),
                          dynamic_axes=dyn, opset_version=opset, dynamo=False)
        torch.onnx.export(actor, (torch.zeros(2, actor[0].in_features),), out / "start_actor.onnx", input_names=["actor_in"],
                          output_names=["action"], dynamic_axes={"actor_in": {0: "batch"}, "action": {0: "batch"}}, opset_version=opset, dynamo=False)
    sha = hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
    spec = {
        "format": "foothold-start-onnx/1", "checkpoint": str(checkpoint), "checkpoint_sha256": sha, "opset": opset, **info,
        "files": {"start_step.onnx": hashlib.sha256((out / "start_step.onnx").read_bytes()).hexdigest(),
                  "start_actor.onnx": hashlib.sha256((out / "start_actor.onnx").read_bytes()).hexdigest()},
        "step_inputs": [
            {"name": "o", "shape": ["batch", OBS_DIM], "dtype": "float32", "what": "proprioceptive observation o_t (45), the policy group of the env, same order and scale"},
            {"name": "hist", "shape": ["batch", HIST_LEN, OBS_DIM], "dtype": "float32", "what": "history ring of o, index 0 = this step (newest)"},
            {"name": "depth2", "shape": ["batch", DEPTH_FRAMES, DEPTH_HW, DEPTH_HW], "dtype": "float32", "what": "2 depth frames from the frame ring after the delay (index 0 = newer), 0..1"},
            {"name": "h_prop", "shape": ["batch", 128], "dtype": "float32", "what": "prop GRU state from the previous step's h_prop_out (zeros at start)"},
            {"name": "h_terr", "shape": ["batch", 128], "dtype": "float32", "what": "TR-Net GRU state from the previous step's h_terr_out (zeros at start)"},
            {"name": "tick", "shape": ["batch", 1], "dtype": "float32", "what": "1.0 on a depth tick (steps_since_reset % depth_tick == 0), else 0.0"},
            {"name": "first", "shape": ["batch", 1], "dtype": "float32", "what": "1.0 on the first step after a reset (zeros both GRU states inside), else 0.0"},
            {"name": "pose", "shape": ["batch", POSE_DIM], "dtype": "float32", "what": "pose command [height change m, roll rad]; 0, 0 = none"}],
        "step_outputs": [
            {"name": "action", "shape": ["batch", ACTION_DIM], "what": "action mean (act_inference), before the env's action scale"},
            {"name": "h_prop_out", "shape": ["batch", 128]}, {"name": "h_terr_out", "shape": ["batch", 128]},
            {"name": "refined_map", "shape": ["batch", MAP_X, MAP_Y], "what": "reconstructed height map, m relative to the base, x 32 (rear -0.475 .. front 1.075, 0.05) x y 16"},
            {"name": "est", "shape": ["batch", EST_DIM], "what": "z mean 16 · v 3 · zf 16 · zb 16"}],
        "actor_only": {"input": f"actor_in [batch, {actor[0].in_features}] = o 45 + est_in 51 + pose 2"
                                + (" + flag_bearing3 3" if info.get("ex42_bprime") else "")
                                + " (est_in = est after the vx correction)", "output": "action [batch, 12]"},
        "vx_correction": {"on": vx[0], "b": vx[1], "band": vx[2], "ramp": float(vx_corr_ramp), "column": 16, "source": vx_source,
                          "rule": "where 0 <= est[16] < band: est_in[16] = est[16] - b * min(est[16] / ramp, 1) * (1 - est[16] / band); other columns unchanged",
                          "note": "part of the policy (training and evaluation apply it to every actor input); the robot uses the same values; start_step.onnx applies it inside, start_actor.onnx expects est_in"},
        "robot_side_rules": {
            "history": "each step: hist = roll(hist, 1) and hist[0] = o; on the first step after a reset every row = o",
            "depth": f"10 Hz: on a tick (steps_since_reset % {info['depth_tick']} == 0) push the new frame into a ring of {DEPTH_FRAMES + info['depth_delay_ticks']} "
                     f"(index 0 newest); on the first step fill the ring with the current frame; depth2 = ring[{info['depth_delay_ticks']}:{info['depth_delay_ticks'] + DEPTH_FRAMES}]",
            "counter": "steps_since_reset starts at 0, tick and first are computed before it is incremented",
            "reset": "first = 1 on the step after a reset (the graph zeros h_prop and h_terr)",
            "depth_preprocessing": "outside the graph: the camera image cropped / resized to 60 x 60 and normalised to 0..1 exactly as foothold_s2/sensors/depth_aug.py",
        },
    }
    if info.get("ex42_bprime"):
        spec["step_inputs"].append({"name": BPRIME_INPUT, "shape": ["batch", 3], "dtype": "float32",
                                    "what": "first flag bearing [valid, unit_x_body, unit_y_body]; zero when unavailable"})
    (out / "start_onnx.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return spec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--vx-corr", choices=("on", "off"), default=None)
    ap.add_argument("--vx-corr-b", type=float, default=None)
    ap.add_argument("--vx-corr-band", type=float, default=None)
    ap.add_argument("--vx-corr-ramp", type=float, default=None)
    a = ap.parse_args(argv)
    spec = export(a.checkpoint, a.out, a.opset, vx_corr_on=None if a.vx_corr is None else a.vx_corr == "on", vx_corr_b=a.vx_corr_b, vx_corr_band=a.vx_corr_band,
                  vx_corr_ramp=a.vx_corr_ramp)
    print(json.dumps({k: spec[k] for k in ("checkpoint_sha256", "perception_source", "files")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
