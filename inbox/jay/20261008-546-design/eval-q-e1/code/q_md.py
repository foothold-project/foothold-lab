# Generate the markdown tables for Q-E1.md from the raw outputs (no hand-copied numbers).
# Usage: python q_md.py > out/Q-E1-tables.md

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
ITS = ["20000", "20499"]
CELL_ORDER = ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
CMD = {"stand": "0, 0, 0", "stop03": "0.3 5초 → 0 5초", "fwd01": "0.1, 0, 0", "fwd02": "0.2, 0, 0", "fwd03": "0.3, 0, 0",
       "fwd05": "0.5, 0, 0", "back03": "-0.3, 0, 0", "left03": "0, 0.3, 0", "right03": "0, -0.3, 0",
       "yawL05": "0, 0, 0.5", "yawR05": "0, 0, -0.5"}
SRC = {"stand": "임시", "stop03": "Q", "fwd01": "임시", "fwd02": "임시", "fwd03": "Q", "fwd05": "임시", "back03": "Q",
       "left03": "Q", "right03": "Q", "yawL05": "Q", "yawR05": "Q"}


def tf(v):
    return str(v) in ("True", "true", "1")


def fl(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def eps(tag):
    p = os.path.join(OUT, tag, "episodes.csv")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cells(tag):
    p = os.path.join(OUT, tag, "cells.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return {(s["family"], s["cell"]): s for s in json.load(f)}


def paired(ea, eb, fam, cell, key):
    A = {int(r["episode"]): tf(r[key]) for r in ea if r["family"] == fam and r["cell"] == cell}
    B = {int(r["episode"]): tf(r[key]) for r in eb if r["family"] == fam and r["cell"] == cell}
    a = sum(A[k] and B[k] for k in A)
    b = sum(A[k] and not B[k] for k in A)
    c = sum((not A[k]) and B[k] for k in A)
    d = sum((not A[k]) and (not B[k]) for k in A)
    diff, lo, hi = Q.newcombe_paired(a, b, c, d)
    return b, c, diff, lo, hi, Q.mcnemar_exact(b, c)


def p0(x):
    return "-" if not np.isfinite(x) else f"{100 * x:.0f}"


def p1(x):
    return "-" if not np.isfinite(x) else f"{100 * x:.1f}"


def f2(x):
    return "-" if not np.isfinite(x) else f"{x:.2f}"


def f3(x):
    return "-" if not np.isfinite(x) else f"{x:.3f}"


def mark(s):
    return "" if s["cell_pass"] else "*"


def pv(p):
    return f"{p:.2g}" if p < 0.1 else f"{p:.2f}"


# ---- table 1: flat, both checkpoints -------------------------------------------
ca, cb = cells("m20000_flat"), cells("m20499_flat")
ea, eb = eps("m20000_flat"), eps("m20499_flat")
print("### 표 1 · 평지 · 두 체크포인트 (각 cell 100 episodes · 값은 20000 / 20499)\n")
print("| cell | 명령 vx, vy, wz | 출처 | 생존 % | Q 통과 % | MAE vx | MAE vy | MAE wz | 이동 보조 통과 % | 짝 차 [95% 구간] · McNemar p |")
print("|---|---|---|---|---|---|---|---|---|---|")
for cell in CELL_ORDER:
    sa, sb = ca[("flat", cell)], cb[("flat", cell)]
    key = sa["rule"]
    b, c, diff, lo, hi, p = paired(ea, eb, "flat", cell, key)
    print(f"| {cell} | {CMD[cell]} | {SRC[cell]} | {p0(sa['survival'])} / {p0(sb['survival'])} | "
          f"{p0(sa['pass_rate'])}{mark(sa)} / {p0(sb['pass_rate'])}{mark(sb)} | "
          f"{f3(sa['mae_vx_mean'])} / {f3(sb['mae_vx_mean'])} | {f3(sa['mae_vy_mean'])} / {f3(sb['mae_vy_mean'])} | "
          f"{f3(sa['mae_wz_mean'])} / {f3(sb['mae_wz_mean'])} | {p0(sa['q1m_pass_rate'])} / {p0(sb['q1m_pass_rate'])} | "
          f"{diff:+.2f} [{lo:+.2f}, {hi:+.2f}] · {pv(p)} |")
print()

# ---- table 2: rough families, pass rate grid -------------------------------------
print("### 표 2 · 험지 7종 · Q 통과 % (출발은 각 지형 tile 중앙 · 값은 20000 / 20499 · `*` 는 cell 판정 미달)\n")
print("| cell | " + " | ".join(ROUGH) + " | 7종 합계 (700) |")
print("|---|" + "---|" * (len(ROUGH) + 1))
for cell in CELL_ORDER:
    row = [cell]
    na = nb = pa = pb = 0
    for fam in ROUGH:
        sa, sb = cells(f"m20000_{fam}")[(fam, cell)], cells(f"m20499_{fam}")[(fam, cell)]
        row.append(f"{p0(sa['pass_rate'])}{mark(sa)} / {p0(sb['pass_rate'])}{mark(sb)}")
        na += sa["n"]
        nb += sb["n"]
        pa += sa["pass"]
        pb += sb["pass"]
    row.append(f"{p0(pa / na)} / {p0(pb / nb)}")
    print("| " + " | ".join(row) + " |")
    if cell == "fwd01":  # Q rule cannot see "not moving" at 0.1 m/s; show the auxiliary move check
        row = ["fwd01 이동 보조"]
        qa = qb = 0
        for fam in ROUGH:
            sa, sb = cells(f"m20000_{fam}")[(fam, cell)], cells(f"m20499_{fam}")[(fam, cell)]
            row.append(f"{p0(sa['q1m_pass_rate'])} / {p0(sb['q1m_pass_rate'])}")
            qa += sa["q1m_pass"]
            qb += sb["q1m_pass"]
        row.append(f"{p0(qa / 700)} / {p0(qb / 700)}")
        print("| " + " | ".join(row) + " |")
print()

# ---- table 3: significant paired differences ----------------------------------------
print("### 표 3 · 두 체크포인트 사이에 McNemar p < 0.05 인 cell (100 episodes 선별 단계)\n")
print("| 지형 | cell | Q 통과 % 20000 → 20499 | 20000 만 통과 | 20499 만 통과 | 차 [95% 구간] | p |")
print("|---|---|---|---|---|---|---|")
for fam in FAMS:
    ca_, cb_ = cells(f"m20000_{fam}"), cells(f"m20499_{fam}")
    ea_, eb_ = eps(f"m20000_{fam}"), eps(f"m20499_{fam}")
    for cell in CELL_ORDER:
        sa, sb = ca_[(fam, cell)], cb_[(fam, cell)]
        b, c, diff, lo, hi, p = paired(ea_, eb_, fam, cell, sa["rule"])
        if p < 0.05:
            print(f"| {fam} · 중앙 | {cell} | {p0(sa['pass_rate'])} → {p0(sb['pass_rate'])} | {b} | {c} | "
                  f"{diff:+.2f} [{lo:+.2f}, {hi:+.2f}] | {pv(p)} |")
_oa, _ob, _coa, _cob = eps("m20000_offplat"), eps("m20499_offplat"), cells("m20000_offplat"), cells("m20499_offplat")
if _oa and _ob:
    for fam in ROUGH:
        for cell in ("stand", "stop03", "yawL05", "yawR05"):
            sa, sb = _coa[(fam, cell)], _cob[(fam, cell)]
            b, c, diff, lo, hi, p = paired(_oa, _ob, fam, cell, sa["rule"])
            if p < 0.05:
                print(f"| {fam} · 띠 출발 | {cell} | {p0(sa['pass_rate'])} → {p0(sb['pass_rate'])} | {b} | {c} | "
                      f"{diff:+.2f} [{lo:+.2f}, {hi:+.2f}] | {pv(p)} |")
print()

# ---- table 4: stop ----------------------------------------------------------------
print("### 표 4 · 정지 (stop03 · vx 0.3 5초 뒤 0 · 값은 20000 / 20499)\n")
print("| 지형 · 출발 | Q2 통과 % | 1초 넘게 걸림 | 창 안에 못 멈춤 | 정지 시각 중앙값 s | 정지 시각 p90 s | 정지 거리 중앙값 m | yaw drift 평균 rad |")
print("|---|---|---|---|---|---|---|---|")


def stop_row(label, ra, rb, sa, sb):
    def parts(rr):
        t = np.array([fl(r["stop_t"]) for r in rr])
        d = np.array([fl(r["stop_dist_m"]) for r in rr])
        y = np.array([fl(r["yaw_drift_rad"]) for r in rr])
        late = int(np.sum(np.isfinite(t) & (t > 1.0)))
        none = int(np.sum(~np.isfinite(t)))
        tf_ = t[np.isfinite(t)]
        return late, none, (np.median(tf_) if tf_.size else np.nan), (np.percentile(tf_, 90) if tf_.size else np.nan), \
            np.nanmedian(d), np.nanmean(y)
    A, B = parts(ra), parts(rb)
    print(f"| {label} | {p0(sa['pass_rate'])}{mark(sa)} / {p0(sb['pass_rate'])}{mark(sb)} | {A[0]} / {B[0]} | {A[1]} / {B[1]} | "
          f"{f2(A[2])} / {f2(B[2])} | {f2(A[3])} / {f2(B[3])} | {f3(A[4])} / {f3(B[4])} | {f3(A[5])} / {f3(B[5])} |")


for fam in FAMS:
    ra = [r for r in eps(f"m20000_{fam}") if r["cell"] == "stop03"]
    rb = [r for r in eps(f"m20499_{fam}") if r["cell"] == "stop03"]
    stop_row(f"{fam} · 중앙", ra, rb, cells(f"m20000_{fam}")[(fam, "stop03")], cells(f"m20499_{fam}")[(fam, "stop03")])
oa, ob = eps("m20000_offplat"), eps("m20499_offplat")
coa, cob = cells("m20000_offplat"), cells("m20499_offplat")
if oa and ob:
    for fam in ROUGH:
        ra = [r for r in oa if r["family"] == fam and r["cell"] == "stop03"]
        rb = [r for r in ob if r["family"] == fam and r["cell"] == "stop03"]
        stop_row(f"{fam} · 띠 출발", ra, rb, coa[(fam, "stop03")], cob[(fam, "stop03")])
print()

# ---- table 5: off-platform in-place cells --------------------------------------------
if oa and ob:
    print("### 표 5 · 제자리 cell 을 경사·계단 띠 위에서 (출발 +2.5 m · 값은 20000 / 20499)\n")
    print("| 지형 | stand Q 통과 % | yawL05 Q 통과 % | yawR05 Q 통과 % | yawL05 MAE wz | yawR05 MAE wz | stand 변위 m |")
    print("|---|---|---|---|---|---|---|")
    for fam in ROUGH:
        g = lambda c, s: s[(fam, c)]  # noqa: E731
        print(f"| {fam} | {p0(g('stand', coa)['pass_rate'])}{mark(g('stand', coa))} / {p0(g('stand', cob)['pass_rate'])}{mark(g('stand', cob))} | "
              f"{p0(g('yawL05', coa)['pass_rate'])}{mark(g('yawL05', coa))} / {p0(g('yawL05', cob)['pass_rate'])}{mark(g('yawL05', cob))} | "
              f"{p0(g('yawR05', coa)['pass_rate'])}{mark(g('yawR05', coa))} / {p0(g('yawR05', cob)['pass_rate'])}{mark(g('yawR05', cob))} | "
              f"{f3(g('yawL05', coa)['mae_wz_mean'])} / {f3(g('yawL05', cob)['mae_wz_mean'])} | "
              f"{f3(g('yawR05', coa)['mae_wz_mean'])} / {f3(g('yawR05', cob)['mae_wz_mean'])} | "
              f"{f3(g('stand', coa)['disp_m_mean'])} / {f3(g('stand', cob)['disp_m_mean'])} |")
    print()

# ---- table 6: Q3 gate/corridor, open loop vs heading hold -------------------------------
print("### 표 6 · 4 m gate · corridor (Q3) · 명령 그대로 대 heading hold 변형 (값은 20000 / 20499)\n")
print("| 지형 묶음 | cell | 그대로: gate 도달 | 그대로: corridor ≤0.30 | 그대로: Q3 통과 | hold: gate 도달 | hold: corridor ≤0.30 | hold: Q3 통과 | hold: Q1 통과 |")
print("|---|---|---|---|---|---|---|---|---|")


def gather(prefix_main, fams, cell, hh_tags):
    rows_main = []
    for fam in fams:
        e = eps(f"{prefix_main}_{fam}")
        rows_main += [r for r in e if r["cell"] == cell]
    rows_hh = []
    for t in hh_tags:
        e = eps(t)
        if e:
            rows_hh += [r for r in e if r["cell"] == cell and r["family"] in fams]
    return rows_main, rows_hh


def q3parts(rr):
    if not rr:
        return ("-",) * 4
    gate = sum(np.isfinite(fl(r["gate_t"])) for r in rr)
    corr = sum(fl(r["corridor_max_m"]) <= 0.30 for r in rr)
    q3 = sum(tf(r["q3_pass"]) for r in rr)
    q1 = sum(tf(r["q1_pass"]) for r in rr)
    n = len(rr)
    return (f"{gate}/{n}", f"{corr}/{n}", f"{q3}/{n}", f"{q1}/{n}")


for label, fams in (("평지", ["flat"]), ("험지 7종", ROUGH)):
    for cell in ("fwd03", "fwd05", "back03", "left03", "right03"):
        out = []
        for it in ITS:
            rm, rh = gather(f"m{it}", fams, cell, [f"m{it}_hh_A", f"m{it}_hh_B"])
            out.append((q3parts(rm), q3parts(rh)))
        (ma, ha), (mb, hb) = out
        print(f"| {label} | {cell} | {ma[0]} / {mb[0]} | {ma[1]} / {mb[1]} | {ma[2]} / {mb[2]} | "
              f"{ha[0]} / {hb[0]} | {ha[1]} / {hb[1]} | {ha[2]} / {hb[2]} | {ha[3]} / {hb[3]} |")
print()

# ---- table 7: falls (compact) ------------------------------------------------------
print("### 표 7 · 낙상 (Q 정의) · 실행별 건수\n")
print("| 실행 | episodes | base 접촉 1 N 초과 (학습 종료 조건) | 기울기 60도 0.2초 (종료 안 됨) | 지지면 아래 | 1.5초 안 낙상 | 낙상 난 cell |")
print("|---|---|---|---|---|---|---|")
tags = [f"m{it}_{fam}" for it in ITS for fam in FAMS] + [f"m{it}_offplat" for it in ITS] +        [f"m{it}_hh_{g}" for it in ITS for g in "AB"]
tot = {"n": 0, "base_contact": 0, "tilt60": 0, "below_support": 0}
for t in tags:
    e = eps(t)
    if not e:
        continue
    cnt = {"base_contact": 0, "tilt60": 0, "below_support": 0}
    early = 0
    where = {}
    for r in e:
        if not tf(r["survived"]):
            cnt[r["fall_reason"]] += 1
            early += fl(r["fall_t"]) < 1.5
            k = f'{r["family"]}/{r["cell"]}'
            where[k] = where.get(k, 0) + 1
    tot["n"] += len(e)
    for k in cnt:
        tot[k] += cnt[k]
    if sum(cnt.values()):
        print(f"| {t} | {len(e)} | {cnt['base_contact']} | {cnt['tilt60']} | {cnt['below_support']} | {early} | "
              + ", ".join(f"{k} {v}" for k, v in sorted(where.items())) + " |")
print(f"| 합계 | {tot['n']} | {tot['base_contact']} | {tot['tilt60']} | {tot['below_support']} | | |")
print()

# ---- table 8: 500 expansion -----------------------------------------------------------
plan_p = os.path.join(OUT, "expand_plan.json")
if os.path.exists(plan_p):
    with open(plan_p, encoding="utf-8") as f:
        plan = json.load(f)
    X500 = {"worse": [], "better": []}
    print("### 표 8 · 임계값 부근 cell 의 500 episodes 확대 (새 표본 · 값은 20000 / 20499)\n")
    print("| 지형 · 출발 | cell | 생존 % [Wilson 95%] | Q 통과 % [Wilson 95%] | cell 판정 | 짝 차 [95% 구간] | McNemar p |")
    print("|---|---|---|---|---|---|---|")
    for mode in ("main", "offplat"):
        for fam, cl in plan[mode].items():
            ta = f"x500_m20000_{fam}" if mode == "main" else f"x500_m20000_offplat_{fam}"
            tb = ta.replace("m20000", "m20499")
            sa_all, sb_all = cells(ta), cells(tb)
            if not sa_all or not sb_all:
                continue
            ea_, eb_ = eps(ta), eps(tb)
            for cell in cl:
                sa, sb = sa_all[(fam, cell)], sb_all[(fam, cell)]
                b, c, diff, lo, hi, p = paired(ea_, eb_, fam, cell, sa["rule"])
                lab = "중앙" if mode == "main" else "띠 출발"
                print(f"| {fam} · {lab} | {cell} | {p1(sa['survival'])} [{p1(sa['survival_ci'][0])}, {p1(sa['survival_ci'][1])}] / "
                      f"{p1(sb['survival'])} [{p1(sb['survival_ci'][0])}, {p1(sb['survival_ci'][1])}] | "
                      f"{p1(sa['pass_rate'])} [{p1(sa['pass_ci'][0])}, {p1(sa['pass_ci'][1])}] / "
                      f"{p1(sb['pass_rate'])} [{p1(sb['pass_ci'][0])}, {p1(sb['pass_ci'][1])}] | "
                      f"{'통과' if sa['cell_pass'] else '미달'} / {'통과' if sb['cell_pass'] else '미달'} | "
                      f"{diff:+.3f} [{lo:+.3f}, {hi:+.3f}] | {pv(p)} |")
                if p < 0.05:
                    X500["worse" if diff > 0 else "better"].append(f"{fam}/{lab}/{cell}")
    print()
    print()
    print(f"확대 단계 McNemar p < 0.05 · 20499 가 나쁜 쪽 {len(X500['worse'])} cell: " + ", ".join(X500["worse"]) + "\n")
    print(f"확대 단계 McNemar p < 0.05 · 20499 가 좋은 쪽 {len(X500['better'])} cell: " + ", ".join(X500["better"]))
    print()

# ---- table 9: observation-noise sensitivity -----------------------------------------
if cells("m20000_noise_flat") and cells("m20499_noise_flat"):
    print("### 표 9 · 관측 noise 민감도 · Q 통과 % (noise 끔 / 학습과 같은 noise · 20000 과 20499 각각)\n")
    print("| 지형 | cell | 20000 끔 | 20000 noise | 20499 끔 | 20499 noise | 20000 noise 짝 차 · p | 20499 noise 짝 차 · p |")
    print("|---|---|---|---|---|---|---|---|")
    for fam in ("flat", "stairs_up"):
        if not cells(f"m20000_noise_{fam}") or not cells(f"m20499_noise_{fam}"):
            continue
        for cell in CELL_ORDER:
            vals, pairs = [], []
            for it in ITS:
                c0, c1 = cells(f"m{it}_{fam}")[(fam, cell)], cells(f"m{it}_noise_{fam}")[(fam, cell)]
                vals += [f"{p0(c0['pass_rate'])}{mark(c0)}", f"{p0(c1['pass_rate'])}{mark(c1)}"]
                b, c, diff, lo, hi, p = paired(eps(f"m{it}_{fam}"), eps(f"m{it}_noise_{fam}"), fam, cell, c0["rule"])
                pairs.append(f"{diff:+.2f} · {pv(p)}")
            print(f"| {fam} | {cell} | " + " | ".join(vals) + " | " + " | ".join(pairs) + " |")
    print()
