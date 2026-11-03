"""Capture exact EX-40 m6000 perception inputs from short Isaac evaluations.

One environment is moved between a flat tile, rough L0 and stairs L2.  Each
map mode has a fresh perception state.  This is a parity fixture, not a judge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_SHA = "d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5"
MODES = ("eval_pred", "probe_prop_only", "eval_gt")
CASES = (("flat", 0, 0), ("rough_L0", 0, 1), ("stairs_L2", 2, 2))
INPUTS = ("obs45", "hist", "depth2", "h_prop", "h_terr", "depth_tick",
          "first_after_reset", "use_gt", "gt_map")
OUTPUTS = ("action", "h_prop_next", "h_terr_next", "recon_map")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terrain_plan():
    """EX-40 continuous geometry, with a zero-noise flat reference tile."""
    import copy

    from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains
    from foothold_s2.terrains.columns import column_types

    source = continuous_subterrains()
    flat = copy.deepcopy(source["random_rough"])
    flat.noise_range = (0.0, 0.0)
    flat.proportion = 1.0 / 3
    rough = copy.deepcopy(source["random_rough"])
    rough.proportion = 1.0 / 3
    stairs = copy.deepcopy(source["stage_stairs"])
    stairs.proportion = 1.0 / 3
    tiles = {"flat": flat, "random_rough": rough, "stage_stairs": stairs}
    generator = build_generator(tiles, 3, seed=42)
    names = column_types({key: value.proportion for key, value in tiles.items()}, 3)
    if names != ["flat", "random_rough", "stage_stairs"]:
        raise RuntimeError(f"terrain columns changed: {names!r}")
    return generator, names


def select_tile(raw, level: int, col: int) -> None:
    import torch

    terrain = raw.scene.terrain
    terrain.terrain_levels[:] = level
    terrain.terrain_types[:] = col
    origins = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    terrain.env_origins[:] = origins
    raw.scene.env_origins[:] = origins
    if int(terrain.terrain_levels[0]) != level or int(terrain.terrain_types[0]) != col:
        raise RuntimeError("terrain selection did not stick")
    if not torch.equal(raw.scene.env_origins, terrain.env_origins):
        raise RuntimeError("scene and terrain origins differ")


def tensor_copy(tensor):
    return tensor.detach().cpu().numpy().copy()


def capture(checkpoint: Path, output: Path, device: str, app) -> dict:
    import torch
    import gymnasium as gym

    import isaaclab_tasks  # noqa: F401
    from isaaclab_tasks.utils import load_cfg_from_registry
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

    import foothold_s2.sb_tasks  # noqa: F401
    from foothold_s2.eval import adapters, map_mode_cells

    task = "FootholdS2-Go2-S2-SB-v0"
    env_cfg = load_cfg_from_registry(task, "env_cfg_entry_point")
    agent_cfg = load_cfg_from_registry(task, "rsl_rl_cfg_entry_point")
    env_cfg.seed = 42
    agent_cfg.seed = 42
    env_cfg.scene.num_envs = 1
    env_cfg.sim.device = device
    agent_cfg.device = device
    generator, names = terrain_plan()
    env_cfg.scene.terrain.terrain_generator = generator
    for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass",
                 "base_com", "push_robot", "base_external_force_torque"):
        if getattr(env_cfg.events, name, None) is not None:
            setattr(env_cfg.events, name, None)
    if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
        env_cfg.actions.joint_pos.max_delay_s = 0.0
    for name in ("terrain_levels", "command_range", "penalty_on"):
        if hasattr(env_cfg.curriculum, name):
            setattr(env_cfg.curriculum, name, None)
    env_cfg.commands.base_velocity.resampling_time_range = (1e9, 1e9)
    torch.manual_seed(42)
    env = RslRlVecEnvWrapper(gym.make(task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
    raw = env.unwrapped
    term = raw.command_manager.get_term("base_velocity")
    map_mode_cells.disable_heading_for_fixed_eval(term)
    runner, saved = adapters.load_s2_runner(env, agent_cfg.to_dict(), checkpoint, device)
    if int(saved.get("iter", -1)) != 6000 or runner.pcfg.get("est_mode") != "learned":
        raise RuntimeError("not the measured EX-40 m6000 learned policy")
    if runner.pcfg.get("map_input") != "reconstruction" or runner.perception.cfg.force_gt is not True:
        raise RuntimeError("m6000 map contract changed")
    output.mkdir(parents=True, exist_ok=False)
    original_advance = runner.perception._advance
    latest: dict = {}

    def tap(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *extra):
        if extra:
            raise RuntimeError("unexpected per-env map-off argument in parity capture")
        latest.clear()
        latest.update(dict(zip(INPUTS[1:], map(tensor_copy,
                     (hist, depth2, h_prop, h_terr, tick, first, use_gt, gt_map)))))
        hp, ht, out = original_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)
        latest.update({"h_prop_next": tensor_copy(hp), "h_terr_next": tensor_copy(ht),
                       "recon_map": tensor_copy(out["refined"])})
        return hp, ht, out

    runner.perception._advance = tap
    receipt = {"format": "ex40-real20-capture/1", "checkpoint": str(checkpoint),
               "checkpoint_sha256": sha256(checkpoint), "task": task, "device": device,
               "steps_per_case": 20, "seed": 42, "terrain_columns": names,
               "cases": {}, "source": str(Path(__file__).resolve()),
               "source_sha256": sha256(Path(__file__))}
    try:
        for case, level, col in CASES:
            for mode in MODES:
                torch.manual_seed(42)
                env.reset()
                select_tile(raw, level, col)
                env.reset()
                select_tile(raw, level, col)
                if (int(raw.scene.terrain.terrain_levels[0]) != level
                        or int(raw.scene.terrain.terrain_types[0]) != col):
                    raise RuntimeError("terrain changed across reset")
                policy = adapters.S2Policy(runner, 1, z_mode="mean", act_mode="mean", map_mode=mode)
                if (mode == "probe_prop_only") != bool(runner.perception.ie.mask_map_tokens):
                    raise RuntimeError("map-off attention flag differs")
                obs = env.get_observations()
                rows = []
                done_count = 0
                for step in range(20):
                    term.vel_command_b[:, :3] = torch.tensor((0.5, 0.0, 0.0), device=raw.device)
                    map_mode_cells.assert_heading_off_for_fixed_eval(term)
                    obs45, _, _, _, _, _ = runner._split(obs.to(runner.device))
                    action = policy(obs)
                    if set(latest) != set(INPUTS[1:]) | set(OUTPUTS[1:]):
                        raise RuntimeError(f"capture missed an input or output at {case}/{mode}/{step}")
                    row = {"obs45": tensor_copy(obs45), **latest, "action": tensor_copy(action)}
                    if bool(row["use_gt"][0]) != (mode == "eval_gt"):
                        raise RuntimeError("map mode GT selection differs")
                    if step == 0 and not bool(row["first_after_reset"][0]):
                        raise RuntimeError("first step lacks reset flag")
                    rows.append(row)
                    obs, _, dones, _ = env.step(action)
                    done_count += int(dones[0])
                    policy.reset(dones)
                arrays = {f"step{step:02d}_{name}": value for step, row in enumerate(rows)
                          for name, value in row.items()}
                path = output / f"{case}_{mode}.npz"
                import numpy as np
                np.savez_compressed(path, **arrays)
                receipt["cases"][f"{case}/{mode}"] = {
                    "path": str(path), "sha256": sha256(path), "resets": done_count,
                    "level": level, "terrain_kind": names[col],
                    "use_gt_steps": sum(bool(r["use_gt"][0]) for r in rows)}
                print(json.dumps({"captured": f"{case}/{mode}", "steps": 20, "resets": done_count}), flush=True)
        # Isaac's app.close() can end the process, so publish before closing it.
        (output / "capture.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    finally:
        env.close()
        app.close()
    return receipt


def main() -> int:
    # record_c_layer.py:277 documents a Windows access violation when this
    # dependency is imported after Kit.  Import it before AppLauncher.
    import tensordict  # noqa: F401
    from isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA)
    parser.add_argument("--output", type=Path, required=True)
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.checkpoint.is_file() and sha256(args.checkpoint) != args.expected_sha256:
        raise ValueError("checkpoint SHA mismatch")
    if args.output.exists():
        raise FileExistsError(args.output)
    if not args.headless or not args.enable_cameras or args.device not in ("cuda:0", "cuda:1"):
        raise ValueError("capture requires --headless --enable_cameras --device cuda:0|cuda:1")
    app = AppLauncher(args).app
    capture(args.checkpoint, args.output, args.device, app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
