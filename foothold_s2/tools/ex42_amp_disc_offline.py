"""EX-42 AMP offline discriminator check (plan AMP-PLAN-1126 step 2, planner 00:26 condition: if one state column alone separates
reference from policy at ~100 %, no GPU run).

Reference: walk transitions of ex42_amp_reference (Classic + Sport). Policy side: the real-robot rollouts of our deployed START
policy (jetson start-*.jsonl, phase policy, command not zero), cut and normalised the same way (q minus that log's zero-command
median pose). Same robot and sensors on both sides, so a column that separates them is a gait difference, not sim-vs-real noise.
(The sim side check is the Kit run of step 4.)

Splits are by segment (80 / 20, fixed seed). Reports:
    full     the AMP discriminator ([512, 256] ELU, LSGAN, GP 10) held-out accuracy, mean D and style reward per side
    single   per state column: a small net on (x_t, x_t+1) of that column only, held-out accuracy
    drop     per column group: the full input minus that group, held-out accuracy

    python -m foothold_s2.tools.ex42_amp_disc_offline --ref DIR/amp_ref.npz --out DIR/amp_disc_offline.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from foothold_s2.runners import ex42_amp_disc as amp
from foothold_s2.tools import ex42_amp_reference as ref_tool

POLICY_LOGS = (ref_tool.TRACE_DIR / "start-20261123-162317-000.jsonl", ref_tool.TRACE_DIR / "start-20261123-140819-000.jsonl")
GROUPS = {"q_hip": range(0, 4), "q_thigh": range(4, 8), "q_calf": range(8, 12), "dq_hip": range(12, 16), "dq_thigh": range(16, 20),
          "dq_calf": range(20, 24), "gyro": range(24, 27), "grav": range(27, 30)}
SEP_LIMIT = 0.98


def policy_rows(paths=POLICY_LOGS) -> dict:
    s, seg, base = [], [], 0
    for p in paths:
        rows = []
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("phase") == "policy" and r.get("q") and r.get("wall") is not None and not r.get("stale"):
                rows.append(r)
        rows.sort(key=lambda r: r["wall"])
        cmd = np.array([r.get("cmd") or [0.0, 0.0, 0.0] for r in rows], dtype=np.float64)
        q = np.array([r["q"] for r in rows]); wall = np.array([r["wall"] for r in rows])
        zero = np.abs(cmd).max(axis=1) < 1e-6
        pose = np.median(q[zero], axis=0)
        st = np.concatenate([q - pose, np.array([r["dq"] for r in rows]), np.array([r["gyro"] for r in rows]),
                             np.array([r["grav"] for r in rows])], axis=1)
        new = np.ones(len(rows), dtype=bool)
        new[1:] = (np.diff(wall) > ref_tool.GAP_S) | (zero[1:] != zero[:-1])
        sg = np.cumsum(new) - 1 + base
        keep = ~zero
        s.append(st[keep]); seg.append(sg[keep]); base = int(sg.max()) + 1
    return {"s": np.concatenate(s).astype(np.float32), "seg": np.concatenate(seg)}


def pairs(s: np.ndarray, seg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    i = np.flatnonzero(seg[1:] == seg[:-1])
    return np.concatenate([s[i], s[i + 1]], axis=1), seg[i]


def split(x, seg, rng, frac=0.2):
    u = np.unique(seg)
    test = set(rng.choice(u, max(1, int(len(u) * frac)), replace=False).tolist())
    m = np.array([g in test for g in seg])
    return x[~m], x[m]


def train(xr, xp, xr_t, xp_t, hidden, steps, seed, gp=amp.GP_WEIGHT, batch=512, lr=None) -> dict:
    torch.manual_seed(seed)
    xr, xp, xr_t, xp_t = (torch.as_tensor(a) for a in (xr, xp, xr_t, xp_t))
    disc = amp.AmpDiscriminator(xr.shape[1], hidden, xr.mean(0), xr.std(0))
    opt = torch.optim.Adam(disc.parameters(), lr=lr or 1e-3)
    g = torch.Generator().manual_seed(seed)
    for _ in range(steps):
        a = xr[torch.randint(len(xr), (batch,), generator=g)]
        b = xp[torch.randint(len(xp), (batch,), generator=g)]
        amp.disc_step(disc, opt, a, b, gp)
    with torch.no_grad():
        dr, dp = disc(xr_t), disc(xp_t)
    acc = 0.5 * (float((dr > 0).float().mean()) + float((dp < 0).float().mean()))
    return {"acc": round(acc, 4), "D_ref": round(float(dr.mean()), 3), "D_pol": round(float(dp.mean()), 3),
            "style_ref": round(float(amp.style_reward(dr).mean()), 3), "style_pol": round(float(amp.style_reward(dp).mean()), 3)}


def cols(x, idx):
    idx = list(idx)
    return x[:, idx + [i + amp.STATE_DIM for i in idx]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--small-steps", type=int, default=400)
    a = ap.parse_args(argv)
    torch.set_num_threads(4)
    r = np.load(a.ref)
    walk = r["kind"] == 0
    xr, sr = pairs(r["s"][walk], r["seg"][walk])
    p = policy_rows()
    xp, sp = pairs(p["s"], p["seg"])
    rng = np.random.default_rng(0)
    xr_tr, xr_te = split(xr, sr, rng)
    xp_tr, xp_te = split(xp, sp, rng)
    out = {"ref_transitions": len(xr), "policy_transitions": len(xp), "policy_logs": [str(x) for x in POLICY_LOGS],
           "sep_limit": SEP_LIMIT}
    out["full"] = train(xr_tr, xp_tr, xr_te, xp_te, amp.HIDDEN, a.steps, 0)
    names = ref_tool.STATE_NAMES
    out["single"] = {names[c]: train(cols(xr_tr, [c]), cols(xp_tr, [c]), cols(xr_te, [c]), cols(xp_te, [c]), (64,), a.small_steps, 0)["acc"]
                     for c in range(amp.STATE_DIM)}
    out["drop"] = {}
    for gname, idx in GROUPS.items():
        keep = [c for c in range(amp.STATE_DIM) if c not in idx]
        out["drop"][gname] = train(cols(xr_tr, keep), cols(xp_tr, keep), cols(xr_te, keep), cols(xp_te, keep), (128, 64), a.small_steps, 0)["acc"]
    worst = max(out["single"].items(), key=lambda kv: kv[1])
    out["single_max"] = {"column": worst[0], "acc": worst[1]}
    out["verdict"] = "BLOCK (one column separates)" if worst[1] >= SEP_LIMIT else "ok (no single column separates)"
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("ref_transitions", "policy_transitions", "full", "single_max", "verdict", "drop")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
