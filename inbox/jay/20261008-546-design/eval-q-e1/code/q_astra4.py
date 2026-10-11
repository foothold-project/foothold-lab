# ASTRA 4 re-aggregation tables from the saved episodes.csv files (CPU only).
# Current Q-E1 rule ("n50") and the ASTRA proposal ("span") side by side, Q2 split, stop
# diagnostics, proposal (a), noise-on results, and Holm-corrected counts of paired tests.
# Usage: python q_astra4.py > out/Q-E1-astra4-tables.md   (also writes out/Q-E1-astra4.json)

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
CELLS = ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
OFFC = ["stand", "stop03", "yawL05", "yawR05"]
_c = {}


def eps(tag):
    if tag not in _c:
        p = os.path.join(OUT, tag, "episodes.csv")
        _c[tag] = list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else None
    return _c[tag]


def tf(v):
    return str(v) in ("True", "true", "1")


def fl(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def rule(cell, span=False):
    return ("span_" if span else "") + ("q2_pass" if cell == "stop03" else "q1_pass")


def group(tag, fam, cell):
    e = eps(tag)
    if e is None:
        return None
    return {int(r["episode"]): r for r in e if r["family"] == fam and r["cell"] == cell}


def mcn(A, B, key):
    b = sum(tf(A[k][key]) and not tf(B[k][key]) for k in A)
    c = sum((not tf(A[k][key])) and tf(B[k][key]) for k in A)
    return b, c, Q.mcnemar_exact(b, c)


def pct(n, d):
    return "-" if not d else f"{100 * n / d:.0f}"


report = {}

# ---- A1/A2: Q2 under both time definitions, with the split ------------------------------
CONDS = [("noise 끔 · 중앙", "m{it}_{fam}", FAMS), ("noise 끔 · 띠", "m{it}_offplat", ROUGH),
         ("noise 켬 · 중앙", "m{it}_noise_{fam}", FAMS), ("noise 켬 · 띠", "m{it}_noise_offplat", ROUGH),
         ("500 확대 · 중앙", "x500_m{it}_{fam}", FAMS)]
print("### 표 A1 · Q2 를 두 시간 정의로 · 분해 (전체 분모 그대로 · 값은 20000 / 20499)\n")
print("현행 = 50 표본 · 시작 j ≥ 250 · 마감 j ≤ 300. 제안 = 시각 원점 j = 250 (t 5.00 s) · 마감 j ≤ 300 · j..j+50 의 51 표본 모두 문턱 아래 · "
      "기울기 0.2 s 도 11 표본. 분해: 전진 미달 / 정지 자체 미달 / 둘 다 충족.\n")
print("| 조건 | 지형 | n | Q2 통과 현행 | Q2 통과 제안 | 현행 분해 (전진 미달 · 정지 미달 · 충족) | 제안 분해 | 바뀐 episode |")
print("|---|---|---|---|---|---|---|---|")
a1 = []
for cname, pat, fams in CONDS:
    for fam in fams:
        cells = []
        for it in ITS:
            g = group(pat.format(it=it, fam=fam), fam, "stop03")
            cells.append(g)
        if any(g is None or not g for g in cells):
            continue
        n = len(cells[0])
        cur = [sum(tf(r["q2_pass"]) for r in g.values()) for g in cells]
        spn = [sum(tf(r["span_q2_pass"]) for r in g.values()) for g in cells]
        sp = [[sum(r["q2_cat"] == k for r in g.values()) for k in ("fwd_fail", "stop_fail", "both_ok")] for g in cells]
        sps = [[sum(r["span_q2_cat"] == k for r in g.values()) for k in ("fwd_fail", "stop_fail", "both_ok")] for g in cells]
        ch = [sum(tf(r["q2_pass"]) != tf(r["span_q2_pass"]) for r in g.values()) for g in cells]
        a1.append(dict(cond=cname, fam=fam, n=n, cur=cur, span=spn, split=sp, split_span=sps, changed=ch))
        print(f"| {cname} | {fam} | {n} | {cur[0]} / {cur[1]} | {spn[0]} / {spn[1]} | "
              f"{'·'.join(map(str, sp[0]))} / {'·'.join(map(str, sp[1]))} | {'·'.join(map(str, sps[0]))} / {'·'.join(map(str, sps[1]))} | "
              f"{ch[0]} / {ch[1]} |")
report["A1_q2"] = a1
print()

# ---- A3: survival / Q1 effect of the span definition (tilt hold 10 -> 11 samples) ---------
print("### 표 A2 · 기울기 0.2 s 를 11 표본으로 바꿨을 때 생존 · Q 통과가 바뀐 episode 수 (모든 저장 실행)\n")
print("| 실행 묶음 | episodes | 생존 현행 → 제안 바뀜 | 낙상 현행 | 낙상 제안 | cell 판정 통과가 바뀐 episode (Q2 제외) |")
print("|---|---|---|---|---|---|")
groups = {"Q-E1 noise 끔 (주 · 띠)": [f"m{it}_{f}" for it in ITS for f in FAMS + ["offplat"]],
          "Q-E1 noise 켬": [f"m{it}_noise_{f}" for it in ITS for f in FAMS + ["offplat"]],
          "Q-E1 500 확대": [f"x500_m{it}_{f}" for it in ITS for f in FAMS] + [f"x500_m{it}_offplat_{f}" for it in ITS for f in ROUGH],
          "Q-E1 heading hold": [f"m{it}_hh_{g}" for it in ITS for g in "AB"],
          "D1-A teacher · 순열": [f"{c}{it}_{f}" for c in ("t", "tp") for it in ITS for f in FAMS + ["offplat"]]}
a2 = {}
for gname, tags in groups.items():
    n = sch = fc = fs = qch = 0
    for t in tags:
        e = eps(t)
        if not e:
            continue
        for r in e:
            n += 1
            sch += tf(r["survived"]) != tf(r["span_survived"])
            fc += not tf(r["survived"])
            fs += not tf(r["span_survived"])
            if r["cell"] != "stop03":
                qch += tf(r["q1_pass"]) != tf(r["span_q1_pass"])
    a2[gname] = dict(n=n, surv_changed=sch, falls_cur=fc, falls_span=fs, q1_changed=qch)
    print(f"| {gname} | {n} | {sch} | {fc} | {fs} | {qch} |")
report["A2_tilt"] = a2
print()

# ---- A3: stop diagnostics ------------------------------------------------------------
print("### 표 A3 · 정지 진단 (전환 t 5.00 s 뒤 5 s · 중앙값 · 값은 20000 / 20499 · 판정에는 쓰지 않음)\n")
print("순변위 = 전환점에서 정지 창 시작점까지 (`stop_net_disp_m`, 예전 `stop_dist_m`). 최대 이탈 = 5 s 동안 전환점에서 가장 먼 거리. "
      "RMS 는 실제 base 속도 (시뮬레이터 값). 0.10 s 창 = 5 표본 RMS 로 마감 뒤 구간에서 문턱 아래인 창의 비율 (보조).\n")
print("| 조건 | 지형 | 순변위 cm | 최대 이탈 cm | yaw 변화 절대값 rad | 평면 속도 RMS m/s | yaw rate RMS rad/s | 0.10 s 창 정지 비율 |")
print("|---|---|---|---|---|---|---|---|")
a3 = []
for cname, pat, fams in CONDS[:4]:
    for fam in fams:
        gs = [group(pat.format(it=it, fam=fam), fam, "stop03") for it in ITS]
        if any(g is None or not g for g in gs):
            continue

        def med(g, k, f=1.0, absv=False):
            v = np.array([fl(r[k]) for r in g.values()])
            v = v[np.isfinite(v)]
            if absv:
                v = np.abs(v)
            return np.median(v) * f if v.size else float("nan")

        vals = [(med(g, "stop_net_disp_m", 100), med(g, "stop_max_dev_m", 100), med(g, "stop_yaw_change_rad", absv=True),
                 med(g, "stop_speed_rms"), med(g, "stop_yawrate_rms"), med(g, "aux10_still_frac")) for g in gs]
        a3.append(dict(cond=cname, fam=fam, v20000=vals[0], v20499=vals[1]))
        print(f"| {cname} | {fam} | {vals[0][0]:.1f} / {vals[1][0]:.1f} | {vals[0][1]:.1f} / {vals[1][1]:.1f} | "
              f"{vals[0][2]:.3f} / {vals[1][2]:.3f} | {vals[0][3]:.3f} / {vals[1][3]:.3f} | {vals[0][4]:.3f} / {vals[1][4]:.3f} | "
              f"{vals[0][5]:.2f} / {vals[1][5]:.2f} |")
report["A3_stop_diag"] = a3
print()

# ---- A4: proposal (a) for low speed -----------------------------------------------------
print("### 표 A4 · 저속 · 현행 Q1 / 이동 보조 / 제안 (a) MAE ≤ min(0.15, 0.5×|명령|) · 통과 % (값은 20000 / 20499)\n")
print("| 조건 | 지형 | fwd01 Q1 | fwd01 이동 보조 | fwd01 (a) | fwd02 Q1 | fwd02 이동 보조 | fwd02 (a) |")
print("|---|---|---|---|---|---|---|---|")
a4 = []
for cname, pat, fams in (CONDS[0], CONDS[2]):
    for fam in fams:
        row = []
        ok = True
        for cell in ("fwd01", "fwd02"):
            gs = [group(pat.format(it=it, fam=fam), fam, cell) for it in ITS]
            if any(g is None or not g for g in gs):
                ok = False
                break
            for key in ("q1_pass", "q1m_pass", "q1a_pass"):
                v = [sum(tf(r[key]) for r in g.values()) / len(g) for g in gs]
                row.append(f"{100 * v[0]:.0f} / {100 * v[1]:.0f}")
                a4.append(dict(cond=cname, fam=fam, cell=cell, key=key, r20000=v[0], r20499=v[1]))
        if ok:
            print(f"| {cname} | {fam} | " + " | ".join(row) + " |")
report["A4_low_speed"] = a4
print()

# ---- B: noise on vs off, cell rule, both checkpoints ------------------------------------
print("### 표 B1 · 관측 noise 켬 (학습과 같음) 대 끔 · cell 규칙 통과 % · 현행 정의 (값은 끔 / 켬)\n")
print("| 체크포인트 | 지형 · 출발 | episodes | 생존 끔 / 켬 | 정지 제외 Q1 끔 / 켬 | 정지 Q2 끔 / 켬 | 정지 Q2 제안 정의 끔 / 켬 | noise 짝 차 McNemar p < 0.05 cell |")
print("|---|---|---|---|---|---|---|---|")
b1 = []
for it in ITS:
    for fam, off in [(f, False) for f in FAMS] + [(f, True) for f in ROUGH]:
        ta = f"m{it}_offplat" if off else f"m{it}_{fam}"
        tb = f"m{it}_noise_offplat" if off else f"m{it}_noise_{fam}"
        if not eps(ta) or not eps(tb):
            continue
        cl = OFFC if off else CELLS
        A = {c: group(ta, fam, c) for c in cl}
        B = {c: group(tb, fam, c) for c in cl}
        if any(not B[c] for c in cl):
            continue
        n = sum(len(A[c]) for c in cl)
        sa = sum(tf(r["survived"]) for c in cl for r in A[c].values())
        sb = sum(tf(r["survived"]) for c in cl for r in B[c].values())
        nq = sum(len(A[c]) for c in cl if c != "stop03")
        qa = sum(tf(r["q1_pass"]) for c in cl if c != "stop03" for r in A[c].values())
        qb = sum(tf(r["q1_pass"]) for c in cl if c != "stop03" for r in B[c].values())
        za = sum(tf(r["q2_pass"]) for r in A["stop03"].values())
        zb = sum(tf(r["q2_pass"]) for r in B["stop03"].values())
        za2 = sum(tf(r["span_q2_pass"]) for r in A["stop03"].values())
        zb2 = sum(tf(r["span_q2_pass"]) for r in B["stop03"].values())
        sig = []
        for c in cl:
            b, cc, p = mcn(A[c], B[c], rule(c))
            if p < 0.05:
                sig.append(f"{c} {'↓' if b > cc else '↑'}")
        b1.append(dict(it=it, fam=fam, band=off, n=n, surv=[sa, sb], q1=[qa, qb, nq], q2=[za, zb], q2span=[za2, zb2], sig=sig))
        print(f"| {it} | {fam} · {'띠' if off else '중앙'} | {n} | {pct(sa, n)} / {pct(sb, n)} | {pct(qa, nq)} / {pct(qb, nq)} | "
              f"{za} / {zb} | {za2} / {zb2} | {', '.join(sig) if sig else '없음'} |")
report["B1_noise"] = b1
print()

# ---- A5: multiple comparisons with Holm ---------------------------------------------------
print("### 표 A5 · 짝 검정 목록별 개수 · 보정 전 p < 0.05 와 Holm 보정 뒤 (탐색 결과)\n")
print("| 목록 | 정의 | 검정 수 | 보정 전 하락 · 상승 | Holm 뒤 하락 · 상승 |")
print("|---|---|---|---|---|")


def collect(pairs, span):
    out = []
    for ta, tb, fam, cells in pairs:
        for c in cells:
            A, B = group(ta, fam, c), group(tb, fam, c)
            if not A or not B:
                continue
            b, cc, p = mcn(A, B, rule(c, span))
            out.append((p, b, cc))
    return out


lists = {
    "Q-E1 선별 (20000 대 20499 · 주 88 + 띠 28)": [(f"m20000_{f}", f"m20499_{f}", f, CELLS) for f in FAMS]
    + [("m20000_offplat", "m20499_offplat", f, OFFC) for f in ROUGH],
    "Q-E1 500 확대 (20000 대 20499 · 앞 결과로 고른 23 cell)": None,
    "Q-E1 noise 켬 (20000 대 20499)": [(f"m20000_noise_{f}", f"m20499_noise_{f}", f, CELLS) for f in FAMS]
    + [("m20000_noise_offplat", "m20499_noise_offplat", f, OFFC) for f in ROUGH],
    "D1-A (teacher 정상 대 순열 · 두 체크포인트)": [(f"t{it}_{f}", f"tp{it}_{f}", f, CELLS) for it in ITS for f in FAMS]
    + [(f"t{it}_offplat", f"tp{it}_offplat", f, OFFC) for it in ITS for f in ROUGH],
}
plan = json.load(open(os.path.join(OUT, "expand_plan.json"), encoding="utf-8"))
lists["Q-E1 500 확대 (20000 대 20499 · 앞 결과로 고른 23 cell)"] = (
    [(f"x500_m20000_{f}", f"x500_m20499_{f}", f, cl) for f, cl in plan["main"].items()]
    + [(f"x500_m20000_offplat_{f}", f"x500_m20499_offplat_{f}", f, cl) for f, cl in plan["offplat"].items()])
a5 = {}
for lname, pairs in lists.items():
    for span in (False, True):
        res = collect(pairs, span)
        if not res:
            continue
        ps = [x[0] for x in res]
        rej = Q.holm_reject(ps)
        down = sum(1 for (p, b, c) in res if p < 0.05 and b > c)
        up = sum(1 for (p, b, c) in res if p < 0.05 and c > b)
        hd = sum(1 for (p, b, c), r in zip(res, rej) if r and b > c)
        hu = sum(1 for (p, b, c), r in zip(res, rej) if r and c > b)
        dname = "제안 (span)" if span else "현행"
        a5[f"{lname} | {dname}"] = dict(m=len(res), raw_down=down, raw_up=up, holm_down=hd, holm_up=hu)
        print(f"| {lname} | {dname} | {len(res)} | {down} · {up} | {hd} · {hu} |")
report["A5_holm"] = a5
print()
print("하락 · 상승의 방향: Q-E1 목록은 20000 이 통과하고 20499 가 실패한 쪽이 많으면 하락, D1-A 는 teacher 정상이 통과하고 순열이 실패한 쪽이 많으면 하락. "
      "500 확대 cell 은 앞 결과로 골랐으므로 Holm 보정으로 선택 편향까지 없어지지 않는다.")
json.dump(report, open(os.path.join(OUT, "Q-E1-astra4.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
