"""CPU-testable depth-camera removal for the opt-in GT-only basic-gait segment."""

import torch


def zero_depth_obs(env):
    return torch.zeros((env.num_envs, 3600), dtype=torch.float32, device=env.device)


def disable_depth_camera_for_gt(env_cfg) -> None:
    if env_cfg.scene.depth_cam is None or env_cfg.observations.depth is None:
        raise ValueError("GT-only mode needs the original START depth observation contract")
    env_cfg.scene.depth_cam = None
    env_cfg.observations.depth.depth.func = zero_depth_obs
    env_cfg.observations.depth.depth.params = {}
