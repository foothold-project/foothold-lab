"""G1 짧은 학습 뒤 재구성 지도 한 장을 정답 지도와 나란히 저장한다 (53 §예행). isaac311 python 으로.

사용: python -m foothold_s2.tasks.probe_s2_recon --headless --device cuda:1 --iters 40 --png <경로>
"""

import argparse
import os
import sys

import tensordict  # noqa: F401
import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--iters", type=int, default=40)
parser.add_argument("--num_envs", type=int, default=64)
parser.add_argument("--png", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.runners.start_runner import StartRunner  # noqa: E402
from foothold_s2.tasks.agents.s2_ppo_cfg import S2PPORunnerCfg  # noqa: E402
from foothold_s2.tasks.s2_env_cfg import FootholdS2G1EnvCfg  # noqa: E402


def main():
    cfg = FootholdS2G1EnvCfg()
    cfg.scene.num_envs = args.num_envs
    cfg.sim.device = args.device
    env = RslRlVecEnvWrapper(gym.make("FootholdS2-Go2-S2-G1-v0", cfg=cfg), clip_actions=None)
    agent = S2PPORunnerCfg()
    agent.device = args.device
    train_cfg = agent.to_dict()
    train_cfg["perception"] = {"map_input": "reconstruction"}
    runner = StartRunner(env, train_cfg, log_dir=None, device=args.device)
    runner.learn(num_learning_iterations=args.iters, init_at_random_ep_len=True)

    with torch.inference_mode():
        raw = env.get_observations().to(args.device)
        o, depth, gmap, _, _, _ = runner._split(raw)
        inp = runner.perception.ingest(runner.pstate, o, depth)
        _, _, out = runner.perception._advance(runner.pstate.h_prop, runner.pstate.h_terr, inp["hist"], inp["depth2"],
                                               inp["tick"], inp["first"], runner.pstate.use_gt, gmap)

    n = min(6, args.num_envs)
    fig, ax = plt.subplots(3, n, figsize=(2.0 * n, 6.4))

    for i in range(n):
        gt = gmap[i].cpu().numpy()
        ref = out["refined"][i].reshape(32, 16).cpu().numpy()
        rough = out["rough"][i].reshape(32, 16).cpu().numpy()

        for r, (img, title) in enumerate(((gt, "정답"), (rough, "rough"), (ref, "refined"))):
            ax[r, i].imshow(img, vmin=-1, vmax=1, cmap="viridis")
            ax[r, i].set_title("env %d %s" % (i, title), fontsize=7)
            ax[r, i].axis("off")

    os.makedirs(os.path.dirname(args.png), exist_ok=True)
    fig.savefig(args.png, dpi=110)
    err = float((out["refined"].reshape(-1, 32, 16) - gmap).abs().mean())
    print(f"[PROBE] mean |refined - gt| {err:.4f} after {args.iters} iters; png {args.png}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
