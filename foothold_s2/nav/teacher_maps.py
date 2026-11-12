"""teacher 가 읽는 지도 둘 (PLAN-HIPAN-V2 §6.1 · M7 · 21 §2 관측). numpy 만, Kit 없음.

방 메시 (room_generator.Room) 에서 0.1 m voxel 점유 격자를 한 번 만들고, 로봇 자세 (위치 · yaw) 로 잘라 읽는다 (매 스텝 광선을 쏘지 않는다 · 계획 가정).
  - 3D 점유  14 x 11 x 11 (x 앞뒤 · y 좌우 · z 위아래), 0.1 m 셀, 몸 yaw 정렬.
  - 2.5D 고도 31 x 21, 0.1 m 셀, 몸 yaw 정렬. 값 = 그 칸의 가장 높은 점유 윗면 높이 - 로봇 몸 높이 (m).
창의 배치 (논문은 개수 14 x 11 x 11 · 31 x 21 · 0.1 m 만 적음 · 나머지는 모두 **가정**, TeacherMapConfig 에 모아 둠):
  3D: x -0.3~1.0 (앞쪽 치우침) · y +-0.5 · z -0.3~0.7 (몸 기준). 평지에 서 있으면 (몸 높이 0.34) 발 밑 바닥은 창 아래로 빠진다.
  2.5D: x -1.0~2.0 (앞쪽 치우침) · y +-1.0. 몸 위 z_cap (= 3D 창의 위 끝, 0.7 m) 보다 높은 점유는 무시 (머리 위 장애물이 바닥으로 읽히지 않게).
방 밖은 점유 (바깥 벽 너머). 셀 중심을 가장 가까운 voxel 로 읽는다 (보간 없음).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foothold_s2.nav import room_generator as rg

RES = rg.RES
Z_MIN = -1.2            # 구덩이 바닥 (PIT_DROP - 0.2) 이 들어오게
Z_MAX = 2.0             # 바깥 벽 높이
NZ = int(round((Z_MAX - Z_MIN) / RES))


@dataclass(frozen=True)
class TeacherMapConfig:
    occ_shape: tuple = (14, 11, 11)          # 논문
    elev_shape: tuple = (31, 21)             # 논문
    occ_center: tuple = (3, 5, 3)            # 몸 위치가 오는 셀 번호 (x y z) 가정: 앞쪽 치우침
    elev_center: tuple = (10, 10)            # 가정
    z_cap_m: float = 0.7                     # 2.5D 가 읽는 몸 위 한계 (3D 창 위 끝과 같게 · 가정)


class RoomVoxels:
    """0.1 m 점유 격자 (N, N, NZ) bool. 층 k 는 z in [Z_MIN + k RES, Z_MIN + (k+1) RES), 셀 중심이 안에 들면 점유."""

    def __init__(self, occ: np.ndarray):
        if occ.shape != (rg.N, rg.N, NZ) or occ.dtype != bool:
            raise ValueError(f"voxel grid must be bool {(rg.N, rg.N, NZ)}")
        self.occ = occ

    @classmethod
    def from_room(cls, room: rg.Room) -> "RoomVoxels":
        zc = Z_MIN + (np.arange(NZ) + 0.5) * RES                         # 층 중심 높이
        occ = zc[None, None, :] < room.height[:, :, None]                  # 바닥: 윗면 아래는 전부 채움 (구덩이는 PIT_DROP)
        for x0, x1, y0, y1, z0, z1 in room.boxes:
            sx, sy = rg._sl(x0, x1, y0, y1)
            layers = (zc >= z0 - 1e-9) & (zc < z1 - 1e-9)
            occ[sx, sy, :] |= layers[None, None, :]
        return cls(occ)


def _world_cells(pos_xy: np.ndarray, yaw: np.ndarray, fx: np.ndarray, fy: np.ndarray):
    """몸 틀 셀 중심 (fx, fy) (같은 모양 배열, m) -> 세계 셀 번호 (ix, iy) (N, ...)."""
    c, s = np.cos(yaw)[:, None, None], np.sin(yaw)[:, None, None]
    wx = pos_xy[:, 0, None, None] + c * fx[None] - s * fy[None]
    wy = pos_xy[:, 1, None, None] + s * fx[None] + c * fy[None]
    return np.floor(wx / RES).astype(np.int64), np.floor(wy / RES).astype(np.int64)


def _check(pose_xyz, yaw):
    p = np.atleast_2d(np.asarray(pose_xyz, float))
    y = np.atleast_1d(np.asarray(yaw, float))
    if p.ndim != 2 or p.shape[1] != 3 or y.shape != (p.shape[0],):
        raise ValueError("pose_xyz (N, 3) and yaw (N,) required")
    return p, y


def crop_occupancy(vox: RoomVoxels, pose_xyz, yaw, cfg: TeacherMapConfig = TeacherMapConfig()) -> np.ndarray:
    """(N, 14, 11, 11) bool. 방 밖 셀은 점유."""
    p, y = _check(pose_xyz, yaw)
    nx, ny, nz = cfg.occ_shape
    fx = (np.arange(nx) - cfg.occ_center[0]) * RES
    fy = (np.arange(ny) - cfg.occ_center[1]) * RES
    gx, gy = np.meshgrid(fx, fy, indexing="ij")
    ix, iy = _world_cells(p[:, :2], y, gx, gy)                              # (N, nx, ny)
    inside = (ix >= 0) & (ix < rg.N) & (iy >= 0) & (iy < rg.N)
    ixc, iyc = np.clip(ix, 0, rg.N - 1), np.clip(iy, 0, rg.N - 1)
    out = np.empty((len(p), nx, ny, nz), bool)
    for k in range(nz):
        iz = np.floor((p[:, 2] + (k - cfg.occ_center[2]) * RES - Z_MIN) / RES).astype(np.int64)
        val = vox.occ[ixc, iyc, np.clip(iz, 0, NZ - 1)[:, None, None]]
        cell = np.where(inside, val, True)                                  # 방 밖은 점유
        cell = np.where((iz >= NZ)[:, None, None] & inside, False, cell)    # 벽 위 하늘
        out[..., k] = np.where((iz < 0)[:, None, None], True, cell)         # 구덩이 바닥 아래는 땅
    return out


def crop_elevation(vox: RoomVoxels, pose_xyz, yaw, cfg: TeacherMapConfig = TeacherMapConfig()) -> np.ndarray:
    """(N, 31, 21) float32: 칸마다 (몸 위 z_cap 이하에서 가장 높은 점유 윗면) - 몸 높이. 점유가 없으면 Z_MIN - 몸 높이. 방 밖은 벽 높이 (z_cap 으로 자름)."""
    p, y = _check(pose_xyz, yaw)
    nx, ny = cfg.elev_shape
    fx = (np.arange(nx) - cfg.elev_center[0]) * RES
    fy = (np.arange(ny) - cfg.elev_center[1]) * RES
    gx, gy = np.meshgrid(fx, fy, indexing="ij")
    ix, iy = _world_cells(p[:, :2], y, gx, gy)
    inside = (ix >= 0) & (ix < rg.N) & (iy >= 0) & (iy < rg.N)
    col = vox.occ[np.clip(ix, 0, rg.N - 1), np.clip(iy, 0, rg.N - 1)]       # (N, nx, ny, NZ)
    zc = Z_MIN + (np.arange(NZ) + 0.5) * RES
    below = zc[None, None, None, :] <= (p[:, 2] + cfg.z_cap_m)[:, None, None, None]
    hit = col & below
    top_idx = np.where(hit.any(-1), NZ - 1 - np.argmax(hit[..., ::-1], axis=-1), -1)
    top = np.where(top_idx >= 0, Z_MIN + (top_idx + 1) * RES, Z_MIN)
    top = np.where(inside, top, np.minimum(rg.WALL_H, p[:, 2] + cfg.z_cap_m)[:, None, None])        # 방 밖 = 벽 (같은 z_cap 으로 자름)
    return (top - p[:, 2][:, None, None]).astype(np.float32)
