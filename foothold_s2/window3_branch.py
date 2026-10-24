"""창 3 분기표 입력 L · R · D 와 분기 판정, 창 판정 회전 층(기록 · 경고 · 멈춤) (SONNET-X25 W3-T6 · W3-P2). 순수 계산 + 파일 읽기, Kit 불필요.

기준 상수는 window3_criteria.py 에 있다(결과 전에 고정). 이 모듈은 상수를 바꾸지 않고 적용만 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from foothold_s2 import window3_criteria as K


def spin_inputs(map_modes: dict, mode: str = "eval_pred") -> dict:
    """map_modes.json 에서 L(spin+1.2) · R(spin-1.2) 요추종 중앙값과 spin 생존 수."""
    m = map_modes["modes"][mode]

    return {"L": float(m["spin+1.2"]["yaw_follow_median"]), "R": float(m["spin-1.2"]["yaw_follow_median"]),
            "alive_L": int(m["spin+1.2"]["alive_envs_at_end"]), "alive_R": int(m["spin-1.2"]["alive_envs_at_end"]), "envs": int(map_modes["envs"])}


def rotation_layer(cur: dict, prev: dict | None = None) -> dict:
    """기록 · 경고 · 멈춤. cur · prev = spin_inputs 꼴. 멈춤이 있으면 level 멈춤, 경고만 있으면 경고, 아니면 통과."""
    L, R, envs = cur["L"], cur["R"], cur["envs"]
    lo, diff = min(L, R), abs(L - R)
    record = {"L": L, "R": R, "diff": diff, "weak_side": "R" if R < L else ("L" if L < R else "같음"), "alive_L": cur["alive_L"], "alive_R": cur["alive_R"], "envs": envs}
    warn, stop = [], []
    if lo < K.STOP_MIN_FOLLOW:
        stop.append(f"min(L, R) {lo:.2f} < {K.STOP_MIN_FOLLOW}")
    stop_surv = K.STOP_SURVIVAL_MIN * envs / K.SPIN_ENVS                      # 64 env 가 아니면 비율로 환산
    for side in ("L", "R"):
        if cur["alive_" + side] < stop_surv:
            stop.append(f"spin 생존 {side} {cur['alive_' + side]}/{envs} < {K.STOP_SURVIVAL_MIN}/{K.SPIN_ENVS}")
    if lo < K.WARN_MIN_FOLLOW:
        warn.append(f"min(L, R) {lo:.2f} < {K.WARN_MIN_FOLLOW}")
    if diff >= K.WARN_DIFF:
        warn.append(f"|L - R| {diff:.2f} >= {K.WARN_DIFF}")
    if prev is not None:
        for side in ("L", "R"):
            drop = prev["alive_" + side] / prev["envs"] - cur["alive_" + side] / envs
            if drop > K.WARN_SURVIVAL_DROP + 1e-12:
                warn.append(f"spin 생존 {side} 이전 창보다 {drop:.2f} 하락 > {K.WARN_SURVIVAL_DROP}")

    return {"record": record, "warn": warn, "stop": stop, "level": "멈춤" if stop else ("경고" if warn else "통과")}


def branch(L: float, R: float, D: float | None) -> dict:
    """§2.3 분기표 한 판. D = 약한 방향의 정체 구간 최대 calf 체류(약한 방향이 없으면 None 가능). label 은 A · B · C · D · «표 밖» · «D 미측정»."""
    lo, diff = min(L, R), abs(L - R)
    weak = lo < K.BRANCH_WEAK_MIN or diff >= K.BRANCH_DIFF_MIN
    hit = []
    if L < K.BRANCH_COLLAPSE_MAX and R < K.BRANCH_COLLAPSE_MAX:
        hit.append("D")
    if weak and D is not None and D >= K.BRANCH_D_C_MAX:                       # D >= 0.5 는 B, 0.3 <= D < 0.5 도 B (초안)
        hit.append("B")
    if weak and D is not None and D < K.BRANCH_D_C_MAX:
        hit.append("C")
    if lo >= K.BRANCH_STRONG_MIN and diff <= K.BRANCH_A_DIFF_MAX:
        hit.append("A")
    label = next((b for b in K.BRANCH_PRIORITY if b in hit), None)
    if label is None:
        label = "D 미측정" if (weak and D is None) else "표 밖"                    # 표 밖 = 약한 방향도 A 도 아닌 사이 구간(예: min 0.3~0.5 이고 차가 작음)

    return {"label": label, "hit": hit, "L": L, "R": R, "D": D, "weak": weak, "weak_side": "R" if R < L else ("L" if L < R else "같음")}


def combine(branches: dict) -> dict:
    """두 판(이름 -> branch 결과)을 우선순위 D > B > C > A 로 합친다. A 는 둘 다 A 일 때만. «표 밖» · «D 미측정» 이 있으면 합치지 않고 판정 보류."""
    labels = {k: v["label"] for k, v in branches.items()}
    if any(lb in ("표 밖", "D 미측정") for lb in labels.values()):
        return {"label": "판정 보류", "per": labels, "reason": "표 밖 또는 D 미측정인 판이 있다"}
    for b in K.BRANCH_PRIORITY:
        if b == "A":
            if all(lb == "A" for lb in labels.values()):
                return {"label": "A", "per": labels}
        elif b in labels.values():
            return {"label": b, "per": labels}

    return {"label": "판정 보류", "per": labels, "reason": "A 와 다른 분기가 섞여 위 우선순위에 안 걸린다"}


def weak_direction_dwell(probe_folder, side: str) -> dict:
    """probe 폴더의 약한 방향(side = 'R' 또는 'L') 시행들에서 네 calf 최대 체류의 안 넘어진 env 평균(정체 구간 한정 · 전체 구간)과 시행 수, 넘어진 수."""
    from foothold_s2.eval import calf_band as C

    d = C.load(probe_folder)
    st, wh, kept_n, fallen = [], [], 0, 0
    for p in K.WEAK_PROTOCOLS[side]:
        v = d["by_protocol"].get(p)
        if v is None or "dwell" not in v:
            raise SystemExit(f"{p} 시행 기록(wz 포함)이 없다: {probe_folder}")
        k = v["kept"]
        kept_n += int(k.sum())
        fallen += int((~k).sum())
        st.extend(v["dwell"]["stalled"][k].tolist())
        wh.extend(v["dwell"]["whole"][k].tolist())
    st = np.array(st, dtype=float)
    ok = ~np.isnan(st)

    return {"D_stalled": float(st[ok].mean()) if ok.any() else None, "n_stalled_trials": int(ok.sum()), "D_whole": float(np.mean(wh)) if wh else None, "n_trials": kept_n, "fallen": fallen,
            "trials_total": kept_n + fallen, "protocols": list(K.WEAK_PROTOCOLS[side])}


def inputs_from_files(map_modes_json, probe_folder) -> dict:
    mm = json.loads(Path(map_modes_json).read_text(encoding="utf-8"))
    cur = spin_inputs(mm)
    side = "R" if cur["R"] < cur["L"] else "L"
    dw = weak_direction_dwell(probe_folder, side)

    return {"spin": cur, "weak_side": side, "dwell": dw, "branch": branch(cur["L"], cur["R"], dw["D_stalled"]), "rotation_layer": rotation_layer(cur), "criteria_sha256": K.criteria_sha256(),
            "checkpoint_iter": mm.get("checkpoint_iter"), "checkpoint_sha256": mm.get("checkpoint_sha256", "")[:12], "map_modes_fixed_sha": (mm.get("fixed_terrain") or {}).get("assignment_sha256")}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 4 or (len(argv) - 1) % 3:
        raise SystemExit("usage: window3_branch <출력 json> <이름1> <map_modes.json 1> <probe 폴더 1> [<이름2> <map_modes.json 2> <probe 폴더 2> ...]")
    out_json, rest = argv[0], argv[1:]
    res = {rest[i]: inputs_from_files(rest[i + 1], rest[i + 2]) for i in range(0, len(rest), 3)}
    res_c = combine({k: v["branch"] for k, v in res.items()}) if len(res) > 1 else None
    Path(out_json).write_text(json.dumps({"판": res, "합침": res_c}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("창 3 분기 입력(미검증 집계, reviewer 확인 전). 기준 파일 SHA", K.criteria_sha256()[:12])
    print("| 판 | iter | L(spin+1.2) | R(spin-1.2) | abs(L-R) | 약한 방향 | D(정체 구간 한정) | D(전체 구간) | 약한 방향 시행(남은/전체) | spin 생존 L · R | 분기 | 회전 층 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, v in res.items():
        s, d, b, r = v["spin"], v["dwell"], v["branch"], v["rotation_layer"]
        dd = "미측정" if d["D_stalled"] is None else f"{d['D_stalled']:.2f}"
        dw = "미측정" if d["D_whole"] is None else f"{d['D_whole']:.2f}"
        print(f"| {name} | {v['checkpoint_iter']} | {s['L']:.2f} | {s['R']:.2f} | {abs(s['L'] - s['R']):.2f} | {v['weak_side']} | {dd} (정체 있는 시행 {d['n_stalled_trials']}) | {dw} | {d['n_trials']}/{d['trials_total']} | {s['alive_L']} · {s['alive_R']} /{s['envs']} | {b['label']} {b['hit']} | {r['level']} {r['stop'] or r['warn']} |")
    if res_c:
        print(f"\n합침(우선순위 D > B > C > A): {res_c['label']} {res_c['per']}")


if __name__ == "__main__":
    main()
