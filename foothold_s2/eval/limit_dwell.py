"""관절 한계 근처 체류 시간 집계 (SONNET-X25 T5): probe 가 남긴 arrays_<시행>.npz 와 probe_result.json 만 읽는다. Kit 불필요.

정의(env 마다, 관절마다, 기록 전체 구간 T 에 대한 비율):
  near_lower  = q <= 하한 + MARGIN        near_upper = q >= 상한 - MARGIN        near = 둘 중 하나
  target_beyond = target 이 [하한, 상한] 밖
  near_and_beyond = near 이면서 target_beyond (한계에 붙어 있는데 정책은 더 밀고 있는 시간)
hard 와 soft 한계 각각. MARGIN 은 turn_probe_logic.LIMIT_MARGIN_RAD 와 같은 값(import 해서 쓴다).
이 집계는 probe 판정기(joint_limit)와 다르다: 판정기는 정체 시간과 겹치는 지속 구간만 세고, 여기는 정체 여부와 무관하게 전체 시간 비율이다.
기록 구간에서 한 번이라도 넘어진 env(kept 가 거짓)는 평균에서 뺀다. 두 체크포인트를 나란히 놓는 표는 고정 지형 칸(fixed_terrain)이 같을 때만 만든다(probe 가 --fixed-terrain 으로 돌지 않은 결과는 비교하지 않는다).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from foothold_s2.eval import fixed_terrain

try:
    from foothold_s2.eval.turn_probe_logic import LIMIT_MARGIN_RAD as MARGIN
except ImportError:                                                  # 단독 실행 시험용
    MARGIN = 0.05

PROTOCOLS = ("indep_right", "fwd_then_right", "left_then_right", "indep_left", "right_then_left")
KEYS = ("near", "near_lower", "near_upper", "target_beyond", "near_and_beyond")


def dwell(q, target, limits, margin: float = MARGIN) -> dict:
    """q, target [E,T,J]; limits [J,2]. 반환: 각 KEYS 마다 per_env [E,J] 배열."""
    q, target, lim = np.asarray(q, dtype=float), np.asarray(target, dtype=float), np.asarray(limits, dtype=float)
    if q.ndim != 3 or q.shape != target.shape or lim.shape != (q.shape[2], 2):
        raise ValueError(f"모양 불일치: q {q.shape} target {target.shape} limits {lim.shape}")
    lo, hi = lim[:, 0], lim[:, 1]
    near_lower, near_upper = q <= lo + margin, q >= hi - margin
    near = near_lower | near_upper
    beyond = (target < lo) | (target > hi)
    masks = {"near": near, "near_lower": near_lower, "near_upper": near_upper, "target_beyond": beyond, "near_and_beyond": near & beyond}

    return {k: m.mean(axis=1) for k, m in masks.items()}


def load(folder) -> dict:
    """폴더 하나 -> {시행: {"hard": dwell, "soft": dwell}} + 관절 이름 + 메타."""
    folder = Path(folder)
    res = json.loads((folder / "probe_result.json").read_text(encoding="utf-8"))
    st = res["static"]
    out = {}
    for proto in PROTOCOLS:
        f = folder / f"arrays_{proto}.npz"
        if not f.exists():
            continue
        z = np.load(f)
        out[proto] = {"hard": dwell(z["q"], z["target"], st["hard_limits"]), "soft": dwell(z["q"], z["target"], st["soft_limits"])}

    for proto, v in out.items():
        z = np.load(folder / f"arrays_{proto}.npz")
        v["kept"] = np.asarray(z["kept"] if "kept" in z.files else z["alive"][:, -1], dtype=bool)               # 옛 결과는 kept 가 없어 기록 구간 끝 생존으로 대신한다

    return {"joint_names": st["joint_names"], "by_protocol": out, "fixed_terrain": res.get("fixed_terrain"), "checkpoint_sha256": res.get("checkpoint_sha256", "")[:12], "task": res.get("task"), "map_mode": res.get("map_mode"), "margin_rad": MARGIN}


TABLE_PROTOCOLS = ("indep_right", "fwd_then_right", "left_then_right", "indep_left", "right_then_left")           # 우회전 셋 + 좌회전 둘


def table(name: str, data: dict, which: str = "hard", key: str = "near", protocols=TABLE_PROTOCOLS) -> str:
    """12 관절 x 시행 표. 칸 = 안 넘어진 env 평균 (env 최소~최대) n=남은/전체. 정의 한 줄을 머리에 둔다."""
    names = data["joint_names"]
    lines = [f"### {name} · {which} 한계 · {key} · margin {data['margin_rad']} rad · ckpt {data['checkpoint_sha256']} · 기록 전체 구간 비율(정체 여부와 무관), 칸 = 안 넘어진 env 평균 (env 최소~최대) n=남은/전체",
             "| 관절 | " + " | ".join(protocols) + " |", "|---|" + "---|" * len(protocols)]
    for j, n in enumerate(names):
        cells = []
        for p in protocols:
            v = data["by_protocol"].get(p)
            if v is None:
                cells.append("미측정")
                continue
            keep = v["kept"]
            if not keep.any():
                cells.append(f"전원 낙상 n=0/{len(keep)}")
                continue
            x = v[which][key][keep, j]
            cells.append(f"{x.mean():.2f} ({x.min():.2f}~{x.max():.2f}) n={int(keep.sum())}/{len(keep)}")
        lines.append(f"| {n} | " + " | ".join(cells) + " |")

    return "\n".join(lines)


def check_comparable(pairs) -> None:
    """둘 이상을 나란히 놓으려면 모두 같은 고정 지형 칸(fixed_terrain 기록이 있고 배열 SHA 가 같음)이어야 한다. 아니면 표를 만들지 않는다."""
    if len(pairs) < 2:
        return
    recs = {name: d.get("fixed_terrain") for name, d in pairs}
    shas = {name: (r or {}).get("assignment_sha256") for name, r in recs.items()}

    if any(r is None for r in recs.values()) or len(set(shas.values())) != 1:
        raise SystemExit(f"비교 불가: 고정 지형 칸이 없거나 서로 다르다 {shas} (probe 를 --fixed-terrain 으로 다시 돌린 결과만 나란히 놓는다)")


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 1 or len(argv) % 2:
        raise SystemExit("usage: limit_dwell <이름1> <폴더1> [<이름2> <폴더2> ...]   (미검증 집계: reviewer 확인 전에는 판정에 쓰지 않는다)")
    pairs = [(argv[i], load(argv[i + 1])) for i in range(0, len(argv), 2)]
    check_comparable(pairs)
    print("미검증 집계(reviewer 확인 전). probe 판정기와 다른 정의: 정체 여부와 무관한 전체 시간 비율, limit_dwell.py 머리 참고\n")
    for name, d in pairs:
        print(f"- {name}: 지형 " + (fixed_terrain.describe(d["fixed_terrain"]) if d.get("fixed_terrain") else "고정 안 함(env 별 지형이 제각각)"))
    print()
    for which in ("hard", "soft"):
        for key in ("near", "near_and_beyond"):
            for name, d in pairs:
                print(table(name, d, which, key))
                print()


if __name__ == "__main__":
    main()
