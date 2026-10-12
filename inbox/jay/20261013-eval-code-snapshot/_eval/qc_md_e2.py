# E2 copy of qc_md.py (tag prefix e2_, output names; the E1-only qc_repro check finds nothing). QC tables: E2 student along checkpoints (Q-E1 main condition, seed 1000, difficulty 0.5).
# Usage: python qc_md_e2.py > out/QC-E2-tables.md   (also writes out/QC-E2-cells.csv, out/QC-E2-checks.json)
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
ITS_ON = ["5000", "10000", "15000", "19500", "20000", "20499"]
ITS_OFF = ["19500", "20000", "20499"]
_c = {}


def eps(tag):
    if tag not in _c:
        p = os.path.join(OUT, tag, "episodes.csv")
        _c[tag] = list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else None
    return _c[tag]


def meta(tag):
    p = os.path.join(OUT, tag, "meta.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def tag(it, nn, fam, band=False):
    pre = f"e2_m{it}_noise_" if nn == "on" else f"e2_m{it}_"
    return pre + ("offplat" if band else fam)


def tf(v):
    return str(v) in ("True", "true", "1")


def group(t, fam, cell):
    e = eps(t)
    if e is None:
        return None
    g = {int(r["episode"]): r for r in e if r["family"] == fam and r["cell"] == cell}
    return g or None


def rule(cell, span=False, a=False):
    base = "q2_pass" if cell == "stop03" else ("q1a_pass" if (a and cell in ("fwd01", "fwd02")) else "q1_pass")
    return ("span_" if span else "") + base


def rate(g, key):
    return sum(tf(r[key]) for r in g.values()) / len(g)


def p0(x):
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{100 * x:.0f}"


def units():
    return [(f, False, c) for f in FAMS for c in CELLS] + [(f, True, c) for f in ROUGH for c in OFFC]


def have(it, nn):
    return all(eps(tag(it, nn, f)) is not None for f in FAMS) and eps(tag(it, nn, "wave", True)) is not None


done = {"on": [it for it in ITS_ON if have(it, "on")], "off": [it for it in ITS_OFF if have(it, "off")]}
checks = {"done": done}

# ---- 1. reproduction of the stored 20000 runs by the current code -----------------------------
rep = {}
for new, old in ():  # E1-only reproduction check, not applicable to E2
    pa, pb = os.path.join(OUT, new, "traj.npz"), os.path.join(OUT, old, "traj.npz")
    if os.path.exists(pa) and os.path.exists(pb):
        a, b = np.load(pa), np.load(pb)
        rep[old] = {"traj_bitwise_equal": bool(np.array_equal(a["traj"], b["traj"])), "term_equal": bool(np.array_equal(a["term"], b["term"])),
                    "traj_max_abs": float(np.nanmax(np.abs(a["traj"].astype(np.float64) - b["traj"].astype(np.float64))))}
checks["repro"] = rep

# ---- 2. pairing ------------------------------------------------------------------------------------
pair = {}
ref_ext = {}
for f in FAMS + ["offplat"]:
    band = f == "offplat"
    fam = "wave" if band else f
    rows = {}
    for nn, its in (("on", ITS_ON), ("off", ITS_OFF)):
        for it in its:
            m = meta(tag(it, nn, fam, band))
            if m:
                rows[f"{it}/{nn}"] = m
    if False:  # E1-only
        rows["20000/on(repro)"] = meta("qc_repro_m20000_noise_flat")
    if False:  # E1-only
        rows["20000/off(repro)"] = meta("qc_repro_m20000_flat")
    if False:  # E1-only fingerprint run
        rows["20000/fp"] = meta("fp_m20000_stairs_up")
    old3 = {k: tuple(v["pairing_sha256"][x] for x in ("init_root_pose", "init_joint_pos", "body_masses")) for k, v in rows.items()}
    ext = {k: json.dumps(v["pairing_sha256_ext"], sort_keys=True) for k, v in rows.items() if v.get("pairing_sha256_ext")}
    mesh = {k: json.dumps(v["terrain_mesh"]) for k, v in rows.items() if "terrain_mesh" in v}
    KEYA = {"policy": "student", "families": None, "cells": "all", "episodes": None, "difficulty": 0.5, "eval_seed": 1000,
            "spawn_offset": "", "heading_hold": 0.0, "height_perm_seed": -1}
    args = {k: json.dumps({a: (v["args"].get(a, d) if v["args"].get(a, d) is not None else d) for a, d in KEYA.items()}, sort_keys=True)
            for k, v in rows.items()}
    pair[f] = {"runs": sorted(rows), "old3_distinct": len(set(old3.values())), "ext_runs": sorted(ext), "ext_distinct": len(set(ext.values())),
               "mesh_distinct": len(set(mesh.values())), "args_distinct": len(set(args.values())),
               "nonfinite": sum(v.get("checks_run", {}).get("nonfinite_action_or_obs_count", 0) for v in rows.values()),
               "cmd_err_max": max([v.get("checks_run", {}).get("obs_single_cmd_vs_target_max_abs", 0) for v in rows.values()] or [0]),
               "uuids": sorted({v["devices"]["torch_cuda0_uuid"][:8] for v in rows.values() if "devices" in v})}
checks["pairing"] = pair
print("### 표 1 · 재현과 짝\n")
print("| 항목 | 결과 |")
print("|---|---|")
for k, v in rep.items():
    print(f"| 현재 코드로 {k} 재실행 · traj bitwise 같음 | {v['traj_bitwise_equal']} (종료 같음 {v['term_equal']}) |")
print(f"| 실행 묶음 (8 지형 + 띠) 별 root · 관절 · 질량 hash 종류 수 | {', '.join(str(v['old3_distinct']) for v in pair.values())} |")
print(f"| 넓힌 fingerprint 종류 수 (기록이 있는 실행끼리) | {', '.join(str(v['ext_distinct']) for v in pair.values())} |")
print(f"| 넓힌 fingerprint 가 있는 실행 수 / 전체 | {', '.join(str(len(v['ext_runs'])) + '/' + str(len(v['runs'])) for v in pair.values())} |")
print(f"| 지형 메시 hash 종류 수 · 설정 (checkpoint · noise 제외) 종류 수 | {', '.join(str(v['mesh_distinct']) for v in pair.values())} · {', '.join(str(v['args_distinct']) for v in pair.values())} |")
print(f"| 비유한 행동 · 관측 / 명령 칸 오차 최대 / GPU UUID | {sum(v['nonfinite'] for v in pair.values())} / {max(v['cmd_err_max'] for v in pair.values())} / {sorted({u for v in pair.values() for u in v['uuids']})} |")
print(f"| 끝낸 체크포인트 (noise 켬 · 끔) | {done['on']} · {done['off']} |")
print()

# ---- 3. summary per checkpoint ---------------------------------------------------------------------


def summary(it, nn, span=False):
    cen = [r for f in FAMS for r in eps(tag(it, nn, f)) if r["family"] == f]
    band = eps(tag(it, nn, "wave", True))
    sk = "span_survived" if span else "survived"
    out = {"surv": sum(tf(r[sk]) for r in cen) / len(cen)}
    mv = [r for r in cen if r["cell"] != "stop03"]
    out["q1"] = sum(tf(r[rule(r["cell"], span)]) for r in mv) / len(mv)
    st = [r for r in cen if r["cell"] == "stop03"]
    out["q2"] = sum(tf(r[rule("stop03", span)]) for r in st) / len(st)
    out["band_q2"] = sum(tf(r[rule("stop03", span)]) for r in band if r["cell"] == "stop03") / sum(1 for r in band if r["cell"] == "stop03")
    by = [r for r in band if r["cell"] in ("yawL05", "yawR05")]
    out["band_yaw"] = sum(tf(r[rule("yawL05", span)]) for r in by) / len(by)
    bs = [r for r in band if r["cell"] == "stand"]
    out["band_stand"] = sum(tf(r[rule("stand", span)]) for r in bs) / len(bs)
    out["falls"] = sum(not tf(r[sk]) for r in cen) + sum(not tf(r[sk]) for r in band)
    return out


print("### 표 2 · 체크포인트별 요약 (% · 현행 정의, 괄호는 제안 span 정의)\n")
print("| noise | 체크포인트 | 생존 (중앙 8) | 정지 밖 Q1 (중앙) | 정지 Q2 (중앙 8) | 띠 정지 Q2 (7) | 띠 회전 Q1 (7 × 2) | 띠 stand Q1 | 낙상 수 (중앙 + 띠) |")
print("|---|---|---|---|---|---|---|---|---|")
summ = {}
for nn, its in (("on", done["on"]), ("off", done["off"])):
    for it in its:
        a, b = summary(it, nn), summary(it, nn, True)
        summ[f"{it}/{nn}"] = {"current": a, "span": b}
        print(f"| {'켬' if nn == 'on' else '끔'} | {it} | {p0(a['surv'])} ({p0(b['surv'])}) | {p0(a['q1'])} ({p0(b['q1'])}) | {p0(a['q2'])} ({p0(b['q2'])}) | "
              f"{p0(a['band_q2'])} ({p0(b['band_q2'])}) | {p0(a['band_yaw'])} ({p0(b['band_yaw'])}) | {p0(a['band_stand'])} ({p0(b['band_stand'])}) | {a['falls']} ({b['falls']}) |")
print()

# ---- 4. capability curves (centre 8 terrains pooled unless noted) ------------------------------------
print("### 표 3 · 능력별 곡선 · noise 켬 · 통과 % (현행, 괄호는 제안 span · fwd01 · fwd02 는 제안 span + (a))\n")
caps = [("stand · 중앙 8", FAMS, False, "stand"), ("stop03 · 중앙 8", FAMS, False, "stop03"), ("stop03 · 평지", ["flat"], False, "stop03"),
        ("stop03 · 띠 7", ROUGH, True, "stop03"), ("stand · 띠 7", ROUGH, True, "stand"),
        ("fwd01 · 중앙 8", FAMS, False, "fwd01"), ("fwd02 · 중앙 8", FAMS, False, "fwd02"), ("fwd03 · 중앙 8", FAMS, False, "fwd03"),
        ("fwd05 · 중앙 8", FAMS, False, "fwd05"), ("back03 · 중앙 8", FAMS, False, "back03"),
        ("back03 · stairs_up", ["stairs_up"], False, "back03"), ("back03 · stairs_down", ["stairs_down"], False, "back03"),
        ("left03 · right03 · 중앙 8", FAMS, False, "lr"), ("yawL05 · yawR05 · 중앙 8", FAMS, False, "yaw"),
        ("yaw · 띠 7", ROUGH, True, "yaw"), ("obstacles 이동 6 cell", ["obstacles"], False, "move6")]
print("| 능력 | " + " | ".join(done["on"]) + " |")
print("|---|" + "---|" * len(done["on"]))
curves = {}
for name, fams, band, cell in caps:
    cl = {"lr": ["left03", "right03"], "yaw": ["yawL05", "yawR05"], "move6": ["fwd03", "fwd05", "back03", "left03", "right03", "yawL05"]}.get(cell, [cell])
    row = []
    for it in done["on"]:
        rr = [r for f in fams for r in eps(tag(it, "on", f, band)) if r["family"] == f and r["cell"] in cl]
        cur = sum(tf(r[rule(r["cell"])]) for r in rr) / len(rr)
        prop = sum(tf(r[rule(r["cell"], True, True)]) for r in rr) / len(rr)
        row.append(f"{p0(cur)} ({p0(prop)})")
        curves.setdefault(name, {})[it] = [cur, prop, len(rr)]
    print(f"| {name} | " + " | ".join(row) + " |")
print()
print("### 표 4 · noise 끔 · 같은 능력 (19500 · 20000 · 20499)\n")
print("| 능력 | " + " | ".join(done["off"]) + " |")
print("|---|" + "---|" * len(done["off"]))
for name, fams, band, cell in caps:
    cl = {"lr": ["left03", "right03"], "yaw": ["yawL05", "yawR05"], "move6": ["fwd03", "fwd05", "back03", "left03", "right03", "yawL05"]}.get(cell, [cell])
    row = []
    for it in done["off"]:
        rr = [r for f in fams for r in eps(tag(it, "off", f, band)) if r["family"] == f and r["cell"] in cl]
        row.append(f"{p0(sum(tf(r[rule(r['cell'])]) for r in rr) / len(rr))} ({p0(sum(tf(r[rule(r['cell'], True, True)]) for r in rr) / len(rr))})")
    print(f"| {name} | " + " | ".join(row) + " |")
print()

# ---- 5. paired McNemar between checkpoints -------------------------------------------------------------


def paired(ita, itb, nn, span=False):
    res = []
    for fam, band, cell in units():
        ga, gb = group(tag(ita, nn, fam, band), fam, cell), group(tag(itb, nn, fam, band), fam, cell)
        k = rule(cell, span)
        b_ = sum(tf(ga[e][k]) and not tf(gb[e][k]) for e in ga)
        c_ = sum((not tf(ga[e][k])) and tf(gb[e][k]) for e in ga)
        res.append((Q.mcnemar_exact(b_, c_), b_, c_, f"{fam}{'·띠' if band else ''}/{cell}", rate(ga, k), rate(gb, k)))
    rej = Q.holm_reject([x[0] for x in res])
    return res, rej


print("### 표 5 · 짝 McNemar (검정 116 개 = 중앙 88 + 띠 28 · Holm α 0.05 · 앞 → 뒤)\n")
print("| noise | 정의 | 비교 | 보정 전 하락 · 상승 | Holm 뒤 하락 · 상승 | Holm 뒤 유의 cell (앞 → 뒤 %) |")
print("|---|---|---|---|---|---|")
pairs_out = []
comps = [("19500", "20000"), ("20000", "20499"), ("19500", "20499"), ("15000", "19500"), ("10000", "15000"), ("5000", "10000")]
for nn, its in (("on", done["on"]), ("off", done["off"])):
    for ita, itb in comps:
        if ita not in its or itb not in its:
            continue
        for span in (False, True):
            res, rej = paired(ita, itb, nn, span)
            down = [x for x in res if x[0] < 0.05 and x[1] > x[2]]
            up = [x for x in res if x[0] < 0.05 and x[2] > x[1]]
            hd = [x for x, r in zip(res, rej) if r and x[1] > x[2]]
            hu = [x for x, r in zip(res, rej) if r and x[2] > x[1]]
            pairs_out.append(dict(noise=nn, span=span, a=ita, b=itb, down=[x[3] for x in down], up=[x[3] for x in up],
                                  holm_down=[(x[3], x[4], x[5], x[0]) for x in hd], holm_up=[(x[3], x[4], x[5], x[0]) for x in hu]))
            names = ", ".join([f"{x[3]} {p0(x[4])}→{p0(x[5])}" for x in hd + hu]) or "없음"
            print(f"| {'켬' if nn == 'on' else '끔'} | {'제안' if span else '현행'} | {ita} → {itb} | {len(down)} · {len(up)} | {len(hd)} · {len(hu)} | {names} |")
print()

# ---- 6. full per-cell table (noise on) --------------------------------------------------------------------
print("### 표 6 · cell 별 통과 % · noise 켬 (현행 · 괄호는 제안 span, fwd01 · fwd02 는 span + (a))\n")
print("| 지형 · 출발 | cell | " + " | ".join(done["on"]) + " |")
print("|---|---|" + "---|" * len(done["on"]))
rows_csv = []
for fam, band, cell in units():
    vals = []
    for it in done["on"]:
        g = group(tag(it, "on", fam, band), fam, cell)
        cur, prop = rate(g, rule(cell)), rate(g, rule(cell, True, True))
        vals.append(f"{p0(cur)} ({p0(prop)})")
        rows_csv.append(dict(noise="on", checkpoint=it, family=fam, start="band" if band else "centre", cell=cell,
                             n=len(g), survival=rate(g, "survived"), pass_current=cur, pass_proposed=prop))
    print(f"| {fam} · {'띠' if band else '중앙'} | {cell} | " + " | ".join(vals) + " |")
for it in done["off"]:
    for fam, band, cell in units():
        g = group(tag(it, "off", fam, band), fam, cell)
        rows_csv.append(dict(noise="off", checkpoint=it, family=fam, start="band" if band else "centre", cell=cell,
                             n=len(g), survival=rate(g, "survived"), pass_current=rate(g, rule(cell)), pass_proposed=rate(g, rule(cell, True, True))))
print()
with open(os.path.join(OUT, "QC-E2-cells.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys()))
    w.writeheader()
    for r in rows_csv:
        w.writerow(r)
checks.update(summary=summ, curves=curves, pairs=pairs_out)
json.dump(checks, open(os.path.join(OUT, "QC-E2-checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
