# Known-answer tests for the ASTRA 4 additions in q_metrics.py:
# time definitions n50 / span at their boundaries, proposal (a), Q2 split, stop diagnostics.
# Run: python test_q_metrics_v2.py

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


def trace_states(J, vx, vy=None, wz=None, tilt_deg=None, cmd=None, yaw0=0.0, term_at=None):
    """Arrays given per state j (length J+1). Position integrates the body velocity of state j."""
    vx = np.asarray(vx, float)
    vy = np.zeros(J + 1) if vy is None else np.asarray(vy, float)
    wz = np.zeros(J + 1) if wz is None else np.asarray(wz, float)
    yaw = np.zeros(J + 1)
    yaw[0] = yaw0
    pos = np.zeros((J + 1, 3))
    for j in range(1, J + 1):
        yaw[j] = yaw[j - 1] + wz[j] * DT
        c, s = math.cos(yaw[j]), math.sin(yaw[j])
        pos[j, 0] = pos[j - 1, 0] + (c * vx[j] - s * vy[j]) * DT
        pos[j, 1] = pos[j - 1, 1] + (s * vx[j] + c * vy[j]) * DT
    vb = np.stack([vx, vy, np.zeros(J + 1)], 1)
    wb = np.stack([np.zeros(J + 1), np.zeros(J + 1), wz], 1)
    tilt = np.zeros(J + 1) if tilt_deg is None else np.asarray(tilt_deg, float)
    term = np.zeros(J + 1, bool)
    if term_at is not None:
        term[term_at] = True
    return dict(pos=pos, yaw=(yaw + math.pi) % (2 * math.pi) - math.pi, vb=vb, wb=wb,
                grav_z=-np.cos(np.radians(tilt)), hag=np.full(J + 1, 0.3), term=term,
                cmd=np.asarray(cmd, float))


stop10 = {"kind": "stop", "duration_s": 10.0, "switch_s": 5.0}
lin20 = {"kind": "lin", "duration_s": 20.0, "switch_s": None}
J10, J20 = 500, 1000
cmd_stop = np.array([[0.3, 0, 0] if (j - 1) < 250 else [0, 0, 0] for j in range(J10 + 1)])


def stop_trace(still_from, still_len=None):
    """vx = 0.3 except states still_from .. still_from+still_len-1 (or to the end) where vx = 0."""
    vx = np.full(J10 + 1, 0.3)
    end = J10 + 1 if still_len is None else still_from + still_len
    vx[still_from:end] = 0.0
    return trace_states(J10, vx, cmd=cmd_stop)


def both(tr, cell):
    return Q.episode_metrics(cell, **tr, time_def="n50"), Q.episode_metrics(cell, **tr, time_def="span")


# 1 hold length: exactly 50 still samples (states 251..300) then moving again
a, b = both(stop_trace(251, 50), stop10)
check("50 still samples: n50 finds stop at 0.02 s", abs(a["stop_t"] - 0.02) < 1e-9, str(a["stop_t"]))
check("50 still samples: span finds no stop", not np.isfinite(b["stop_t"]), str(b["stop_t"]))
a, b = both(stop_trace(251, 51), stop10)
check("51 still samples: span finds stop at 0.02 s", abs(b["stop_t"] - 0.02) < 1e-9, str(b["stop_t"]))
check("51 still samples: n50 also stops", abs(a["stop_t"] - 0.02) < 1e-9)

# 2 start deadline j <= 300 (t = 6.00 s) for both definitions. Between the switch and the still
#   start the robot creeps at 0.06 m/s (not still, but only ~0.06 m) so the distance rule does not decide.


def creep_then_still(still_from):
    vx = np.full(J10 + 1, 0.3)
    vx[251:still_from] = 0.06
    vx[still_from:] = 0.0
    return trace_states(J10, vx, cmd=cmd_stop)


a, b = both(creep_then_still(300), stop10)
check("still from j=300: n50 stop_t 1.00, stop-only pass", abs(a["stop_t"] - 1.0) < 1e-9 and a["q2_stop_only"], str(a["stop_t"]))
check("still from j=300: span stop_t 1.00, stop-only pass", abs(b["stop_t"] - 1.0) < 1e-9 and b["q2_stop_only"], str(b["stop_t"]))
a, b = both(creep_then_still(301), stop10)
check("still from j=301: n50 stop_t 1.02 -> stop-only fail", abs(a["stop_t"] - 1.02) < 1e-9 and not a["q2_stop_only"], str(a["stop_t"]))
check("still from j=301: span stop_t 1.02 -> stop-only fail", abs(b["stop_t"] - 1.02) < 1e-9 and not b["q2_stop_only"], str(b["stop_t"]))

# 3 tilt hold: 10 tilted samples -> n50 fall, span not; 11 -> both fall
t10 = np.zeros(J20 + 1); t10[500:510] = 70.0
t11 = np.zeros(J20 + 1); t11[500:511] = 70.0
cmd_lin = np.tile([0.3, 0, 0], (J20 + 1, 1))
a, b = both(trace_states(J20, np.full(J20 + 1, 0.3), tilt_deg=t10, cmd=cmd_lin), lin20)
check("tilt 10 samples: n50 fall at 10.0 s", (not a["survived"]) and a["fall_reason"] == "tilt60" and abs(a["fall_t"] - 10.0) < 1e-9)
check("tilt 10 samples: span no fall", b["survived"], b["fall_reason"])
a, b = both(trace_states(J20, np.full(J20 + 1, 0.3), tilt_deg=t11, cmd=cmd_lin), lin20)
check("tilt 11 samples: both fall", (not a["survived"]) and (not b["survived"]))

# 4 proposal (a): MAE <= min(0.15, 0.5 |cmd|) on the commanded linear axis
cmd01 = np.tile([0.1, 0, 0], (J20 + 1, 1))
for v, want_q1, want_a, name in ((0.06, True, True, "0.06 under 0.1 (MAE 0.04)"),
                                 (0.04, True, False, "0.04 under 0.1 (MAE 0.06)"),
                                 (0.0, True, False, "standing under 0.1 (MAE 0.10)"),
                                 (0.15, True, True, "0.15 under 0.1 (MAE 0.05, boundary)")):
    m = Q.episode_metrics(lin20, **trace_states(J20, np.full(J20 + 1, v), cmd=cmd01))
    check(f"(a) {name}: q1 {want_q1}, q1a {want_a}", m["q1_pass"] == want_q1 and m["q1a_pass"] == want_a,
          f'{m["mae_vx"]} {m["q1_pass"]} {m["q1a_pass"]}')
cmd03 = np.tile([0.3, 0, 0], (J20 + 1, 1))
m = Q.episode_metrics(lin20, **trace_states(J20, np.full(J20 + 1, 0.16), cmd=cmd03))
check("(a) 0.16 under 0.3: MAE 0.14 passes both (bound min(0.15,0.15))", m["q1_pass"] and m["q1a_pass"])
cmdl = np.tile([0, 0.1, 0], (J20 + 1, 1))
m = Q.episode_metrics(lin20, **trace_states(J20, np.zeros(J20 + 1), vy=np.full(J20 + 1, 0.04), yaw0=-math.pi / 2, cmd=cmdl))
check("(a) lateral 0.04 under vy 0.1: q1a fail on the y axis", m["q1_pass"] and not m["q1a_pass"])

# 5 Q2 split over the full denominator
m = Q.episode_metrics(stop10, **stop_trace(260))
check("split: moved then stopped -> both_ok", m["q2_cat"] == "both_ok")
m = Q.episode_metrics(stop10, **stop_trace(320))
check("split: moved, stopped late -> stop_fail", m["q2_cat"] == "stop_fail")
m = Q.episode_metrics(stop10, **trace_states(J10, np.zeros(J10 + 1), cmd=cmd_stop))
check("split: never moved -> fwd_fail", m["q2_cat"] == "fwd_fail")

# 6 stop diagnostics: go 0.1 m forward then come back to the switch point -> max dev 0.1, net disp ~0
vx = np.full(J10 + 1, 0.3)
vx[251:276] = 0.2    # 25 samples x 0.2 x 0.02 = +0.10 m
vx[276:301] = -0.2   # back -0.10 m
vx[301:] = 0.0
m = Q.episode_metrics(stop10, **trace_states(J10, vx, cmd=cmd_stop))
check("diag: max excursion 0.10 m", abs(m["stop_max_dev_m"] - 0.10) < 1e-9, str(m["stop_max_dev_m"]))
check("diag: net displacement at stop ~0 (named stop_net_disp_m)", m["stop_net_disp_m"] < 1e-9, str(m["stop_net_disp_m"]))
check("diag: speed RMS = sqrt(50*0.04/250)", abs(m["stop_speed_rms"] - math.sqrt(50 * 0.04 / 250)) < 1e-9, str(m["stop_speed_rms"]))

# 7 auxiliary 0.10 s RMS does not cancel signed motion: +-0.1 alternating after the deadline
vx = np.full(J10 + 1, 0.3)
vx[251:] = 0.0
alt = np.where(np.arange(J10 + 1) % 2 == 0, 0.1, -0.1)
vx[301:] = alt[301:]
m = Q.episode_metrics(stop10, **trace_states(J10, vx, cmd=cmd_stop))
check("aux: alternating +-0.1 -> window RMS 0.1 (not ~0)", abs(m["aux10_speed_rms_max"] - 0.1) < 1e-9, str(m["aux10_speed_rms_max"]))
check("aux: still fraction 0 under alternating motion", m["aux10_still_frac"] == 0.0)
check("aux: Q2 n50 stop found inside 251..300? (still 50 samples 251..300) -> yes", abs(m["stop_t"] - 0.02) < 1e-9, str(m["stop_t"]))
m2 = Q.episode_metrics(stop10, **trace_states(J10, vx, cmd=cmd_stop), time_def="span")
check("aux: same trace under span -> 50 samples only -> no stop", not np.isfinite(m2["stop_t"]), str(m2["stop_t"]))

# 8 stop cell that falls before the switch: diagnostics are NaN, Q2 fails as fwd_fail, no crash
tr = stop_trace(400)
tr["term"][200] = True
m = Q.episode_metrics(stop10, **tr)
check("fell at 4 s in stop cell: q2_cat fwd_fail, diag NaN", m["q2_cat"] == "fwd_fail" and not np.isfinite(m["stop_max_dev_m"])
      and not m["q2_pass"], f'{m["q2_cat"]} {m["stop_max_dev_m"]}')

# 9 Holm step-down (sanity on known p-values)
r = Q.holm_reject([0.01, 0.04, 0.03, 0.005])
check("holm: 0.005<=0.0125, 0.01<=0.0167, 0.03>0.025 stop -> [T,F,F,T]", r == [True, False, False, True], str(r))
r = Q.holm_reject([0.2, 0.3])
check("holm: nothing rejected", r == [False, False])
r = Q.holm_reject([0.001] * 10)
check("holm: 10 x 0.001 all rejected (0.001 <= 0.005)", all(r))
sys.path.insert(0, ".")
print()
print(f"{len(FAILS)} failed" if FAILS else "all passed")
sys.exit(1 if FAILS else 0)
