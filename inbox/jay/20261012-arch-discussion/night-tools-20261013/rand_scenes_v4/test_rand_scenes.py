# CPU tests of the randomization scene tools (no Isaac, no GPU). Every gate is broken on purpose before it is trusted.
#   python test_rand_scenes.py            -> runs all tests, writes _eval/out_rand/_cpu_tests/<stamp>/results.json
#   python -m pytest test_rand_scenes.py  -> same tests under pytest
# Synthetic data only: frames are a brown block texture (passes the gate), black (dark), uniform grey (flat), a blue
# gradient (sky). Attempt folders are written by fake_q_rand(), which imitates q_rand.py's files (the Isaac run itself is
# not tested here).
import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rand_driver as RD  # noqa: E402
import rand_gate as RG  # noqa: E402
import rand_lib as RL  # noqa: E402
import rand_overlay as RO  # noqa: E402

STAMP = time.strftime("%Y%m%d-%H%M%S") + f"-p{os.getpid()}"
ROOT = os.path.join(RL.OUT_RAND, "_cpu_tests", STAMP)
os.makedirs(ROOT, exist_ok=True)
DR = RL.load_train_dr(RL.TRAIN_YAML_DEFAULT)
FACTS = {}  # values worth reporting (not pass/fail)


# --- synthetic frames and videos ------------------------------------------------------------------------------------------
def tex(seed=0):
    rng = np.random.default_rng(seed)
    base = rng.integers(60, 170, (720 // 8, 1280 // 8)).repeat(8, 0).repeat(8, 1)
    a = np.stack([base + 30, base + 10, base], axis=-1).astype(np.uint8)
    a[311:351, 564:604] = 235  # white "robot" at the projected base pixel of q_video (584, 331)
    return a


TEX = tex()


def good(i):
    return np.roll(TEX, shift=4 * i, axis=1)


def black():
    return np.zeros((720, 1280, 3), np.uint8)


def flat():
    return np.full((720, 1280, 3), 128, np.uint8)


def sky():
    y = np.linspace(0, 1, 720)[:, None]
    a = np.zeros((720, 1280, 3), np.float32)
    a[..., 0] = 60 + 80 * y  # gradient steep enough that the 3D-area std is > 6: refused by the blue test, not the flat one
    a[..., 1] = 120 + 60 * y
    a[..., 2] = 190 + 60 * y
    return a.astype(np.uint8)


def write_video(path, frames, fps=50):
    import imageio
    w = imageio.get_writer(path, fps=fps, codec="libx264", quality=8, macro_block_size=8)
    for f in frames:
        w.append_data(f)
    w.close()
    return path


def frames_with(n, bad):
    """n frames, bad: dict index -> callable producing the defective frame."""
    return [bad[i]() if i in bad else good(i) for i in range(n)]


# --- 1. push schedule ------------------------------------------------------------------------------------------------------
def test_push_schedule_parse():
    s = RL.parse_push_schedule("vy=+0.4;vy=-0.4;;vx=0.2,wz=0.5")
    assert [d["vy"] for d in s] == [0.4, -0.4, 0.0, 0.0] and s[2]["none"] and s[3]["vx"] == 0.2 and s[3]["wz"] == 0.5
    for bad in ("vq=1", "vy=1,vy=2"):
        try:
            RL.parse_push_schedule(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    assert RL.parse_push_schedule("") == []


def test_to_world_rotation():
    d = {"vx": 0.0, "vy": 0.4, "wx": 0.0, "wy": 0.0, "wz": 0.0}
    w0 = RL.to_world(d, 0.0, "heading")
    assert np.allclose(w0, [0, 0.4, 0, 0, 0, 0])
    w90 = RL.to_world(d, math.pi / 2, "heading")  # robot facing +y: its left is -x
    assert np.allclose(w90, [-0.4, 0, 0, 0, 0, 0], atol=1e-12)
    dx = {"vx": 0.3, "vy": 0.0, "wx": 0.0, "wy": 0.0, "wz": 0.0}
    assert np.allclose(RL.to_world(dx, math.pi, "heading"), [-0.3, 0, 0, 0, 0, 0], atol=1e-12)
    assert np.allclose(RL.to_world(d, 1.0, "world"), [0, 0.4, 0, 0, 0, 0])


def test_range_checks():
    rng = DR["push_velocity_range"]
    assert rng["x"] == [-0.4, 0.4] and rng["y"] == [-0.4, 0.4] and rng["yaw"] == [-0.6, 0.6], rng
    assert not RL.range_violations([0, 0.4, 0, 0, 0, 0], rng)
    assert RL.range_violations([0, 0.41, 0, 0, 0, 0], rng)[0]["axis"] == "y"
    assert RL.range_violations([0, 0, 0.1, 0, 0, 0], rng)[0]["axis"] == "z"  # z is not in the training range -> (0, 0)
    sch = RL.parse_push_schedule("vy=+0.4;vy=-0.4;vy=+0.4;vy=-0.4")
    assert not RL.plan_violations(sch, rng, "heading")
    comb = RL.parse_push_schedule("vx=0.3,vy=0.3")  # 0.424 at 45 deg of heading
    assert RL.plan_violations(comb, rng, "heading")
    assert not RL.plan_violations(comb, rng, "world")
    w45 = RL.to_world(comb[0], math.pi / 4, "heading")
    assert RL.range_violations(w45, rng)  # the runtime check catches what the plan check predicted


def test_predict_fire_states_vs_event_manager_arithmetic():
    """Same arithmetic as isaaclab EventManager.apply(mode='interval') with torch float32 on CPU."""
    import torch
    T = 1000
    pred = RL.predict_fire_states(4.0, 0.02, T)
    lo, hi = 4.0, 4.0
    tl = torch.rand(1) * (hi - lo) + lo
    fires = []
    for j in range(1, T + 1):
        tl -= 0.02
        if (tl < 1e-6).any():
            fires.append(j)
            tl[:] = torch.rand(1) * (hi - lo) + lo
    assert fires == pred, (fires, pred)
    FACTS["predicted_push_states_20s"] = pred
    FACTS["predicted_push_times_s"] = [round(j * 0.02, 2) for j in pred]


def test_train_dr_matches_yaml():
    assert DR["push_interval_s"] == [4.0, 4.0] and DR["push_func"].endswith("push_by_setting_velocity")
    assert DR["material_static_range"] == [0.0, 2.0] and DR["material_dynamic_range"] == [0.0, 2.0]
    assert DR["material_restitution_range"] == [0.0, 0.5] and DR["material_num_buckets"] == 64 and DR["material_make_consistent"]
    g = DR["ground_material"]
    assert g["static_friction"] == 1.0 and g["dynamic_friction"] == 1.0 and g["friction_combine_mode"] == "average", g
    FACTS["ground_material_yaml"] = g
    FACTS["sim_default_material_yaml"] = DR["sim_default_material"]


# --- 2. friction --------------------------------------------------------------------------------------------------------------
def test_effective_friction():
    r, gm = {"static": 0.2, "dynamic": 0.2}, {"static": 1.0, "dynamic": 1.0}
    assert RL.effective_friction(r, gm, "average", "average") == {"static": 0.6, "dynamic": 0.6, "mode": "average"}
    assert RL.effective_friction(r, gm, "min", "average")["static"] == 0.2
    assert RL.effective_friction(r, gm, "average", "max")["static"] == 1.0
    assert abs(RL.effective_friction(r, gm, "multiply", "min")["static"] - 0.2) < 1e-12
    assert RL.effective_friction({"static": 1.5, "dynamic": 1.5}, gm, "average", "average")["static"] == 1.25
    # what the training range means at the contact (robot 0..2, ground 1.0, average): 0.5..1.5
    FACTS["training_contact_friction_range_average"] = [RL.effective_friction({"static": v, "dynamic": v}, gm, "average", "average")["static"] for v in (0.0, 2.0)]
    FACTS["contact_friction_low_high_average"] = [RL.effective_friction({"static": v, "dynamic": v}, gm, "average", "average")["static"] for v in (0.2, 1.5)]


# --- 3. record ------------------------------------------------------------------------------------------------------------------
def synth_rows(T, kind="none", push_events=(), friction=1.0, probe=False):
    """Synthetic record. push_events: [(state_j, world delta 6-list)], the body lateral speed decays after each push."""
    col = {c: i for i, c in enumerate(RL.COLUMNS)}
    n = T + 1
    r = np.full((n, len(RL.COLUMNS)), np.nan)
    t = np.arange(n) * RL.DT
    r[:, col["step"]] = np.arange(n)
    r[:, col["t_s"]] = t
    vx = 0.5 * (1 - np.exp(-t / 0.5)) * (0.9 if friction < 0.5 else 1.0)
    vy = np.zeros(n)
    for j0, w in push_events:
        k = np.arange(n) - j0
        vy += np.where(k >= 0, w[1] * np.exp(-np.maximum(k, 0) * RL.DT / 0.3), 0.0)
    r[:, col["base_x_m"]] = np.cumsum(vx) * RL.DT
    r[:, col["base_y_m"]] = np.cumsum(vy) * RL.DT
    r[:, col["base_z_w_m"]] = 0.32
    r[:, col["quat_w"]], r[:, col["quat_x"]], r[:, col["quat_y"]], r[:, col["quat_z"]] = 1, 0, 0, 0
    r[:, col["heading_rad"]] = 0.0
    r[:, col["linvel_world_x_mps"]], r[:, col["linvel_world_y_mps"]], r[:, col["linvel_world_z_mps"]] = vx, vy, 0
    r[:, col["linvel_body_x_mps"]], r[:, col["linvel_body_y_mps"]], r[:, col["linvel_body_z_mps"]] = vx, vy, 0
    r[:, col["angvel_body_x_radps"]], r[:, col["angvel_body_y_radps"]], r[:, col["angvel_body_z_radps"]] = 0, 0, 0
    r[:, col["gravity_body_z"]] = -1.0
    r[:, col["ground_z_m"]] = 0.0
    r[:, col["base_height_above_ground_m"]] = 0.32
    r[:, col["cmd_vx_mps"]], r[:, col["cmd_vy_mps"]], r[:, col["cmd_wz_radps"]] = 0.5, 0.0, 0.0
    r[:, col["base_contact"]] = 0
    r[:, col["fall_online"]] = 0
    r[:, col["push_index"]] = -1
    for k, (j0, w) in enumerate(push_events):
        r[j0, col["push_index"]] = k
        for c, v in zip(RL.PUSH_COLUMNS, (w[0], w[1], w[3], w[4], w[5])):
            r[j0, col[c]] = v
    for i, f in enumerate(RL.FEET):
        c = ((np.arange(n) // 10 + i) % 2 == 0).astype(float)
        r[:, col[f"{f}_contact"]] = c
        r[:, col[f"{f}_normal_force_N"]] = 40 * c
        r[:, col[f"{f}_speed_xy_mps"]] = np.where(c > 0, 0.01 / max(friction, 0.1), 0.6)
        if probe:
            r[:, col[f"{f}_probe_normal_N"]] = 40 * c
            r[:, col[f"{f}_probe_friction_N"]] = 40 * c * min(0.3, 0.5 * friction)
    r[1:, col["action_abs_mean"]] = 0.3
    return r


def write_both(d, rows):
    os.makedirs(d, exist_ok=True)
    RL.write_record(os.path.join(d, "record.csv"), rows)
    np.savez(os.path.join(d, "traj.npz"), rows=rows, columns=np.array(RL.COLUMNS))
    return os.path.join(d, "record.csv"), os.path.join(d, "traj.npz")


def fall_of(rows):
    c = {name: rows[:, i] for i, name in enumerate(RL.COLUMNS)}
    return RL.fall_summary(c["base_contact"] > 0.5, c["gravity_body_z"], c["base_height_above_ground_m"])


def test_record_checks_csv_npz_and_meaning():
    """ASTRA 17d 2.3: both files, joined; judgement columns finite before the fall; meanings; probe NaN kept apart; fall
    recomputed. Each defect fails its own part."""
    rows = synth_rows(100)
    cmd = [0.5, 0.0, 0.0]
    d = os.path.join(ROOT, "rec_ok")
    cp, npp = write_both(d, rows)
    head, a = RL.read_record(cp)
    assert head == RL.COLUMNS and np.allclose(np.nan_to_num(a, nan=-9), np.nan_to_num(rows, nan=-9), rtol=1e-6, atol=1e-6)
    ok = RL.record_checks(cp, npp, 101, cmd, False, fall_of(rows))
    assert ok["ok"], ok
    assert not RL.record_checks(cp, npp, 1001, cmd, False, fall_of(rows))["ok"]
    res = {}

    def broken(name, fn, part, probe=False, fall=None, csv_rows=None, npz_rows=None):
        r = rows.copy()
        fn(r)
        dd = os.path.join(ROOT, f"rec_{name}")
        os.makedirs(dd, exist_ok=True)
        RL.write_record(os.path.join(dd, "record.csv"), r if csv_rows is None else csv_rows(r))
        np.savez(os.path.join(dd, "traj.npz"), rows=(r if npz_rows is None else npz_rows(r)), columns=np.array(RL.COLUMNS))
        out = RL.record_checks(os.path.join(dd, "record.csv"), os.path.join(dd, "traj.npz"), 101, cmd, probe,
                               fall if fall is not None else fall_of(r))
        failed = sorted(k for k, v in out["parts"].items() if not v)
        assert failed == sorted(part if isinstance(part, list) else [part]), (name, failed, out["detail"])
        res[name] = failed

    C = RL.COLUMNS.index

    def setv(c, j, v):
        def f(r):
            r[j, C(c)] = v
        return f
    broken("support_nan_both", lambda r: (r.__setitem__((slice(None), C("ground_z_m")), np.nan),
                                          r.__setitem__((slice(None), C("base_height_above_ground_m")), np.nan)), "judge_finite_before_fall")
    broken("height_nan_one_state", setv("base_height_above_ground_m", 40, np.nan), "judge_finite_before_fall")
    broken("contact_not_binary", setv("FL_foot_contact", 12, 2.0), "values_meaningful")
    broken("quat_not_unit", setv("quat_w", 12, 0.9), "values_meaningful")
    broken("height_not_base_minus_ground", setv("base_height_above_ground_m", 12, 0.5), "values_meaningful")
    broken("command_other", setv("cmd_vx_mps", 12, 0.4), "values_meaningful")
    broken("step_broken", setv("step", 5, 6), "step_time")
    broken("npz_only_x", lambda r: None, "csv_equals_npz", npz_rows=lambda r: (lambda q: (q.__setitem__((10, C("base_x_m")), q[10, C("base_x_m")] + 0.02), q)[1])(r.copy()))
    broken("probe_nan_while_on", lambda r: None, "probe_columns", probe=True)
    broken("probe_values_while_off", lambda r: r.__setitem__((slice(None), C("FL_foot_probe_normal_N")), 1.0), "probe_columns")
    broken("push_marker_without_push", setv("push_dv_world_x_mps", 30, 0.1), "nan_markers")
    broken("action_nan_mid", setv("action_abs_mean", 50, np.nan), "nan_markers")
    broken("fall_result_other", lambda r: None, "fall_matches_result", fall={"fell": True, "j": 50, "reason": "tilt60"})
    # after a fall, missing data is allowed (shown as a reference); before it, it is not
    def fall_then_nan(r):
        r[60, C("base_contact")] = 1
        r[61:, C("ground_z_m")] = np.nan
        r[61:, C("base_height_above_ground_m")] = np.nan
    rr = rows.copy()
    fall_then_nan(rr)
    cp2, np2 = write_both(os.path.join(ROOT, "rec_fall_then_nan"), rr)
    out = RL.record_checks(cp2, np2, 101, cmd, False, fall_of(rr))
    assert out["ok"] and out["detail"]["fall_recomputed"]["j"] == 60, out
    FACTS["record_defects_caught"] = res


def test_fall_summary_known():
    n = 501
    bc, gz, hag = np.zeros(n, bool), -np.ones(n), np.full(n, 0.3)
    assert not RL.fall_summary(bc, gz, hag)["fell"]
    bc2 = bc.copy()
    bc2[123] = True
    f = RL.fall_summary(bc2, gz, hag)
    assert f["fell"] and f["j"] == 123 and f["reason"] == "base_contact" and abs(f["t_s"] - 2.46) < 1e-9
    gz2 = gz.copy()
    gz2[50:60] = -0.3  # tilt > 60 deg for exactly 10 states (0.2 s)
    f = RL.fall_summary(bc, gz2, hag)
    assert f["fell"] and f["j"] == 50 and f["reason"] == "tilt60"
    gz3 = gz.copy()
    gz3[50:59] = -0.3  # 9 states: not a fall
    assert not RL.fall_summary(bc, gz3, hag)["fell"]
    hag2 = hag.copy()
    hag2[300] = -0.01
    assert RL.fall_summary(bc, gz, hag2)["reason"] == "below_support"
    hag3 = hag.copy()
    hag3[300] = np.nan  # the Q rule alone skips a NaN height: record_checks must refuse such a record (test above)
    assert not RL.fall_summary(bc, gz, hag3)["fell"]


def test_push_response_censored_and_timestamp_span():
    """ASTRA 17d 7: settle right-censored at the next push and the fall; the 0.25 s hold is a t_s span."""
    W = [0.0, 0.4, 0.0, 0.0, 0.0, 0.0]
    rows = synth_rows(1000, push_events=[(200, W)])
    c = {name: rows[:, i] for i, name in enumerate(RL.COLUMNS)}
    ev = [{"index": 0, "state_j": 200, "applied": True}]
    pr = RL.push_response(c, ev)[0]
    # vy = 0.4 exp(-t / 0.3) < 0.1 from k = 21 (0.42 s); the span 0.25 s is reached at k = 34 (0.26 s after 21)
    assert abs(pr["vy_body_at_push_mps"] - 0.4) < 1e-12 and abs(pr["peak_abs_vy_body_mps"] - 0.4) < 1e-12
    assert abs(pr["settle_t_s"] - 0.42) < 1e-9 and pr["settle_censored_by"] is None, pr
    assert abs(pr["sideways_after_window_m"] - (0.4 * 0.02 * np.exp(-np.arange(1, 101) * 0.02 / 0.3)).sum()) < 1e-9, pr
    # next push 20 states later: censored, no settle time, no sideways number
    ev2 = ev + [{"index": 1, "state_j": 220, "applied": True}]
    p2 = RL.push_response(c, ev2)[0]
    assert p2["settle_t_s"] is None and p2["settle_censored_by"] == "next push" and p2["sideways_after_window_m"] is None, p2
    # next push at 230: the span (needs state 234) is not reached before it -> censored (the old 12-sample rule said 0.42 s)
    p3 = RL.push_response(c, ev + [{"index": 1, "state_j": 230, "applied": True}])[0]
    assert p3["settle_t_s"] is None and p3["settle_censored_by"] == "next push", p3
    # fall at 225: censored by the fall
    p4 = RL.push_response(c, ev, fall_j=225)[0]
    assert p4["settle_t_s"] is None and p4["settle_censored_by"] == "fall", p4
    assert RL.push_response(c, ev, fall_j=150)[0]["note"].startswith("at or after")
    # exactly 13 samples (12 intervals, 0.24 s) under the threshold, then above: not settled
    c5 = {k: v.copy() for k, v in c.items()}
    c5["linvel_body_y_mps"][:] = 0.3
    c5["linvel_body_y_mps"][300:313] = 0.0
    p5 = RL.push_response(c5, [{"index": 0, "state_j": 290, "applied": True}])[0]
    assert p5["settle_t_s"] is None, p5
    c5["linvel_body_y_mps"][313] = 0.0  # 14 samples = 0.26 s
    p6 = RL.push_response(c5, [{"index": 0, "state_j": 290, "applied": True}])[0]
    assert abs(p6["settle_t_s"] - 0.20) < 1e-9, p6


def test_compare_rows_nan_is_not_equal():
    """ASTRA 17d 2.3: two NaN are not 'equal' outside the defined NaN markers."""
    rows = synth_rows(100)
    a = {name: rows[:, i] for i, name in enumerate(RL.COLUMNS)}
    b = {k: v.copy() for k, v in a.items()}
    assert RL.compare_rows(a, b, 101) == 0.0
    b["base_x_m"][10] += 0.02
    assert abs(RL.compare_rows(a, b, 101) - 0.02) < 1e-12 and RL.compare_rows(a, b, 10) == 0.0
    a2 = {k: v.copy() for k, v in a.items()}
    b2 = {k: v.copy() for k, v in a.items()}
    a2["ground_z_m"][:] = np.nan
    b2["ground_z_m"][:] = np.nan
    assert RL.compare_rows(a2, b2, 101) == float("inf")
    a3 = {k: v.copy() for k, v in a.items()}
    a3["push_dv_world_x_mps"][5] = 0.1  # marker column: NaN on one side only
    assert RL.compare_rows(a3, a, 101) == float("inf")
    del a3["heading_rad"]
    assert RL.compare_rows(a3, a, 101) == float("inf")


# --- 4. frame gate -----------------------------------------------------------------------------------------------------------------
def test_frame_check_known():
    assert RG.frame_check(good(0))[0]
    assert RG.frame_check(black())[1] == "dark"
    assert RG.frame_check(flat())[1] == "flat"
    assert RG.frame_check(sky())[1] == "blue"
    assert RG.robot_window_check(good(0), (584, 331))[0]
    assert RG.robot_window_check(good(0), (1400, 331))[1] == "robot_off_frame"
    b = good(0).copy()
    b[271:391, 524:644] = 0
    assert RG.robot_window_check(b, (584, 331))[1] == "robot_window_dark"


def test_capture_with_gate_retry_loop():
    log = []
    seq = [black(), good(1)]
    out = RG.capture_with_gate(lambda t: seq[t], (584, 331), 12, 30, log)
    assert np.array_equal(out, good(1)) and log == [(30, "dark", 1, True)]
    log = []
    RG.capture_with_gate(lambda t: good(2), (584, 331), 12, 5, log)
    assert log == []
    log = []
    try:
        RG.capture_with_gate(lambda t: sky(), (584, 331), 12, 20, log)
        raise AssertionError("sky accepted")
    except RG.FrameGateError as ex:
        assert "FRAME_GATE frame 20" in str(ex) and len(log) == 12 and not log[-1][3]


def test_video_gate_breaks_on_known_defects():
    sys.path.insert(0, RL.EVAL)
    import frame_audit
    n = 100
    cases = {
        "clean": ({}, 0),
        "odd_black": ({i: black for i in range(1, n, 2)}, 50),
        "sky_segment": ({i: sky for i in range(40, 60)}, 20),
        "single_black": ({37: black}, 1),
        "single_flat": ({10: flat}, 1),
    }
    res = {}
    for name, (bad, n_bad) in cases.items():
        frames = frames_with(n, bad)
        p = write_video(os.path.join(ROOT, f"gate_{name}.mp4"), frames)
        a = RG.audit(p)
        res[name] = {"n": a["n"], "bad": a["bad"], "dark": a["dark"], "flat": a["flat"], "blue": a["blue"]}
        assert a["n"] == n and a["bad"] == n_bad, (name, a)
        # the loop check agrees frame by frame with the file audit on the same frames
        loop_bad = [i for i, f in enumerate(frames) if not RG.frame_check(f)[0]]
        assert len(loop_bad) == n_bad and loop_bad == sorted(bad), (name, loop_bad)
        if name == "single_black":
            s4 = frame_audit.audit(p, fps=4)
            res[name]["sampled_4fps_bad"] = s4["bad"]
    assert res["odd_black"]["dark"] == 50 and res["sky_segment"]["blue"] == 20 and res["single_flat"]["flat"] == 1
    FACTS["gate_known_defects"] = res


def test_publish_accepts_clean_and_refuses_defects():
    d = os.path.join(ROOT, "publish")
    os.makedirs(d, exist_ok=True)
    m = write_video(os.path.join(d, "clean_master.mp4"), frames_with(151, {}))
    w = os.path.join(d, "clean_web.mp4")
    info = RG.publish(m, w, os.path.join(d, "rejected"), expect_master_frames=151)
    pr = info["web_probe"]
    assert pr["codec"] == "h264" and (pr["width"], pr["height"]) == (1280, 720) and abs(pr["fps"] - 30) < 0.01, pr
    assert info["web_faststart"] and RL.faststart_ok(w) and abs(pr["frames"] - 91) <= 1, pr
    FACTS["publish_clean_web"] = {k: pr[k] for k in ("codec", "width", "height", "fps", "frames", "bytes")} | {"crf": info["web_encode"]["crf"]}
    # defective master: refused, moved, no web copy
    mb = write_video(os.path.join(d, "bad_master.mp4"), frames_with(151, {i: black for i in range(1, 151, 2)}))
    wb = os.path.join(d, "bad_web.mp4")
    try:
        RG.publish(mb, wb, os.path.join(d, "rejected"))
        raise AssertionError("defective master published")
    except RG.FrameGateError:
        assert not os.path.exists(mb) and not os.path.exists(wb) and os.path.exists(os.path.join(d, "rejected", "bad_master.mp4"))
    # wrong frame count: refused
    mc = write_video(os.path.join(d, "short_master.mp4"), frames_with(150, {}))
    try:
        RG.publish(mc, os.path.join(d, "short_web.mp4"), os.path.join(d, "rejected"), expect_master_frames=151)
        raise AssertionError("short master published")
    except RG.FrameGateError:
        pass

    # defect introduced in the web copy only: the web gate refuses
    def bad_web(src, dst):
        write_video(dst, [black() if i == 45 else good(i) for i in range(90)], fps=30)
        return {"crf": -1}
    m2 = write_video(os.path.join(d, "ok2_master.mp4"), frames_with(151, {}))
    w2 = os.path.join(d, "ok2_web.mp4")
    try:
        RG.publish(m2, w2, os.path.join(d, "rejected"), make_web=bad_web)
        raise AssertionError("defective web copy published")
    except RG.FrameGateError as ex:
        assert "bad frames 1/90" in str(ex) and not os.path.exists(w2)

    # web copy without faststart and at 50 fps: refused
    def slow_web(src, dst):
        import subprocess
        subprocess.run([RG.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", dst], check=True)
        return {"crf": -1}
    m3 = write_video(os.path.join(d, "ok3_master.mp4"), frames_with(151, {}))
    w3 = os.path.join(d, "ok3_web.mp4")
    try:
        RG.publish(m3, w3, os.path.join(d, "rejected"), make_web=slow_web)
        raise AssertionError("non-faststart 50 fps web copy published")
    except RG.FrameGateError as ex:
        assert "not faststart" in str(ex) and "format" in str(ex), str(ex)


def test_faststart_detector():
    d = os.path.join(ROOT, "publish")
    src = os.path.join(d, "clean_master.mp4")
    import subprocess
    a, b = os.path.join(ROOT, "fs_yes.mp4"), os.path.join(ROOT, "fs_no.mp4")
    subprocess.run([RG.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-c", "copy", "-movflags", "+faststart", a], check=True)
    subprocess.run([RG.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-c", "copy", b], check=True)
    assert RL.faststart_ok(a) and not RL.faststart_ok(b), (RL.top_level_boxes(a), RL.top_level_boxes(b))


# --- 5. overlay -------------------------------------------------------------------------------------------------------------------
def overlay_info(**kw):
    info = {"run_line": "E1 student · model_20000 · 평지 · 시드 1000 · 같은 출발 · 사전 정한 1판 (결과로 고르지 않음)",
            "scene_line": "밀기 · 4 s 마다 고정값 (학습 범위 안) · 옆 +0.40 m/s / 옆 -0.40 m/s / 옆 +0.40 m/s / 옆 -0.40 m/s",
            "scene_color": RO.ORANGE, "t_s": 8.12, "cmd": [0.5, 0.0, 0.0], "vel": (0.47, -0.31, 0.02),
            "status": "넘어짐 없음", "bottom_line": "밀기 #2 · 8.00 s · 옆 -0.40 m/s (몸통 방향 기준) · 세계 속도 변화 (+0.00, -0.40) m/s",
            "bottom_color": RO.ORANGE, "duration_s": 20.0, "ticks_sched": [4.0, 8.0, 12.0, 16.0], "ticks_applied": [4.0, 8.0],
            "fall_t": None, "arrow": ((584, 331), (590, 420))}
    info.update(kw)
    return info


def test_overlay_layout_and_gate_interaction():
    out = RO.draw_overlay(good(0), overlay_info())
    assert out.shape == (720, 1280, 3)
    assert RG.frame_check(out)[0], RG.frame_check(out)
    # the overlay must not hide a defect: black 3D area with the overlay is still refused
    ob = RO.draw_overlay(black(), overlay_info(arrow=None))
    assert RG.frame_check(ob)[1] == "dark"
    os_ = RO.draw_overlay(sky(), overlay_info(arrow=None))
    assert RG.frame_check(os_)[1] == "blue"
    # text only outside the 3D area (except the arrow): with no arrow the 3D rows are unchanged
    plain = RO.draw_overlay(good(3), overlay_info(arrow=None, status="넘어짐 감지 7.32 s (몸통 접촉) · 이후는 참고 화면",
                                                  status_color=RO.RED, fall_t=7.32))
    assert np.array_equal(plain[224:616], good(3)[224:616])
    from PIL import Image
    p = os.path.join(ROOT, "overlay_sample.png")
    Image.fromarray(out).save(p)
    FACTS["overlay_sample_png"] = p


# --- 6. attempt validation and the driver -----------------------------------------------------------------------------------------
def q_rand_args(cmd):
    i = next(k for k, c in enumerate(cmd) if c.endswith("q_rand.py"))
    ap = argparse.ArgumentParser()
    for k in ("--scene", "--kind", "--attempt_id", "--outdir", "--checkpoint", "--train_yaml", "--cmd", "--duration_s",
              "--eval_seed", "--friction", "--restitution", "--push_frame", "--push", "--test_inject"):
        ap.add_argument(k, default="")
    ap.add_argument("--friction_probe", action="store_true")
    s = ap.parse_args(cmd[i + 1:])
    log = cmd[cmd.index("--watch_log") + 1]
    return s, log


def _hex(s):
    return hashlib.sha256(str(s).encode()).hexdigest()


FAKE_FP_KEYS = RL.FP_REQUIRED + ("actuator_base_legs_stiffness", "actuator_base_legs_damping", "actuator_base_legs_delay_lags")
FAKE_TERRAIN = [{"path": RL.TERRAIN_MESH_PATH, "points": 72, "faces": 50, "geom_sha256": _hex("geom"),
                 "xform_world": [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                 "world_sha256": _hex("world")}]
FAKE_CONTRACT = {"diffs": {"observations": ["observations/policy/enable_corruption: True vs False",
                                            "observations/single_obs/enable_corruption: True vs False"],
                           "actions": [], "decimation": [], "sim": [],
                           "scene/robot": ["scene/robot/prim_path: '/World/envs/env_.*/Robot' vs '{ENV_REGEX_NS}/Robot'"]}}
USD_KEY = "20261013_190000_1234"


def write_slot_v3(cmd, log, adir, slot_rc, state="scene_built"):
    """What isaac_slot_v3 + usd_isolate_run_v3 leave: <attempt>/slot.json, <usd_root>/isolate_state.json, assigned.jsonl."""
    i = cmd.index("--")
    usd_root = cmd[cmd.index("--usd_root") + 1]
    root = RL._norm(usd_root)
    folder = f"{root}/isaaclab/usd_{USD_KEY}"
    rec = {"slot_version": "v3", "attempt": cmd[cmd.index("--attempt") + 1], "cmd": cmd[i + 1:], "watch_log": RL._norm(log),
           "usd_root": root, "expect_conversions": cmd[cmd.index("--expect_conversions") + 1], "lock_wait_s": 0.0,
           "state_at_release": state, "slot_rc": slot_rc}
    if not state.startswith("not launched"):
        os.makedirs(usd_root, exist_ok=True)
        iso = {"t": "2026-10-13 20:00:00", "pid": 1, "version": "v3", "root": root, "patched_by": "loader", "patched": ["loader"],
               "terrain_patched_by": "loader", "blocked": [], "warnings": [], "meta_path": []}
        json.dump(iso, open(os.path.join(usd_root, "isolate_state.json"), "w"))
        open(os.path.join(usd_root, "assigned.jsonl"), "w").write(json.dumps({"usd_dir": folder, "kind": "assigned"}) + "\n")
        rec.update({"child_rc": slot_rc, "usd_at_release": [folder], "usd_final": [folder], "usd_final_keys": [USD_KEY],
                    "usd_outside_root": [], "usd_unassigned": [], "assigned": [folder], "assigned_refused": [], "assigned_bad_lines": 0,
                    "assigned_outside_root": [], "convert_hint": True, "hint_without_assigned": False, "conflicts": {},
                    "registry_error": "", "scan_unreadable": [], "legacy_registry_missing_logs": [], "usd_changed_after_release": False,
                    "isolate_state": iso, "conversion_attempts": 1, "unexpected_refused": [], "launcher_blocked": [],
                    "expect_violation": False})
    json.dump(rec, open(os.path.join(adir, "slot.json"), "w"))


def fake_q_rand(cmd, mode="ok", guard_stop=False, post=None):
    """Writes what q_rand.py + gpu_guard.py + isaac_slot_v3.py leave for one attempt. mode: ok | traceback (Isaac exit 0 after an
    exception) | wrong_attempt (done line of another attempt) | slot98 (gate did not launch) | gate94 · gate91 · gate96 · gate90
    (gate refusal). guard_stop: the GPU guard stopped the child (exit 99, no result). post(adir, log): edit the files afterwards."""
    s, log = q_rand_args(cmd)
    adir = s.outdir
    os.makedirs(adir, exist_ok=True)
    if mode == "slot98":
        write_slot_v3(cmd, log, adir, 98, state="not launched (stop file)")
        return 98
    if mode.startswith("gate"):
        code = int(mode[4:])
        open(log, "w", encoding="utf-8").write("[INFO]: Time taken for scene creation : 3.1 seconds\n")
        write_slot_v3(cmd, log, adir, code)
        j = json.load(open(os.path.join(adir, "slot.json")))
        j.update({"child_rc": -9, "killed": {"at": "scene_line", "codes": [code]}})
        json.dump(j, open(os.path.join(adir, "slot.json"), "w"))
        json.dump({"exit_code": -9, "stopped_by_guard": False}, open(os.path.join(adir, "guard.json"), "w"))
        return code
    if guard_stop or mode == "guard_then_gate94":
        # as gpu_guard.py writes it: exit_code is the KILLED child's code (here 1), the guard process itself exits 99.
        # guard_then_gate94: the gate then reports its own code (USD outside the root found in the log), so 99 is in no exit code
        open(log, "w", encoding="utf-8").write("[INFO]: Time taken for scene creation : 3.1 seconds\n")
        gate = 94 if mode == "guard_then_gate94" else 99
        write_slot_v3(cmd, log, adir, gate)
        j = json.load(open(os.path.join(adir, "slot.json")))
        j["child_rc"] = 99
        json.dump(j, open(os.path.join(adir, "slot.json"), "w"))
        json.dump({"exit_code": 1, "stopped_by_guard": True, "stop": {"free_mib": 3000}, "min_free_mib": 3000, "max_used_mib": 13000,
                   "wall_s": 50.0, "gpu_uuid": "GPU-test"}, open(os.path.join(adir, "guard.json"), "w"))
        return gate
    dur = float(s.duration_s)
    T = int(round(dur / RL.DT))
    fs, fd = (float(x) for x in s.friction.split(","))
    sched = RL.parse_push_schedule(s.push)
    fires = RL.predict_fire_states(4.0, RL.DT, T)
    events, push_events = [], []
    for k, j in enumerate(fires):
        e = {"index": k, "state_j": j, "t_s": j * RL.DT, "applied": False}
        if k < len(sched) and not sched[k]["none"]:
            w = RL.to_world(sched[k], 0.0, s.push_frame)
            e.update(applied=True, request=sched[k], frame=s.push_frame, heading_rad=0.0, dv_world_requested=w,
                     dv_world_measured=list(w), vel_w_before=[0.0] * 6, vel_w_after=list(w))
            push_events.append((j, w))
        events.append(e)
    rows = synth_rows(T, s.kind, push_events, fs, probe=s.friction_probe)
    sky_fail = s.test_inject.startswith("sky_always")
    lines = ["[INFO]: Time taken for scene creation : 3.1 seconds"]
    slot_rc = 0
    if sky_fail:
        os.makedirs(os.path.join(adir, "rejected"), exist_ok=True)
        open(os.path.join(adir, "rejected", f"{s.scene}_master.mp4.failed"), "wb").write(b"\x00" * 64)
        lines += ["[RAND] FAIL FrameGateError: FRAME_GATE frame 20 fails (blue) after 12 re-renders",
                  "Traceback (most recent call last):", "rand_gate.FrameGateError: FRAME_GATE frame 20 fails (blue) after 12 re-renders"]
        slot_rc = 3
    else:
        RL.write_record(os.path.join(adir, "record.csv"), rows)
        np.savez(os.path.join(adir, "traj.npz"), rows=rows, columns=np.array(RL.COLUMNS))
        master, web = os.path.join(adir, f"{s.scene}_master.mp4"), os.path.join(adir, f"{s.scene}_web.mp4")
        write_video(master, [good(i) for i in range(T + 1)])
        rr = [(30, "dark", 1, True)] if s.test_inject.startswith("black_once:30") else []
        os.makedirs(os.path.join(adir, "stills"), exist_ok=True)
        st = f"stills/{s.scene}_t00_j0000.png"
        from PIL import Image
        Image.fromarray(good(0)).save(os.path.join(adir, st))
        v = {"master": os.path.basename(master), "web": os.path.basename(web), "frames_master": T + 1,
             "rerendered_frames": len({x[0] for x in rr}), "rerender_calls": len(rr), "rerenders": [list(x) for x in rr],
             "stills": [st]}
        v.update(RG.publish(master, web, os.path.join(adir, "rejected"), expect_master_frames=T + 1))
        c = {name: rows[:, i] for i, name in enumerate(RL.COLUMNS)}
        fall = RL.fall_summary(c["base_contact"] > 0.5, c["gravity_body_z"], c["base_height_above_ground_m"])
        fp = {k: _hex(k) for k in FAKE_FP_KEYS}
        fp["robot_material"] = _hex(f"material {fs} {fd}")
        res = {"schema": RL.RESULT_SCHEMA, "attempt_id": s.attempt_id, "scene": s.scene, "kind": s.kind,
               "checkpoint_sha256": RL.sha256_file(s.checkpoint), "train_yaml_sha256": RL.sha256_file(s.train_yaml),
               "loaded_iter": 20000, "cmd": [float(x) for x in s.cmd.split(",")], "duration_s": dur, "T_steps": T,
               "eval_seed": int(s.eval_seed), "friction_probe": bool(s.friction_probe),
               "friction_requested": {"static": fs, "dynamic": fd, "restitution": 0.0},
               "material_readback": {"robot_tensor": {"n_shapes": 17, "static_min": fs, "static_max": fs, "dynamic_min": fd,
                                                      "dynamic_max": fd, "restitution_min": 0.0, "restitution_max": 0.0},
                                     "ground_usd": {"static_friction": 1.0, "dynamic_friction": 1.0, "friction_combine_mode": "average"},
                                     "effective": {"by_robot_mode": {"average": RL.effective_friction({"static": fs, "dynamic": fd}, {"static": 1.0, "dynamic": 1.0}, "average", "average")}}},
               "fingerprint": fp, "terrain_mesh": json.loads(json.dumps(FAKE_TERRAIN)),
               "eval_env": dict(RL.train_env_expect(DR), source="fake"), "train_contract": json.loads(json.dumps(FAKE_CONTRACT)),
               "push": {"schedule": sched, "frame": s.push_frame, "interval_s": [4.0, 4.0], "velocity_range": DR["push_velocity_range"],
                        "events": events, "predicted_fire_states": fires},
               "fall": fall, "stats": {"walk": RL.walk_summary(c, fall["j"]), "push_response": RL.push_response(c, events, fall["j"])},
               "checks_pre": {"teacher_input_randomized_max_abs_action_change": 0.0, "manual_student_path_vs_act_inference_max_abs": 0.0},
               "checks_run": {"obs_single_cmd_vs_target_max_abs": 0.0, "obs_history_latest_cmd_vs_target_max_abs": 0.0, "nonfinite_action_or_obs_count": 0},
               "video": v, "wall_s": 1.0}
        with open(os.path.join(adir, "result.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        aid = s.attempt_id if mode != "wrong_attempt" else s.attempt_id + "x"
        if mode == "traceback":
            lines += ["Traceback (most recent call last):", "RuntimeError: something after the video"]
        lines.append(f"[RAND] done scene={s.scene} attempt={aid}")
    with open(log, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    write_slot_v3(cmd, log, adir, slot_rc)
    json.dump({"exit_code": slot_rc, "stopped_by_guard": False, "min_free_mib": 6000, "max_used_mib": 9000, "wall_s": 100.0, "gpu_uuid": "GPU-test"},
              open(os.path.join(adir, "guard.json"), "w"))
    if post is not None:
        post(adir, log)
    return slot_rc


def _flow(argv, plan, free=99999):
    """Run the driver with a fake runner. plan(scene, attempt) -> mode | 'guard' | (mode, post). Returns (rc, run root, calls)."""
    if "--deadline" not in argv and "--stop_after_smoke" not in argv:
        argv = list(argv) + ["--deadline", "9999999999"]
    old = RL.OUT_RAND
    RL.OUT_RAND = os.path.join(ROOT, "flow_out_rand")
    os.makedirs(RL.OUT_RAND, exist_ok=True)
    calls = []
    try:
        def runner(cmd):
            s, _ = q_rand_args(cmd)
            scene, k = s.attempt_id.split(".")[-2], int(s.attempt_id.split(".")[-1][1:])
            calls.append(scene)
            m = plan(scene, k)
            mode, post = (m if isinstance(m, tuple) else (m, None))
            return fake_q_rand(cmd, mode=("ok" if mode == "guard" else mode), guard_stop=(mode == "guard"), post=post)
        try:
            rc = RD.main(argv, runner=runner, free_fn=lambda: free)
        except SystemExit as ex:
            rc = ex.code
        return rc, os.path.join(RL.OUT_RAND, argv[argv.index("--run_id") + 1]), calls
    finally:
        RL.OUT_RAND = old


def _man(root):
    return json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))


def test_driver_flow_retry_and_records():
    rc, root, _ = _flow(["--run_id", "flowA", "--duration_s", "4.2", "--smoke_s", "1.0", "--tries", "3"],
                        lambda scene, k: "traceback" if (scene == "fric_low" and k == 1) else ("wrong_attempt" if (scene == "fric_high" and k == 1) else "ok"))
    assert rc == 0, rc
    man = _man(root)
    got = [(x["scene"], x["attempt"], x["ok"]) for x in man["attempts"]]
    assert got == [("smoke_base", 1, True), ("smoke_probe", 1, True), ("smoke_skyfail", 1, False), ("base", 1, True),
                   ("push_lat", 1, True), ("fric_low", 1, False), ("fric_low", 2, True), ("fric_high", 1, False), ("fric_high", 2, True)], got
    fl = {(x["scene"], x["attempt"]): x["failed_checks"] for x in man["attempts"]}
    assert fl[("fric_low", 1)] == ["log_no_traceback"], fl[("fric_low", 1)]
    assert fl[("fric_high", 1)] == ["log_done_line_this_attempt"], fl[("fric_high", 1)]
    assert os.path.exists(os.path.join(root, "fric_low", "a1", "result.json"))  # the failed attempt is kept
    assert man["stages"]["smoke"]["S1"]["black_frame_recovered_at_30"] and man["stages"]["smoke"]["S3"]["failed_as_expected"]
    assert man["stages"]["probe_used"] is True
    cross = man["stages"]["main"]["cross"]
    assert cross["same_start_fingerprints"]["equal"] and cross["same_terrain"]["equal"] and cross["pairing"]["valid"], cross
    assert cross["base_vs_push_before_first_push"]["equal"] and cross["base_vs_push_before_first_push"]["states"] == 201
    assert cross["smoke_base_vs_base_first_states"]["equal"]
    summ = json.load(open(os.path.join(root, "summary.json"), encoding="utf-8"))
    assert summ["pairing"]["valid"] and len(summ["scenes"]["push_lat"]["pushes"]) == 1
    assert [x["attempt"] for x in summ["scenes"]["fric_low"]["attempts"]] == [1, 2]  # the retry and its reason are in the summary
    FACTS["driver_flow_attempts"] = got


def test_driver_stops_when_smoke_gate_does_not_refuse():
    orig = q_rand_args  # make the forced-sky run "succeed" (a broken loop gate): the fake ignores the injection

    def patched(cmd):
        s, log = orig(cmd)
        if s.test_inject.startswith("sky_always"):
            s.test_inject = ""
        return s, log
    globals()["q_rand_args"] = patched
    try:
        rc, root, _ = _flow(["--run_id", "flowB", "--duration_s", "4.2", "--smoke_s", "1.0"], lambda scene, k: "ok")
    finally:
        globals()["q_rand_args"] = orig
    assert rc == 5, rc
    man = _man(root)
    assert [x["scene"] for x in man["attempts"]] == ["smoke_base", "smoke_probe", "smoke_skyfail"]
    assert "problem" in man["stages"]["smoke"]["S3"]


def test_driver_protective_stops_at_the_common_boundary():
    """ASTRA 17d 2.1: guard stop, gate refusals and a low free-memory reading stop the driver wherever attempt() is called,
    with no retry and no next scene."""
    out = {}
    rc, root, calls = _flow(["--run_id", "flowC", "--duration_s", "4.2", "--skip_smoke"], lambda s, k: "guard" if s == "push_lat" else "ok")
    assert rc == 99 and calls == ["base", "push_lat"] and _man(root)["stop_code"] == 99, (rc, calls)
    out["guard_main"] = rc
    # the guard stopped the child, then the gate reported 94 from what it found in the log: still a GPU-memory stop (99)
    rc, root, calls = _flow(["--run_id", "flowC2", "--duration_s", "4.2", "--skip_smoke"],
                            lambda s, k: "guard_then_gate94" if s == "push_lat" else "ok")
    assert rc == 99 and calls == ["base", "push_lat"] and "GPU guard" in _man(root)["stopped"], (rc, calls, _man(root).get("stopped"))
    out["guard_then_gate94"] = rc
    for code in (94, 91, 96, 90, 97, 95, 89):
        rc, root, calls = _flow(["--run_id", f"flowG{code}", "--duration_s", "4.2", "--skip_smoke", "--tries", "3"],
                                lambda s, k, c=code: f"gate{c}" if s == "push_lat" else "ok")
        assert rc == code and calls == ["base", "push_lat"], (code, rc, calls)
        out[f"gate{code}"] = rc
    rc, root, calls = _flow(["--run_id", "flowM", "--duration_s", "4.2", "--skip_smoke"], lambda s, k: "ok", free=1000)
    assert rc == 99 and calls == [] and "before launching" in _man(root)["stopped"], (rc, calls)
    out["free_before_launch"] = rc
    FACTS["protective_stops"] = out


def test_driver_stop_file_deadline_and_slot98():
    called = []

    def plan(scene, k):
        called.append(scene)
        return "ok"
    stopf = os.path.join(ROOT, "STOP_test")
    open(stopf, "w").write("stop\n")
    rc, root, _ = _flow(["--run_id", "flowD", "--duration_s", "4.2", "--skip_smoke", "--stop_file", stopf], plan)
    man = _man(root)
    assert rc == 98 and not called and man["attempts"] == [] and "stop file" in man["stopped"], (rc, called, man.get("stopped"))
    rc, root, _ = _flow(["--run_id", "flowE", "--duration_s", "4.2", "--skip_smoke", "--deadline", repr(time.time() - 5.0)], plan)
    man = _man(root)
    assert rc == 98 and not called and man["attempts"] == [] and "deadline" in man["stopped"], (rc, man.get("stopped"))
    rc, root, _ = _flow(["--run_id", "flowF", "--duration_s", "4.2", "--skip_smoke"], lambda s, k: "slot98" if s == "push_lat" else "ok")
    man = _man(root)
    assert rc == 98 and [x["scene"] for x in man["attempts"]] == ["base", "push_lat"] and man["stop_code"] == 98, (rc, man.get("stopped"))


# ASTRA 17d 8: the five counterexamples, each was rc 0 before
def _edit_json(path, f):
    j = json.load(open(path, encoding="utf-8"))
    f(j)
    json.dump(j, open(path, "w", encoding="utf-8"))


def _rows_edit(adir, f, csv=True, npz=True):
    cols, rows = RL.load_npz_rows(os.path.join(adir, "traj.npz"))
    f(rows)
    if npz:
        np.savez(os.path.join(adir, "traj.npz"), rows=rows, columns=np.array(RL.COLUMNS))
    if csv:
        RL.write_record(os.path.join(adir, "record.csv"), rows)


def _terrain_changed(adir, log):
    _edit_json(os.path.join(adir, "result.json"), lambda j: j["terrain_mesh"][0].update(world_sha256=_hex("moved terrain")))


def _x_plus(adir, csv):
    _rows_edit(adir, lambda r: r.__setitem__((10, RL.COLUMNS.index("base_x_m")), r[10, RL.COLUMNS.index("base_x_m")] + 0.02), csv=csv)


def _empty_fp(adir, log):
    _edit_json(os.path.join(adir, "result.json"), lambda j: j.update(fingerprint={}, terrain_mesh=[]))


def _support_nan(adir, log):
    def f(r):
        r[:, RL.COLUMNS.index("ground_z_m")] = np.nan
        r[:, RL.COLUMNS.index("base_height_above_ground_m")] = np.nan
    _rows_edit(adir, f)


def _push_world_x(adir, log):
    def f(j):
        e = [x for x in j["push"]["events"] if x["applied"]][0]
        e["dv_world_requested"] = [0.4, 0.0, 0.0, 0.0, 0.0, 0.0]
        e["dv_world_measured"] = [0.4, 0.0, 0.0, 0.0, 0.0, 0.0]
    _edit_json(os.path.join(adir, "result.json"), f)


def test_astra17d_counterexamples_not_rc0():
    base = ["--duration_s", "4.2", "--tries", "1", "--scenes", "base,push_lat"]
    out = {}
    # 1. guard stop in smoke_probe: stop there, no smoke_skyfail, no main scene
    rc, root, calls = _flow(["--run_id", "cx1"] + base + ["--smoke_s", "1.0"], lambda s, k: "guard" if s == "smoke_probe" else "ok")
    assert rc == 99 and calls == ["smoke_base", "smoke_probe"], (rc, calls)
    out["1_smoke_probe_guard"] = rc
    # 2. push terrain fingerprint changed + state 10 x + 0.02 in the NPZ (as ASTRA did)
    rc, root, _ = _flow(["--run_id", "cx2"] + base + ["--skip_smoke"],
                        lambda s, k: ("ok", (lambda a, l: (_terrain_changed(a, l), _x_plus(a, csv=False)))) if s == "push_lat" else "ok")
    assert rc != 0, rc
    out["2_terrain_and_x_npz"] = rc
    # 2b. only the terrain world hash: every attempt valid, the pairing must break -> 6
    rc, root, _ = _flow(["--run_id", "cx2b"] + base + ["--skip_smoke"], lambda s, k: ("ok", _terrain_changed) if s == "push_lat" else "ok")
    assert rc == 6 and not _man(root)["stages"]["main"]["cross"]["same_terrain"]["equal"], rc
    out["2b_terrain_only"] = rc
    # 2c. x + 0.02 at state 10 in both CSV and NPZ: every attempt valid, base and push differ before the first push -> 6
    rc, root, _ = _flow(["--run_id", "cx2c"] + base + ["--skip_smoke"], lambda s, k: ("ok", lambda a, l: _x_plus(a, csv=True)) if s == "push_lat" else "ok")
    cr = _man(root)["stages"]["main"]["cross"]
    assert rc == 6 and abs(cr["base_vs_push_before_first_push"]["max_abs_diff"] - 0.02) < 1e-9, (rc, cr)
    out["2c_x_both_files"] = rc
    # 3. empty fingerprint and terrain in every scene
    rc, root, _ = _flow(["--run_id", "cx3"] + base + ["--skip_smoke"], lambda s, k: ("ok", _empty_fp))
    assert rc != 0 and all({"fingerprint_complete", "terrain_complete"} <= set(x["failed_checks"]) for x in _man(root)["attempts"]), rc
    out["3_empty_fingerprint"] = rc
    # 4. support height NaN in both files of both scenes
    rc, root, _ = _flow(["--run_id", "cx4"] + base + ["--skip_smoke"], lambda s, k: ("ok", _support_nan))
    assert rc != 0 and all("record_judge_finite_before_fall" in x["failed_checks"] for x in _man(root)["attempts"]), rc
    out["4_support_nan"] = rc
    # 5. first push turned into world +x while the plan is heading +vy
    rc, root, _ = _flow(["--run_id", "cx5"] + base + ["--skip_smoke"], lambda s, k: ("ok", _push_world_x) if s == "push_lat" else "ok")
    fl = [x for x in _man(root)["attempts"] if x["scene"] == "push_lat"][0]["failed_checks"]
    assert rc != 0 and "push_direction" in fl, (rc, fl)
    out["5_push_direction"] = rc
    FACTS["astra17d_counterexamples_rc"] = out


FAKE_CHILD = '''import json, os, sys, time
log, where = sys.argv[1], sys.argv[2]
root = os.environ["FOOTHOLD_USD_ROOT"]
k = "29991231_235959_" + str(os.getpid())
base = root if where in ("inside", "unassigned", "second_refused") else "C:/tmp"
path = base + "/IsaacLab/usd_" + k
os.makedirs(root, exist_ok=True)
json.dump({"version": "v3", "patched_by": "fake_child", "blocked": [], "warnings": []}, open(os.path.join(root, "isolate_state.json"), "w"))
if where in ("inside", "second_refused"):
    open(os.path.join(root, "assigned.jsonl"), "a").write(json.dumps({"usd_dir": path, "kind": "assigned"}) + "\\n")
if where == "second_refused":
    open(os.path.join(root, "assigned.jsonl"), "a").write(json.dumps({"usd_dir": None, "kind": "refused_unexpected_conversion", "n": 2}) + "\\n")
with open(log, "a", encoding="utf-8") as f:
    f.write("[USD-ISOLATE] root " + root + " (v3)\\n")
    f.write("converting to " + path + "/go2.usd\\n")
    f.write("[INFO]: Time taken for scene creation : 0.1 seconds\\n")
time.sleep(1.5)
'''


def test_real_isaac_slot_v3_accepts_our_args():
    """The real SLOT_SCRIPT (isaac_slot_v3.py) with exactly the gate arguments slot_guard_cmd builds, except a private lock and
    registry (the shared ones belong to tonight's runs) and a fake child instead of gpu_guard -> Isaac. The fake child gets the
    real child command as ignored arguments so the recorded cmd is the one the driver would launch."""
    import subprocess
    assert os.path.exists(RL.SLOT_SCRIPT), f"{RL.SLOT_SCRIPT} missing: the real-gate test cannot run"
    d = os.path.join(ROOT, "real_slot_v3")
    os.makedirs(d, exist_ok=True)
    slot_copy = os.path.join(d, "isaac_slot_v3_copy.py")  # frozen copy: the shared file may change while it is finished
    shutil.copyfile(RL.SLOT_SCRIPT, slot_copy)
    if os.path.exists(RL.ISOLATE_SCRIPT):
        shutil.copyfile(RL.ISOLATE_SCRIPT, os.path.join(d, "usd_isolate_run_v3_copy.py"))
    child = os.path.join(d, "fake_child.py")
    open(child, "w", encoding="utf-8").write(FAKE_CHILD)
    a = RD.parse_args(["--run_id", "realslot"])
    spec = RD.scene_specs(a)["base"]
    out = {}
    for name, where, stop in (("inside", "inside", False), ("outside", "outside", False), ("unassigned", "unassigned", False),
                              ("second_refused", "second_refused", False), ("stopped", "inside", True)):
        adir = os.path.join(d, name)
        os.makedirs(adir, exist_ok=True)
        log = os.path.join(d, f"realslot__{name}.log")
        aid = f"realslot.{name}.a1"
        stopf = os.path.join(d, f"STOP_{name}")
        if stop:
            open(stopf, "w").write("stop\n")
        cmd = RL.slot_guard_cmd(sys.executable, log, os.path.join(adir, "slot.json"), os.path.join(adir, "guard.json"),
                                RD.script_args(a, "base", spec, aid, adir, 20.0, False), os.path.join(adir, "usd"), aid,
                                stop_file=stopf, deadline=0.0)
        i = cmd.index("--")
        slot_args = list(cmd[:i])
        assert slot_args[1] == RL.SLOT_SCRIPT
        slot_args[1] = slot_copy
        slot_args[slot_args.index("--lock") + 1] = os.path.join(d, "test.lock")
        slot_args[slot_args.index("--registry") + 1] = os.path.join(d, "test_registry.json")
        r = subprocess.run(slot_args + ["--", sys.executable, child, log, where] + cmd[i + 1:], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300, cwd=d)
        assert "usage:" not in r.stderr and "error:" not in r.stderr, r.stderr[-800:]
        rec = json.load(open(os.path.join(adir, "slot.json"), encoding="utf-8"))
        exp = RD.expect_for(a, "x", 20000, DR, "base", spec, aid, 20.0, adir)
        v = RL.validate_attempt(adir, log, exp)
        sc = {c["name"]: c["ok"] for c in v["checks"] if c["name"].startswith("slot_") or c["name"].startswith("usd_isolate")}
        out[name] = {"rc": r.returncode, "state": rec.get("state_at_release"), "usd_final": rec.get("usd_final"),
                     "failed_slot_checks": sorted(k for k, ok in sc.items() if not ok)}
        if name == "inside":
            assert r.returncode == 0 and rec["slot_version"] == "v3" and rec["child_rc"] == 0 and rec["state_at_release"] == "scene_built", out[name]
            assert all(sc.values()) and len(sc) == 17, sc  # every gate check of the validator passes on the real v3 record
        elif name == "outside":
            assert r.returncode == 94 and {"slot_rc_zero", "slot_usd_inside_root", "slot_expected_conversions"} <= set(out[name]["failed_slot_checks"]), out[name]
        elif name == "second_refused":
            assert r.returncode == 89 and {"slot_rc_zero", "slot_expect_one_conversion"} <= set(out[name]["failed_slot_checks"]), out[name]
        elif name == "unassigned":
            assert r.returncode == 91 and {"slot_rc_zero", "slot_usd_assigned"} <= set(out[name]["failed_slot_checks"]), out[name]
        else:
            assert r.returncode == 98 and rec["state_at_release"].startswith("not launched") and not os.path.exists(log), out[name]
    FACTS["real_isaac_slot_v3_runs"] = out
    FACTS["isaac_slot_v3_copy_sha256"] = RL.sha256_file(slot_copy)
    FACTS["usd_isolate_run_v3_copy_sha256"] = RL.sha256_file(os.path.join(d, "usd_isolate_run_v3_copy.py")) if os.path.exists(RL.ISOLATE_SCRIPT) else None


def test_validate_attempt_mutations():
    """One good synthetic attempt, then one defect at a time: each must fail exactly its own check(s)."""
    old = RL.OUT_RAND
    RL.OUT_RAND = os.path.join(ROOT, "mut_out_rand")
    os.makedirs(RL.OUT_RAND, exist_ok=True)
    try:
        a = RD.parse_args(["--run_id", "mut"])
        spec = RD.scene_specs(a)["push_lat"]
        dur = 4.2
        base_dir = os.path.join(RL.OUT_RAND, "mut", "push_lat", "a1")
        log = os.path.join(RL.OUT_RAND, "mut__push_lat__a1.log")
        cmd = RL.slot_guard_cmd(sys.executable, log, os.path.join(base_dir, "slot.json"), os.path.join(base_dir, "guard.json"),
                                RD.script_args(a, "push_lat", spec, "mut.push_lat.a1", base_dir, dur, True),
                                os.path.join(base_dir, "usd"), "mut.push_lat.a1")
        fake_q_rand(cmd)
        exp = RD.expect_for(a, RL.sha256_file(a.checkpoint), 20000, DR, "push_lat", spec, "mut.push_lat.a1", dur, base_dir, probe=True)
        assert exp["push_expected"] == 1
        v = RL.validate_attempt(base_dir, log, exp, audit_fn=RG.audit, probe_fn=RG.probe)
        assert v["ok"] and not v["warnings"], [c for c in v["checks"] if not c["ok"]]
        base_root = RL._norm(os.path.join(base_dir, "usd"))

        def mutate(name, fn, expect_failed, still_ok=False):
            d = os.path.join(RL.OUT_RAND, "mut", "push_lat", f"m_{name}")
            shutil.copytree(base_dir, d)
            lg = os.path.join(RL.OUT_RAND, f"mut__m_{name}.log")
            shutil.copy(log, lg)
            # the copy is its own attempt folder: its USD root is <copy>/usd and the gate record says so
            sp = os.path.join(d, "slot.json")
            txt = open(sp, encoding="utf-8").read()
            open(sp, "w", encoding="utf-8").write(txt.replace(base_root, RL._norm(os.path.join(d, "usd"))))
            exp_d = dict(exp, usd_root=os.path.join(d, "usd"))
            fn(d, lg)
            vv = RL.validate_attempt(d, lg, exp_d, audit_fn=RG.audit, probe_fn=RG.probe)
            failed = sorted(c["name"] for c in vv["checks"] if not c["ok"])
            assert failed == sorted(expect_failed), (name, failed)
            assert vv["ok"] == still_ok, (name, vv["ok"])
            return failed

        def ej(d, fn_name, f):
            _edit_json(os.path.join(d, fn_name), f)

        def append_log(lg, s):
            open(lg, "a", encoding="utf-8").write(s + "\n")

        def replace_web(d, frames, fps=30):
            p = os.path.join(d, "push_lat_web.mp4")
            os.remove(p)
            import subprocess
            tmp = os.path.join(d, "tmp.mp4")
            write_video(tmp, frames, fps=fps)
            subprocess.run([RG.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", tmp, "-c", "copy", "-movflags", "+faststart", p], check=True)
            os.remove(tmp)

        T = int(round(dur / RL.DT))
        n30 = int(round(dur * 30))
        res = {}

        def M(name, fn, failed, still_ok=False):
            res[name] = mutate(name, fn, failed, still_ok)

        def slot(f):
            return lambda d, lg: ej(d, "slot.json", f)

        def result(f):
            return lambda d, lg: ej(d, "result.json", f)

        def iso(f):
            return lambda d, lg: ej(os.path.join(d, "usd"), "isolate_state.json", f)

        # log and guard
        M("traceback", lambda d, lg: append_log(lg, "Traceback (most recent call last):"), ["log_no_traceback"])
        M("fail_line", lambda d, lg: append_log(lg, "[RAND] FAIL X"), ["log_no_fail_line"])
        M("no_done", lambda d, lg: open(lg, "w").write("nothing\n"), ["log_done_line_this_attempt"])
        M("two_done", lambda d, lg: append_log(lg, "[RAND] done scene=push_lat attempt=mut.push_lat.a1"), ["log_done_line_this_attempt"])
        M("guard_stop", lambda d, lg: ej(d, "guard.json", lambda j: j.update(stopped_by_guard=True)), ["guard_record"])
        # gate record (isaac_slot_v3 + usd_isolate_run_v3, one conversion expected)
        M("slot_v2_record", slot(lambda j: j.pop("slot_version")), ["slot_version"])
        M("slot_other_attempt", slot(lambda j: j.update(attempt="mut.push_lat.a0")), ["slot_attempt_is_this_attempt"])
        M("slot_rc_94", slot(lambda j: j.update(slot_rc=94)), ["slot_rc_zero"])
        M("slot_child_rc", slot(lambda j: j.update(child_rc=3)), ["slot_child_rc_zero"])
        M("slot_not_built", slot(lambda j: j.update(state_at_release="convert_timeout")), ["slot_scene_built"])
        M("slot_expect_violation", slot(lambda j: j.update(expect_violation=True)), ["slot_expect_one_conversion"])
        M("slot_expect_zero", slot(lambda j: j.update(expect_conversions="0")), ["slot_expect_one_conversion"])
        M("slot_no_expect_field", slot(lambda j: j.pop("expect_violation")), ["slot_expect_one_conversion"])

        def two_usd(j):
            j["usd_final"] = j["usd_final"] + [j["usd_final"][0][:-4] + "9999"]
            j["assigned"] = list(j["usd_final"])
        M("slot_two_conversions", slot(two_usd), ["slot_expected_conversions"])
        M("slot_no_conversion", slot(lambda j: j.update(usd_final=[], assigned=[])), ["slot_expected_conversions"])
        M("slot_usd_outside", slot(lambda j: j.update(usd_outside_root=["c:/tmp/isaaclab/usd_x"])), ["slot_usd_inside_root"])
        M("slot_assigned_outside", slot(lambda j: j.update(assigned_outside_root=["c:/tmp/isaaclab/usd_x"])), ["slot_usd_inside_root"])
        M("slot_unassigned", slot(lambda j: j.update(usd_unassigned=list(j["usd_final"]))), ["slot_usd_assigned"])
        M("slot_assigned_other", slot(lambda j: j.update(assigned=[])), ["slot_usd_assigned"])
        M("slot_hint_without_assigned", slot(lambda j: j.update(hint_without_assigned=True)), ["slot_usd_assigned"])
        M("slot_conflict", slot(lambda j: j.update(conflicts={"x": ["y"]})), ["slot_no_conflicts"])
        M("slot_registry_error", slot(lambda j: j.update(registry_error="registry is not JSON")), ["slot_registry_ok"])
        M("slot_killed", slot(lambda j: j.update(killed={"at": "after_release"})), ["slot_not_killed"])
        M("slot_other_root", slot(lambda j: j.update(usd_root="c:/tmp")), ["slot_usd_root_is_this_attempt"])
        M("slot_v2_runner", slot(lambda j: j.update(cmd=[x.replace("usd_isolate_run_v3.py", "usd_isolate_run.py") for x in j["cmd"]])), ["slot_cmd_isolated"])
        M("slot_other_script", slot(lambda j: j.update(cmd=[x for x in j["cmd"] if not x.endswith("q_rand.py")])), ["slot_cmd_isolated"])
        M("isolate_missing", lambda d, lg: os.remove(os.path.join(d, "usd", "isolate_state.json")), ["usd_isolate_patched"])
        M("isolate_unpatched", iso(lambda j: j.update(patched_by="")), ["usd_isolate_patched"])
        M("isolate_v2", iso(lambda j: j.update(version="v2")), ["usd_isolate_patched"])
        M("isolate_blocked", iso(lambda j: j.update(blocked=[{"why": "outside"}])), ["usd_isolate_patched"])
        M("isolate_warning", iso(lambda j: j.update(warnings=[{"what": "terrain cache"}])), ["usd_isolate_no_warnings"], still_ok=True)
        M("slot_missing", lambda d, lg: os.remove(os.path.join(d, "slot.json")),
          ["slot_record_exists", "slot_version", "slot_attempt_is_this_attempt", "slot_rc_zero", "slot_child_rc_zero", "slot_scene_built",
           "slot_expect_one_conversion",
           "slot_expected_conversions", "slot_usd_inside_root", "slot_usd_assigned", "slot_no_conflicts", "slot_registry_ok",
           "slot_usd_root_is_this_attempt", "slot_cmd_isolated"])
        # result against the request bundle and the training contract
        M("stale_result", result(lambda j: j.update(attempt_id="old")), ["result_matches_request"])
        M("other_ckpt", result(lambda j: j.update(checkpoint_sha256="0" * 64)), ["result_matches_request"])
        M("probe_flag", result(lambda j: j.update(friction_probe=False)), ["result_matches_request"])
        M("other_train_yaml", result(lambda j: j.update(train_yaml_sha256="1" * 64)), ["train_yaml_is_request"])
        M("contract_sim_dt", result(lambda j: j["train_contract"]["diffs"]["sim"].append("sim/dt: 0.005 vs 0.01")), ["train_contract_kept"])
        M("contract_obs_scale", result(lambda j: j["train_contract"]["diffs"]["observations"].append("observations/policy/base_ang_vel/scale: 0.25 vs 1.0")), ["train_contract_kept"])
        M("contract_group_missing", result(lambda j: j["train_contract"]["diffs"].pop("actions")), ["train_contract_kept"])
        M("contract_missing", result(lambda j: j.pop("train_contract")), ["train_contract_kept"])
        M("env_step_dt", result(lambda j: j["eval_env"].update(step_dt=0.04)), ["eval_env_is_training"])
        M("env_joint_order", result(lambda j: j["eval_env"].update(action_joint_names=list(reversed(j["eval_env"]["action_joint_names"])))), ["eval_env_is_training"])
        M("env_scale", result(lambda j: j["eval_env"].update(action_scale=[0.5] * 12)), ["eval_env_is_training"])
        M("fp_missing_key", result(lambda j: j["fingerprint"].pop("com")), ["fingerprint_complete"])
        M("fp_not_hex", result(lambda j: j["fingerprint"].update(body_masses="abc")), ["fingerprint_complete"])
        M("fp_no_actuator", result(lambda j: [j["fingerprint"].pop(k) for k in list(j["fingerprint"]) if k.startswith("actuator_")]), ["fingerprint_complete"])
        M("fp_empty", result(lambda j: j.update(fingerprint={})), ["fingerprint_complete"])
        M("terrain_empty", result(lambda j: j.update(terrain_mesh=[])), ["terrain_complete"])
        M("terrain_other_path", result(lambda j: j["terrain_mesh"][0].update(path="/World/ground/other")), ["terrain_complete"])
        M("terrain_no_xform", result(lambda j: j["terrain_mesh"][0].update(xform_world=[1.0] * 15)), ["terrain_complete"])
        M("terrain_no_world_hash", result(lambda j: j["terrain_mesh"][0].pop("world_sha256")), ["terrain_complete"])
        # record (CSV and NPZ joined, fall recomputed)
        M("short_record", lambda d, lg: RL.write_record(os.path.join(d, "record.csv"), synth_rows(T - 1)),
          ["record_csv_structure", "record_csv_equals_npz", "record_step_time", "record_judge_finite_before_fall",
           "record_values_meaningful", "record_nan_markers", "record_probe_columns", "record_fall_matches_result"])  # no joined part can pass
        M("support_nan", lambda d, lg: _support_nan(d, lg), ["record_judge_finite_before_fall"])
        M("npz_only_x", lambda d, lg: _x_plus(d, csv=False), ["record_csv_equals_npz"])
        M("fall_result_other", result(lambda j: j.update(fall={"fell": True, "j": 30, "reason": "tilt60"})), ["record_fall_matches_result"])
        M("contact_not_binary", lambda d, lg: _rows_edit(d, lambda r: r.__setitem__((12, RL.COLUMNS.index("FL_foot_contact")), 2.0)), ["record_values_meaningful"])
        M("cmd_error", result(lambda j: j["checks_run"].update(obs_single_cmd_vs_target_max_abs=0.1)), ["command_seen_by_policy"])
        M("teacher_leak", result(lambda j: j["checks_pre"].update(teacher_input_randomized_max_abs_action_change=0.2)), ["student_path_only"])
        M("material", result(lambda j: j["material_readback"]["robot_tensor"].update(static_max=1.3)), ["robot_material_readback_equals_request"])

        # pushes against the frozen schedule
        def ev0(j):
            return [x for x in j["push"]["events"] if x["applied"]][0]
        M("push_world_x", result(lambda j: ev0(j).update(dv_world_requested=[0.4, 0, 0, 0, 0, 0], dv_world_measured=[0.4, 0, 0, 0, 0, 0])),
          ["push_direction", "push_measured"])
        M("push_other_request", result(lambda j: ev0(j).update(request=dict(ev0(j)["request"], vy=-0.4))), ["push_order_and_request"])
        M("push_request_missing", result(lambda j: ev0(j).update(request={})), ["push_order_and_request"])
        M("push_request_nan", result(lambda j: ev0(j)["request"].update(vy=float("nan"))), ["push_order_and_request"])
        M("push_request_string", result(lambda j: ev0(j)["request"].update(vy="0.4")), ["push_order_and_request"])
        M("push_other_frame", result(lambda j: ev0(j).update(frame="world")), ["push_order_and_request"])

        def linked_heading(d, lg, event_heading, row_heading):
            # Literal deltas for body-left +0.4 m/s, hand checked independently of to_world.
            if event_heading == math.pi / 2:
                w = [-0.4, 0.0, 0.0, 0.0, 0.0, 0.0]
            elif event_heading == math.pi:
                w = [0.0, -0.4, 0.0, 0.0, 0.0, 0.0]
            else:
                w = [-0.00008, -0.4, 0.0, 0.0, 0.0, 0.0]  # pi - 0.0002 rad
            def edit_result(j):
                e = ev0(j)
                e.update(heading_rad=event_heading, dv_world_requested=w, dv_world_measured=w,
                         vel_w_after=w)
            _edit_json(os.path.join(d, "result.json"), edit_result)
            def edit_rows(rows):
                j = 201
                rows[j, RL.COLUMNS.index("heading_rad")] = row_heading
                for c, x in zip(RL.PUSH_COLUMNS, (w[0], w[1], w[3], w[4], w[5])):
                    rows[j, RL.COLUMNS.index(c)] = x
            _rows_edit(d, edit_rows)

        M("push_heading_other_world_consistent", lambda d, lg: linked_heading(d, lg, math.pi / 2, 0.0), ["push_direction"])
        M("push_heading_wrap", lambda d, lg: linked_heading(d, lg, math.pi, -math.pi), [], still_ok=True)
        M("push_heading_near_wrap", lambda d, lg: linked_heading(d, lg, math.pi - 0.0002, -math.pi + 0.0002), [], still_ok=True)

        def extra_push(j):
            e = j["push"]["events"][1] if len(j["push"]["events"]) > 1 else None
            assert e is None
            j["push"]["events"].append({"index": 1, "state_j": 205, "t_s": 4.1, "applied": True})
        # an applied event the run never fired: count, order/request (no request stored), direction (no heading), timing warning
        M("push_extra_event", result(extra_push), ["push_count", "push_direction", "push_order_and_request", "push_fire_states_as_predicted"])
        M("push_measured_other", result(lambda j: ev0(j)["dv_world_measured"].__setitem__(1, 0.2)), ["push_measured"])
        M("push_after_before", result(lambda j: ev0(j).update(vel_w_after=[0.0] * 6)), ["push_measured"])
        M("push_nonfinite", result(lambda j: ev0(j).update(heading_rad=None)), ["push_direction"])
        M("push_record_row", lambda d, lg: _rows_edit(d, lambda r: r.__setitem__((201, RL.COLUMNS.index("push_dv_world_y_mps")), 0.3)), ["push_record_rows"])

        def out_of_range(j):
            e = ev0(j)
            e.update(dv_world_requested=[0.0, 0.45, 0, 0, 0, 0], dv_world_measured=[0.0, 0.45, 0, 0, 0, 0], vel_w_after=[0.0, 0.45, 0, 0, 0, 0])
        M("push_range", result(out_of_range), ["push_direction", "push_measured", "push_range"])
        M("push_missing", result(lambda j: [x.update(applied=False) for x in j["push"]["events"]]), ["push_count", "push_order_and_request"])
        M("push_late", result(lambda j: ev0(j).update(state_j=ev0(j)["state_j"] + 1, t_s=(ev0(j)["state_j"] + 1) * RL.DT)),
          ["push_fire_states_as_predicted", "push_record_rows"])
        # videos
        M("web_black_frame", lambda d, lg: replace_web(d, [black() if i == 77 else good(i) for i in range(n30)]), ["frame_gate_web_all_frames"])
        M("web_50fps", lambda d, lg: replace_web(d, [good(i) for i in range(n30)], fps=50), ["web_h264_720p_30fps"])

        def master_sky(d, lg):
            p = os.path.join(d, "push_lat_master.mp4")
            os.remove(p)
            write_video(p, [sky() if 100 <= i < 130 else good(i) for i in range(T + 1)])
        M("master_sky", master_sky, ["frame_gate_master_all_frames"])

        def no_faststart(d, lg):
            import subprocess
            p = os.path.join(d, "push_lat_web.mp4")
            tmp = os.path.join(d, "tmp.mp4")
            os.replace(p, tmp)
            subprocess.run([RG.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", tmp, "-c", "copy", p], check=True)
            os.remove(tmp)
        M("web_no_faststart", no_faststart, ["web_faststart"])
        M("no_still", lambda d, lg: shutil.rmtree(os.path.join(d, "stills")), ["stills"])
        FACTS["validate_mutations_caught"] = sorted(res)
        FACTS["validate_mutation_cells"] = len(res)
    finally:
        RL.OUT_RAND = old


def test_driver_dry_run_and_paths():
    import io
    from contextlib import redirect_stdout
    before = set(os.listdir(RL.OUT_RAND))
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = RD.main(["--dry_run", "--run_id", "dry_check"])
    assert rc == 0
    plan = json.loads(buf.getvalue())
    assert set(os.listdir(RL.OUT_RAND)) == before, "dry run wrote something"
    cmds = plan["commands"]
    assert len(cmds) == 7
    for p_, c in zip(plan["attempts"], cmds):
        assert c.split(" ")[1] == RL.SLOT_SCRIPT and RL.SLOT_SCRIPT.endswith("isaac_slot_v3.py")
        assert "--lock" in c and "isaac_convert.lock" in c and "isaac_usd_registry_v3.json" in c
        assert "--scan_dirs" in c and "gpu_guard.py --gpu 1 --min_free_mib 4096" in c
        assert f"--usd_root {os.path.join(p_['dir'], 'usd')} --attempt {p_['attempt_id']} " in c, c
        assert f"--stop_file {os.path.join(RL.OUT_RAND, 'STOP')} --deadline 0.0 --expect_conversions 1 -- " in c
        assert RL.ISOLATE_SCRIPT.endswith("usd_isolate_run_v3.py") and (RL.ISOLATE_SCRIPT + " " + os.path.join(RL.HERE, "q_rand.py") + " --scene") in c
        assert f"--outdir {p_['dir']} " in c  # scan inputs may include old out/branch; output stays private
    assert "--friction 0.0,0.0" in cmds[5] and "--friction 1.5,1.5" in cmds[6]  # fric_low default: robot-side training low end
    assert plan["predicted_push_states"] == RL.predict_fire_states(4.0, RL.DT, 1000)
    FACTS["dry_run_first_command"] = cmds[3]
    for bad in (os.path.join(RL.EVAL, "out", "x"), os.path.join(RL.EVAL, "out_rand", "handover_1"), "C:/tmp/x"):
        try:
            RL.check_out_path(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    rc = RD.main(["--dry_run", "--run_id", "dry2", "--push", "vx=0.3,vy=0.3"])
    assert rc == 2  # plan refused: outside the training range for some heading
    rc = RD.main(["--dry_run", "--run_id", "dry3", "--fric_low", "2.5"])
    assert rc == 2


def test_cross_checks_refuse_empty_unequal_and_repeat_mismatch():
    """cross_checks on its own (defence in depth behind the per-attempt checks): empty fingerprints and terrain never match,
    different fingerprints break the pairing, the reference scene repeated in another process must match exactly."""
    d0 = os.path.join(ROOT, "cross_unit")

    def mk(name, fp, terrain, rows):
        d = os.path.join(d0, name)
        os.makedirs(d, exist_ok=True)
        json.dump({"fingerprint": fp, "terrain_mesh": terrain, "push": {"events": []}}, open(os.path.join(d, "result.json"), "w"))
        np.savez(os.path.join(d, "traj.npz"), rows=rows, columns=np.array(RL.COLUMNS))
        return {"dir": d}
    rows = synth_rows(100)
    full = {k: _hex(k) for k in FAKE_FP_KEYS}

    class A:
        smoke_s = 1.0

    class Dd:
        a = A()
    ok = RD.cross_checks(Dd(), {"base": mk("b_ok", full, FAKE_TERRAIN, rows), "fric_low": mk("f_ok", full, FAKE_TERRAIN, rows)})
    assert ok["pairing"]["valid"], ok
    empty = RD.cross_checks(Dd(), {"base": mk("b_e", {}, [], rows), "fric_low": mk("f_e", {}, [], rows)})
    assert not empty["pairing"]["valid"] and not empty["same_start_fingerprints"]["equal"] and not empty["same_terrain"]["equal"], empty
    other = dict(full, com=_hex("other com"))
    diff = RD.cross_checks(Dd(), {"base": mk("b_d", full, FAKE_TERRAIN, rows), "fric_low": mk("f_d", other, FAKE_TERRAIN, rows)})
    assert not diff["pairing"]["valid"] and diff["same_start_fingerprints"]["complete"] and not diff["same_start_fingerprints"]["equal"]
    r2 = rows.copy()
    r2[20, RL.COLUMNS.index("base_y_m")] += 1e-6
    rep = RD.cross_checks(Dd(), {"base": mk("b_r", full, FAKE_TERRAIN, rows), "fric_low": mk("f_r", full, FAKE_TERRAIN, rows)},
                          smoke_base_dir=mk("s_r", full, FAKE_TERRAIN, r2)["dir"])
    assert not rep["pairing"]["valid"] and not rep["smoke_base_vs_base_first_states"]["equal"], rep
    single = RD.cross_checks(Dd(), {"base": mk("b_s", full, FAKE_TERRAIN, rows)})
    assert not single["pairing"]["applicable"] and not single["pairing"]["valid"]


def test_contract_helpers_known():
    allowed = RL.allowed_train_diff_paths()
    assert RL.contract_problems(FAKE_CONTRACT, allowed) == []
    assert RL.contract_problems({"diffs": {}}, allowed)  # nothing compared is a problem
    assert RL.contract_problems(FAKE_CONTRACT, RL.allowed_train_diff_paths(obs_noise=True))  # noise on: corruption diffs not allowed
    assert RL.fingerprint_problems({}) == ["fingerprint missing or empty"]
    assert RL.terrain_problems([]) == ["terrain mesh list missing or empty"]
    assert RL.eval_env_problems(dict(RL.train_env_expect(DR)), RL.train_env_expect(DR)) == []


def test_astra17g_registry_is_separate_and_legacy_read_is_required():
    import importlib.util
    d = os.path.join(ROOT, "registry_17g")
    os.makedirs(d, exist_ok=True)
    legacy = os.path.join(d, "legacy.json")
    v3 = os.path.join(d, "v3.json")
    old_legacy, old_v3 = RL.LEGACY_REGISTRY, RL.V3_REGISTRY
    try:
        RL.LEGACY_REGISTRY, RL.V3_REGISTRY = legacy, v3
        old_log = os.path.join(d, "other_logs", "gpu0.log")
        os.makedirs(os.path.dirname(old_log), exist_ok=True)
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump({"old-usd": old_log}, f)
        args = RL.slot_guard_cmd(sys.executable, os.path.join(d, "rand.log"), os.path.join(d, "slot.json"),
                                 os.path.join(d, "guard.json"), [], os.path.join(d, "usd"), "rand.a1")
        assert args[args.index("--registry") + 1] == v3
        assert args[args.index("--lock") + 1] == os.path.join(RL.EVAL, "slot", "isaac_convert.lock")
        dirs = args[args.index("--scan_dirs") + 1].split(",")
        required = ["out/branch", "out_branch", "out_uncr", "out_uncr_v5", "out_uncr_v6", "out_ce12/native", "out_rand"]
        assert all(os.path.join(RL.EVAL, *p.split("/")) in dirs for p in required), dirs
        assert os.path.dirname(old_log) in dirs

        # A stale legacy writer overwrites only its own file. The v3 write uses the registry
        # path from RAND's actual command, so this detects accidental path sharing.
        spec = importlib.util.spec_from_file_location("slot_v3_test", RL.SLOT_SCRIPT)
        slot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(slot)
        stale = json.load(open(legacy, encoding="utf-8"))
        mine = {os.path.join(d, "usd", "isaaclab", "usd_1"): "usd_1"}
        _, _, shared_err = slot.registry_update(legacy, mine, os.path.join(d, "rand.log"))
        assert shared_err == "" and len(json.load(open(legacy, encoding="utf-8"))) == 2
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump(stale, f)
        assert len(json.load(open(legacy, encoding="utf-8"))) == 1  # ASTRA's stale writer loses RAND's shared entry
        actual_v3 = args[args.index("--registry") + 1]
        _, _, err = slot.registry_update(actual_v3, mine, os.path.join(d, "rand.log"))
        assert err == "", err
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump(stale, f)
        assert len(json.load(open(actual_v3, encoding="utf-8"))) == 1
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("not json")
        assert any("legacy registry" in p for p in RD.check_plan(RD.parse_args(["--run_id", "registry_bad", "--deadline", "9999999999"]))[0])
    finally:
        RL.LEGACY_REGISTRY, RL.V3_REGISTRY = old_legacy, old_v3


def test_astra17g_gpu_unknown_and_main_deadline():
    a = RD.parse_args(["--run_id", "gpu_unknown", "--skip_smoke", "--deadline", "9999999999"])
    root = os.path.join(ROOT, "gpu_unknown")
    os.makedirs(root, exist_ok=True)
    calls = []
    d = RD.Driver(a, DR, 20000, root, runner=lambda cmd: calls.append(cmd) or 0, free_fn=lambda: None)
    try:
        d.attempt("base", RD.scene_specs(a)["base"], 1, 4.2, False)
        raise AssertionError("unknown GPU memory launched")
    except SystemExit as ex:
        assert ex.code == 99
    assert not calls and not os.path.exists(os.path.join(root, "base", "a1"))
    assert "unverified" in d.manifest["stopped"]
    a_ok = RD.parse_args(["--run_id", "gpu_known", "--skip_smoke", "--deadline", "9999999999"])
    root_ok = os.path.join(ROOT, "gpu_known")
    os.makedirs(root_ok, exist_ok=True)
    known_calls = []
    def known_runner(cmd):
        known_calls.append(cmd)
        return fake_q_rand(cmd)
    d_ok = RD.Driver(a_ok, DR, 20000, root_ok, runner=known_runner, free_fn=lambda: 6000)
    assert d_ok.attempt("base", RD.scene_specs(a_ok)["base"], 1, 1.0, False)["validation"]["ok"]
    assert len(known_calls) == 1
    assert any("deadline" in p for p in RD.check_plan(RD.parse_args(["--run_id", "no_deadline", "--skip_smoke"]))[0])
    assert not any("deadline" in p for p in RD.check_plan(a_ok)[0])
    assert not any("deadline" in p for p in RD.check_plan(RD.parse_args(["--run_id", "smoke_only", "--stop_after_smoke"]))[0])


def test_no_forbidden_text():
    """No em / en dash or U+2212 anywhere; no 'same start' claim and no 'feet only' / 'floor friction' wording burned into the
    frames (ASTRA 17d 2.2 · 5)."""
    bad = {}
    for f in ("q_rand.py", "rand_lib.py", "rand_gate.py", "rand_overlay.py", "rand_driver.py", "test_rand_scenes.py",
              "mutate_rand_scenes.py", "README-rand-scenes.md"):
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            t = open(p, encoding="utf-8").read()
            n = t.count("\u2014") + t.count("\u2013") + t.count("\u2212")
            if n:
                bad[f] = n
    assert not bad, bad
    src = open(os.path.join(HERE, "q_rand.py"), encoding="utf-8").read()
    body = src[src.index("    run_line = "):src.index("    stills_at = ")] + src[src.index("    def frame_for("):src.index("    cmd_err_single = ")]
    for phrase in ("같은 출발", "발 재질", "바닥 마찰", "로봇 발"):
        assert phrase not in body, phrase


def main():
    only = [x for x in sys.argv[1:] if x.startswith("test_")]
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f) and (not only or n in only)]
    results = []
    for n, f in tests:
        t0 = time.time()
        try:
            f()
            results.append({"test": n, "ok": True, "s": round(time.time() - t0, 2)})
            print(f"PASS {n} ({time.time() - t0:.1f}s)", flush=True)
        except Exception as ex:  # noqa: BLE001
            results.append({"test": n, "ok": False, "error": f"{type(ex).__name__}: {ex}", "tb": traceback.format_exc()})
            print(f"FAIL {n}: {type(ex).__name__}: {str(ex)[:400]}", flush=True)
    summary = {"stamp": STAMP, "root": ROOT, "passed": sum(r["ok"] for r in results), "total": len(results),
               "results": results, "facts": FACTS,
               "code_sha256": {f: RL.sha256_file(os.path.join(HERE, f)) for f in ("q_rand.py", "rand_lib.py", "rand_gate.py", "rand_overlay.py", "rand_driver.py", "test_rand_scenes.py")},
               "gate_files_sha256_at_test": {os.path.basename(f): (RL.sha256_file(f) if os.path.exists(f) else None) for f in (RL.SLOT_SCRIPT, RL.ISOLATE_SCRIPT)}}
    with open(os.path.join(ROOT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({"passed": summary["passed"], "total": summary["total"], "results": os.path.join(ROOT, "results.json")}))
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
