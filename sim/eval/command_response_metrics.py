# -*- coding: utf-8 -*-
"""명령 반응 프로브의 **판정 없는 계산**. Isaac 없이 돌고 시험이 돈다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-18
근거: `sim/eval/eval_command_response.py` 에서 순수 계산만 떼어 냄
요지: 프로브 지표를 Isaac 밖에서 부를 수 있게 한다. 그래야 시험이 돌고 관문이 생긴다
상태: 확정

## 왜 떼어 냈나

`eval_command_response.py` 는 모듈을 읽는 것만으로 `AppLauncher` 가 돌아서
**Isaac 을 안 띄우면 import 가 안 된다.** 그러면 지표 계산을 시험할 수가 없다.

`gap_observations.py` 가 같은 이유로 떼어져 나왔다. 그때 적힌 말을 그대로 옮기면,
「우리 평가의 핵심 한 줄이 관문 없이 남아 있었다」는 것이다.

2026-09-18 검증에서 이 계산들에 실제로 결함 둘이 잡혔다.

    정지 판정   창이 1초를 못 채워도 통과시켰다. 마지막 한 표본만 느려도 «멈췄다»
    낙상 집계   표본이 모자란 env 를 통째로 빼서 **가장 심하게 실패한 판이 사라졌다**

둘 다 Isaac 을 띄워야만 드러나는 자리에 있었다. 그래서 여기로 옮기고 시험을 건다.

## 판정이 아니다

**성공률을 내지 않는다.** 판정은 `eval_generalization.py` 의 네 축 AND 하나다.
여기 있는 것은 전부 관측이다.

`torch` 도 `isaaclab` 도 쓰지 않는다. 표준 라이브러리뿐이다.
"""

from __future__ import annotations

import math

# 접지로 볼 접촉력 (N) 과 「멈췄다」로 볼 속도 (m/s) 의 기본값.
# 부르는 쪽이 바꿀 수 있다. **숫자를 두 군데 적지 않으려고 여기 한 번만 둔다.**
DEFAULT_CONTACT_THRESHOLD_N = 1.0
DEFAULT_SETTLE_SPEED_MPS = 0.05

# 요레이트 추종비를 볼 명령 계단. 0 은 비를 만들 수 없어 뺀다.
YAW_GRID = (-1.0, -0.5, 0.5, 1.0)

# 응답곡선을 볼 명령 격자.
SPEED_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.25, 1.5)

FOOT_SLOTS = ("fl", "fr", "rl", "rr")


def mean(values):
    """`None` 과 NaN 을 빼고 평균. 남는 것이 없으면 `None`.

    **0 으로 채우지 않는다.** 0 은 「쟀는데 0」이고 `None` 은 「못 쟀다」다.
    """
    clean = [v for v in values if v is not None and v == v]

    return sum(clean) / len(clean) if clean else None


def joint_target_deltas(rows, joint_names):
    """스텝마다 관절 목표각이 얼마나 움직였나. `sum |delta|` 12관절.

    **이 도구의 요점이다.** 다만 이 값 하나로 원인을 확정하지는 못한다.

        0 으로 수렴    정책 출력이 굳었다. 이것은 이 값만으로 말할 수 있다
        계속 큼        정책은 계속 새 목표를 낸다. 몸이 따라오는지 «아닌지» 는
                       `joint_pos` 와 `base_*` 를 함께 봐야 안다. 정상 보행도
                       이 값이 크다

    즉 굳었다는 것은 이 열이 혼자 말할 수 있고, 안 따라온다는 것은 못 한다.
    후자는 목표각과 실제 관절각의 차이를 따로 봐야 한다.

    돌려주는 목록의 길이는 `len(rows) - 1` 이다. 첫 스텝에는 «직전» 이 없다.
    """
    keys = ["joint_target_{}".format(name) for name in joint_names]
    out = []

    for index in range(1, len(rows)):
        prev, here = rows[index - 1], rows[index]
        out.append(sum(abs(here[k] - prev[k]) for k in keys))

    return out


def slow_walk_metrics(rows, dt, joint_names, commanded_vx, skip_s):
    """저속 고정 명령의 가속 구간을 버리고 남은 표본만 잰다.

    버릴 구간과 측정 구간 사이의 관절 목표각 변화도 세지 않는다. 그 한 스텝은
    가속 구간의 값에 영향을 받으므로 측정 구간 안에서 생긴 변화가 아니다.
    표본이 모자라면 0 으로 채우지 않고 수치와 사유를 함께 남긴다.
    """
    skip_samples = max(0, int(round(skip_s / dt)))
    samples_skipped = min(len(rows), skip_samples)
    samples_used = max(0, len(rows) - skip_samples)

    result = {
        "commanded_vx_mps": commanded_vx,
        "tracked_vx_mps": None,
        "tracking_ratio": None,
        "residual_lateral_mps": None,
        "joint_target_delta_mean": None,
        "samples_used": samples_used,
        "samples_skipped": samples_skipped,
        "note": None,
    }

    if not samples_used:
        result["note"] = (
            "표본 {:.2f} 초로는 앞 {:.1f} 초를 버린 뒤 측정할 구간이 없다"
            .format(len(rows) * dt, skip_s)
        )
        return result

    measured = rows[skip_samples:]
    tracked_vx = mean([row["vx_mps"] for row in measured])

    result.update({
        "tracked_vx_mps": tracked_vx,
        "tracking_ratio": (
            None if tracked_vx is None or commanded_vx == 0
            else tracked_vx / commanded_vx
        ),
        "residual_lateral_mps": mean(
            [abs(row["vy_mps"]) for row in measured]
        ),
        "joint_target_delta_mean": mean(
            joint_target_deltas(measured, joint_names)
        ),
    })

    return result


def first_zero_command_index(rows, tolerance=1.0e-9):
    """명령 3축이 처음으로 전부 0 이 되는 자리. 없으면 `None`."""
    for index, row in enumerate(rows):
        if (abs(row["cmd_vx_mps"]) < tolerance
                and abs(row["cmd_vy_mps"]) < tolerance
                and abs(row["cmd_wz_rps"]) < tolerance):
            return index

    return None


def stop_time_s(rows, dt, settle_speed_mps=DEFAULT_SETTLE_SPEED_MPS,
                window_s=1.0):
    """명령이 0 이 된 뒤 **`window_s` 내내** 문턱 아래로 유지된 첫 시각.

    돌려주는 것은 `(시각, 사유)` 다. 못 잰 경우 시각이 `None` 이고 사유가 남는다.

    **창을 온전히 채워야 한다.** 끝자락에서 창이 짧아지는 것을 허용하면 표본
    한두 개만 느려도 「멈췄다」가 된다. 2026-09-18 검증에서 100 표본 중 마지막
    하나만 0 인 입력이 1.98 초로 통과했다. 그 자리를 막는다.

    창 내내 **명령도 0 이어야 한다.** 중간에 명령이 다시 들어왔다면 그때의
    저속은 「멈춘 것」이 아니라 「아직 못 따라간 것」이다.
    """
    n = len(rows)
    window = max(1, int(round(window_s / dt)))

    start = first_zero_command_index(rows)

    if start is None:
        return (None, "명령이 0 이 되는 구간이 없다")

    if n - start < window:
        return (None, "명령 0 이후가 {:.2f} 초뿐이라 {:.1f}초 창을 못 채운다".format(
            (n - start) * dt, window_s))

    for index in range(start, n - window + 1):
        chunk = rows[index:index + window]

        if len(chunk) < window:
            break

        commands_zero = all(
            abs(r["cmd_vx_mps"]) < 1.0e-9
            and abs(r["cmd_vy_mps"]) < 1.0e-9
            and abs(r["cmd_wz_rps"]) < 1.0e-9
            for r in chunk
        )

        if not commands_zero:
            continue

        if max(r["speed_mps"] for r in chunk) < settle_speed_mps:
            return ((index - start) * dt, None)

    return (None, "{:.1f}초 내내 문턱 아래로 유지된 창이 없다".format(window_s))


def response_curve(rows, grid=SPEED_GRID, tolerance=0.05):
    """명령 격자마다 **구간 뒤쪽 절반의 평균 응답**.

    **「정상상태」가 아니다.** 램프는 명령이 계속 움직이는 중이라 정상상태에
    이르렀는지 확인하지 않았다. 앞쪽 절반은 직전 명령에서 넘어오는 과도구간이라
    빼고, 남은 뒤쪽 절반의 평균을 낸다. 그 이상을 주장하지 않는다.
    """
    out = {}

    for target in grid:
        picked = [r["vx_mps"] for r in rows
                  if abs(r["cmd_vx_mps"] - target) < tolerance]

        if len(picked) >= 2:
            out["{:.2f}".format(target)] = mean(picked[len(picked) // 2:])

    return out


def yaw_follow(rows, grid=YAW_GRID, tolerance=1.0e-6):
    """요레이트 추종비. 명령 계단마다 뒤쪽 절반의 평균을 명령으로 나눈다."""
    out = {}

    for target in grid:
        picked = [r["base_wz_rps"] for r in rows
                  if abs(r["cmd_wz_rps"] - target) < tolerance]

        if len(picked) >= 2:
            actual = mean(picked[len(picked) // 2:])

            out["{:+.2f}".format(target)] = {
                "actual_rps": actual,
                "ratio": None if actual is None else actual / target,
            }

    return out


def foot_slip_m(rows, contact_threshold_n=DEFAULT_CONTACT_THRESHOLD_N):
    """접지 중인 발이 수평으로 움직인 거리 합 (m). 발 열이 없으면 `None`.

    발이 땅에 닿아 있는데 자리가 움직이면 미끄러진 것이다. **양 끝 스텝 모두**
    접촉해 있어야 그 구간을 센다.
    """
    total = 0.0
    counted = False

    for slot in FOOT_SLOTS:
        fx_key = "foot_x_{}_m".format(slot)
        fy_key = "foot_y_{}_m".format(slot)
        fn_key = "foot_contact_{}_n".format(slot)

        for index in range(1, len(rows)):
            prev, here = rows[index - 1], rows[index]

            values = (prev[fx_key], here[fx_key], prev[fy_key], here[fy_key],
                      prev[fn_key], here[fn_key])

            if any(v is None for v in values):
                continue

            if min(prev[fn_key], here[fn_key]) < contact_threshold_n:
                continue

            total += math.hypot(here[fx_key] - prev[fx_key],
                                here[fy_key] - prev[fy_key])
            counted = True

    return total if counted else None


def quad_stance_s(rows, dt, contact_threshold_n=DEFAULT_CONTACT_THRESHOLD_N):
    """네 발이 동시에 닿아 있던 **가장 긴** 구간 (초). 발 열이 없으면 `None`.

    멈춘 방식의 질이다. 네 발로 버티고 서 있으면 길고, 계속 발을 바꿔 딛으면
    짧다.
    """
    keys = ["foot_contact_{}_n".format(slot) for slot in FOOT_SLOTS]

    longest = 0
    run = 0

    for row in rows:
        values = [row[k] for k in keys]

        if any(v is None for v in values):
            return None

        if min(values) >= contact_threshold_n:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    return longest * dt


def episode_metrics(rows, dt, joint_names, fell_at_s,
                    contact_threshold_n=DEFAULT_CONTACT_THRESHOLD_N,
                    settle_speed_mps=DEFAULT_SETTLE_SPEED_MPS,
                    env_id=None, timeseries_file=None):
    """env 하나의 설계 문서 5-3 절 지표. **전부 93열에서 나온다.**

    `env_id` 와 `timeseries_file` 은 **이 줄이 어느 로봇의 것인지**를 남긴다.
    없으면 `per_env.json` 과 parquet 파일을 서로 못 맞춘다.
    """
    n = len(rows)
    tail_len = max(1, int(round(1.0 / dt)))
    tail = rows[max(0, n - tail_len):]

    deltas = joint_target_deltas(rows, joint_names)
    settled_at, stop_note = stop_time_s(rows, dt, settle_speed_mps)

    fell = fell_at_s is not None and fell_at_s == fell_at_s

    return {
        "env_id": env_id,
        "timeseries_file": timeseries_file,
        "samples": n,
        "duration_s": n * dt,
        "fell": fell,
        "fell_at_s": fell_at_s if fell else None,
        "degenerate": False,

        # G1
        "stop_time_s": settled_at,
        "stop_note": stop_note,
        "residual_speed_mps": mean([r["speed_mps"] for r in tail]),
        "residual_vx_mps": mean([r["vx_mps"] for r in tail]),
        "residual_vy_mps": mean([r["vy_mps"] for r in tail]),

        # 「얼음」의 정체
        "joint_target_delta_mean": mean(deltas),
        "joint_target_delta_tail": mean(deltas[max(0, len(deltas) - tail_len):]),
        "joint_target_delta_max": max(deltas) if deltas else None,

        # 무게중심
        "pitch_abs_max_deg": max((abs(r["pitch_deg"]) for r in rows), default=None),
        "roll_abs_max_deg": max((abs(r["roll_deg"]) for r in rows), default=None),
        "base_z_min_m": min((r["base_z_m"] for r in rows), default=None),
        "base_z_tail_m": mean([r["base_z_m"] for r in tail]),

        # G2 · G3
        "response": response_curve(rows),
        "yaw_follow": yaw_follow(rows),

        # 멈춘 방식의 질
        "foot_slip_m": foot_slip_m(rows, contact_threshold_n),
        "quad_stance_s": quad_stance_s(rows, dt, contact_threshold_n),
    }


def degenerate_entry(samples, dt, fell_at_s, env_id=None):
    """시계열이 모자란 env 한 대. **낙상 집계에는 들어간다.**

    첫 스텝에 넘어지면 표본이 한 개뿐이라 시간 지표를 낼 수 없다. 그렇다고
    통째로 빼면 **가장 심하게 실패한 판이 낙상률에서 사라진다.**
    """
    fell = fell_at_s is not None and fell_at_s == fell_at_s

    return {
        "env_id": env_id,
        "timeseries_file": None,
        "samples": samples,
        "duration_s": samples * dt,
        "fell": fell,
        "fell_at_s": fell_at_s if fell else None,
        "degenerate": True,
        "note": "표본이 모자라 시계열 지표 없음",
    }


def aggregate(per_env, degenerate, name, what):
    """env 들을 하나로 접는다. **평균만 낸다.**

    산포는 안 낸다. env 마다의 값이 `per_env.json` 에 그대로 남으므로 퍼짐이
    필요하면 그 파일에서 구한다.

    **분모가 둘이다.** 낙상은 모든 env 가 분모이고, 시간 지표 평균은 시계열이
    있는 env 만 분모다. 섞으면 넘어져서 표본이 없는 판이 통계에서 사라진다.
    """
    everyone = list(per_env) + list(degenerate)

    if not everyone:
        return {"scenario": name, "what": what, "envs": 0}

    fell = [e for e in everyone if e["fell"]]

    merged_response = {}
    merged_yaw = {}

    for entry in per_env:
        for key, value in entry["response"].items():
            merged_response.setdefault(key, []).append(value)

        for key, value in entry["yaw_follow"].items():
            merged_yaw.setdefault(key, []).append(value["ratio"])

    def across(key):
        return mean([e[key] for e in per_env])

    result = {
        "scenario": name,
        "what": what,

        # **낙상은 전체가 분모다.** 표본이 모자란 env 도 로봇 한 대다.
        "envs": len(everyone),
        "fell_count": len(fell),
        "fell_ratio": len(fell) / len(everyone),

        # 아래 평균들의 분모. 위와 다르다.
        "envs_with_timeseries": len(per_env),
        "envs_degenerate": len(degenerate),

        "stop_time_s": mean(
            [e["stop_time_s"] for e in per_env if e["stop_time_s"] is not None]
        ),
        "stop_reached_count": sum(
            1 for e in per_env if e["stop_time_s"] is not None
        ),
        "stop_reached_of": len(per_env),

        "residual_speed_mps": across("residual_speed_mps"),
        "joint_target_delta_mean": across("joint_target_delta_mean"),
        "joint_target_delta_tail": across("joint_target_delta_tail"),
        "pitch_abs_max_deg": across("pitch_abs_max_deg"),
        "roll_abs_max_deg": across("roll_abs_max_deg"),
        "base_z_tail_m": across("base_z_tail_m"),
        "foot_slip_m": across("foot_slip_m"),
        "quad_stance_s": across("quad_stance_s"),

        "response_curve": {k: mean(v) for k, v in sorted(merged_response.items())},
        "yaw_follow_ratio": {k: mean(v) for k, v in sorted(merged_yaw.items())},
    }

    # 저속 고정 시나리오에만 있는 값이다. 기존 시나리오의 결과 키와 계산은
    # 그대로 둔다.
    if per_env and "commanded_vx_mps" in per_env[0]:
        for key in (
                "commanded_vx_mps", "tracked_vx_mps", "tracking_ratio",
                "residual_lateral_mps", "samples_used", "samples_skipped"):
            result[key] = across(key)

        result["slow_metrics_count"] = sum(
            1 for entry in per_env if entry["tracked_vx_mps"] is not None
        )
        result["slow_metrics_of"] = len(everyone)

    return result
