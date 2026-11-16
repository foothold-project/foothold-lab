"""상위 보상 열 항 + 방문 수 격자 (PLAN-HIPAN-V2 §6.2 · M8 · 21 §2 Table II). numpy 만, Kit 없음.

항 · 가중치는 논문 Table II 그대로 (21 §2). 계획 v2 가 바꾸는 곳만 다르다:
  r3 v_des ~ U[0.3, 1.0] (논문 1.2 · 하위 상한 1.0 · 가정) · r6 자세 스위치가 꺼지면 세 칸 [vx vy wz], 켜지면 다섯 칸 [vx vy wz h roll]
  r9 「명령 공간 층이 값을 고쳤다」 지시자 (command_space.Applied.modified) · r10 충돌 지시자 (몸체 = base · 허벅지 · 머리 · 가정)
논문이 적지 않은 것은 가정으로 고정: η 격자 0.5 m · 에피소드마다 비움 · 걸음마다 +1 한 뒤의 η (처음 들른 칸은 η = 1) · v_des 는 에피소드 시작에 한 번.
r8 은 관절 자세 q 와 기본 자세 q0 의 제곱 거리. 모든 입력은 (N, ...) 배열 (N = env 수).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

WEIGHTS = {"r1": 5.0, "r2": 0.5, "r3": 0.25, "r4": -0.1, "r5": -0.1, "r6": -0.2, "r7": -0.1, "r8": -0.04,
           "r9": -2.5, "r10": -2.5}
ARRIVE_M = 0.1
V_TOL = 0.3
V_DES_RANGE = (0.3, 1.0)
VISIT_RES_M = 0.5
ROOM_M = 20.0


class VisitGrid:
    """env 마다 0.5 m 격자 방문 수 (r2). 에피소드가 끝난 env 는 reset 으로 비운다."""

    def __init__(self, num_envs: int, room_m: float = ROOM_M, res_m: float = VISIT_RES_M):
        self.n = int(round(room_m / res_m))
        self.res, self.room = res_m, room_m
        self.counts = np.zeros((num_envs, self.n, self.n), np.int32)

    def reset(self, env_ids) -> None:
        self.counts[np.asarray(env_ids, dtype=int)] = 0

    def visit(self, pos_xy) -> np.ndarray:
        """한 걸음 방문을 세고 (N,) η (이번 걸음 포함, >= 1) 를 돌려준다. 방 밖은 가장자리 칸으로 센다."""
        p = np.asarray(pos_xy, float)
        cell = np.clip(np.floor(p / self.res).astype(int), 0, self.n - 1)
        idx = np.arange(len(p))
        self.counts[idx, cell[:, 0], cell[:, 1]] += 1
        return self.counts[idx, cell[:, 0], cell[:, 1]].astype(np.float64)


def sample_v_des(rng: np.random.Generator, n: int, low_high=V_DES_RANGE) -> np.ndarray:
    """에피소드 시작에 한 번 뽑는 원하는 속력 (N,)."""
    return rng.uniform(low_high[0], low_high[1], n)


@dataclass
class HLState:
    pos_xy: np.ndarray        # (N, 2) 몸 위치 (방 틀)
    subgoal_xy: np.ndarray    # (N, 2) 지금 부목표 (PGCL)
    v_xy: np.ndarray          # (N, 2) 몸 틀 선속도 xy
    v_z: np.ndarray           # (N,)
    omega_xy: np.ndarray      # (N, 2) 몸 틀 각속도 roll · pitch 성분
    q: np.ndarray             # (N, J) 관절 위치
    q0: np.ndarray            # (J,) 기본 자세
    cmd: np.ndarray           # (N, C) 지금 명령 (C = 3 또는 5, 자세 칸이 가려졌으면 0)
    cmd_prev: np.ndarray      # (N, C)
    cmd_prev2: np.ndarray     # (N, C)
    actual: np.ndarray        # (N, 3 또는 5) 실제 [vx vy wz (h roll)]
    v_des: np.ndarray         # (N,)
    eta: np.ndarray           # (N,) VisitGrid.visit 의 값
    limited: np.ndarray       # (N,) bool 명령 공간 층이 값을 고쳤다
    collision: np.ndarray     # (N,) bool


def reward_terms(s: HLState, pose_active: bool = False) -> dict:
    """항마다 (N,) 값 (가중치 곱하기 전) 을 돌려준다."""
    arrive = (np.linalg.norm(s.pos_xy - s.subgoal_xy, axis=1) < ARRIVE_M).astype(np.float64)
    speed = np.linalg.norm(s.v_xy, axis=1)
    cols = 5 if pose_active else 3
    if s.actual.shape[1] < cols or s.cmd.shape[1] < cols:
        raise ValueError(f"pose_active={pose_active} needs {cols} command and state columns")
    return {
        "r1": arrive,
        "r2": 1.0 / np.sqrt(np.maximum(s.eta, 1.0)),
        "r3": np.exp(-np.abs(s.v_des - speed) / V_TOL),
        "r4": np.sum((s.cmd - s.cmd_prev) ** 2, axis=1),
        "r5": np.sum((s.cmd - 2.0 * s.cmd_prev + s.cmd_prev2) ** 2, axis=1),
        "r6": np.linalg.norm(s.cmd[:, :cols] - s.actual[:, :cols], axis=1),             # 논문 ‖c - 실제‖2 (제곱 아님)
        "r7": s.v_z ** 2 + np.sum(s.omega_xy ** 2, axis=1),
        "r8": np.sum((s.q - s.q0[None]) ** 2, axis=1),
        "r9": s.limited.astype(np.float64),
        "r10": s.collision.astype(np.float64),
    }


def reward_total(s: HLState, pose_active: bool = False, weights: dict | None = None) -> tuple[np.ndarray, dict]:
    """(합 (N,), 가중치를 곱한 항 dict)."""
    w = WEIGHTS if weights is None else weights
    if set(w) != set(WEIGHTS):
        raise ValueError("weights must name r1..r10")
    terms = {k: w[k] * v for k, v in reward_terms(s, pose_active).items()}
    return sum(terms.values()), terms
