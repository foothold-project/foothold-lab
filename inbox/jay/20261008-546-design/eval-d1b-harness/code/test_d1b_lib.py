# Known-answer tests for d1b_lib.py (CPU only). Every expected value below is written by hand from the
# rule text in VERIFY-astra-5.md, not computed with the function under test.
# Run: python test_d1b_lib.py   (writes out/d1b_cpu_tests.json)

import json
import math
import os
import sys

import numpy as np
import torch

import d1b_lib as L

DT = L.DT
RES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)))
    RES.append({"name": name, "pass": bool(cond), "detail": "" if cond else str(detail)})


# ---------------------------------------------------------------- 1/2. G0 raw stage and error classes
f32 = torch.float32
def S(z):  # one sensor at height z
    return torch.tensor([[0.0, 0.0, z]], dtype=f32)
def H(*zs):  # hits of one env
    return torch.tensor([[[0.0, 0.0, z] for z in zs]], dtype=f32)

inf = float("inf")
nan = float("nan")
leg = L.manager_clip_scale(L.legacy_raw_height(S(0.38), H(0.0, 0.10, inf, -inf, nan)))[0]
g0 = L.manager_clip_scale(L.g0_raw_height(S(0.38), H(0.0, 0.10, inf, -inf, nan)))[0]
check("flat 0.38 m: legacy and G0 final -0.30 (clip/scale once)", abs(leg[0] + 0.30) < 1e-6 and abs(g0[0] + 0.30) < 1e-6, (leg[0], g0[0]))
check("step +0.10 m: final -0.55 both", abs(leg[1] + 0.55) < 1e-6 and abs(g0[1] + 0.55) < 1e-6, (leg[1], g0[1]))
check("finite cells: G0 == legacy bitwise", bool(torch.equal(leg[:2], g0[:2])))
check("+inf no-hit: legacy -2.5, G0 +2.5", float(leg[2]) == -2.5 and float(g0[2]) == 2.5, (leg[2], g0[2]))
check("-inf hit: legacy +2.5 (clip), G0 +2.5", float(leg[3]) == 2.5 and float(g0[3]) == 2.5, (leg[3], g0[3]))
check("NaN hit: legacy NaN, G0 +2.5 (value only; flagged as error)", math.isnan(float(leg[4])) and float(g0[4]) == 2.5, (leg[4], g0[4]))
dbl = L.manager_clip_scale(L.manager_clip_scale(L.legacy_raw_height(S(0.38), H(0.0))))[0, 0]
check("negative control: clip/scale applied twice turns flat -0.30 into -0.75", abs(float(dbl) + 0.75) < 1e-6, dbl)

m = L.input_masks(S(0.38), H(0.0, inf, -inf, nan))
check("masks: +inf is the normal no-hit class only", m["hit_posinf_nohit"][0].tolist() == [False, True, False, False]
      and m["hit_neginf"][0].tolist() == [False, False, True, False] and m["hit_nan"][0].tolist() == [False, False, False, True]
      and not bool(m["pose_invalid"][0]) and not bool(m["finite_overflow"].any()), {k: v.tolist() for k, v in m.items()})
for bad in (nan, inf, -inf):
    m = L.input_masks(S(bad), H(0.0, 0.1))
    g = L.manager_clip_scale(L.g0_raw_height(S(bad), H(0.0, 0.1)))
    check(f"sensor z {bad}: pose_invalid set, finite hits not counted as no-hit, G0 value +2.5",
          bool(m["pose_invalid"][0]) and not bool(m["hit_posinf_nohit"].any()) and bool((g == 2.5).all()),
          ({k: v.tolist() for k, v in m.items()}, g.tolist()))
m = L.input_masks(S(3.0e38), H(-3.0e38))
check("finite inputs, overflow in sensor_z - hit_z: finite_overflow only", bool(m["finite_overflow"][0, 0])
      and not bool(m["hit_posinf_nohit"].any()) and not bool(m["pose_invalid"].any()), {k: v.tolist() for k, v in m.items()})

# ---------------------------------------------------------------- 6. contactless fall (ASTRA 10 + kept rules)
def ser(n):
    return np.arange(n) * DT

n = 60
t = ser(n)
r = L.gap_fall(np.full(n, 0.38), np.zeros(n), 0.0, local_all_miss=np.zeros(n, bool))
check("T1 z=+0.38 v=0 hits: no fall", r["j_fail"] == n and r["reason"] == "", r)
r = L.gap_fall(np.full(n, 0.38), np.zeros(n), 0.0, local_all_miss=np.ones(n, bool))
check("T2 same, all no-hit: no fall, all_local_miss counted separately", r["j_fail"] == n and r["all_local_miss_count"] == n, r)
zf, vf = 0.38 - 4.905 * t ** 2, -9.81 * t
r = L.gap_fall(zf, vf, 0.0, local_all_miss=np.ones(n, bool))
check("T3 free fall, all no-hit: detected at t=0.42 s", r["j_fail"] == 21 and abs(r["t_fail"] - 0.42) < 1e-9 and r["reason"] == "sink", r)
r = L.gap_fall(zf, vf, 0.0, local_all_miss=np.zeros(n, bool))
check("T4 free fall, some bank rays finite: detected at 0.42 s", r["j_fail"] == 21, r)
r = L.gap_fall(np.full(n, -0.60), np.zeros(n), 0.0)
check("T5 z=-0.60 v=0: immediate (deep)", r["j_fail"] == 0 and r["reason"] == "deep", r)
z = np.full(n, 0.38); v = np.zeros(n); z[10:15] = -0.11; v[10:15] = -0.21
r = L.gap_fall(z, v, 0.0)
check("T6 z=-0.11 vz=-0.21 for 0.08 s (5 samples): not detected", r["j_fail"] == n, r)
z = np.full(n, 0.38); v = np.zeros(n); z[10:16] = -0.11; v[10:16] = -0.21
r = L.gap_fall(z, v, 0.0)
check("T7 same for 0.10 s (6 samples): detected at the 6th sample", r["j_fail"] == 15, r)
tj = np.clip(t, 0, 0.30)
zj = np.where(t <= 0.30, 0.38 + 1.5 * tj - 4.905 * tj ** 2, 0.38 + 1.5 * 0.30 - 4.905 * 0.09)
vj = np.where(t <= 0.30, 1.5 - 9.81 * tj, 0.0)
miss = (t > 0.02) & (t < 0.30)
r = L.gap_fall(zj, vj, 0.0, local_all_miss=miss)
check("T8 jump and land at normal height, temporary no-hit: no fall", r["j_fail"] == n and r["all_local_miss_count"] == int(miss.sum())
      and zj.min() > 0.3, (r, zj.min()))
z9, v9 = zf.copy(), vf.copy()
z9[30:] = 0.38; v9[30:] = 0.0
r = L.gap_fall(z9, v9, 0.0)
check("T9 reset to normal height after detection: failure stays at 0.42 s", r["j_fail"] == 21, r)
o = L.gap_outcome(np.where(np.arange(n) < 30, 0.7, 3.0), np.zeros(n), r["j_fail"], [31, 31, 31, 31], 1.5, 0.2)
check("T9b outcome after the reset is still fall (no survival appended)", o["outcome"] == "fall" and o["j"] == 21, o)
zn = np.full(n, 0.38); zn[5] = nan
try:
    L.gap_fall(zn, np.zeros(n), 0.0)
    ok = False
except L.HarnessError:
    ok = True
check("T10 base NaN: harness error, not a trajectory", ok)
try:
    L.gap_fall(np.full(n, 0.38), np.where(np.arange(n) == 3, inf, 0.0), 0.0)
    ok = False
except L.HarnessError:
    ok = True
check("T10b world vz inf: harness error", ok)
bc = np.zeros(n, bool); bc[7] = True
r = L.gap_fall(np.full(n, 0.38), np.zeros(n), 0.0, base_contact=bc)
check("kept rule: base contact at sample 7", r["j_fail"] == 7 and r["reason"] == "base_contact", r)
gz = np.full(n, -1.0); gz[20:31] = -math.cos(math.radians(61))
r = L.gap_fall(np.full(n, 0.38), np.zeros(n), 0.0, grav_z=gz)
check("kept rule: tilt 61 deg for 0.20 s (11 samples) detected at the 11th", r["j_fail"] == 30 and r["reason"] == "tilt60", r)
gz = np.full(n, -1.0); gz[20:30] = -math.cos(math.radians(61))
r = L.gap_fall(np.full(n, 0.38), np.zeros(n), 0.0, grav_z=gz)
check("kept rule: tilt for 10 samples not detected", r["j_fail"] == n, r)
z = np.full(n, 0.38); v = np.zeros(n); z[10:20] = -0.05; v[10:20] = -0.5
r = L.gap_fall(z, v, 0.0)
check("z_ref-0.05 falling fast: not a fall (above z_ref-0.10)", r["j_fail"] == n, r)
z = np.full(n, 0.38); v = np.zeros(n); z[10:] = -0.30; v[10:] = -0.19
r = L.gap_fall(z, v, 0.0)
check("wedged at -0.30 with vz -0.19: not detected (documented gap of the rule)", r["j_fail"] == n, r)
r = L.gap_fall(np.full(n, 0.38 + 0.5), np.zeros(n), 0.5)
check("z_ref is an argument (bank top 0.5): standing at 0.88 no fall", r["j_fail"] == n, r)

# ---------------------------------------------------------------- 7. foot events, regions, margins
td, lo, ini = L.foot_events([0, 0, 5, 5, 5, 0, 0, 5, 0, 5, 5])
check("events: td at 2nd sample (3), liftoff at 6, single spike ignored, td at 10", td == [3, 10] and lo == [6] and ini == [], (td, lo, ini))
td, lo, ini = L.foot_events([5, 5, 5, 0, 0])
check("events: stance present at sample 0 is initial, not a landing", td == [] and ini == [1] and lo == [4], (td, lo, ini))
td, lo, ini = L.foot_events([0, 1.0, 1.0, 2, 2])
check("events: exactly 1 N is not > 1 N", td == [4], td)
td, lo, ini = L.foot_events([0, 5, 5, 0, 5, 5])
check("events: one-sample dropout is not a liftoff", td == [2] and lo == [], (td, lo))
a, w = 1.5, 0.2
reg = [str(L.region(x, y, a, w, 4.5)) for x, y in [(0, 0), (1.5, 0), (1.6, 0), (1.7, 0), (4.6, 0), (0, -1.6)]]
check("regions: inner, inner(lip), void, outer(lip), outside, void(y side)", reg == ["inner", "inner", "void", "outer", "outside", "void"], reg)
pts = [(1.40, 0.0, 0.10), (1.49, 0.3, 0.01), (1.60, 0.0, -0.10), (1.55, 0.0, -0.05), (1.75, 0.0, 0.05),
       (1.8, 1.8, math.hypot(0.1, 0.1)), (1.45, 1.45, 0.05), (1.6, 1.6, -0.1), (-1.75, 0.2, 0.05)]
got = [float(L.support_margin(x, y, a, w)) for x, y, _ in pts]
check("support margin to the outline (corners Euclidean)", all(abs(g - e) < 1e-9 for g, (_, _, e) in zip(got, pts)), got)
rk = [bool(L.risky(mm, 0.022)) for mm in (0.041, 0.043, 0.0, -0.01, 0.30)]
check("risky: margin-r < 0.02 (0.041 yes, 0.043 no, 0 yes, -0.01 yes, 0.30 no)", rk == [True, False, True, True, False], rk)
check("risky boundary exact: margin-r == 0.02 is not risky (strict <)", L.risky(0.375, 0.125, 0.25) == False and L.risky(0.37, 0.125, 0.25) == True)
check("error classes exclude the normal +inf no-hit", "hit_posinf_nohit" not in L.ERROR_KEYS and set(L.ERROR_KEYS) == {"pose_invalid", "hit_nan", "hit_neginf", "finite_overflow"}, L.ERROR_KEYS)
r = L.gap_fall(np.full(n, -0.5), np.zeros(n), 0.0)
check("deep boundary: z = z_ref-0.50 exactly is immediate (<=)", r["j_fail"] == 0 and r["reason"] == "deep", r)
cl = [L.classify_touchdown(*p, a, w, 4.5, 0.022) for p in [(1.0, 0, 0.022), (1.8, 0, 0.023), (1.6, 0, 0.022), (1.69, 0, -0.05), (1.8, 0, 0.10)]]
check("touchdown class: inner, outer, gap, wall below top, airborne other", cl == ["inner", "outer", "void_or_wall", "void_or_wall", "other"], cl)
sl = L.stance_slip(np.array([0, 0, 0.01, 0.03, 0.03]), np.zeros(5), [1], [3], 4)
check("slip: |p(lo) - p(td)| = 0.03", abs(sl[0] - 0.03) < 1e-12, sl)

# ---------------------------------------------------------------- 4. directions, cells, manifests
for al in (0, 45, 90, -45, -90):
    yaw, cmd = L.body_direction(al)
    vx, vy = L.world_velocity(yaw, cmd)
    check(f"direction {al}: world velocity (+0.30, 0)", abs(vx - 0.30) < 1e-12 and abs(vy) < 1e-12, (vx, vy, yaw, cmd))
yaw, cmd = L.body_direction(45)
check("45 deg: yaw -pi/4, body cmd (0.3/sqrt2, 0.3/sqrt2, 0)", abs(yaw + math.pi / 4) < 1e-12 and abs(cmd[0] - 0.3 / math.sqrt(2)) < 1e-12
      and abs(cmd[1] - 0.3 / math.sqrt(2)) < 1e-12 and cmd[2] == 0.0, (yaw, cmd))
c = L.cell_geometry(3.0, 0.30, 45)
check("validation 3.0/0.30/45: start 0.70, goal 2.60, scanner front 3.67 < 4.5",
      abs(c["start_x_nominal"] - 0.70) < 1e-12 and abs(c["goal_x"] - 2.60) < 1e-12 and c["inside_tile"]
      and abs(c["scanner_front_after_survival"] - (2.75 + 0.8 * math.cos(math.pi / 4) + 0.5 * math.sin(math.pi / 4))) < 1e-12, c)
c = L.cell_geometry(2.5, 0.25, -90)
check("holdout 2.5/0.25/-90: start 0.45 (half-width based), goal 2.30", abs(c["start_x_nominal"] - 0.45) < 1e-12
      and abs(c["goal_x"] - 2.30) < 1e-12 and abs(c["yaw"] - math.pi / 2) < 1e-12 and c["inside_tile"], c)
m1 = L.make_manifest(12000, range(1000, 1100), 17, 0, 17)
m2 = L.make_manifest(12000, range(1000, 1100), 17, 0, 17)
m3 = L.make_manifest(12000, [1005], 17, 0, 17)
mh = L.make_manifest(22000, range(2000, 2100), 17, 0, 17)
check("manifest deterministic (same seed, same ids)", L.sha(m1) == L.sha(m2))
check("manifest row depends only on (seed, id), not on the list", m3["rows"][0] == m1["rows"][5])
check("validation and holdout DR manifests differ", L.sha(m1["rows"]) != L.sha(mh["rows"]) and L.sha(m1["buckets"]) != L.sha(mh["buckets"]))
b = np.array(m1["buckets"])
dx = np.array([r["start_dx"] for r in m1["rows"]])
check("manifest ranges: dynamic <= static, dx in [-0.1, 0.1], lags 0..4", bool((b[:, 1] <= b[:, 0]).all()) and dx.min() >= -0.1
      and dx.max() <= 0.1 and set(r["delay_lag"] for r in m1["rows"]) <= set(range(5)), (dx.min(), dx.max()))

# ---------------------------------------------------------------- outcome
N = 1001
x = 0.7 + 0.3 * np.arange(N) * DT  # reaches 2.5 at j = 300
y = np.zeros(N)
o = L.gap_outcome(x, y, N, [250, 260, 270, 280], 1.5, 0.2)
check("outcome: reach 2.5 at j=300 with 4 outer touchdowns -> success at 325 (before leaving the tile at j=634)", o == {"outcome": "success", "j": 325}, o)
o = L.gap_outcome(x, y, N, [250, 260, 270, 340], 1.5, 0.2)
check("outcome: last outer touchdown at 340 -> success at 365", o == {"outcome": "success", "j": 365}, o)
o = L.gap_outcome(np.minimum(x, 3.0), y, N, [250, 260, 270, -1], 1.5, 0.2)
check("outcome: one foot never on the outer bank (base stops at 3.0) -> timeout", o["outcome"] == "timeout", o)
o = L.gap_outcome(x, y, 320, [250, 260, 270, 280], 1.5, 0.2)
check("outcome: fall at 320 inside the 0.5 s survival -> fall", o == {"outcome": "fall", "j": 320}, o)
y2 = y.copy(); y2[100:] = 0.31
o = L.gap_outcome(x, y2, N, [250, 260, 270, 280], 1.5, 0.2)
check("outcome: |y| 0.31 at j=100 -> path", o == {"outcome": "path", "j": 100}, o)
o = L.gap_outcome(0.7 + 1.8 / 990 * np.arange(N), y, N, [900, 900, 900, 900], 1.5, 0.2)
check("outcome: goal at j=990, survival would end after 20 s -> timeout", o["outcome"] == "timeout", o)

nf = sum(not r["pass"] for r in RES)
print()
print(f"{len(RES)} checks, {nf} failed")
os.makedirs("out", exist_ok=True)
json.dump({"n": len(RES), "failed": nf, "results": RES}, open(os.path.join("out", "d1b_cpu_tests.json"), "w"), indent=1)
sys.exit(1 if nf else 0)
