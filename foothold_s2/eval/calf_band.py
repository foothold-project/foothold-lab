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

from foothold_s2.eval import turn_probe_plan as P
from foothold_s2.eval import turn_probe_logic as L

STALL_FRAC = L.STALL_FRAC                         # |wz| < 0.1 |cmd_wz| 이면 정체(판정기와 같은 값)
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


def band_flags(q, hi, margin: float = MARGIN):
    """q [E,T,4], hi [4]. 띠 안(q > hi - margin) 인지 bool [E,T,4]."""
    return np.asarray(q, dtype=float) > (np.asarray(hi, dtype=float) - margin)


def max_calf_dwell(q, hi, wz, cmd_wz: float, margin: float = MARGIN) -> dict:
    """W3-T4: env 마다 «네 calf 중 띠 체류 비율이 가장 큰 값». 두 가지로 센다.
      whole   = 기록 전체 구간 중 띠 안에 있던 시간 비율(관절마다), 그 최댓값
      stalled = 정체 구간(|wz| < STALL_FRAC |cmd_wz|) 만 분모로 한 같은 비율의 최댓값. 정체 시간이 없는 env 는 NaN(0 이 아니다)
    n_stalled = 정체 substep 수, argmax = 가장 큰 관절 열(0~3)."""
    flags = band_flags(q, hi, margin)
    wz = np.asarray(wz, dtype=float)
    if flags.ndim != 3 or wz.shape != flags.shape[:2]:
        raise ValueError(f"모양 불일치: q {flags.shape} wz {wz.shape}")
    whole_j = flags.mean(axis=1)
    stall = np.abs(wz) < STALL_FRAC * abs(cmd_wz)
    n = stall.sum(axis=1)
    per_j = (flags & stall[:, :, None]).sum(axis=1) / np.maximum(n, 1)[:, None]

    return {"whole": whole_j.max(axis=1), "stalled": np.where(n > 0, per_j.max(axis=1), np.nan), "n_stalled": n, "argmax_stalled": per_j.argmax(axis=1), "argmax_whole": whole_j.argmax(axis=1)}


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
        cmd = P.PROTOCOLS.get(proto, {}).get("cmd")
        if cmd is not None and "wz" in z.files:                                   # 회전 시행만(전진 걸음은 정체 정의가 없다)
            out[proto]["dwell"] = max_calf_dwell(q, hi, z["wz"], cmd[2])
            if "alive" in z.files:                                                    # env 별 yaw 추종 비(turn_probe_plan.yaw_follow 와 같은 정의)
                al = np.asarray(z["alive"], dtype=bool)
                wzz = np.asarray(z["wz"], dtype=float)
                out[proto]["follow"] = np.array([wzz[e][al[e]].mean() / cmd[2] if al[e].any() else np.nan for e in range(wzz.shape[0])])

    return {"calf_names": [st["joint_names"][c] for c in cols], "hard_hi": hi.tolist(), "by_protocol": out, "fixed_terrain": res.get("fixed_terrain"),
            "checkpoint_sha256": res.get("checkpoint_sha256", "")[:12], "envs": res.get("envs")}


def _cell(x, keep, fmt="{:.4f}"):
    if not keep.any():
        return f"전원 낙상 n=0/{len(keep)}"
    v = x[keep]

    return f"{fmt.format(v.mean())} ({fmt.format(v.min())}~{fmt.format(v.max())}) n={int(keep.sum())}/{len(keep)}"


def _nan_cell(x, keep, fmt="{:.2f}"):
    """NaN(정체 시간 없음)을 뺀 env 평균. 남은 수를 적는다."""
    ok = keep & ~np.isnan(x)
    if not ok.any():
        return f"정체 없음 n=0/{int(keep.sum())}"
    v = x[ok]

    return f"{fmt.format(v.mean())} ({fmt.format(v.min())}~{fmt.format(v.max())}) n={int(ok.sum())}/{int(keep.sum())}"


def table(name: str, d: dict, protocols=PROTOCOLS) -> str:
    lines = [f"### {name} · ckpt {d['checkpoint_sha256']} · hard 상한 {', '.join(f'{n} {h:.4f}' for n, h in zip(d['calf_names'], d['hard_hi']))} · margin {MARGIN} rad · W={W} · 칸 = 안 넘어진 env 평균 (env 최소~최대) n=남은/전체",
             "| 시행 | r 평균 [rad] | W*r 평균 [/step] | r>0 인 시간 비율 | r 최대 [rad] | " + " | ".join(f"{n} 띠 점유" for n in d["calf_names"]) + " | 최대 calf 체류(정체 구간 한정) | 최대 calf 체류(전체 구간) | 넘어진 env 수 |",
             "|---|---|---|---|---|" + "---|" * (len(d["calf_names"]) + 3)]
    for p in protocols:
        v = d["by_protocol"].get(p)
        if v is None:
            lines.append(f"| {p} | 미측정 |  |  |  |" + " |" * (len(d["calf_names"]) + 3))
            continue
        k = v["kept"]
        occ = " | ".join(_cell(v["occ"][:, j], k, "{:.2f}") for j in range(len(d["calf_names"])))
        dw = v.get("dwell")
        st, wh = (_nan_cell(dw["stalled"], k), _nan_cell(dw["whole"], k)) if dw is not None else ("해당 없음", "해당 없음")
        lines.append(f"| {p} | {_cell(v['r_mean'], k)} | {_cell(W * v['r_mean'], k)} | {_cell(v['r_pos'], k, '{:.2f}')} | {_cell(v['r_max'], k)} | {occ} | {st} | {wh} | {int((~k).sum())}/{len(k)} |")

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
