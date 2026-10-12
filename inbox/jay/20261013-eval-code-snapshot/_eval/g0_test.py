# CPU fixture for G0 (answer-known synthetic ray hits). Run: python g0_test.py
# Cases: flat, steps up/down, tall wall, deep finite hole (height-field hole), no-hit (inf), NaN,
# all-invalid. Pass rules from DESIGN 4 G0: finite-hit outputs of legacy and G0 differ <= 1e-6,
# no-hit final output +2.5 under G0, zero non-finite outputs under G0. The legacy outputs are
# printed to show the inversion (no-hit encoded like a tall wall).

import json
import math
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g0_encoding as G  # noqa: E402

LAB = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/sim/eval"
FAILS = []
REC = {}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + detail))
    if not cond:
        FAILS.append(name)


inf, nan = float("inf"), float("nan")
base = torch.tensor([0.38])  # base 0.38 m above a ground at z = 0
cases = {
    "flat": [0.0, 0.0, 0.0],
    "step_up_0.2": [0.2, 0.2, 0.0],
    "step_down_0.2": [-0.2, -0.2, 0.0],
    "wall_1.0": [1.0, 1.0, 0.0],
    "deep_finite_hole_-10": [-10.0, -10.0, 0.0],
    "no_hit_inf": [inf, inf, 0.0],
    "nan": [nan, nan, 0.0],
    "all_invalid_inf": [inf, inf, inf],
    "all_invalid_nan": [nan, nan, nan],
    "minus_inf": [-inf, 0.0, 0.0],
}
for name, z in cases.items():
    hz = torch.tensor([z], dtype=torch.float32)
    L = G.legacy_encode(base, hz)[0]
    N = G.g0_encode(base, hz)[0]
    REC[name] = {"hit_z": [str(v) for v in z], "legacy": [float(v) for v in L], "g0": [float(v) for v in N],
                 "cause": G.classify(hz)[0].tolist()}
    print(f"{name:22s} hit_z {z}  legacy {[round(float(v), 4) for v in L]}  g0 {[round(float(v), 4) for v in N]}")

# expected values by hand: h = 0.38 - z - 0.5
check("flat: -0.12 * 2.5 = -0.3 (both)", abs(REC["flat"]["legacy"][0] + 0.3) < 1e-6 and abs(REC["flat"]["g0"][0] + 0.3) < 1e-6)
check("step up 0.2: h -0.32 -> -0.8", abs(REC["step_up_0.2"]["g0"][0] + 0.8) < 1e-6)
check("step down 0.2: h 0.08 -> 0.2", abs(REC["step_down_0.2"]["g0"][0] - 0.2) < 1e-6)
check("wall 1.0: h -1.12 -> clip -1 -> -2.5", abs(REC["wall_1.0"]["g0"][0] + 2.5) < 1e-6)
check("deep finite hole: h 9.88 -> clip 1 -> +2.5", abs(REC["deep_finite_hole_-10"]["g0"][0] - 2.5) < 1e-6)
# rule 1: finite hits identical
fin_diff = 0.0
for name in ("flat", "step_up_0.2", "step_down_0.2", "wall_1.0", "deep_finite_hole_-10"):
    fin_diff = max(fin_diff, max(abs(a - b) for a, b in zip(REC[name]["legacy"], REC[name]["g0"])))
for name in ("no_hit_inf", "nan"):
    fin_diff = max(fin_diff, abs(REC[name]["legacy"][2] - REC[name]["g0"][2]))
check("rule 1: finite-hit outputs legacy vs G0 max diff <= 1e-6", fin_diff <= 1e-6, str(fin_diff))
# rule 2: no-hit final output +2.5 under G0
check("rule 2: no-hit (inf) -> G0 +2.5", REC["no_hit_inf"]["g0"][:2] == [2.5, 2.5])
check("rule 2: all invalid inf -> G0 all +2.5", REC["all_invalid_inf"]["g0"] == [2.5, 2.5, 2.5])
# rule 3: no non-finite output under G0
allg0 = [v for r in REC.values() for v in r["g0"]]
check("rule 3: G0 non-finite outputs = 0", sum(not math.isfinite(v) for v in allg0) == 0)
# the inversion under legacy
check("legacy: no-hit encodes exactly like a tall wall (-2.5)", REC["no_hit_inf"]["legacy"][0] == REC["wall_1.0"]["legacy"][0] == -2.5)
check("legacy: no-hit is the opposite sign of a deep finite hole (+2.5)", REC["deep_finite_hole_-10"]["legacy"][0] == 2.5)
nanleg = [v for v in REC["nan"]["legacy"][:2] + REC["all_invalid_nan"]["legacy"]]
check("legacy: NaN hits pass through as NaN outputs", all(math.isnan(v) for v in nanleg))
check("G0: NaN -> +2.5 (counted as cause NaN, not inf)", REC["nan"]["g0"][:2] == [2.5, 2.5] and REC["nan"]["cause"][:2] == [2, 2])
check("-inf hit (not produced by the ray caster): both +2.5", REC["minus_inf"]["legacy"][0] == 2.5 and REC["minus_inf"]["g0"][0] == 2.5)

# cross-check with the lab reference implementation (torch only, no Isaac import)
sys.path.insert(0, LAB)
import gap_observations as ref  # noqa: E402


class _D:  # minimal fake env exposing env.scene.sensors[name].data.{pos_w, ray_hits_w}
    pass


hz = torch.tensor([[0.0, 0.2, -0.2, 1.0, -10.0, inf, nan, -inf]])
env = _D(); env.scene = _D(); s = _D(); s.data = _D()
s.data.pos_w = torch.tensor([[0.0, 0.0, 0.38]])
s.data.ray_hits_w = torch.stack([torch.zeros_like(hz), torch.zeros_like(hz), hz], dim=-1)
env.scene.sensors = {"height_scanner": s}
cfgn = _D(); cfgn.name = "height_scanner"
ref_out = ref.height_scan_with_gap(env, cfgn, offset=0.5, miss_value=1.0).clip(-1, 1) * 2.5
mine = G.g0_encode(torch.tensor([0.38]), hz)
check("G0 equals lab reference height_scan_with_gap (+clip, scale)", torch.equal(ref_out, mine), f"{ref_out} vs {mine}")

json.dump({"cases": REC, "fails": FAILS}, open(os.path.join(HERE, "out", "G0-fixture.json"), "w"), indent=1)
print()
print(f"{len(FAILS)} failed" if FAILS else "all passed")
sys.exit(1 if FAILS else 0)
