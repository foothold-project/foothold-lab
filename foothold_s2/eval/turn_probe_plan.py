"""우회전 probe 의 시행표와 요약 계산(순수, CPU 시험). Kit 스크립트(turn_probe.py)가 쓴다.

시행 다섯, 모두 타일 중앙 env 원점에서 시작하고 4 env 씩, 기록 구간 8 s(200 Hz):
  indep_right      reset -> 우회전(-1.2) 8 s                (독립 시작)
  indep_left       reset -> 좌회전(+1.2) 8 s                (독립 시작, 같은 초기 yaw)
  fwd_then_right   reset -> 전진 0.5 4 s -> 우회전 8 s      (연속 시작, 전진 뒤)
  left_then_right  reset -> 좌회전 4 s -> 우회전 8 s        (순서 반전 대조)
  right_then_left  reset -> 우회전 4 s -> 좌회전 8 s        (순서 반전 대조)
앞 구간(pre)은 기록하지 않고 마지막 8 s 만 기록한다. 로봇을 거울 복제하지 않는다.
"""

from __future__ import annotations

import numpy as np

from foothold_s2.eval import turn_probe_logic as L

RECORD_S = 8.0
PRE_S = 4.0
WZ = 1.2
PROTOCOLS = {
    "indep_right": {"pre": None, "cmd": (0.0, 0.0, -WZ)},
    "indep_left": {"pre": None, "cmd": (0.0, 0.0, +WZ)},
    "fwd_then_right": {"pre": (0.5, 0.0, 0.0), "cmd": (0.0, 0.0, -WZ)},
    "left_then_right": {"pre": (0.0, 0.0, +WZ), "cmd": (0.0, 0.0, -WZ)},
    "right_then_left": {"pre": (0.0, 0.0, -WZ), "cmd": (0.0, 0.0, +WZ)},
}
FOLLOW_INDEPENDENT = {"right": "indep_right", "left": "indep_left"}
FOLLOW_SEQUENTIAL = {"right": ("fwd_then_right", "left_then_right"), "left": ("right_then_left",)}


def classify_link(name: str) -> str:
    """Go2 링크 이름 -> 'foot' | 'calf' | 'thigh' | 'hip' | 'base' | 'head' | 'other'. 발만 'foot', 나머지는 전부 발 아닌 링크로 센다(모르는 이름은 'other', base 로 치지 않는다)."""
    n = name.lower()

    for key in ("foot", "calf", "thigh", "hip", "head"):
        if key in n:
            return key
    if n == "base" or "trunk" in n:
        return "base"

    return "other"


def yaw_follow(wz: np.ndarray, alive: np.ndarray, cmd_wz: float) -> float:
    """살아 있는 구간 평균 yaw rate / 명령. 살아 있는 구간이 없으면 NaN."""
    a = np.asarray(alive, dtype=bool)

    return float(np.asarray(wz)[a].mean() / cmd_wz) if a.any() else float("nan")


def summarize(per_protocol: dict) -> dict:
    """per_protocol[이름] = env 별 judge 결과 리스트 + 'follow' 리스트(env 별 yaw 추종 비). 가설별 «지지한 env 수/전체» 와 순서 판정."""
    out = {"protocols": {}}

    for name, envs in per_protocol.items():
        row = {"n_env": len(envs["judge"]), "follow_median": float(np.nanmedian(envs["follow"]))}

        for h in ("joint_limit", "actuator", "foot_support", "posture"):
            verdicts = [j[h]["verdict"] for j in envs["judge"]]
            row[h] = {v: verdicts.count(v) for v in sorted(set(verdicts))}
        out["protocols"][name] = row
    ind = {side: out["protocols"][p]["follow_median"] for side, p in FOLLOW_INDEPENDENT.items() if p in out["protocols"]}
    seq = {}

    for side, names in FOLLOW_SEQUENTIAL.items():
        vals = [out["protocols"][n]["follow_median"] for n in names if n in out["protocols"]]
        if vals:
            seq[side] = float(np.median(vals))
    out["order"] = L.order(ind, seq) if len(ind) == 2 and seq else {"verdict": "미확인", "reason": "독립 좌/우 또는 연속 측정 없음"}
    out["side_asymmetry_independent"] = L.side_asymmetry(ind["left"], ind["right"]) if len(ind) == 2 else None

    return out
