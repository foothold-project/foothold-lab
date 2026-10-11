# CMD-R rollout test analysis: out/branch/cmdr_{off,on}/ -> out/branch/cmdr_summary.json
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "out", "branch")
EPS = 1e-6
S = {}
for arm in ("off", "on"):
    d = os.path.join(D, f"cmdr_{arm}")
    ev = np.load(os.path.join(d, "events.npy"))  # k, env, age, reason, lb, lb>hi, vx, vy, wz, time_left
    C = np.load(os.path.join(d, "cmd_steps.npy"))
    r = json.load(open(os.path.join(d, "result.json")))
    b = json.load(open(os.path.join(d, "bundle.json")))
    hi = 1.0
    out = {"n_events": int(len(ev)), "logs": r["rollout"]["logs_sum_or_last"], "adapter_calls": r["rollout"]["adapter_calls"],
           "terrain_level_mean_every_1s": r["rollout"]["terrain_level_mean_every_50"]}
    for code, name in ((0, "periodic"), (1, "reset_timeout"), (2, "reset_terminated"), (3, "branch_reset")):
        m = ev[:, 3] == code
        if not m.any():
            out[name] = {"n": 0}
            continue
        vx, vy = ev[m, 6], ev[m, 7]
        out[name] = {
            "n": int(m.sum()),
            "age_seen_by_sampler_unique_head": np.unique(ev[m, 2])[:5].tolist(),
            "lower_bound_gt_upper": int(ev[m, 5].sum()),
            "lower_bound_quantiles": np.quantile(ev[m, 4], [0, 0.5, 1]).round(4).tolist(),
            "both_planar_at_+bound": float(((np.abs(vx - hi) < 1e-4) & (np.abs(vy - hi) < 1e-4)).mean()),
            "both_planar_at_a_bound": float(((np.abs(np.abs(vx) - hi) < 1e-4) & (np.abs(np.abs(vy) - hi) < 1e-4)).mean()),
            "planar_zero": float((np.hypot(vx, vy) < EPS).mean()),
            "vx_negative": float((vx < 0).mean()),
            "planar_speed_lt_0.5_nonzero": float(((np.hypot(vx, vy) < 0.5) & (np.hypot(vx, vy) >= EPS)).mean()),
        }
    # time-weighted over the 30 s window
    vx, vy = C[..., 0], C[..., 1]
    out["time_weighted"] = {"both_at_+bound": float(((np.abs(vx - 1) < 1e-4) & (np.abs(vy - 1) < 1e-4)).mean()),
                            "planar_zero": float((np.hypot(vx, vy) < EPS).mean()),
                            "planar_lt_0.2_nonzero": float(((np.hypot(vx, vy) < 0.2) & (np.hypot(vx, vy) >= EPS)).mean()),
                            "full_stop": float(((np.hypot(vx, vy) < EPS) & (np.abs(C[..., 2]) < EPS)).mean())}
    out["timeout_events_vs_log"] = [int((ev[:, 3] == 1).sum()), out["logs"].get("Episode_Termination/time_out")]
    out["bundle_sha"] = b["state"]["sha"]
    out["bundle_obs_sha"] = b["state"]["obs_sha"]
    S[arm] = out
S["initial_state_equal_off_on"] = S["off"]["bundle_sha"] == S["on"]["bundle_sha"] and S["off"]["bundle_obs_sha"] == S["on"]["bundle_obs_sha"]
json.dump(S, open(os.path.join(D, "cmdr_summary.json"), "w"), indent=1)
for arm in ("off", "on"):
    o = S[arm]
    print(arm, "events", o["n_events"], "adapter calls", o["adapter_calls"], "time-out events vs log", o["timeout_events_vs_log"])
    for name in ("branch_reset", "reset_timeout", "reset_terminated", "periodic"):
        print("  ", name, o[name])
    print("   time-weighted", o["time_weighted"])
    print("   logs", o["logs"])
    print("   terrain level mean per s", [round(x, 3) for x in o["terrain_level_mean_every_1s"]][::5])
print("initial state equal off/on:", S["initial_state_equal_off_on"])
