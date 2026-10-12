# CPU analysis of out/cmd_dist/<tag>/ (events.npz, cmd_steps.npy, meta.json) -> summary.json
# Usage: python cmd_analyze.py <tag> [--expect_test]
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
tag = sys.argv[1]
D = os.path.join(HERE, "out", "cmd_dist", tag)
meta = json.load(open(os.path.join(D, "meta.json")))
z = np.load(os.path.join(D, "events.npz"), allow_pickle=False)
ev, tidx, tnames = z["ev"], z["terrain_idx"], [str(t) for t in z["terrain_names"]]
C = np.load(os.path.join(D, "cmd_steps.npy"))  # (T, N, 3)
T, N, _ = C.shape
dt = meta["episode"]["step_dt"]
vx, vy, wz = C[..., 0], C[..., 1], C[..., 2]
sp = np.hypot(vx, vy)
EPS = 1e-6


def frac(m, w=None):
    return float(m.mean()) if w is None else float(m[w].mean()) if w.any() else None


def cats(vx, vy, wz, sel=None):
    sp_ = np.hypot(vx, vy)
    if sel is not None:
        vx, vy, wz, sp_ = vx[sel], vy[sel], wz[sel], sp_[sel]
    pz = sp_ < EPS
    out = {
        "n": int(vx.size),
        "stop_all_zero": frac(pz & (np.abs(wz) < EPS)),
        "planar_zero_turn": frac(pz & (np.abs(wz) >= EPS)),
        "planar_speed": {b: frac((sp_ >= lo) & (sp_ < hi) & ~pz) for b, lo, hi in (
            ("(0,0.1)", 0, 0.1), ("[0.1,0.2)", 0.1, 0.2), ("[0.2,0.3)", 0.2, 0.3), ("[0.3,0.5)", 0.3, 0.5),
            ("[0.5,0.75)", 0.5, 0.75), ("[0.75,1.0]", 0.75, 1.0 + 1e-5), (">1.0", 1.0 + 1e-5, 9))},
        "abs_vx_lt_0.2": frac(np.abs(vx) < 0.2),
        "abs_vx_in_(0,0.2)": frac((np.abs(vx) < 0.2) & (np.abs(vx) >= EPS)),
        "abs_vx_lt_0.2_with_planar_nonzero": frac((np.abs(vx) < 0.2) & ~pz),
        "forward_dominant": frac(~pz & (vx > 0) & (np.abs(vx) >= np.abs(vy))),
        "backward_dominant": frac(~pz & (vx < 0) & (np.abs(vx) >= np.abs(vy))),
        "lateral_dominant": frac(~pz & (np.abs(vy) > np.abs(vx))),
        "vx_negative": frac(vx < -EPS),
        "abs_wz": {b: frac((np.abs(wz) >= lo) & (np.abs(wz) < hi)) for b, lo, hi in (
            ("0", 0, EPS), ("(0,0.25)", EPS, 0.25), ("[0.25,0.5)", 0.25, 0.5), ("[0.5,1.0)", 0.5, 1.0), ("[1.0,1.5]", 1.0, 1.5 + 1e-5))},
    }
    near = {}
    for name, (cx, cy, cw) in {"stand": (0, 0, 0), "fwd01": (0.1, 0, 0), "fwd02": (0.2, 0, 0), "fwd03": (0.3, 0, 0), "fwd05": (0.5, 0, 0),
                               "back03": (-0.3, 0, 0), "left03": (0, 0.3, 0), "right03": (0, -0.3, 0), "yawL05": (0, 0, 0.5), "yawR05": (0, 0, -0.5)}.items():
        near[name] = frac((np.abs(vx - cx) <= 0.05) & (np.abs(vy - cy) <= 0.05) & (np.abs(wz - cw) <= 0.1))
    out["near_Q_cell_(lin+-0.05,wz+-0.1)"] = near
    return out


def hist1(v, lo, hi, w):
    edges = np.round(np.arange(lo, hi + w / 2, w), 6)
    h, _ = np.histogram(v, bins=edges)
    return {"edges": edges.tolist(), "frac": (h / v.size).round(5).tolist()}


S = {"tag": tag, "meta_ranges_after_warmup": meta["after_warmup"], "meta_end": meta["end"], "T": T, "N": N,
     "check_event_log_vs_commands": meta["event_log_vs_commands_every_step_max_abs"]}
# time-weighted (every env-step of the recorded window)
S["time_weighted_all"] = cats(vx, vy, wz)
S["time_weighted_by_terrain"] = {}
for i, t in enumerate(tnames):
    m = tidx == i
    if m.any():
        S["time_weighted_by_terrain"][t] = cats(vx[:, m], vy[:, m], wz[:, m])
S["hist_time_weighted"] = {"vx": hist1(vx.ravel(), -1.0, 1.0, 0.1), "vy": hist1(vy.ravel(), -1.0, 1.0, 0.1), "wz": hist1(wz.ravel(), -1.5, 1.5, 0.25)}
# events
k, env, buf, reason = ev[:, 0], ev[:, 1].astype(int), ev[:, 2], ev[:, 3].astype(int)
evx, evy, ewz = ev[:, 4], ev[:, 5], ev[:, 6]
S["events"] = {"n": int(len(ev)), "periodic": int((reason == 0).sum()), "reset_timeout": int((reason == 1).sum()), "reset_terminated": int((reason == 2).sum())}
rng = meta["after_warmup"]
vxr = np.array(rng["env_range_vx_unique"])
vmax = float(np.max(np.abs(vxr)))  # common planar bound after warm-up (all terrains share it in these runs)
vyr = np.array(rng["env_range_vy_unique"])
vymax = float(np.max(np.abs(vyr)))
S["events_by_reason"] = {}
for r, name in ((0, "periodic"), (1, "reset_timeout"), (2, "reset_terminated")):
    m = reason == r
    if not m.any():
        continue
    d = cats(evx, evy, ewz, m)
    d["vx_and_vy_both_at_+bound(+-1e-4)"] = frac((np.abs(evx - vmax) < 1e-4) & (np.abs(evy - vymax) < 1e-4), m)
    d["vx_at_bound_or_zero_and_vy_at_bound_or_zero(limit_vel signature)"] = frac(
        ((np.abs(np.abs(evx) - vmax) < 1e-4) | (np.abs(evx) < EPS)) & ((np.abs(np.abs(evy) - vymax) < 1e-4) | (np.abs(evy) < EPS)), m)
    d["episode_time_seen_by_sampler_s_quantiles"] = np.quantile(buf[m] * dt, [0, 0.1, 0.5, 0.9, 1]).round(3).tolist()
    S["events_by_reason"][name] = d
# periodic resample timing: episode time of periodic events, 1 s bins
m0 = reason == 0
h, e = np.histogram(buf[m0] * dt, bins=np.arange(0, 26, 1.0))
S["periodic_event_episode_time_hist_1s"] = {"edges": e.tolist(), "count": h.tolist()}
# gaps between consecutive periodic events of the same env (steps)
gaps = []
order = np.lexsort((k, env))
ks, es, rs = k[order], env[order], reason[order]
for i in range(1, len(ks)):
    if es[i] == es[i - 1] and rs[i] == 0:
        gaps.append(ks[i] - ks[i - 1])
g = np.array(gaps)
S["gap_between_events_same_env_steps"] = {"n": int(g.size), "unique_counts": {str(int(a)): int(b) for a, b in zip(*np.unique(g, return_counts=True))} if g.size and np.unique(g).size < 30 else None,
                                          "quantiles": np.quantile(g, [0, 0.1, 0.5, 0.9, 1]).tolist() if g.size else None}
# vel_low_bound: |vx|, |vy| of periodic events by episode time window
S["periodic_abs_vx_by_episode_time"] = {}
for lo, hi in ((0, 5), (5, 10), (10, 15), (15, 20), (20, 25.1)):
    m = m0 & (buf * dt >= lo) & (buf * dt < hi)
    if m.any():
        S["periodic_abs_vx_by_episode_time"][f"[{lo},{hi})"] = {"n": int(m.sum()), "abs_vx_lt_0.2": frac(np.abs(evx) < 0.2, m),
                                                                "abs_vx_median": float(np.median(np.abs(evx[m]))),
                                                                "planar_zero": frac(np.hypot(evx, evy) < EPS, m)}
json.dump(S, open(os.path.join(D, "summary.json"), "w"), indent=1)
print(json.dumps({k_: S[k_] for k_ in ("events", "check_event_log_vs_commands")}))
if "--expect_test" in sys.argv:
    ok = []
    ok.append(("all steps exactly (0.3, 0, 0.5)", bool((np.abs(vx - 0.3) < 1e-7).all() and (vy == 0).all() and (np.abs(wz - 0.5) < 1e-7).all())))
    ok.append(("all events exactly (0.3, 0, 0.5)", bool((np.abs(evx - 0.3) < 1e-7).all() and (evy == 0).all() and (np.abs(ewz - 0.5) < 1e-7).all())))
    tw = S["time_weighted_all"]
    ok.append(("time-weighted: planar speed [0.3,0.5) = 1, near fwd03 = 0", tw["planar_speed"]["[0.3,0.5)"] == 1.0 and tw["near_Q_cell_(lin+-0.05,wz+-0.1)"]["fwd03"] == 0.0))
    gu = S["gap_between_events_same_env_steps"]["unique_counts"] or {}
    ok.append(("periodic gap 50 or 51 steps (1 s at 0.02 s, float)", set(gu) <= {"50", "51"} and len(gu) > 0))
    ok.append(("event log reproduces commands every step", S["check_event_log_vs_commands"] == 0.0))
    for name, v in ok:
        print(("PASS " if v else "FAIL ") + name)
    S["test_checks"] = ok
    json.dump(S, open(os.path.join(D, "summary.json"), "w"), indent=1)
    sys.exit(0 if all(v for _, v in ok) else 1)
