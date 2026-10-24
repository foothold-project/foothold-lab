"""B1500 같은 모델을 지도 모드 셋(eval_gt · eval_pred · probe_prop_only)으로 평가 (SONNET-X25 T4/준비). 학습 · 저장 없음.

    python -m foothold_s2.eval.eval_map_modes --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint <model_1500.pt> --out <폴더> --headless --device cuda:0

diag_z_action 과 같은 틀: 학습 env 그대로 64 env 300 스텝, DR(게인 · 세기 · 마찰 · 질량 · 무게중심 · 밀기 · 지연)만 끔, z mean · action mean.
명령 전진 0.5 · 1.0 → 제자리 회전 +1.2 · -1.2 를 매 스텝 고정값으로 덮어쓴다(순차 영상 촬영과 같은 명령 넷이되 명령마다 리셋하는 독립 시험).
모드마다 정책 입력 지도에 실제로 GT 가 몇 번 들어갔는지 지각의 _advance 를 감싸 센다: eval_pred · probe_prop_only 는 0, eval_gt 는 전부여야 하고 어긋나면 그 자리에서 멈춘다.
산출: 모드 x 명령별 전진 거리 · 요 추종 · 멈춤 비율 · 몸 기울기(roll/pitch 절댓값 평균) · 살아남은 env 수 · GT 사용 횟수.
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
parser.add_argument("--modes", default="eval_gt,eval_pred,probe_prop_only")
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

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
import foothold_s2.x23f_tasks  # noqa: E402,F401
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

env_cfg.commands.base_velocity.resampling_time_range = (1.0e9, 1.0e9)
env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
raw = env.unwrapped
dev = raw.device
robot = raw.scene["robot"]
term = raw.command_manager.get_term("base_velocity")
dt = raw.step_dt
sha = __import__("foothold_s2.runners.manifest", fromlist=["x"]).sha256_file(args.checkpoint)
CMDS = {"fwd0.5": (0.5, 0.0, 0.0), "fwd1.0": (1.0, 0.0, 0.0), "spin+1.2": (0.0, 0.0, 1.2), "spin-1.2": (0.0, 0.0, -1.2)}
S = args.steps
res = {"task": args.task, "checkpoint": args.checkpoint, "checkpoint_sha256": sha, "envs": args.envs, "steps": S, "dr_off": dr_off, "modes": {}}

for mode in args.modes.split(","):
    runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)       # 모드마다 새 runner: probe_prop_only 의 mask 가 다른 모드로 새지 않는다
    res["checkpoint_iter"] = int(sd.get("iter", -1))
    res["restored_modes"] = {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt_saved": runner.perception.cfg.force_gt}
    counts = {"gt": 0, "total": 0}
    orig_adv = runner.perception._advance

    def tapped(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, _orig=orig_adv, _c=counts):
        _c["gt"] += int(use_gt.sum())
        _c["total"] += int(use_gt.numel())

        return _orig(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)

    runner.perception._advance = tapped
    res["modes"][mode] = {}

    for cname, cmd in CMDS.items():
        torch.manual_seed(42)
        env.reset()
        term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
        counts["gt"] = counts["total"] = 0
        policy = adapters.S2Policy(runner, env.num_envs, z_mode="mean", act_mode="mean", map_mode=mode)
        obs = env.get_observations()
        alive = torch.ones(env.num_envs, dtype=torch.bool, device=dev)
        VX, WZ, TILT = (torch.zeros(S, env.num_envs, device=dev) for _ in range(3))
        AL = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)

        for k in range(S):
            term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
            a = policy(obs)
            obs, _r, dones, _x = env.step(a)
            policy.reset(dones)
            AL[k] = alive
            VX[k] = robot.data.root_lin_vel_b[:, 0]
            WZ[k] = robot.data.root_ang_vel_b[:, 2]
            g = robot.data.projected_gravity_b
            TILT[k] = torch.atan2(g[:, :2].norm(dim=1), -g[:, 2]).abs()
            alive = alive & ~dones.bool()

        if mode in ("eval_pred", "probe_prop_only") and counts["gt"] != 0:
            raise RuntimeError("%s 인데 정책 입력에 GT 가 %d 번 들어갔다" % (mode, counts["gt"]))
        if mode == "eval_gt" and counts["gt"] != counts["total"]:
            raise RuntimeError("eval_gt 인데 GT 가 %d/%d 번만 들어갔다" % (counts["gt"], counts["total"]))

        vx, wz, al, tilt = VX.cpu().numpy(), WZ.cpu().numpy(), AL.cpu().numpy(), TILT.cpu().numpy()
        sl = slice(int(2.0 / dt), int(4.0 / dt))
        dist = (vx * al).sum(0) * dt
        nalive = np.maximum(al.sum(0), 1)
        spin = abs(cmd[2]) > 0
        follow = (wz * al).sum(0) / nalive / (cmd[2] if spin else 1.0)
        used = al[sl].any(0)

        if spin:
            stall = float(np.mean((np.abs(np.where(al[sl], wz[sl], np.nan)).mean(0)[used]) < 0.1 * abs(cmd[2])))
        else:
            stall = float(np.mean((np.where(al[sl], vx[sl], np.nan).mean(0)[used]) < 0.05))

        row = {"forward_dist_median_m": float(np.median(dist)), "yaw_follow_median": float(np.median(follow)), "stalled_fraction_2to4s": stall,
               "tilt_rad_mean_alive": float((tilt * al).sum() / max(al.sum(), 1)), "alive_envs_at_end": int(al[-1].sum()), "gt_used": counts["gt"], "policy_steps_x_envs": counts["total"]}
        res["modes"][mode][cname] = row
        print("MAPMODE", mode, cname, json.dumps(row), flush=True)

os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "map_modes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("MAPMODE_DONE", flush=True)
os._exit(0)
