"""명령 반응 시험 (lead 10/21 밤): 정책이 명령을 읽는지 · est 에 기대는지 · 행동 크기.

    python -m foothold_s2.eval.diag_cmd_response --kind s2open|s2start|s1scan|s1d2 --checkpoint <pt> --out <폴더> --headless --device cuda:0

학습 env 그대로(지형 · 명령 모드 · 관측 잡음 그대로) 64 env, 무작위(DR: 게인 · 세기 · 마찰 · 질량 · 무게중심 · 밀기 · 지연)만 끈다. 정책은 결정 행동(평균).
(1) 스텝마다: actor 입력에서 명령과 같은 3 칸의 자리 · command_manager 버퍼 · 보상 track_lin_vel 이 쓰는 목표 · 실제 몸 속도.
(2) 같은 상태에서 명령 칸만 바꿔 넣은 평균 행동 차이(12 차원 L2, env · 상태 평균).
(3) S2: est 51 칸을 0 으로 · 다른 env 것으로 섞어 바꿨을 때. S1 scan: 높이 스캔 187 칸을 0 으로(est 에 해당하는 입력).
(4) 행동 |a| 평균 · env 간 표준편차 · 관절 목표가 기본 자세에서 벗어난 양(= 행동 x 척도) · 실제 관절 위치 편차.
"""

import argparse
import json
import os
import sys

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--kind", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--steps", type=int, default=300)
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters  # noqa: E402

TASKS = {"s2open": "FootholdS2-Go2-S2-diag-G0-open-v0", "s2start": "FootholdS2-Go2-S2-diag-G0-start-v0",
         "s1scan": "FootholdS2-Go2-S1a-scan-v0", "s1d2": "FootholdS2-Go2-S1a-diag-D2-v0"}
IS_S2 = args.kind.startswith("s2")
task = TASKS[args.kind]
env_cfg = load_cfg_from_registry(task, "env_cfg_entry_point")
agent_cfg = load_cfg_from_registry(task, "rsl_rl_cfg_entry_point")
env_cfg.scene.num_envs = args.envs
env_cfg.sim.device = args.device
agent_cfg.device = args.device
dr_off = []

for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass", "base_com", "push_robot", "base_external_force_torque"):
    if getattr(env_cfg.events, name, None) is not None:
        setattr(env_cfg.events, name, None)
        dr_off.append(name)

if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
    env_cfg.actions.joint_pos.max_delay_s = 0.0
    dr_off.append("action_delay")

scale = float(env_cfg.actions.joint_pos.scale)
env = RslRlVecEnvWrapper(gym.make(task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
raw = env.unwrapped
dev = raw.device
robot = raw.scene["robot"]

if IS_S2:
    runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)
    policy = adapters.S2Policy(runner, env.num_envs)
    KEY = "actor_in"
else:
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=args.device)
    runner.load(args.checkpoint)
    policy = runner.get_inference_policy(device=dev)
    KEY = "policy"

runner.alg.policy.eval()
net = runner.alg.policy
term = raw.command_manager.get_term("base_velocity")
obs = env.get_observations()
default = robot.data.default_joint_pos[0].clone()


def act_from(od):
    with torch.inference_mode():
        return net.act_inference(od)


def policy_obs():
    """지금 관측에서 actor 입력 묶음(S2: 지각 한 스텝은 이미 policy(obs) 가 진행했다 -> est 는 policy.last_est)."""
    if IS_S2:
        return runner._ppo_obs(obs.to(runner.device), policy.last_est)

    return obs


def edit(od, cols, vals):
    o2 = od.clone()
    x = o2[KEY].clone()
    x[:, cols] = vals
    o2[KEY] = x

    return o2


cmd_cols = None
match_steps = []          # (1) 칸 자리 찾기용: 칸 i 마다 평균 |obs[i:i+3] - cmd|
col_err = None
rew_check = []
vel_rows = []
sens_states = []
acts = []
joint_dev = []
term_cfg = raw.reward_manager.get_term_cfg("track_lin_vel")
std = float(term_cfg.params["std"])

for k in range(args.steps):
    with torch.inference_mode():
        a = policy(obs)

    if IS_S2:
        pass

    acts.append(a.detach().float().cpu())
    od = policy_obs()
    x = od[KEY]
    cmd = raw.command_manager.get_command("base_velocity")[:, :3]
    err = torch.stack([(x[:, i:i + 3] - cmd).abs().mean() for i in range(x.shape[1] - 2)]).cpu().numpy()
    col_err = err if col_err is None else col_err + err

    if k >= 150 and (k - 150) % 10 == 0 and k < 260:
        sens_states.append({"od": od.clone(), "est": (policy.last_est.clone() if IS_S2 else None), "cmd": cmd.clone()})

    with torch.inference_mode():
        obs, _r, dones, _x = env.step(a)

    if IS_S2:
        policy.reset(dones)

    c2 = raw.command_manager.get_command("base_velocity")[:, :3]
    v = robot.data.root_lin_vel_b[:, :3]
    func_val = term_cfg.func(raw, **term_cfg.params)
    plain = torch.exp(-torch.sum((v[:, :2] - c2[:, :2]) ** 2, dim=-1) / std ** 2)
    minf = torch.exp(-torch.sum((torch.minimum(v[:, :2], c2[:, :2]) - c2[:, :2]) ** 2, dim=-1) / std ** 2)
    rew_check.append([float((func_val - plain).abs().max()), float((func_val - minf).abs().max())])
    moving = c2[:, 0].abs() > 0.3
    vel_rows.append([float(c2[:, 0].mean()), float(v[:, 0].mean()), float(moving.float().mean()),
                     float(v[moving, 0].mean()) if bool(moving.any()) else float("nan"), float(c2[moving, 0].mean()) if bool(moving.any()) else float("nan")])
    joint_dev.append(float((robot.data.joint_pos - default).abs().mean()))

col_err = col_err / args.steps
best = int(np.argmin(col_err))
cmd_cols = list(range(best, best + 3))
res = {"kind": args.kind, "checkpoint": args.checkpoint, "task": task, "dr_off": dr_off, "joint_action_scale": scale, "envs": args.envs, "steps": args.steps}
res["cmd_col_search"] = {"best_start_col": best, "best_mean_abs_err": float(col_err[best]), "second_best_err": float(np.sort(col_err)[1]),
                         "obs_dim": int(len(col_err) + 2)}
rc = np.array(rew_check)
res["reward_target"] = {"max_abs_diff_vs_plain_exp": float(rc[:, 0].max()), "max_abs_diff_vs_min_form": float(rc[:, 1].max()),
                        "lin_std": std, "form_used": "A(min)" if rc[:, 1].max() < rc[:, 0].max() else "B(plain)"}
vr = np.array(vel_rows)
res["velocity"] = {"cmd_vx_mean": float(np.nanmean(vr[:, 0])), "body_vx_mean": float(np.nanmean(vr[:, 1])), "frac_envs_cmd_moving": float(np.nanmean(vr[:, 2])),
                   "body_vx_when_cmd_moving": float(np.nanmean(vr[:, 3])), "cmd_vx_when_moving": float(np.nanmean(vr[:, 4]))}

# (2) 민감도
variants = {"zero": (0, 0, 0), "vx0.5": (0.5, 0, 0), "vx1.0": (1.0, 0, 0), "vy0.5": (0, 0.5, 0), "wz1.0": (0, 0, 1.0)}
vals = {}
for s in sens_states:
    od = s["od"]
    base = act_from(od)
    outs = {name: act_from(edit(od, cmd_cols, torch.tensor(c, dtype=torch.float32, device=dev))) for name, c in variants.items()}
    d = lambda p, q: float((p - q).norm(dim=-1).mean())  # noqa: E731
    for name in ("vx0.5", "vx1.0", "vy0.5", "wz1.0"):
        vals.setdefault("L2 %s vs zero" % name, []).append(d(outs[name], outs["zero"]))
    vals.setdefault("L2 vx1.0 vs vx0.5", []).append(d(outs["vx1.0"], outs["vx0.5"]))
    vals.setdefault("L2 actual cmd vs zero", []).append(d(base, outs["zero"]))
    vals.setdefault("norm |a(zero)|", []).append(float(outs["zero"].norm(dim=-1).mean()))
    vals.setdefault("norm |a(actual)|", []).append(float(base.norm(dim=-1).mean()))

    if IS_S2:
        x = od[KEY].clone()
        o_zero = od.clone()
        xz = x.clone()
        xz[:, 45:] = 0
        o_zero[KEY] = xz
        o_shuf = od.clone()
        xs = x.clone()
        xs[:, 45:] = x[torch.randperm(x.shape[0], device=dev), 45:]
        o_shuf[KEY] = xs
        vals.setdefault("L2 est zero vs base", []).append(d(act_from(o_zero), base))
        vals.setdefault("L2 est shuffled(other env) vs base", []).append(d(act_from(o_shuf), base))
    elif args.kind in ("s1scan", "s1d2"):
        x = od[KEY].clone()
        o_zero = od.clone()
        xz = x.clone()
        xz[:, 45:] = 0
        o_zero[KEY] = xz
        vals.setdefault("L2 height-scan(187) zero vs base", []).append(d(act_from(o_zero), base))

res["sensitivity"] = {k: float(np.mean(v)) for k, v in vals.items()}
res["sensitivity_states"] = len(sens_states)

# (4) 행동 크기
A = torch.stack(acts)                                   # (T, N, 12)
res["action"] = {"mean_abs": float(A.abs().mean()), "std_across_envs_mean_over_dims_time": float(A.std(dim=1).mean()),
                 "std_over_time_mean_over_envs_dims": float(A.std(dim=0).mean()), "p99": float(torch.quantile(A.abs().flatten()[:2000000], 0.99)),
                 "target_dev_from_default_rad_mean": float(A.abs().mean()) * scale,
                 "measured_joint_dev_from_default_rad_mean": float(np.mean(joint_dev[100:]))}
os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "cmd_response_%s.json" % args.kind), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("CMDRESP", json.dumps(res, ensure_ascii=False)[:2500], flush=True)
os._exit(0)
