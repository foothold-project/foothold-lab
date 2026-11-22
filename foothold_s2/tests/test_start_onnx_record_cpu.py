"""START ONNX against a real Isaac record (lead 2026-11-22 09:19 / 09:21 / 10:02): the observations o and the depth frames that went into the
evaluation policy (S2Policy, eval_pred, camera A, rx2qh m250) on three scenes (balance beams L2, gaps L1, flat level 0), 200 steps, 8 envs,
recorded on a Pod by onnx_rec/run_child_onnxrec.py. Replayed on CPU through the deployment path (StartPerception.ingest + step, deterministic,
reconstructed map, resets as recorded) and through start_step.onnx with the GRU states carried by the ONNX outputs.

Judgement (lead 10:06, registered before the record came): (1) main: for action, est and the refined map, max |ONNX - float64| <= 5 x
max |torch float32 - float64| (same inputs, same scene); (2) beside it, absolute: action < 5e-5, est < 5e-5, refined map < 3e-4 (1e-5 is the
float32 floor itself: a synthetic-record rehearsal gave torch float32 1.01e-5 off float64 on the action) reported as flags beside the main
judgement; outer limits (lead 10:08 with the planner): action > 1e-4, est > 1e-4 or refined map > 1e-3 fails whatever the ratio (est outer 1e-4: lead 10:11); (3) no drift: the worst error of
every later 50-step block <= 3 x the first block, for action, est and map; (4) the record-off run (byte check of env_arrays, done beside this
test) decides whether the record is usable at all. The ground-truth map path is not compared (the robot has only the reconstructed map).
Envs with a reset inside the record are reported before and after the reset separately. Written beside the record (onnx_record_check.json): those numbers per scene and
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
    out = {"action": [], "est": [], "map": [], "inp": []}
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
    return out


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
              "judgement": {"main_ratio_vs_float32": 5.0, "abs_beside": {"action": 5e-5, "est": 5e-5, "refined_map": 3e-4}, "outer_fail": {"action": 1e-4, "est": 1e-4, "refined_map": 1e-3}, "block_growth": 3.0, "gt_map_path": "not compared (the robot has the reconstructed map only)"}, "scenes": {}}
    for path in RECORDS:
        rec = dict(np.load(path))
        assert rec["o"].shape[0] >= 200 and float(rec["use_gt"].max()) == 0.0, "record must be 200+ eval_pred steps"
        ref = _replay(perc, actor, rec, torch.float32)
        r64 = _replay(perc64, actor64, rec, torch.float64)
        T, K = rec["o"].shape[:2]
        h_prop = np.zeros((K, 128), np.float32); h_terr = np.zeros((K, 128), np.float32)
        err = {"action": np.zeros(T), "est": np.zeros(T), "refined_map": np.zeros(T), "actor_only": np.zeros(T)}
        f64 = {f"{w}_{k}": 0.0 for w in ("onnx", "torch") for k in ("action", "est", "map")}
        per_env = np.zeros((T, K))
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
                                   "beside_flags": {k: bool(float(err[k].max()) < lim) for k, lim in (("action", 5e-5), ("est", 5e-5), ("refined_map", 3e-4))}}
        print(f"\n{scene}: {json.dumps(report['scenes'][scene]['worst'])} blocks {report['scenes'][scene]['blocks']['action']}")
    (Path(REC_DIR) / "onnx_record_check.json").write_text(json.dumps(report, indent=1))
    for scene, r in report["scenes"].items():
        w = r["worst"]
        f = r["float64"]
        failed = [k for k in ("action", "est", "map") if f[f"ratio_{k}"] > 5.0] + \
                 [f"outer_{k}" for k, lim in (("action", 1e-4), ("actor_only", 1e-4), ("est", 1e-4), ("refined_map", 1e-3)) if w[k] > lim]
        assert not failed, (scene, failed, w, f)
        for k, b in r["blocks"].items():
            assert max(b[1:], default=0.0) <= 3.0 * max(b[0], 1e-9), (scene, k, b)
