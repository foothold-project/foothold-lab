# CMD-R morning tables v2 (lead, 2026-10-13 00:20; rules from VERIFY-astra-7 2(c) and VERIFY-astra-8 section 5).
# Reads only runs the driver marked "valid" in out/cmdr_eval_driver.json (validated, stamped with the current pins,
# initial-state fingerprints equal within the group). Writes out/cmdr_post.json and out/CMDR-tables.md.
#   main pass (span time definition, ASTRA 7 proposal):  stop03 -> span_q2_pass,  fwd01 / fwd02 -> span_q1a_pass
#               (commanded-axis MAE <= min(0.15, 0.5 x command)),  other cells -> span_q1_pass.
#               n50 columns (q2_pass / q1a_pass / q1_pass) are kept as reference.
#   startup   : from traj.npz, states 1..50 (0 to 1 s) before the first invalid state (q_metrics.fall_index, span):
#               planar tracking error integral [m], yaw-rate error integral [rad], max yaw-rate error, base-contact
#               termination in the first second, 5 s survival, progress along the command at 5 s [m].
#               Failed episodes stay in: their counts are reported, integrals cover the valid part only.
#   paired    : episode i of seed s against episode i of seed s. on - off at the same update and branch - parent.
#               Newcombe method 10 interval, exact McNemar p (q_metrics). Holm over the three targets per update.
#   lines     : +10 pp on the target mean, -5 pp regression bound on the interval, MAE +10 % are the ASTRA 7 PROPOSAL
#               (team lead: "권고" confirmed 10/12; 2(c) is labelled 제안 and not yet confirmed). Shown, never adopted.
# Usage: python cmdr_post.py    (CMDR_POST_OUT=<folder> for tests)
import csv
import json
import os
from collections import defaultdict

import numpy as np

import q_metrics as Q

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("CMDR_POST_OUT", os.path.join(HERE, "out"))  # test: point at a synthetic folder
MODELS = ["p20000", "off22000", "on22000", "off24000", "on24000"]
CELLS = ["stop03", "fwd01", "fwd02", "stand", "fwd03", "fwd05", "back03", "left03", "right03", "yawL05", "yawR05"]
TARGETS = ["stop03", "fwd01", "fwd02"]
FAMILIES = ["flat", "obstacles", "rough_slope", "slope_up", "slope_down", "stairs_up", "stairs_down", "wave"]
SEEDS = [1000, 1001, 1002, 1003, 1004]


def main_col(cell):
    return "span_q2_pass" if cell == "stop03" else ("span_q1a_pass" if cell in ("fwd01", "fwd02") else "span_q1_pass")


def ref_col(cell):
    return "q2_pass" if cell == "stop03" else ("q1a_pass" if cell in ("fwd01", "fwd02") else "q1_pass")


def startup(d):
    z = np.load(os.path.join(d, "traj.npz"))
    traj, term = z["traj"].astype(np.float64), z["term"]
    cmd = z["cmd_hist"].astype(np.float64)
    out = []
    for e in range(traj.shape[1]):
        tr, c = traj[:, e], cmd[:, e]
        jf, _ = Q.fall_index(term[:, e], tr[:, 10], tr[:, 11], Q.DT, "span")
        jl = min(50, jf - 1)
        js = np.arange(1, jl + 1)
        lin = np.abs(tr[js, 4] - c[js, 0]) + np.abs(tr[js, 5] - c[js, 1])
        yaw = np.abs(tr[js, 9] - c[js, 2])
        j5 = 250
        prog = float("nan")
        if jf > j5 and np.linalg.norm(c[1, :2]) > 0:
            y0 = tr[0, 3]
            v = c[1, :2] / np.linalg.norm(c[1, :2])
            dw = np.array([np.cos(y0) * v[0] - np.sin(y0) * v[1], np.sin(y0) * v[0] + np.cos(y0) * v[1]])
            prog = float((tr[j5, :2] - tr[0, :2]) @ dw)
        out.append({"lin_err_int_m": float(lin.sum() * Q.DT), "yaw_err_int_rad": float(yaw.sum() * Q.DT),
                    "yaw_err_max": float(yaw.max()) if len(js) else float("nan"),
                    "contact_1s": bool(term[1:51, e].any()), "survive_5s": bool(jf > j5), "progress_5s_m": prog,
                    "valid_steps_1s": int(len(js))})
    return out


def load(tag):
    d = os.path.join(OUT, tag)
    eps = sorted(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")), key=lambda r: int(r["episode"]))
    cell = eps[0]["cell"]
    st = startup(d)
    return {"cell": cell, "main": [r[main_col(cell)] == "True" for r in eps], "ref": [r[ref_col(cell)] == "True" for r in eps],
            "surv": [r["span_survived"] == "True" for r in eps],
            "mae": {k: float(np.nanmean([float(r[f"mae_{k}"]) for r in eps])) for k in ("vx", "vy", "wz")}, "startup": st}


drv = json.load(open(os.path.join(OUT, "cmdr_eval_driver.json"), encoding="utf-8")) if os.path.exists(
    os.path.join(OUT, "cmdr_eval_driver.json")) else {"matrix": {}}
valid = sorted(t for t, s in drv.get("matrix", {}).items() if s == "valid")
R = {}
for tag in valid:
    _, m, rest = tag.split("_", 2)
    rest, seed = rest.rsplit("_s", 1)
    rest, noise = rest.rsplit("_", 1)
    fam, cell = rest.rsplit("_", 1)
    R[(m, fam, cell, noise, int(seed))] = load(tag)


def paired(xs, ys):
    """xs, ys: lists of per-episode booleans, same keys in the same order. Returns y - x."""
    a = sum(x and y for x, y in zip(xs, ys))
    b = sum((not x) and y for x, y in zip(xs, ys))
    c = sum(x and (not y) for x, y in zip(xs, ys))
    d = sum((not x) and (not y) for x, y in zip(xs, ys))
    diff, lo, hi = Q.newcombe_paired(a, b, c, d)  # a both, b y only, c x only, d neither -> y - x
    return {"n": a + b + c + d, "diff": diff, "lo": lo, "hi": hi, "p": Q.mcnemar_exact(b, c), "b_y_only": b, "c_x_only": c}


def pooled(m, fam, cell, noise, seeds):
    have = [s for s in seeds if (m, fam, cell, noise, s) in R]
    return have, sum((R[(m, fam, cell, noise, s)]["main"] for s in have), [])


def compare(mx, my, fam, cell, noise, seeds):
    sx, _ = pooled(mx, fam, cell, noise, seeds)
    sy, _ = pooled(my, fam, cell, noise, seeds)
    common = [s for s in sx if s in sy]
    if not common:
        return None
    xs = sum((R[(mx, fam, cell, noise, s)]["main"] for s in common), [])
    ys = sum((R[(my, fam, cell, noise, s)]["main"] for s in common), [])
    r = paired(xs, ys)
    r["seeds"] = common
    r["mae_change"] = {k: (np.mean([R[(my, fam, cell, noise, s)]["mae"][k] for s in common]) /
                           max(1e-9, np.mean([R[(mx, fam, cell, noise, s)]["mae"][k] for s in common])) - 1.0) for k in ("vx", "vy", "wz")}
    return r


res = {"targets": {}, "startup": {}, "cells": [], "holm": {}, "completion": {}, "proposal_lines": {}}
for cell in TARGETS:
    row = {}
    for m in MODELS:
        have, xs = pooled(m, "flat", cell, "on", SEEDS)
        if have:
            row[m] = {"seeds": have, "n": len(xs), "rate": sum(xs) / len(xs), "ci": Q.wilson(sum(xs), len(xs)),
                      "per_seed": {s: float(np.mean(R[(m, "flat", cell, "on", s)]["main"])) for s in have},
                      "ref_rate_s1000": float(np.mean(R[(m, "flat", cell, "on", 1000)]["ref"])) if 1000 in have else None}
            st = sum((R[(m, "flat", cell, "on", s)]["startup"] for s in have), [])
            res["startup"].setdefault(cell, {})[m] = {
                "n": len(st), "contact_1s": sum(x["contact_1s"] for x in st), "survive_5s": sum(x["survive_5s"] for x in st),
                "lin_err_int_m_mean": float(np.mean([x["lin_err_int_m"] for x in st])),
                "yaw_err_int_rad_mean": float(np.mean([x["yaw_err_int_rad"] for x in st])),
                "yaw_err_max_p90": float(np.percentile([x["yaw_err_max"] for x in st if x["valid_steps_1s"]], 90)),
                "progress_5s_m_mean": float(np.nanmean([x["progress_5s_m"] for x in st])) if any(
                    not np.isnan(x["progress_5s_m"]) for x in st) else None}
    for u in ("22000", "24000"):
        r = compare(f"off{u}", f"on{u}", "flat", cell, "on", SEEDS)
        if r:
            row[f"on_minus_off_{u}"] = r
        for arm in ("off", "on"):
            r = compare("p20000", f"{arm}{u}", "flat", cell, "on", SEEDS)
            if r:
                row[f"{arm}{u}_minus_parent"] = r
    res["targets"][cell] = row
for u in ("22000", "24000"):
    ps = [res["targets"][c].get(f"on_minus_off_{u}", {}).get("p") for c in TARGETS]
    seeds = [tuple(res["targets"][c].get(f"on_minus_off_{u}", {}).get("seeds", [])) for c in TARGETS]
    if all(p is not None for p in ps):
        res["holm"][u] = {"rejected": dict(zip(TARGETS, Q.holm_reject(ps))), "seeds": [list(s) for s in seeds]}
        diffs = [res["targets"][c][f"on_minus_off_{u}"]["diff"] for c in TARGETS]
        res["proposal_lines"][u] = {"target_mean_diff_pp": 100 * float(np.mean(diffs)), "meets_plus10": bool(np.mean(diffs) >= 0.10)}
for fam in FAMILIES:
    for cell in CELLS:
        for noise in ("on", "off"):
            row = {"family": fam, "cell": cell, "noise": noise}
            for m in MODELS:
                k = (m, fam, cell, noise, 1000)
                if k in R:
                    row[m] = {"rate": float(np.mean(R[k]["main"])), "ref": float(np.mean(R[k]["ref"])),
                              "surv": float(np.mean(R[k]["surv"])), "mae": R[k]["mae"]}
            for u in ("22000", "24000"):
                r = compare(f"off{u}", f"on{u}", fam, cell, noise, [1000])
                if r:
                    r["regression_bound_crossed"] = bool(r["lo"] < -0.05)
                    r["mae_over_10pct"] = bool(any(v > 0.10 for v in r["mae_change"].values()))
                    row[f"on_minus_off_{u}"] = r
            if any(m in row for m in MODELS):
                res["cells"].append(row)
for m in MODELS:
    for fam in FAMILIES:
        res["completion"][f"{m}/{fam}"] = sum((m, fam, c, "on", 1000) in R for c in CELLS)
res["n_valid_runs"] = len(R)
res["driver_pair_fail"] = drv.get("pair_fail", [])
res["driver_invalid"] = drv.get("skipped", [])
json.dump(res, open(os.path.join(OUT, "cmdr_post.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


def pct(v):
    return "" if v is None else f"{100 * v:.0f}"


def dfmt(p):
    return "" if not p else f"{100 * p['diff']:+.0f} [{100 * p['lo']:+.0f}, {100 * p['hi']:+.0f}] p={p['p']:.2g}"


L = ["# CMD-R 아침 표 (자동 생성 · cmdr_post.py v2)", "",
     "주 통과 = span 정의 (stop03 span_q2 · fwd01/02 span_q1a · 그 밖 span_q1). 차이는 같은 시드 · 같은 episode 끼리 짝지은 %p 와 95 % 구간.",
     "판정선 (목표 평균 +10 %p · 구간 하한 −5 %p · MAE +10 %) 은 ASTRA 7 의 제안이며 팀장 확정 전이다. 이 표는 채택 · 기각을 쓰지 않는다.", "",
     "## 목표 세 칸 (평지 · noise 켬 · 시드 묶음)", "",
     "| 칸 | 부모 20000 | off 22000 | on 22000 | off 24000 | on 24000 | on−off 22000 | on−off 24000 |", "|---|---|---|---|---|---|---|---|"]
for c in TARGETS:
    r = res["targets"][c]
    L.append(f"| {c} | " + " | ".join(f"{pct(r[m]['rate'])} (n {r[m]['n']})" if m in r else "" for m in MODELS)
             + f" | {dfmt(r.get('on_minus_off_22000'))} | {dfmt(r.get('on_minus_off_24000'))} |")
L += ["", f"Holm (on−off, 목표 셋): {json.dumps(res['holm'], ensure_ascii=False)}",
      f"제안선 비교 (채택 아님): {json.dumps(res['proposal_lines'], ensure_ascii=False)}", "",
      "## 시작 직후 (0~1 s) · 5 s", "", "| 칸 | 모델 | n | 1 s 안 몸통 접촉 | 5 s 생존 | 평면 오차 적분 m | yaw 오차 적분 rad | 5 s 진행 m |",
      "|---|---|---|---|---|---|---|---|"]
for c, d in res["startup"].items():
    for m, s in d.items():
        L.append(f"| {c} | {m} | {s['n']} | {s['contact_1s']} | {s['survive_5s']} | {s['lin_err_int_m_mean']:.3f} | "
                 f"{s['yaw_err_int_rad_mean']:.3f} | {'' if s['progress_5s_m_mean'] is None else round(s['progress_5s_m_mean'], 2)} |")
L += ["", "## 모든 칸 (시드 1000)", "", "| 지형 | 칸 | noise | 부모 | off 22000 | on 22000 | off 24000 | on 24000 | on−off 24000 |", "|---|---|---|---|---|---|---|---|---|"]
for r in res["cells"]:
    L.append(f"| {r['family']} | {r['cell']} | {r['noise']} | " + " | ".join(pct(r[m]["rate"]) if m in r else "" for m in MODELS)
             + f" | {dfmt(r.get('on_minus_off_24000'))} |")
L += ["", "## 채워진 칸 수 (noise 켬 · 시드 1000 · 지형마다 11 칸)", "", "| 모델 | " + " | ".join(FAMILIES) + " |", "|---|" + "---|" * len(FAMILIES)]
for m in MODELS:
    L.append(f"| {m} | " + " | ".join(str(res["completion"][f"{m}/{f}"]) for f in FAMILIES) + " |")
L += ["", f"유효 실행 {res['n_valid_runs']} · 짝 불일치 {len(res['driver_pair_fail'])} · 무효 {len(res['driver_invalid'])}"]
open(os.path.join(OUT, "CMDR-tables.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"valid runs {len(R)} · targets {[c for c in TARGETS if res['targets'][c]]} · holm {res['holm']}")
