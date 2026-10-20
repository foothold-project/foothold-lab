"""G3 발 가장자리 보상이 실제로 값을 내는지 (무작위 행동으로 몇 백 스텝). isaac311 python 으로."""

import argparse
import os
import sys

import tensordict  # noqa: F401
import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--steps", type=int, default=400)
parser.add_argument("--num_envs", type=int, default=128)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

from foothold_s2.tasks.s2_env import FootholdS2Env  # noqa: E402
from foothold_s2.tasks.s2_env_cfg import FootholdS2G3EnvCfg  # noqa: E402


def main():
    cfg = FootholdS2G3EnvCfg()
    cfg.scene.num_envs = args.num_envs
    cfg.sim.device = args.device
    env = FootholdS2Env(cfg)
    env.reset()
    rm = env.reward_manager
    k = rm.active_terms.index("foot_edge")
    w = rm.get_term_cfg("foot_edge").weight
    term = env.command_manager.get_term("base_velocity")
    tot = torch.zeros(env.num_envs, device=env.device)
    hits = torch.zeros(env.num_envs, device=env.device)
    on_edge_sparse = 0

    for _ in range(args.steps):
        act = torch.randn(env.num_envs, 12, device=env.device) * 0.5
        env.step(act)
        v = rm._step_reward[:, k]
        tot += v
        hits += (v != 0).float()

    flag = term.is_flag_env
    grp = env.s2_tables.group_col[env.scene.terrain.terrain_types.cpu().numpy()]
    sparse = torch.as_tensor(grp != "continuous", device=env.device)
    print(f"[PROBE] weight {w}; mean step reward (per sec) all {float(tot.mean()) / args.steps / env.step_dt:.4f}")

    for name, m in (("sparse tile envs", sparse), ("continuous tile envs", ~sparse)):
        n = int(m.sum())
        print(f"[PROBE] {name}: n {n} mean total {float(tot[m].mean()) if n else 0:.4f} "
              f"nonzero-step fraction {float(hits[m].mean() / args.steps) if n else 0:.4f} any negative {bool((tot[m] < 0).any()) if n else False} any positive {bool((tot[m] > 0).any()) if n else False}")

    for name, m in (("flag envs", flag), ("non-flag envs", ~flag)):
        n = int(m.sum())
        print(f"[PROBE] {name}: n {n} mean total {float(tot[m].mean()) if n else 0:.4f}")

    del on_edge_sparse

    # 강제 배치: 듬성한 칸 env 의 몸을 칸 좌표 x 0.7~1.3 (출발 단 모서리 x = 1.0 둘레)에 걸쳐 놓고 가만히 세워 둔다
    ids = sparse.nonzero(as_tuple=False).flatten()
    xs = torch.linspace(0.7, 1.3, len(ids), device=env.device)
    terrain = env.scene.terrain
    asset = env.scene["robot"]
    state = asset.data.root_state_w.clone()
    state[ids, 0] = terrain.terrain_levels[ids].float() * 8.0 + xs
    state[ids, 1] = terrain.terrain_types[ids].float() * 8.0 + 4.0
    state[ids, 2] = 0.40
    state[ids, 3:7] = torch.tensor([1.0, 0.0, 0.0, 0.0], device=env.device)
    state[ids, 7:] = 0.0
    asset.write_root_state_to_sim(state[ids], env_ids=ids)
    got = torch.zeros(len(ids), device=env.device)

    for _ in range(40):
        env.step(torch.zeros(env.num_envs, 12, device=env.device))
        got += rm._step_reward[ids, k]

    nz = got != 0
    print(f"[PROBE] forced placement near the platform edge: {int(nz.sum())} of {len(ids)} envs got a nonzero edge reward, "
          f"min total {float(got.min()):.3f}, max total {float(got.max()):.3f}, any positive {bool((got > 0).any())}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
