"""EX-10 네 조합 평가 (SONNET-X11 2 단계): z{mean,sample} x action{mean,sample}, 명령 전진 0.5 · 1.0, 제자리 회전 +1.2 · -1.2.

    python -m foothold_s2.eval.diag_z_action --task FootholdS2-Go2-S2-diag-G0-start-v0 --checkpoint <pt> --out <폴더> --headless --device cuda:0

diag_cmd_response 와 같은 틀: 학습 env 그대로(지형 · 관측 잡음 그대로) 64 env 300 스텝, DR(게인 · 세기 · 마찰 · 질량 · 무게중심 · 밀기 · 지연)만 끔.
명령은 매 스텝 고정값으로 덮어쓴다(재표집 끔). 조합마다 env 를 리셋하고 지각 상태를 새로 만든다.
산출: 조합 x 명령별 전진 거리(몸 vx 적분, 6 s) · 요 추종(평균 wz / 명령 wz) · 멈춤 비율(2~4 s) · 원 행동(clip 전) |a| p50 · p99 · p99.9 · |a|>17 비율 · 살아남은 env 수.
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
parser.add_argument("--task", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--steps", type=int, default=300)
parser.add_argument("--out", required=True)
parser.add_argument("--free_cmd", action="store_true", help="명령을 고정하지 않고 학습 명령 생성기 그대로(점검용: 예전 diag_cmd_response 와 같은 조건), z mean x action mean 한 조합만")
parser.add_argument("--no_reset", action="store_true", help="점검용: 조합 시작 때 env.reset() 을 부르지 않는다(예전 diag_cmd_response 와 같은 조건)")
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

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters  # noqa: E402

env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
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

cmd_cfg = env_cfg.commands.base_velocity
if not args.free_cmd:
    cmd_cfg.resampling_time_range = (1.0e9, 1.0e9)
env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
raw = env.unwrapped
dev = raw.device
robot = raw.scene["robot"]
term = raw.command_manager.get_term("base_velocity")
dt = raw.step_dt
runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)
clip = float(agent_cfg.clip_actions)
CMDS = {"free": None} if args.free_cmd else {"fwd0.5": (0.5, 0.0, 0.0), "fwd1.0": (1.0, 0.0, 0.0), "spin+1.2": (0.0, 0.0, 1.2), "spin-1.2": (0.0, 0.0, -1.2)}
res = {"task": args.task, "checkpoint": args.checkpoint, "checkpoint_iter": int(sd.get("iter", -1)), "envs": args.envs, "steps": args.steps,
       "dr_off": dr_off, "clip_actions": clip, "restored_modes": {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input")},
       "checkpoint_sha256": __import__("foothold_s2.runners.manifest", fromlist=["x"]).sha256_file(args.checkpoint), "combos": {}}
S = args.steps

for z in (("mean",) if args.free_cmd else ("mean", "sample")):
    for act in (("mean",) if args.free_cmd else ("mean", "sample")):
        key = "z_%s__act_%s" % (z, act)
        res["combos"][key] = {}

        for cname, cmd in CMDS.items():
            torch.manual_seed(42)
            if not args.no_reset:
                env.reset()

            if cmd is not None:
                term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
            policy = adapters.S2Policy(runner, env.num_envs, z_mode=z, act_mode=act)
            obs = env.get_observations()
            alive = torch.ones(env.num_envs, dtype=torch.bool, device=dev)
            VX = torch.zeros(S, env.num_envs, device=dev)
            WZ = torch.zeros(S, env.num_envs, device=dev)
            AL = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)
            acts = []

            for k in range(S):
                if cmd is not None:
                    term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)

                a = policy(obs)
                acts.append(a.detach().float().cpu())
                obs, _r, dones, _x = env.step(a)
                policy.reset(dones)
                AL[k] = alive
                VX[k] = robot.data.root_lin_vel_b[:, 0]
                WZ[k] = robot.data.root_ang_vel_b[:, 2]
                alive = alive & ~dones.bool()

            vx, wz, al = VX.cpu().numpy(), WZ.cpu().numpy(), AL.cpu().numpy()
            sl = slice(int(2.0 / dt), int(4.0 / dt))
            dist = (vx * al).sum(0) * dt
            nalive = np.maximum(al.sum(0), 1)
            c2 = cmd[2] if cmd is not None and abs(cmd[2]) > 0 else 1.0
            follow = (wz * al).sum(0) / nalive / c2
            used = al[sl].any(0)

            if cmd is not None and abs(cmd[2]) > 0:
                stall = float(np.mean((np.abs(np.where(al[sl], wz[sl], np.nan)).mean(0)[used]) < 0.1 * abs(cmd[2])))
            else:
                stall = float(np.mean((np.where(al[sl], vx[sl], np.nan).mean(0)[used]) < 0.05))

            A = torch.stack(acts)[torch.from_numpy(al)[..., None].expand(-1, -1, 12)].abs()
            q = lambda p: float(torch.quantile(A[:2000000], p))  # noqa: E731
            res["combos"][key][cname] = {"all_envs_all_steps_a_abs_p99": float(torch.quantile(torch.stack(acts).abs().flatten()[:2000000], 0.99)), "all_envs_all_steps_a_abs_mean": float(torch.stack(acts).abs().mean()), "forward_dist_median_m": float(np.median(dist)), "forward_dist_mean_m": float(dist.mean()),
                                         "yaw_follow_median": float(np.median(follow)), "stalled_fraction_2to4s": stall,
                                         "alive_envs_at_end": int(al[-1].sum()), "a_abs_p50": q(0.5), "a_abs_p99": q(0.99), "a_abs_p99.9": q(0.999),
                                         "a_abs_gt_clip_fraction": float((A > clip).float().mean()), "a_abs_max": float(A.max())}
            print("ZACT", key, cname, json.dumps(res["combos"][key][cname]), flush=True)

os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "z_action.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ZACT_DONE", flush=True)
os._exit(0)
