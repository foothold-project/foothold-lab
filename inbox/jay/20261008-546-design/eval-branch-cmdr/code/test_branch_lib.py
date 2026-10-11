# CPU tests for branch_lib.py and for the reset-age arithmetic of the real sampler code.
# The sampler lines are taken from the repository source by AST (commands.py) and the real
# sample_disjoint_intervals is loaded from utils.py, so the test runs the code text that trains E1.
# Run: python test_branch_lib.py  (writes ../out/branch/cpu_tests.json)
import ast
import importlib.util
import json
import math
import os
import sys
import types

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import branch_lib as B  # noqa: E402

REPO = "C:/isaac/ext/go2_rl_robotlab"
CMD = os.path.join(REPO, "source/robot_lab/robot_lab/tasks/go2/mdp/commands.py")
UTL = os.path.join(REPO, "source/robot_lab/robot_lab/tasks/go2/mdp/utils.py")
CUR = os.path.join(REPO, "source/robot_lab/robot_lab/tasks/go2/mdp/curriculums.py")
RES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)))
    RES.append({"name": name, "pass": bool(cond), "detail": "" if cond else str(detail)})


# ---- real code pieces -------------------------------------------------------------------------------
spec = importlib.util.spec_from_file_location("go2_utils", UTL)
U = importlib.util.module_from_spec(spec)
spec.loader.exec_module(U)
tree = ast.parse(open(CMD, encoding="utf-8").read())
res_fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_resample"][0]
stmts = {}
for n in ast.walk(res_fn):
    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("remaining_dist", "vel_low_bound", "next_time_left"):
        stmts[n.targets[0].id] = compile(ast.Expression(n.value), CMD, "eval")
check("found the three sampler expressions in commands.py", set(stmts) == {"remaining_dist", "vel_low_bound", "next_time_left"}, list(stmts))


def sampler_terms(age, accum_norm=0.0, terrain_length=8.0, n=10000, max_lin=1.0):
    env = types.SimpleNamespace(max_episode_length=1250, episode_length_buf=torch.full((n,), float(age)), step_dt=0.02, max_episode_length_s=25.0)
    me = types.SimpleNamespace(terrain_length=terrain_length, commands_xy_accumulation=torch.zeros(n, 2), max_lin_vel=max_lin,
                               cfg=types.SimpleNamespace(resampling_time=5.0))
    me.commands_xy_accumulation[:, 0] = accum_norm
    ns = {"torch": torch, "self": me, "env": env, "env_ids": torch.arange(n)}
    ns["remaining_dist"] = eval(stmts["remaining_dist"], ns)
    lb = eval(stmts["vel_low_bound"], ns)
    ntl = eval(stmts["next_time_left"], ns)
    return ns["remaining_dist"], lb, ntl


rd, lb_old, ntl_old = sampler_terms(1250)
rd0, lb_new, ntl_new = sampler_terms(0)
check("terrain length 8 m (9 m tile - 2 x 0.5 border): remaining distance 5 m", abs(float(rd[0]) - 5.0) < 1e-6, float(rd[0]))
check("time-out reset, pre-reset age 1250: lower bound 5 / (1 x 0.02) = 250", abs(float(lb_old[0]) - 250.0) < 1e-3, float(lb_old[0]))
check("same reset with age 0: lower bound 5 / (1251 x 0.02) = 0.19984", abs(float(lb_new[0]) - 5.0 / (1251 * 0.02)) < 1e-6, float(lb_new[0]))
check("zero branch time: age 1250 -> 0 (zero impossible), age 0 -> clip(25 - 5/0.8, 0, 5) = 5", float(ntl_old[0]) == 0.0 and abs(float(ntl_new[0]) - 5.0) < 1e-6,
      (float(ntl_old[0]), float(ntl_new[0])))
torch.manual_seed(0)
lo, hi = torch.full((10000,), -1.0), torch.full((10000,), 1.0)
s_old = U.sample_disjoint_intervals(torch.arange(10000), lb_old, lo, hi, "cpu")
s_new = U.sample_disjoint_intervals(torch.arange(10000), lb_new, lo, hi, "cpu")
check("age 1250: all 10,000 samples in [+1, +1 + 1e-6] (the +bound bias)", bool(((s_old >= 1.0) & (s_old <= 1.0 + 1e-6)).all()), (float(s_old.min()), float(s_old.max())))
check("age 0: both signs, |v| >= 0.19984, inside [-1, 1]", bool((s_new < 0).any() and (s_new > 0).any() and (s_new.abs() >= float(lb_new[0]) - 1e-6).all()
                                                               and (s_new.abs() <= 1.0 + 1e-6).all()), (float(s_new.min()), float(s_new.max())))
neg = float((s_new < 0).float().mean())
check("age 0: negative share about (1-0.2)/(2*(1-0.2)) = 0.5", abs(neg - 0.5) < 0.02, neg)
_, lb_mid, _ = sampler_terms(1240)
check("lower bound > upper bound (1.0) also happens near the end without the reset bug: age 1240 -> 5/(11 x 0.02) = 22.7", float(lb_mid[0]) > 1.0, float(lb_mid[0]))

# ---- adapter ---------------------------------------------------------------------------------------------
class FakeTerm:
    def __init__(self, env):
        self.env = env
        self.seen = None

    def reset(self, env_ids=None):
        self.seen = self.env.episode_length_buf[env_ids].clone()
        return {"ok": 1}


env = types.SimpleNamespace(episode_length_buf=torch.tensor([1250, 300, 1250, 7]))
term = FakeTerm(env)
ad = B.ResetAgeAdapter(env, term)
out = term.reset(torch.tensor([0, 2]))
check("adapter: sampler sees age 0 for the reset envs", term.seen.tolist() == [0, 0], term.seen.tolist())
check("adapter: buffer restored for everything after the command reset", env.episode_length_buf.tolist() == [1250, 300, 1250, 7], env.episode_length_buf.tolist())
check("adapter: return value passed through, calls counted", out == {"ok": 1} and ad.calls == 1)
ad.remove()
term.reset(torch.tensor([0]))
check("adapter removed: original age seen again", term.seen.tolist() == [1250], term.seen.tolist())

# ---- schedule targets ------------------------------------------------------------------------------------
stages = sorted([{"iter": 20000, "lin_vel_x": [-1.0, 1.0], "lin_vel_y": [-1.0, 1.0], "ang_vel_yaw": [-1.5, 1.5]},
                 {"iter": 50000, "lin_vel_x": [-2.0, 2.0], "lin_vel_y": [-1.0, 1.0], "ang_vel_yaw": [-2.0, 2.0]}], key=lambda x: x["iter"], reverse=True)
L, ctr = B.next_label_and_counter(20000)
r, rem = B.apply_command_stages(stages, ctr // 24)
check("L=20000: next 20001, counter 480,024, stage 20000 applied, 50000 left", L == 20001 and ctr == 480024 and r["lin_vel_x"] == [-1.0, 1.0]
      and r["ang_vel_yaw"] == [-1.5, 1.5] and [s["iter"] for s in rem] == [50000], (L, ctr, r, rem))
L, ctr = B.next_label_and_counter(99)
r, rem = B.apply_command_stages(stages, ctr // 24)
check("L=99: next 100, counter 2,400, no stage applied", L == 100 and ctr == 2400 and r is None and len(rem) == 2)
zc = {"start_iter": 0, "end_iter": 1500, "start_value": 0.0, "end_value": 0.1}
check("zero prob: iter 100 -> 0.0066667, iter 20001 -> 0.1", abs(B.zero_prob(100, zc) - 0.1 * 100 / 1500) < 1e-12 and B.zero_prob(20001, zc) == 0.1)
check("base_height (-1 -> -10 over 0..5000): iter 100 -> -1.18, 20001 -> -10", abs(B.gradual_weight(100, -1, -10, 0, 5000) + 1.18) < 1e-12 and B.gradual_weight(20001, -1, -10, 0, 5000) == -10)
check("lin_vel_z (-2 -> 0 over 0..1500): iter 100 -> -1.86667, 20001 -> 0", abs(B.gradual_weight(100, -2, 0, 0, 1500) - (-2 + 100 / 1500 * 2)) < 1e-12 and B.gradual_weight(20001, -2, 0, 0, 1500) == 0)
src = open(CUR, encoding="utf-8").read()
check("curriculums.py still divides by the literal 24 (lines 163 and 186)", src.count("common_step_counter // 24") == 2)
tt = np.repeat(np.arange(20), 51)
lv = B.stratified_levels(tt)
cnt = np.array([[np.sum((tt == c) & (lv == k)) for k in range(6)] for c in range(20)])
check("stratified levels: every column holds levels 0..5 with counts differing by at most 1", bool((cnt.max(1) - cnt.min(1) <= 1).all()), cnt[:2].tolist())
check("stratified levels are a pure function of the column layout", np.array_equal(B.stratified_levels(tt), lv))
ok = [B.gate_allowed(True, 1024, 3, False)[0], B.gate_allowed(True, 4096, 0, False)[0], B.gate_allowed(True, 1024, 4, False)[0],
      B.gate_allowed(True, 2048, 1, False)[0], B.gate_allowed(False, 1024, 1, False)[0], B.gate_allowed(False, 8192, 4000, True)[0]]
check("gate policy: allow (1024,3) and rollout-only 4096; refuse 4 updates, 2048 envs, no-gate without contract; allow confirmed experiment",
      ok == [True, True, False, False, False, True], ok)

nf = sum(not r["pass"] for r in RES)
print(f"\n{len(RES)} checks, {nf} failed")
os.makedirs(os.path.join(HERE, "..", "out", "branch"), exist_ok=True)
json.dump({"n": len(RES), "failed": nf, "results": RES}, open(os.path.join(HERE, "..", "out", "branch", "cpu_tests.json"), "w"), indent=1)
sys.exit(1 if nf else 0)
