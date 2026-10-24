"""우회전 원인 분리 표(설계 v1.0 §7.1) 판정의 순수 계산. Kit 없이 시험된다.

입력은 200 Hz 물리 substep 시계열(numpy)이다. 판정 문턱은 결과를 보기 전에 여기 상수로 등록하고, 결과를 보고 바꾸지 않는다(결과 json 에 문턱과 이 파일의 git blob SHA 를 남긴다).
없는 물리량을 다른 값으로 대신 확정하지 않는다: 입력이 None 이면 그 가설은 「미확인」 이다.
가설 다섯: joint_limit · actuator · foot_support(발 아닌 링크 접촉) · posture(정책 자세) · order(촬영 순서/바닥).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

HZ = 200.0
SUSTAIN_S = 0.5                    # 「해당 시간 지속」 의 최소 길이
LIMIT_MARGIN_RAD = 0.05            # 실제 q 가 한계에서 이만큼 안이면 「한계 근처」
SATURATION_FRAC = 0.98             # |적용 토크| >= 이 비율 x (그 순간의 DC 곡선 상한) 이면 곡선 위
CLIP_GAP_NM = 1.0e-3               # 계산 토크와 적용 토크 차가 이보다 크면 클립(잘림)
CONTACT_FORCE_N = 1.0              # 발 아닌 링크의 접촉 힘 문턱
STALL_FRAC = 0.1                   # |wz| < 0.1 |cmd_wz| 이면 정체
ORDER_GAP = 0.25                   # 독립 시작과 연속 시작의 yaw 추종 비 차이가 이보다 크면 순서 영향
POSTURE_MIN_TARGET_STD_RAD = 0.02  # 목표 관절각의 시간 표준편차가 이보다 작으면 「정책이 발을 안 움직임」
POSTURE_MIN_STALL_FRACTION = 0.5   # 정체가 이 비율 이하이면 자세 가설은 「해당 없음」(판정 대상 아님)
EFFORT_LIMIT_SENTINEL = 1.0e6      # 이 이상이면 구동기 cfg 의 실제 한계가 아니라 설치 기본값(1e9)으로 본다


def thresholds() -> dict:
    return {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}


def module_blob_sha() -> str:
    """이 파일의 git blob SHA(git hash-object 와 같은 값). 결과를 본 뒤 상수를 바꿔 다시 계산한 경우를 결과 파일로 알 수 있게 한다."""
    data = Path(__file__).read_bytes().replace(b"\r\n", b"\n")

    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def longest_run(mask: np.ndarray) -> np.ndarray:
    """마지막 축(시간)을 따라 True 가 이어진 가장 긴 길이(substep 수). 입력 [..., T] -> [...]."""
    m = np.asarray(mask, dtype=bool)
    flat = m.reshape(-1, m.shape[-1])
    out = np.zeros(flat.shape[0], dtype=np.int64)

    for i, row in enumerate(flat):
        best = cur = 0

        for v in row:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        out[i] = best

    return out.reshape(m.shape[:-1])


def stall_mask(wz: np.ndarray, cmd_wz: float, alive: np.ndarray | None = None) -> np.ndarray:
    """[T] 정체 구간. alive 가 있으면 살아 있는 구간만."""
    m = np.abs(wz) < STALL_FRAC * abs(cmd_wz)

    return m if alive is None else (m & alive)


def dc_envelope(qd, effort_limit, saturation_effort, velocity_limit):
    """DC 모터 토크-속도 곡선의 (하한, 상한). foothold_s2.robots.go2_params.dc_motor_clip / 설치 actuator_pd.py `_clip_effort` 와 같은 식. qd [T,J], 나머지 [J]."""
    qd, el, se, vl = (np.asarray(x, dtype=np.float64) for x in (qd, effort_limit, saturation_effort, velocity_limit))
    vmax = vl * (1.0 + el / se)
    qd = np.clip(qd, -vmax, vmax)
    top = np.minimum(se * (1.0 - qd / vl), el)
    bottom = np.maximum(se * (-1.0 - qd / vl), -el)

    return bottom, top


def _limit_check(q, target, lim, stall, hz):
    lo, hi = lim[:, 0], lim[:, 1]
    near_hi, near_lo = q >= hi - LIMIT_MARGIN_RAD, q <= lo + LIMIT_MARGIN_RAD
    pressed = (near_hi & (target > hi)) | (near_lo & (target < lo))      # [T,J]
    run = longest_run(pressed.T) / hz
    both = longest_run((pressed & stall[:, None]).T) / hz
    flagged = [int(j) for j in np.nonzero(both >= SUSTAIN_S)[0]]

    return {"verdict": "지지" if flagged else "반증", "joints": flagged, "longest_pressed_s": run.tolist(), "longest_pressed_while_stalled_s": both.tolist(),
            "near_limit_fraction": (near_hi | near_lo).mean(0).tolist()}


def joint_limit(q, target, hard, stall, hz: float = HZ, soft=None) -> dict:
    """q,target [T,J], hard/soft [J,2](하한,상한), stall [T]. 한계 근처 + 목표가 한계 밖 + 정체가 같은 시간에 지속된 관절. 판정은 hard 기준, soft 는 따로 같이 보고한다."""
    if q is None or target is None or hard is None:
        return {"verdict": "미확인", "reason": "관절 한계 입력 없음"}
    q, target = np.asarray(q), np.asarray(target)
    out = _limit_check(q, target, np.asarray(hard), stall, hz)
    out["note"] = "외형(예 -48도 근처)만으로 한계라 하지 않음: target 이 한계 밖이고 q 가 한계 안쪽 margin 이내인 경우만. 판정은 hard 한계 기준"
    out["soft"] = _limit_check(q, target, np.asarray(soft), stall, hz) if soft is not None else {"verdict": "미확인", "reason": "soft 한계 입력 없음"}

    return out


def actuator(q, target, computed, applied, qd, limits, stall, hz: float = HZ) -> dict:
    """계산 토크 · 적용 토크 · DC 곡선. [T,J]; limits = {effort_limit, saturation_effort, velocity_limit} 각 [J](실제 구동기 cfg 값).
    포화 = (a) 계산 토크와 적용 토크의 차가 문턱 초과(잘림, 속도 의존 잘림 포함) 또는 (b) 적용 토크가 그 순간 DC 곡선 상한의 98 % 이상. 정체와 겹쳐 0.5 s 지속되면 지지.
    limits 의 effort_limit 이 설치 기본값(>=1e6)이면 (b) 는 쓰지 않고 (a) 만 쓴다. 둘 다 못 쓰면 「미확인」. 마지막 substep 하나로 판정하지 않는다."""
    if computed is None or applied is None:
        return {"verdict": "미확인", "reason": "토크 입력 없음(계산 또는 적용 토크를 지원 API 가 안 줌)"}
    applied, computed = np.asarray(applied), np.asarray(computed)
    clip = np.abs(computed - applied) > CLIP_GAP_NM
    usable = limits is not None and qd is not None and np.all(np.asarray(limits["effort_limit"]) < EFFORT_LIMIT_SENTINEL)
    at_curve = np.zeros_like(clip)

    if usable:
        bottom, top = dc_envelope(qd, limits["effort_limit"], limits["saturation_effort"], limits["velocity_limit"])
        at_curve = ((applied > 0) & (applied >= SATURATION_FRAC * top)) | ((applied < 0) & (applied <= SATURATION_FRAC * bottom))
    sat = clip | at_curve
    run = longest_run((sat & stall[:, None]).T) / hz
    flagged = [int(j) for j in np.nonzero(run >= SUSTAIN_S)[0]]
    err = np.abs(np.asarray(target) - np.asarray(q)) if q is not None and target is not None else None
    verdict = "지지" if flagged else "반증"                                # 계산≠적용(잘림)은 실제 토크 제한의 완전한 척도다. 곡선 근처(98 %)는 한계가 쓸 만할 때만 본다

    return {"verdict": verdict, "joints": flagged, "clipped_fraction": clip.mean(0).tolist(), "at_dc_curve_fraction": at_curve.mean(0).tolist(), "curve_used": bool(usable),
            "longest_saturated_while_stalled_s": run.tolist(), "target_minus_q_mean_abs": None if err is None else err.mean(0).tolist(),
            "note": "곡선 근처(98 %) 판정은 못 씀(한계가 설치 기본값이거나 속도 없음): 잘림(계산≠적용)만으로 판정, 곡선 근처 포화는 미확인" if not usable else "잘림 또는 곡선 98 % 이상"}


def foot_support(force, kinds, stall, hz: float = HZ) -> dict:
    """force [T,L] 링크별 접촉 힘 크기(N), kinds 길이 L 의 문자열("foot","calf","thigh","base"...). 발이 아닌 링크의 접촉이 정체와 같은 시간에 지속되면 지지."""
    if force is None or kinds is None:
        return {"verdict": "미확인", "reason": "링크 접촉 입력 없음"}
    force = np.asarray(force)
    non_foot = [i for i, k in enumerate(kinds) if k != "foot"]
    on = force[:, non_foot] > CONTACT_FORCE_N
    run = longest_run(on.T) / hz
    run_stall = longest_run((on & stall[:, None]).T) / hz
    flagged = [kinds[non_foot[i]] + f"#{non_foot[i]}" for i in np.nonzero(run_stall >= SUSTAIN_S)[0]]

    return {"verdict": "지지" if flagged else "반증", "links": flagged, "longest_contact_s": run.tolist(), "longest_contact_while_stalled_s": run_stall.tolist(),
            "non_foot_link_indices": non_foot, "note": "접촉 힘 크기만으로는 접선 미끄럼을 모른다(track_contact_points 가 꺼져 있으면 링크 중심 XY 속도가 대용치)"}


def posture(target, stall, other_verdicts: list[str], feet_air_fraction=None) -> dict:
    """한계 · 포화 · 지지 접촉이 모두 반증인데도 정체이고 목표 자체가 안 움직이면 「정책의 불리한 자세」. 정체가 짧으면(<=50 %) «해당 없음»."""
    if target is None:
        return {"verdict": "미확인", "reason": "목표 관절각 없음"}
    t = np.asarray(target)
    frac = float(stall.mean())
    air = None if feet_air_fraction is None else float(feet_air_fraction)

    if stall.sum() <= 1 or frac <= POSTURE_MIN_STALL_FRACTION:
        return {"verdict": "해당 없음", "stall_fraction": frac, "target_std_while_stalled_mean": None, "target_flat": False, "feet_air_fraction": air, "note": "정체가 짧아 자세 가설을 판정할 대상이 아님(반증이 아니다)"}
    std = t[stall].std(0)
    flat = bool(np.mean(std) < POSTURE_MIN_TARGET_STD_RAD)

    if "미확인" in other_verdicts:
        verdict = "미확인"
    else:
        verdict = "지지" if (all(v == "반증" for v in other_verdicts) and flat) else "보류"

    return {"verdict": verdict, "stall_fraction": frac, "target_std_while_stalled_mean": float(np.mean(std)), "target_flat": flat, "feet_air_fraction": air,
            "note": "보류: 정체이지만 다른 가설 하나가 지지이거나 목표가 움직이는 경우. 거울 복제를 하지 않고 좌/우 독립 시작과 순서 반전으로 대조한다"}


def order_pair(follow_independent: float, follow_sequential: float) -> dict:
    """한 쌍(같은 회전 방향)의 yaw 추종 비: 독립 시작 대 연속 시작. 독립이 연속보다 ORDER_GAP 넘게 높으면 «순서/바닥 영향 지지»."""
    if follow_independent is None or follow_sequential is None or np.isnan(follow_independent) or np.isnan(follow_sequential):
        return {"verdict": "미확인", "reason": "측정 없음"}
    gap = float(follow_independent - follow_sequential)

    return {"verdict": "지지" if gap > ORDER_GAP else "반증", "independent": float(follow_independent), "sequential": float(follow_sequential), "gap": gap,
            "note": "전진 뒤 우회전에서만 정체하고 독립 시작에서는 회복되면 촬영 순서/바닥"}


def side_asymmetry(follow_left: float, follow_right: float) -> float:
    """독립 시작 좌/우 yaw 추종 비의 차(좌-우). 좌우 대칭 명령에서 0 에 가까워야 한다."""
    return float(follow_left - follow_right)


def judge(arrays: dict, cmd_wz: float) -> dict:
    """한 시행(한 env)의 200 Hz 배열 묶음 -> 가설별 판정. arrays 키: q qd target computed applied hard soft limits force kinds wz alive (없는 것은 None)."""
    stall = stall_mask(np.asarray(arrays["wz"]), cmd_wz, arrays.get("alive"))
    h1 = joint_limit(arrays.get("q"), arrays.get("target"), arrays.get("hard"), stall, soft=arrays.get("soft"))
    h2 = actuator(arrays.get("q"), arrays.get("target"), arrays.get("computed"), arrays.get("applied"), arrays.get("qd"), arrays.get("limits"), stall)
    h3 = foot_support(arrays.get("force"), arrays.get("kinds"), stall)
    h4 = posture(arrays.get("target"), stall, [h1["verdict"], h2["verdict"], h3["verdict"]])

    return {"stall_fraction": float(stall.mean()), "joint_limit": h1, "actuator": h2, "foot_support": h3, "posture": h4}
