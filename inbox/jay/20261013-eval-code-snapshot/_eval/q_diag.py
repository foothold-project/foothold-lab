# Diagnostics behind the cell pass rates (reads out/m<it>_<family>/episodes.csv).
# 1) stop failures split by cause, 2) heading drift on straight cells (signed),
# 3) Q3 gate / corridor, 4) falls. Writes out/Q-E1-diag.json and prints a digest.

import csv
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FAMS = ["flat", "wave", "slope_up", "slope_down", "rough_slope", "stairs_up", "stairs_down", "obstacles"]
ITS = ["20000", "20499"]
STRAIGHT = ["fwd02", "fwd03", "fwd05", "back03", "left03", "right03"]


def tf(v):
    return str(v) in ("True", "true", "1")


def fl(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(tag):
    p = os.path.join(OUT, tag, "episodes.csv")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


diag = {"stop": {}, "heading": {}, "q3": {}, "falls": {}, "offplat": {}}
for it in ITS:
    for fam in FAMS:
        eps = load(f"m{it}_{fam}")
        st = [r for r in eps if r["cell"] == "stop03"]
        if st:
            no_stop = sum(not np.isfinite(fl(r["stop_t"])) for r in st)
            late = sum(np.isfinite(fl(r["stop_t"])) and fl(r["stop_t"]) > 1.0 for r in st)
            far = sum(np.isfinite(fl(r["stop_t"])) and fl(r["stop_t"]) <= 1.0 and fl(r["stop_dist_m"]) > 0.2 for r in st)
            fell = sum(not tf(r["survived"]) for r in st)
            mov = sum(not tf(r["q1_pass"]) for r in st)
            t = np.array([fl(r["stop_t"]) for r in st])
            t = t[np.isfinite(t)]
            d = np.array([fl(r["stop_dist_m"]) for r in st])
            diag["stop"][f"{it}/{fam}"] = dict(
                n=len(st), q2_pass=sum(tf(r["q2_pass"]) for r in st), no_stop_within_window=no_stop,
                stop_after_1s=late, stop_dist_over_0p2=far, fell=fell, moving_phase_fail=mov,
                stop_t_median=float(np.median(t)) if t.size else None, stop_t_p90=float(np.percentile(t, 90)) if t.size else None,
                stop_dist_median=float(np.nanmedian(d)), still_frac_after=None)
        hd = {}
        for cell in STRAIGHT + ["stand"]:
            rr = [r for r in eps if r["cell"] == cell]
            h = np.array([fl(r["heading_err_rad"]) for r in rr])
            h = h[np.isfinite(h)]
            if h.size:
                hd[cell] = dict(mean_signed=float(h.mean()), mean_abs=float(np.abs(h).mean()),
                                p90_abs=float(np.percentile(np.abs(h), 90)), frac_pos=float((h > 0).mean()))
        diag["heading"][f"{it}/{fam}"] = hd
        q3 = {}
        for cell in STRAIGHT + ["fwd01"]:
            rr = [r for r in eps if r["cell"] == cell]
            if not rr:
                continue
            gate = sum(np.isfinite(fl(r["gate_t"])) for r in rr)
            corr = np.array([fl(r["corridor_max_m"]) for r in rr])
            q3[cell] = dict(gate_reached=gate, q3_pass=sum(tf(r["q3_pass"]) for r in rr),
                            corridor_median=float(np.nanmedian(corr)),
                            corridor_le_0p3=int(np.sum(corr <= 0.3)))
        diag["q3"][f"{it}/{fam}"] = q3
        falls = {}
        for r in eps:
            if not tf(r["survived"]):
                falls.setdefault(r["cell"], []).append((r["fall_reason"], round(fl(r["fall_t"]), 2)))
        diag["falls"][f"{it}/{fam}"] = falls
    eps = load(f"m{it}_offplat")
    if eps:
        for fam in FAMS[1:]:
            for cell in ("stand", "stop03", "yawL05", "yawR05"):
                rr = [r for r in eps if r["family"] == fam and r["cell"] == cell]
                if not rr:
                    continue
                rule = "q2_pass" if cell == "stop03" else "q1_pass"
                t = np.array([fl(r["stop_t"]) for r in rr])
                diag["offplat"][f"{it}/{fam}/{cell}"] = dict(
                    n=len(rr), survived=sum(tf(r["survived"]) for r in rr), rule_pass=sum(tf(r[rule]) for r in rr),
                    q1m=sum(tf(r["q1m_pass"]) for r in rr),
                    mae_wz=float(np.nanmean([fl(r["mae_wz"]) for r in rr])),
                    mae_vx=float(np.nanmean([fl(r["mae_vx"]) for r in rr])),
                    disp_mean=float(np.nanmean([fl(r["disp_m"]) for r in rr])),
                    no_stop=int(np.sum(~np.isfinite(t))) if cell == "stop03" else None,
                    falls=[(r["fall_reason"], fl(r["fall_t"])) for r in rr if not tf(r["survived"])])

with open(os.path.join(OUT, "Q-E1-diag.json"), "w", encoding="utf-8") as f:
    json.dump(diag, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

for k, v in diag["stop"].items():
    print("STOP", k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if vv is not None})
for k, v in diag["heading"].items():
    print("HEAD", k, {c: (round(x["mean_signed"], 2), round(x["mean_abs"], 2), round(x["frac_pos"], 2)) for c, x in v.items()})
for k, v in diag["q3"].items():
    print("Q3", k, {c: (x["gate_reached"], x["corridor_le_0p3"], x["q3_pass"], round(x["corridor_median"], 2)) for c, x in v.items()})
for k, v in diag["falls"].items():
    if v:
        print("FALL", k, v)
for k, v in diag["offplat"].items():
    print("OFF", k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()})

# 5) stop-phase jitter with and without observation noise (t = 6..10 s, states 300..500)
jit = {}
for tag in ["m20000_flat", "m20000_noise_flat", "m20499_flat", "m20499_noise_flat",
            "m20000_stairs_up", "m20000_noise_stairs_up", "m20499_stairs_up", "m20499_noise_stairs_up"]:
    p = os.path.join(OUT, tag, "traj.npz")
    if not os.path.exists(p):
        continue
    z = np.load(p)
    tr, cel = z["traj"], z["cel"]
    with open(os.path.join(OUT, tag, "meta.json"), encoding="utf-8") as f:
        names = [c["name"] for c in json.load(f)["cells"]]
    e = np.where(cel == names.index("stop03"))[0]
    seg = tr[300:501][:, e]
    sp = np.hypot(seg[..., 4], seg[..., 5])
    wz = np.abs(seg[..., 9])
    drift = np.hypot(tr[500, e, 0] - tr[250, e, 0], tr[500, e, 1] - tr[250, e, 1])
    jit[tag] = dict(speed_mean=float(sp.mean()), speed_over_0p05=float((sp >= 0.05).mean()),
                    yawrate_mean=float(wz.mean()), yawrate_over_0p10=float((wz >= 0.10).mean()),
                    both_below=float(((sp < 0.05) & (wz < 0.10)).mean()), drift_5_10s_median_m=float(np.median(drift)))
diag["stop_jitter_t6_10"] = jit
with open(os.path.join(OUT, "Q-E1-diag.json"), "w", encoding="utf-8") as f:
    json.dump(diag, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
for k, v in jit.items():
    print("JIT", k, {kk: round(vv, 3) for kk, vv in v.items()})
