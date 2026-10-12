# Checks of a full-record directory against its run: python fr_check.py <tag>
#  1 CSV vs traj.npz / cmd_hist (same states, same commands)
#  2 action -> target = offset + 0.25 x action
#  3 known answers: standing (flat stand cell): sum of foot vertical forces = robot mass x g, all four feet in contact,
#    applied torque = Kp (target - q) - Kd dq within the actuator friction; walking on flat: feet in contact sit at the
#    sphere radius above the ground, lifted feet are higher, duty factor between 0.2 and 0.9
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
tag = sys.argv[1]
FD = os.path.join(HERE, "out", "full", tag)
RD = os.path.join(HERE, "out", tag)
z = np.load(os.path.join(RD, "traj.npz"))
traj, cmd_hist = z["traj"], z["cmd_hist"]
st = np.load(os.path.join(FD, "statics.npz"))
summ = list(csv.DictReader(open(os.path.join(FD, "episodes_summary.csv"), encoding="utf-8")))
FEET = ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
res = {"files": len(summ)}
worst = 0.0
for s in summ:
    D = np.genfromtxt(os.path.join(FD, s["file"]), delimiter=",", names=True)
    e, n = int(s["env"]), len(D)
    tr = traj[:n, e]
    zc = "base_z_w_m" if "base_z_w_m" in D.dtype.names else "base_z_m"  # renamed 2026-10-12 (lab name)
    pairs = [("base_x_m", tr[:, 0]), ("base_y_m", tr[:, 1]), (zc, tr[:, 2]), ("linvel_body_x_mps", tr[:, 4]), ("linvel_body_y_mps", tr[:, 5]),
             ("angvel_body_z_radps", tr[:, 9]), ("gravity_body_z", tr[:, 10]), ("base_height_above_ground_m", tr[:, 11]),
             ("cmd_vx_mps", cmd_hist[:n, e, 0]), ("cmd_vy_mps", cmd_hist[:n, e, 1]), ("cmd_wz_radps", cmd_hist[:n, e, 2])]
    for col, ref in pairs:
        d = np.abs(D[col] - ref) / np.maximum(1.0, np.abs(ref))
        worst = max(worst, float(np.nanmax(d)))
res["csv_vs_traj_max_rel_diff"] = worst
jn = [str(x) for x in st["joint_names"]]
# 2 target = offset + 0.25 action
tmax = 0.0
for s in summ:
    D = np.genfromtxt(os.path.join(FD, s["file"]), delimiter=",", names=True)
    e = int(s["env"])
    a = np.stack([D[f"action_{j}"] for j in jn], 1)
    tg = np.stack([D[f"target_{j}_rad"] for j in jn], 1)
    ok = np.isfinite(a).all(1)
    tmax = max(tmax, float(np.abs(tg[ok] - (st["offset"][e] + 0.25 * np.clip(a[ok], -100, 100))).max()))
res["target_minus_offset_plus_scaled_action_max_abs"] = tmax
# 3 known answers
ka = {}
stand = [s for s in summ if s["family"] == "flat" and s["cell"] == "stand"]
if stand:
    ratios, contact, slope, resid, tau_abs = [], [], [], [], []
    for s in stand:
        D = np.genfromtxt(os.path.join(FD, s["file"]), delimiter=",", names=True)
        e = int(s["env"])
        w = D["t_s"] >= 1.0
        fz = sum(D[f"{f}_force_vertical_N"] for f in FEET)
        ratios.append(float(np.mean(fz[w]) / (float(s["robot_mass_kg"]) * 9.81)))
        contact.append(float(np.mean([D[f"{f}_contact"][w].mean() for f in FEET])))
        q = np.stack([D[f"q_{j}_rad"] for j in jn], 1)
        dq = np.stack([D[f"dq_{j}_radps"] for j in jn], 1)
        tau = np.stack([D[f"tau_{j}_Nm"] for j in jn], 1)
        tg = np.stack([D[f"target_{j}_rad"] for j in jn], 1)
        kp, kd = st["kp"][e], st["kd"][e]
        pred = kp * (tg[:-1] - q[1:]) - kd * dq[1:]  # torque of row k comes from the action of row k-1
        tt = tau[1:]
        ww = w[1:]
        A = np.vstack([pred[ww].ravel(), np.ones(pred[ww].size)]).T
        sl, ic = np.linalg.lstsq(A, tt[ww].ravel(), rcond=None)[0]
        slope.append(float(sl))
        resid.append(float(np.median(np.abs(tt[ww] - pred[ww]))))
        tau_abs.append(float(np.median(np.abs(tt[ww]))))
    ka["stand_sum_vertical_force_over_mg"] = [round(min(ratios), 4), round(max(ratios), 4)]
    ka["stand_contact_fraction"] = [round(min(contact), 4), round(max(contact), 4)]
    ka["stand_torque_vs_pd_slope"] = [round(min(slope), 4), round(max(slope), 4)]
    ka["stand_torque_minus_pd_median_abs_Nm"] = [round(min(resid), 4), round(max(resid), 4)]
    ka["stand_torque_median_abs_Nm"] = [round(min(tau_abs), 3), round(max(tau_abs), 3)]
walk = [s for s in summ if s["family"] == "flat" and s["cell"] in ("fwd03", "fwd05", "back03")]
if walk:
    zc, zs, duty = [], [], []
    for s in walk:
        D = np.genfromtxt(os.path.join(FD, s["file"]), delimiter=",", names=True)
        w = D["t_s"] >= 1.0
        for f in FEET:
            c = D[f"{f}_contact"][w] > 0.5
            fz_ = D[f"{f}_z_m"][w] - D["ground_z_m"][w]
            if c.any():
                zc.append(float(np.median(fz_[c])))
            if (~c).any():
                zs.append(float(np.median(fz_[~c])))
            duty.append(float(c.mean()))
    ka["walk_foot_height_in_contact_median_m"] = [round(min(zc), 4), round(max(zc), 4)]
    ka["walk_foot_height_lifted_median_m"] = [round(min(zs), 4), round(max(zs), 4)]
    ka["walk_duty_factor"] = [round(min(duty), 3), round(max(duty), 3)]
res["known_answers"] = ka
json.dump(res, open(os.path.join(FD, "checks.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
