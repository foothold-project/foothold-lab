"""한 판(에피소드)의 판정. 순수 numpy, Kit 없음.

두 가지가 있다.
  `judge_axis1`   축 1. v2 의 성분 넷(생존 · 전진 · 속도 추종 · 방향)과 R/S/J.
  `judge_command` 축 3 과 START 시험지. 몸 기준 명령 (vx, vy, wz) 에 대한 진행 · 방향 이탈.

입력 배열은 한 판 동안 스텝 «전» 에 쌓은 것이다 (스텝 뒤에 읽으면 리셋이 접촉 · 상태를
지운다. 옛 하네스가 한 번 겪은 일). 배열 길이는 모두 n 이고 같은 스텝을 가리킨다.

용어
  R 기준선 도달   전진(명령 방향 진행)이 기준 거리를 한 번이라도 넘었다.
  S 끝까지 생존   시간 T 까지 넘어지지 않았다 (time-out 이고 terminated 아님).
  J 둘 다         R AND S.
"""

import math

import numpy as np

# 부동소수 합이 기준 거리 바로 위 · 아래로 갈리는 일을 막는 여유. 루프의 정지 판정도 같은 값을 쓴다.
REACH_EPS = 1.0e-9

# ---------------------------------------------------------------- 공통 기하


def lateral_axis(fwd):
    """전방축을 왼쪽으로 90도 돌린 축."""
    return np.array([-fwd[1], fwd[0]], dtype=float)


def wrap_pi(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def unwrap_yaw(yaw):
    """스텝 사이 +-pi 점프를 펴서 누적 요각으로."""
    return np.unwrap(np.asarray(yaw, dtype=float))


def gate_crossing(progress, lateral, gate_m):
    """진행이 처음 `gate_m` 이상이 되는 자리의 좌우 이탈(절댓값), 선형 보간.

    못 넘으면 `None` (0.0 이 아니다: 「도달했고 곧았다」와 구별해야 한다).
    """
    previous = None

    for i in range(len(progress)):
        if progress[i] >= gate_m:
            if previous is None:
                return abs(float(lateral[i]))

            p0, l0 = previous
            span = progress[i] - p0

            if span <= 0.0:
                return abs(float(lateral[i]))

            t = (gate_m - p0) / span

            return abs(float(l0 + t * (lateral[i] - l0)))

        previous = (float(progress[i]), float(lateral[i]))

    return None


# ---------------------------------------------------------------- 축 1


def judge_axis1(pos_xy, vel_err, fwd_dir, timed_out, terminated, dt,
                min_progress_m, max_lateral_drift_m, max_velocity_mae_mps):
    """축 1 한 판. 성분 넷 + R/S/J.

    `pos_xy`   (n, 2) 스텝 전 위치. 첫 표본이 출발점, 마지막 표본이 끝점(마지막 스텝 전).
    `vel_err`  (n,)  평면 속도 오차 |v_body_xy - cmd_xy|.
    성분 정의는 v2 와 같다 (생존 AND 전진 AND 속도 추종 AND 통과선 위 방향).
    """
    pos = np.asarray(pos_xy, dtype=float)
    n = len(pos)

    if n == 0:
        raise ValueError("표본이 없는 판은 판정할 수 없습니다")

    fwd = np.asarray(fwd_dir, dtype=float)
    lat = lateral_axis(fwd)

    rel = pos - pos[0]
    progress = rel @ fwd
    lateral = rel @ lat

    forward_end = float(progress[-1])
    gate_lat = gate_crossing(progress, lateral, min_progress_m)

    survival = bool(timed_out and not terminated)
    progress_ok = bool(forward_end >= min_progress_m)
    tracking_ok = bool(float(np.mean(vel_err)) <= max_velocity_mae_mps)
    direction_ok = bool(gate_lat is not None and gate_lat <= max_lateral_drift_m)

    reached = bool(np.max(progress) >= min_progress_m)

    return {
        "overall_success": bool(survival and progress_ok and tracking_ok and direction_ok),
        "survival_success": survival,
        "progress_success": progress_ok,
        "tracking_success": tracking_ok,
        "direction_success": direction_ok,
        "R_body": reached,
        "S": survival,
        "J_body": bool(reached and survival),
        "forward_progress_m": forward_end,
        "max_forward_m": float(np.max(progress)),
        "gate_lateral_drift_m": gate_lat,
        "peak_lateral_drift_m": float(np.max(np.abs(lateral))),
        "velocity_mae_mps": float(np.mean(vel_err)),
        "duration_s": n * dt,
        "samples": n,
        "termination_reason": "timeout" if timed_out else "base_contact",
    }


# ---------------------------------------------------------------- 명령 방향 진행 (축 3 · START)


def projected_progress_step(vel_b_xy, cmd_xy, dt):
    """한 스텝의 명령 방향 진행 증분 = (몸 기준 속도 · 명령 단위벡터) x dt.

    명령 선속도가 0 이면 0. 옆 명령을 몸을 돌려 전진으로 대신하면 몸 기준 옆 속도가
    0 이라 이 값이 0 이다 (ASTRA 19f Q5).
    """
    cmd = np.asarray(cmd_xy, dtype=float)
    norm = float(np.hypot(cmd[0], cmd[1]))

    if norm < 1.0e-9:
        return 0.0

    return float((vel_b_xy[0] * cmd[0] + vel_b_xy[1] * cmd[1]) / norm * dt)


def expected_displacement(cmd, active_s, steps=400):
    """상수 명령 (vx, vy, wz) 를 `active_s` 초 적분한 변위(출발 몸 좌표계).

    wz = 0 이면 직선, 아니면 호. 방향 이탈의 「기대 방향」을 만드는 데 쓴다.
    """
    vx, vy, wz = cmd

    if active_s <= 0.0:
        return np.zeros(2)

    if abs(wz) < 1.0e-9:
        return np.array([vx, vy], dtype=float) * active_s

    h = active_s / steps
    x = y = th = 0.0

    for _ in range(steps):
        x += (vx * math.cos(th) - vy * math.sin(th)) * h
        y += (vx * math.sin(th) + vy * math.cos(th)) * h
        th += wz * h

    return np.array([x, y])


def judge_command(pos_xy, yaw, vel_b_xy, wz_b, cmd, active, timed_out, terminated,
                  dt, reference_m, yaw_deviation_deg=30.0, min_motion_m=0.1):
    """몸 기준 명령 한 개를 받은 한 판.

    입력 (모두 길이 n)
      pos_xy     (n, 2)  세계 위치(스텝 전)
      yaw        (n,)    세계 요각 [rad]
      vel_b_xy   (n, 2)  몸 좌표계 선속도
      wz_b       (n,)    몸 좌표계 요 각속도
      cmd        (n, 3)  그 스텝에 정책이 따른 명령 (vx, vy, wz)
      active     (n,)    명령이 «켜진» 스텝 (도달 뒤 정지로 바뀐 뒤는 False)

    R 은 명령 선속도가 있는 칸에만 정의된다 (정지 · 제자리 회전에는 쓰지 않는다: 41 §5).
    방향 이탈은 세 가지를 따로 남긴다.
      yaw_dev_deg      실제 요각 변화 - 명령이 만든 요각 변화 (30 도 넘으면 이탈 표시)
      heading_err_deg  실제 순변위 방향 - 기대 순변위 방향 (출발 몸 좌표계)
      lateral_dev_m    기대 방향에 수직인 순변위 성분의 절댓값
      gate_lateral_dev_m 직선 명령에서 진행이 기준 거리를 넘는 순간의 옆 이탈
    """
    pos = np.asarray(pos_xy, dtype=float)
    yaw = unwrap_yaw(yaw)
    vel = np.asarray(vel_b_xy, dtype=float)
    cmd = np.asarray(cmd, dtype=float)
    act = np.asarray(active, dtype=bool)
    n = len(pos)

    if n == 0:
        raise ValueError("표본이 없는 판은 판정할 수 없습니다")

    survival = bool(timed_out and not terminated)

    c0 = cmd[act][0] if act.any() else cmd[0]
    lin_speed = float(np.hypot(c0[0], c0[1]))
    has_lin = lin_speed > 1.0e-9
    has_yaw = abs(float(c0[2])) > 1.0e-9

    # 명령 방향 진행: 켜진 스텝에서만 쌓는다.
    steps = np.zeros(n)

    if has_lin:
        unit = np.array([c0[0], c0[1]]) / lin_speed
        steps = np.where(act, (vel @ unit) * dt, 0.0)

    # 표본 i 는 스텝 «전» 상태다. 표본 i 까지 실제로 흘러간 것은 스텝 0..i-1 이므로 한 칸 민다.
    progress = np.concatenate([[0.0], np.cumsum(steps)[:-1]])
    total_progress = float(progress[-1])
    reached = bool(has_lin and np.max(progress) >= reference_m - REACH_EPS)

    # 실제로 흘러간 스텝(마지막 표본의 스텝은 아직 안 일어났다) 중 명령이 켜진 수
    n_act = int(act[:-1].sum()) if n > 1 else 0
    err = np.hypot(vel[:, 0] - cmd[:, 0], vel[:, 1] - cmd[:, 1])
    vel_mae = float(np.mean(err[act])) if act.any() else None

    # 요 추종
    yaw_ratio = None

    if has_yaw and n_act >= 2:
        idx = np.nonzero(act)[0]
        second_half = idx[len(idx) // 2:]
        yaw_ratio = float(np.mean(wz_b[second_half]) / c0[2])

    # 방향 이탈
    start_yaw = float(yaw[0])
    cos0, sin0 = math.cos(start_yaw), math.sin(start_yaw)
    world = pos[-1] - pos[0]
    disp_b = np.array([cos0 * world[0] + sin0 * world[1],
                       -sin0 * world[0] + cos0 * world[1]])

    commanded_yaw = float(np.sum(np.where(act, cmd[:, 2], 0.0)[:-1]) * dt)
    actual_yaw = float(yaw[-1] - yaw[0])
    yaw_dev = abs(math.degrees(actual_yaw - commanded_yaw))

    active_s = n_act * dt
    expect = expected_displacement(tuple(c0), active_s)

    heading_err = None
    lateral_dev = None

    if has_lin and np.hypot(*disp_b) >= min_motion_m and np.hypot(*expect) > 1.0e-9:
        dot = float(disp_b @ expect)
        cross = float(expect[0] * disp_b[1] - expect[1] * disp_b[0])
        heading_err = abs(math.degrees(math.atan2(cross, dot)))
        lateral_dev = abs(cross) / float(np.hypot(*expect))
    elif has_lin:
        # 거의 안 움직였다: 방향을 말할 수 없다 (이탈 아님 · 진행 0 이 그 사실을 이미 담는다).
        heading_err = None
        lateral_dev = None

    gate_lat = None

    if has_lin and not has_yaw:
        rel_b = (pos - pos[0]) @ np.array([[cos0, -sin0], [sin0, cos0]])
        unit = np.array([c0[0], c0[1]]) / lin_speed
        lat_i = rel_b[:, 0] * (-unit[1]) + rel_b[:, 1] * unit[0]
        gate_lat = gate_crossing(progress, lat_i, reference_m)

    # 방향 이탈 표시는 선속도 명령이 있는 칸에서만 뜻이 있다.
    yaw_flag = bool(yaw_dev > yaw_deviation_deg) if has_lin else None

    return {
        "survival_success": survival,
        "R_body": reached if has_lin else None,
        "S": survival,
        "J_body": bool(reached and survival) if has_lin else None,
        "cmd_progress_m": total_progress,
        "cmd_progress_ratio": total_progress / reference_m if has_lin else None,
        "cmd_progress_ratio_capped": (min(max(total_progress / reference_m, 0.0), 1.0)
                                      if has_lin else None),
        "velocity_mae_mps": vel_mae,
        "yaw_follow_ratio": yaw_ratio,
        "yaw_dev_deg": yaw_dev,
        "yaw_dev_flag": yaw_flag,
        "heading_err_deg": heading_err,
        "lateral_dev_m": lateral_dev,
        "gate_lateral_dev_m": gate_lat,
        "net_disp_x_m": float(disp_b[0]),
        "net_disp_y_m": float(disp_b[1]),
        "active_s": active_s,
        "duration_s": n * dt,
        "samples": n,
        "termination_reason": "timeout" if timed_out else "base_contact",
    }
