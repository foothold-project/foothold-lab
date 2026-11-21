"""NavState -> 상위 보상 (설계 §3 N2 · PLAN-HIPAN-V2 M8). 보상 식은 `rewards_hl` 에 있고 여기는 환경 상태를 그 입력 꼴로 옮기는 층이다. numpy 만.

옮기는 규칙 (가정은 표시):
  명령 c · 직전 · 전전 = 하위에 실제 넣은 [vx vy wz] (자세 스위치 꺼짐 -> 세 칸) · 실제 상태 = 몸 틀 [vx vy wz] (yaw_rate = 몸 z 각속도)
  r6 의 「실제」 는 윈도 끝의 값 (가정) · r7 = 몸 z 속도² + roll · pitch 각속도² (몸 틀) · r8 = 관절 q 와 기본 자세 q0
  r9 = 명령 공간 층이 값을 고쳤다 · r10 = 충돌 (몸통 · 허벅지 · 머리) · r1 = 부목표 0.1 m 안 · r2 = 방문 수 격자 0.5 m
"""
from __future__ import annotations

import numpy as np

from foothold_s2.nav import rewards_hl as rh


def to_hl_state(state, *, pos_room_xy, subgoal_xy, eta, v_des, cmd_prev, cmd_prev2) -> rh.HLState:
    from foothold_s2.nav import pose_actions

    cols = pose_actions.command_cols()
    cmd = np.asarray(state.applied)[:, :cols]
    actual = np.concatenate([np.asarray(state.vel_b)[:, :2], np.asarray(state.yaw_rate).reshape(-1, 1)], axis=1)
    if cols == 5:                                                   # HIPAN_POSE_ACTIONS=1: r6 이 자세 두 칸도 잰다 (실제 dh · roll)
        actual = np.concatenate([actual, pose_actions.actual_pose(state)], axis=1)
    return rh.HLState(
        pos_xy=np.asarray(pos_room_xy, float), subgoal_xy=np.asarray(subgoal_xy, float), v_xy=np.asarray(state.vel_b)[:, :2],
        v_z=np.asarray(state.vel_b)[:, 2], omega_xy=np.asarray(state.ang_vel_b)[:, :2], q=np.asarray(state.q), q0=np.asarray(state.q0),
        cmd=cmd, cmd_prev=np.asarray(cmd_prev, float), cmd_prev2=np.asarray(cmd_prev2, float), actual=actual,
        v_des=np.asarray(v_des, float), eta=np.asarray(eta, float), limited=np.asarray(state.modified, bool),
        collision=np.asarray(state.collision, bool))


def reward(state, arrive_m: float = rh.ARRIVE_M, **kw) -> tuple:
    """(합 (n,), 가중치를 곱한 항 dict). 자세 스위치는 끈 채 (설계 결정 1: 상위 출력 3 칸). arrive_m = r1 의 도달 반경 (기본 논문 0.1 m)."""
    from foothold_s2.nav import pose_actions

    return rh.reward_total(to_hl_state(state, **kw), pose_active=pose_actions.enabled(), arrive_m=arrive_m)
