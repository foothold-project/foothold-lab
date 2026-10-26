import json, sys, os
L = sys.argv[1]
for run in ("sb10_eval", "sb50_eval"):
    print("##", run)
    for m in ("m800","m900","m1000","m1100","m1200","m1300","m1400","m1500"):
        p = os.path.join(L, run, m, "map64", "map_modes.json")
        if not os.path.exists(p): print(m, "-"); continue
        d = json.load(open(p, encoding="utf-8"))["modes"]
        row = []
        for mode in ("eval_gt", "probe_prop_only"):
            v = d.get(mode)
            if not v: row.append("%s -" % mode); continue
            row.append("%s L %.3f/%d R %.3f/%d fwd1.0 %.3f/%d" % (mode[:4], v["spin+1.2"]["yaw_follow_median"], v["spin+1.2"]["alive_envs_at_end"], v["spin-1.2"]["yaw_follow_median"], v["spin-1.2"]["alive_envs_at_end"], v["fwd1.0"]["body_vx_integral_median_m"], v["fwd1.0"]["alive_envs_at_end"]))
        print(m, " | ".join(row))
