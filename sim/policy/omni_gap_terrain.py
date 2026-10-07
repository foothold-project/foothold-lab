# -*- coding: utf-8 -*-
"""스폰을 둘러싼 바닥 없는 고리와 회전 도랑을 만드는 학습 지형.

분류: 실험
작성: Codex 세션 (오흥재 지시) · 2026-09-20 09:33
근거: inbox/jay/20260920-FG-design.md v1.1 · fg_task1.md 0·1절
요지: 기본 ring 으로 사방 도랑을 만들고 rotated 를 비교군으로 남긴다
상태: 구현 · 물리 학습 미실행
판: v1.0

반지름 2.50 m 는 기존 조주 1.50 m 보다 길어 초기 방향 전환 여유를 둔다.
최대 폭에서 바깥 착지판은 4.0 - (2.5 + 0.40/2) = 1.30 m 남는다.
vx 하한 0.4 에서 중심선까지 6.25 초로 20 초의 31.25 % 다. 최대 바깥
반지름 2.70 m 는 승급 거리 4.0 m 안쪽이다. 실제 정책의 도달 보장은 아니다.
평가 floating_ring 과 모양이 닮는 교란은 후속 판정에서 별도로 표시한다.
"""

from __future__ import annotations

import numpy as np
import trimesh

from isaaclab.utils import configclass

from .gap_terrain import ForwardGapTerrainCfg, forward_gap_terrain


def _slab(polygon: np.ndarray, thickness: float) -> trimesh.Trimesh:
    """반시계 방향 볼록 다각형을 z=-두께부터 0 까지 닫힌 슬랩으로 만든다."""
    count = len(polygon)
    vertices = np.vstack((
        np.column_stack((polygon, np.zeros(count))),
        np.column_stack((polygon, np.full(count, -thickness))),
    ))
    faces = []
    for index in range(1, count - 1):
        faces.extend(((0, index, index + 1),
                      (count, count + index + 1, count + index)))
    for index in range(count):
        next_index = (index + 1) % count
        faces.extend(((index, count + index, count + next_index),
                      (index, count + next_index, next_index)))
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)


def omni_gap_terrain(
    difficulty: float, cfg: "OmniGapTerrainCfg",
) -> tuple[list[trimesh.Trimesh], np.ndarray]:
    """윗면 z=0 인 슬랩만 만들며 도랑 아래에는 바닥을 두지 않는다."""
    size = np.asarray(cfg.size, dtype=float)
    lo, hi = cfg.gap_width_range
    if (size.shape != (2,) or not np.all(np.isfinite(size)) or np.any(size <= 0)
            or not np.isfinite([lo, hi, cfg.slab_thickness, difficulty]).all()
            or not 0 < lo <= hi or cfg.slab_thickness <= 0):
        raise ValueError("타일 크기 · 틈 폭 · 두께 · 난이도를 확인하십시오")
    center = np.r_[size / 2, 0.0]

    if cfg.mode == "rotated":
        meshes, origin = forward_gap_terrain(difficulty, cfg)
        angle = float(np.random.uniform(-np.pi, np.pi))
        transform = trimesh.transformations.rotation_matrix(angle, (0, 0, 1), center)
        for mesh in meshes:
            mesh.apply_transform(transform)
            mesh.metadata["gap_rotation_rad"] = angle
        origin = trimesh.transform_points(origin[None, :], transform)[0]
        return meshes, origin
    if cfg.mode != "ring":
        raise ValueError(f"지원하지 않는 도랑 모드: {cfg.mode!r}")

    width = lo + float(np.clip(difficulty, 0.0, 1.0)) * (hi - lo)
    inner = cfg.ring_radius - width / 2
    outer = cfg.ring_radius + width / 2
    count = cfg.num_sides
    if (not np.isfinite(cfg.ring_radius) or inner <= 0 or outer >= min(size) / 2
            or not isinstance(count, (int, np.integer)) or count < 8):
        raise ValueError("고리 반지름과 폭은 타일 안에 있어야 하며 변 수는 8 이상의 정수여야 합니다")

    angles = np.arange(count) * (2 * np.pi / count)
    unit = np.column_stack((np.cos(angles), np.sin(angles)))
    meshes = [_slab(center[:2] + inner * unit, cfg.slab_thickness)]
    # 각 고리 변과 타일 경계 사이를 채운다. 섹터 안에 드는 사각형 꼭짓점도
    # 넣어 모서리의 빈 삼각형을 막는다. 직사각 타일과 임의 변 수도 지원한다.
    half = size / 2
    corners = np.array(((half[0], half[1]), (-half[0], half[1]),
                        (-half[0], -half[1]), (half[0], -half[1])))
    corner_angles = np.mod(np.arctan2(corners[:, 1], corners[:, 0]), 2 * np.pi)
    for index in range(count):
        next_index = (index + 1) % count
        start = angles[index]
        end = start + 2 * np.pi / count
        directions = unit[[index, next_index]]
        scale = np.min(half / np.maximum(np.abs(directions), 1e-15), axis=1)
        boundary = directions * scale[:, None]
        inside = np.flatnonzero((corner_angles > start + 1e-12)
                               & (corner_angles < end - 1e-12))
        inside = inside[np.argsort(corner_angles[inside])]
        polygon = np.vstack((outer * directions[0], boundary[0],
                             corners[inside], boundary[1], outer * directions[1]))
        meshes.append(_slab(polygon + center[:2], cfg.slab_thickness))
    return meshes, center


@configclass
class OmniGapTerrainCfg(ForwardGapTerrainCfg):
    """B 와 같은 폭 범위의 고리 도랑. rotated 는 기존 도랑을 그대로 회전한다."""

    function = omni_gap_terrain
    gap_width_range: tuple[float, float] = (0.15, 0.40)
    slab_thickness: float = 1.00
    mode: str = "ring"
    ring_radius: float = 2.50
    num_sides: int = 64
