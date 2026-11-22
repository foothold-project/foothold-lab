"""Judge a START ONNX export against a real Isaac record (lead 2026-11-22 11:34, the registered next-round rule). CPU only.

Per step and for action, est and the refined map: r = max|ONNX - float64| / max(max|torch float32 - float64|, floor 2e-5) must be <= 5 at every
step; absolute cap on the action only: max|ONNX - torch float32| < 1e-4. Written beside (not judged): device baseline (GPU record action vs
CPU torch), the action difference to another checkpoint replayed on the same record (e.g. the original model_N.pt against its EMA), and for
records made with the map switched off (probe_prop_only) only that on/off action difference (ONNX has no map switch: the robot always has
the reconstructed map). Prints one VERDICT line per scene and writes <record dir>/onnx_judge.json.

  python -m foothold_s2.deploy.onnx_record_judge --checkpoint <model_N.pt> --record-dir <out_cam> --vx-corr on --vx-corr-b 0.009 \\
      --vx-corr-band 0.3 --vx-corr-ramp 0.05 [--compare-checkpoint <other model_N.pt>]
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import torch

from foothold_s2.deploy import export_start_onnx as ex
from foothold_s2.runners.start_runner import correct_est_vx

FLOOR = 2e-5
R_MAX = 5.0
ACTION_CAP = 1e-4


def replay(perc, actor, rec, dtype, vx):
    T, K = rec["o"].shape[:2]
    st = perc.init_state(K, "cpu"); st.use_gt[:] = False
    if dtype == torch.float64:
        for k in ("h_prop", "h_terr", "hist", "frames"):
            setattr(st, k, getattr(st, k).double())
    no_gt = torch.zeros(K, dtype=torch.bool); gt = torch.zeros(K, 32, 16, dtype=dtype)
    out = {"action": [], "est": [], "map": [], "inp": []}
    for t in range(T):
        reset = torch.tensor(rec["reset_before"][t] > 0)
        if reset.any():
            perc.reset_envs(st, reset, no_gt)
        o = torch.tensor(rec["o"][t], dtype=dtype); d = torch.tensor(rec["depth"][t], dtype=dtype)
        pose = torch.tensor(rec["pose"][t], dtype=dtype)
        with torch.no_grad():
            inp = perc.ingest(st, o, d)
            est = perc.step(st, inp, gt, deterministic=True)
            _r, refined = perc.trnet.decode(st.h_terr)
            act = actor(torch.cat([o, correct_est_vx(est, vx[:3]), pose], -1))
        out["action"].append(act.numpy().astype(np.float64)); out["est"].append(est.numpy().astype(np.float64))
        out["map"].append(refined.numpy().astype(np.float64)); out["inp"].append({k: v.clone() for k, v in inp.items()} | {"pose": pose})
    return out


def judge(checkpoint, record_dir, vx, compare=None) -> dict:
    import onnxruntime as ort
    tmp = tempfile.mkdtemp()
    spec = ex.export(checkpoint, tmp, vx_corr_on=vx[0], vx_corr_b=vx[1], vx_corr_band=vx[2], vx_corr_ramp=vx[3])
    sess = ort.InferenceSession(str(Path(tmp) / "start_step.onnx"), providers=["CPUExecutionProvider"])
    perc, actor, _ = ex.load(checkpoint)
    perc64, actor64 = copy.deepcopy(perc).double(), copy.deepcopy(actor).double()
    other = ex.load(compare)[:2] if compare else None
    report = {"checkpoint": str(checkpoint), "checkpoint_sha256": spec["checkpoint_sha256"], "vx_correction": spec["vx_correction"],
              "rule": {"r_max": R_MAX, "floor": FLOOR, "action_cap": ACTION_CAP}, "compare_checkpoint": str(compare) if compare else None, "scenes": {}}
    for path in sorted(glob.glob(os.path.join(record_dir, "*", "onnxrec.npz"))):
        scene = Path(path).parent.name; rec = dict(np.load(path)); T, K = rec["o"].shape[:2]
        mapoff = scene.endswith("_mapoff")
        ref = replay(perc, actor, rec, torch.float32, vx)
        row = {"steps": T, "envs": K, "map_off_record": mapoff,
               "device_baseline_action": float(np.abs(np.stack(ref["action"]) - rec["action"]).max())}
        if other is not None:
            oth = replay(other[0], other[1], rec, torch.float32, vx)
            row["compare_action_max"] = float(np.abs(np.stack(oth["action"]) - np.stack(ref["action"])).max())
            row["compare_action_mean"] = float(np.abs(np.stack(oth["action"]) - np.stack(ref["action"])).mean())
        if mapoff:                                       # ONNX has no map switch: record the recorded action only
            row["verdict"] = "record only (map off)"; report["scenes"][scene] = row; print(f"VERDICT {scene} record-only {row}"); continue
        r64 = replay(perc64, actor64, rec, torch.float64, vx)
        hp = np.zeros((K, 128), np.float32); ht = hp.copy()
        rmax = {"action": 0.0, "est": 0.0, "refined_map": 0.0}; bad = {k: [] for k in rmax}; cap = 0.0
        for t in range(T):
            inp = ref["inp"][t]
            feed = {"o": rec["o"][t].astype(np.float32), "hist": inp["hist"].numpy(), "depth2": inp["depth2"].numpy(), "h_prop": hp, "h_terr": ht,
                    "tick": inp["tick"].float()[:, None].numpy(), "first": inp["first"].float()[:, None].numpy(), "pose": inp["pose"].numpy().astype(np.float32)}
            action, hp, ht, refined, est = sess.run(list(ex.STEP_OUTPUTS), feed)
            for k, (x, y, z) in {"action": (action, ref["action"][t], r64["action"][t]), "est": (est, ref["est"][t], r64["est"][t]),
                                 "refined_map": (refined, ref["map"][t], r64["map"][t])}.items():
                r = float(np.abs(x - z).max()) / max(float(np.abs(y - z).max()), FLOOR)
                rmax[k] = max(rmax[k], r)
                if r > R_MAX:
                    bad[k].append(t)
            cap = max(cap, float(np.abs(action - ref["action"][t]).max()))
        fails = [f"r_{k}_steps{v[:5]}" for k, v in bad.items() if v] + (["action_cap"] if cap >= ACTION_CAP else [])
        row.update(r_max=rmax, action_max_onnx_vs_torch32=cap, fails=fails, verdict="PASS" if not fails else "FAIL")
        report["scenes"][scene] = row
        print(f"VERDICT {scene} {row['verdict']} r_max {rmax} action_cap {cap:.2e} device {row['device_baseline_action']:.2e} fails {fails}")
    (Path(record_dir) / "onnx_judge.json").write_text(json.dumps(report, indent=1))
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--checkpoint", required=True); ap.add_argument("--record-dir", required=True)
    ap.add_argument("--vx-corr", choices=("on", "off"), required=True); ap.add_argument("--vx-corr-b", type=float, required=True)
    ap.add_argument("--vx-corr-band", type=float, required=True); ap.add_argument("--vx-corr-ramp", type=float, required=True)
    ap.add_argument("--compare-checkpoint")
    a = ap.parse_args(argv)
    rep = judge(a.checkpoint, a.record_dir, (a.vx_corr == "on", a.vx_corr_b, a.vx_corr_band, a.vx_corr_ramp), a.compare_checkpoint)
    return 0 if all(s.get("verdict") in ("PASS", "record only (map off)") for s in rep["scenes"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
