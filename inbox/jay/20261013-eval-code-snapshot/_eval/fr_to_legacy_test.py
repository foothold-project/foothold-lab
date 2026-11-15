# Known-answer tests of fr_to_legacy.py. Usage: python fr_to_legacy_test.py <converted dir of a flat tag> <full tag>
import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fr_to_legacy as F  # noqa: E402

res = {}
# 1. synthetic rows: start at (0, 0) facing +x; then 1 m ahead facing left (yaw 90); then 1 m left of start
names = list(np.genfromtxt(os.path.join(HERE, "out", "full", sys.argv[2], "episodes_summary.csv"), delimiter=",", names=True, dtype=None, encoding="utf-8").dtype.names)
src = [f for f in os.listdir(os.path.join(HERE, "out", "full", sys.argv[2])) if f.endswith(".csv") and f != "episodes_summary.csv"][0]
D0 = np.genfromtxt(os.path.join(HERE, "out", "full", sys.argv[2], src), delimiter=",", names=True)
D = D0[:3].copy()
for c in D.dtype.names:
    D[c] = 0.0
D["quat_w"] = 1.0
D["step"] = [0, 1, 2]
D["t_s"] = [0.0, 0.02, 0.04]
D["base_x_m"] = [0.0, 1.0, 0.0]
D["base_y_m"] = [0.0, 0.0, 1.0]
zc = "base_z_w_m" if "base_z_w_m" in D.dtype.names else "base_z_m"
D[zc] = [0.5, 0.6, 0.7]
c45 = math.cos(math.pi / 4)
D["quat_w"][1], D["quat_z"][1] = c45, c45
D["linvel_body_x_mps"] = [0.0, 0.3, 0.0]
D["linvel_body_y_mps"] = [0.0, 0.4, 0.0]
D["cmd_vx_mps"] = [0.0, 0.3, 0.0]
D["cmd_vy_mps"] = [0.0, 0.0, 0.0]
D["FL_foot_force_vertical_N"] = [30.0, 0.0, 0.0]
D["FL_foot_normal_force_horizontal_N"] = [40.0, 0.0, 0.0]
D["target_FL_hip_joint_rad"] = [0.11, 0.22, 0.33]
rows = F.convert_rows(D, floor_z=0.1)
r0, r1, r2 = rows
exp = {"r1.fwd_m": (r1["fwd_m"], 1.0), "r1.lat_m": (r1["lat_m"], 0.0), "r2.fwd_m": (r2["fwd_m"], 0.0), "r2.lat_m (left +)": (r2["lat_m"], 1.0),
       "r1.yaw_deg": (r1["yaw_deg"], 90.0), "r1.base_yaw_deg": (r1["base_yaw_deg"], 90.0), "r1.speed_mps": (r1["speed_mps"], 0.5),
       "r1.vel_err_mps": (r1["vel_err_mps"], 0.4), "r0.base_z_m (floor 0.1)": (r0["base_z_m"], 0.4), "r0.base_z_w_m": (r0["base_z_w_m"], 0.5),
       "r0.foot_contact_fl_n (3-4-5)": (r0["foot_contact_fl_n"], 50.0), "r1.joint_target_FL_hip (row 0 target)": (r1["joint_target_FL_hip_joint"], 0.11),
       "r2.joint_target_FL_hip (row 1 target)": (r2["joint_target_FL_hip_joint"], 0.22)}
res["synthetic"] = {k: [round(g, 6), e, abs(g - e) < 1e-5] for k, (g, e) in exp.items()}
res["synthetic"]["r0.joint_target empty"] = [r0["joint_target_FL_hip_joint"], None, r0["joint_target_FL_hip_joint"] is None]
# 2. real flat stand episode, converted: sum of contact force = m g; torque = Kp (joint_target - q) - Kd dq with the shift
import timeseries  # noqa: E402
CD = sys.argv[1]
summ = {r["file"]: r for r in csv.DictReader(open(os.path.join(HERE, "out", "full", sys.argv[2], "episodes_summary.csv"), encoding="utf-8"))}
st = np.load(os.path.join(HERE, "out", "full", sys.argv[2], "statics.npz"))
jn_term = [str(x) for x in st["joint_names"]]
out = []
for fn, s in summ.items():
    if s["cell"] != "stand":
        continue
    meta, R = timeseries.read(os.path.join(CD, "timeseries", fn[:-4] + ".parquet"))
    e = int(s["env"])
    w = [r for r in R if r["t_s"] >= 1.0]
    fz = np.array([sum(r[f"foot_contact_{sl}_n"] for sl in ("fl", "fr", "rl", "rr")) for r in w])
    kp = {j: st["kp"][e][jn_term.index(j)] for j in F.LAB_JOINT_ORDER}
    kd = {j: st["kd"][e][jn_term.index(j)] for j in F.LAB_JOINT_ORDER}
    tau = np.array([[r[f"joint_torque_{j}"] for j in F.LAB_JOINT_ORDER] for r in w])
    pred = np.array([[kp[j] * (r[f"joint_target_{j}"] - r[f"joint_pos_{j}"]) - kd[j] * r[f"joint_vel_{j}"] for j in F.LAB_JOINT_ORDER] for r in w])
    # unshifted (wrong) alignment for comparison: target of the action computed at the same row
    nxt = {r["frame"]: r for r in R}
    pred_wrong = np.array([[kp[j] * (nxt[r["frame"] + 1][f"joint_target_{j}"] - r[f"joint_pos_{j}"]) - kd[j] * r[f"joint_vel_{j}"]
                            for j in F.LAB_JOINT_ORDER] for r in w if r["frame"] + 1 in nxt])
    tau_w = tau[: len(pred_wrong)]
    out.append({"file": fn, "sum_contact_over_mg": round(float(fz.mean() / (float(s["robot_mass_kg"]) * 9.81)), 4),
                "torque_resid_median_Nm (shifted, as written)": round(float(np.median(np.abs(tau - pred))), 4),
                "torque_resid_median_Nm (unshifted)": round(float(np.median(np.abs(tau_w - pred_wrong))), 4),
                "columns_equal_lab_layout": list(timeseries.read(os.path.join(CD, "timeseries", fn[:-4] + ".parquet"))[1][0].keys()) == list(timeseries.columns_for(F.LAB_JOINT_ORDER))})
res["stand"] = out
# 2b. walking: the one-row shift of joint_target must fit the torque better than no shift (targets move fast)
walk = []
for fn, s in summ.items():
    if s["cell"] not in ("fwd05", "yawL05"):
        continue
    meta, R = timeseries.read(os.path.join(CD, "timeseries", fn[:-4] + ".parquet"))
    e = int(s["env"])
    kp = np.array([st["kp"][e][jn_term.index(j)] for j in F.LAB_JOINT_ORDER])
    kd = np.array([st["kd"][e][jn_term.index(j)] for j in F.LAB_JOINT_ORDER])
    g = lambda pre: np.array([[np.nan if r[pre + j] is None else r[pre + j] for j in F.LAB_JOINT_ORDER] for r in R])  # noqa: E731
    q, dq, tau, tg = g("joint_pos_"), g("joint_vel_"), g("joint_torque_"), g("joint_target_")
    a_ = slice(51, len(R) - 1)
    shifted = np.nanmedian(np.abs(tau[a_] - (kp * (tg[a_] - q[a_]) - kd * dq[a_])))
    unshifted = np.nanmedian(np.abs(tau[a_] - (kp * (tg[52:len(R)] - q[a_]) - kd * dq[a_])))
    walk.append({"file": fn, "resid_shifted_Nm": round(float(shifted), 3), "resid_unshifted_Nm": round(float(unshifted), 3),
                 "shift_better": bool(shifted < unshifted)})
res["walk_shift"] = walk
# 3. the fold-back check must fire on a wrong judged value (break the guard)
fn0 = next(f for f, s in summ.items() if s["cell"] == "fwd05")
s0 = dict(summ[fn0])
D1 = np.genfromtxt(os.path.join(HERE, "out", "full", sys.argv[2], fn0), delimiter=",", names=True)
meta_run = json.load(open(os.path.join(HERE, "out", sys.argv[2], "meta.json"), encoding="utf-8"))
cells = {c["name"]: c for c in meta_run["cells"]}
rows1 = F.convert_rows(D1, 0.0)
ok_true = all(c[4] for c in F.fold_back(rows1, cells["fwd05"], s0))
s0["mae_vx"] = str(float(s0["mae_vx"]) + 0.001)
fired = not all(c[4] for c in F.fold_back(rows1, cells["fwd05"], s0))
res["fold_back"] = {"true_values_pass": ok_true, "mae_vx_plus_0.001_detected": fired}
print(json.dumps(res, indent=1, ensure_ascii=False))
