"""EX-42 AMP reference data (lead 2026-11-26 00:26 / 02:05, team lead 00:20 · 00:25, planner 00:26 conditions; plan AMP-PLAN-1126).

Real Go2 lowstate at 50 Hz (jetson factory-auto traces of 11/23, sport-mode controller driven by the stick) cut into
reference rows for a style discriminator:

    state s (30) = q - stand pose of that mode (12) · dq (12) · gyro (3, body rate) · grav (3, projected gravity)

Joint order is the policy order hip x4 · thigh x4 · calf x4, legs FL FR RL RR (factory_record.py POLICY_FROM_SDK, no sign flip).
The foot force channel (SDK raw order, nearly constant on this robot) is not used.

Row kinds (planner 00:27 (3)): walk = the stick commands motion (any |stick| > STICK_EPS); stop = the first STOP_S after the stick
returns to zero; stand = the rest of a zero-stick stretch. Command rows of the policy are matched against walk rows only, zero
command rows against stop + stand rows. Sit / stand-up transitions are not in these windows.

Stand pose per mode = the median q of that mode's stand rows ("q minus the stand pose of the same data", planner 00:27 (2)): the real
robot stands with the rear thigh near 0.7 rad, the sim default is 1.0, so absolute q would pull the policy toward the real pose.

    python -m foothold_s2.tools.ex42_amp_reference --out DIR [--trace-dir DIR]

Writes DIR/amp_ref.npz (s, mode, kind, seg, wall, stick, stand_pose) and DIR/amp_ref_report.json (counts, stand poses, the order and
sign checks, dq noise at stand). No Kit, no torch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

TRACE_DIR = Path("/home/jay/data/overnight-1122/jetson-logs/trace-1123")
FILES = ("factory-auto-20261123-140821-000.jsonl", "factory-auto-20261123-140821-001.jsonl")
_T = lambda s: time.mktime(time.strptime("2026-11-23 " + s, "%Y-%m-%d %H:%M:%S"))  # noqa: E731  (local time, as CMP-MODES-1123)
WINDOWS = {"classic": (_T("14:11:19"), _T("14:15:31")), "sport": (_T("14:20:55"), _T("14:23:24"))}  # cmp_modes_1123.py SETS
MODES = ("classic", "sport")
KINDS = ("walk", "stop", "stand")
STICK_EPS = 0.05
STOP_S = 1.5
DT = 0.02
GAP_S = 0.035            # a longer step between rows starts a new segment (no transition across it)
SIM_DEFAULT = np.array([0.1, -0.1, 0.1, -0.1, 0.8, 0.8, 1.0, 1.0, -1.5, -1.5, -1.5, -1.5])
STATE_NAMES = ([f"q_{j}_{leg}" for j in ("hip", "thigh", "calf") for leg in ("FL", "FR", "RL", "RR")]
               + [f"dq_{j}_{leg}" for j in ("hip", "thigh", "calf") for leg in ("FL", "FR", "RL", "RR")]
               + ["gyro_x", "gyro_y", "gyro_z", "grav_x", "grav_y", "grav_z"])


def load_rows(trace_dir: Path) -> list[dict]:
    rows = []
    for name in FILES:
        for line in open(trace_dir / name, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("wall") is None or not r.get("q") or r.get("stale") or r.get("phase") != "factory":
                continue
            rows.append(r)
    rows.sort(key=lambda r: r["wall"])
    return rows


def label(stick: np.ndarray, wall: np.ndarray) -> np.ndarray:
    """Per row 0 walk / 1 stop / 2 stand from the stick; stop = within STOP_S of the last moving row."""
    moving = np.abs(stick).max(axis=1) > STICK_EPS
    kind = np.full(len(stick), 2, dtype=np.int8)
    kind[moving] = 0
    last = -np.inf
    for i in range(len(stick)):
        if moving[i]:
            last = wall[i]
        elif wall[i] - last < STOP_S:
            kind[i] = 1
    return kind


def segments(wall: np.ndarray, kind: np.ndarray) -> np.ndarray:
    """Segment id per row: a new segment at a time gap or a kind change (a transition never spans two kinds)."""
    new = np.ones(len(wall), dtype=bool)
    new[1:] = (np.diff(wall) > GAP_S) | (kind[1:] != kind[:-1])
    return np.cumsum(new) - 1


def build(trace_dir: Path = TRACE_DIR) -> dict:
    rows = load_rows(trace_dir)
    out = {k: [] for k in ("q", "dq", "gyro", "grav", "mode", "wall", "stick")}
    for m, name in enumerate(MODES):
        a, b = WINDOWS[name]
        for r in rows:
            if a <= r["wall"] <= b:
                out["q"].append(r["q"]); out["dq"].append(r["dq"]); out["gyro"].append(r["gyro"]); out["grav"].append(r["grav"])
                out["mode"].append(m); out["wall"].append(r["wall"]); out["stick"].append(r["stick"])
    d = {k: np.asarray(v, dtype=np.float64) for k, v in out.items()}
    d["mode"] = d["mode"].astype(np.int8)
    kind = np.zeros(len(d["wall"]), dtype=np.int8)
    seg = np.zeros(len(d["wall"]), dtype=np.int64)
    stand_pose = np.zeros((len(MODES), 12))
    offset = 0
    for m in range(len(MODES)):
        sel = d["mode"] == m
        kind[sel] = label(d["stick"][sel], d["wall"][sel])
        seg[sel] = segments(d["wall"][sel], kind[sel]) + offset
        offset = int(seg[sel].max()) + 1 if sel.any() else offset
        st = sel & (kind == 2)
        if not st.any():
            raise ValueError(f"no stand rows for mode {MODES[m]}")
        stand_pose[m] = np.median(d["q"][st], axis=0)
    s = np.concatenate([d["q"] - stand_pose[d["mode"]], d["dq"], d["gyro"], d["grav"]], axis=1)
    return {"s": s.astype(np.float32), "mode": d["mode"], "kind": kind, "seg": seg, "wall": d["wall"], "stick": d["stick"].astype(np.float32),
            "stand_pose": stand_pose, "q": d["q"]}


def transitions(ref: dict) -> tuple[np.ndarray, np.ndarray]:
    """(index of s_t, index of s_t+1) for consecutive rows of the same segment."""
    i = np.arange(len(ref["seg"]) - 1)
    ok = ref["seg"][1:] == ref["seg"][:-1]
    return i[ok], i[ok] + 1


def diag_phase_corr(ref: dict, mode: int) -> dict:
    """Thigh angle correlation inside walk segments: diagonal pairs (FL-RR, FR-RL) move together in a trot, lateral pairs oppose."""
    q = ref["q"]
    out = {"FL_RR": [], "FR_RL": [], "FL_FR": []}
    for sg in np.unique(ref["seg"][(ref["mode"] == mode) & (ref["kind"] == 0)]):
        idx = np.flatnonzero(ref["seg"] == sg)
        if len(idx) < 100:
            continue
        t = q[idx, 4:8] - q[idx, 4:8].mean(axis=0)
        if (t.std(axis=0) < 0.02).any():
            continue
        c = np.corrcoef(t.T)
        out["FL_RR"].append(c[0, 3]); out["FR_RL"].append(c[1, 2]); out["FL_FR"].append(c[0, 1])
    return {k: (round(float(np.median(v)), 3) if v else None) for k, v in out.items()} | {"segments": len(out["FL_RR"])}


def report(ref: dict) -> dict:
    src, dst = transitions(ref)
    rep = {"rows": int(len(ref["s"])), "transitions": int(len(src)), "state_names": STATE_NAMES, "dt": DT,
           "stick_eps": STICK_EPS, "stop_s": STOP_S, "windows": {k: list(v) for k, v in WINDOWS.items()}, "modes": {}}
    for m, name in enumerate(MODES):
        sel = ref["mode"] == m
        cnt = {KINDS[k]: round(float(((ref["kind"] == k) & sel).sum()) * DT, 1) for k in range(3)}
        st = sel & (ref["kind"] == 2)
        pose = ref["stand_pose"][m]
        sign_ok = {"hip": bool(np.all(np.sign(pose[0:4]) == np.sign(SIM_DEFAULT[0:4]))) if np.all(np.abs(pose[0:4]) > 0.02) else None,
                   "thigh_positive": bool(np.all(pose[4:8] > 0)), "calf_negative": bool(np.all(pose[8:12] < 0))}
        rep["modes"][name] = {
            "seconds": cnt, "stand_pose": [round(float(x), 3) for x in pose],
            "stand_minus_sim_default": [round(float(x), 3) for x in pose - SIM_DEFAULT], "sign_checks": sign_ok,
            "grav_z_median": round(float(np.median(ref["s"][sel, 29])), 4),
            "stand_dq_rms": round(float(np.sqrt(np.mean(ref["s"][st, 12:24] ** 2))), 4),
            "walk_dq_rms": round(float(np.sqrt(np.mean(ref["s"][sel & (ref["kind"] == 0), 12:24] ** 2))), 4),
            "thigh_corr_walk": diag_phase_corr(ref, m)}
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--trace-dir", default=str(TRACE_DIR))
    a = ap.parse_args(argv)
    ref = build(Path(a.trace_dir))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "amp_ref.npz", **{k: v for k, v in ref.items() if k != "q"})
    rep = report(ref)
    rep["sources"] = {n: hashlib.sha256((Path(a.trace_dir) / n).read_bytes()).hexdigest() for n in FILES}
    rep["npz_sha256"] = hashlib.sha256((out / "amp_ref.npz").read_bytes()).hexdigest()
    (out / "amp_ref_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("state_names",)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
