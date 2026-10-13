# -*- coding: utf-8 -*-
"""S2 지도 입력: RayCaster 자료 (센서 위치 · 맞은 점) -> height 187 · mask 187 (B) 또는 상수 (A).

분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 (CPU · 학습 없음)
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 2026-10-13 19:21
근거: inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md 3 절 (A 의 상수 · B 의 의미) · 4 절 (T1 ~ T3)
      E1 params/env.yaml 446 ~ 480 (height_scanner: base 에 붙음 · offset z 20 · ray_alignment yaw · grid 1.6 x 1.0 · 0.1 · xy)
      IsaacLab envs/mdp/observations.py 292 ~ 300 (height_scan = pos_w.z - ray_hits_w.z - offset · offset 기본 0.5)
      IsaacLab sensors/ray_caster/ray_caster.py 218 ~ 224 (cfg.offset 은 ray_starts 에만 더함) · 238 ~ 248 (pos_w = base 위치 + drift)
      IsaacLab sensors/ray_caster/patterns/patterns.py grid_pattern · utils/warp/ops.py raycast_mesh (안 맞으면 inf)
요지: B 는 height = clip(센서 z - 맞은 점 z - 0.5, -1, 1) 과 mask (맞았고 몸 아래 1 m 안이면 1) 를 준다.
      안 맞음 (inf · nan) 과 1 m 보다 깊음은 mask 0 · height 1 (「깊음」 쪽). A 는 지형과 상관없이 height 0 · mask 0.
상태: CPU 시험 (test_s2.py) · 변이 (mutate_s2.py) 만 거침. Isaac 안에서 실제 RayCaster 자료로 돌려 본 적 없음 (미확인)

지도 입력 배치: m = [height 187, mask 187] (열 0 ~ 186 이 height · 187 ~ 373 이 mask). 광선 순서는 센서 순서 그대로
(grid_pattern ordering xy: x 가 가장 빨리 돈다 · 광선 k 의 몸체 좌표 = (x[k % 17], y[k // 17])).
"""
from __future__ import annotations

import math

import torch

# ------------------------------------------------------------------ 설정 (E1 params/env.yaml height_scanner 에서 옮김)
GRID_SIZE = (1.6, 1.0)        # pattern_cfg.size (x 길이, y 너비) [m]
GRID_RESOLUTION = 0.1         # pattern_cfg.resolution [m]
GRID_ORDERING = "xy"          # pattern_cfg.ordering
NUM_RAYS = 187                # 17 x 11
HEIGHT_OFFSET = 0.5           # isaaclab height_scan 의 offset 기본값 (env.yaml params 에 offset 없음)
HEIGHT_CLIP = (-1.0, 1.0)     # 설계 3 절 B 의 clip (critic 의 height_scan 항과 같은 범위 · 단 critic 은 이 뒤에 x 2.5)
MASK_MAX_DEPTH = 1.0          # 센서 (base) 아래 이 깊이 [m] 까지만 mask 1 (경계 포함)
INVALID_HEIGHT = 1.0          # mask 0 칸의 height (「깊음」 쪽)
A_HEIGHT = 0.0                # A 의 상수 height
A_MASK = 0.0                  # A 의 상수 mask (mask 만 실제 값이면 A 가 구멍을 본다 · ASTRA 11 2.2)
MAP_DIM = 2 * NUM_RAYS        # 374


def grid_ray_xy_body(size=GRID_SIZE, resolution=GRID_RESOLUTION, ordering=GRID_ORDERING) -> torch.Tensor:
    """광선 k 의 몸체 (yaw 정렬) 좌표 (x, y) [R, 2]. IsaacLab grid_pattern 과 같은 식 (offset z 20 은 뺌).

    ordering xy 는 torch.meshgrid(indexing="xy") 라서 x 가 가장 빨리 돈다. yx 는 indexing="ij" (y 가 가장 빨리).
    """
    if ordering not in ("xy", "yx"):
        raise ValueError(f"ordering 은 xy 또는 yx: {ordering!r}")
    indexing = "xy" if ordering == "xy" else "ij"
    x = torch.arange(start=-size[0] / 2, end=size[0] / 2 + 1.0e-9, step=resolution)
    y = torch.arange(start=-size[1] / 2, end=size[1] / 2 + 1.0e-9, step=resolution)
    gx, gy = torch.meshgrid(x, y, indexing=indexing)
    return torch.stack([gx.flatten(), gy.flatten()], dim=-1)


def height_and_mask(sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """B 의 height [N, R] 와 mask [N, R] (0 또는 1, height 와 같은 dtype).

    sensor_pos_w: [N, 3] RayCaster data.pos_w (base 위치. cfg.offset z 20 은 들어 있지 않다)
    ray_hits_w:   [N, R, 3] RayCaster data.ray_hits_w (안 맞은 광선은 inf)
    """
    if sensor_pos_w.dim() != 2 or sensor_pos_w.shape[-1] != 3:
        raise ValueError(f"sensor_pos_w 모양 [N, 3] 이어야 함: {tuple(sensor_pos_w.shape)}")
    if ray_hits_w.dim() != 3 or ray_hits_w.shape[-1] != 3 or ray_hits_w.shape[0] != sensor_pos_w.shape[0]:
        raise ValueError(f"ray_hits_w 모양 [N, R, 3] 이어야 함: {tuple(ray_hits_w.shape)}")
    sensor_z = sensor_pos_w[:, 2:3]
    hit_z = ray_hits_w[..., 2]
    depth = sensor_z - hit_z                      # 센서 (base) 아래 깊이. 양수 = 아래
    raw = depth - HEIGHT_OFFSET                   # isaaclab height_scan 과 같은 식
    valid = torch.isfinite(depth) & (depth <= MASK_MAX_DEPTH)
    height = torch.where(valid, raw.clamp(HEIGHT_CLIP[0], HEIGHT_CLIP[1]), torch.full_like(raw, INVALID_HEIGHT))
    mask = valid.to(height.dtype)
    return height, mask


def map_obs_b(sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor) -> torch.Tensor:
    """B 의 지도 입력 [N, 374] = [height, mask]."""
    height, mask = height_and_mask(sensor_pos_w, ray_hits_w)
    return torch.cat([height, mask], dim=-1)


def map_obs_a(num_envs: int, num_rays: int = NUM_RAYS, device=None, dtype=torch.float32) -> torch.Tensor:
    """A 의 지도 입력 [N, 374]: height 와 mask 모두 상수. 지형 자료를 받지 않는다."""
    height = torch.full((num_envs, num_rays), A_HEIGHT, device=device, dtype=dtype)
    mask = torch.full((num_envs, num_rays), A_MASK, device=device, dtype=dtype)
    return torch.cat([height, mask], dim=-1)


def map_obs(mode: str, sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor) -> torch.Tensor:
    """mode 에 따른 지도 입력. A 는 모양 (env 수 · 광선 수) 만 쓰고 값은 버린다."""
    if mode == "B":
        return map_obs_b(sensor_pos_w, ray_hits_w)
    if mode == "A":
        if ray_hits_w.dim() != 3 or ray_hits_w.shape[0] != sensor_pos_w.shape[0]:
            raise ValueError(f"ray_hits_w 모양 [N, R, 3] 이어야 함: {tuple(ray_hits_w.shape)}")
        return map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], device=ray_hits_w.device, dtype=ray_hits_w.dtype)
    raise ValueError(f"mode 는 A 또는 B: {mode!r}")


def is_a_constant(m: torch.Tensor, num_rays: int = NUM_RAYS) -> bool:
    """지도 입력이 A 의 상수와 같은가 (height 칸은 A_HEIGHT · mask 칸은 A_MASK)."""
    if m.shape[-1] != 2 * num_rays:
        return False
    return bool(torch.all(m[..., :num_rays] == A_HEIGHT)) and bool(torch.all(m[..., num_rays:] == A_MASK))


def ray_hits_from_terrain(sensor_pos_w: torch.Tensor, yaw: torch.Tensor, terrain_z) -> torch.Tensor:
    """시험용 CPU RayCaster 흉내: ray_alignment yaw 로 광선을 놓고, 세계 (x, y) 에서 terrain_z(x, y) 를 맞은 점 z 로 준다.

    terrain_z 가 inf · nan 을 주면 그 광선은 안 맞은 것으로 보고 xyz 를 모두 inf 로 둔다 (raycast_mesh 와 같은 꼴).
    실제 RayCaster 의 mesh 교차는 흉내 내지 않는다 (수직 광선 · 높이장 지형만).
    """
    xy_b = grid_ray_xy_body().to(dtype=sensor_pos_w.dtype, device=sensor_pos_w.device)   # [R, 2]
    c = torch.cos(yaw).unsqueeze(-1)
    s = torch.sin(yaw).unsqueeze(-1)
    xw = sensor_pos_w[:, 0:1] + c * xy_b[:, 0] - s * xy_b[:, 1]
    yw = sensor_pos_w[:, 1:2] + s * xy_b[:, 0] + c * xy_b[:, 1]
    z = terrain_z(xw, yw).to(sensor_pos_w.dtype)
    hits = torch.stack([xw, yw, z], dim=-1)
    miss = ~torch.isfinite(z)
    return torch.where(miss.unsqueeze(-1), torch.full_like(hits, math.inf), hits)
