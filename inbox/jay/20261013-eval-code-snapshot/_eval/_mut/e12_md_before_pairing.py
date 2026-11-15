# E1 (seed 42) vs E2 (seed 43) per cell under the same evaluation conditions (same eval seed, layout, DR, mesh).
# Flags a cell when the pass-rate difference exceeds 10 pp or the MAE sum (vx + vy + wz, survived episodes) differs
# by more than 20 % (ASTRA criterion for seed variation). Usage: python e12_md.py > out/E12-tables.md
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import q_metrics as Q  # noqa: E402

OUT = os.path.join(HERE, "out")
FAMS = ["flat", "wave", "slope_up", "slope_down", "rough_slope", "stairs_up", "stairs_down", "obstacles"]
ROUGH = FAMS[1:]
CELLS = ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
OFFC = ["stand", "stop03", "yawL05", "yawR05"]
_c = {}


def eps(tag):
    if tag not in _c:
        p = os.path.join(OUT, tag, "episodes.csv")
        _c[tag] = list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else None
    return _c[tag]


def meta(tag):
    p = os.path.join(OUT, tag, "meta.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


tf = lambda v: str(v) in ("True", "true", "1")  # noqa: E731


def rule(cell, span=False):
    return ("span_" if span else "") + ("q2_pass" if cell == "stop03" else "q1_pass")


def maesum(rows):
    v = [float(r["mae_vx"]) + float(r["mae_vy"]) + float(r["mae_wz"]) for r in rows if tf(r["survived"]) and r["mae_vx"] not in ("", "nan")]
    return float(np.mean(v)) if v else float("nan")


def p0(x):
    return "-" if x is None or not np.isfinite(x) else f"{100 * x:.0f}"


# condition groups: (name, list of (unit label, E1 tag, E2 tag, family, cells))
def qmain(it, nn):
    mid = "noise_" if nn == "on" else ""
    u = [(f, f"m{it}_{mid}{f}", f"e2_m{it}_{mid}{f}", f, CELLS) for f in FAMS]
    u += [(f"{f}·띠", f"m{it}_{mid}offplat", f"e2_m{it}_{mid}offplat", f, OFFC) for f in ROUGH]
    return u


def d1(it, perm):
    t = "tp" if perm else "t"
    u = [(f, f"{t}{it}_{f}", f"e2_{t}{it}_{f}", f, CELLS) for f in FAMS]
    u += [(f"{f}·띠", f"{t}{it}_offplat", f"e2_{t}{it}_offplat", f, OFFC) for f in ROUGH]
    return u


def qd(dd, nn, it):
    A, B = FAMS[:4], FAMS[4:]
    u = [(f, f"qd{dd}_{nn}_m{it}_{'A' if f in A else 'B'}", f"e2_qd{dd}_{nn}_m{it}_{'A' if f in A else 'B'}", f, CELLS) for f in FAMS]
    u += [(f"{f}·띠", f"qd{dd}_{nn}_m{it}_band", f"e2_qd{dd}_{nn}_m{it}_band", f, OFFC) for f in ROUGH]
    return u


GROUPS = []
for it in ("20000", "20499"):
    GROUPS.append((f"Q 주 실행 · noise 끔 · {it}", qmain(it, "off")))
    GROUPS.append((f"Q 주 실행 · noise 켬 · {it}", qmain(it, "on")))
for it in ("5000", "10000", "15000", "19500"):
    GROUPS.append((f"능력 곡선 · noise 켬 · {it}", qmain(it, "on")))
GROUPS.append(("능력 곡선 · noise 끔 · 19500", qmain("19500", "off")))
for it in ("20000", "20499"):
    GROUPS.append((f"D1-A teacher 정상 · {it}", d1(it, False)))
    GROUPS.append((f"D1-A teacher permutation · {it}", d1(it, True)))
for nn in ("off", "on"):
    for dd in ("02", "05", "08"):
        for it in ("20000", "20499"):
            GROUPS.append((f"난이도 0.{dd[1]} · noise {'켬' if nn == 'on' else '끔'} · {it}", qd(dd, nn, it)))

rows_csv, summary = [], []
print("### 표 E · E1 대 E2 · 조건별 요약 (같은 평가 시드 · 배치 · DR · 메시)\n")
print("ASTRA 기준: 두 시드의 통과율 차 > 10 pp 또는 MAE 합 (vx + vy + wz, 생존 episode) 차 > 20 % 인 cell 을 표시한다. 통과율은 현행 정의 (괄호는 span 정의 기준 표시 수).\n")
print("| 조건 | cell 수 | E1 통과 평균 % | E2 통과 평균 % | 10 pp 초과 cell (span) | MAE 20 % 초과 cell (그중 차 < 0.02) | 짝 McNemar Holm 뒤 유의 (E2 낮음 · 높음) |")
print("|---|---|---|---|---|---|---|")
for gname, units in GROUPS:
    if any(eps(t1) is None or eps(t2) is None for _, t1, t2, _, _ in units):
        summary.append({"group": gname, "status": "missing"})
        print(f"| {gname} | - | - | - | 실행 없음 | - | - |")
        continue
    flags_pp, flags_pp_span, flags_mae, flags_mae_small, pv, recs, r1s, r2s = 0, 0, 0, 0, [], [], [], []
    for lab, t1, t2, fam, cl in units:
        for cell in cl:
            g1 = {int(r["episode"]): r for r in eps(t1) if r["family"] == fam and r["cell"] == cell}
            g2 = {int(r["episode"]): r for r in eps(t2) if r["family"] == fam and r["cell"] == cell}
            k = rule(cell)
            a = sum(tf(r[k]) for r in g1.values()) / len(g1)
            b = sum(tf(r[k]) for r in g2.values()) / len(g2)
            ks = rule(cell, True)
            as_ = sum(tf(r[ks]) for r in g1.values()) / len(g1)
            bs_ = sum(tf(r[ks]) for r in g2.values()) / len(g2)
            m1, m2 = maesum(g1.values()), maesum(g2.values())
            rel = (m2 - m1) / m1 if np.isfinite(m1) and m1 > 0 else float("nan")
            bb = sum(tf(g1[e][k]) and not tf(g2[e][k]) for e in g1 if e in g2)
            cc = sum((not tf(g1[e][k])) and tf(g2[e][k]) for e in g1 if e in g2)
            p = Q.mcnemar_exact(bb, cc)
            fpp, fmae = abs(b - a) > 0.10, np.isfinite(rel) and abs(rel) > 0.20
            flags_pp += fpp
            flags_pp_span += abs(bs_ - as_) > 0.10
            flags_mae += fmae
            flags_mae_small += fmae and abs(m2 - m1) < 0.02
            pv.append((p, bb, cc, f"{lab}/{cell}"))
            r1s.append(a)
            r2s.append(b)
            rec = dict(group=gname, unit=lab, cell=cell, e1_pass=a, e2_pass=b, diff_pp=100 * (b - a), e1_pass_span=as_, e2_pass_span=bs_,
                       e1_mae_sum=m1, e2_mae_sum=m2, mae_rel=rel, flag_pp=fpp, flag_mae=bool(fmae), mcnemar_p=p, b_e1_only=bb, c_e2_only=cc)
            rows_csv.append(rec)
            recs.append(rec)
    rej = Q.holm_reject([x[0] for x in pv])
    hd = [x[3] for x, r in zip(pv, rej) if r and x[1] > x[2]]
    hu = [x[3] for x, r in zip(pv, rej) if r and x[2] > x[1]]
    summary.append({"group": gname, "cells": len(recs), "flags_pp": flags_pp, "flags_pp_span": flags_pp_span, "flags_mae": flags_mae,
                    "flags_mae_abs_lt_0.02": flags_mae_small, "holm_e2_lower": hd, "holm_e2_higher": hu,
                    "e1_mean": float(np.mean(r1s)), "e2_mean": float(np.mean(r2s))})
    print(f"| {gname} | {len(recs)} | {p0(np.mean(r1s))} | {p0(np.mean(r2s))} | {flags_pp} ({flags_pp_span}) | {flags_mae} ({flags_mae_small}) | {len(hd)} · {len(hu)} |")
print()
print("### 표 E-2 · 10 pp 를 넘는 cell (현행 정의, E1 → E2 %)\n")
print("| 조건 | cell | E1 | E2 | 차 pp | MAE 합 E1 → E2 |")
print("|---|---|---|---|---|---|")
for r in rows_csv:
    if r["flag_pp"]:
        print(f"| {r['group']} | {r['unit']}/{r['cell']} | {p0(r['e1_pass'])} | {p0(r['e2_pass'])} | {r['diff_pp']:+.0f} | {r['e1_mae_sum']:.3f} → {r['e2_mae_sum']:.3f} |")
print()
if rows_csv:
    with open(os.path.join(OUT, "E12-cells.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys()))
        w.writeheader()
        for r in rows_csv:
            w.writerow(r)
json.dump(summary, open(os.path.join(OUT, "E12-summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
