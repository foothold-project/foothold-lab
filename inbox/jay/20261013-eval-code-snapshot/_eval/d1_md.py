# D1 tables from raw outputs: student (Q-E1 runs m<it>_*), teacher normal (t<it>_*),
# teacher with the frozen height permutation (tp<it>_*). Usage: python d1_md.py > out/D1-E1-tables.md
# Also writes out/D1-E1-cells.csv and out/D1-E1-checks.json.

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
COND = {"S": "m", "T": "t", "Tp": "tp"}


def tf(v):
    return str(v) in ("True", "true", "1")


def fl(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


_cache = {}


def eps(tag):
    if tag not in _cache:
        p = os.path.join(OUT, tag, "episodes.csv")
        _cache[tag] = list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else None
    return _cache[tag]


def meta(tag):
    p = os.path.join(OUT, tag, "meta.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def tag(cond, it, fam):
    return f"{COND[cond]}{it}_{fam}"


def rows_of(cond, it, fam, cell, off=False):
    e = eps(tag(cond, it, "offplat" if off else fam))
    if e is None:
        return None
    return {int(r["episode"]): r for r in e if r["family"] == fam and r["cell"] == cell}


def rule(cell):
    return "q2_pass" if cell == "stop03" else "q1_pass"


def paired(A, B, key):
    a = sum(tf(A[k][key]) and tf(B[k][key]) for k in A)
    b = sum(tf(A[k][key]) and not tf(B[k][key]) for k in A)
    c = sum((not tf(A[k][key])) and tf(B[k][key]) for k in A)
    d = len(A) - a - b - c
    diff, lo, hi = Q.newcombe_paired(a, b, c, d)
    return dict(n=len(A), a=a, b=b, c=c, d=d, diff=diff, lo=lo, hi=hi, p=Q.mcnemar_exact(b, c))


def p0(x):
    return "-" if x is None or not np.isfinite(x) else f"{100 * x:.0f}"


def pv(p):
    return f"{p:.2g}" if p < 0.1 else f"{p:.2f}"


# ---- pairing and pre-checks ---------------------------------------------------------
DEF = {"spawn_offset": "", "heading_hold": 0.0}
checks = {"pairing": {}, "pre": {}}
for it in ITS:
    for fam in FAMS + ["offplat"]:
        ms, mt, mp = meta(f"m{it}_{fam}"), meta(f"t{it}_{fam}"), meta(f"tp{it}_{fam}")
        if not (ms and mt and mp):
            checks["pairing"][f"{it}/{fam}"] = "missing"
            continue
        checks["pairing"][f"{it}/{fam}"] = {
            "init_and_dr_equal_S_T_Tp": ms["pairing_sha256"] == mt["pairing_sha256"] == mp["pairing_sha256"],
            "mesh_equal_S_T_Tp": ms["terrain_mesh"] == mt["terrain_mesh"] == mp["terrain_mesh"],
            "ckpt_equal": ms["checkpoint_sha256"] == mt["checkpoint_sha256"] == mp["checkpoint_sha256"],
            # Q-E1 main runs used q_eval_batch1.py, which had no --spawn_offset / --heading_hold option;
            # an absent key equals the option's default ('' = no offset, 0.0 = off)
            "args_equal_except_policy_perm": all(
                ms["args"].get(k, DEF.get(k)) == mt["args"].get(k, DEF.get(k)) == mp["args"].get(k, DEF.get(k))
                for k in ("families", "cells", "episodes", "difficulty", "eval_seed", "obs_noise", "spawn_offset",
                          "heading_hold")),
            "perm_sha256": mp.get("height_perm", {}).get("sha256"),
            "perm_fixed_points": mp.get("height_perm", {}).get("fixed_points"),
            "devices_T": mt["devices"]["torch_cuda0_uuid"], "devices_Tp": mp["devices"]["torch_cuda0_uuid"],
        }
for it in ITS:
    for fam in FAMS + ["offplat"]:
        for c in ("T", "Tp"):
            m = meta(f"{COND[c]}{it}_{fam}")
            if m:
                checks["pre"][f"{c}{it}/{fam}"] = m["checks_pre"]
json.dump(checks, open(os.path.join(OUT, "D1-E1-checks.json"), "w", encoding="utf-8"), indent=1)

pre = checks["pre"]
print("### 표 1 · 사전 점검 (각 실행 첫 관측 · 모든 D1 실행)\n")
print("| 점검 | 기대 | 결과 (실행 수) |")
print("|---|---|---|")


def agg(key):
    v = [x[key] for x in pre.values() if key in x]
    return v


for key, want in (("student_height_permuted_max_abs_action_change", "≤ 1e-6"),
                  ("teacher_manual_vs_module_act_mean_max_abs", "0"),
                  ("teacher_identity_perm_vs_normal_max_abs", "0"),
                  ("height_block_vs_raycaster_recomputed_max_abs", "0"),
                  ("non_height_critic_unchanged_max_abs", "0")):
    v = agg(key)
    print(f"| `{key}` | {want} | " + (f"최대 {max(v):.3g} ({len(v)})" if v else "-") + " |")
for key in ("height_block_values_same_multiset", "critic_dims_sum_equals_width"):
    v = agg(key)
    print(f"| `{key}` | 참 | {sum(bool(x) for x in v)} / {len(v)} 참 |")
pv_ = [x["perm_sha256"] for x in checks["pairing"].values() if isinstance(x, dict)]
print(f"| permutation (시드 2026) | 모든 실행이 같은 순열 | sha256 {len(set(pv_))} 종류 · {pv_[0][:16] if pv_ else '-'} |")
pp = [x for x in checks["pairing"].values() if isinstance(x, dict)]
print(f"| 짝 (student · teacher · teacher perm 의 초기 root 자세 · 관절각 · 질량 · 메시 · 체크포인트 · 설정. 넓힌 DR 은 1절) | 같음 | "
      f"{sum(x['init_and_dr_equal_S_T_Tp'] and x['mesh_equal_S_T_Tp'] and x['ckpt_equal'] and x['args_equal_except_policy_perm'] for x in pp)} / {len(pp)} 같음 |")
print()
print("### 표 2 · 양성 대조 · 첫 관측에서 height 순열이 teacher 행동을 바꾸는 양 (최대 절대 차)\n")
print("| 지형 | 20000 | 20499 |")
print("|---|---|---|")
for fam in FAMS + ["offplat"]:
    vals = []
    for it in ITS:
        x = pre.get(f"T{it}/{fam}", {}).get("teacher_height_permuted_max_abs_action_change")
        vals.append("-" if x is None else f"{x:.3g}")
    print(f"| {fam} | " + " | ".join(vals) + " |")
print()

# ---- per terrain pooled -------------------------------------------------------------
csv_rows = []
for it in ITS:
    print(f"### 표 3 ({it}) · 지형별 합계 · Q 통과 % (S = student · T = teacher · Tp = teacher height 순열)\n")
    print("| 지형 · 출발 | episodes | S | T | Tp | T − Tp [95% 구간] · p | T − S [95% 구간] · p | Tp 에서 10 pp 이상 하락 |")
    print("|---|---|---|---|---|---|---|---|")
    for fam, off, cl in [(f, False, CELLS) for f in FAMS] + [(f, True, OFFC) for f in ROUGH]:
        A = {}
        for cond in ("S", "T", "Tp"):
            A[cond] = {}
            for cell in cl:
                r = rows_of(cond, it, fam, cell, off)
                if r is None:
                    A[cond] = None
                    break
                for k, v in r.items():
                    vv = dict(v)
                    vv["pass_rule"] = vv[rule(cell)]
                    A[cond][(cell, k)] = vv
            if A[cond] is None:
                break
        if any(A[c] is None for c in ("S", "T", "Tp")):
            continue
        tp = paired(A["T"], A["Tp"], "pass_rule")
        ts = paired(A["T"], A["S"], "pass_rule")
        n = tp["n"]
        rs = {c: sum(tf(v["pass_rule"]) for v in A[c].values()) / n for c in A}
        flag = "예" if tp["diff"] >= 0.10 else "아니오"
        lab = f"{fam} · {'띠 출발 (제자리 4 cell)' if off else '중앙'}"
        print(f"| {lab} | {n} | {p0(rs['S'])} | {p0(rs['T'])} | {p0(rs['Tp'])} | "
              f"{tp['diff'] * 100:+.1f} [{tp['lo'] * 100:+.1f}, {tp['hi'] * 100:+.1f}] · {pv(tp['p'])} | "
              f"{ts['diff'] * 100:+.1f} [{ts['lo'] * 100:+.1f}, {ts['hi'] * 100:+.1f}] · {pv(ts['p'])} | {flag} |")
    print()

# ---- per cell -------------------------------------------------------------------------
for it in ITS:
    print(f"### 표 4 ({it}) · cell 별 Q 통과 % · S / T / Tp (`!` 는 T − Tp ≥ 10 pp 이고 McNemar p < 0.05)\n")
    print("| cell | " + " | ".join(FAMS) + " |")
    print("|---|" + "---|" * len(FAMS))
    for cell in CELLS:
        row = [cell]
        for fam in FAMS:
            R = {c: rows_of(c, it, fam, cell) for c in ("S", "T", "Tp")}
            if any(R[c] is None for c in R):
                row.append("-")
                continue
            key = rule(cell)
            rate = {c: sum(tf(v[key]) for v in R[c].values()) / len(R[c]) for c in R}
            tp = paired(R["T"], R["Tp"], key)
            mark = "!" if (tp["diff"] >= 0.10 and tp["p"] < 0.05) else ""
            row.append(f"{p0(rate['S'])} / {p0(rate['T'])} / {p0(rate['Tp'])}{mark}")
            csv_rows.append({"it": it, "family": fam, "start": "centre", "cell": cell, "n": len(R["T"]),
                             "S_pass": rate["S"], "T_pass": rate["T"], "Tp_pass": rate["Tp"],
                             "T_minus_Tp": tp["diff"], "T_minus_Tp_lo": tp["lo"], "T_minus_Tp_hi": tp["hi"],
                             "T_vs_Tp_mcnemar_p": tp["p"],
                             **{f"{c}_survival": sum(tf(v["survived"]) for v in R[c].values()) / len(R[c]) for c in R},
                             **{f"{c}_mae_{a}": float(np.nanmean([fl(v[f'mae_{a}']) for v in R[c].values()]))
                                for c in R for a in ("vx", "vy", "wz")},
                             **{f"{c}_q1m": sum(tf(v["q1m_pass"]) for v in R[c].values()) / len(R[c]) for c in R}})
        print("| " + " | ".join(row) + " |")
    print()
    print(f"띠 출발 ({it}) · S / T / Tp\n")
    print("| cell | " + " | ".join(ROUGH) + " |")
    print("|---|" + "---|" * len(ROUGH))
    for cell in OFFC:
        row = [cell]
        for fam in ROUGH:
            R = {c: rows_of(c, it, fam, cell, True) for c in ("S", "T", "Tp")}
            if any(R[c] is None or not R[c] for c in R):
                row.append("-")
                continue
            key = rule(cell)
            rate = {c: sum(tf(v[key]) for v in R[c].values()) / len(R[c]) for c in R}
            tp = paired(R["T"], R["Tp"], key)
            mark = "!" if (tp["diff"] >= 0.10 and tp["p"] < 0.05) else ""
            row.append(f"{p0(rate['S'])} / {p0(rate['T'])} / {p0(rate['Tp'])}{mark}")
            csv_rows.append({"it": it, "family": fam, "start": "band", "cell": cell, "n": len(R["T"]),
                             "S_pass": rate["S"], "T_pass": rate["T"], "Tp_pass": rate["Tp"],
                             "T_minus_Tp": tp["diff"], "T_minus_Tp_lo": tp["lo"], "T_minus_Tp_hi": tp["hi"],
                             "T_vs_Tp_mcnemar_p": tp["p"],
                             **{f"{c}_survival": sum(tf(v["survived"]) for v in R[c].values()) / len(R[c]) for c in R},
                             **{f"{c}_mae_{a}": float(np.nanmean([fl(v[f'mae_{a}']) for v in R[c].values()]))
                                for c in R for a in ("vx", "vy", "wz")},
                             **{f"{c}_q1m": sum(tf(v["q1m_pass"]) for v in R[c].values()) / len(R[c]) for c in R}})
        print("| " + " | ".join(row) + " |")
    print()

if csv_rows:
    with open(os.path.join(OUT, "D1-E1-cells.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        w.writeheader()
        for r in csv_rows:
            w.writerow(r)

# ---- significant T vs Tp cells -------------------------------------------------------
print("### 표 5 · teacher 정상 대 height 순열 · McNemar p < 0.05 인 cell\n")
print("| 체크포인트 | 지형 · 출발 | cell | T % | Tp % | T − Tp [95% 구간] | p | 10 pp 이상 |")
print("|---|---|---|---|---|---|---|---|")
nsig = {"down": 0, "up": 0}
for r in csv_rows:
    if r["T_vs_Tp_mcnemar_p"] < 0.05:
        nsig["down" if r["T_minus_Tp"] > 0 else "up"] += 1
        print(f"| {r['it']} | {r['family']} · {'중앙' if r['start'] == 'centre' else '띠'} | {r['cell']} | {p0(r['T_pass'])} | "
              f"{p0(r['Tp_pass'])} | {r['T_minus_Tp'] * 100:+.1f} [{r['T_minus_Tp_lo'] * 100:+.1f}, {r['T_minus_Tp_hi'] * 100:+.1f}] | "
              f"{pv(r['T_vs_Tp_mcnemar_p'])} | {'예' if r['T_minus_Tp'] >= 0.10 else '아니오'} |")
print()
print(f"순열에서 나빠진 쪽 {nsig['down']} cell · 좋아진 쪽 {nsig['up']} cell (검정 {len(csv_rows)} 개 · 보정 없음)")
print()

# ---- falls and MAE by condition ----------------------------------------------------------
print("### 표 6 · 조건별 생존 · 낙상 · 이동 cell MAE (주 실행 8 지형 + 띠 출발 합계)\n")
print("| 체크포인트 | 조건 | episodes | 낙상 | base 접촉 | 기울기 60도 | MAE vx 평균 | MAE vy 평균 | MAE wz 평균 | 이동 보조 통과 % |")
print("|---|---|---|---|---|---|---|---|---|---|")
for it in ITS:
    for cond, name in (("S", "student"), ("T", "teacher"), ("Tp", "teacher 순열")):
        allr = []
        for fam in FAMS + ["offplat"]:
            e = eps(tag(cond, it, fam))
            if e:
                allr += e
        if not allr:
            continue
        falls = [r for r in allr if not tf(r["survived"])]
        mov = [r for r in allr if r["cell"] not in ("stand",)]
        m = {a: float(np.nanmean([fl(r[f"mae_{a}"]) for r in mov])) for a in ("vx", "vy", "wz")}
        q1m = sum(tf(r["q1m_pass"]) for r in mov) / len(mov)
        print(f"| {it} | {name} | {len(allr)} | {len(falls)} | {sum(r['fall_reason'] == 'base_contact' for r in falls)} | "
              f"{sum(r['fall_reason'] == 'tilt60' for r in falls)} | {m['vx']:.3f} | {m['vy']:.3f} | {m['wz']:.3f} | {100 * q1m:.0f} |")
print()
