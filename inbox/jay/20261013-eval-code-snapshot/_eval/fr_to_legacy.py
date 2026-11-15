# Full-record CSV (q_eval --full_record, 115 columns) -> the lab's legacy formats, read only:
#   1. 93-column episode parquet written with the lab's `timeseries.write()` (schema foothold-timeseries/1)
#   2. 17-column HUD trace CSV written with the lab's `overlay/trace.write()` (schema foothold-trace/2)
# The lab files are imported, never modified. Column meanings follow the lab producers:
#   eval_command_response.py (per-step command, "now" contact force, vel_err = planar norm) and
#   eval_generalization.py (floor_z = terrain env origin z), yaw_deg = turn from the start axis (trace.py,
#   record_terrain_demo.py). See RECORD-HUD.md for the column table.
# Every converted episode is folded back and compared with the q_post values of that episode (MAE vx, vy, wz over
# the same window, number of rows); a mismatch raises ConversionError (nothing is written for that episode).
# Usage: python fr_to_legacy.py --tag <full tag> [--files all|a.csv,b.csv] [--origins <npy>] [--out <dir>]
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
LAB_EVAL = os.path.join(LAB, "sim", "eval")
sys.path.insert(0, HERE)
sys.path.insert(0, LAB_EVAL)
import q_metrics as Q  # noqa: E402
import metrics  # noqa: E402  (lab, read only)
import timeseries  # noqa: E402  (lab, read only)
from overlay import trace as trace_mod  # noqa: E402  (lab, read only)

# Articulation order of the Go2 joints, as the lab parquet files list them (meta `joint_names`,
# e.g. results/20260923-v2rs-axis2/.../ep0001.parquet). columns_for() builds the 93 columns in this order.
LAB_JOINT_ORDER = ["FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
                   "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
                   "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint"]
FEET = [("fl", "FL_foot"), ("fr", "FR_foot"), ("rl", "RL_foot"), ("rr", "RR_foot")]
DT = Q.DT
FOOT_CONTACT_SEMANTICS = (
    "foot_contact_*_n = |net normal contact force| on the foot at the last 5 ms physics substep before this "
    "state (Isaac Lab ContactSensor.data.net_forces_w, normal force only, friction not recorded). Same meaning as "
    "eval_command_response.py ('now' force); eval_generalization.py writes the max over a 3-step history instead.")


class ConversionError(ValueError):
    """The converted rows do not fold back to the judged values of the episode."""


def lab_provenance():
    out = {}
    try:
        out["lab_head"] = subprocess.run(["git", "-C", LAB, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:  # pragma: no cover
        out["lab_head"] = ""
    for rel in ("sim/eval/timeseries.py", "sim/eval/overlay/trace.py", "sim/eval/metrics.py"):
        out[rel] = hashlib.sha256(open(os.path.join(LAB, rel), "rb").read()).hexdigest()[:16]
    return out


def quat_forward_xy(w, x, y, z):
    """Body +x axis in the world, projected on the plane and normalised (eval_generalization.initial_forward_vectors)."""
    fx = 1.0 - 2.0 * (y * y + z * z)
    fy = 2.0 * (x * y + w * z)
    n = max(math.hypot(fx, fy), 1.0e-8)
    return (fx / n, fy / n)


def yaw_rel_deg(yaw_w_rad, fwd):
    """Turn from the start axis, left positive (record_terrain_demo.py 561-563)."""
    return math.degrees(math.atan2(math.sin(yaw_w_rad) * fwd[0] - math.cos(yaw_w_rad) * fwd[1],
                                   math.cos(yaw_w_rad) * fwd[0] + math.sin(yaw_w_rad) * fwd[1]))


def nn(v):
    v = float(v)
    return None if v != v else v


def convert_rows(D, floor_z):
    """D: structured array of one full-record CSV. Returns the list of 93-column row dicts."""
    r0 = D[0]
    start_xy = (float(r0["base_x_m"]), float(r0["base_y_m"]))
    fwd = quat_forward_xy(float(r0["quat_w"]), float(r0["quat_x"]), float(r0["quat_y"]), float(r0["quat_z"]))
    zcol = "base_z_w_m" if "base_z_w_m" in D.dtype.names else "base_z_m"  # CSVs written before the rename
    rows = []
    for k in range(len(D)):
        r = D[k]
        qw, qx, qy, qz = (float(r[c]) for c in ("quat_w", "quat_x", "quat_y", "quat_z"))
        roll, pitch, yaw = timeseries.euler_deg_from_quat(qw, qx, qy, qz)
        vx, vy = float(r["linvel_body_x_mps"]), float(r["linvel_body_y_mps"])
        cvx, cvy, cwz = float(r["cmd_vx_mps"]), float(r["cmd_vy_mps"]), float(r["cmd_wz_radps"])
        here = (float(r["base_x_m"]), float(r["base_y_m"]))
        pz = float(r[zcol])
        row = {
            "frame": int(r["step"]), "t_s": float(r["t_s"]),
            "cmd_vx_mps": cvx, "vx_mps": vx, "vy_mps": vy, "speed_mps": math.hypot(vx, vy),
            "vel_err_mps": math.hypot(vx - cvx, vy - cvy),
            "fwd_m": metrics.forward_offset_m(start_xy, here, fwd), "lat_m": metrics.lateral_offset_m(start_xy, here, fwd),
            "base_z_m": None if floor_z is None else pz - floor_z,
            "pitch_deg": pitch, "roll_deg": roll, "yaw_deg": yaw_rel_deg(math.radians(yaw), fwd),
            "base_x_m": here[0], "base_y_m": here[1], "base_z_w_m": pz,
            "base_qw": qw, "base_qx": qx, "base_qy": qy, "base_qz": qz, "base_yaw_deg": yaw,
            "base_vx_w_mps": float(r["linvel_world_x_mps"]), "base_vy_w_mps": float(r["linvel_world_y_mps"]),
            "base_vz_w_mps": float(r["linvel_world_z_mps"]),
            "base_wx_rps": float(r["angvel_body_x_radps"]), "base_wy_rps": float(r["angvel_body_y_radps"]),
            "base_wz_rps": float(r["angvel_body_z_radps"]),
            "cmd_vy_mps": cvy, "cmd_wz_rps": cwz,
        }
        for slot, ft in FEET:
            fz = float(r[f"{ft}_z_m"])
            row[f"foot_z_{slot}_m"] = None if floor_z is None else fz - floor_z
            row[f"foot_x_{slot}_m"] = float(r[f"{ft}_x_m"])
            row[f"foot_y_{slot}_m"] = float(r[f"{ft}_y_m"])
            row[f"foot_contact_{slot}_n"] = math.hypot(float(r[f"{ft}_force_vertical_N"]), float(r[f"{ft}_normal_force_horizontal_N"]))
        for j in LAB_JOINT_ORDER:
            row[f"joint_pos_{j}"] = float(r[f"q_{j}_rad"])
            row[f"joint_vel_{j}"] = float(r[f"dq_{j}_radps"])
            row[f"joint_torque_{j}"] = float(r[f"tau_{j}_Nm"])
            # joint_pos_target read before step k holds the target of the action of row k-1 (it is set while
            # stepping); the full record keeps the target of the action computed at row k. Shift by one row.
            row[f"joint_target_{j}"] = None if k == 0 else nn(D[k - 1][f"target_{j}_rad"])
        rows.append(row)
    return rows


def fold_back(rows, cell, summ):
    """Same window and formulas as q_metrics.episode_metrics. Returns (name, expected, got, diff, ok) list."""
    J = int(round(cell["duration_s"] / DT))
    survived = str(summ["survived"]) == "True"
    fall_t = float(summ["fall_t"]) if summ["fall_t"] not in ("", "nan") else float("nan")
    j_last = J if survived else int(round(fall_t / DT)) - 1
    j0 = int(round(Q.SKIP_S / DT))
    track_end = int(round(cell["switch_s"] / DT)) if cell["kind"] == "stop" else J
    jj = [j for j in range(j0, min(track_end, j_last) + 1) if j < len(rows)]
    out = []

    def add(name, exp, got, tol):
        if exp is None or got is None or exp != exp:
            out.append((name, exp, got, None, exp != exp and got is None))
            return
        out.append((name, exp, got, abs(exp - got), abs(exp - got) <= tol))
    if jj:
        add("mae_vx", float(summ["mae_vx"]), float(np.mean([abs(rows[j]["vx_mps"] - rows[j]["cmd_vx_mps"]) for j in jj])), 2e-4)
        add("mae_vy", float(summ["mae_vy"]), float(np.mean([abs(rows[j]["vy_mps"] - rows[j]["cmd_vy_mps"]) for j in jj])), 2e-4)
        add("mae_wz", float(summ["mae_wz"]), float(np.mean([abs(rows[j]["base_wz_rps"] - rows[j]["cmd_wz_rps"]) for j in jj])), 2e-4)
    add("rows", float(summ["rows"]), float(len(rows)), 0.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--files", default="all")
    ap.add_argument("--origins", default=None, help="env_origins.npy of the run (N x 3); default out/<tag>/env_origins.npy or out/org_<tag>/env_origins.npy")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no_floor", action="store_true", help="write base_z_m / foot_z_*_m empty when the origins are unknown")
    a = ap.parse_args()
    FD = os.path.join(HERE, "out", "full", a.tag)
    OUTD = a.out or os.path.join(HERE, "out", "legacy", a.tag)
    os.makedirs(os.path.join(OUTD, "timeseries"), exist_ok=True)
    os.makedirs(os.path.join(OUTD, "trace"), exist_ok=True)
    meta_run = json.load(open(os.path.join(HERE, "out", a.tag, "meta.json"), encoding="utf-8"))
    cells = {c["name"]: c for c in meta_run["cells"]}
    org = a.origins
    if org is None and not a.no_floor:
        for cand in (os.path.join(HERE, "out", a.tag, "env_origins.npy"), os.path.join(HERE, "out", "org_" + a.tag, "env_origins.npy")):
            if os.path.exists(cand):
                org = cand
                break
    origins = np.load(org) if org else None
    if origins is None and not a.no_floor:
        raise SystemExit(f"no env origins for {a.tag}; pass --origins or --no_floor")
    summ = {r["file"]: r for r in csv.DictReader(open(os.path.join(FD, "episodes_summary.csv"), encoding="utf-8"))}
    files = sorted(summ) if a.files == "all" else a.files.split(",")
    prov = lab_provenance()
    cols = timeseries.columns_for(LAB_JOINT_ORDER)
    assert len(cols) == 93, len(cols)
    report = []
    for fn in files:
        s = summ[fn]
        D = np.genfromtxt(os.path.join(FD, fn), delimiter=",", names=True)
        env = int(s["env"])
        floor_z = None if origins is None else float(origins[env, 2])
        rows = convert_rows(D, floor_z)
        checks = fold_back(rows, cells[s["cell"]], s)
        bad = [c for c in checks if not c[4]]
        if bad:
            raise ConversionError(f"{a.tag}/{fn}: folded values differ from q_post: {bad}")
        key = fn[:-4]
        fell = s["fall_t"] if s["survived"] != "True" else "nan"
        meta = {"probe": "q_eval_full_record", "source_csv": f"out/full/{a.tag}/{fn}", "tag": a.tag, "family": s["family"],
                "cell": s["cell"], "episode": s["episode"], "env_id": env, "labels": s["labels"], "checkpoint": s["checkpoint"],
                "obs_noise": s["obs_noise"], "dt_s": DT, "fell_at_s": fell, "fall_reason": s["fall_reason"],
                "joint_names": ",".join(LAB_JOINT_ORDER), "floor_z_m": "" if floor_z is None else floor_z,
                "floor_z_source": "terrain env_origins z of this env (eval_generalization.py meaning)" if floor_z is not None else "unknown: base_z_m and foot_z_*_m left empty",
                "yaw_deg_semantics": "turn from the start axis, left positive (trace.py, record_terrain_demo.py); base_yaw_deg is the world yaw",
                "joint_target_semantics": "target in force during the step that ended at this state (target of the previous row's action); row 0 empty",
                "foot_contact_semantics": FOOT_CONTACT_SEMANTICS,
                "rows_note": "one row per 50 Hz state, state 0 = after reset; the last row is the state after the last step",
                "converter": "fr_to_legacy.py", "lab_provenance": json.dumps(prov)}
        pq_path = os.path.join(OUTD, "timeseries", key + ".parquet")
        timeseries.write(pq_path, meta, rows, cols)
        back_meta, back_rows = timeseries.read(pq_path)
        assert len(back_rows) == len(rows)
        # 17-column trace for the HUD (only the trace columns; render.py takes the parquet rows through trace_obj
        # for the flat mode, as _out/loop/axis2_hud.py does)
        # E2 tags: e2_* · e2fr_* · un_e2_* (VERIFY-astra-14 7.3: startswith("e2_") titled every un_e2 / e2fr trace E1)
        run = ("E2" if a.tag.split("_", 1)[0].startswith("e2") or a.tag.startswith("un_e2_") else "E1") \
            + " m" + os.path.basename(s["checkpoint"]).split("_")[1].split(".")[0]
        title = "{} {} {} ep{:03d}".format(run, s["family"], s["cell"], int(s["episode"]))
        tmeta = {"fps": 1.0 / DT, "dt_s": DT, "slowmo": 1, "command_vx_mps": abs(rows[0]["cmd_vx_mps"]), "env_id": env,
                 "episode": int(s["episode"]), "terrain": s["family"], "title": title[:34], "fell_at_s": fell,
                 "termination_reason": "base_contact" if s["fall_reason"] == "base_contact" else "",
                 "source_csv": f"out/full/{a.tag}/{fn}"}
        tr_path = os.path.join(OUTD, "trace", key + ".trace.csv")
        trace_mod.write(tr_path, tmeta, [{c: r[c] for c in trace_mod.TRACE_COLUMNS} for r in rows])
        tr = trace_mod.read(tr_path)
        assert len(tr.rows) == len(rows)
        report.append({"file": fn, "rows": len(rows), "floor_z_m": floor_z, "checks": [list(c) for c in checks],
                       "parquet_bytes": os.path.getsize(pq_path), "trace_bytes": os.path.getsize(tr_path)})
    json.dump({"tag": a.tag, "origins": org, "columns": len(cols), "lab": prov, "episodes": report},
              open(os.path.join(OUTD, "convert_report.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps({"tag": a.tag, "episodes": len(report), "origins": org}))


if __name__ == "__main__":
    main()
