"""Isaac-free RayCaster interface. The caller supplies height_scanner and base yaw."""
from __future__ import annotations

import math
from typing import Protocol

import torch

import s2_map_obs as M


class RayData(Protocol):
    pos_w: torch.Tensor
    ray_hits_w: torch.Tensor


class RayCaster(Protocol):
    cfg: object
    data: RayData


class AdapterFault(RuntimeError):
    pass


def validate_scanner_config(cfg) -> None:
    """Testable E1 scan contract; 20 m applies to ray starts, never pos_w."""
    pattern = cfg.pattern_cfg
    checks = (
        (cfg.ray_alignment == "yaw", "ray_alignment"),
        (pattern.ordering == M.GRID_ORDERING, "ray ordering"),
        (tuple(pattern.size) == M.GRID_SIZE, "grid size"),
        (float(pattern.resolution) == M.GRID_RESOLUTION, "grid resolution"),
        (tuple(pattern.direction) == (0.0, 0.0, -1.0), "ray direction"),
        (tuple(cfg.offset.pos) == (0.0, 0.0, 20.0), "ray start offset"),
    )
    for okay, label in checks:
        if not okay:
            raise AdapterFault(f"height_scanner {label} differs from pinned E1 contract")
    if M.grid_ray_xy_body().shape != (M.NUM_RAYS, 2):
        raise AdapterFault("ray count or xy ordering changed")


def expected_world_xy(pos_w: torch.Tensor, yaw_w: torch.Tensor) -> torch.Tensor:
    """Map ray index k to yaw-aligned world XY, x varying fastest."""
    if pos_w.shape[-1] != 3 or yaw_w.shape != pos_w.shape[:1]:
        raise AdapterFault("base position or yaw shape invalid")
    if not bool(torch.isfinite(pos_w).all()) or not bool(torch.isfinite(yaw_w).all()):
        raise AdapterFault("base position or yaw nonfinite")
    xy = M.grid_ray_xy_body().to(device=pos_w.device, dtype=pos_w.dtype)
    x, y = xy[:, 0], xy[:, 1]
    c, s = yaw_w.cos()[:, None], yaw_w.sin()[:, None]
    world = torch.stack((pos_w[:, 0:1] + c*x - s*y,
                         pos_w[:, 1:2] + s*x + c*y), dim=-1)
    if not bool(torch.isfinite(world).all()):
        raise AdapterFault("world xy transform nonfinite")
    return world


def yaw_from_quat_wxyz(quat: torch.Tensor) -> torch.Tensor:
    if quat.ndim != 2 or quat.shape[-1] != 4:
        raise AdapterFault("root quaternion must be [N,4] wxyz")
    if not bool(torch.isfinite(quat).all()):
        raise AdapterFault("root quaternion nonfinite")
    norm = torch.linalg.vector_norm(quat, dim=-1)
    if not bool(((norm-1).abs() <= 1e-3).all()):
        raise AdapterFault("root quaternion not unit normalized")
    w, x, y, z = quat.unbind(-1)
    yaw = torch.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
    if not bool(torch.isfinite(yaw).all()):
        raise AdapterFault("root yaw nonfinite")
    return yaw


def verify_hit_geometry(pos_w: torch.Tensor, ray_hits_w: torch.Tensor,
                        yaw_w: torch.Tensor, *, tolerance_m: float) -> None:
    if type(tolerance_m) not in (float, int) or not math.isfinite(tolerance_m) or tolerance_m <= 0:
        raise ValueError("positive finite geometry tolerance required")
    expected = expected_world_xy(pos_w, yaw_w)
    if ray_hits_w.shape != (pos_w.shape[0], M.NUM_RAYS, 3):
        raise AdapterFault("ray packet shape or order changed")
    finite = torch.isfinite(ray_hits_w).all(dim=-1)
    delta = (ray_hits_w[..., :2] - expected).abs()
    if not bool(torch.isfinite(delta[finite]).all()):
        raise AdapterFault("geometry transform nonfinite")
    if bool((finite[..., None] & (delta > tolerance_m)).any()):
        raise AdapterFault("ray ordering, yaw alignment or scan time mismatch")


def sample_map(sensor: RayCaster, *, mode: str, yaw_w: torch.Tensor,
               strict: bool, geometry_tolerance_m: float):
    """Use data.pos_w as-is. Isaac already applied offset to ray starts."""
    validate_scanner_config(sensor.cfg)
    pos_w, hits = sensor.data.pos_w, sensor.data.ray_hits_w
    verify_hit_geometry(pos_w, hits, yaw_w, tolerance_m=geometry_tolerance_m)
    _, _, faults = M.classify_rays(pos_w, hits)
    try:
        map_value, checked = M.map_obs(mode, pos_w, hits, strict=strict)
    except M.MapObsFault as ex:
        ex.faults = faults
        raise
    return map_value, checked


def training_map(sensor: RayCaster, *, mode: str, yaw_w: torch.Tensor,
                 geometry_tolerance_m: float):
    return sample_map(sensor, mode=mode, yaw_w=yaw_w, strict=True,
                      geometry_tolerance_m=geometry_tolerance_m)
