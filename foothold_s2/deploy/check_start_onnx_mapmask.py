"""Compare a masked START step graph with the old on/off graphs and Torch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from foothold_s2.deploy import export_start_onnx as base

OUTPUTS = base.STEP_OUTPUTS
TOL = 1e-4


def records(paths, max_ticks):
    chunks = []
    for path in paths:
        with np.load(path, allow_pickle=False) as z:
            part = {key: z[key][:max_ticks].astype(np.float32) for key in ("o", "depth", "pose", "reset_before")}
        part["reset_before"][0] = 1.0
        chunks.append(part)
    if not chunks:
        raise ValueError("at least one real recording is required")
    return {key: np.concatenate([part[key] for part in chunks]) for key in chunks[0]}


def random_records(stats_path, ticks, envs, seed):
    rng = np.random.default_rng(seed)
    with np.load(stats_path, allow_pickle=False) as z:
        obs = z["o"].reshape(-1, 45)
    o = (obs.mean(0) + obs.std(0) * rng.standard_normal((ticks, envs, 45))).astype(np.float32)
    depth = rng.uniform(0, 1, (ticks, envs, 60, 60)).astype(np.float32)
    reset = (rng.random((ticks, envs)) < .003).astype(np.float32)
    reset[0] = 1.0
    return {"o": o, "depth": depth, "pose": np.zeros((ticks, envs, 2), np.float32), "reset_before": reset}


def input_rows(data, delay, depth_tick):
    n = data["o"].shape[1]
    hist = np.zeros((n, 10, 45), np.float32)
    frames = np.zeros((n, 2 + delay, 60, 60), np.float32)
    count = np.zeros(n, np.int64)
    for o, depth, pose, reset in zip(data["o"], data["depth"], data["pose"], data["reset_before"]):
        reset = reset.astype(bool)
        count[reset] = 0
        first = count == 0
        hist = np.where(first[:, None, None], o[:, None, :], np.roll(hist, 1, 1)).copy()
        hist[:, 0] = o
        tick = count % depth_tick == 0
        moved = np.roll(frames, 1, 1)
        moved[:, 0] = depth
        candidate = np.where(first[:, None, None, None], depth[:, None], moved)
        frames = np.where(tick[:, None, None, None], candidate, frames).copy()
        count += 1
        yield {"o": o, "hist": hist.copy(), "depth2": frames[:, delay:delay + 2].copy(),
               "h_prop": np.zeros((n, 128), np.float32), "h_terr": np.zeros((n, 128), np.float32),
               "tick": tick.astype(np.float32)[:, None], "first": first.astype(np.float32)[:, None], "pose": pose}


def compare(checkpoint, masked_path, legacy_on, legacy_off, data, *, max_abs=TOL):
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    opts.inter_op_num_threads = 1
    sessions = {"masked": ort.InferenceSession(str(masked_path), opts, providers=["CPUExecutionProvider"]),
                "on": ort.InferenceSession(str(legacy_on), opts, providers=["CPUExecutionProvider"]),
                "off": ort.InferenceSession(str(legacy_off), opts, providers=["CPUExecutionProvider"])}
    spec = json.loads((Path(masked_path).parent / "start_onnx.json").read_text(encoding="utf-8"))
    if tuple(v.name for v in sessions["masked"].get_inputs()) != base.STEP_INPUTS + ("map_mask",):
        raise ValueError("masked ONNX input contract differs")
    if tuple(v.name for v in sessions["masked"].get_outputs()) != OUTPUTS:
        raise ValueError("masked ONNX output contract differs")
    vx_spec = spec["vx_correction"]
    vx = base.vx_params(vx_spec["on"], vx_spec["b"], vx_spec["band"], vx_spec["ramp"])
    torch_nets = {}
    for mode in ("on", "off"):
        perc, actor, _ = base.load(checkpoint)
        perc.ie.mask_map_tokens = mode == "off"
        torch_nets[mode] = base.StepNet(perc, actor, vx).eval()
    n = data["o"].shape[1]
    states = {name: {"h_prop": np.zeros((n, 128), np.float32), "h_terr": np.zeros((n, 128), np.float32)}
              for name in ("mask_on", "mask_off", "old_on", "old_off", "torch_on", "torch_off")}
    maxima = {mode: {source: {output: 0.0 for output in OUTPUTS} for source in ("old", "torch")}
              for mode in ("on", "off")}
    rows = input_rows(data, int(spec["depth_delay_ticks"]), int(spec["depth_tick"]))
    with torch.inference_mode():
        for row in rows:
            for mode in ("on", "off"):
                compared = {}
                for name, session, mask in (("mask", sessions["masked"], float(mode == "off")),
                                             ("old", sessions[mode], None)):
                    state = states[name + "_" + mode if name == "mask" else "old_" + mode]
                    feed = {**row, "h_prop": state["h_prop"], "h_terr": state["h_terr"]}
                    if mask is not None:
                        feed["map_mask"] = np.full((n, 1), mask, np.float32)
                    out = dict(zip(OUTPUTS, session.run(list(OUTPUTS), feed)))
                    state["h_prop"], state["h_terr"] = out["h_prop_out"], out["h_terr_out"]
                    compared[name] = out
                state = states["torch_" + mode]
                tfeed = {**row, "h_prop": state["h_prop"], "h_terr": state["h_terr"]}
                tout = torch_nets[mode](*(torch.from_numpy(tfeed[key]) for key in base.STEP_INPUTS))
                torch_out = {key: value.numpy() for key, value in zip(OUTPUTS, tout)}
                state["h_prop"], state["h_terr"] = torch_out["h_prop_out"], torch_out["h_terr_out"]
                for source, reference in (("old", compared["old"]), ("torch", torch_out)):
                    for key in OUTPUTS:
                        delta = float(np.max(np.abs(compared["mask"][key] - reference[key])))
                        maxima[mode][source][key] = max(maxima[mode][source][key], delta)
    # The acceptance gate is parity with the two existing ONNX graphs. Torch
    # recurrent self-feedback can accumulate a separate ONNX/BLAS roundoff;
    # report every Torch output independently rather than hiding that drift.
    if not all(np.isfinite(v) and v <= max_abs for mode in maxima.values()
               for v in mode["old"].values()):
        raise AssertionError(f"masked versus legacy ONNX exceeds {max_abs}: {maxima}")
    if not all(np.isfinite(mode["torch"][key]) and mode["torch"][key] <= max_abs
               for mode in maxima.values() for key in ("action", "est")):
        raise AssertionError(f"masked versus Torch action/est exceeds {max_abs}: {maxima}")
    return {"ticks": int(data["o"].shape[0]), "envs": int(n), "tolerance": max_abs,
            "torch_fastpath": torch.backends.mha.get_fastpath_enabled(), "max_abs": maxima,
            "torch_refined_map_within_1e_minus4": all(mode["torch"]["refined_map"] <= max_abs for mode in maxima.values())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--masked", required=True)
    ap.add_argument("--legacy-on", required=True)
    ap.add_argument("--legacy-off", required=True)
    ap.add_argument("--real", nargs="+")
    ap.add_argument("--random-stats")
    ap.add_argument("--max-ticks", type=int, default=100)
    ap.add_argument("--random-ticks", type=int, default=100)
    ap.add_argument("--random-envs", type=int, default=4)
    ap.add_argument("--no-fastpath", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.no_fastpath:
        torch.backends.mha.set_fastpath_enabled(False)
    cases = {}
    if args.real:
        cases["real"] = records(args.real, args.max_ticks)
    if args.random_stats:
        cases["random"] = random_records(args.random_stats, args.random_ticks, args.random_envs, 1123)
    if not cases:
        ap.error("--real or --random-stats required")
    result = {name: compare(args.checkpoint, args.masked, args.legacy_on, args.legacy_off, data)
              for name, data in cases.items()}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
