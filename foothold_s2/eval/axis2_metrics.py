"""축 2 (평지 명령 응답) 지표. 순수 numpy.

env 한 대의 시계열에서 칸마다의 값을 뽑고, 시나리오로 접고, 아홉 칸 판정표를 만든다.
정의는 v2 9 절과 같다 (옛 `command_response_metrics.py` 를 보고 새로 썼다).

분모 규칙: 낙상 비율은 표본이 모자란(첫 스텝에 넘어진) env 도 분모에 넣는다.
시간 지표 평균은 표본이 2 개 이상인 env 만 분모다. 섞으면 가장 심하게 실패한 판이
낙상률에서 사라진다.
"""

import numpy as np

from foothold_s2.eval.cells import AXIS2_CELLS

YAW_GRID = (-1.0, -0.5, 0.5, 1.0)


def _clean_mean(values):
    vals = [float(v) for v in values if v is not None and v == v]

    return sum(vals) / len(vals) if vals else None


def joint_target_deltas(joint_target):
    """스텝마다 12관절 목표 변화의 절댓값 합. 길이 n-1."""
    jt = np.asarray(joint_target, dtype=float)

    if len(jt) < 2:
        return np.zeros(0)

    return np.abs(np.diff(jt, axis=0)).sum(axis=1)


def yaw_follow(wz_b, cmd_wz, grid=YAW_GRID, tolerance=1.0e-6):
    """명령 계단마다 뒤쪽 절반의 평균 각속도 / 명령."""
    wz_b = np.asarray(wz_b, dtype=float)
    cmd_wz = np.asarray(cmd_wz, dtype=float)
    out = {}

    for target in grid:
        picked = wz_b[np.abs(cmd_wz - target) < tolerance]

        if len(picked) >= 2:
            actual = float(np.mean(picked[len(picked) // 2:]))
            out["%+.2f" % target] = actual / target

    return out


def env_metrics(vx_b, vy_b, wz_b, cmd, joint_target, dt, fell_at_s):
    """env 한 대. 표본이 2 개 미만이면 `degenerate` 로 낙상 여부만 남긴다."""
    n = len(vx_b)
    fell = fell_at_s is not None and fell_at_s == fell_at_s

    if n < 2:
        return {"degenerate": True, "fell": fell, "samples": n}

    tail_len = max(1, int(round(1.0 / dt)))
    speed = np.hypot(np.asarray(vx_b, dtype=float), np.asarray(vy_b, dtype=float))
    deltas = joint_target_deltas(joint_target)

    return {
        "degenerate": False,
        "fell": fell,
        "samples": n,
        "residual_speed_mps": float(np.mean(speed[max(0, n - tail_len):])),
        "joint_target_delta_tail": float(np.mean(deltas[max(0, len(deltas) - tail_len):])),
        "yaw_follow": yaw_follow(wz_b, np.asarray(cmd, dtype=float)[:, 2]),
    }


def aggregate_scenario(per_env):
    """시나리오 하나로 접는다. 평균만 낸다 (env 별 값은 per_env 에 그대로 남는다)."""
    if not per_env:
        return {"envs": 0}

    full = [e for e in per_env if not e["degenerate"]]
    fell = sum(1 for e in per_env if e["fell"])

    merged = {}

    for entry in full:
        for key, value in entry["yaw_follow"].items():
            merged.setdefault(key, []).append(value)

    return {
        "envs": len(per_env),
        "fell_count": fell,
        "fell_ratio": fell / len(per_env),
        "envs_with_timeseries": len(full),
        "envs_degenerate": len(per_env) - len(full),
        "residual_speed_mps": _clean_mean(e["residual_speed_mps"] for e in full),
        "joint_target_delta_tail": _clean_mean(e["joint_target_delta_tail"] for e in full),
        "yaw_follow_ratio": {k: _clean_mean(v) for k, v in sorted(merged.items())},
    }


def _lookup(summary, cell):
    """`turn/yaw_follow/+0.50` 같은 칸 이름에서 값을 꺼낸다. 없으면 None (0 이 아니다)."""
    parts = cell.split("/")
    scenario = summary.get(parts[0])

    if not scenario:
        return None

    if parts[1] == "yaw_follow":
        return scenario.get("yaw_follow_ratio", {}).get(parts[2])

    return scenario.get(parts[1])


def judge_cells(summary):
    """아홉 칸 판정표. `summary` 는 {시나리오: aggregate_scenario 결과}.

    값을 못 잰 칸은 `value=None, passed=False` 로 남는다 (통과로 세지 않는다).
    """
    rows = []

    for cell, op, threshold in AXIS2_CELLS:
        value = _lookup(summary, cell)

        if value is None:
            passed = False
        elif op == "<=":
            passed = value <= threshold
        else:
            passed = value >= threshold

        rows.append({"cell": cell, "threshold": "%s %s" % (op, threshold),
                     "value": value, "passed": bool(passed)})

    return rows
