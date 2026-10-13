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
# v3 (00:30, VERIFY-astra-8b 3): startup split into episodes that completed the first second and early failures
# (counts, valid time, integrals of each group); empty groups give None, not an error; 5 s progress carries its n.
# MAE regression: relative +10 % when the control MAE > 0, otherwise absolute 10 % of the Q tolerance
# (vx, vy 0.15 m/s -> 0.015; wz 0.20 rad/s -> 0.02), as VERIFY-astra-7 2(c).
# v4 (10/13 09:58): the 2(c) lines are no longer a proposal. Team lead 01:10 「제안 · 권고대로 진행」 (HANDOFF-night-20261013
# line 34): 500 episodes per target cell; 「개선」 = every one of the three cells has a 95 % interval low end > 0 AND the
# equal-weight mean of the three on - off differences is >= +10 pp (VERIFY-astra-7 2(c) line 60 · VERIFY-astra-15 6.1).
# Per-cell interval readings are description, not the judgment; Holm over the three is shown beside it. (An earlier
# lead note said 「per cell, no three-cell average」: that misquoted the rule and is withdrawn, 10/13 10:02.) Regression = n=100 screen at 24000, cells with a point estimate <= -5 pp are measured
# again at n=500 (seeds 1001-1004, cmdr_eval_driver_v33 --plan remeasure) and judged on the interval against -5 pp
# (crossing = 「비퇴행 미확인」); MAE +10 % flagged; the basic contract (survival >= 95 %, command pass >= 90 %) is judged
# separately per arm and cell. Reads the valid runs of both driver logs (base + GPU 0 remeasure). Nothing here writes
# 「채택」 or 「기각」: that needs every family measured and the team lead.
# v5 (10/13 10:36, VERIFY-astra-16 1 / 4 / 5 / 7):
#   - paired intervals: Tango score interval (paired_ci.py; exact coverage checked, test_paired_ci.py) instead of the
#     pinned q_metrics.newcombe_paired, which is zero-width without discordant pairs (ASTRA 16 7.2). The Newcombe pair
#     is kept beside it as "newcombe" for comparison with earlier published numbers.
#   - the joint target judgment is written only when all three targets have both arms on all five seeds (500 pairs
#     each); before that it says 「수집 중 · 결합 판정 보류」 with the seeds and pairs it has.
#   - regression rows carry three statuses: pass rate (interval against -5 pp; a screen cell that was not flagged is
#     「비퇴행」 only if its own n=100 interval clears -5 pp, otherwise 「비퇴행 미확인」), MAE (contract line +10 %,
#     missing when not finite) and overall. Flagged cells also show the four new seeds alone (independent of the
#     screen) and seed-by-seed differences. Planned 99 cells: the measured and unmeasured lists are written.
#   - basic contract: k / n and Wilson intervals for survival and pass per cell, planned vs measured cells.
#   - inputs: episode ids 0..99 per run, equal lengths when pairing, the two logs' pins and checkpoint hashes must
#     agree, a run whose stamp carries output hashes is used only if they still match; log file hashes and as_of are
#     written. Never writes 「채택」 or 「기각」.
# Usage: python cmdr_post_v5.py    (CMDR_POST_OUT=<folder> for tests)
import csv
import json
import os

import hashlib
import math
import time

import numpy as np

import paired_ci as PCI
import q_metrics as Q

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("CMDR_POST_OUT", os.path.join(HERE, "out"))  # test: point at a synthetic folder
DEST = os.environ.get("CMDR_POST_DEST", OUT)  # v4: tables can be written elsewhere (tests, dry runs)
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
    if [int(r["episode"]) for r in eps] != list(range(100)):
        raise ValueError(f"{tag}: episode ids are not 0..99")
    cell = eps[0]["cell"]
    st = startup(d)
    mae, mae_n = {}, {}
    for k in ("vx", "vy", "wz"):
        v = [float(r[f"mae_{k}"]) for r in eps]
        f = [x for x in v if math.isfinite(x)]
        mae[k], mae_n[k] = (float(np.mean(f)) if f else float("nan")), len(f)
    return {"cell": cell, "main": [r[main_col(cell)] == "True" for r in eps], "ref": [r[ref_col(cell)] == "True" for r in eps],
            "surv": [r["span_survived"] == "True" for r in eps], "mae": mae, "mae_n": mae_n, "startup": st}


def filehash(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


LOGS = ["cmdr_eval_driver", "cmdr_eval_driver_g0"]
drv = {"matrix": {}, "pair_fail": [], "skipped": [], "logs": {}}
for name in LOGS:
    p = os.path.join(OUT, f"{name}.json")
    if not os.path.exists(p):
        continue
    raw = open(p, "rb").read()
    d = json.loads(raw.decode("utf-8"))
    drv.setdefault("inputs", {})[name] = hashlib.sha256(raw).hexdigest()
    for k in ("pins", "ckpt"):
        for kk, vv in (d.get(k) or {}).items():
            vv = vv.get("sha256") if isinstance(vv, dict) else vv
            prev = drv.setdefault(k, {}).setdefault(kk, vv)
            assert prev == vv, f"{name}: {k} {kk} differs between the two logs"
    both = set(drv["matrix"]) & set(d.get("matrix", {}))
    assert not both, f"{name}: tags in two logs {sorted(both)[:3]}"  # the two instances never share a run
    drv["matrix"].update(d.get("matrix", {}))
    drv["pair_fail"] += d.get("pair_fail", [])
    drv["skipped"] += d.get("skipped", [])
    drv["logs"][name] = {"version": d.get("version", "3.2 or earlier"), "runs": len(d.get("runs", [])),
                         "ended": d.get("ended"), "stopped": d.get("stopped")}
valid = sorted(t for t, s in drv["matrix"].items() if s == "valid")
R = {}
changed = []
for tag in valid:
    st = os.path.join(OUT, tag, "driver_stamp.json")
    try:
        stp = json.load(open(st, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        stp = {}
    if isinstance(stp.get("out_sha256"), dict) and any(filehash(os.path.join(OUT, tag, f)) != h for f, h in stp["out_sha256"].items()):
        changed.append(tag)  # outputs changed after the driver validated them: not used
        continue
    _, m, rest = tag.split("_", 2)
    rest, seed = rest.rsplit("_s", 1)
    rest, noise = rest.rsplit("_", 1)
    fam, cell = rest.rsplit("_", 1)
    R[(m, fam, cell, noise, int(seed))] = load(tag)


def paired(xs, ys):
    """xs, ys: lists of per-episode booleans, same keys in the same order. Returns y - x (Tango score interval)."""
    if len(xs) != len(ys) or not xs:
        raise ValueError(f"pairing lengths {len(xs)} {len(ys)}")
    a = sum(x and y for x, y in zip(xs, ys))
    b = sum((not x) and y for x, y in zip(xs, ys))
    c = sum(x and (not y) for x, y in zip(xs, ys))
    d = sum((not x) and (not y) for x, y in zip(xs, ys))
    n = a + b + c + d
    diff, lo, hi = PCI.tango(b, c, n)  # b y only, c x only -> y - x
    _, nlo, nhi = Q.newcombe_paired(a, b, c, d)
    return {"n": n, "diff": diff, "lo": lo, "hi": hi, "method": "tango", "newcombe": [nlo, nhi], "p": Q.mcnemar_exact(b, c),
            "b_y_only": b, "c_x_only": c}


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
    r["per_seed"] = {s: (sum(R[(my, fam, cell, noise, s)]["main"]) - sum(R[(mx, fam, cell, noise, s)]["main"])) / 100 for s in common}
    r["mae"] = {}
    for k, tol in (("vx", 0.15), ("vy", 0.15), ("wz", 0.20)):
        xv = [R[(mx, fam, cell, noise, s)]["mae"][k] for s in common]
        yv = [R[(my, fam, cell, noise, s)]["mae"][k] for s in common]
        if not all(math.isfinite(v) for v in xv + yv):
            r["mae"][k] = {"x": None, "y": None, "missing": True, "worse_than_line": False}
            continue
        x, y = float(np.mean(xv)), float(np.mean(yv))
        worse = (y / x - 1.0 > 0.10) if x > 0 else (y - x > 0.1 * tol)
        r["mae"][k] = {"x": x, "y": y, "rel": (y / x - 1.0) if x > 0 else None, "abs": y - x, "worse_than_line": bool(worse),
                       "missing": False, "n_finite": [sum(R[(m_, fam, cell, noise, s)]["mae_n"][k] for s in common) for m_ in (mx, my)]}
    return r


def mae_status(p):
    over = sorted(k for k, v in p["mae"].items() if v.get("worse_than_line"))
    miss = sorted(k for k, v in p["mae"].items() if v.get("missing"))
    parts = ([f"{', '.join(over)} MAE 계약선 초과"] if over else []) + ([f"{', '.join(miss)} MAE 결측"] if miss else [])
    return {"over": over, "missing": miss, "text": " · ".join(parts) or "MAE 계약선 안"}


def overall(pass_status, ms):
    if pass_status == "퇴행" or ms["over"]:
        return "전체 조건 미충족"
    if pass_status == "비퇴행" and not ms["missing"]:
        return "전체 조건 충족"
    return "미확인"


res = {"targets": {}, "startup": {}, "cells": [], "holm": {}, "completion": {}, "target_verdict": {}, "regression_24000": {},
       "contract_24000": {}}


def cell_reading(p):
    """description of one target cell's interval (not the judgment)."""
    if p["lo"] > 0:
        return "구간 하한 0 위"
    return "구간 전체가 0 아래" if p["hi"] < 0 else "구간이 0 을 걸침"


def joint_verdict(ps):
    """2(c) as confirmed: 개선 = all three low ends > 0 and the equal-weight mean difference >= +10 pp (exact fractions)."""
    from fractions import Fraction
    mean = sum(Fraction(p["b_y_only"] - p["c_x_only"], p["n"]) for p in ps) / len(ps)
    low = all(p["lo"] > 0 for p in ps)
    return {"all_low_above_0": low, "mean_pp": float(100 * mean), "mean_ge_10": mean >= Fraction(1, 10),
            "verdict": "개선" if low and mean >= Fraction(1, 10) else "개선 아님"}


def regression_tag(p):
    """against the -5 pp line on the n=500 interval."""
    if p["hi"] < -0.05:
        return "퇴행"
    if p["lo"] >= -0.05:
        return "비퇴행"
    return "비퇴행 미확인"

for cell in TARGETS:
    row = {}
    for m in MODELS:
        have, xs = pooled(m, "flat", cell, "on", SEEDS)
        if have:
            row[m] = {"seeds": have, "n": len(xs), "rate": sum(xs) / len(xs), "ci": Q.wilson(sum(xs), len(xs)),
                      "per_seed": {s: float(np.mean(R[(m, "flat", cell, "on", s)]["main"])) for s in have},
                      "ref_rate_s1000": float(np.mean(R[(m, "flat", cell, "on", 1000)]["ref"])) if 1000 in have else None}
            st = sum((R[(m, "flat", cell, "on", s)]["startup"] for s in have), [])
            full = [x for x in st if x["valid_steps_1s"] == 50]
            early = [x for x in st if x["valid_steps_1s"] < 50]
            prog = [x["progress_5s_m"] for x in st if not np.isnan(x["progress_5s_m"])]
            mean = lambda v: float(np.mean(v)) if v else None  # noqa: E731
            res["startup"].setdefault(cell, {})[m] = {
                "n": len(st), "completed_1s": len(full), "early_fail_1s": len(early),
                "early_valid_s_mean": mean([x["valid_steps_1s"] * Q.DT for x in early]),
                "contact_1s": sum(x["contact_1s"] for x in st), "survive_5s": sum(x["survive_5s"] for x in st),
                "lin_err_int_m_completed": mean([x["lin_err_int_m"] for x in full]),
                "yaw_err_int_rad_completed": mean([x["yaw_err_int_rad"] for x in full]),
                "lin_err_int_m_early_partial": mean([x["lin_err_int_m"] for x in early]),
                "yaw_err_max_p90_completed": float(np.percentile([x["yaw_err_max"] for x in full], 90)) if full else None,
                "progress_5s_m_mean": mean(prog), "progress_5s_n": len(prog)}
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
        pp = [res["targets"][c][f"on_minus_off_{u}"] for c in TARGETS]
        per_seed = {}
        for c in TARGETS:  # seed-by-seed on - off (ASTRA 15 6.1: the five seeds share terrain and layout variation)
            ro, rn = res["targets"][c].get(f"off{u}", {}), res["targets"][c].get(f"on{u}", {})
            per_seed[c] = {s: rn["per_seed"][s] - ro["per_seed"][s] for s in ro.get("per_seed", {}) if s in rn.get("per_seed", {})}
        have = {c: res["targets"][c][f"on_minus_off_{u}"]["seeds"] for c in TARGETS}
        complete = all(have[c] == SEEDS and res["targets"][c][f"on_minus_off_{u}"]["n"] == 100 * len(SEEDS) for c in TARGETS)
        tv = {"cells": {c: cell_reading(p) for c, p in zip(TARGETS, pp)}, "complete": complete,
              "n_pairs": {c: res["targets"][c][f"on_minus_off_{u}"]["n"] for c in TARGETS},
              "seeds_expected": SEEDS, "seeds_have": have, "seeds_missing": {c: [x for x in SEEDS if x not in have[c]] for c in TARGETS},
              "per_seed_diff": per_seed, "holm_rejected": res["holm"][u]["rejected"]}
        if complete:
            tv.update(joint_verdict(pp))
        else:
            tv["verdict"] = "수집 중 · 결합 판정 보류"
        res["target_verdict"][u] = tv
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
                    r["mae_worse_than_line"] = bool(any(v["worse_than_line"] for v in r["mae"].values()))
                    row[f"on_minus_off_{u}"] = r
            if any(m in row for m in MODELS):
                res["cells"].append(row)
for m in MODELS:
    for fam in FAMILIES:
        res["completion"][f"{m}/{fam}"] = sum((m, fam, c, "on", 1000) in R for c in CELLS)
# regression at 24000 (2(c)): screen on seed 1000 (n=100); flagged cells judged on seeds 1000-1004 (n=500)
PLANNED = [(f, c, n) for f in FAMILIES for c in CELLS for n in ("on", "off") if n == "on" or f == "flat"]
for fam, cell, noise in PLANNED:
    key = f"{fam}/{cell}/{noise}"
    if fam == "flat" and noise == "on" and cell in TARGETS:
        p5 = res["targets"][cell].get("on_minus_off_24000")
        if not p5:
            continue
        done = p5["seeds"] == SEEDS
        ms = mae_status(p5)
        ps = regression_tag(p5) if done else "수집 중"
        res["regression_24000"][key] = {"stage": "n500 (target)" if done else "target (수집 중)", "n": p5["n"], "diff": p5["diff"],
                                        "lo": p5["lo"], "hi": p5["hi"], "per_seed": p5["per_seed"], "pass_status": ps,
                                        "mae": ms, "overall": overall(ps, ms), "verdict": ps}
        continue
    s1 = compare("off24000", "on24000", fam, cell, noise, [1000])
    if not s1:
        continue
    row = {"screen_n": s1["n"], "screen_diff": s1["diff"], "screen_lo": s1["lo"], "screen_hi": s1["hi"]}
    if 100 * (s1["b_y_only"] - s1["c_x_only"]) > -5 * s1["n"]:  # not flagged (point estimate above -5 pp; same rule as the driver)
        ps = "비퇴행" if s1["lo"] >= -0.05 else "비퇴행 미확인"
        ms = mae_status(s1)
        row.update(stage="선별 비해당 · 추가 측정 없음", pass_status=ps, mae=ms, overall=overall(ps, ms))
    else:
        p5 = compare("off24000", "on24000", fam, cell, noise, SEEDS)
        if p5 and p5["seeds"] == SEEDS:
            ps = regression_tag(p5)
            ms = mae_status(p5)
            new = compare("off24000", "on24000", fam, cell, noise, [x for x in SEEDS if x != 1000])
            row.update(stage="선별 → 500 판", n=p5["n"], diff=p5["diff"], lo=p5["lo"], hi=p5["hi"], per_seed=p5["per_seed"],
                       pass_status=ps, mae=ms, overall=overall(ps, ms),
                       new400={"n": new["n"], "diff": new["diff"], "lo": new["lo"], "hi": new["hi"]} if new else None)
        else:
            ms = mae_status(s1)
            row.update(stage="선별 → 다시 재는 중", pass_status="다시 재는 중", mae=ms, overall="미확인",
                       seeds_have=(p5 or {}).get("seeds", [1000]))
    row["verdict"] = row["pass_status"]
    res["regression_24000"][key] = row
res["regression_coverage"] = {"planned": len(PLANNED), "measured": len(res["regression_24000"]),
                              "unmeasured": [f"{f}/{c}/{n}" for f, c, n in PLANNED if f"{f}/{c}/{n}" not in res["regression_24000"]]}
# basic contract per arm (survival >= 95 %, command pass >= 90 %, judged apart), seed 1000 n=100 per cell, point estimate
# with the Wilson interval beside it (ASTRA 16 4: the recorded rule sets a line, not an interval rule)
for m in ("off24000", "on24000"):
    rows = {}
    for fam, cell, noise in PLANNED:
        k = (m, fam, cell, noise, 1000)
        if k not in R:
            continue
        sv, ps = R[k]["surv"], R[k]["main"]
        rows[f"{fam}/{cell}/{noise}"] = {"surv_k": sum(sv), "pass_k": sum(ps), "n": len(ps), "surv": sum(sv) / len(sv), "pass": sum(ps) / len(ps),
                                         "surv_ok": sum(sv) >= 0.95 * len(sv), "pass_ok": sum(ps) >= 0.90 * len(ps),
                                         "surv_ci": Q.wilson(sum(sv), len(sv)), "pass_ci": Q.wilson(sum(ps), len(ps))}
    res["contract_24000"][m] = {"cells": rows, "n_cells": len(rows), "planned": len(PLANNED),
                                "unmeasured": [f"{f}/{c}/{n}" for f, c, n in PLANNED if f"{f}/{c}/{n}" not in rows],
                                "surv_below": sorted(k for k, v in rows.items() if not v["surv_ok"]),
                                "pass_below": sorted(k for k, v in rows.items() if not v["pass_ok"])}
res["n_valid_runs"] = len(R)
res["as_of"] = time.strftime("%Y-%m-%d %H:%M:%S")
res["inputs"] = drv.get("inputs", {})
res["changed_after_validation"] = changed
res["interval_method"] = "tango score (paired_ci.py); newcombe kept for comparison"
res["driver_logs"] = drv["logs"]
res["driver_pair_fail"] = drv.get("pair_fail", [])
res["driver_invalid"] = drv.get("skipped", [])
json.dump(res, open(os.path.join(DEST, "cmdr_post.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


def pct(v):
    return "" if v is None else f"{100 * v:.0f}"


def dfmt(p):
    return "" if not p else f"{100 * p['diff']:+.0f} [{100 * p['lo']:+.0f}, {100 * p['hi']:+.0f}] p={p['p']:.2g}"


L = ["# CMD-R 표 (자동 생성 · cmdr_post_v5.py)", "",
     "주 통과 = span 정의 (stop03 span_q2 · fwd01/02 span_q1a · 그 밖 span_q1). 차이는 같은 시드 · 같은 episode 끼리 짝지은 %p 와 95 % 구간.",
     "판정선은 팀장 확정 2(c) (10/13 01:10): 목표 칸마다 500 판 · 「개선」 = 세 칸 모두 95 % 구간 하한 > 0 이고 세 칸 평균 +10 %p 이상 · 퇴행은 100 판 훑기에서 점추정 −5 %p 이하 칸만 500 판으로 다시 재서 구간으로 판정 (−5 %p 를 걸치면 「비퇴행 미확인」) · MAE +10 % · 기본 계약 (생존 95 % · 통과 90 %) 은 따로. 이 표는 채택 · 기각을 쓰지 않는다.", "",
     "## 목표 세 칸 (평지 · noise 켬 · 시드 묶음)", "",
     "| 칸 | 부모 20000 | off 22000 | on 22000 | off 24000 | on 24000 | on−off 22000 | on−off 24000 |", "|---|---|---|---|---|---|---|---|"]
for c in TARGETS:
    r = res["targets"][c]
    L.append(f"| {c} | " + " | ".join(f"{pct(r[m]['rate'])} (n {r[m]['n']})" if m in r else "" for m in MODELS)
             + f" | {dfmt(r.get('on_minus_off_22000'))} | {dfmt(r.get('on_minus_off_24000'))} |")
L += ["", f"Holm (on−off, 목표 셋): {json.dumps(res['holm'], ensure_ascii=False)}",
      f"목표 판정 (세 칸 결합 · 칸별은 서술): {json.dumps(res['target_verdict'], ensure_ascii=False)}", "",
      "## 시작 직후 (0~1 s) · 5 s", "",
      "평면 오차 적분은 vx · vy 절대오차 합 (L1) × 0.02 s. 1 초를 다 채운 판과 1 초 안에 끝난 판을 나눠 적는다.", "",
      "| 칸 | 모델 | n | 1 s 채움 | 1 s 안 끝남 (평균 유효 s) | 1 s 안 몸통 접촉 | 5 s 생존 | 평면 오차 적분 m (채운 판) | yaw 오차 적분 rad (채운 판) | 5 s 진행 m (n) |",
      "|---|---|---|---|---|---|---|---|---|---|"]
f3 = lambda v, d=3: "" if v is None else f"{v:.{d}f}"  # noqa: E731
for c, d in res["startup"].items():
    for m, s in d.items():
        L.append(f"| {c} | {m} | {s['n']} | {s['completed_1s']} | {s['early_fail_1s']} ({f3(s['early_valid_s_mean'], 2)}) | "
                 f"{s['contact_1s']} | {s['survive_5s']} | {f3(s['lin_err_int_m_completed'])} | {f3(s['yaw_err_int_rad_completed'])} | "
                 f"{f3(s['progress_5s_m_mean'], 2)} ({s['progress_5s_n']}) |")
L += ["", "## 모든 칸 (시드 1000)", "", "| 지형 | 칸 | noise | 부모 | off 22000 | on 22000 | off 24000 | on 24000 | on−off 24000 |", "|---|---|---|---|---|---|---|---|---|"]
for r in res["cells"]:
    L.append(f"| {r['family']} | {r['cell']} | {r['noise']} | " + " | ".join(pct(r[m]["rate"]) if m in r else "" for m in MODELS)
             + f" | {dfmt(r.get('on_minus_off_24000'))} |")
L += ["", "## 채워진 칸 수 (noise 켬 · 시드 1000 · 지형마다 11 칸)", "", "| 모델 | " + " | ".join(FAMILIES) + " |", "|---|" + "---|" * len(FAMILIES)]
for m in MODELS:
    L.append(f"| {m} | " + " | ".join(str(res["completion"][f"{m}/{f}"]) for f in FAMILIES) + " |")
L += ["", f"## 24,000 퇴행 (on − off · Tango 구간) · 계획 {res['regression_coverage']['planned']} 칸 중 {res['regression_coverage']['measured']} 칸 잼", "",
      "| 칸 | 단계 | 선별 (n 100) | 500 판 | 새 시드 400 판 | 통과율 | MAE | 전체 |", "|---|---|---|---|---|---|---|---|"]
for k, r in res["regression_24000"].items():
    sc = "" if "screen_diff" not in r else f"{100 * r['screen_diff']:+.0f} [{100 * r['screen_lo']:+.1f}, {100 * r['screen_hi']:+.1f}]"
    n5 = "" if "lo" not in r else f"{100 * r['diff']:+.1f} [{100 * r['lo']:+.1f}, {100 * r['hi']:+.1f}]"
    nw = r.get("new400") or {}
    n4 = "" if not nw else f"{100 * nw['diff']:+.1f} [{100 * nw['lo']:+.1f}, {100 * nw['hi']:+.1f}]"
    L.append(f"| {k} | {r['stage']} | {sc} | {n5} | {n4} | {r['pass_status']} | {r['mae']['text']} | {r['overall']} |")
L += ["", "## 24,000 기본 계약 (시드 1000 · 칸마다 100 판 · 점추정 · Wilson 95 % 구간)", ""]
for m, c in res["contract_24000"].items():
    L.append(f"- {m}: 계획 {c['planned']} 칸 중 {c['n_cells']} 칸 잼 · 생존 95 % 아래 {len(c['surv_below'])} 칸 · 통과 90 % 아래 {len(c['pass_below'])} 칸")
    for k, v in c["cells"].items():
        if not (v["surv_ok"] and v["pass_ok"]):
            L.append(f"  - {k}: 생존 {v['surv_k']}/{v['n']} [{100 * v['surv_ci'][0]:.1f}, {100 * v['surv_ci'][1]:.1f}] · "
                     f"통과 {v['pass_k']}/{v['n']} [{100 * v['pass_ci'][0]:.1f}, {100 * v['pass_ci'][1]:.1f}]")
L += ["", f"유효 실행 {res['n_valid_runs']} · 짝 불일치 {len(res['driver_pair_fail'])} · 무효 {len(res['driver_invalid'])} · 기록 {json.dumps(res['driver_logs'], ensure_ascii=False)}"]
open(os.path.join(DEST, "CMDR-tables.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"valid runs {len(R)} · targets {[c for c in TARGETS if res['targets'][c]]} · holm {res['holm']}")
