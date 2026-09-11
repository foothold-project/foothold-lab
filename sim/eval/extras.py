"""FOOTHOLD CSV v1 의 «더한 열» 을 계산하는 순수 함수들.

분류: 운영
작성: 오흥재 · 2026-09-11 19:55
근거: `docs/CSV-SPEC-v1.md` 묶음 2·3·5 · 팀장 지시 「험지 참여도 열 추가」
요지: 에피소드가 끝날 때 한 번 접는 계산. torch 도 isaaclab 도 안 쓴다
상태: 확정

## 왜 따로 두나

하네스(`eval_generalization.py`)는 Isaac 안에서만 돈다. 그래서 그 안에 계산을
넣으면 **시험을 못 붙인다.** 규격 2 핵심 함수에 시험이 없었던 것도 같은
이유였다 (2026-09-11 6차 검증).

여기 있는 것은 전부 파이썬 기본 자료형만 받는다. 어디서나 부를 수 있고
`tests/test_extras.py` 가 알려진 답으로 못 박는다.

## 무엇을 안 하나

**판정을 안 바꾼다.** `overall_success` 는 여전히 네 축의 AND 다. 여기 있는
열은 전부 관측이고, 「그 성공이 어떤 성공이었나」를 나중에 되물을 수 있게
남기는 것이다.
"""

from __future__ import annotations

import math

# 접촉으로 치는 힘의 문턱. 머리 접촉 열이 쓰는 값과 같다.
DEFAULT_CONTACT_THRESHOLD_N = 1.0


def percentile(values, q):
    """정렬 후 선형 보간 백분위. `values` 가 비면 `None`.

    `numpy.percentile` 의 기본(`linear`)과 같은 값을 낸다. numpy 를 안 쓰는
    것은 이 파일을 Isaac 밖에서도 부르기 위해서다.

    Args:
        values: 수치 목록. `None` 은 걸러서 넣는다.
        q: 0~100.
    """
    xs = sorted(v for v in values if v is not None)

    if not xs:
        return None

    if len(xs) == 1:
        return float(xs[0])

    pos = (len(xs) - 1) * (float(q) / 100.0)
    low = int(math.floor(pos))
    high = int(math.ceil(pos))

    if low == high:
        return float(xs[low])

    return float(xs[low] + (xs[high] - xs[low]) * (pos - low))


def rms_from_sum_sq(sum_sq, count):
    """제곱합과 개수에서 RMS. 개수가 0 이면 `None`.

    **스텝마다 목록에 쌓지 않으려고** 제곱합만 들고 다닌다. 18,000 판 x
    300 스텝 x 12 관절이면 목록으로는 6,480만 개가 된다.
    """
    if not count:
        return None

    return math.sqrt(float(sum_sq) / float(count))


def relief_m(min_z, max_z):
    """지형 높이의 최솟값과 최댓값에서 기복. 둘 중 하나라도 없으면 `None`.

    **이것이 「험지를 얼마나 탔나」의 바탕이다.** 평지를 걸으면 0 에 가깝다.
    """
    if min_z is None or max_z is None:
        return None

    if not (math.isfinite(min_z) and math.isfinite(max_z)):
        return None

    return float(max_z) - float(min_z)


def engagement_ratio(underfoot_m, scan_m):
    """넘을 것이 있었는데(`scan`) 실제로 탔는가(`underfoot`).

    | 값 | 읽는 법 |
    |---|---|
    | 1 에 가까움 | 주변 기복을 몸으로 다 넘었다 |
    | 0 에 가까움 | 옆에 있었는데 **비켜 갔다** |
    | `None` | 주변에 기복이 없었다. 물을 것이 없다 |

    `scan` 이 0 에 가까우면 나누지 않는다. 평지에서 0/0 을 1 로 읽으면
    「완벽히 넘었다」가 되어 거꾸로 말한다.
    """
    if underfoot_m is None or scan_m is None:
        return None

    if scan_m < 0.02:          # 평지. 스캔 잡음보다 작다
        return None

    return max(0.0, min(1.0, float(underfoot_m) / float(scan_m)))


def contact_summary(forces_n, step_dt, threshold_n=DEFAULT_CONTACT_THRESHOLD_N):
    """한 부위의 스텝별 접촉력에서 네 값.

    Args:
        forces_n: 스텝마다의 힘 크기(N). 그 부위 강체들의 **최댓값**을 넣는다.
        step_dt: 스텝 한 번의 시간(s).
        threshold_n: 이 값을 «넘으면» 닿은 것으로 친다.

    Returns:
        `peak_force_n` 최댓값
        `impulse_proxy_ns` 문턱을 넘은 힘 x 시간의 합. 「얼마나 세게 오래」
        `contact_time_s` 문턱을 넘은 스텝의 총 시간
        `contact_events` 안 닿음에서 닿음으로 «바뀐» 횟수

    `impulse_proxy` 라고 부르는 것은 진짜 충격량이 아니기 때문이다. 힘은
    스텝 안에서 변하는데 우리는 스텝마다 한 값만 갖고 있다 `미확인`.
    """
    if not forces_n:
        return {
            "peak_force_n": None,
            "impulse_proxy_ns": None,
            "contact_time_s": None,
            "contact_events": None,
        }

    peak = 0.0
    impulse = 0.0
    touching_steps = 0
    events = 0
    was_touching = False

    for f in forces_n:
        if f is None or not math.isfinite(f):
            continue

        f = float(f)

        if f > peak:
            peak = f

        touching = f > threshold_n

        if touching:
            impulse += f * float(step_dt)
            touching_steps += 1

            if not was_touching:
                events += 1

        was_touching = touching

    return {
        "peak_force_n": peak,
        "impulse_proxy_ns": impulse,
        "contact_time_s": touching_steps * float(step_dt),
        "contact_events": events,
    }


def foot_slip_m(positions_xy, contacts_n, threshold_n=DEFAULT_CONTACT_THRESHOLD_N):
    """발이 «닿아 있는 동안» 수평으로 움직인 거리의 합.

    닿아 있으면 안 움직이는 것이 정상이다. 움직였다면 미끄러진 것이다.

    Args:
        positions_xy: 스텝마다 `(x, y)`. 발 하나의 것.
        contacts_n: 같은 길이의 접촉력.

    첫 스텝은 «직전» 이 없으므로 세지 않는다. 닿았다가 떨어졌다 다시 닿으면
    그 사이 공중 이동은 안 센다. 두 스텝이 **연속으로** 닿아 있을 때만 잰다.
    """
    if not positions_xy or len(positions_xy) != len(contacts_n):
        return None

    total = 0.0

    for i in range(1, len(positions_xy)):
        a, b = contacts_n[i - 1], contacts_n[i]

        if a is None or b is None:
            continue

        if not (a > threshold_n and b > threshold_n):
            continue

        (x0, y0), (x1, y1) = positions_xy[i - 1], positions_xy[i]

        if None in (x0, y0, x1, y1):
            continue

        total += math.hypot(float(x1) - float(x0), float(y1) - float(y0))

    return total


def episode_id(terrain, spec_version, difficulty, command_vx, episode):
    """한 줄만 보고도 출처를 알 수 있는 이름.

        gap_s2_d0.50_v1.0_e007

    manifest 를 안 열어도 여러 실행의 CSV 를 한 표로 합칠 수 있게 한다.
    """
    return "{}_s{}_d{:.2f}_v{:.1f}_e{:03d}".format(
        terrain, spec_version, float(difficulty), float(command_vx), int(episode))


# ── 더해지는 열 ────────────────────────────────────────────────────────
#
# **순서를 바꾸지 마십시오.** `metrics.RAW_COLUMNS` 가 이 순서로 이어 붙인다.

POSTURE_COLUMNS = (
    "roll_abs_p95_deg",
    "pitch_abs_p95_deg",
    "surface_relative_pitch_abs_p95_deg",
    "forward_velocity_rmse_mps",
    "lateral_velocity_rms_mps",
    "joint_torque_rms_nm",
    "action_delta_rms",
    "foot_slip_distance_proxy_m",
)

CONTACT_PARTS = ("foot", "thigh", "calf", "base")
CONTACT_FIELDS = ("peak_force_n", "impulse_proxy_ns", "contact_time_s", "contact_events")

CONTACT_COLUMNS = tuple(
    "{}_{}".format(part, field)
    for part in CONTACT_PARTS
    for field in CONTACT_FIELDS
)

# 팀장 지시로 더한 둘. 「그 성공이 진짜 험지 보행이었나」에 답한다.
ENGAGEMENT_COLUMNS = (
    "terrain_relief_scan_m",
    "terrain_relief_underfoot_m",
    "terrain_engagement_ratio",
)

TRACE_COLUMNS = (
    "episode_id",
    "eval_spec_version",
    "policy_sha256",
    "seed",
    "run_id",
)

# `metrics.ADDED_COLUMNS` 와 헷갈리지 않게 이름을 다르게 둔다.
# 그쪽은 «스냅샷에 없던 열» 이고 이쪽은 «FOOTHOLD 판 v1 에서 더한 열» 이다.
FOOTHOLD_V1_COLUMNS = (
    POSTURE_COLUMNS + CONTACT_COLUMNS + ENGAGEMENT_COLUMNS + TRACE_COLUMNS
)
