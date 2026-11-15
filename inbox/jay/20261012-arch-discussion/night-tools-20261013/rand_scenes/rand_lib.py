# Pure helpers for the randomization scene videos (no Isaac import; tested on CPU by test_rand_scenes.py).
# Revised 2026-10-13 20:xx for ASTRA 17d 2.1 to 2.4, 5, 7 (record joins, push linkage, fingerprints, execution gate v3).
#   push schedule  : parse "vy=+0.4;vy=-0.4;..." (k-th item = k-th firing of the training push interval), rotate to
#                    world, check every world component against the training velocity_range, predict the firing states
#                    with the event manager's float32 arithmetic
#   friction       : PhysX combine rule (average < min < multiply < max, the higher one wins)
#   record         : CSV columns, writer, reader, checks
#   statistics     : fall (q_metrics.fall_index, the Q rule), push response, foot slip (descriptive, one episode)
#   attempt check  : everything the driver checks after one Isaac run (log, result, record, videos)
#   paths          : outputs only under _eval/out_rand
import csv
import hashlib
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
OUT_RAND = os.path.join(EVAL, "out_rand")
E1_DIR = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
CKPT_DEFAULT = E1_DIR + "/model_20000.pt"
TRAIN_YAML_DEFAULT = E1_DIR + "/params/env.yaml"
DT = 0.02  # policy step (sim dt 0.005 x decimation 4), same as q_metrics.DT
RESULT_SCHEMA = "rand_scene_result/1"
DONE_RE = re.compile(r"^\[RAND\] done scene=(\S+) attempt=(\S+)\s*$", re.M)
FEET = ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
PUSH_KEYS = ("vx", "vy", "wx", "wy", "wz")  # frame components; vx/vy linear [m/s], wx/wy/wz angular [rad/s]
WORLD_KEYS = ("x", "y", "z", "roll", "pitch", "yaw")  # order of root_vel_w and of the training velocity_range keys


# --- paths ---------------------------------------------------------------------------------------------------------
def _norm(p):
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")


def check_out_path(p):
    """Outputs only under _eval/out_rand. Never _eval/out (closed results) or a frozen handover folder."""
    n = _norm(p)
    root = _norm(OUT_RAND)
    if not (n == root or n.startswith(root + "/")):
        raise ValueError(f"output path {p} is not under {OUT_RAND}")
    if "/handover" in n or n.startswith(_norm(os.path.join(EVAL, "out")) + "/"):
        raise ValueError(f"output path {p} touches a frozen or closed folder")
    return p


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --- training DR settings from the run's own env.yaml ------------------------------------------------------------------
def load_train_dr(yaml_path):
    """Push and material settings as stored by the training run (params/env.yaml)."""
    import yaml
    with open(yaml_path, "r", encoding="utf-8") as f:
        y = yaml.load(f, Loader=yaml.UnsafeLoader)
    ev = y["events"]
    push = ev["randomize_push_robot"]
    mat = ev["randomize_rigid_body_material"]["params"]
    ter = y["scene"]["terrain"]["physics_material"]
    sim = y["sim"]["physics_material"]
    return {
        "push_func": push["func"],
        "push_interval_s": [float(v) for v in push["interval_range_s"]],
        "push_is_global_time": bool(push.get("is_global_time", False)),
        "push_velocity_range": {k: [float(v[0]), float(v[1])] for k, v in push["params"]["velocity_range"].items()},
        "material_func": ev["randomize_rigid_body_material"]["func"],
        "material_mode": ev["randomize_rigid_body_material"]["mode"],
        "material_static_range": [float(v) for v in mat["static_friction_range"]],
        "material_dynamic_range": [float(v) for v in mat["dynamic_friction_range"]],
        "material_restitution_range": [float(v) for v in mat["restitution_range"]],
        "material_num_buckets": int(mat["num_buckets"]),
        "material_make_consistent": bool(mat["make_consistent"]),
        "ground_material": {k: ter[k] for k in ("static_friction", "dynamic_friction", "restitution",
                                                "friction_combine_mode", "restitution_combine_mode")},
        "sim_default_material": {k: sim[k] for k in ("static_friction", "dynamic_friction", "restitution",
                                                     "friction_combine_mode", "restitution_combine_mode")},
        "decimation": int(y["decimation"]), "sim_dt": float(y["sim"]["dt"]),
        "action_joint_names": [str(x) for x in y["actions"]["joint_pos"]["joint_names"]],
        "action_scale_cfg": {str(k): float(v) for k, v in y["actions"]["joint_pos"]["scale"].items()}
        if isinstance(y["actions"]["joint_pos"]["scale"], dict) else float(y["actions"]["joint_pos"]["scale"]),
    }


def train_env_expect(dr):
    """What the evaluation env must be, from the training env.yaml: physics dt, step dt, decimation, action joints in order and
    the scale of each (first regex in the yaml order that matches the whole name, as Isaac Lab resolves it)."""
    names = dr["action_joint_names"]
    sc = dr["action_scale_cfg"]
    if isinstance(sc, dict):
        scale = []
        for n in names:
            v = next((val for pat, val in sc.items() if re.fullmatch(pat, n)), None)
            if v is None:
                raise ValueError(f"no action scale pattern matches {n}")
            scale.append(v)
    else:
        scale = [float(sc)] * len(names)
    return {"physics_dt": dr["sim_dt"], "step_dt": dr["sim_dt"] * dr["decimation"], "decimation": dr["decimation"],
            "action_joint_names": names, "action_scale": scale}


# --- push schedule -------------------------------------------------------------------------------------------------------
def parse_push_schedule(spec):
    """'vy=+0.4;vy=-0.4' -> [{'vx':0,'vy':0.4,...}, {...}]. Item k is applied at the k-th firing of the push interval.
    An empty item or 'none' means no push at that firing. Unknown keys or repeated keys are errors."""
    out = []
    if spec is None or spec.strip() == "":
        return out
    for item in spec.split(";"):
        item = item.strip()
        d = {k: 0.0 for k in PUSH_KEYS}
        d["none"] = item in ("", "none")
        if not d["none"]:
            seen = set()
            for kv in item.split(","):
                k, v = kv.split("=")
                k = k.strip()
                if k not in PUSH_KEYS:
                    raise ValueError(f"unknown push key {k!r} in {item!r} (allowed {PUSH_KEYS})")
                if k in seen:
                    raise ValueError(f"repeated key {k!r} in {item!r}")
                seen.add(k)
                d[k] = float(v)
        out.append(d)
    return out


def to_world(delta, heading, frame):
    """Push delta in the given frame -> world 6-vector in root_vel_w order (x, y, z, roll, pitch, yaw).
    frame 'heading': vx forward, vy left (yaw-only rotation by the base heading), wx/wy rotated the same way, wz = world
    yaw rate. frame 'world': components as given (what the training push samples)."""
    if frame == "world":
        c, s = 1.0, 0.0
    elif frame == "heading":
        c, s = math.cos(heading), math.sin(heading)
    else:
        raise ValueError(frame)
    vx, vy, wx, wy, wz = (delta[k] for k in PUSH_KEYS)
    return [c * vx - s * vy, s * vx + c * vy, 0.0, c * wx - s * wy, s * wx + c * wy, wz]


def range_violations(world6, vel_range, tol=1e-9):
    """Components outside the training velocity_range (a key missing from the training range means (0, 0))."""
    bad = []
    for i, k in enumerate(WORLD_KEYS):
        lo, hi = vel_range.get(k, (0.0, 0.0))
        if world6[i] < lo - tol or world6[i] > hi + tol:
            bad.append({"axis": k, "value": world6[i], "range": [lo, hi]})
    return bad


def plan_violations(schedule, vel_range, frame):
    """Plan-time check that holds for every heading: in the heading frame a rotated xy component can reach
    sqrt(vx^2 + vy^2) (and sqrt(wx^2 + wy^2)), so that magnitude must fit the x and y (roll and pitch) ranges."""
    bad = []
    for k, d in enumerate(schedule):
        if d.get("none"):
            continue
        if frame == "world":
            w = to_world(d, 0.0, "world")
            for v in range_violations(w, vel_range):
                bad.append({"item": k, **v})
            continue
        lin = math.hypot(d["vx"], d["vy"])
        ang = math.hypot(d["wx"], d["wy"])
        for axis, mag in (("x", lin), ("y", lin), ("roll", ang), ("pitch", ang)):
            lo, hi = vel_range.get(axis, (0.0, 0.0))
            if mag > min(hi, -lo) + 1e-9:
                bad.append({"item": k, "axis": axis, "worst_case_abs": mag, "range": [lo, hi]})
        lo, hi = vel_range.get("yaw", (0.0, 0.0))
        if not (lo - 1e-9 <= d["wz"] <= hi + 1e-9):
            bad.append({"item": k, "axis": "yaw", "value": d["wz"], "range": [lo, hi]})
    return bad


def predict_fire_states(interval_s, step_dt, n_steps):
    """States j (= episode_length_buf after the step) at which the interval event fires. Emulates
    EventManager.apply(mode='interval'): float32 time_left -= dt, fire when time_left < 1e-6, then time_left = interval
    (range (a, a): rand * 0 + a). Reset also sets time_left = interval."""
    f32 = np.float32
    t = f32(interval_s)
    d = f32(step_dt)
    fires = []
    for j in range(1, n_steps + 1):
        t = f32(t - d)
        if t < f32(1e-6):
            fires.append(j)
            t = f32(interval_s)
    return fires


def describe_push(d, frame):
    if d.get("none"):
        return "none"
    parts = []
    names = {"vx": "vx", "vy": "vy", "wx": "wx", "wy": "wy", "wz": "wz"}
    for k in PUSH_KEYS:
        if d[k] != 0.0:
            parts.append(f"{names[k]} {d[k]:+.2f}")
    return " ".join(parts) + f" ({frame})"


# --- friction ------------------------------------------------------------------------------------------------------------
COMBINE_PRIORITY = {"average": 0, "min": 1, "multiply": 2, "max": 3}


def combine(a, b, mode_a, mode_b):
    """PhysX material combine: the mode with the higher priority wins (average < min < multiply < max)."""
    ma, mb = mode_a.lower(), mode_b.lower()
    mode = ma if COMBINE_PRIORITY[ma] >= COMBINE_PRIORITY[mb] else mb
    if mode == "average":
        return 0.5 * (a + b), mode
    if mode == "min":
        return min(a, b), mode
    if mode == "multiply":
        return a * b, mode
    return max(a, b), mode


def effective_friction(robot, ground, robot_mode, ground_mode):
    """robot / ground: dicts with static, dynamic. Returns combined static and dynamic friction and the mode used."""
    s, mode = combine(robot["static"], ground["static"], robot_mode, ground_mode)
    d, _ = combine(robot["dynamic"], ground["dynamic"], robot_mode, ground_mode)
    return {"static": s, "dynamic": d, "mode": mode}


# --- record -------------------------------------------------------------------------------------------------------------
COLUMNS = (
    ["step", "t_s", "base_x_m", "base_y_m", "base_z_w_m", "quat_w", "quat_x", "quat_y", "quat_z", "heading_rad",
     "linvel_world_x_mps", "linvel_world_y_mps", "linvel_world_z_mps",
     "linvel_body_x_mps", "linvel_body_y_mps", "linvel_body_z_mps",
     "angvel_body_x_radps", "angvel_body_y_radps", "angvel_body_z_radps",
     "gravity_body_z", "ground_z_m", "base_height_above_ground_m",
     "cmd_vx_mps", "cmd_vy_mps", "cmd_wz_radps", "base_contact", "fall_online",
     "push_index", "push_dv_world_x_mps", "push_dv_world_y_mps", "push_dw_world_x_radps", "push_dw_world_y_radps",
     "push_dw_world_z_radps"]
    + [f"{f}_contact" for f in FEET]
    + [f"{f}_normal_force_N" for f in FEET]
    + [f"{f}_speed_xy_mps" for f in FEET]
    + [f"{f}_probe_normal_N" for f in FEET]
    + [f"{f}_probe_friction_N" for f in FEET]
    + ["action_abs_mean"]
)
INT_COLUMNS = {"step", "base_contact", "fall_online", "push_index"} | {f"{f}_contact" for f in FEET}
# Columns the fall rule, the comparisons and the page read. Every one must be finite in every state before the fall: a missing
# support height before the fall is a measurement failure, never "no fall" (ASTRA 17d 2.3).
JUDGE_COLUMNS = (["t_s", "base_x_m", "base_y_m", "base_z_w_m", "quat_w", "quat_x", "quat_y", "quat_z", "heading_rad",
                  "linvel_world_x_mps", "linvel_world_y_mps", "linvel_world_z_mps",
                  "linvel_body_x_mps", "linvel_body_y_mps", "linvel_body_z_mps",
                  "angvel_body_x_radps", "angvel_body_y_radps", "angvel_body_z_radps",
                  "gravity_body_z", "ground_z_m", "base_height_above_ground_m", "cmd_vx_mps", "cmd_vy_mps", "cmd_wz_radps",
                  "base_contact", "fall_online", "push_index"]
                 + [f"{f}_contact" for f in FEET] + [f"{f}_normal_force_N" for f in FEET] + [f"{f}_speed_xy_mps" for f in FEET])
PUSH_COLUMNS = ["push_dv_world_x_mps", "push_dv_world_y_mps", "push_dw_world_x_radps", "push_dw_world_y_radps", "push_dw_world_z_radps"]
PROBE_COLUMNS = [f"{f}_probe_normal_N" for f in FEET] + [f"{f}_probe_friction_N" for f in FEET]
# NaN is a defined marker only in these: push columns on states without a push, probe columns when the probe is off,
# action_abs_mean at state 0 (no action yet). Anywhere else NaN is missing data.
NAN_MARKER_COLUMNS = set(PUSH_COLUMNS) | set(PROBE_COLUMNS) | {"action_abs_mean"}
BINARY_COLUMNS = ["base_contact", "fall_online"] + [f"{f}_contact" for f in FEET]


def write_record(path, rows):
    """rows: (T+1, len(COLUMNS)) float array. Integer columns written as integers, floats with 7 significant digits
    (the exact values go to traj.npz)."""
    rows = np.asarray(rows, dtype=np.float64)
    assert rows.ndim == 2 and rows.shape[1] == len(COLUMNS), rows.shape
    idx_int = [i for i, c in enumerate(COLUMNS) if c in INT_COLUMNS]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([("" if not np.isfinite(v) else str(int(round(v)))) if i in idx_int else
                        ("" if not np.isfinite(v) else f"{v:.7g}") for i, v in enumerate(r)])


def read_record(path):
    with open(path, encoding="utf-8") as f:
        rd = csv.reader(f)
        head = next(rd)
        data = [[float(x) if x != "" else float("nan") for x in r] for r in rd]
    return head, np.asarray(data, dtype=np.float64).reshape(-1, len(head))


def load_npz_rows(path):
    """traj.npz -> (columns, rows float64). Raises ValueError when the structure is not the record's."""
    with np.load(path, allow_pickle=False) as z:
        if sorted(z.files) != ["columns", "rows"]:
            raise ValueError(f"npz keys {sorted(z.files)}")
        cols = [str(c) for c in z["columns"]]
        rows = np.asarray(z["rows"])
    if rows.ndim != 2 or rows.dtype.kind != "f" or rows.shape[1] != len(cols):
        raise ValueError(f"npz rows shape {rows.shape} dtype {rows.dtype}")
    return cols, rows.astype(np.float64)


def as_cols(cols, rows):
    return {c: rows[:, i] for i, c in enumerate(cols)}


def first_nonfinite(col, columns, n):
    """First state index where any of columns is not finite (n when none)."""
    j = n
    for c in columns:
        bad = np.nonzero(~np.isfinite(col[c][:n]))[0]
        if bad.size:
            j = min(j, int(bad[0]))
    return j


def record_checks(csv_path, npz_path, n_rows, cmd, probe, fall_result=None):
    """Both record files, joined (ASTRA 17d 2.3). Parts, each True / False:
      csv_structure · npz_structure · csv_equals_npz (same NaN pattern, values to the CSV's 7 significant digits) · step_time ·
      judge_finite_before_fall (fall recomputed from the NPZ with the Q rule; every JUDGE_COLUMNS value finite before it) ·
      values_meaningful (0/1 flags, unit quaternion, |gravity z| <= 1, forces and speeds >= 0, heading in [-pi, pi],
      height above ground = base z - ground z, command = request; before the fall) · nan_markers (push columns NaN exactly off
      push states, action_abs_mean NaN only at state 0) · probe_columns (all NaN when the probe is off, finite and >= 0 before
      the fall when on) · fall_matches_result (result.json fall = recomputed)."""
    out = {"parts": {}, "detail": {}}
    P, D = out["parts"], out["detail"]
    try:
        head, a = read_record(csv_path)
        P["csv_structure"] = head == COLUMNS and a.shape == (n_rows, len(COLUMNS))
        D["csv_shape"] = list(a.shape)
    except (OSError, ValueError, StopIteration) as ex:
        P["csv_structure"], a = False, None
        D["csv_error"] = repr(ex)
    try:
        nc, b = load_npz_rows(npz_path)
        P["npz_structure"] = nc == COLUMNS and b.shape == (n_rows, len(COLUMNS))
        D["npz_shape"] = list(b.shape)
    except (OSError, ValueError, KeyError) as ex:
        P["npz_structure"], b = False, None
        D["npz_error"] = repr(ex)
    if not (P["csv_structure"] and P["npz_structure"]):
        for k in ("csv_equals_npz", "step_time", "judge_finite_before_fall", "values_meaningful", "nan_markers", "probe_columns",
                  "fall_matches_result"):
            P[k] = False
        out["ok"] = False
        return out
    same_nan = np.array_equal(np.isnan(a), np.isnan(b))
    fa, fb = np.nan_to_num(a, nan=0.0), np.nan_to_num(b, nan=0.0)
    err = np.abs(fa - fb) - (5e-7 * np.maximum(1.0, np.abs(fb)) + 1e-9)
    P["csv_equals_npz"] = bool(same_nan and (err <= 0).all())
    if not P["csv_equals_npz"]:
        D["csv_npz_first_mismatch"] = [int(x) for x in np.argwhere((err > 0) | (np.isnan(a) != np.isnan(b)))[0]]
    col = as_cols(COLUMNS, b)
    P["step_time"] = bool(np.array_equal(col["step"], np.arange(n_rows)) and np.allclose(col["t_s"], col["step"] * DT, atol=1e-9, rtol=0))
    with np.errstate(invalid="ignore"):
        fall = fall_summary(col["base_contact"] > 0.5, col["gravity_body_z"], col["base_height_above_ground_m"])
    jf = fall["j"] if fall["fell"] else n_rows
    D["fall_recomputed"] = fall
    jn = first_nonfinite(col, JUDGE_COLUMNS, n_rows)
    D["first_nonfinite_judge_state"] = None if jn == n_rows else jn
    P["judge_finite_before_fall"] = bool(jn >= jf)
    w = slice(0, min(jf, jn))
    with np.errstate(invalid="ignore"):
        q = np.sqrt(col["quat_w"][w] ** 2 + col["quat_x"][w] ** 2 + col["quat_y"][w] ** 2 + col["quat_z"][w] ** 2)
        mean = {
            "binary_flags": all(np.isin(col[c][w], (0.0, 1.0)).all() for c in BINARY_COLUMNS),
            "push_index_integer": bool(((col["push_index"][w] >= -1) & (col["push_index"][w] == np.round(col["push_index"][w]))).all()),
            "unit_quaternion": bool((np.abs(q - 1.0) <= 1e-3).all()),
            "gravity_z_range": bool((np.abs(col["gravity_body_z"][w]) <= 1.0 + 1e-3).all()),
            "forces_nonnegative": all((col[f"{f}_normal_force_N"][w] >= 0).all() for f in FEET),
            "speeds_nonnegative": all((col[f"{f}_speed_xy_mps"][w] >= 0).all() for f in FEET),
            "heading_range": bool((np.abs(col["heading_rad"][w]) <= math.pi + 1e-6).all()),
            "height_is_base_minus_ground": bool((np.abs(col["base_height_above_ground_m"][w] - (col["base_z_w_m"][w] - col["ground_z_m"][w])) <= 1e-5).all()),
            "command_is_request": all(bool((np.abs(col[c][w] - v) <= 1e-6).all()) for c, v in zip(("cmd_vx_mps", "cmd_vy_mps", "cmd_wz_radps"), cmd)),
        }
    D["values_meaningful"] = mean
    P["values_meaningful"] = all(mean.values())
    pushed = col["push_index"] >= 0
    pc_nan = np.isnan(np.stack([col[c] for c in PUSH_COLUMNS], axis=1))
    am = col["action_abs_mean"]
    P["nan_markers"] = bool(np.array_equal(pc_nan.all(axis=1), ~pushed) and (~pc_nan[pushed]).all() and np.isnan(am[0])
                            and np.isfinite(am[1:min(jf, n_rows)]).all())
    pr = np.stack([col[c] for c in PROBE_COLUMNS], axis=1)
    if probe:
        P["probe_columns"] = bool(np.isfinite(pr[:jf]).all() and (pr[:jf] >= 0).all())
    else:
        P["probe_columns"] = bool(np.isnan(pr).all())
    if fall_result is None:
        P["fall_matches_result"] = False
    else:
        P["fall_matches_result"] = (bool(fall_result.get("fell")) == fall["fell"] and fall_result.get("j") == fall["j"]
                                    and fall_result.get("reason") == fall["reason"])
    out["ok"] = all(P.values())
    return out


def compare_rows(ra, rb, n, cols=None):
    """Largest |a - b| over states 0..n-1 (ASTRA 17d 2.3). NaN equals NaN only in NAN_MARKER_COLUMNS; elsewhere a NaN on
    either side is a mismatch (inf). A missing column or fewer than n states is a mismatch. No tolerance: callers compare to 0."""
    cols = [c for c in COLUMNS if c not in PROBE_COLUMNS] if cols is None else cols
    m = 0.0
    for c in cols:
        if c not in ra or c not in rb or len(ra[c]) < n or len(rb[c]) < n:
            return float("inf")
        a, b = np.asarray(ra[c][:n], float), np.asarray(rb[c][:n], float)
        na, nb = np.isnan(a), np.isnan(b)
        if c in NAN_MARKER_COLUMNS:
            if not np.array_equal(na, nb):
                return float("inf")
            ok = ~na
            if ok.any():
                m = max(m, float(np.abs(a[ok] - b[ok]).max()))
        else:
            if na.any() or nb.any() or not (np.isfinite(a).all() and np.isfinite(b).all()):
                return float("inf")
            if n:
                m = max(m, float(np.abs(a - b).max()))
    return m


# --- statistics (descriptive, one predefined episode: not a performance claim) ------------------------------------------
def _q_metrics():
    if EVAL not in sys.path:
        sys.path.insert(0, EVAL)
    import q_metrics
    return q_metrics


def fall_summary(base_contact, grav_z, hag, dt=DT):
    """Q rule (q_metrics.fall_index): base contact > 1 N (the training termination), tilt > 60 deg held 0.2 s, or the base
    below the support surface. Returns the first invalid state index, its time and the reason. The caller must check that
    the inputs are finite before that index (record_checks does): q_metrics skips a NaN height."""
    Q = _q_metrics()
    j, why = Q.fall_index(np.asarray(base_contact, bool), np.asarray(grav_z, float), np.asarray(hag, float), dt)
    n = len(base_contact)
    return {"fell": bool(j < n), "j": int(j) if j < n else None, "t_s": float(j * dt) if j < n else None, "reason": why,
            "rule": "q_metrics.fall_index (n50): base contact > 1 N | tilt > 60 deg for 0.2 s | base below support"}


def push_response(col, events, fall_j=None, dt=DT, window_s=2.0, settle_v=0.10, settle_hold_s=0.25):
    """Per applied push, descriptive (one episode, ASTRA 17d 7): body lateral speed at the push, peak |body vy| inside the
    window, and the settle time = first state from which |body vy| < settle_v holds over a timestamp span >= settle_hold_s
    (t_s values, not a sample count). Everything is right-censored at the next applied push and at the fall: when the
    condition is not met before them, settle_t_s is None and settle_censored_by names the censor. The sideways displacement
    needs the whole window before the censor."""
    vy, t = col["linvel_body_y_mps"], col["t_s"]
    x, y, hd = col["base_x_m"], col["base_y_m"], col["heading_rad"]
    n = len(vy)
    pushes = sorted(int(e["state_j"]) for e in events if e.get("applied"))
    w = int(round(window_s / dt))
    out = []
    for e in events:
        if not e.get("applied"):
            continue
        j0 = int(e["state_j"])
        cands = [(n, "end of record")] + [(j, "next push") for j in pushes if j > j0][:1]
        if fall_j is not None:
            cands.append((int(fall_j), "fall"))
        end, why = min(cands)
        r = {"index": e["index"], "state_j": j0, "t_s": float(t[j0]) if j0 < n else j0 * dt, "censor_state": end, "censor": why}
        if j0 >= end:
            r["note"] = "at or after the censor (fall)"
            out.append(r)
            continue
        j1 = min(end, j0 + w + 1)
        r["vy_body_at_push_mps"] = float(vy[j0])
        r["peak_abs_vy_body_mps"] = float(np.abs(vy[j0:j1]).max())
        r["peak_window_censored"] = bool(j0 + w + 1 > end)
        settle, start = None, None
        for k in range(j0, end):
            if np.isfinite(vy[k]) and abs(vy[k]) < settle_v:
                start = k if start is None else start
                if t[k] - t[start] >= settle_hold_s - 1e-9:
                    settle = start
                    break
            else:
                start = None
        r["settle_t_s"] = None if settle is None else float(t[settle] - t[j0])
        r["settle_censored_by"] = None if settle is not None else why
        r["settle_rule"] = f"|body vy| < {settle_v} m/s over a t_s span >= {settle_hold_s} s, before the next push or the fall"
        if j0 + w < end:
            c, s = math.cos(hd[j0]), math.sin(hd[j0])
            dx, dy = x[j0 + w] - x[j0], y[j0 + w] - y[j0]
            r["sideways_after_window_m"] = float(-s * dx + c * dy)
            r["window_s"] = window_s
        else:
            r["sideways_after_window_m"] = None
        out.append(r)
    return out


def walk_summary(col, fall_j=None, dt=DT, skip_s=1.0):
    """Mean body velocities after the first second (until the fall), foot speed while in contact, probe force ratio."""
    n = len(col["t_s"])
    j0, j1 = int(round(skip_s / dt)), (n if fall_j is None else fall_j)
    out = {"window": [j0, j1]}
    if j1 - j0 < 5:
        out["note"] = "too short"
        return out
    out["mean_vx_body_mps"] = float(np.mean(col["linvel_body_x_mps"][j0:j1]))
    out["mean_vy_body_mps"] = float(np.mean(col["linvel_body_y_mps"][j0:j1]))
    out["mean_wz_body_radps"] = float(np.mean(col["angvel_body_z_radps"][j0:j1]))
    out["mae_vx_mps"] = float(np.mean(np.abs(col["linvel_body_x_mps"][j0:j1] - col["cmd_vx_mps"][j0:j1])))
    sp = np.concatenate([col[f"{f}_speed_xy_mps"][j0:j1][col[f"{f}_contact"][j0:j1] > 0.5] for f in FEET])
    out["contact_foot_speed_samples"] = int(sp.size)
    if sp.size:
        out["contact_foot_speed_median_mps"] = float(np.median(sp))
        out["contact_foot_speed_p95_mps"] = float(np.percentile(sp, 95))
    ratios = []
    for f in FEET:
        nn, ff = col[f"{f}_probe_normal_N"][j0:j1], col[f"{f}_probe_friction_N"][j0:j1]
        m = np.isfinite(nn) & np.isfinite(ff) & (nn > 5.0)
        ratios.append(ff[m] / nn[m])
    rr = np.concatenate(ratios) if ratios else np.zeros(0)
    out["probe_force_ratio_samples"] = int(rr.size)
    if rr.size:
        out["probe_force_ratio_max"] = float(rr.max())
        out["probe_force_ratio_p99"] = float(np.percentile(rr, 99))
        out["probe_force_ratio_p95"] = float(np.percentile(rr, 95))
        out["probe_rule"] = ("descriptive force statistic: |sum of friction forces| / |sum of normal forces| per foot against "
                             "/World/ground, normal > 5 N. Not a friction coefficient: sticking samples stay below it and "
                             "several contacts and the integration step mix in (ASTRA 17d 5)")
    return out


# --- mp4 container ----------------------------------------------------------------------------------------------------------
def top_level_boxes(path, limit=64):
    """Top-level ISO BMFF boxes in file order."""
    out = []
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        pos = 0
        while pos < size and len(out) < limit:
            f.seek(pos)
            h = f.read(8)
            if len(h) < 8:
                break
            n = int.from_bytes(h[:4], "big")
            typ = h[4:8].decode("latin-1")
            if n == 1:
                n = int.from_bytes(f.read(8), "big")
            elif n == 0:
                n = size - pos
            if n < 8:
                break
            out.append(typ)
            pos += n
    return out


def faststart_ok(path):
    b = top_level_boxes(path)
    return "moov" in b and "mdat" in b and b.index("moov") < b.index("mdat")


# --- attempt validation (driver) -------------------------------------------------------------------------------------------
# Execution gate (lead 10/13 20:06): isaac_slot_v3 + usd_isolate_run_v3 (written by another sub-task). One path constant each,
# so a rename touches one line; the slot check reads the isolation runner's file name from here.
SLOT_SCRIPT = os.path.join(EVAL, "isaac_slot_v3.py")
ISOLATE_SCRIPT = os.path.join(EVAL, "usd_isolate_run_v3.py")
SLOT_VERSION = "v3"
EXPECTED_CONVERSIONS = 1  # the Go2 URDF -> USD conversion; the generated flat terrain is a mesh, not a converter
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FP_REQUIRED = ("init_root_pose", "init_joint_pos", "body_masses", "com", "motor_zero_offset", "robot_material")
FP_PATTERNS = (r"^actuator_.+_stiffness$", r"^actuator_.+_damping$")
TERRAIN_MESH_PATH = "/World/ground/terrain/mesh"


def _load_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _finite_list(v, n):
    return isinstance(v, list) and len(v) == n and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)


def fingerprint_problems(fp):
    """Required keys, actuator keys, every value a sha256 hex string. An empty fingerprint is a problem, not a match."""
    if not isinstance(fp, dict) or not fp:
        return ["fingerprint missing or empty"]
    probs = [f"missing {k}" for k in FP_REQUIRED if k not in fp]
    probs += [f"no key matching {p}" for p in FP_PATTERNS if not any(re.match(p, k) for k in fp)]
    probs += [f"{k} is not a sha256" for k, v in fp.items() if not (isinstance(v, str) and HEX64.match(v))]
    return probs


def terrain_problems(entries):
    """Terrain mesh entries: present, the generated terrain mesh among them, points and faces > 0, local geometry hash and
    world hash (world transform applied) as sha256, the 4 x 4 world transform finite."""
    if not isinstance(entries, list) or not entries:
        return ["terrain mesh list missing or empty"]
    probs, paths = [], []
    for e in entries:
        if not isinstance(e, dict):
            probs.append("terrain entry is not an object")
            continue
        paths.append(e.get("path"))
        if not (isinstance(e.get("points"), int) and e["points"] > 0 and isinstance(e.get("faces"), int) and e["faces"] > 0):
            probs.append(f"{e.get('path')}: points / faces")
        for k in ("geom_sha256", "world_sha256"):
            if not (isinstance(e.get(k), str) and HEX64.match(e[k])):
                probs.append(f"{e.get('path')}: {k}")
        if not _finite_list(e.get("xform_world"), 16):
            probs.append(f"{e.get('path')}: xform_world")
    if TERRAIN_MESH_PATH not in paths:
        probs.append(f"{TERRAIN_MESH_PATH} not in the terrain entries")
    return probs


def allowed_train_diff_paths(obs_noise=False, physx_small=False, sim_device="cuda:0"):
    """Differences between the evaluation config and the training env.yaml that this tool makes on purpose. Anything else
    in observations · actions · decimation · sim · scene/robot fails the attempt."""
    a = {"scene/robot/prim_path"}  # env.yaml stores the resolved regex path, the config the template
    if not obs_noise:
        a |= {"observations/policy/enable_corruption", "observations/single_obs/enable_corruption"}
    if physx_small:
        a |= {"sim/physx/gpu_max_rigid_patch_count", "sim/physx/gpu_collision_stack_size"}
    if sim_device != "cuda:0":
        a.add("sim/device")
    return a


TRAIN_CONTRACT_GROUPS = ("observations", "actions", "decimation", "sim", "scene/robot")


def contract_problems(tc, allowed):
    if not isinstance(tc, dict) or not isinstance(tc.get("diffs"), dict):
        return ["train_contract missing"]
    probs = [f"group {g} not compared" for g in TRAIN_CONTRACT_GROUPS if g not in tc["diffs"]]
    for g, lst in tc["diffs"].items():
        for s in lst:
            if str(s).split(": ", 1)[0] not in allowed:
                probs.append(str(s)[:300])
    return probs


def eval_env_problems(ev, want):
    """The evaluation env as built (sim dt, step dt, decimation, action joints and scales) against the training env.yaml."""
    if not isinstance(ev, dict):
        return ["eval_env missing"]
    probs = []
    for k in ("physics_dt", "step_dt"):
        if not (isinstance(ev.get(k), (int, float)) and abs(ev[k] - want[k]) <= 1e-9):
            probs.append(f"{k} {ev.get(k)} != {want[k]}")
    if ev.get("decimation") != want["decimation"]:
        probs.append(f"decimation {ev.get('decimation')} != {want['decimation']}")
    if ev.get("action_joint_names") != want["action_joint_names"]:
        probs.append("action joint names / order")
    sc = ev.get("action_scale")
    if not (_finite_list(sc, len(want["action_scale"])) and all(abs(a - b) <= 1e-9 for a, b in zip(sc, want["action_scale"]))):
        probs.append(f"action scale {sc}")
    return probs


def push_checks(events, schedule, frame, vel_range, col, n_rows):
    """Each recorded push event against the frozen schedule and the record (ASTRA 17d 2.4). Returns {part: [problems]}:
      order_and_request: event k is the k-th firing, state_j increasing, applied exactly where the schedule has an item,
                         the stored request equals the schedule item and its frame
      direction:         the requested world delta equals to_world(schedule item, recorded heading, frame) (6 finite numbers)
      measured:          before / after root velocities finite, after - before = measured = requested
      range:             every world component inside the training velocity_range
      record_rows:       the record row at state_j has push_index k and the delta; no other row has a push index; t = j * dt"""
    P = {k: [] for k in ("order_and_request", "direction", "measured", "range", "record_rows")}
    if not isinstance(events, list):
        P["order_and_request"].append("events missing")
        return P
    last = 0
    applied_states = []
    for k, e in enumerate(events):
        if not isinstance(e, dict) or e.get("index") != k:
            P["order_and_request"].append(f"event {k}: index")
            continue
        j = e.get("state_j")
        if not (isinstance(j, int) and last < j < n_rows):
            P["order_and_request"].append(f"event {k}: state_j {j}")
            continue
        last = j
        if abs(e.get("t_s", -1) - j * DT) > 1e-9:
            P["record_rows"].append(f"event {k}: t_s {e.get('t_s')} != {j * DT}")
        want = k < len(schedule) and not schedule[k]["none"]
        if bool(e.get("applied")) != want:
            P["order_and_request"].append(f"event {k}: applied {e.get('applied')} but schedule {'has' if want else 'has no'} item")
            continue
        if not want:
            continue
        applied_states.append(j)
        req = e.get("request") or {}
        if any(abs(float(req.get(key, float("nan"))) - schedule[k][key]) > 1e-12 for key in PUSH_KEYS) or e.get("frame") != frame:
            P["order_and_request"].append(f"event {k}: request / frame differ from the schedule")
        hd = e.get("heading_rad")
        w_req = e.get("dv_world_requested")
        if not (isinstance(hd, (int, float)) and math.isfinite(hd) and _finite_list(w_req, 6)):
            P["direction"].append(f"event {k}: heading / requested delta not finite or not 6 numbers")
            continue
        w = to_world(schedule[k], hd, frame)
        if max(abs(a - b) for a, b in zip(w_req, w)) > 1e-6:
            P["direction"].append(f"event {k}: requested {w_req} != schedule at heading {hd}: {w}")
        vb, va, wm = e.get("vel_w_before"), e.get("vel_w_after"), e.get("dv_world_measured")
        if not (_finite_list(vb, 6) and _finite_list(va, 6) and _finite_list(wm, 6)):
            P["measured"].append(f"event {k}: before / after / measured not 6 finite numbers")
        else:
            if max(abs((a - b) - m) for a, b, m in zip(va, vb, wm)) > 1e-6:
                P["measured"].append(f"event {k}: after - before != measured")
            if max(abs(m - x) for m, x in zip(wm, w)) > 1e-4:
                P["measured"].append(f"event {k}: measured {wm} != schedule delta {w}")
        bad = range_violations(w_req, vel_range)
        if bad:
            P["range"].append(f"event {k}: {bad}")
        r = {c: col[c][j] for c in ["push_index"] + PUSH_COLUMNS}
        expect_row = [w[0], w[1], w[3], w[4], w[5]]
        if r["push_index"] != k or any(not math.isfinite(r[c]) or abs(r[c] - v) > 1e-5 for c, v in zip(PUSH_COLUMNS, expect_row)):
            P["record_rows"].append(f"event {k}: record row {j} {r} != index {k} delta {expect_row}")
    if not P["order_and_request"]:
        rows_pushed = [int(i) for i in np.nonzero(col["push_index"] >= 0)[0]]
        if rows_pushed != applied_states:
            P["record_rows"].append(f"record push rows {rows_pushed} != applied states {applied_states}")
    return P


def validate_attempt(adir, log_path, expect, audit_fn=None, probe_fn=None):
    """All checks of one Isaac attempt (one check per condition, so a failure names its cause). expect (rand_driver.expect_for):
    scene, attempt_id, kind, checkpoint_sha256, train_yaml_sha256, loaded_iter, cmd, duration_s, eval_seed, probe, friction,
    schedule, push_frame, push_expected, vel_range, train_env, usd_root, no_video. audit_fn(path) -> frame_audit.audit (every
    frame); probe_fn(path) -> video probe. Returns {"ok", "checks", "warnings"}."""
    checks = []

    def add(name, ok, detail=None, blocking=True):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "blocking": blocking})

    # --- execution gate record: isaac_slot_v3 + usd_isolate_run_v3, one conversion expected -------------------------------
    slot = _load_json(os.path.join(adir, "slot.json")) or {}
    s_cmd = [str(x).replace("\\", "/") for x in slot.get("cmd", [])]
    root = _norm(expect["usd_root"])
    fin = slot.get("usd_final")
    add("slot_record_exists", bool(slot), None)
    add("slot_version", slot.get("slot_version") == SLOT_VERSION, slot.get("slot_version"))
    add("slot_attempt_is_this_attempt", slot.get("attempt") == expect["attempt_id"], slot.get("attempt"))
    add("slot_rc_zero", slot.get("slot_rc") == 0, slot.get("slot_rc"))
    add("slot_child_rc_zero", slot.get("child_rc") == 0, slot.get("child_rc"))
    add("slot_scene_built", slot.get("state_at_release") == "scene_built", slot.get("state_at_release"))
    add("slot_expect_one_conversion", slot.get("expect_conversions") == str(EXPECTED_CONVERSIONS) and slot.get("expect_violation", None) is False,
        {"expect_conversions": slot.get("expect_conversions"), "expect_violation": slot.get("expect_violation")})
    add("slot_expected_conversions", isinstance(fin, list) and len(fin) == EXPECTED_CONVERSIONS and
        all(str(f).startswith(root + "/isaaclab/usd_") for f in fin), fin)
    add("slot_usd_inside_root", slot.get("usd_outside_root", None) == [] and slot.get("assigned_outside_root", None) == [],
        {"outside": slot.get("usd_outside_root"), "assigned_outside": slot.get("assigned_outside_root")})
    add("slot_usd_assigned", slot.get("usd_unassigned", None) == [] and slot.get("hint_without_assigned", None) is False
        and isinstance(fin, list) and sorted(slot.get("assigned") or []) == sorted(fin),
        {"unassigned": slot.get("usd_unassigned"), "assigned": slot.get("assigned"), "hint_without_assigned": slot.get("hint_without_assigned")})
    add("slot_no_conflicts", "conflicts" in slot and not slot["conflicts"], slot.get("conflicts"))
    add("slot_registry_ok", slot.get("registry_error", None) == "", slot.get("registry_error"))
    add("slot_not_killed", "killed" not in slot and "slot_error" not in slot, slot.get("killed") or slot.get("slot_error"))
    add("slot_usd_root_is_this_attempt", slot.get("usd_root") == root, {"record": slot.get("usd_root"), "expected": root})
    iso_name = "/" + os.path.basename(ISOLATE_SCRIPT)
    add("slot_cmd_isolated", any(c.endswith(iso_name) for c in s_cmd) and any(c.endswith("/q_rand.py") for c in s_cmd),
        [c for c in s_cmd if c.endswith(".py")])
    iso = _load_json(os.path.join(expect["usd_root"], "isolate_state.json")) or {}
    add("usd_isolate_patched", bool(iso.get("patched_by")) and iso.get("version") == SLOT_VERSION and iso.get("blocked", None) == [],
        {k: iso.get(k) for k in ("patched_by", "version", "blocked")})
    add("usd_isolate_no_warnings", not iso.get("warnings"), iso.get("warnings"), blocking=False)
    guard = _load_json(os.path.join(adir, "guard.json"))
    add("guard_record", guard is not None and guard.get("exit_code") == 0 and not guard.get("stopped_by_guard"),
        None if guard is None else {k: guard.get(k) for k in ("exit_code", "stopped_by_guard", "min_free_mib", "max_used_mib", "wall_s", "gpu_uuid")})
    # --- log ------------------------------------------------------------------------------------------------------------------
    log = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            log = f.read()
    add("log_exists", bool(log), log_path)
    add("log_no_traceback", "Traceback (most recent call last)" not in log, None)
    add("log_no_fail_line", "[RAND] FAIL" not in log, None)
    dones = DONE_RE.findall(log)
    add("log_done_line_this_attempt", dones == [(expect["scene"], expect["attempt_id"])], dones)
    # --- result against the request ----------------------------------------------------------------------------------------
    res = _load_json(os.path.join(adir, "result.json"))
    add("result_json", res is not None and res.get("schema") == RESULT_SCHEMA, None)
    if res is None:
        return {"ok": False, "checks": checks, "warnings": []}
    same = {k: (res.get(k), expect[k]) for k in ("scene", "attempt_id", "kind", "checkpoint_sha256", "loaded_iter", "eval_seed")}
    same["friction_probe"] = (res.get("friction_probe"), expect["probe"])
    add("result_matches_request", all(a == b for a, b in same.values()), same)
    add("result_cmd_duration", list(res.get("cmd", [])) == list(expect["cmd"]) and
        abs(res.get("duration_s", -1) - expect["duration_s"]) < 1e-9, {"cmd": res.get("cmd"), "duration_s": res.get("duration_s")})
    add("train_yaml_is_request", res.get("train_yaml_sha256") == expect["train_yaml_sha256"], res.get("train_yaml_sha256"))
    tcp = contract_problems(res.get("train_contract"), allowed_train_diff_paths())
    add("train_contract_kept", not tcp, tcp[:20])
    evp = eval_env_problems(res.get("eval_env"), expect["train_env"])
    add("eval_env_is_training", not evp, evp)
    fpp = fingerprint_problems(res.get("fingerprint"))
    add("fingerprint_complete", not fpp, fpp[:20])
    tp = terrain_problems(res.get("terrain_mesh"))
    add("terrain_complete", not tp, tp[:20])
    # --- record: CSV and NPZ, joined; fall recomputed -------------------------------------------------------------------------
    T = int(round(expect["duration_s"] / DT))
    rc = record_checks(os.path.join(adir, "record.csv"), os.path.join(adir, "traj.npz"), T + 1, expect["cmd"], expect["probe"],
                       res.get("fall"))
    for part, ok in rc["parts"].items():
        add(f"record_{part}", ok, rc["detail"] if not ok else None)
    cr = res.get("checks_run", {})
    add("command_seen_by_policy", cr.get("obs_single_cmd_vs_target_max_abs", 1.0) <= 1e-6 and
        cr.get("obs_history_latest_cmd_vs_target_max_abs", 1.0) <= 1e-6, cr)
    add("finite_actions_obs", cr.get("nonfinite_action_or_obs_count", 1) == 0, None)
    cp = res.get("checks_pre", {})
    add("student_path_only", cp.get("teacher_input_randomized_max_abs_action_change", 1.0) <= 1e-6 and
        cp.get("manual_student_path_vs_act_inference_max_abs", 1.0) <= 1e-5, cp)
    mt = res.get("material_readback", {}).get("robot_tensor", {})
    fr = expect["friction"]
    mat_ok = bool(mt) and all(abs(mt.get(f"{k}_min", -9) - fr[k]) <= 1e-6 and abs(mt.get(f"{k}_max", -9) - fr[k]) <= 1e-6
                              for k in ("static", "dynamic", "restitution"))
    add("robot_material_readback_equals_request", mat_ok, {"readback": mt, "request": fr})
    add("ground_material_read", bool(res.get("material_readback", {}).get("ground_usd", {}).get("friction_combine_mode")),
        res.get("material_readback", {}).get("ground_usd"))
    # --- pushes against the frozen schedule -----------------------------------------------------------------------------------
    ev = res.get("push", {}).get("events", [])
    applied = [e for e in ev if isinstance(e, dict) and e.get("applied")]
    add("push_count", len(applied) == expect["push_expected"], {"applied": len(applied), "expected": expect["push_expected"]})
    if rc["parts"].get("npz_structure"):
        col = as_cols(*load_npz_rows(os.path.join(adir, "traj.npz")))
        pc = push_checks(ev, expect["schedule"], expect["push_frame"], expect["vel_range"], col, T + 1)
    else:
        pc = {k: ["record unreadable"] for k in ("order_and_request", "direction", "measured", "range", "record_rows")}
    for part, probs in pc.items():
        add(f"push_{part}", not probs, probs[:10])
    pred = res.get("push", {}).get("predicted_fire_states", [])
    fired = [e.get("state_j") for e in ev if isinstance(e, dict)]
    # not blocking: a wrong time prediction is an error of predict_fire_states; the order and the direction above are required
    add("push_fire_states_as_predicted", fired == pred[:len(fired)] and len(fired) == len(pred), {"fired": fired, "predicted": pred},
        blocking=False)
    # --- videos -----------------------------------------------------------------------------------------------------------------
    if expect.get("no_video"):
        add("video_skipped", True, "no_video")
    else:
        v = res.get("video", {})
        mp, wp = os.path.join(adir, v.get("master", "-")), os.path.join(adir, v.get("web", "-"))
        add("video_files", os.path.exists(mp) and os.path.exists(wp), {"master": mp, "web": wp})
        if os.path.exists(mp) and os.path.exists(wp) and audit_fn is not None:
            am, aw = audit_fn(mp), audit_fn(wp)
            add("frame_gate_master_all_frames", am["bad"] == 0 and am["n"] == T + 1, {k: am[k] for k in ("n", "bad", "dark", "flat", "blue", "min_std", "max_blue", "min_mean")})
            n30 = int(round(expect["duration_s"] * 30))
            add("frame_gate_web_all_frames", aw["bad"] == 0 and abs(aw["n"] - n30) <= 2, {k: aw[k] for k in ("n", "bad", "dark", "flat", "blue", "min_std", "max_blue", "min_mean")})
        if os.path.exists(wp) and probe_fn is not None:
            pr = probe_fn(wp)
            add("web_h264_720p_30fps", pr.get("codec") == "h264" and pr.get("height") == 720 and pr.get("width") == 1280 and
                abs(pr.get("fps", 0) - 30.0) < 0.01, pr)
            add("web_faststart", faststart_ok(wp), top_level_boxes(wp)[:6])
        add("stills", all(os.path.exists(os.path.join(adir, s)) for s in v.get("stills", [])) and len(v.get("stills", [])) > 0, v.get("stills"))
    return {"ok": all(c["ok"] for c in checks if c["blocking"]), "checks": checks,
            "warnings": [c["name"] for c in checks if not c["ok"] and not c["blocking"]]}


# --- commands (driver) ---------------------------------------------------------------------------------------------------------
def scan_dirs():
    """Log folders of the Isaac runs of the same night (isaac_slot --scan_dirs): ours and the branch / unseen runs."""
    return ",".join([OUT_RAND, os.path.join(EVAL, "out_branch"), os.path.join(EVAL, "out_uncr")])


def slot_guard_cmd(py, log, slot_json, guard_json, script_args, usd_root, attempt_id, stop_file="", deadline=0.0,
                   gpu=1, min_free_mib=4096):
    """SLOT_SCRIPT (per-attempt USD root, attempt id, lock, registry, scan, stop file, deadline) -> gpu_guard (GPU 1 floor) ->
    ISOLATE_SCRIPT (conversion folder under the USD root, refused elsewhere) -> q_rand.py."""
    return [py, SLOT_SCRIPT, "--watch_log", log, "--record", slot_json,
            "--usd_root", usd_root, "--attempt", attempt_id,
            "--lock", os.path.join(EVAL, "slot", "isaac_convert.lock"),
            "--registry", os.path.join(EVAL, "slot", "isaac_usd_registry.json"),
            "--scan_dirs", scan_dirs(), "--stop_file", stop_file, "--deadline", repr(float(deadline)),
            "--expect_conversions", str(EXPECTED_CONVERSIONS), "--",
            py, os.path.join(EVAL, "gpu_guard.py"), "--gpu", str(gpu), "--min_free_mib", str(min_free_mib),
            "--log", log, "--summary", guard_json, "--",
            py, ISOLATE_SCRIPT, os.path.join(HERE, "q_rand.py")] + list(script_args)


def child_env():
    return dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES",
                PYTHONUNBUFFERED="1")
