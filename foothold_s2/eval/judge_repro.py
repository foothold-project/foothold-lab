"""J-T6: 같은 저장본 재측정 폭을 새 식(env 동일 가중 kept 평균 Q · C)으로 다시 계산한다 (JUDGE-SPEC v0.2 3 절 첫 줄 · 6.6).

- 회전 24 쌍: 옛 `six_repro.py` 와 같은 쌍(B1500 · b50 m1510 · b50 m1550 · a50 m1550 의 이전 실행 대 이번 실행, 다섯 경우 + 단독 fwd_then_left). 옛 pooled 식 결과를 나란히 낸다.
- 회전 6 쌍: B1500 rep1 대 rep2 (eval_gt, 여섯 경우). 명세 6.6: |dQ| 최대 0.0833(좌 -> 우).
- 64 env 반복 폭: 같은 저장본 쌍이 있는 것만(B1500 parent 대 b_m1500_repeat, rep1 대 rep2 의 세 모드). 전진(m) · 회전 추종비 · 생존 수.
최댓값은 신뢰구간이 아니고 다른 문턱의 하한도 아니다. 좋은 재실행만 고르지 않는다(쌍은 정해진 목록 전부).

사용: python -m foothold_s2.eval.judge_repro [출력.json]
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from foothold_s2.eval import judge_stats as S

LOGS = Path(os.environ.get("JUDGE_LOGS_ROOT", "C:/mai/wt/foothold-lab/impl-turncases/logs"))
T5 = Path(os.environ.get("JUDGE_T5_ROOT", "C:/mai/wt/foothold-lab/impl-t5/logs/onset_sweep"))
T5_LOGS = Path(os.environ.get("JUDGE_T5_LOGS", "C:/mai/wt/foothold-lab/impl-t5/logs"))
W2_PARENT = Path(os.environ.get("JUDGE_W2_PARENT", "C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval/parent_b1500/map_modes.json"))
NEW = LOGS / "six_cases"
SOLO = LOGS / "fwd_then_left"
OLD = {"b1500": T5_LOGS / "w3p1_b1500_20261025_063715", "b50_m1510": T5 / "probe_b50_m1510", "b50_m1550": T5 / "probe_b50_m1550", "a50_m1550": T5 / "probe_a50_m1550"}
CASES_24 = ("indep_left", "indep_right", "left_then_right", "right_then_left", "fwd_then_right")           # 이전 실행에 있던 다섯 경우(fwd_then_left 는 단독 실행 쌍)


def old_pooled(npz, case):
    """옛 생성기(six_table.one)의 식: 살아 있는 표본을 전부 합친 평균 wz(부호 없음) · 네 발 동시 접촉 비율."""
    with np.load(npz) as z:
        a = z["alive"]
        c = (z["force"][..., list(S.FEET)] > S.CONTACT_N).all(-1)

        return float(z["wz"][a].mean()), float(c[a].mean())


def pairs_24() -> list:
    """24 쌍: [{tag, case, old: {Q, C, pooled_yaw, pooled_four}, new: {...}}]. 새 식은 부호 정렬 kept 평균."""
    rows = []

    for tag, old_dir in OLD.items():
        items = [(Path(old_dir) / ("arrays_%s.npz" % c), NEW / tag / ("arrays_%s.npz" % c), c, c) for c in CASES_24]
        items.append((SOLO / tag / "arrays_fwd_then_left.npz", NEW / tag / "arrays_fwd_then_left.npz", "fwd_then_left", "fwd_then_left(solo)"))

        for a, b, case, label in items:
            sa, sb = S.turn_stats(a, case), S.turn_stats(b, case)
            ya, ca = old_pooled(a, case)
            yb, cb = old_pooled(b, case)
            rows.append({"tag": tag, "case": label, "old_run": str(a), "new_run": str(b),
                         "Q": (sa["Q"], sb["Q"]), "C": (sa["C"], sb["C"]), "kept": (sa["kept"], sb["kept"]),
                         "pooled_yaw": (ya, yb), "pooled_four": (ca, cb)})

    return rows


def pairs_rep() -> list:
    """B1500 rep1 대 rep2 (eval_gt) 여섯 경우."""
    r1 = S.read_turn_dir(LOGS / "b1500_baseline/rep1/turn16_eval_gt")
    r2 = S.read_turn_dir(LOGS / "b1500_baseline/rep2/turn16_eval_gt")

    return [{"case": c, "Q": (r1[c]["Q"], r2[c]["Q"]), "C": (r1[c]["C"], r2[c]["C"]), "kept": (r1[c]["kept"], r2[c]["kept"])} for c in S.SIX_CASES if c in r1 and c in r2]


def map64_pairs() -> list:
    """64 env 같은 저장본 쌍(B1500). 전진 적분(m) · spin 추종비 · 생존."""
    rep1, rep2 = LOGS / "b1500_baseline/rep1/map64/map_modes.json", LOGS / "b1500_baseline/rep2/map64/map_modes.json"
    pairs = [("parent_vs_repeat", W2_PARENT, T5 / "b_m1500_repeat/map_modes.json", ("eval_gt", "eval_pred")),
             ("rep1_vs_rep2", rep1, rep2, ("eval_gt", "probe_prop_only", "eval_pred"))]
    out = []

    for name, pa, pb, modes in pairs:
        a, b = S.read_map64(pa)["modes"], S.read_map64(pb)["modes"]

        for mode in modes:
            for cmd in S.MAP64_CMDS:
                va, vb = a[mode][cmd], b[mode][cmd]
                out.append({"pair": name, "mode": mode, "cmd": cmd, "fwd_m": (va["fwd_m"], vb["fwd_m"]), "yaw_follow": (va["yaw_follow"], vb["yaw_follow"]), "alive": (va["alive"], vb["alive"])})

    return out


def _absmax(rows, key):
    d = [abs(r[key][0] - r[key][1]) for r in rows]

    return {"n": len(d), "max": max(d), "mean": sum(d) / len(d), "min": min(d)}


def summarize() -> dict:
    p24, rep, m64 = pairs_24(), pairs_rep(), map64_pairs()
    fwd = [r for r in m64 if r["cmd"].startswith("fwd")]
    spin = [r for r in m64 if r["cmd"].startswith("spin")]
    new24 = {"dQ": _absmax(p24, "Q"), "dC": _absmax(p24, "C")}
    old24 = {"dYaw": _absmax(p24, "pooled_yaw"), "dFour": _absmax(p24, "pooled_four")}

    return {"spec": S.SPEC_VERSION, "pairs24": {"new_formula": new24, "old_pooled": old24, "rows": p24},
            "rep_pairs6": {"dQ": _absmax(rep, "Q"), "dC": _absmax(rep, "C"), "rows": rep},
            "map64": {"fwd_m": _absmax(fwd, "fwd_m"), "spin_yaw_follow": _absmax(spin, "yaw_follow"), "alive": _absmax(m64, "alive"), "rows": m64}}


def to_markdown(s: dict) -> str:
    n, o, r, m = s["pairs24"]["new_formula"], s["pairs24"]["old_pooled"], s["rep_pairs6"], s["map64"]
    lines = ["# 같은 저장본 재측정 폭 (새 식, %s)" % s["spec"], "",
             "| 무엇 | 쌍 수 | 최대 | 평균 | 최소 |", "|---|---:|---:|---:|---:|",
             "| 회전 24 쌍 |dQ| (새 식: kept 평균, 부호 정렬) | %d | %.4f | %.4f | %.4f |" % (n["dQ"]["n"], n["dQ"]["max"], n["dQ"]["mean"], n["dQ"]["min"]),
             "| 회전 24 쌍 |dC| (새 식) | %d | %.4f | %.4f | %.4f |" % (n["dC"]["n"], n["dC"]["max"], n["dC"]["mean"], n["dC"]["min"]),
             "| 옛 pooled 24 쌍 |d요| | %d | %.4f | %.4f | %.4f |" % (o["dYaw"]["n"], o["dYaw"]["max"], o["dYaw"]["mean"], o["dYaw"]["min"]),
             "| 옛 pooled 24 쌍 |d네 발| | %d | %.4f | %.4f | %.4f |" % (o["dFour"]["n"], o["dFour"]["max"], o["dFour"]["mean"], o["dFour"]["min"]),
             "| B1500 rep1 대 rep2 |dQ| | %d | %.4f | %.4f | %.4f |" % (r["dQ"]["n"], r["dQ"]["max"], r["dQ"]["mean"], r["dQ"]["min"]),
             "| B1500 rep1 대 rep2 |dC| | %d | %.4f | %.4f | %.4f |" % (r["dC"]["n"], r["dC"]["max"], r["dC"]["mean"], r["dC"]["min"]),
             "| 64 env 전진 |d적분| (m) | %d | %.4f | %.4f | %.4f |" % (m["fwd_m"]["n"], m["fwd_m"]["max"], m["fwd_m"]["mean"], m["fwd_m"]["min"]),
             "| 64 env spin |d추종비| | %d | %.4f | %.4f | %.4f |" % (m["spin_yaw_follow"]["n"], m["spin_yaw_follow"]["max"], m["spin_yaw_follow"]["mean"], m["spin_yaw_follow"]["min"]),
             "| 64 env |d생존| (env 수) | %d | %.1f | %.2f | %.1f |" % (m["alive"]["n"], m["alive"]["max"], m["alive"]["mean"], m["alive"]["min"]), "",
             "최댓값은 신뢰구간이 아니고 다른 문턱의 하한도 아니다. 회전(rad/s) 과 전진(m) 은 단위가 다르다."]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    res = summarize()
    print(to_markdown(res))

    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8", newline="\n")
