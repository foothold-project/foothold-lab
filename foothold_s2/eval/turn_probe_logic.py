"""우회전 원인 분리 표(설계 v1.0 §7.1) 판정의 순수 계산. Kit 없이 시험된다.

입력은 200 Hz 물리 substep 시계열(numpy)이다. 판정 문턱은 결과를 보기 전에 여기 상수로 등록하고, 결과를 보고 바꾸지 않는다.
없는 물리량을 다른 값으로 대신 확정하지 않는다: 입력이 None 이면 그 가설은 「미확인」 이다.
가설 다섯: joint_limit · actuator · foot_support(발 아닌 링크 접촉) · posture(정책 자세) · order(촬영 순서/바닥).
"""

from __future__ import annotations

import numpy as np

HZ = 200.0
SUSTAIN_S = 0.5                    # 「해당 시간 지속」 의 최소 길이
LIMIT_MARGIN_RAD = 0.05            # 실제 q 가 한계에서 이만큼 안이면 「한계 근처」
SATURATION_FRAC = 0.98             # |적용 토크| >= 이 비율 x effort_limit 이면 포화
CLIP_GAP_NM = 1.0e-3               # 계산 토크와 적용 토크 차가 이보다 크면 클립됨
CONTACT_FORCE_N = 1.0              # 발 아닌 링크의 접촉 힘 문턱
STALL_FRAC = 0.1                   # |wz| < 0.1 |cmd_wz| 이면 정체
ORDER_GAP = 0.25                   # 독립 시작과 연속 시작의 yaw 추종 비 차이가 이보다 크면 순서 영향
POSTURE_MIN_TARGET_STD_RAD = 0.02  # 목표 관절각의 시간 표준편차가 이보다 작으면 「정책이 발을 안 움직임」


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


def joint_limit(q, target, hard, stall, hz: float = HZ) -> dict:
    """q,target [T,J], hard [J,2](하한,상한), stall [T]. 한계 근처 + 목표가 한계 밖 + 정체가 같은 시간에 지속된 관절."""
    if q is None or target is None or hard is None:
        return {"verdict": "미확인", "reason": "관절 한계 입력 없음"}
    q, target, hard = np.asarray(q), np.asarray(target), np.asarray(hard)
    lo, hi = hard[:, 0], hard[:, 1]
    near_hi = q >= hi - LIMIT_MARGIN_RAD
    near_lo = q <= lo + LIMIT_MARGIN_RAD
    out_hi = target > hi
    out_lo = target < lo
    pressed = (near_hi & out_hi) | (near_lo & out_lo)                     # [T,J]
    near_only = near_hi | near_lo
    run = longest_run(pressed.T) / hz                                      # [J]
    both = longest_run((pressed & stall[:, None]).T) / hz
    flagged = [int(j) for j in np.nonzero(both >= SUSTAIN_S)[0]]

    return {"verdict": "지지" if flagged else "반증", "joints": flagged, "longest_pressed_s": run.tolist(), "longest_pressed_while_stalled_s": both.tolist(),
            "near_limit_fraction": near_only.mean(0).tolist(), "note": "외형(예 -48도 근처)만으로 한계라 하지 않음: target 이 한계 밖이고 q 가 한계 안쪽 margin 이내인 경우만"}


def actuator(q, target, computed, applied, effort_limit, stall, hz: float = HZ) -> dict:
    """계산 토크 · 적용 토크 · 한계. [T,J], effort_limit [J]. 포화 지속 + 정체가 겹치면 지지. 마지막 substep 하나로 판정하지 않는다."""
    if computed is None or applied is None or effort_limit is None:
        return {"verdict": "미확인", "reason": "토크 입력 없음(계산 또는 적용 토크를 지원 API 가 안 줌)"}
    applied, computed, eff = np.asarray(applied), np.asarray(computed), np.asarray(effort_limit)
    sat = np.abs(applied) >= SATURATION_FRAC * eff[None, :]
    clip = np.abs(computed - applied) > CLIP_GAP_NM
    sat_run = longest_run((sat & stall[:, None]).T) / hz
    flagged = [int(j) for j in np.nonzero(sat_run >= SUSTAIN_S)[0]]
    err = np.abs(np.asarray(target) - np.asarray(q)) if q is not None and target is not None else None

    return {"verdict": "지지" if flagged else "반증", "joints": flagged, "saturated_fraction": sat.mean(0).tolist(), "clipped_fraction": clip.mean(0).tolist(),
            "longest_saturated_while_stalled_s": sat_run.tolist(), "target_minus_q_mean_abs": None if err is None else err.mean(0).tolist()}


def foot_support(force, kinds, stall, hz: float = HZ) -> dict:
    """force [T,L] 링크별 접촉 힘 크기(N), kinds 길이 L 의 문자열("foot","calf","thigh","base","hip"...). 발이 아닌 링크의 접촉이 정체와 같은 시간에 지속되면 지지."""
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
    """한계 · 포화 · 지지 접촉이 모두 반증인데도 정체이고 목표 자체가 안 움직이면 「정책의 불리한 자세」."""
    if target is None:
        return {"verdict": "미확인", "reason": "목표 관절각 없음"}
    t = np.asarray(target)
    if stall.sum() <= 1:                                                  # 정체가 없으면 자세 문제를 물을 이유가 없다
        return {"verdict": "반증", "stall_fraction": float(stall.mean()), "target_std_while_stalled_mean": None, "target_flat": False, "feet_air_fraction": None if feet_air_fraction is None else float(feet_air_fraction),
                "note": "정체 구간 없음"}
    std = t[stall].std(0)
    flat = bool(np.nanmean(std) < POSTURE_MIN_TARGET_STD_RAD)
    others_clear = all(v == "반증" for v in other_verdicts)
    stalled = bool(stall.mean() > 0.5)

    if "미확인" in other_verdicts:
        verdict = "미확인"
    else:
        verdict = "지지" if (others_clear and stalled and flat) else "반증" if not stalled else "보류"

    return {"verdict": verdict, "stall_fraction": float(stall.mean()), "target_std_while_stalled_mean": float(np.nanmean(std)), "target_flat": flat,
            "feet_air_fraction": None if feet_air_fraction is None else float(feet_air_fraction),
            "note": "보류: 정체이지만 다른 가설 하나가 지지이거나 목표가 움직이는 경우. 거울 복제를 하지 않고 좌/우 독립 시작과 순서 반전으로 대조한다"}


def order(follow_independent: dict, follow_sequential: dict | None) -> dict:
    """yaw 추종 비(실제/명령) 의 독립 시작 대 연속(전진 뒤) 시작. 키는 'left','right'. 둘 다 있어야 판정한다."""
    if not follow_sequential:
        return {"verdict": "미확인", "reason": "연속 시작 측정 없음"}
    gaps = {k: abs(follow_independent[k] - follow_sequential[k]) for k in follow_independent if k in follow_sequential}

    if not gaps:
        return {"verdict": "미확인", "reason": "짝이 되는 측 없음"}
    worst = max(gaps, key=gaps.get)
    recovered = follow_independent.get("right", 0.0) > follow_sequential.get("right", 0.0) + ORDER_GAP

    return {"verdict": "지지" if gaps[worst] > ORDER_GAP and recovered else "반증", "gaps": gaps, "right_recovers_when_independent": bool(recovered),
            "note": "전진 뒤 우회전에서만 정체하고 독립 시작에서는 회복되면 촬영 순서/바닥"}


def side_asymmetry(follow_left: float, follow_right: float) -> float:
    """독립 시작 좌/우 yaw 추종 비의 차(좌-우). 좌우 대칭 명령에서 0 에 가까워야 한다."""
    return float(follow_left - follow_right)


def judge(arrays: dict, cmd_wz: float) -> dict:
    """한 시행(한 env)의 200 Hz 배열 묶음 -> 가설별 판정. arrays 키: q target computed applied hard effort_limit force kinds wz alive (없는 것은 None)."""
    stall = stall_mask(np.asarray(arrays["wz"]), cmd_wz, arrays.get("alive"))
    h1 = joint_limit(arrays.get("q"), arrays.get("target"), arrays.get("hard"), stall)
    h2 = actuator(arrays.get("q"), arrays.get("target"), arrays.get("computed"), arrays.get("applied"), arrays.get("effort_limit"), stall)
    h3 = foot_support(arrays.get("force"), arrays.get("kinds"), stall)
    h4 = posture(arrays.get("target"), stall, [h1["verdict"], h2["verdict"], h3["verdict"]])

    return {"stall_fraction": float(stall.mean()), "joint_limit": h1, "actuator": h2, "foot_support": h3, "posture": h4}
