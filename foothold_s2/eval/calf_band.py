"""종아리 펴짐 한계 띠 값 r 의 사전 점검 (SONNET-X25, W3-P1): probe 가 남긴 arrays_<시행>.npz 와 probe_result.json 만 읽는다. Kit 불필요. 학습 아님.

    r(t) = sum_{j in calf 네 관절} max(0, q_j(t) - (hard_hi_j - MARGIN))          [rad, 물리 substep 200 Hz 마다]
    벌점 = W * r  (초안 DESIGN-W3 §3.1: W=2.0, MARGIN=0.05; 이 파일은 «벌점이 아니라 r 과 W*r 을 잰다»)

hard_hi_j 는 probe_result.json static.hard_limits 의 calf 관절 상한이다(상수를 박지 않는다). 칸 = 안 넘어진 env(kept) 평균 (env 최소~최대).
substep 평균은 정책 스텝 평균과 거의 같지만 같은 값은 아니다(보상은 정책 스텝 끝 q 로 계산되므로 4 substep 중 마지막 것). 이 표는 «띠가 쓰이는 정도»의 크기를 보는 점검이다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

MARGIN = 0.05
W = 2.0
FORWARD_RULE_PER_STEP = 0.03                     # 초안 §6 W3-P1: 정상 전진이 이 값을 넘으면 W 를 1.0 으로 내리는 것을 검토
PROTOCOLS = ("fwd0.5", "fwd1.0", "indep_right", "fwd_then_right", "left_then_right", "indep_left", "right_then_left")


def calf_columns(joint_names) -> list[int]:
    cols = [i for i, n in enumerate(joint_names) if "calf" in n.lower()]
    if len(cols) != 4:
        raise ValueError(f"calf 관절이 4 개가 아니다: {cols} {list(joint_names)}")

    return cols


def band_value(q, hi, margin: float = MARGIN):
    """q [E,T,4] (calf 네 관절각), hi [4] (hard 상한). 반환 r [E,T] = 네 관절 합 max(0, q - (hi - margin))."""
    q, hi = np.asarray(q, dtype=float), np.asarray(hi, dtype=float)
    if q.ndim != 3 or q.shape[2] != 4 or hi.shape != (4,):
        raise ValueError(f"모양 불일치: q {q.shape} hi {hi.shape}")

    return np.maximum(0.0, q - (hi - margin)).sum(axis=2)


def occupancy(q, hi, margin: float = MARGIN):
    """관절마다 띠 안(q > hi - margin) 에 있던 시간 비율 [E,4]."""
    q, hi = np.asarray(q, dtype=float), np.asarray(hi, dtype=float)

    return (q > (hi - margin)).mean(axis=1)


def load(folder) -> dict:
    folder = Path(folder)
    res = json.loads((folder / "probe_result.json").read_text(encoding="utf-8"))
    st = res["static"]
    cols = calf_columns(st["joint_names"])
    hi = np.asarray(st["hard_limits"], dtype=float)[cols, 1]
    out = {}
    for proto in PROTOCOLS:
        f = folder / f"arrays_{proto}.npz"
        if not f.exists():
            continue
        z = np.load(f)
        q = z["q"][:, :, cols]
        kept = np.asarray(z["kept"] if "kept" in z.files else z["alive"][:, -1], dtype=bool)
        r = band_value(q, hi)
        out[proto] = {"r_mean": r.mean(axis=1), "r_max": r.max(axis=1), "r_pos": (r > 0).mean(axis=1), "occ": occupancy(q, hi), "kept": kept}

    return {"calf_names": [st["joint_names"][c] for c in cols], "hard_hi": hi.tolist(), "by_protocol": out, "fixed_terrain": res.get("fixed_terrain"),
            "checkpoint_sha256": res.get("checkpoint_sha256", "")[:12], "envs": res.get("envs")}


def _cell(x, keep, fmt="{:.4f}"):
    if not keep.any():
        return f"전원 낙상 n=0/{len(keep)}"
    v = x[keep]

    return f"{fmt.format(v.mean())} ({fmt.format(v.min())}~{fmt.format(v.max())}) n={int(keep.sum())}/{len(keep)}"


def table(name: str, d: dict, protocols=PROTOCOLS) -> str:
    lines = [f"### {name} · ckpt {d['checkpoint_sha256']} · hard 상한 {', '.join(f'{n} {h:.4f}' for n, h in zip(d['calf_names'], d['hard_hi']))} · margin {MARGIN} rad · W={W} · 칸 = 안 넘어진 env 평균 (env 최소~최대) n=남은/전체",
             "| 시행 | r 평균 [rad] | W*r 평균 [/step] | r>0 인 시간 비율 | r 최대 [rad] | " + " | ".join(f"{n} 띠 점유" for n in d["calf_names"]) + " |",
             "|---|---|---|---|---|" + "---|" * len(d["calf_names"])]
    for p in protocols:
        v = d["by_protocol"].get(p)
        if v is None:
            lines.append(f"| {p} | 미측정 |  |  |  |" + " |" * len(d["calf_names"]))
            continue
        k = v["kept"]
        occ = " | ".join(_cell(v["occ"][:, j], k, "{:.2f}") for j in range(len(d["calf_names"])))
        lines.append(f"| {p} | {_cell(v['r_mean'], k)} | {_cell(W * v['r_mean'], k)} | {_cell(v['r_pos'], k, '{:.2f}')} | {_cell(v['r_max'], k)} | {occ} |")

    return "\n".join(lines)


def forward_rule_line(name: str, d: dict) -> str:
    """전진 두 시행의 W*r 평균(안 넘어진 env 평균)이 0.03 을 넘는지 사실만 적는다. 규칙을 적용(W 변경)하는 것은 설계자 몫."""
    parts = []
    for p in ("fwd0.5", "fwd1.0"):
        v = d["by_protocol"].get(p)
        if v is None or not v["kept"].any():
            parts.append(f"{p} 미측정 또는 전원 낙상")
            continue
        x = float((W * v["r_mean"])[v["kept"]].mean())
        parts.append(f"{p} W*r {x:.4f}/step ({'> ' if x > FORWARD_RULE_PER_STEP else '<= '}{FORWARD_RULE_PER_STEP})")

    return f"- {name}: " + " · ".join(parts)


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or len(argv) % 2:
        raise SystemExit("usage: calf_band <이름1> <폴더1> [<이름2> <폴더2> ...]")
    pairs = [(argv[i], load(argv[i + 1])) for i in range(0, len(argv), 2)]
    shas = {n: (d.get("fixed_terrain") or {}).get("assignment_sha256") for n, d in pairs}
    if len(pairs) > 1 and (None in shas.values() or len(set(shas.values())) != 1):
        raise SystemExit(f"비교 불가: 고정 지형 칸이 없거나 서로 다르다 {shas}")
    print("W3-P1 사전 점검(미검증 집계, reviewer 확인 전). r = 네 calf 의 sum max(0, q - (hard_hi - 0.05)), 벌점은 W*r 로 계산만 했고 학습에 쓴 적 없다. 이 표의 q 는 200 Hz substep 값이고 보상은 정책 스텝 끝 q 로 계산되므로 같은 값이 아니다\n")
    for name, d in pairs:
        print(table(name, d))
        print()
    for name, d in pairs:
        print(forward_rule_line(name, d))


if __name__ == "__main__":
    main()
