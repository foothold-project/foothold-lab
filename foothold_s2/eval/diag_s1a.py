"""S1-a 평가 진단 (lead 10/21 03:3x): 같은 정책을 «학습 env 그대로» 와 «평가 S1Adapter 길» 에서 돌려 명령 대비 속도를 맞댄다.

    python -m foothold_s2.eval.diag_s1a --mode train|eval --variant scan|blind --checkpoint <pt> --cmd 0.5,0,0 --out <폴더> --headless --device cuda:0

mode=train: 학습 지형 · 학습 env 클래스 그대로, 명령만 고정 (DR 은 --keep_dr 이 없으면 끔), 에피소드 길이 학습 그대로.
mode=eval : 평가 길 (v2 지형 생성기의 한 지형 `--terrain`, 6 s, S1Adapter.make_env).
기록: 스텝별 평균 전진 속도 · 관측 속의 명령 칸 · 낙상 수, 지형 레벨 / 지형 종류별 전진 거리.
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
parser.add_argument("--mode", choices=["train", "eval"], required=True)
parser.add_argument("--variant", choices=["scan", "blind"], required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--cmd", default="0.5,0,0")
parser.add_argument("--terrain", default="random_rough")
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--seconds", type=float, default=6.0)
parser.add_argument("--keep_dr", action="store_true")
parser.add_argument("--sample", action="store_true", help="평균 행동 대신 학습처럼 표집한 행동 (가설: 정책이 행동 잡음에 기대고 있다)")
parser.add_argument("--native", action="store_true", help="학습 명령 생성기 그대로 (train 모드 전용): 명령 대비 속도 오차를 잰다")
parser.add_argument("--zero_obs_cmd", action="store_true", help="진단: 관측 속 명령 칸을 0 으로 (정책이 명령을 보는지)")
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, terrain_sets  # noqa: E402

cmd = tuple(float(x) for x in args.cmd.split(","))
adapter = adapters.S1Adapter(args.variant)
device = args.device

if args.mode == "eval":
    generator = terrain_sets.merged_generator([args.terrain], 0.5, 42)
    built = adapter.make_env(generator=generator, num_envs=args.envs, duration_s=args.seconds, seed=42,
                             difficulty=0.5, base_cmd=[cmd] * args.envs, device=device)
    raw = built["raw"]
else:
    env_cfg = adapter.env_cfg_class()
    env_cfg.seed = 42
    env_cfg.scene.num_envs = args.envs
    env_cfg.sim.device = device
    env_cfg.observations.policy.enable_corruption = False
    c = env_cfg.commands.base_velocity
    if not args.native:
        c.fixed_cmd = cmd
        c.flag_stride = 0
        c.resampling_time_range = (1.0e9, 1.0e9)

    if not args.keep_dr:
        for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass", "base_com",
                     "push_robot", "base_external_force_torque"):
            if hasattr(env_cfg.events, name):
                setattr(env_cfg.events, name, None)

        env_cfg.actions.joint_pos.max_delay_s = 0.0

    for name in ("terrain_levels", "command_range", "penalty_on"):
        if hasattr(env_cfg.curriculum, name):
            setattr(env_cfg.curriculum, name, None)

    agent_cfg = load_cfg_from_registry(adapter.task_id, "rsl_rl_cfg_entry_point")
    agent_cfg.device = device
    raw = ManagerBasedRLEnv(cfg=env_cfg)
    built = {"gym_env": raw, "raw": raw, "env_cfg": env_cfg, "agent_cfg": agent_cfg}

env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)
raw.reset()
obs = env.get_observations()
robot = raw.scene["robot"]
term = raw.command_manager.get_term("base_velocity")
n = raw.num_envs
steps = int(round(args.seconds / raw.step_dt))
terrain = raw.scene.terrain
levels = terrain.terrain_levels.detach().cpu().numpy().copy() if hasattr(terrain, "terrain_levels") else np.zeros(n, int)
types = terrain.terrain_types.detach().cpu().numpy().copy() if hasattr(terrain, "terrain_types") else np.zeros(n, int)
start = robot.data.root_pos_w[:, :2].clone()
unit = torch.tensor(cmd[:2], device=raw.device)
unit = unit / unit.norm().clamp_min(1e-9)
log = {"mode": args.mode, "variant": args.variant, "cmd": cmd, "steps": steps, "dt": raw.step_dt, "obs_dim": int(obs["policy"].shape[1]),
       "series": [], "cmd_obs": [], "term_cmd": []}
alive = torch.ones(n, dtype=torch.bool, device=raw.device)
progress_at_end = torch.zeros(n, device=raw.device)
fell = torch.zeros(n, dtype=torch.bool, device=raw.device)
maxp = torch.zeros(n, device=raw.device)
prog_acc = torch.zeros(n, device=raw.device)
cmd_lo = 66 + 30 if args.variant == 'blind' else 6

for k in range(steps):
    with torch.inference_mode():
        o = obs
        if args.zero_obs_cmd:
            o = obs.clone()
            p = o["policy"].clone()
            p[:, 66:99] = 0.0 if args.variant == 'blind' else p[:, 66:99]
            if args.variant == 'scan':
                p[:, 6:9] = 0.0                      # cmd 칸 (term 순서 ang_vel 33 · gravity 33 · cmd 33 ...)
            o["policy"] = p
        actions = policy_nn.act(o) if args.sample else policy(o)
        obs, _r, dones, _x = env.step(actions)
        policy_nn.reset(dones)

    pos = robot.data.root_pos_w[:, :2]
    vel_b = robot.data.root_lin_vel_b[:, :2]
    v_along = (vel_b * unit).sum(1)
    prog = prog_acc = (prog_acc + v_along * raw.step_dt) if k else v_along * raw.step_dt
    term_fell = raw.reset_terminated
    fell |= term_fell
    maxp = torch.maximum(maxp, prog)

    cmd_now = term.vel_command_b[:, :2]
    err_now = (vel_b - cmd_now).norm(dim=1)
    moving = (cmd_now.norm(dim=1) > 0.2) & ~term.is_flag_env
    log.setdefault("track", []).append([k * raw.step_dt, float(err_now[moving].mean()) if moving.any() else None,
                                        float(cmd_now[moving].norm(dim=1).mean()) if moving.any() else None,
                                        float(vel_b[moving].norm(dim=1).mean()) if moving.any() else None,
                                        float((vel_b[moving] * cmd_now[moving]).sum(1).mean() / (cmd_now[moving].norm(dim=1) ** 2).mean()) if moving.any() else None,
                                        int(moving.sum())])

    h = robot.data.root_pos_w[:, 2] - raw.scene.terrain.env_origins[:, 2]
    low = h < 0.22
    log.setdefault("posture", []).append([k * raw.step_dt, float(h.mean()), float(low.float().mean()),
                                          float(robot.data.projected_gravity_b[:, 2].mean()),
                                          float(vel_b[low].norm(dim=1).mean()) if low.any() else None,
                                          float(vel_b[~low].norm(dim=1).mean()) if (~low).any() else None])

    if k % 10 == 0:
        p = obs["policy"]
        log["series"].append({"k": k, "t": k * raw.step_dt, "v_along_mean": float(v_along.mean()),
                              "v_along_median": float(v_along.median()), "prog_median": float(prog.median()),
                              "speed_norm_mean": float(vel_b.norm(dim=1).mean()), "fell": int(fell.sum()),
                              "obs_cmd_last": [float(x) for x in p[0, cmd_lo:cmd_lo + 3]],
                              "term_cmd": [float(x) for x in term.vel_command_b[0]],
                              "wz_mean_abs": float(robot.data.root_ang_vel_b[:, 2].abs().mean())})

summary = {"max_prog_median": float(maxp.median()), "max_prog_mean": float(maxp.mean()), "fell": int(fell.sum()), "n": n}
groups = {}

for i in range(n):
    key = "level%d_type%d" % (levels[i], types[i]) if args.mode == "train" else "type%d" % types[i]
    groups.setdefault(key, []).append(float(maxp[i]))

summary["by_group"] = {g: {"n": len(v), "median_max_prog": float(np.median(v)), "mean": float(np.mean(v))} for g, v in sorted(groups.items())}
log["summary"] = summary
os.makedirs(args.out, exist_ok=True)

with open(os.path.join(args.out, "diag.json"), "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=1)

print("DIAG", json.dumps(summary, ensure_ascii=False)[:1500], flush=True)
sys.stdout.flush()
os._exit(0)
