# Post-processing for q_eval.py: traj.npz + meta.json -> episodes.csv + cells.json.
# Separate from the simulator run so metric changes can be re-applied to saved
# trajectories without re-simulating. Usage: python q_post.py out/<tag> [...]

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import q_metrics as Q  # noqa: E402

SPAWN_ROWS = 8


def postprocess(out_dir: str) -> list[dict]:
    with open(os.path.join(out_dir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    cells, families = meta["cells"], meta["families"]
    z = np.load(os.path.join(out_dir, "traj.npz"))
    traj, term = z["traj"], z["term"]
    cel, fam, epi = z["cel"], z["fam"], z["epi"]
    cmd_a, cmd_b, sw = z["cmd_a"], z["cmd_b"], z["sw"]
    act_abs = z["act_abs_mean"]
    cmd_hist = z["cmd_hist"] if "cmd_hist" in z.files else None
    T = traj.shape[0] - 1
    jj = np.arange(T + 1)
    rows = []
    for e in range(traj.shape[1]):
        c = cells[int(cel[e])]
        # command in force for state j is the one shown for action j-1
        cmd = np.where(((jj - 1) >= sw[e])[:, None], cmd_b[e], cmd_a[e])
        if cmd_hist is not None:  # recorded command (heading-hold variant changes wz per step)
            cmd = cmd_hist[:, e].astype(np.float64)
        tr = traj[:, e].astype(np.float64)
        m = Q.episode_metrics(c, pos=tr[:, 0:3], yaw=tr[:, 3], vb=tr[:, 4:7], wb=tr[:, 7:10],
                              grav_z=tr[:, 10], hag=tr[:, 11], term=term[:, e], cmd=cmd)
        row = {"family": families[int(fam[e])], "cell": c["name"], "episode": int(epi[e]), "env": e,
               "start_row": int(epi[e] % SPAWN_ROWS), "act_abs_mean": float(act_abs[e])}
        row.update(m)
        rows.append(row)
    keys = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(out_dir, "episodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    summary = []
    for fname in families:
        for c in cells:
            rr = [r for r in rows if r["family"] == fname and r["cell"] == c["name"]]
            key = "q2_pass" if c["kind"] == "stop" else "q1_pass"
            s = {"family": fname, "cell": c["name"], "kind": c["kind"], "cmd": c["cmd"], "src": c["src"], "rule": key}
            s.update(Q.cell_summary(rr, key))
            sm = Q.cell_summary(rr, "q1m_pass")
            s["q1m_pass"], s["q1m_pass_rate"], s["q1m_pass_ci"], s["q1m_cell_pass"] = (
                sm["pass"], sm["pass_rate"], sm["pass_ci"], sm["cell_pass"])
            if c["kind"] == "lin":
                s3 = Q.cell_summary(rr, "q3_pass")
                s["q3_pass"], s["q3_pass_rate"], s["q3_pass_ci"] = s3["pass"], s3["pass_rate"], s3["pass_ci"]
            if c["kind"] == "stop":
                s["q2_stop_only_pass"] = int(sum(r["q2_stop_only"] for r in rr))
                s["moving_phase_q1_pass"] = int(sum(r["q1_pass"] for r in rr))
            hd = np.array([r["heading_err_rad"] for r in rr], dtype=float)
            hd = hd[np.isfinite(hd)]
            s["abs_heading_err_rad_mean"] = float(np.abs(hd).mean()) if hd.size else float("nan")
            summary.append(s)
    with open(os.path.join(out_dir, "cells.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    return summary


def print_summary(tag, summary):
    for s in summary:
        print("[Q-EVAL]", tag, s["family"], s["cell"], "surv", s["survived"], "/", s["n"], s["rule"], s["pass"],
              "q1m", s["q1m_pass"], "mae", round(s["mae_vx_mean"], 3), round(s["mae_vy_mean"], 3),
              round(s["mae_wz_mean"], 3), "move", round(s["move_ratio_mean"], 3))


if __name__ == "__main__":
    for d in sys.argv[1:]:
        print_summary(os.path.basename(d.rstrip("/")), postprocess(d))
