"""S2 어댑터 점검: 명령이 관측에 들어가는지 · 행동 크기 · 지각 추정 크기를 몇 스텝 찍는다. 정책을 새로 돌리지 않는다(체크포인트 읽기만).

    python -m foothold_s2.eval.diag_s2_adapter --policy s2open --checkpoint <pt> --out <폴더> --headless --device cuda:1
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
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, runtime, terrain_sets  # noqa: E402

cmd = (0.5, 0.0, 0.0)
adapter = adapters.S2Adapter(args.policy[2:])
generator = terrain_sets.merged_generator(["random_rough"], 0.5, 42)
generator.sub_terrains["random_rough"].noise_range = (0.0, 0.003)
built = adapter.make_env(generator=generator, num_envs=8, duration_s=4.0, seed=42, difficulty=0.5, base_cmd=[cmd] * 8, device=args.device)
raw = built["raw"]
pin = runtime.CommandPin(8, raw.device, [cmd] * 8)
term = adapter.pin_command(raw, pin)
env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)
raw.reset()
runtime.EpisodeRunner._write_command(term, pin.want)
obs = env.get_observations()
res = {"obs_keys": sorted(obs.keys()), "policy_shape": list(obs["policy"].shape), "term_class": type(term).__name__,
       "cmd_in_term": term.vel_command_b[0].tolist(), "steps": []}
for k in range(60):
    with torch.inference_mode():
        a = policy(obs)
        o = obs["policy"][0]
        obs, _r, dones, _x = env.step(a)
        policy_nn.reset(dones)
    runtime.EpisodeRunner._write_command(term, pin.want)
    if k % 10 == 0:
        res["steps"].append({"k": k, "obs_0_12": [round(float(x), 3) for x in o[:12]], "act_abs_mean": float(a.abs().mean()),
                             "vx": float(raw.scene["robot"].data.root_lin_vel_b[0, 0]), "cmd_term": term.vel_command_b[0].tolist()})
os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "adapter_check.json"), "w", encoding="utf-8"), indent=1)
print("ADAPTER_CHECK", json.dumps(res)[:1500], flush=True)
os._exit(0)
