"""HiPAN 상위 5 차원 행동 [vx, vy, wz, dh, roll] (원문 126-133 행 · lead 2026-11-21 19:34 (3)). 기본 꺼짐: HIPAN_POSE_ACTIONS=1 일 때만.
꺼짐이면 상위 출력 3 칸 · 직전 명령 3 칸 · 보상 3 열 (지금 판과 같은 바이트).
켜짐이면: 출력 5 칸 · teacher 관측의 c_prev 5 칸 · 상위 보상 r4 · r5 · r6 이 5 열 (rewards_hl.reward_terms pose_active) ·
자세 두 칸은 원문 범위로 자른다 (높이 h ∈ [0.1, 0.4] m -> dh = h - H0 · roll ∈ [-1, 1] rad · 2604.26504.txt:635).
하위가 자세를 배웠다는 영수증 (lower_adapter.pose_active_from_receipt · E6a 통과) 이 없으면 nav_env 가 거절한다 (명령 공간과 하위의 스위치가 달라서).
H0 는 하위 EX-42 자세 경로 (commands/ex42_posture.H0_DEFAULT 0.31 m · 가정) 와 같은 값. No Kit import.
"""
from __future__ import annotations

import os

import numpy as np

ENV_SWITCH = "HIPAN_POSE_ACTIONS"
H_RANGE = (0.1, 0.4)
ROLL_RANGE = (-1.0, 1.0)
H0 = 0.31


def enabled() -> bool:
    v = os.environ.get(ENV_SWITCH, "")
    if v not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {v!r})")
    return v == "1"


def action_dim() -> int:
    return 5 if enabled() else 3


def command_cols() -> int:
    return 5 if enabled() else 3


def split(action):
    """(n, 5) 상위 행동 -> ((n, 3) 속도 행동 · (n, 2) 자세 [dh, roll] 원문 범위로 자름). (n, 3) 이면 (그대로, None)."""
    a = np.asarray(action, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] not in (3, 5):
        raise ValueError(f"high action must be (n, 3) or (n, 5), got {a.shape}")
    if a.shape[1] == 3:
        return a, None
    pose = np.column_stack([np.clip(a[:, 3], H_RANGE[0] - H0, H_RANGE[1] - H0), np.clip(a[:, 4], *ROLL_RANGE)])
    return a[:, :3], pose


def actual_pose(state) -> np.ndarray:
    """실제 [dh, roll] (n, 2): dh = 몸통 z (env 원점 기준) - H0 (가정 · 바닥 높이를 빼지 않음) · roll = 몸통 쿼터니언 (w x y z) 의 roll."""
    q = np.asarray(state.quat_w, float)
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    roll = np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    return np.column_stack([np.asarray(state.pos_local, float)[:, 2] - H0, roll])
