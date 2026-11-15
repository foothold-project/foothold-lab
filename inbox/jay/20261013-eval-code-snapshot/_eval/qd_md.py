# QD-E1 tables (difficulty 0.2 / 0.5 / 0.8, seed 2000) from out/qd*_*/episodes.csv and meta.json.
# Usage: python qd_md.py > out/QD-E1-tables.md   (also writes out/QD-E1-cells.csv, out/QD-E1-checks.json)
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import q_metrics as Q  # noqa: E402

OUT = os.path.join(HERE, "out")
A = ["flat", "wave", "slope_up", "slope_down"]
B = ["rough_slope", "stairs_up", "stairs_down", "obstacles"]
FAMS = A + B
ROUGH = FAMS[1:]
CELLS = ["stand", "stop03", "fwd01", "fwd02", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
OFFC = ["stand", "stop03", "yawL05", "yawR05"]
ITS = ["20000", "20499"]
DDS = [("02", 0.2), ("05", 0.5), ("08", 0.8)]
NOISE = [("on", "noise 켬"), ("off", "noise 끔")]
_c = {}


def eps(tag):
    if tag not in _c:
        p = os.path.join(OUT, tag, "episodes.csv")
        _c[tag] = list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else None
    return _c[tag]


def meta(tag):
    p = os.path.join(OUT, tag, "meta.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def tf(v):
    return str(v) in ("True", "true", "1")


def qd_tag(dd, nn, it, fam, band=False):
    g = "band" if band else ("A" if fam in A else "B")
    return f"qd{dd}_{nn}_m{it}_{g}"


def group(tag, fam, cell):
    e = eps(tag)
    if e is None:
        return None
    g = {int(r["episode"]): r for r in e if r["family"] == fam and r["cell"] == cell}
    return g or None


def rule(cell, span=False):
    return ("span_" if span else "") + ("q2_pass" if cell == "stop03" else "q1_pass")


def rate(g, key):
    return sum(tf(r[key]) for r in g.values()) / len(g)


def p0(x):
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{100 * x:.0f}"


def pv(p):
    return f"{p:.2g}" if p < 0.1 else f"{p:.2f}"


def avail(nn):
    return all(eps(qd_tag(dd, nn, it, f)) is not None for dd, _ in DDS for it in ITS for f in FAMS) and \
        all(eps(qd_tag(dd, nn, it, "wave", True)) is not None for dd, _ in DDS for it in ITS)


done = {nn: [(dd, it) for dd, _ in DDS for it in ITS
             if all(eps(qd_tag(dd, nn, it, f)) is not None for f in FAMS) and eps(qd_tag(dd, nn, it, "wave", True)) is not None]
        for nn, _ in NOISE}
checks = {"done": done, "pairing": {}}

# ---- pairing between checkpoints -------------------------------------------------------
for nn, _ in NOISE:
    for dd, _ in DDS:
        for g in ("A", "B", "band"):
            a, b = meta(f"qd{dd}_{nn}_m20000_{g}"), meta(f"qd{dd}_{nn}_m20499_{g}")
            if not a or not b:
                continue
            checks["pairing"][f"{dd}/{nn}/{g}"] = {
                "ext_equal": a["pairing_sha256_ext"] == b["pairing_sha256_ext"],
                "old3_equal": all(a["pairing_sha256"][k] == b["pairing_sha256"][k] for k in ("init_root_pose", "init_joint_pos", "body_masses")),
                "mesh_equal": a["terrain_mesh"] == b["terrain_mesh"],
                "uuid": [a["devices"]["torch_cuda0_uuid"][:8], b["devices"]["torch_cuda0_uuid"][:8]],
                "nonfinite": a["checks_run"]["nonfinite_action_or_obs_count"] + b["checks_run"]["nonfinite_action_or_obs_count"],
                "cmd_err": max(a["checks_run"]["obs_single_cmd_vs_target_max_abs"], b["checks_run"]["obs_single_cmd_vs_target_max_abs"]),
                "teacher_input_change": max(a["checks_pre"]["teacher_input_randomized_max_abs_action_change"],
                                            b["checks_pre"]["teacher_input_randomized_max_abs_action_change"]),
                "difficulty": a["args"]["difficulty"], "seed": a["args"]["eval_seed"], "noise": a["args"]["obs_noise"]}
pp = checks["pairing"]
print("### 표 1 · 짝과 점검 (두 체크포인트 사이 · 실행 묶음별)\n")
print("| 항목 | 결과 |")
print("|---|---|")
print(f"| 비교한 묶음 (난이도 · noise · A/B/띠) | {len(pp)} |")
print(f"| 넓힌 fingerprint (COM · 마찰 · 반발 · 강성 · 감쇠 · 영점 · 지연) 같음 | {sum(v['ext_equal'] for v in pp.values())} / {len(pp)} |")
print(f"| root 자세 · 관절각 · 질량 hash 같음 | {sum(v['old3_equal'] for v in pp.values())} / {len(pp)} |")
print(f"| 지형 메시 hash 같음 | {sum(v['mesh_equal'] for v in pp.values())} / {len(pp)} |")
print(f"| GPU UUID 315d098f | {sum(v['uuid'] == ['315d098f', '315d098f'] for v in pp.values())} / {len(pp)} |")
print(f"| 비유한 행동 · 관측 / 명령 칸 오차 / teacher 입력 교란에 대한 student 행동 변화 | "
      f"{sum(v['nonfinite'] for v in pp.values())} / {max([v['cmd_err'] for v in pp.values()] or [0])} / {max([v['teacher_input_change'] for v in pp.values()] or [0])} |")
print()

# ---- overview ------------------------------------------------------------------------------
print("### 표 2 · 난이도별 요약 (값은 20000 / 20499 · % · 현행 정의, 괄호는 제안 정의 Q2)\n")
print("| noise | 난이도 | 생존 (중앙 8 지형) | 정지 밖 Q1 (중앙) | 정지 Q2 (중앙 8) | 띠 정지 Q2 (7) | 띠 회전 Q1 (7 × 2) | 띠 stand Q1 | 낙상 수 (중앙 + 띠) |")
print("|---|---|---|---|---|---|---|---|---|")
overview = []
for nn, nname in NOISE:
    for dd, d in DDS:
        vals = []
        for it in ITS:
            if (dd, it) not in done[nn]:
                vals = None
                break
            cen = [r for f in FAMS for r in eps(qd_tag(dd, nn, it, f)) if r["family"] == f]
            band = [r for r in eps(qd_tag(dd, nn, it, "wave", True))]
            surv = sum(tf(r["survived"]) for r in cen) / len(cen)
            mv = [r for r in cen if r["cell"] != "stop03"]
            q1 = sum(tf(r["q1_pass"]) for r in mv) / len(mv)
            st = [r for r in cen if r["cell"] == "stop03"]
            q2 = sum(tf(r["q2_pass"]) for r in st) / len(st)
            q2s = sum(tf(r["span_q2_pass"]) for r in st) / len(st)
            bst = [r for r in band if r["cell"] == "stop03"]
            bq2 = sum(tf(r["q2_pass"]) for r in bst) / len(bst)
            bq2s = sum(tf(r["span_q2_pass"]) for r in bst) / len(bst)
            by = [r for r in band if r["cell"] in ("yawL05", "yawR05")]
            byq = sum(tf(r["q1_pass"]) for r in by) / len(by)
            bs = [r for r in band if r["cell"] == "stand"]
            bsq = sum(tf(r["q1_pass"]) for r in bs) / len(bs)
            falls = sum(not tf(r["survived"]) for r in cen + band)
            vals.append(dict(surv=surv, q1=q1, q2=q2, q2s=q2s, bq2=bq2, bq2s=bq2s, byq=byq, bsq=bsq, falls=falls))
        if not vals:
            continue
        a, b = vals
        overview.append(dict(noise=nn, d=d, v20000=a, v20499=b))
        print(f"| {nname} | {d} | {p0(a['surv'])} / {p0(b['surv'])} | {p0(a['q1'])} / {p0(b['q1'])} | "
              f"{p0(a['q2'])} ({p0(a['q2s'])}) / {p0(b['q2'])} ({p0(b['q2s'])}) | {p0(a['bq2'])} ({p0(a['bq2s'])}) / {p0(b['bq2'])} ({p0(b['bq2s'])}) | "
              f"{p0(a['byq'])} / {p0(b['byq'])} | {p0(a['bsq'])} / {p0(b['bsq'])} | {a['falls']} / {b['falls']} |")
print()

# ---- collapse map ----------------------------------------------------------------------------
rows_csv = []
for nn, nname in NOISE:
    if not all((dd, it) in done[nn] for dd, _ in DDS for it in ITS):
        continue
    print(f"### 표 3 ({nname}) · 난이도에 따라 무너지는 cell · Q 통과 % 0.2 → 0.5 → 0.8 (`*` cell 판정 미달 · 생존 95 % · 통과 90 %)\n")
    print("한 체크포인트라도 어느 난이도에서 cell 판정 미달이거나 0.2 → 0.8 변화가 10 pp 이상인 행만 싣는다. 정지 (stop03) 는 따로 표 4.\n")
    print("| 지형 · 출발 | cell | 20000 | 20499 | 20000 생존 0.8 | 20499 생존 0.8 |")
    print("|---|---|---|---|---|---|")
    for fam, band, cl in [(f, False, CELLS) for f in FAMS] + [(f, True, OFFC) for f in ROUGH]:
        for cell in cl:
            if cell == "stop03":
                continue
            line, show, sv = [], False, []
            for it in ITS:
                rs, marks = [], []
                for dd, d in DDS:
                    g = group(qd_tag(dd, nn, it, fam, band), fam, cell)
                    r_ = rate(g, rule(cell))
                    s_ = rate(g, "survived")
                    ok = r_ >= Q.CELL_PASS and s_ >= Q.CELL_SURVIVAL
                    rs.append(r_)
                    marks.append("" if ok else "*")
                    show |= not ok
                    rows_csv.append(dict(noise=nn, d=d, it=it, family=fam, start="band" if band else "centre", cell=cell,
                                         n=len(g), survival=s_, pass_rate=r_, span_pass=rate(g, rule(cell, True)),
                                         q1m=rate(g, "q1m_pass"), q1a=rate(g, "q1a_pass"),
                                         mae_vx=float(np.nanmean([float(x["mae_vx"]) for x in g.values()])),
                                         mae_vy=float(np.nanmean([float(x["mae_vy"]) for x in g.values()])),
                                         mae_wz=float(np.nanmean([float(x["mae_wz"]) for x in g.values()]))))
                show |= abs(rs[2] - rs[0]) >= 0.10
                line.append(" → ".join(f"{p0(x)}{m}" for x, m in zip(rs, marks)))
                sv.append(s_)
            if show:
                print(f"| {fam} · {'띠' if band else '중앙'} | {cell} | {line[0]} | {line[1]} | {p0(sv[0])} | {p0(sv[1])} |")
    print()
    print(f"### 표 4 ({nname}) · 정지 stop03 · Q2 통과 % 0.2 → 0.5 → 0.8 (현행 정의 · 괄호 제안 정의)\n")
    print("| 지형 · 출발 | 20000 | 20499 |")
    print("|---|---|---|")
    for fam, band in [(f, False) for f in FAMS] + [(f, True) for f in ROUGH]:
        line = []
        for it in ITS:
            parts = []
            for dd, d in DDS:
                g = group(qd_tag(dd, nn, it, fam, band), fam, "stop03")
                parts.append(f"{p0(rate(g, 'q2_pass'))} ({p0(rate(g, 'span_q2_pass'))})")
                rows_csv.append(dict(noise=nn, d=d, it=it, family=fam, start="band" if band else "centre", cell="stop03",
                                     n=len(g), survival=rate(g, "survived"), pass_rate=rate(g, "q2_pass"),
                                     span_pass=rate(g, "span_q2_pass"), q1m=float("nan"), q1a=float("nan"),
                                     mae_vx=float("nan"), mae_vy=float("nan"), mae_wz=float("nan")))
            line.append(" → ".join(parts))
        print(f"| {fam} · {'띠' if band else '중앙'} | {line[0]} | {line[1]} |")
    print()

if rows_csv:
    with open(os.path.join(OUT, "QD-E1-cells.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys()))
        w.writeheader()
        for r in rows_csv:
            w.writerow(r)

# ---- checkpoint difference per difficulty --------------------------------------------------
print("### 표 5 · 두 체크포인트 차이 · 난이도별 짝 McNemar (탐색 결과 · 하락 = 20000 만 통과가 많음)\n")
print("| noise | 난이도 | 검정 수 | 보정 전 하락 · 상승 | Holm 뒤 하락 · 상승 | 보정 전 유의 cell |")
print("|---|---|---|---|---|---|")
diffs = []
for nn, nname in NOISE:
    for dd, d in DDS:
        if not all((dd, it) in done[nn] for it in ITS):
            continue
        res = []
        for fam, band, cl in [(f, False, CELLS) for f in FAMS] + [(f, True, OFFC) for f in ROUGH]:
            for cell in cl:
                ga = group(qd_tag(dd, nn, "20000", fam, band), fam, cell)
                gb = group(qd_tag(dd, nn, "20499", fam, band), fam, cell)
                k = rule(cell)
                b_ = sum(tf(ga[e][k]) and not tf(gb[e][k]) for e in ga)
                c_ = sum((not tf(ga[e][k])) and tf(gb[e][k]) for e in ga)
                res.append((Q.mcnemar_exact(b_, c_), b_, c_, f"{fam}{'·띠' if band else ''}/{cell}"))
        rej = Q.holm_reject([x[0] for x in res])
        down = [x for x in res if x[0] < 0.05 and x[1] > x[2]]
        up = [x for x in res if x[0] < 0.05 and x[2] > x[1]]
        hd = sum(1 for x, r in zip(res, rej) if r and x[1] > x[2])
        hu = sum(1 for x, r in zip(res, rej) if r and x[2] > x[1])
        diffs.append(dict(noise=nn, d=d, m=len(res), down=[x[3] for x in down], up=[x[3] for x in up], holm_down=hd, holm_up=hu))
        names = ", ".join([x[3] + " ↓" for x in down] + [x[3] + " ↑" for x in up]) or "없음"
        print(f"| {nname} | {d} | {len(res)} | {len(down)} · {len(up)} | {hd} · {hu} | {names} |")
print()

# ---- seed 1000 vs 2000 at difficulty 0.5 --------------------------------------------------
print("### 표 6 · 난이도 0.5 · 지형 시드 1000 (Q-E1) 대 2000 (QD) · 짝 아님 (메시 · 출발 자세 · DR 모두 다름)\n")
print("Q-E1 은 지형 하나씩 띄운 실행 (env 1,100), QD 는 지형 넷씩 묶은 실행 (env 4,400) 이라 env 배치도 다르다. 차이는 두 독립 표본의 차이이고 Wilson 구간이 겹치는지로만 본다.\n")
print("| noise | 체크포인트 | 지형 · 출발 | 정지 밖 Q1 시드 1000 → 2000 | 정지 Q2 시드 1000 → 2000 | 10 pp 이상 다른 cell (1000 → 2000) |")
print("|---|---|---|---|---|---|")
seedcmp = []
for nn, nname in NOISE:
    if not all(("05", it) in done[nn] for it in ITS):
        continue
    for it in ITS:
        for fam, band, cl in [(f, False, CELLS) for f in FAMS] + [(f, True, OFFC) for f in ROUGH]:
            if band:
                t1 = f"m{it}_noise_offplat" if nn == "on" else f"m{it}_offplat"
            else:
                t1 = f"m{it}_noise_{fam}" if nn == "on" else f"m{it}_{fam}"
            t2 = qd_tag("05", nn, it, fam, band)
            if eps(t1) is None:
                continue
            mv1 = [r for r in eps(t1) if r["family"] == fam and r["cell"] in cl and r["cell"] != "stop03"]
            mv2 = [r for r in eps(t2) if r["family"] == fam and r["cell"] in cl and r["cell"] != "stop03"]
            s1 = [r for r in eps(t1) if r["family"] == fam and r["cell"] == "stop03"]
            s2 = [r for r in eps(t2) if r["family"] == fam and r["cell"] == "stop03"]
            big = []
            for cell in cl:
                g1, g2 = group(t1, fam, cell), group(t2, fam, cell)
                r1, r2 = rate(g1, rule(cell)), rate(g2, rule(cell))
                if abs(r2 - r1) >= 0.10:
                    big.append(f"{cell} {p0(r1)} → {p0(r2)}")
            q1a, q1b = sum(tf(r["q1_pass"]) for r in mv1) / len(mv1), sum(tf(r["q1_pass"]) for r in mv2) / len(mv2)
            z1, z2 = sum(tf(r["q2_pass"]) for r in s1) / len(s1), sum(tf(r["q2_pass"]) for r in s2) / len(s2)
            seedcmp.append(dict(noise=nn, it=it, fam=fam, band=band, q1=[q1a, q1b], q2=[z1, z2], big=big))
            print(f"| {nname} | {it} | {fam} · {'띠' if band else '중앙'} | {p0(q1a)} → {p0(q1b)} | {p0(z1)} → {p0(z2)} | {', '.join(big) if big else '없음'} |")
print()

# ---- low-speed proposal by difficulty -------------------------------------------------------
print("### 표 7 · 저속 fwd01 · 현행 Q1 / 이동 보조 / 제안 (a) · 중앙 8 지형 합계 % (값은 20000 / 20499)\n")
print("| noise | 난이도 | Q1 | 이동 보조 | (a) |")
print("|---|---|---|---|---|")
for nn, nname in NOISE:
    for dd, d in DDS:
        if not all((dd, it) in done[nn] for it in ITS):
            continue
        out = []
        for key in ("q1_pass", "q1m_pass", "q1a_pass"):
            v = []
            for it in ITS:
                rr = [r for f in FAMS for r in eps(qd_tag(dd, nn, it, f)) if r["family"] == f and r["cell"] == "fwd01"]
                v.append(sum(tf(r[key]) for r in rr) / len(rr))
            out.append(f"{p0(v[0])} / {p0(v[1])}")
        print(f"| {nname} | {d} | " + " | ".join(out) + " |")
print()

# ---- falls ------------------------------------------------------------------------------
print("### 표 8 · 낙상 · 지형별 건수 (중앙 + 띠 · 값은 20000 / 20499)\n")
print("| noise | 난이도 | " + " | ".join(FAMS) + " |")
print("|---|---|" + "---|" * len(FAMS))
for nn, nname in NOISE:
    for dd, d in DDS:
        if not all((dd, it) in done[nn] for it in ITS):
            continue
        cells_ = []
        for fam in FAMS:
            v = []
            for it in ITS:
                n = sum(not tf(r["survived"]) for r in eps(qd_tag(dd, nn, it, fam)) if r["family"] == fam)
                if fam in ROUGH:
                    n += sum(not tf(r["survived"]) for r in eps(qd_tag(dd, nn, it, fam, True)) if r["family"] == fam)
                v.append(n)
            cells_.append(f"{v[0]} / {v[1]}")
        print(f"| {nname} | {d} | " + " | ".join(cells_) + " |")
print()
checks.update(overview=overview, diffs=diffs, seedcmp=seedcmp)
json.dump(checks, open(os.path.join(OUT, "QD-E1-checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
