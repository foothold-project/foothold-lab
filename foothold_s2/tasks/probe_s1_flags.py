"""S1 깃발 열 위치 확인 (Kit). 깃발 env 의 깃발이 칸 가운데 기준 +0.5 ~ +3.5 m 인지."""

import argparse
import os
import sys

import tensordict  # noqa: F401
import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402

from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg  # noqa: E402


def main():
    cfg = FootholdS1aBlindEnvCfg()
    cfg.scene.num_envs = 64
    cfg.sim.device = args.device
    env = ManagerBasedRLEnv(cfg)
    env.reset()
    term = env.command_manager.get_term("base_velocity")
    ids = term.flag_ids
    flags = term.flag_state.flags[term._flag_row[ids]]
    rel = flags - env.scene.terrain.env_origins[ids, None, :2]
    print(f"[PROBE] flag envs {len(ids)}; offsets x min {float(rel[..., 0].min()):.3f} max {float(rel[..., 0].max()):.3f} "
          f"y abs max {float(rel[..., 1].abs().max()):.3f}; first flag offsets {sorted(set(round(float(v), 3) for v in rel[:, 0, 0]))}")
    print(f"[PROBE] flag_vmax {term.range_curriculum.flag_vmax} vmax_x {term.range_curriculum.vmax_x}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
