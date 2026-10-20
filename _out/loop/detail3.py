# -*- coding: utf-8 -*-
"""종합 보고서 수준의 «상세 표» 를 만든다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 지적 「report-v1 은 스윕별·지형별·속도별 자세히 다뤘는데 지금 두 페이지는
      누락된 내용이 많다」 · `sim/eval/results/report-v1/report-v1.html` 의 표 10 개
요지: 48 칸 «평균» 하나로는 아무것도 못 본다. **칸을 다 편다.**

내는 것
    지형별 x 속도별 성공률   16 지형 x 3 속도 · 기준선 둘과 우리 셋을 나란히
    집합별 요약              rough6 · unseen10 x 3 속도 · 기준선 대비 %p
    실패 성분 분해           생존 · 진행 · 추종 · 방향 중 무엇이 무너졌나
    체크포인트별 흐름        다섯 점에서 48 칸 평균이 어떻게 움직이나

**빈 칸을 0 으로 채우지 않는다.** 없으면 「없음」이라고 적는다.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A1 = os.path.join(LAB, "sim", "eval", "results", "20260923-v2rs")
NV = os.path.join(LAB, "sim", "eval", "results", "20260921-nvidia-axis1")
V1 = os.path.join(LAB, "models", "foothold-v1.json")

SETS = ("rough6", "unseen10")
SPEEDS = (("v0.5", "0.5 m/s"), ("v1.0", "1.0 m/s"), ("v1.5", "1.5 m/s"))
CKPTS = (1500, 2000, 2500, 3000, 3750, 4000, 4500)

# 팀장이 정한 비교 대상 셋
OURS = (
    ("v2g2-feetair01", "v2g2", 3000),
    ("fs1-scratch-f001", "fs1", 4500),
    ("fs2-scratch-f01", "fs2", 4500),
)

# 학습에 «들어 있는» 지형. 미경험 주장에서 빠진다.
TRAINED = {"pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
           "hf_pyramid_slope", "hf_pyramid_slope_inv", "rails"}


def read_cells(root, model_dir=None):
    """{(set, speed, terrain): row} 로 읽는다. 없으면 빈 dict."""
    out = {}
    base = os.path.join(root, model_dir) if model_dir else root
    for s in SETS:
        for v, _ in SPEEDS:
            f = os.path.join(base, s, "d0.5", v, "generalization_summary.csv")
            if not os.path.isfile(f):
                continue
            with io.open(f, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    out[(s, v, r["terrain"])] = r
    return out


def pct(row, key="overall_success_rate"):
    try:
        return 100.0 * float(row[key])
    except (TypeError, ValueError, KeyError):
        return None


def v1_cells():
    """모델 카드의 칸 값. 이미 백분율이다."""
    if not os.path.isfile(V1):
        return {}
    d = json.load(io.open(V1, encoding="utf-8"))
    sc = d.get("scores_difficulty_0_5") or {}
    out = {}
    for spd_label, sets in sc.items():
        v = {"0.5 m/s": "v0.5", "1.0 m/s": "v1.0", "1.5 m/s": "v1.5"}.get(spd_label)
        if not v:
            continue
        for s, terr in (sets or {}).items():
            for t, val in (terr or {}).items():
                out[(s, v, t)] = float(val)
    return out


def fmt(x, bold=False):
    if x is None:
        return "없음"
    s = "%.0f" % x if abs(x - round(x)) < 0.05 else "%.1f" % x
    return "**%s**" % s if bold else s


def table_by_terrain(data, nv, v1):
    """지형별 x 속도별. 16 지형 x 3 속도 = 48 행."""
    L = ["| 지형 | 속도 | NVIDIA | foothold-v1 | v2g2 | fs1 | fs2 |",
         "|---|---|---|---|---|---|---|"]
    for s in SETS:
        terrains = sorted({k[2] for k in nv if k[0] == s} |
                          {k[2] for k in v1 if k[0] == s})
        for t in terrains:
            mark = " *" if t in TRAINED else ""
            for v, vlab in SPEEDS:
                cells = []
                r = nv.get((s, v, t))
                cells.append(fmt(pct(r) if r else None))
                cells.append(fmt(v1.get((s, v, t))))
                for label, short, ck in OURS:
                    rr = data.get(short, {}).get((s, v, t))
                    cells.append(fmt(pct(rr) if rr else None))
                L.append("| %s%s | %s | %s |" % (t, mark, vlab, " | ".join(cells)))
    L.append("")
    L.append("`*` 는 **학습 지형**이다. 미경험 주장에서 빠진다.")
    return "\n".join(L)


def table_by_set(data, nv, v1):
    """집합별 x 속도별 평균과 기준선 대비 %p."""
    L = ["| 지형 집합 | 속도 | NVIDIA | foothold-v1 | v2g2 | fs1 | fs2 | fs1 - v1 | fs2 - v1 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in SETS:
        for v, vlab in SPEEDS:
            def avg(get):
                vals = [x for x in (get(t) for t in
                        sorted({k[2] for k in nv if k[0] == s} |
                               {k[2] for k in v1 if k[0] == s})) if x is not None]
                return sum(vals) / len(vals) if vals else None
            a_nv = avg(lambda t: pct(nv[(s, v, t)]) if (s, v, t) in nv else None)
            a_v1 = avg(lambda t: v1.get((s, v, t)))
            outs = []
            for label, short, ck in OURS:
                outs.append(avg(lambda t, sh=short:
                                pct(data.get(sh, {})[(s, v, t)])
                                if (s, v, t) in data.get(sh, {}) else None))
            d1 = (outs[1] - a_v1) if (outs[1] is not None and a_v1 is not None) else None
            d2 = (outs[2] - a_v1) if (outs[2] is not None and a_v1 is not None) else None
            def dfmt(x):
                if x is None:
                    return "없음"
                return "**%+.1f**" % x if abs(x) >= 1.0 else "%+.1f" % x
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                s, vlab, fmt(a_nv), fmt(a_v1),
                fmt(outs[0]), fmt(outs[1], True), fmt(outs[2], True),
                dfmt(d1), dfmt(d2)))
    L.append("")
    L.append("마지막 두 열은 **foothold-v1 대비 %p** 다. 양수면 올랐다.")
    return "\n".join(L)


def table_components(data):
    """성공률이 100 이 아닌 칸에서 «무엇이» 무너졌나."""
    L = ["| 판 | 지형 | 속도 | 종합 | 생존 | 진행 | 추종 | 방향 |",
         "|---|---|---|---|---|---|---|---|"]
    n = 0
    for label, short, ck in OURS:
        cells = data.get(short, {})
        for (s, v, t), r in sorted(cells.items()):
            o = pct(r)
            if o is None or o >= 99.5:
                continue
            vlab = dict(SPEEDS)[v]
            L.append("| `%s` | %s | %s | **%s** | %s | %s | %s | %s |" % (
                label, t, vlab, fmt(o),
                fmt(pct(r, "survival_rate")),
                fmt(pct(r, "progress_success_rate")),
                fmt(pct(r, "tracking_success_rate")),
                fmt(pct(r, "direction_success_rate"))))
            n += 1
    if n == 0:
        return "_아직 자료가 없습니다._"
    L.append("")
    L.append("종합은 네 성분의 **AND** 다. 어느 하나가 낮으면 종합이 낮다. "
             "「못 건넌다」와 「느리다」가 같은 숫자로 내려오지 않게 성분을 편다.")
    return "\n".join(L)


def table_ckpt_flow():
    """체크포인트 다섯 점에서 48 칸 평균이 어떻게 움직이나."""
    L = ["| 판 | " + " | ".join("iter%d" % c for c in CKPTS) + " |",
         "|---|" + "---|" * len(CKPTS)]
    any_row = False
    for label, short, ck in OURS:
        row = []
        for c in CKPTS:
            cells = read_cells(A1, "%s-iter%d" % (label, c))
            vals = [pct(r) for r in cells.values()]
            vals = [x for x in vals if x is not None]
            row.append("**%.2f**" % (sum(vals) / len(vals)) if len(vals) == 48
                       else ("미완 (%d/48)" % len(vals)))
        if any("미완 (0/48)" != x for x in row):
            any_row = True
        L.append("| `%s` | %s |" % (label, " | ".join(row)))
    return "\n".join(L) if any_row else "_아직 자료가 없습니다._"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    nv = read_cells(NV)
    v1 = v1_cells()
    data = {}
    for label, short, ck in OURS:
        data[short] = read_cells(A1, "%s-iter%d" % (label, ck))

    parts = {
        "terrain": table_by_terrain(data, nv, v1),
        "set": table_by_set(data, nv, v1),
        "components": table_components(data),
        "ckptflow": table_ckpt_flow(),
    }
    for name, body in parts.items():
        p = os.path.join(a.out, "detail-%s.md" % name)
        io.open(p, "w", encoding="utf-8").write(body + "\n")
        print("  detail-%-11s %d 줄" % (name + ".md", len(body.split("\n"))))

    print("  기준선 · NVIDIA %d 칸 · foothold-v1 %d 칸" % (len(nv), len(v1)))
    for label, short, ck in OURS:
        print("  우리 · %-20s iter%-5d %d 칸" % (label, ck, len(data[short])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
