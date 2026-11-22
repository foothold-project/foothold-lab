"""START ONNX against a real Isaac record (lead 2026-11-22 09:19 / 09:21 / 10:02): the observations o and the depth frames that went into the
evaluation policy (S2Policy, eval_pred, camera A, rx2qh m250) on three scenes (balance beams L2, gaps L1, flat level 0), 200 steps, 8 envs,
recorded on a Pod by onnx_rec/run_child_onnxrec.py. Replayed on CPU through the deployment path (StartPerception.ingest + step, deterministic,
reconstructed map, resets as recorded) and through start_step.onnx with the GRU states carried by the ONNX outputs.

Judgement (lead 10:26, the third registered form, before the second record was opened): per step r = max|ONNX - float64| / max(max|torch
float32 - float64|, floor 1e-7) for action, est and map each: (a) every 50-step block median of r <= 5, (b) the last block median <= 2 x the
first block median; outer limits: action and actor-only 1e-4, est 1e-4, map 1e-3; device baseline: max |GPU record action - CPU torch| < 1e-4
(the record must come from a copy that reads perception_ema). Written, not judged: the whole-record max ratio, A' (relative block medians),
B (rise), the 5e-5 / 3e-4 beside flags, the 50-step block maxima, and the reference "state fed in" comparison (ONNX given the torch GRU
states each step against ONNX carrying its own). The record-off run (byte check of env_arrays, beside this test) decides whether the record
is usable. The ground-truth map path is not compared (the robot has only the reconstructed map). Envs with a reset inside the record are reported before and after the reset separately. Written beside the record (onnx_record_check.json): those numbers per scene and
block, the float64 reference (ONNX and torch float32 against the same net in float64, and their ratio) and, as the device baseline, CPU torch
against the action / est recorded on the GPU (not judged). Set ONNXREC_DIR to the fetched folder (out_cam/onnxrec_*/onnxrec.npz)."""
from __future__ import annotations

import copy
import glob
import json
import os
from pathlib import Path

import numpy as np
import pytest
import torch

ort = pytest.importorskip("onnxruntime")
from foothold_s2.deploy import export_start_onnx as ex  # noqa: E402

CKPT = "/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261120_193344_r2/main/EX-42-B-E2_20261122_033431/model_250.pt"
REC_DIR = os.environ.get("ONNXREC_DIR", "")
RECORDS = sorted(glob.glob(os.path.join(REC_DIR, "*", "onnxrec.npz"))) if REC_DIR else []
BLOCK = 50
R_FLOOR = 1e-7       # floor of the torch32 vs float64 error in r (lead 10:26): below it float64 and float32 agree to the printed digits


def _state64(st):
    for k in ("h_prop", "h_terr", "hist", "frames"):
        setattr(st, k, getattr(st, k).double())
    return st


def _replay(perc, actor, rec, dtype):
    """Torch deployment path over the record; returns per-step action, est, refined map and the ingest outputs (for the ONNX feed)."""
    T, K = rec["o"].shape[:2]
    st = perc.init_state(K, "cpu"); st.use_gt[:] = False
    if dtype == torch.float64:
        st = _state64(st)
    no_gt = torch.zeros(K, dtype=torch.bool)
    gt = torch.zeros(K, 32, 16, dtype=dtype)
    out = {"action": [], "est": [], "map": [], "inp": [], "h": []}
    for t in range(T):
        reset = torch.tensor(rec["reset_before"][t] > 0)
        if reset.any():
            perc.reset_envs(st, reset, no_gt)
        o = torch.tensor(rec["o"][t], dtype=dtype); d = torch.tensor(rec["depth"][t], dtype=dtype)
        pose = torch.tensor(rec["pose"][t], dtype=dtype) if "pose" in rec else torch.zeros(K, 2, dtype=dtype)
        with torch.no_grad():
            inp = perc.ingest(st, o, d)
            est = perc.step(st, inp, gt, deterministic=True)
            _r, refined = perc.trnet.decode(st.h_terr)
            act = actor(torch.cat([o, est, pose], -1))
        out["action"].append(act.numpy().astype(np.float64)); out["est"].append(est.numpy().astype(np.float64))
        out["map"].append(refined.numpy().astype(np.float64)); out["inp"].append({k: v.clone() for k, v in inp.items()} | {"pose": pose})
        out["h"].append((st.h_prop.float().numpy().copy(), st.h_terr.float().numpy().copy()))     # torch state after this step
    return out


def _medians(err):
    return [float(np.median(err[i:i + BLOCK])) for i in range(0, len(err), BLOCK)]


def _rise(rel):
    """B: (95 % upper end of the least-squares slope of the relative error) x (record length) <= the first 50-step block median."""
    r = _slope(rel)
    up = r["slope_per_step"] + r["half_width_95"]
    first = float(np.median(np.asarray(rel)[:BLOCK]))
    return {"slope_per_step": r["slope_per_step"], "half_width_95": r["half_width_95"], "interval_holds_0": r["pass"],
            "upper_95_x_length": up * len(rel), "first_block_median": first, "pass": bool(up * len(rel) <= first)}


def _slope(err):
    """Least-squares slope of the per-step error over the step index, its 95 % half-width, and whether the rule (slope <= 0 or interval holds 0) passes."""
    t = np.arange(len(err), dtype=np.float64); e = np.asarray(err, np.float64)
    tc = t - t.mean(); b = float((tc * (e - e.mean())).sum() / (tc * tc).sum())
    resid = e - e.mean() - b * tc
    se = float(np.sqrt((resid * resid).sum() / max(len(e) - 2, 1) / (tc * tc).sum()))
    return {"slope_per_step": b, "half_width_95": 1.96 * se, "pass": bool(b <= 0 or b - 1.96 * se <= 0)}


def _blocks(err):
    return [float(err[i:i + BLOCK].max()) for i in range(0, len(err), BLOCK)]


@pytest.mark.skipif(not RECORDS, reason="no ONNX record (set ONNXREC_DIR)")
def test_record_replay_matches(tmp_path):
    spec = ex.export(CKPT, tmp_path)
    perc, actor, _ = ex.load(CKPT)
    perc64, actor64 = copy.deepcopy(perc).double(), copy.deepcopy(actor).double()
    sess = ort.InferenceSession(str(tmp_path / "start_step.onnx"), providers=["CPUExecutionProvider"])
    sess_a = ort.InferenceSession(str(tmp_path / "start_actor.onnx"), providers=["CPUExecutionProvider"])
    brk = float(os.environ.get("ONNXREC_BREAK_ACTION", "0"))                # break test only: offset added to the ONNX action
    report = {"checkpoint_sha256": spec["checkpoint_sha256"], "perception_source": spec["perception_source"],
              "judgement": {"main_ratio_vs_float32": 5.0, "abs_beside": {"action": 5e-5, "est": 5e-5, "refined_map": 3e-4}, "outer_fail": {"action": 1e-4, "est": 1e-4, "refined_map": 1e-3}, "block_growth": 3.0, "gt_map_path": "not compared (the robot has the reconstructed map only)", "eval_copy_note": os.environ.get("ONNXREC_COPY_NOTE", "")}, "scenes": {}}
    for path in RECORDS:
        rec = dict(np.load(path))
        assert rec["o"].shape[0] >= 200 and float(rec["use_gt"].max()) == 0.0, "record must be 200+ eval_pred steps"
        ref = _replay(perc, actor, rec, torch.float32)
        r64 = _replay(perc64, actor64, rec, torch.float64)
        T, K = rec["o"].shape[:2]
        h_prop = np.zeros((K, 128), np.float32); h_terr = np.zeros((K, 128), np.float32)
        err = {"action": np.zeros(T), "est": np.zeros(T), "refined_map": np.zeros(T), "actor_only": np.zeros(T)}
        f64 = {f"{w}_{k}": 0.0 for w in ("onnx", "torch") for k in ("action", "est", "map")}
        per_env = np.zeros((T, K)); rel = {k: np.zeros(T) for k in ("action", "est", "refined_map")}
        d_onnx = {k: np.zeros(T) for k in ("action", "est", "refined_map")}; d_t32 = {k: np.zeros(T) for k in ("action", "est", "refined_map")}
        injected = {k: np.zeros(T) for k in ("action", "est", "refined_map")}
        ticks = 0
        for t in range(T):
            inp = ref["inp"][t]
            feed = {"o": rec["o"][t].astype(np.float32), "hist": inp["hist"].numpy(), "depth2": inp["depth2"].numpy(), "h_prop": h_prop,
                    "h_terr": h_terr, "tick": inp["tick"].float()[:, None].numpy(), "first": inp["first"].float()[:, None].numpy(),
                    "pose": inp["pose"].numpy().astype(np.float32)}
            action, h_prop, h_terr, refined, est = sess.run(list(ex.STEP_OUTPUTS), feed)
            action = action + brk
            (a_only,) = sess_a.run(["action"], {"actor_in": np.concatenate([feed["o"], ref["est"][t].astype(np.float32), feed["pose"]], -1)})
            err["actor_only"][t] = np.abs(a_only - ref["action"][t]).max()
            ticks += int(inp["tick"].any())
            err["action"][t] = np.abs(action - ref["action"][t]).max()
            err["est"][t] = np.abs(est - ref["est"][t]).max()
            err["refined_map"][t] = np.abs(refined - ref["map"][t]).max()
            per_env[t] = np.abs(action - ref["action"][t]).max(-1)
            for k, (x, y) in {"action": (action, ref["action"][t]), "est": (est, ref["est"][t]), "refined_map": (refined, ref["map"][t])}.items():
                rel[k][t] = float(np.abs(x - y).max() / max(float(np.abs(y).max()), 1.0))
            for k, (x, y, z) in {"action": (action - brk, ref["action"][t], r64["action"][t]), "est": (est, ref["est"][t], r64["est"][t]),
                                 "refined_map": (refined, ref["map"][t], r64["map"][t])}.items():
                d_onnx[k][t] = float(np.abs((x + (brk if k == "action" else 0.0)) - z).max()); d_t32[k][t] = float(np.abs(y - z).max())
            hp0, ht0 = (np.zeros((K, 128), np.float32),) * 2 if t == 0 else ref["h"][t - 1]       # reference only: torch state fed in each step
            a_i, _hp, _ht, m_i, e_i = sess.run(list(ex.STEP_OUTPUTS), feed | {"h_prop": hp0, "h_terr": ht0})
            injected["action"][t] = float(np.abs(a_i - ref["action"][t]).max()); injected["est"][t] = float(np.abs(e_i - ref["est"][t]).max())
            injected["refined_map"][t] = float(np.abs(m_i - ref["map"][t]).max())
            f64["onnx_est"] = max(f64["onnx_est"], float(np.abs(est - r64["est"][t]).max()))
            f64["torch_est"] = max(f64["torch_est"], float(np.abs(ref["est"][t] - r64["est"][t]).max()))
            f64["onnx_action"] = max(f64["onnx_action"], float(np.abs(action - r64["action"][t]).max()))
            f64["torch_action"] = max(f64["torch_action"], float(np.abs(ref["action"][t] - r64["action"][t]).max()))
            f64["onnx_map"] = max(f64["onnx_map"], float(np.abs(refined - r64["map"][t]).max()))
            f64["torch_map"] = max(f64["torch_map"], float(np.abs(ref["map"][t] - r64["map"][t]).max()))
        device = {"action": float(np.abs(np.stack(ref["action"]) - rec["action"]).max()), "est": float(np.abs(np.stack(ref["est"]) - rec["est"]).max())}
        scene = Path(path).parent.name
        report["scenes"][scene] = {"steps": T, "envs": K, "ticks": ticks, "resets": int((rec["reset_before"] > 0).sum()),
                                   "worst": {k: float(v.max()) for k, v in err.items()}, "blocks": {k: _blocks(v) for k, v in err.items()},
                                   "float64": f64 | {f"ratio_{k}": f64[f"onnx_{k}"] / max(f64[f"torch_{k}"], 1e-30) for k in ("action", "est", "map")},
                                   "reset_envs_action": {str(e): {"step": int(np.argmax(rec["reset_before"][:, e] > 0)),
                                                                  "before": float(per_env[:int(np.argmax(rec["reset_before"][:, e] > 0)), e].max(initial=0.0)),
                                                                  "after": float(per_env[int(np.argmax(rec["reset_before"][:, e] > 0)):, e].max())}
                                                         for e in range(K) if (rec["reset_before"][1:, e] > 0).any()},
                                   "device_baseline_cpu_torch_vs_gpu_record": device,
                                   "r_floor": R_FLOOR,
                                   "r_block_median": {k: _medians(d_onnx[k] / np.maximum(d_t32[k], R_FLOOR)) for k in d_onnx},
                                   "state_injected_onnx_vs_torch_max": {k: float(v.max()) for k, v in injected.items()},
                                   "rel_block_median": {k: _medians(v) for k, v in rel.items()},
                                   "est_block_median": _medians(err["est"]),
                                   "rise_B": {k: _rise(v) for k, v in rel.items()},
                                   "beside_flags": {k: bool(float(err[k].max()) < lim) for k, lim in (("action", 5e-5), ("est", 5e-5), ("refined_map", 3e-4))}}
        print(f"\n{scene}: {json.dumps(report['scenes'][scene]['worst'])} blocks {report['scenes'][scene]['blocks']['action']}")
    (Path(REC_DIR) / "onnx_record_check.json").write_text(json.dumps(report, indent=1))
    for scene, r in report["scenes"].items():
        w = r["worst"]
        f = r["float64"]
        failed = [f"outer_{k}" for k, lim in (("action", 1e-4), ("actor_only", 1e-4), ("est", 1e-4), ("refined_map", 1e-3)) if w[k] > lim]
        for k, m in r["r_block_median"].items():                                   # lead 10:26: (가) every block median r <= 5 (나) last <= 2 x first
            failed += [f"r_block_{k}"] if max(m) > 5.0 else []
            failed += [f"r_last_vs_first_{k}"] if m[-1] > 2.0 * m[0] else []
        failed += ["device_baseline_action"] if r["device_baseline_cpu_torch_vs_gpu_record"]["action"] >= 1e-4 else []
        assert not failed, (scene, failed, r["r_block_median"], r["device_baseline_cpu_torch_vs_gpu_record"])     # A' · B · max ratio: values only
