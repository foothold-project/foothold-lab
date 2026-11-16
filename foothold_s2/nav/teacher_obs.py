"""teacher 관측 조립 (설계 §3 N2 · PLAN-HIPAN-V2 M7 · 21 §2). numpy 만 (Kit 없음).

논문 teacher 관측: 3D 점유 14 x 11 x 11 + 2.5D 고도 31 x 21 (둘 다 0.1 m) / 상위 고유감각 o_p (= 하위 o_p + 직전 명령 c_{t-1}) /
특권 운동 상태 x_m / 부목표 상대 위치. 지도는 `teacher_maps` 가 방 격자에서 몸 yaw 정렬로 잘라 낸다 (광선 아님).

가정 (논문이 값을 적지 않은 것 · `TeacherObsLayout` 에 모음):
  o_p = 하위 관측의 앞 45 칸 (`NavState.proprio`) · x_m = [몸통 선속도 3, 각속도 3] (몸 틀) · 부목표 상대 위치 = 몸 틀 (x 앞, y 왼쪽) 2 칸, 방 틀에서 yaw 로 돌림.
환경은 방마다 다른 격자를 읽는다: env 마다 방 번호 `room_id` 로 가른다. 방 틀 위치 = env 원점 기준 위치 + `ROOM_ORIGIN_XY` (방 메시는 방 중심이 env 원점, `room_generator.write_room`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foothold_s2.nav import room_generator as rg
from foothold_s2.nav import teacher_maps as tm

ROOM_ORIGIN_XY = np.array([rg.ROOM_M / 2, rg.ROOM_M / 2])


@dataclass(frozen=True)
class TeacherObsLayout:
    o_p: int = 45
    c_prev: int = 3
    x_m: int = 6
    subgoal: int = 2
    occ: tuple = (14, 11, 11)
    elev: tuple = (31, 21)

    @property
    def sizes(self) -> dict:
        return {"o_p": self.o_p, "c_prev": self.c_prev, "x_m": self.x_m, "subgoal": self.subgoal,
                "occ": int(np.prod(self.occ)), "elev": int(np.prod(self.elev))}

    @property
    def total(self) -> int:
        return sum(self.sizes.values())

    @property
    def offsets(self) -> dict:
        out, at = {}, 0
        for name, size in self.sizes.items():
            out[name] = (at, at + size)
            at += size
        return out


def yaw_from_quat_wxyz(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=np.float64)
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    return np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def to_room_frame(pos_local: np.ndarray) -> np.ndarray:
    p = np.array(pos_local, dtype=np.float64, copy=True)
    p[:, :2] += ROOM_ORIGIN_XY
    return p


def subgoal_in_body(pos_xy: np.ndarray, yaw: np.ndarray, subgoal_xy: np.ndarray) -> np.ndarray:
    """방 틀 부목표 -> 몸 틀 (x 앞, y 왼쪽). (n, 2)."""
    d = np.asarray(subgoal_xy, dtype=np.float64) - np.asarray(pos_xy, dtype=np.float64)
    c, s = np.cos(yaw), np.sin(yaw)
    return np.stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]], axis=1)


def build(voxels: dict, room_id, state, c_prev, subgoal_xy, layout: TeacherObsLayout = TeacherObsLayout(),
          map_cfg: tm.TeacherMapConfig = tm.TeacherMapConfig()) -> dict:
    """(부분 dict, 평탄 (n, total) float32). voxels = {방 번호: RoomVoxels}. state = `NavState`. subgoal_xy = 방 틀 (n, 2)."""
    n = len(state.pos_local)
    room_id = np.asarray(room_id)
    c_prev = np.asarray(c_prev, dtype=np.float64)
    subgoal_xy = np.asarray(subgoal_xy, dtype=np.float64)
    if room_id.shape != (n,) or c_prev.shape != (n, layout.c_prev) or subgoal_xy.shape != (n, 2) or state.proprio.shape != (n, layout.o_p):
        raise ValueError("room_id (n,), c_prev (n, 3), subgoal_xy (n, 2) and a state with proprio (n, 45) are required")
    if not set(np.unique(room_id)) <= set(voxels):
        raise ValueError(f"room_id names rooms without voxels: {sorted(set(np.unique(room_id)) - set(voxels))}")
    pos = to_room_frame(state.pos_local)
    yaw = yaw_from_quat_wxyz(state.quat_w)
    occ = np.empty((n, *layout.occ), bool)
    elev = np.empty((n, *layout.elev), np.float32)
    for rid in np.unique(room_id):
        idx = np.flatnonzero(room_id == rid)
        occ[idx] = tm.crop_occupancy(voxels[int(rid)], pos[idx], yaw[idx], map_cfg)
        elev[idx] = tm.crop_elevation(voxels[int(rid)], pos[idx], yaw[idx], map_cfg)
    parts = {"o_p": state.proprio.astype(np.float32), "c_prev": c_prev.astype(np.float32),
             "x_m": np.concatenate([state.vel_b, state.ang_vel_b], axis=1).astype(np.float32),
             "subgoal": subgoal_in_body(pos[:, :2], yaw, subgoal_xy).astype(np.float32),
             "occ": occ, "elev": elev}
    flat = np.concatenate([parts[k].reshape(n, -1).astype(np.float32) for k in layout.sizes], axis=1)
    if flat.shape[1] != layout.total or not np.isfinite(flat).all():
        raise RuntimeError("teacher observation has the wrong width or non-finite values")
    return {"parts": parts, "flat": flat, "pos_room": pos, "yaw": yaw}
