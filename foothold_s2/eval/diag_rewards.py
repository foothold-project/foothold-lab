"""정지 진단 (lead 10/21 03:5x): 항별 보상 «걷는 구간 대 멈춘 구간» + 정지 후 재시작 시험.

    python -m foothold_s2.eval.diag_rewards --policy s1scan|s1blind|v2 --checkpoint <pt> --terrain random_rough [--noise lo,hi] --out <폴더> --headless --device cuda:0

시간표(명령 월드 고정, 몸 기준 전진): 0~4 s 0.5 m/s (여기서 멈춘다) → 4~6 s 1.0 → 6~7 s 0.5 와 0 을 0.25 s 마다 번갈아(흔들기) → 7~9 s 0.5.
보상: env 의 reward_manager 가 낸 «가중치 곱한 초당 값» 을 스텝마다 쌓는다 (v2 env 는 v2 의 보상 항 이름으로 나온다).
분류: 3~4 s 평균 전진 속도 < 0.05 이면 «멈춤», > 0.2 이면 «걷는 중».
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
parser.add_argument("--policy", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--terrain", default="random_rough")
parser.add_argument("--noise", default=None)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, runtime, terrain_sets  # noqa: E402

SECONDS = 9.0
BASE = (0.5, 0.0, 0.0)


def command_at(t):
    if t < 4.0:
        return (0.5, 0.0, 0.0)

    if t < 6.0:
        return (1.0, 0.0, 0.0)

    if t < 7.0:
        return (0.5, 0.0, 0.0) if int((t - 6.0) / 0.25) % 2 == 0 else (0.0, 0.0, 0.0)

    return (0.5, 0.0, 0.0)


adapter = adapters.S2Adapter(args.policy[2:]) if args.policy.startswith("s2") else adapters.S1Adapter(args.policy[2:]) if args.policy.startswith("s1") else terrain_sets.isaaclab_adapter(args.policy, "unseen10")
generator = terrain_sets.merged_generator([args.terrain], 0.5, 42)

if args.noise:
    lo_, hi_ = (float(x) for x in args.noise.split(","))
    generator.sub_terrains[args.terrain].noise_range = (lo_, hi_)

built = adapter.make_env(generator=generator, num_envs=args.envs, duration_s=SECONDS, seed=42, difficulty=0.5,
                         base_cmd=[BASE] * args.envs, device=args.device)
raw = built["raw"]
pin = runtime.CommandPin(args.envs, raw.device, [BASE] * args.envs)
term = adapter.pin_command(raw, pin)
env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)
raw.reset()
runtime.EpisodeRunner._write_command(term, pin.want)
obs = env.get_observations()
robot = raw.scene["robot"]
n, dt = raw.num_envs, raw.step_dt
steps = int(round(SECONDS / dt))
names = list(raw.reward_manager.active_terms)
R = np.zeros((steps, n, len(names)))
VEL = np.zeros((steps, n))
ALIVE = np.zeros((steps, n), dtype=bool)
alive = torch.ones(n, dtype=torch.bool, device=raw.device)

for k in range(steps):
    cmd = torch.tensor(command_at(k * dt), device=raw.device)
    pin.want[:] = cmd
    runtime.EpisodeRunner._write_command(term, pin.want)

    with torch.inference_mode():
        actions = policy(obs)
        obs, _r, dones, _x = env.step(actions)
        policy_nn.reset(dones)

    ALIVE[k] = alive.cpu().numpy()
    R[k] = raw.reward_manager._step_reward.cpu().numpy()
    VEL[k] = robot.data.root_lin_vel_b[:, 0].cpu().numpy()
    alive &= ~dones.bool()

keep = ALIVE.all(axis=0) | (ALIVE[int(4.0 / dt) - 1])        # 0~4 s 동안 살아 있던 env
sl = lambda a, b: slice(int(a / dt), int(b / dt))  # noqa: E731
v34 = np.array([VEL[sl(3, 4), e][ALIVE[sl(3, 4), e]].mean() if ALIVE[sl(3, 4), e].any() else np.nan for e in range(n)])
cls = np.where(keep & (v34 < 0.05), "stalled", np.where(keep & (v34 > 0.2), "walking", "other"))


def window_mean(env_mask, a, b):
    out = {}
    m = ALIVE[sl(a, b)][:, env_mask]
    r = R[sl(a, b)][:, env_mask, :]

    if m.sum() == 0:
        return None

    for j, name in enumerate(names):
        out[name] = float((r[:, :, j] * m).sum() / m.sum())

    out["_sum"] = float(sum(out[nm] for nm in names))

    return out


table = {}

for label in ("stalled", "walking", "other"):
    mask = cls == label
    table[label] = {"envs": int(mask.sum()), "w0_2s": window_mean(mask, 0, 2), "w2_4s": window_mean(mask, 2, 4)} if mask.any() else {"envs": 0}

rest = {}
stalled = cls == "stalled"

for name, (a, b) in {"cmd1.0 (4~6 s)": (5, 6), "shake (6~7 s)": (6.5, 7), "cmd0.5 again (8~9 s)": (8, 9)}.items():
    m = ALIVE[sl(a, b)][:, stalled]
    v = VEL[sl(a, b)][:, stalled]

    if m.size and stalled.any():
        per_env = [float(v[:, i][m[:, i]].mean()) if m[:, i].any() else np.nan for i in range(v.shape[1])]
        per_env = np.array(per_env)
        rest[name] = {"n_stalled_alive": int(np.sum(~np.isnan(per_env))), "restart_ratio_v>0.15": float(np.nanmean(per_env > 0.15)),
                      "mean_v": float(np.nanmean(per_env))}

res = {"policy": args.policy, "terrain": args.terrain, "noise": args.noise, "terms": names, "class_counts": {k: int((cls == k).sum()) for k in ("stalled", "walking", "other")},
       "reward_by_class_window": table, "restart": rest,
       "speed_by_second": [float(VEL[sl(s, s + 1)][ALIVE[sl(s, s + 1)]].mean()) for s in range(int(SECONDS))]}
os.makedirs(args.out, exist_ok=True)

with open(os.path.join(args.out, "rewards.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)

print("REWARDS", json.dumps({k: res[k] for k in ("class_counts", "restart", "speed_by_second")}, ensure_ascii=False), flush=True)
sys.stdout.flush()
os._exit(0)
