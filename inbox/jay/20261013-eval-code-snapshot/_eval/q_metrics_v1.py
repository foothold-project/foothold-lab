# Q-v1 metric functions for the E1 (MoE-CTS) student evaluation.
#
# Pure numpy. No Isaac import, so it can be tested with known-answer traces
# (see test_q_metrics.py) before it is trusted on simulator output.
#
# Source of the numbers: DESIGN-astra-rl-topdown.md section 3, table
# "공통 평가 계약 Q" and the paragraph "낙상과 착지의 의미".
# Values that are NOT in that contract are marked LEAD_TEMP.
#
# Time indexing used everywhere in this file:
#   state j = 0      initial state after reset (t = 0)
#   state j >= 1     state after policy step j-1, t_j = j * dt
#   cmd[j]           command that was in the policy observation for the
#                    action that produced state j (cmd[0] := cmd[1])
#   term[j]          True if the env terminated in the step that produced
#                    state j. Isaac auto-resets in that step, so state j is
#                    already a post-reset state and is NOT valid.

from __future__ import annotations

import math

import numpy as np

DT = 0.02  # policy step: sim.dt 0.005 x decimation 4 (env_cfg.py:483-486)

# --- Q contract values -------------------------------------------------------
SKIP_S = 1.0          # "이동 구간 첫 1초 제외"
MAE_LIN = 0.15        # vx, vy MAE [m/s]
MAE_YAW = 0.20        # wz MAE [rad/s]
CELL_SURVIVAL = 0.95  # "각 명령 cell 생존 >=95%"
CELL_PASS = 0.90      # "해당 명령 기준 통과 >=90%"
STOP_SPEED = 0.05     # planar speed [m/s]
STOP_YAW = 0.10       # yaw rate [rad/s]
STOP_HOLD_S = 1.0     # "이를 1초 유지"
STOP_WITHIN_S = 1.0   # "1초 안에"
STOP_DIST = 0.20      # [m]
GATE_M = 4.0          # "4m gate"
CORRIDOR_M = 0.30     # "corridor 최대 이탈 <=0.30m"
TILT_DEG = 60.0       # "몸 기울기 >60도가 0.2초 지속"
TILT_HOLD_S = 0.2
# LEAD_TEMP: auxiliary "it actually moved" check. Not in Q. Added because the
# zero-action run passes Q1 at vx=0.1 (standing still gives MAE 0.10 <= 0.15).
MOVE_RATIO = 0.5      # progress (or heading change) >= 50% of commanded


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for k successes out of n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    lo = 0.0 if k == 0 else max(0.0, centre - half)  # exact bound, avoids 1e-18 residue
    hi = 1.0 if k == n else min(1.0, centre + half)
    return (lo, hi)


def newcombe_paired(a: int, b: int, c: int, d: int, z: float = 1.959963984540054):
    """Paired difference p1 - p2 with Newcombe (1998) method 10 interval.

    a: both pass, b: 1 pass 2 fail, c: 1 fail 2 pass, d: both fail.
    No continuity correction on phi.
    """
    n = a + b + c + d
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p1 = (a + b) / n
    p2 = (a + c) / n
    l1, u1 = wilson(a + b, n, z)
    l2, u2 = wilson(a + c, n, z)
    den = (a + b) * (c + d) * (a + c) * (b + d)
    phi = 0.0 if den == 0 else (a * d - b * c) / math.sqrt(den)
    delta = math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    eps = math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    diff = p1 - p2
    return (diff, diff - delta, diff + eps)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value on discordant counts."""
    m = b + c
    if m == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(m, i) for i in range(0, k + 1)) / (2.0 ** m)
    return min(1.0, 2.0 * tail)


def _runs_start(mask: np.ndarray, hold: int) -> int:
    """First index i such that mask[i:i+hold] is all True. -1 if none."""
    if hold <= 0:
        return 0
    n = mask.shape[0]
    if n < hold:
        return -1
    cs = np.concatenate([[0], np.cumsum(mask.astype(np.int64))])
    win = cs[hold:] - cs[:-hold]  # win[i] = sum(mask[i:i+hold])
    idx = np.nonzero(win == hold)[0]
    return int(idx[0]) if idx.size else -1


def fall_index(term: np.ndarray, grav_z: np.ndarray, hag: np.ndarray, dt: float = DT):
    """Earliest fall state index and reason.

    term   : (J+1,) bool, termination flag per state (base contact > 1 N in this env)
    grav_z : (J+1,) projected gravity z in body frame (-1 when upright)
    hag    : (J+1,) base height above local ground [m]
    Returns (j_fall, reason). j_fall = len(term) means no fall.
    Fall rules (Q "낙상과 착지의 의미"): base collision termination, tilt > 60 deg
    held 0.2 s, base below the support surface (hag < 0).
    j_fall is the first INVALID state index: states j < j_fall are usable.
    For tilt the onset index is returned (the fall is declared after the hold).
    """
    n = term.shape[0]
    j_term = int(np.argmax(term)) if term.any() else n
    valid = np.arange(n) < j_term
    cos_lim = math.cos(math.radians(TILT_DEG))
    tilted = (-grav_z < cos_lim) & valid
    hold = int(round(TILT_HOLD_S / dt))
    j_tilt = _runs_start(tilted, hold)
    j_tilt = n if j_tilt < 0 else j_tilt
    below = (hag < 0.0) & valid & np.isfinite(hag)
    j_below = int(np.argmax(below)) if below.any() else n
    cands = [(j_term, "base_contact"), (j_tilt, "tilt60"), (j_below, "below_support")]
    j, why = min(cands, key=lambda x: x[0])
    if j >= n:
        return n, ""
    return j, why


def unwrap(yaw: np.ndarray) -> np.ndarray:
    return np.unwrap(yaw)


def episode_metrics(
    cell: dict,
    pos: np.ndarray,      # (J+1, 3) world
    yaw: np.ndarray,      # (J+1,)  heading_w
    vb: np.ndarray,       # (J+1, 3) base lin vel, body frame
    wb: np.ndarray,       # (J+1, 3) base ang vel, body frame
    grav_z: np.ndarray,   # (J+1,)
    hag: np.ndarray,      # (J+1,)
    term: np.ndarray,     # (J+1,) bool
    cmd: np.ndarray,      # (J+1, 3) command in force for each state
    dt: float = DT,
) -> dict:
    """All per-episode numbers for one env. `cell` holds kind, duration_s, switch_s."""
    J = int(round(cell["duration_s"] / dt))  # last state index used
    pos, yaw, vb, wb = pos[: J + 1], yaw[: J + 1], vb[: J + 1], wb[: J + 1]
    grav_z, hag, term, cmd = grav_z[: J + 1], hag[: J + 1], term[: J + 1], cmd[: J + 1]
    j_fall, why = fall_index(term, grav_z, hag, dt)
    survived = j_fall > J
    j_last = min(J, j_fall - 1)  # last valid state
    out = {
        "survived": bool(survived),
        "fall_reason": why,
        "fall_t": float(j_fall * dt) if not survived else float("nan"),
    }
    j0 = int(round(SKIP_S / dt))
    kind = cell["kind"]
    if kind == "stop":
        j_sw = int(round(cell["switch_s"] / dt))
        track_end = j_sw  # moving phase: states up to t_sw
    else:
        j_sw = None
        track_end = J
    jj = np.arange(j0, min(track_end, j_last) + 1)
    if jj.size:
        err = np.abs(vb[jj, 0] - cmd[jj, 0]), np.abs(vb[jj, 1] - cmd[jj, 1]), np.abs(wb[jj, 2] - cmd[jj, 2])
        out["mae_vx"], out["mae_vy"], out["mae_wz"] = (float(e.mean()) for e in err)
        out["mean_vx"] = float(vb[jj, 0].mean())
        out["mean_vy"] = float(vb[jj, 1].mean())
        out["mean_wz"] = float(wb[jj, 2].mean())
        out["window_s"] = float(jj.size * dt)
    else:
        for k in ("mae_vx", "mae_vy", "mae_wz", "mean_vx", "mean_vy", "mean_wz"):
            out[k] = float("nan")
        out["window_s"] = 0.0
    # tracking survives only if the whole tracking window was alive
    alive_track = j_fall > track_end
    track_ok = (
        alive_track
        and jj.size > 0
        and out["mae_vx"] <= MAE_LIN
        and out["mae_vy"] <= MAE_LIN
        and out["mae_wz"] <= MAE_YAW
    )
    out["q1_pass"] = bool(track_ok)

    # path frame from the commanded direction at the initial heading
    c = cmd[min(1, J)]
    lin = math.hypot(c[0], c[1])
    xy = pos[:, :2] - pos[0, :2]
    if lin > 1e-9:
        th = yaw[0] + math.atan2(c[1], c[0])
        e = np.array([math.cos(th), math.sin(th)])
        s = xy @ e
        lat = xy[:, 0] * (-e[1]) + xy[:, 1] * e[0]
        sv = s[: j_last + 1]
        hit = np.nonzero(sv >= GATE_M)[0]
        j_gate = int(hit[0]) if hit.size else -1
        out["progress_m"] = float(sv[-1])
        out["progress_expected_m"] = float(lin * (cell["switch_s"] if kind == "stop" else cell["duration_s"]))
        out["gate_t"] = float(j_gate * dt) if j_gate >= 0 else float("nan")
        upto = j_gate if j_gate >= 0 else j_last
        out["corridor_max_m"] = float(np.abs(lat[: upto + 1]).max())
        out["q3_pass"] = bool(track_ok and survived and j_gate >= 0 and out["corridor_max_m"] <= CORRIDOR_M)
        # body-frame speed along the commanded direction over the tracking window,
        # divided by the commanded speed (not affected by heading drift)
        if jj.size:
            d = np.array([c[0], c[1]]) / lin
            out["move_ratio"] = float((vb[jj, 0] * d[0] + vb[jj, 1] * d[1]).mean() / lin)
        else:
            out["move_ratio"] = float("nan")
    else:
        for k in ("progress_m", "progress_expected_m", "gate_t", "corridor_max_m"):
            out[k] = float("nan")
        out["q3_pass"] = False
        out["move_ratio"] = float("nan")

    yu = unwrap(yaw)
    disp = float(np.linalg.norm(xy[j_last]))
    out["disp_m"] = disp
    if jj.size:
        # heading change over the tracking window; for lin/stop/stand cells the
        # expected change is 0, so heading_err is the heading drift
        dpsi = yu[jj[-1]] - yu[jj[0] - 1]
        expected = float(cmd[jj, 2].mean()) * jj.size * dt
        out["heading_change_rad"] = float(dpsi)
        out["heading_err_rad"] = float(dpsi - expected)
        if kind == "yaw":
            out["move_ratio"] = float(dpsi / expected) if abs(expected) > 1e-9 else float("nan")
    else:
        out["heading_change_rad"] = float("nan")
        out["heading_err_rad"] = float("nan")
    if kind == "stand":
        out["q1m_pass"] = out["q1_pass"]
    else:
        mr = out.get("move_ratio", float("nan"))
        out["q1m_pass"] = bool(out["q1_pass"] and np.isfinite(mr) and mr >= MOVE_RATIO)

    speed = np.hypot(vb[:, 0], vb[:, 1])
    still = (speed < STOP_SPEED) & (np.abs(wb[:, 2]) < STOP_YAW)
    if jj.size:
        out["still_frac"] = float(still[jj].mean())
    else:
        out["still_frac"] = float("nan")

    if kind == "stop":
        hold = int(round(STOP_HOLD_S / dt))
        seg = still[j_sw : j_last + 1]  # window must be complete and alive
        k = _runs_start(seg, hold)
        p_sw = pos[j_sw, :2]
        if k >= 0:
            j_stop = j_sw + k
            out["stop_t"] = float(k * dt)
            out["stop_dist_m"] = float(np.linalg.norm(pos[j_stop, :2] - p_sw))
        else:
            out["stop_t"] = float("nan")
            out["stop_dist_m"] = float(np.linalg.norm(pos[j_last, :2] - p_sw))
        out["post_stop_drift_m"] = float(np.linalg.norm(pos[j_last, :2] - p_sw))
        out["yaw_drift_rad"] = float(abs(yu[j_last] - yu[j_sw]))
        stop_ok = (
            survived
            and k >= 0
            and out["stop_t"] <= STOP_WITHIN_S + 1e-9
            and out["stop_dist_m"] <= STOP_DIST
        )
        out["q2_stop_only"] = bool(stop_ok)
        out["q2_pass"] = bool(stop_ok and track_ok)  # LEAD_TEMP: moving phase must track
    else:
        for k_ in ("stop_t", "stop_dist_m", "post_stop_drift_m", "yaw_drift_rad"):
            out[k_] = float("nan")
        out["q2_stop_only"] = False
        out["q2_pass"] = False
    return out


def cell_summary(rows: list[dict], key: str) -> dict:
    """Aggregate one cell. key: q1_pass, q2_pass or q3_pass."""
    n = len(rows)
    ns = sum(r["survived"] for r in rows)
    npass = sum(r[key] for r in rows)
    s_lo, s_hi = wilson(ns, n)
    p_lo, p_hi = wilson(npass, n)
    out = {
        "n": n,
        "survived": ns,
        "survival": ns / n if n else float("nan"),
        "survival_ci": [s_lo, s_hi],
        "pass": npass,
        "pass_rate": npass / n if n else float("nan"),
        "pass_ci": [p_lo, p_hi],
        "cell_pass": bool(n and ns / n >= CELL_SURVIVAL and npass / n >= CELL_PASS),
    }
    for m in ("mae_vx", "mae_vy", "mae_wz", "mean_vx", "mean_vy", "mean_wz", "corridor_max_m",
              "progress_m", "stop_t", "stop_dist_m", "yaw_drift_rad", "heading_err_rad", "disp_m",
              "still_frac", "post_stop_drift_m", "move_ratio"):
        v = np.array([r.get(m, np.nan) for r in rows], dtype=float)
        v = v[np.isfinite(v)]
        out[m + "_n"] = int(v.size)
        out[m + "_mean"] = float(v.mean()) if v.size else float("nan")
        out[m + "_p90"] = float(np.percentile(v, 90)) if v.size else float("nan")
        out[m + "_max"] = float(v.max()) if v.size else float("nan")
    gate = [r for r in rows if np.isfinite(r.get("gate_t", np.nan))]
    out["gate_reached"] = len(gate)
    reasons = {}
    for r in rows:
        if r["fall_reason"]:
            reasons[r["fall_reason"]] = reasons.get(r["fall_reason"], 0) + 1
    out["fall_reasons"] = reasons
    return out
