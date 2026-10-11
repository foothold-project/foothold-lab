# Known-answer tests for q_metrics.py. Run: python test_q_metrics.py
# Every case builds a synthetic trace whose correct metric value is known
# by construction, then checks the function output against it.

import math
import sys

import numpy as np

import q_metrics as Q

DT = Q.DT
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + detail))
    if not cond:
        FAILS.append(name)


def trace(duration_s, vx_fn, vy_fn=lambda t: 0.0, wz_fn=lambda t: 0.0, yaw0=0.0, cmd=(0, 0, 0),
          cmd_fn=None, tilt_deg_fn=lambda t: 0.0, hag_fn=lambda t: 0.3, term_at=None):
    J = int(round(duration_s / DT))
    t = np.arange(J + 1) * DT
    vb = np.zeros((J + 1, 3))
    wb = np.zeros((J + 1, 3))
    vb[:, 0] = [vx_fn(x) for x in t]
    vb[:, 1] = [vy_fn(x) for x in t]
    wb[:, 2] = [wz_fn(x) for x in t]
    yaw = np.zeros(J + 1)
    yaw[0] = yaw0
    pos = np.zeros((J + 1, 3))
    for j in range(1, J + 1):
        # state j reached by integrating the velocity of state j (explicit, simple)
        yaw[j] = yaw[j - 1] + wb[j, 2] * DT
        c, s = math.cos(yaw[j]), math.sin(yaw[j])
        pos[j, 0] = pos[j - 1, 0] + (c * vb[j, 0] - s * vb[j, 1]) * DT
        pos[j, 1] = pos[j - 1, 1] + (s * vb[j, 0] + c * vb[j, 1]) * DT
    yaw_wrapped = (yaw + math.pi) % (2 * math.pi) - math.pi
    grav_z = -np.cos(np.radians([tilt_deg_fn(x) for x in t]))
    hag = np.array([hag_fn(x) for x in t])
    term = np.zeros(J + 1, dtype=bool)
    if term_at is not None:
        term[int(round(term_at / DT))] = True
    if cmd_fn is None:
        cmdarr = np.tile(np.array(cmd, dtype=float), (J + 1, 1))
    else:
        cmdarr = np.array([cmd_fn(x) for x in t], dtype=float)
    return dict(pos=pos, yaw=yaw_wrapped, vb=vb, wb=wb, grav_z=grav_z, hag=hag, term=term, cmd=cmdarr)


def run(cell, tr):
    return Q.episode_metrics(cell, **tr)


lin20 = {"kind": "lin", "duration_s": 20.0, "switch_s": None}
yaw20 = {"kind": "yaw", "duration_s": 20.0, "switch_s": None}
stop10 = {"kind": "stop", "duration_s": 10.0, "switch_s": 5.0}

# 1 perfect forward tracking: MAE 0, gate at 4.0/0.3 s, corridor 0
m = run(lin20, trace(20, lambda t: 0.3, cmd=(0.3, 0, 0)))
check("perfect vx: mae 0", abs(m["mae_vx"]) < 1e-12 and abs(m["mae_vy"]) < 1e-12 and abs(m["mae_wz"]) < 1e-12)
check("perfect vx: q1 pass", m["q1_pass"])
check("perfect vx: gate 13.34 s", abs(m["gate_t"] - 13.34) < 1e-9, str(m["gate_t"]))
check("perfect vx: corridor 0", m["corridor_max_m"] < 1e-12)
check("perfect vx: q3 pass", m["q3_pass"])
check("perfect vx: progress 6.0", abs(m["progress_m"] - 6.0) < 1e-9, str(m["progress_m"]))

# 2 constant +0.2 offset: MAE 0.2 -> fail. Offset +0.14 -> pass (threshold side)
m = run(lin20, trace(20, lambda t: 0.5, cmd=(0.3, 0, 0)))
check("offset 0.2: mae 0.2", abs(m["mae_vx"] - 0.2) < 1e-12, str(m["mae_vx"]))
check("offset 0.2: q1 fail", not m["q1_pass"])
m = run(lin20, trace(20, lambda t: 0.44, cmd=(0.3, 0, 0)))
check("offset 0.14: q1 pass", m["q1_pass"], str(m["mae_vx"]))

# 3 first 1 s excluded: huge error before 1.0 s does not count
m = run(lin20, trace(20, lambda t: 3.0 if t < 0.999 else 0.3, cmd=(0.3, 0, 0)))
check("first 1 s excluded", abs(m["mae_vx"]) < 1e-12, str(m["mae_vx"]))

# 4 backward and lateral: path frame follows the command direction, any start yaw
m = run(lin20, trace(20, lambda t: -0.3, yaw0=math.pi, cmd=(-0.3, 0, 0)))
check("backward: progress +6", abs(m["progress_m"] - 6.0) < 1e-9, str(m["progress_m"]))
m = run(lin20, trace(20, lambda t: 0.0, vy_fn=lambda t: 0.3, yaw0=-math.pi / 2, cmd=(0, 0.3, 0)))
check("lateral +y: progress +6", abs(m["progress_m"] - 6.0) < 1e-9, str(m["progress_m"]))
check("lateral +y: q1 pass", m["q1_pass"])
m = run(lin20, trace(20, lambda t: 0.3, vy_fn=lambda t: 0.0, yaw0=1.0, cmd=(0, 0.3, 0)))
check("moving forward under +y cmd: progress ~0, corridor 6", abs(m["progress_m"]) < 1e-9 and abs(m["corridor_max_m"] - 6.0) < 1e-9,
      f'{m["progress_m"]} {m["corridor_max_m"]}')
check("moving forward under +y cmd: q1 fail", not m["q1_pass"])

# 5 corridor: steady 0.25 m/s lateral drift during forward walk -> corridor > 0.30 before gate
m = run(lin20, trace(20, lambda t: 0.3, vy_fn=lambda t: 0.025, cmd=(0.3, 0, 0)))
check("drift 0.025 m/s: q1 pass (mae_vy 0.025)", m["q1_pass"])
check("drift: corridor ~0.333 at gate", 0.30 < m["corridor_max_m"] < 0.36, str(m["corridor_max_m"]))
check("drift: q3 fail", not m["q3_pass"])

# 6 yaw tracking and heading wrap
m = run(yaw20, trace(20, lambda t: 0.0, wz_fn=lambda t: 0.5, cmd=(0, 0, 0.5)))
check("yaw 0.5: mae 0", abs(m["mae_wz"]) < 1e-12)
check("yaw 0.5: heading err ~0 across wraps", abs(m["heading_err_rad"]) < 1e-9, str(m["heading_err_rad"]))
m = run(yaw20, trace(20, lambda t: 0.0, wz_fn=lambda t: 0.25, cmd=(0, 0, 0.5)))
check("yaw half speed: mae 0.25 -> fail", abs(m["mae_wz"] - 0.25) < 1e-12 and not m["q1_pass"])
check("yaw half speed: heading err -0.25*19.02", abs(m["heading_err_rad"] + 0.25 * 19.02) < 1e-6, str(m["heading_err_rad"]))

# 7 falls
m = run(lin20, trace(20, lambda t: 0.3, cmd=(0.3, 0, 0), term_at=7.0))
check("termination at 7 s: not survived, reason base_contact", (not m["survived"]) and m["fall_reason"] == "base_contact"
      and abs(m["fall_t"] - 7.0) < 1e-9)
check("termination: q1 fail even with perfect tracking", not m["q1_pass"])
m = run(lin20, trace(20, lambda t: 0.3, cmd=(0.3, 0, 0), tilt_deg_fn=lambda t: 70.0 if 5.0 <= t < 5.18 else 0.0))
check("tilt 70 deg for 0.18 s: no fall", m["survived"], m["fall_reason"])
m = run(lin20, trace(20, lambda t: 0.3, cmd=(0.3, 0, 0), tilt_deg_fn=lambda t: 70.0 if 5.0 <= t < 5.2 else 0.0))
check("tilt 70 deg for 0.20 s: fall tilt60 at 5.0", (not m["survived"]) and m["fall_reason"] == "tilt60"
      and abs(m["fall_t"] - 5.0) < 1e-9, f'{m["fall_reason"]} {m["fall_t"]}')
m = run(lin20, trace(20, lambda t: 0.3, cmd=(0.3, 0, 0), tilt_deg_fn=lambda t: 55.0))
check("tilt 55 deg all along: no fall", m["survived"])
m = run(lin20, trace(20, lambda t: 0.3, cmd=(0.3, 0, 0), hag_fn=lambda t: -0.01 if t >= 9.0 else 0.3))
check("base below support at 9 s: fall", (not m["survived"]) and m["fall_reason"] == "below_support")

# 8 stop: exponential decay with tau. still when 0.3 exp(-(t-5)/tau) < 0.05
tau = 0.2


def v_stop(t):
    return 0.3 if t <= 5.0 else 0.3 * math.exp(-(t - 5.0) / tau)


m = run(stop10, trace(10, v_stop, cmd_fn=lambda t: (0.3, 0, 0) if t <= 5.0 else (0, 0, 0)))
t_expect = math.ceil(tau * math.log(0.3 / 0.05) / DT - 1e-9) * DT
check("stop tau 0.2: stop_t", abs(m["stop_t"] - t_expect) < 1e-9, f'{m["stop_t"]} vs {t_expect}')
# distance: explicit sum of v over states 251..j_stop times DT
js = int(round(5.0 / DT)) + int(round(t_expect / DT))
d_expect = sum(v_stop(j * DT) for j in range(251, js + 1)) * DT
check("stop tau 0.2: stop_dist", abs(m["stop_dist_m"] - d_expect) < 1e-9, f'{m["stop_dist_m"]} vs {d_expect}')
check("stop tau 0.2: q2 pass", m["q2_pass"] and m["q2_stop_only"])
# slow stop: tau 1.0 -> still only after 1.79 s -> fail
m = run(stop10, trace(10, lambda t: 0.3 if t <= 5.0 else 0.3 * math.exp(-(t - 5.0) / 1.0),
                      cmd_fn=lambda t: (0.3, 0, 0) if t <= 5.0 else (0, 0, 0)))
check("stop tau 1.0: stop_t > 1 -> q2 fail", m["stop_t"] > 1.0 and not m["q2_pass"], str(m["stop_t"]))
# yaw spin after stop: planar still, yaw rate 0.15 -> never still
m = run(stop10, trace(10, lambda t: 0.3 if t <= 5.0 else 0.0, wz_fn=lambda t: 0.15 if t > 5.0 else 0.0,
                      cmd_fn=lambda t: (0.3, 0, 0) if t <= 5.0 else (0, 0, 0)))
check("stop with yaw spin 0.15: no stop", not np.isfinite(m["stop_t"]) and not m["q2_pass"])
# incomplete hold window at the end (still only for the last 0.5 s) -> no stop
m = run(stop10, trace(10, lambda t: 0.3 if t < 9.5 else 0.0, cmd_fn=lambda t: (0.3, 0, 0) if t <= 5.0 else (0, 0, 0)))
check("still only last 0.5 s: no stop", not np.isfinite(m["stop_t"]))
# zero-action like trace: never moved. stop-only passes, q2 (with moving precondition) fails
m = run(stop10, trace(10, lambda t: 0.0, cmd_fn=lambda t: (0.3, 0, 0) if t <= 5.0 else (0, 0, 0)))
check("never moved: q2_stop_only True but q2 False", m["q2_stop_only"] and not m["q2_pass"])

# 8b auxiliary move check (LEAD_TEMP): standing still under vx=0.1 passes Q1 but not q1m
m = run(lin20, trace(20, lambda t: 0.0, cmd=(0.1, 0, 0)))
check("stand under vx 0.1: q1 pass (Q blind spot)", m["q1_pass"], str(m["mae_vx"]))
check("stand under vx 0.1: q1m fail", not m["q1m_pass"] and abs(m["move_ratio"]) < 1e-12)
m = run(lin20, trace(20, lambda t: 0.06, cmd=(0.1, 0, 0)))
check("0.06 under vx 0.1: move ratio 0.6, q1m pass", abs(m["move_ratio"] - 0.6) < 1e-9 and m["q1m_pass"], str(m["move_ratio"]))
m = run(lin20, trace(20, lambda t: -0.05, yaw0=math.pi, cmd=(-0.1, 0, 0)))
check("backward 0.05 under vx -0.1: move ratio 0.5 (boundary pass)", abs(m["move_ratio"] - 0.5) < 1e-9 and m["q1m_pass"],
      str(m["move_ratio"]))
m = run(yaw20, trace(20, lambda t: 0.0, wz_fn=lambda t: 0.3, cmd=(0, 0, 0.5)))
check("yaw 0.3 under 0.5: ratio 0.6, mae 0.2 -> q1 boundary", abs(m["move_ratio"] - 0.6) < 1e-9, str(m["move_ratio"]))
m = run(stop10, trace(10, lambda t: 0.0, cmd_fn=lambda t: (0.3, 0, 0) if t <= 5.0 else (0, 0, 0)))
check("stop cell never moved: move ratio 0", abs(m["move_ratio"]) < 1e-12)
# heading drift: body speed exact, heading turns 0.05 rad/s -> move ratio 1, world progress < 6, drift ~0.95 rad
m = run(lin20, trace(20, lambda t: 0.3, wz_fn=lambda t: 0.05, cmd=(0.3, 0, 0)))
check("heading drift: move ratio 1.0", abs(m["move_ratio"] - 1.0) < 1e-9, str(m["move_ratio"]))
check("heading drift: world progress < 6, corridor > 0.3", m["progress_m"] < 5.9 and m["corridor_max_m"] > 0.3,
      f'{m["progress_m"]} {m["corridor_max_m"]}')
check("heading drift: heading_err 0.05*19.02", abs(m["heading_err_rad"] - 0.05 * 19.02) < 1e-6, str(m["heading_err_rad"]))
check("heading drift: q1 pass (mae_wz 0.05), q3 fail", m["q1_pass"] and not m["q3_pass"])

# 9 statistics
lo, hi = Q.wilson(95, 100)
check("wilson 95/100", abs(lo - 0.8883) < 5e-4 and abs(hi - 0.9785) < 5e-4, f"{lo} {hi}")
lo, hi = Q.wilson(0, 100)
check("wilson 0/100 upper 0.037", lo == 0.0 and abs(hi - 0.0370) < 5e-4, f"{lo} {hi}")
check("mcnemar b=10 c=0", abs(Q.mcnemar_exact(10, 0) - 2 * 0.5 ** 10) < 1e-12)
check("mcnemar b=c", Q.mcnemar_exact(5, 5) == 1.0)
d, l, u = Q.newcombe_paired(50, 0, 0, 50)
check("newcombe identical: diff 0, interval contains 0", d == 0 and l <= 0 <= u, f"{d} {l} {u}")

# Newcombe coverage by simulation: correlated pairs, n=100
rng = np.random.default_rng(0)
cover = 0
reps = 4000
p1t, p2t, rho_hit = 0.85, 0.75, 0.6
for _ in range(reps):
    z = rng.random(100)
    both = z < rho_hit * min(p1t, p2t)
    x1 = both | (rng.random(100) < (p1t - rho_hit * min(p1t, p2t)) / (1 - rho_hit * min(p1t, p2t)))
    x2 = both | (rng.random(100) < (p2t - rho_hit * min(p1t, p2t)) / (1 - rho_hit * min(p1t, p2t)))
    a = int(np.sum(x1 & x2)); b = int(np.sum(x1 & ~x2)); c = int(np.sum(~x1 & x2)); dd = int(np.sum(~x1 & ~x2))
    _, l, u = Q.newcombe_paired(a, b, c, dd)
    cover += l <= (p1t - p2t) <= u
cov = cover / reps
check("newcombe coverage ~0.95 (0.93..0.975)", 0.93 <= cov <= 0.975, str(cov))

print()
print(f"{len(FAILS)} failed" if FAILS else "all passed")
sys.exit(1 if FAILS else 0)
