"""우회전 probe 의 시행표와 요약 계산(순수, CPU 시험). Kit 스크립트(turn_probe.py)가 쓴다.

시행 다섯, 모두 타일 중앙 env 원점에서 시작하고 4 env 씩, 기록 구간 8 s(200 Hz):
  indep_right      reset -> 우회전(-1.2) 8 s                (독립 시작)
  indep_left       reset -> 좌회전(+1.2) 8 s                (독립 시작, 같은 초기 yaw)
  fwd_then_right   reset -> 전진 0.5 4 s -> 우회전 8 s      (연속 시작, 전진 뒤)
  left_then_right  reset -> 좌회전 4 s -> 우회전 8 s        (순서 반전 대조)
  right_then_left  reset -> 우회전 4 s -> 좌회전 8 s        (순서 반전 대조)
추가 경우(표에는 있고 기본 실행에는 없다, --cases 로 고른다):
  fwd_then_left    reset -> 전진 0.5 4 s -> 좌회전 8 s      (fwd_then_right 의 좌우 대칭)
앞 구간(pre)은 기록하지 않고 마지막 8 s 만 기록한다. 로봇을 거울 복제하지 않는다.
"""

from __future__ import annotations

import numpy as np

from foothold_s2.eval import turn_probe_logic as L

RECORD_S = 8.0
PRE_S = 4.0
WZ = 1.2
# 경우 표(한 곳). 새 경우(후진 · 정지 · 걸으며 돌기)는 여기 한 줄을 더하고, 기본 실행에 넣을지는 DEFAULT_CASES 로 정한다. 기존 다섯의 정의 · 이름은 바꾸지 않는다(기존 결과와 비교).
PROTOCOLS = {
    "indep_right": {"pre": None, "cmd": (0.0, 0.0, -WZ)},
    "indep_left": {"pre": None, "cmd": (0.0, 0.0, +WZ)},
    "fwd_then_right": {"pre": (0.5, 0.0, 0.0), "cmd": (0.0, 0.0, -WZ)},
    "left_then_right": {"pre": (0.0, 0.0, +WZ), "cmd": (0.0, 0.0, -WZ)},
    "right_then_left": {"pre": (0.0, 0.0, -WZ), "cmd": (0.0, 0.0, +WZ)},
    "fwd_then_left": {"pre": (0.5, 0.0, 0.0), "cmd": (0.0, 0.0, +WZ)},      # SONNET-X25d: fwd_then_right 의 좌우 대칭(전진 0.5 4 s -> 좌회전 +1.2 8 s)
    "walk_turn_left": {"pre": None, "cmd": (0.5, 0.0, +0.5)},               # SONNET-X26a(J-T7): 걸으며 돌기. reset -> 전진 0.5 + 좌회전 0.5 8 s(앞 구간 없음). 명령 과정 단계(JUDGE-SPEC 4.4)의 성공선 입력
    "walk_turn_right": {"pre": None, "cmd": (0.5, 0.0, -0.5)},
}
DEFAULT_CASES = ("indep_right", "indep_left", "fwd_then_right", "left_then_right", "right_then_left")    # --cases 를 안 주면 도는 경우(X25 의 기존 다섯, 순서 고정)


def select_cases(spec: str | None) -> list[str]:
    """--cases 값 -> 경우 이름 목록. None/'' = 기본 다섯, 'all' = 표 전체, 'a,b' = 그 이름들(표에 없으면 ValueError, 중복 거절)."""
    if not spec:
        return list(DEFAULT_CASES)
    if spec == "all":
        return list(PROTOCOLS)
    names = [n.strip() for n in spec.split(",") if n.strip()]
    bad = [n for n in names if n not in PROTOCOLS]
    if bad or not names or len(set(names)) != len(names):
        raise ValueError(f"--cases: 알 수 없거나 중복된 경우 {bad or names} (표: {list(PROTOCOLS)})")

    return names


FOLLOW_INDEPENDENT = {"right": "indep_right", "left": "indep_left"}
ORDER_PAIRS = {                                                         # 연속 시행마다 따로 판정한다(맥락을 섞지 않는다): 이름 -> (독립 시행, 연속 시행)
    "right_after_forward": ("indep_right", "fwd_then_right"),           # 설계 §7.1 의 촬영 순서 가설(전진 뒤 우회전에서만 정체)
    "left_after_forward": ("indep_left", "fwd_then_left"),              # X25d: 위의 좌우 대칭
    "right_after_left_turn": ("indep_right", "left_then_right"),
    "left_after_right_turn": ("indep_left", "right_then_left"),
}


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
    """per_protocol[이름] = env 별 judge 결과 리스트 + 'follow' 리스트(env 별 yaw 추종 비) + 'kept'(안 넘어진 env). 가설별 «지지한 env 수/남은 env» 와 순서 판정."""
    out = {"protocols": {}}

    for name, envs in per_protocol.items():
        total = len(envs["judge"])
        kept = list(envs.get("kept") or [True] * total)                    # 한 번도 안 넘어진 env 만 센다(넘어져 reset 된 env 의 뒤 기록은 뜻이 없다)
        if len(kept) != total:
            raise ValueError(f"{name}: kept {len(kept)} 와 env {total} 가 다르다")
        follow = [f for f, k in zip(envs["follow"], kept) if k]
        judge = [j for j, k in zip(envs["judge"], kept) if k]
        row = {"n_env": len(judge), "n_total": total, "n_excluded_fallen": total - len(judge), "follow_median": float(np.nanmedian(follow)) if follow else float("nan")}

        for h in ("joint_limit", "actuator", "foot_support", "posture"):
            verdicts = [j[h]["verdict"] for j in judge]
            row[h] = {v: verdicts.count(v) for v in sorted(set(verdicts))}
        out["protocols"][name] = row
    fm = {n: v["follow_median"] for n, v in out["protocols"].items()}
    out["order"] = {name: L.order_pair(fm.get(a), fm.get(b)) for name, (a, b) in ORDER_PAIRS.items()}
    ind = {side: fm[p] for side, p in FOLLOW_INDEPENDENT.items() if p in fm}
    out["side_asymmetry_independent"] = L.side_asymmetry(ind["left"], ind["right"]) if len(ind) == 2 else None

    return out
