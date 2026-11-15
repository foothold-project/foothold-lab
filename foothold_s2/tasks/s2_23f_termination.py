"""TopDown-only fall termination relative to each generated tile's support plane."""

import torch

from foothold_s2.eval import start_sheet


def below_plane(feet_z: torch.Tensor, plane_z: torch.Tensor, margin: float) -> torch.Tensor:
    if feet_z.ndim != 2 or plane_z.shape != feet_z.shape[:1]:
        raise ValueError("expected [env, foot] and [env]")
    return (feet_z < plane_z[:, None] - margin).any(dim=1)


def world_support_plane(world_origin_z: torch.Tensor, local_origin_z: float,
                        local_support_z: float) -> torch.Tensor:
    return world_origin_z - local_origin_z + local_support_z


def foot_below_support_plane(env, sensor_cfg, asset_cfg, margin: float = 0.25):
    """Use generated start/goal support surface, not a pit-floor ray or fixed world zero."""
    del sensor_cfg
    if not hasattr(env, "s2_tables"):
        raise RuntimeError("TopDown support-plane table not bound")
    terrain = env.scene.terrain
    rows, cols = terrain.terrain_levels.long(), terrain.terrain_types.long()
    # The generator's origin is a local tile spawn coordinate. The terrain
    # manager adds the mesh world transform to that local origin.
    world_origin_z = terrain.terrain_origins[rows, cols, 2]
    # make_tile origin z is 0.0; sheet generator start/goal plateau uses PLATFORM_Z.
    plane_z = world_support_plane(world_origin_z, 0.0, start_sheet.PLATFORM_Z)
    feet_z = env.scene[asset_cfg.name].data.body_pos_w[:, asset_cfg.body_ids, 2]
    return below_plane(feet_z, plane_z, margin)
