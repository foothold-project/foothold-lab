# Pure helpers for the randomization scene videos (no Isaac import; tested on CPU by test_rand_scenes.py).
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
    }


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
CORE_FINITE = ["t_s", "base_x_m", "base_y_m", "base_z_w_m", "linvel_body_x_mps", "linvel_body_y_mps",
               "angvel_body_z_radps", "gravity_body_z", "cmd_vx_mps"]


def write_record(path, rows):
    """rows: (T+1, len(COLUMNS)) float array. Integer columns written as integers, floats with 7 significant digits
    (the exact float32 arrays go to traj.npz)."""
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


def record_checks(path, n_rows):
    head, a = read_record(path)
    out = {"columns_equal": head == COLUMNS, "rows": int(a.shape[0]), "rows_expected": int(n_rows)}
    if head == COLUMNS and a.shape[0] == n_rows:
        col = {c: a[:, i] for i, c in enumerate(head)}
        out["step_is_0_to_T"] = bool(np.array_equal(col["step"], np.arange(n_rows)))
        out["t_matches_step_dt"] = bool(np.allclose(col["t_s"], col["step"] * DT, atol=5e-7))
        out["core_finite"] = bool(all(np.isfinite(col[c]).all() for c in CORE_FINITE))
    out["ok"] = bool(out["columns_equal"] and out["rows"] == n_rows and out.get("step_is_0_to_T") and
                     out.get("t_matches_step_dt") and out.get("core_finite"))
    return out


# --- statistics (descriptive, one predefined episode: not a performance claim) ------------------------------------------
def _q_metrics():
    if EVAL not in sys.path:
        sys.path.insert(0, EVAL)
    import q_metrics
    return q_metrics


def fall_summary(base_contact, grav_z, hag, dt=DT):
    """Q rule (q_metrics.fall_index): base contact > 1 N (the training termination), tilt > 60 deg held 0.2 s, or the base
    below the support surface. Returns the first invalid state index, its time and the reason."""
    Q = _q_metrics()
    j, why = Q.fall_index(np.asarray(base_contact, bool), np.asarray(grav_z, float), np.asarray(hag, float), dt)
    n = len(base_contact)
    return {"fell": bool(j < n), "j": int(j) if j < n else None, "t_s": float(j * dt) if j < n else None, "reason": why,
            "rule": "q_metrics.fall_index (n50): base contact > 1 N | tilt > 60 deg for 0.2 s | base below support"}


def push_response(col, events, fall_j=None, dt=DT, window_s=2.0, settle_v=0.10, settle_hold_s=0.25):
    """Per applied push: body lateral speed right after, peak |body vy| within the window, time until |body vy| stays below
    settle_v for settle_hold_s, sideways displacement (perpendicular to the heading at the push) after the window.
    Only states before the fall are used."""
    vy = col["linvel_body_y_mps"]
    x, y, hd = col["base_x_m"], col["base_y_m"], col["heading_rad"]
    n = len(vy)
    end = n if fall_j is None else fall_j
    hold = int(round(settle_hold_s / dt))
    w = int(round(window_s / dt))
    out = []
    for e in events:
        if not e.get("applied"):
            continue
        j0 = int(e["state_j"])
        r = {"index": e["index"], "state_j": j0, "t_s": j0 * dt}
        if j0 >= end:
            r["note"] = "after the fall"
            out.append(r)
            continue
        j1 = min(end, j0 + w + 1)
        seg = np.abs(vy[j0:j1])
        r["vy_body_at_push_mps"] = float(vy[j0])
        r["peak_abs_vy_body_mps"] = float(seg.max())
        settle = None
        for k in range(j0, end - hold + 1):
            if np.all(np.abs(vy[k:k + hold]) < settle_v):
                settle = k
                break
        r["settle_t_s"] = None if settle is None else float((settle - j0) * dt)
        r["settle_rule"] = f"|body vy| < {settle_v} m/s held {settle_hold_s} s"
        if j0 + w < end:
            c, s = math.cos(hd[j0]), math.sin(hd[j0])
            dx, dy = x[j0 + w] - x[j0], y[j0 + w] - y[j0]
            r["sideways_after_window_m"] = float(-s * dx + c * dy)
            r["window_s"] = window_s
        out.append(r)
    return out


def walk_summary(col, fall_j=None, dt=DT, skip_s=1.0):
    """Mean body velocities after the first second (until the fall), foot speed while in contact."""
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
    out["probe_ratio_samples"] = int(rr.size)
    if rr.size:
        out["probe_friction_over_normal_max"] = float(rr.max())
        out["probe_friction_over_normal_p99"] = float(np.percentile(rr, 99))
        out["probe_friction_over_normal_p95"] = float(np.percentile(rr, 95))
        out["probe_rule"] = "|friction| / |normal| per foot vs /World/ground, normal > 5 N; under slip this is the effective dynamic friction, otherwise a lower bound"
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
def _load_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def validate_attempt(adir, log_path, expect, audit_fn=None, probe_fn=None):
    """All checks of one Isaac attempt. expect: scene, attempt_id, kind, checkpoint_sha256, loaded_iter, cmd, duration_s,
    eval_seed, friction (static, dynamic, restitution), push_expected (number of applied pushes) or 0, vel_range,
    no_video (bool). audit_fn(path) -> frame audit dict (frame_audit.audit with every frame); probe_fn(path) -> dict.
    Returns {"ok": bool, "checks": [{name, ok, detail}]}."""
    checks = []

    def add(name, ok, detail=None, blocking=True):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "blocking": blocking})

    # isaac_slot.py v2 record (one check per condition, so a failure names its cause)
    slot = _load_json(os.path.join(adir, "slot.json")) or {}
    s_cmd = [str(x).replace("\\", "/") for x in slot.get("cmd", [])]
    add("slot_record_exists", bool(slot), None)
    add("slot_attempt_is_this_attempt", slot.get("attempt") == expect["attempt_id"], slot.get("attempt"))
    add("slot_rc_zero", slot.get("slot_rc") == 0, slot.get("slot_rc"))
    add("slot_child_rc_zero", slot.get("child_rc") == 0, slot.get("child_rc"))
    add("slot_scene_built", slot.get("state_at_release") == "scene_built", slot.get("state_at_release"))
    add("slot_one_usd_folder", isinstance(slot.get("usd_final"), list) and len(slot["usd_final"]) == 1, slot.get("usd_final"))
    add("slot_usd_inside_root", slot.get("usd_outside_root", None) == [], slot.get("usd_outside_root"))
    add("slot_no_conflicts", "conflicts" in slot and not slot["conflicts"], slot.get("conflicts"))
    add("slot_usd_root_is_this_attempt", slot.get("usd_root") == _norm(expect["usd_root"]),
        {"record": slot.get("usd_root"), "expected": _norm(expect["usd_root"])})
    add("slot_cmd_isolated", any(c.endswith("/usd_isolate_run.py") for c in s_cmd) and any(c.endswith("/q_rand.py") for c in s_cmd),
        [c for c in s_cmd if c.endswith(".py")])
    iso = _load_json(os.path.join(expect["usd_root"], "isolate_state.json")) or {}
    add("usd_isolate_patched", bool(iso.get("patched_by")), iso.get("patched_by"))
    guard = _load_json(os.path.join(adir, "guard.json"))
    add("guard_record", guard is not None and guard.get("exit_code") == 0 and not guard.get("stopped_by_guard"),
        None if guard is None else {k: guard.get(k) for k in ("exit_code", "stopped_by_guard", "min_free_mib", "max_used_mib", "wall_s", "gpu_uuid")})
    log = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            log = f.read()
    add("log_exists", bool(log), log_path)
    add("log_no_traceback", "Traceback (most recent call last)" not in log, None)
    add("log_no_fail_line", "[RAND] FAIL" not in log, None)
    dones = DONE_RE.findall(log)
    add("log_done_line_this_attempt", dones == [(expect["scene"], expect["attempt_id"])], dones)
    res = _load_json(os.path.join(adir, "result.json"))
    add("result_json", res is not None and res.get("schema") == RESULT_SCHEMA, None)
    if res is None:
        return {"ok": False, "checks": checks}
    same = {k: (res.get(k), expect[k]) for k in ("scene", "attempt_id", "kind", "checkpoint_sha256", "loaded_iter", "eval_seed")}
    add("result_matches_request", all(a == b for a, b in same.values()), same)
    add("result_cmd_duration", list(res.get("cmd", [])) == list(expect["cmd"]) and
        abs(res.get("duration_s", -1) - expect["duration_s"]) < 1e-9, {"cmd": res.get("cmd"), "duration_s": res.get("duration_s")})
    T = int(round(expect["duration_s"] / DT))
    rec = os.path.join(adir, "record.csv")
    rc = record_checks(rec, T + 1) if os.path.exists(rec) else {"ok": False, "missing": rec}
    add("record_csv", rc["ok"], rc)
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
    ev = res.get("push", {}).get("events", [])
    applied = [e for e in ev if e.get("applied")]
    add("push_count", len(applied) == expect["push_expected"], {"applied": len(applied), "expected": expect["push_expected"]})
    rng = expect["vel_range"]
    in_rng = all(not range_violations(e["dv_world_requested"], rng) for e in applied)
    add("push_world_components_in_training_range", in_rng, None)
    meas = all(max(abs(a - b) for a, b in zip(e["dv_world_measured"], e["dv_world_requested"])) <= 1e-4 for e in applied)
    add("push_measured_equals_requested", meas,
        [max(abs(a - b) for a, b in zip(e["dv_world_measured"], e["dv_world_requested"])) for e in applied])
    pred = res.get("push", {}).get("predicted_fire_states", [])
    fired = [e["state_j"] for e in ev]
    # not blocking: a wrong prediction is an error of predict_fire_states, not of the run (the actual states are recorded)
    add("push_fire_states_as_predicted", fired == pred[:len(fired)] and len(fired) == len(pred), {"fired": fired, "predicted": pred},
        blocking=False)
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
    """isaac_slot.py v2 (per-attempt USD root, attempt id, lock, registry, scan, stop file, deadline) -> gpu_guard (GPU 1
    floor) -> usd_isolate_run.py (conversion folder under the USD root) -> q_rand.py."""
    return [py, os.path.join(EVAL, "isaac_slot.py"), "--watch_log", log, "--record", slot_json,
            "--usd_root", usd_root, "--attempt", attempt_id,
            "--lock", os.path.join(EVAL, "slot", "isaac_convert.lock"),
            "--registry", os.path.join(EVAL, "slot", "isaac_usd_registry.json"),
            "--scan_dirs", scan_dirs(), "--stop_file", stop_file, "--deadline", repr(float(deadline)), "--",
            py, os.path.join(EVAL, "gpu_guard.py"), "--gpu", str(gpu), "--min_free_mib", str(min_free_mib),
            "--log", log, "--summary", guard_json, "--",
            py, os.path.join(EVAL, "usd_isolate_run.py"), os.path.join(HERE, "q_rand.py")] + list(script_args)


def child_env():
    return dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES",
                PYTHONUNBUFFERED="1")
