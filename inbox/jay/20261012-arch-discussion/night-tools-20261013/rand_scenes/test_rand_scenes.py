# CPU tests of the randomization scene tools (no Isaac, no GPU). Every gate is broken on purpose before it is trusted.
#   python test_rand_scenes.py            -> runs all tests, writes _eval/out_rand/_cpu_tests/<stamp>/results.json
#   python -m pytest test_rand_scenes.py  -> same tests under pytest
# Synthetic data only: frames are a brown block texture (passes the gate), black (dark), uniform grey (flat), a blue
# gradient (sky). Attempt folders are written by fake_q_rand(), which imitates q_rand.py's files (the Isaac run itself is
# not tested here).
import argparse
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
def synth_rows(T, kind="none", push_states=(), friction=1.0, probe=False):
    col = {c: i for i, c in enumerate(RL.COLUMNS)}
    n = T + 1
    r = np.full((n, len(RL.COLUMNS)), np.nan)
    t = np.arange(n) * RL.DT
    r[:, col["step"]] = np.arange(n)
    r[:, col["t_s"]] = t
    vx = 0.5 * (1 - np.exp(-t / 0.5)) * (0.9 if friction < 0.5 else 1.0)
    vy = np.zeros(n)
    for j0 in push_states:
        k = np.arange(n) - j0
        vy += np.where(k >= 0, 0.4 * np.exp(-np.maximum(k, 0) * RL.DT / 0.3), 0.0)
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
    for k, j0 in enumerate(push_states):
        r[j0, col["push_index"]] = k
        r[j0, col["push_dv_world_y_mps"]] = 0.4
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


def test_record_roundtrip_and_checks():
    p = os.path.join(ROOT, "rec.csv")
    rows = synth_rows(100)
    RL.write_record(p, rows)
    head, a = RL.read_record(p)
    assert head == RL.COLUMNS and a.shape == rows.shape
    assert np.allclose(np.nan_to_num(a, nan=-9), np.nan_to_num(rows, nan=-9), rtol=1e-6, atol=1e-6)
    assert RL.record_checks(p, 101)["ok"]
    assert not RL.record_checks(p, 1001)["ok"]  # wrong length is caught
    bad = rows.copy()
    bad[5, 0] = 6
    RL.write_record(p, bad)
    assert not RL.record_checks(p, 101)["ok"]  # step column broken
    bad = rows.copy()
    bad[7, RL.COLUMNS.index("base_x_m")] = np.nan
    RL.write_record(p, bad)
    assert not RL.record_checks(p, 101)["ok"]  # NaN in a core column


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


def test_push_response_known():
    rows = synth_rows(1000, push_states=(200,))
    c = {name: rows[:, i] for i, name in enumerate(RL.COLUMNS)}
    ev = [{"index": 0, "state_j": 200, "applied": True}]
    pr = RL.push_response(c, ev)[0]
    # vy = 0.4 exp(-t / 0.3): below 0.1 m/s from t = 0.3 ln 4 = 0.416 s -> first state 21 (0.42 s)
    assert abs(pr["vy_body_at_push_mps"] - 0.4) < 1e-12 and abs(pr["peak_abs_vy_body_mps"] - 0.4) < 1e-12
    assert abs(pr["settle_t_s"] - 0.42) < 1e-9, pr
    assert abs(pr["sideways_after_window_m"] - (0.4 * 0.02 * np.exp(-np.arange(1, 101) * 0.02 / 0.3)).sum()) < 1e-9, pr
    assert RL.push_response(c, ev, fall_j=150)[0]["note"] == "after the fall"


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


def write_slot_v2(cmd, log, adir, slot_rc, state="scene_built"):
    """What isaac_slot.py v2 + usd_isolate_run.py leave: <attempt>/slot.json and <usd_root>/isolate_state.json."""
    i = cmd.index("--")
    usd_root = cmd[cmd.index("--usd_root") + 1]
    k = "20261013_190000_1234"
    launched = not state.startswith("not launched")
    rec = {"attempt": cmd[cmd.index("--attempt") + 1], "cmd": cmd[i + 1:], "watch_log": RL._norm(log), "usd_root": RL._norm(usd_root),
           "lock_wait_s": 0.0, "state_at_release": state, "slot_rc": slot_rc}
    if launched:
        os.makedirs(usd_root, exist_ok=True)
        json.dump({"t": "2026-10-13 19:00:00", "pid": 1, "patched_by": "loader", "meta_path": []},
                  open(os.path.join(usd_root, "isolate_state.json"), "w"))
        rec.update({"usd_at_release": [k], "child_rc": slot_rc, "usd_final": [k], "usd_outside_root": [], "conflicts": {},
                    "usd_changed_after_release": False})
    json.dump(rec, open(os.path.join(adir, "slot.json"), "w"))


def fake_q_rand(cmd, mode="ok", guard_stop=False):
    """Writes what q_rand.py + gpu_guard.py + isaac_slot.py v2 would leave for one attempt. mode: ok | traceback (Isaac exit 0
    after an exception) | wrong_attempt (done line of another attempt) | slot98 (isaac_slot did not launch: stop file)."""
    s, log = q_rand_args(cmd)
    adir = s.outdir
    os.makedirs(adir, exist_ok=True)
    if mode == "slot98":
        write_slot_v2(cmd, log, adir, 98, state="not launched (stop file)")
        return 98
    dur = float(s.duration_s)
    T = int(round(dur / RL.DT))
    fs, fd = (float(x) for x in s.friction.split(","))
    sched = RL.parse_push_schedule(s.push)
    fires = RL.predict_fire_states(4.0, RL.DT, T)
    events, push_states = [], []
    for k, j in enumerate(fires):
        e = {"index": k, "state_j": j, "t_s": j * RL.DT, "applied": False}
        if k < len(sched) and not sched[k]["none"]:
            w = RL.to_world(sched[k], 0.0, s.push_frame)
            e.update(applied=True, request=sched[k], frame=s.push_frame, heading_rad=0.0, dv_world_requested=w,
                     dv_world_measured=list(w), vel_w_before=[0.0] * 6, vel_w_after=w)
            push_states.append(j)
        events.append(e)
    rows = synth_rows(T, s.kind, push_states, fs, probe=s.friction_probe)
    sky_fail = s.test_inject.startswith("sky_always")
    lines = ["[INFO]: Time taken for scene creation : 3.1 seconds"]
    slot_rc = 0
    if sky_fail:
        os.makedirs(os.path.join(adir, "rejected"), exist_ok=True)
        open(os.path.join(adir, "rejected", f"{s.scene}_master.mp4.failed"), "wb").write(b"\x00" * 64)
        lines += [f"[RAND] FAIL FrameGateError: FRAME_GATE frame 20 fails (blue) after 12 re-renders",
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
        res = {"schema": RL.RESULT_SCHEMA, "attempt_id": s.attempt_id, "scene": s.scene, "kind": s.kind,
               "checkpoint_sha256": RL.sha256_file(s.checkpoint), "loaded_iter": 20000, "cmd": [float(x) for x in s.cmd.split(",")],
               "duration_s": dur, "T_steps": T, "eval_seed": int(s.eval_seed), "friction_requested": {"static": fs, "dynamic": fd, "restitution": 0.0},
               "material_readback": {"robot_tensor": {"n_shapes": 17, "static_min": fs, "static_max": fs, "dynamic_min": fd,
                                                      "dynamic_max": fd, "restitution_min": 0.0, "restitution_max": 0.0},
                                     "ground_usd": {"static_friction": 1.0, "dynamic_friction": 1.0, "friction_combine_mode": "average"},
                                     "effective": {"by_robot_mode": {"average": RL.effective_friction({"static": fs, "dynamic": fd}, {"static": 1.0, "dynamic": 1.0}, "average", "average")}}},
               "fingerprint": {"init_root_pose": "a", "init_joint_pos": "b", "body_masses": "c", "com": "d", "robot_material": f"m{fs}"},
               "terrain_mesh": [["/World/ground/terrain/mesh", 72, "h"]],
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
    write_slot_v2(cmd, log, adir, slot_rc)
    json.dump({"exit_code": slot_rc, "stopped_by_guard": guard_stop, "min_free_mib": 6000, "max_used_mib": 9000, "wall_s": 100.0, "gpu_uuid": "GPU-test"},
              open(os.path.join(adir, "guard.json"), "w"))
    return slot_rc if not guard_stop else 99


def _flow(argv, plan):
    """Run the driver with a fake runner. plan(scene, attempt) -> mode or 'guard'."""
    old = RL.OUT_RAND
    RL.OUT_RAND = os.path.join(ROOT, "flow_out_rand")
    os.makedirs(RL.OUT_RAND, exist_ok=True)
    try:
        def runner(cmd):
            s, _ = q_rand_args(cmd)
            scene, k = s.attempt_id.split(".")[-2], int(s.attempt_id.split(".")[-1][1:])
            m = plan(scene, k)
            return fake_q_rand(cmd, mode=("ok" if m == "guard" else m), guard_stop=(m == "guard"))
        try:
            rc = RD.main(argv, runner=runner)
        except SystemExit as ex:
            rc = ex.code
        return rc, os.path.join(RL.OUT_RAND, argv[argv.index("--run_id") + 1])
    finally:
        RL.OUT_RAND = old


def test_driver_flow_retry_and_records():
    rid = "flowA"
    rc, root = _flow(["--run_id", rid, "--duration_s", "4.2", "--smoke_s", "1.0", "--tries", "3"],
                     lambda scene, k: "traceback" if (scene == "fric_low" and k == 1) else ("wrong_attempt" if (scene == "fric_high" and k == 1) else "ok"))
    assert rc == 0, rc
    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
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
    assert cross["same_start_fingerprints"]["equal"] and cross["same_terrain_mesh"]
    assert cross["base_vs_push_before_first_push"]["equal"] and cross["base_vs_push_before_first_push"]["states"] in (200, 201)
    summ = json.load(open(os.path.join(root, "summary.json"), encoding="utf-8"))
    assert summ["scenes"]["push_lat"]["pushes"] and len(summ["scenes"]["push_lat"]["pushes"]) == 1
    assert os.path.exists(os.path.join(root, "summary.csv"))
    FACTS["driver_flow_attempts"] = got


def test_driver_stops_when_smoke_gate_does_not_refuse():
    rid = "flowB"

    def runner_plan(scene, k):
        return "ok"
    orig = q_rand_args  # make the forced-sky run "succeed" (a broken loop gate): the fake ignores the injection

    def patched(cmd):
        s, log = orig(cmd)
        if s.test_inject.startswith("sky_always"):
            s.test_inject = ""
        return s, log
    globals()["q_rand_args"] = patched
    try:
        rc, root = _flow(["--run_id", rid, "--duration_s", "4.2", "--smoke_s", "1.0"], runner_plan)
    finally:
        globals()["q_rand_args"] = orig
    assert rc == 5, rc
    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    assert [x["scene"] for x in man["attempts"]] == ["smoke_base", "smoke_probe", "smoke_skyfail"]
    assert "problem" in man["stages"]["smoke"]["S3"]


def test_driver_stops_on_gpu_guard():
    rc, root = _flow(["--run_id", "flowC", "--duration_s", "4.2", "--skip_smoke"], lambda scene, k: "guard" if scene == "push_lat" else "ok")
    assert rc == 99, rc
    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    assert man.get("stopped") == "gpu_guard" and [x["scene"] for x in man["attempts"]] == ["base", "push_lat"]


def test_driver_stop_file_deadline_and_slot98():
    called = []

    def plan(scene, k):
        called.append(scene)
        return "ok"
    stopf = os.path.join(ROOT, "STOP_test")
    open(stopf, "w").write("stop\n")
    rc, root = _flow(["--run_id", "flowD", "--duration_s", "4.2", "--skip_smoke", "--stop_file", stopf], plan)
    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    assert rc == 98 and not called and man["attempts"] == [] and "stop file" in man["stopped"], (rc, called, man.get("stopped"))
    rc, root = _flow(["--run_id", "flowE", "--duration_s", "4.2", "--skip_smoke", "--deadline", repr(time.time() - 5.0)], plan)
    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    assert rc == 98 and not called and man["attempts"] == [] and "deadline" in man["stopped"], (rc, man.get("stopped"))
    rc, root = _flow(["--run_id", "flowF", "--duration_s", "4.2", "--skip_smoke"], lambda s, k: "slot98" if s == "push_lat" else "ok")
    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    assert rc == 98 and [x["scene"] for x in man["attempts"]] == ["base", "push_lat"] and "isaac_slot refused" in man["stopped"], (rc, man.get("stopped"))


FAKE_CHILD = '''import json, os, sys, time
log, where = sys.argv[1], sys.argv[2]
root = os.environ["FOOTHOLD_USD_ROOT"]
k = "29991231_235959_" + str(os.getpid())
base = root if where == "inside" else "C:/tmp"
os.makedirs(root, exist_ok=True)
json.dump({"patched_by": "fake_child"}, open(os.path.join(root, "isolate_state.json"), "w"))
with open(log, "a", encoding="utf-8") as f:
    f.write("[USD-ISOLATE] root " + root + "\\n")
    f.write("converting to " + base + "/IsaacLab/usd_" + k + "/go2.usd\\n")
    f.write("[INFO]: Time taken for scene creation : 0.1 seconds\\n")
time.sleep(1.5)
'''


def test_real_isaac_slot_accepts_our_args():
    """The real _eval/isaac_slot.py (v2) with exactly the isaac_slot arguments rand_lib.slot_guard_cmd builds, except a private
    lock and registry (the shared ones belong to tonight's runs) and a fake child instead of gpu_guard -> Isaac. The fake child
    gets the real child command as ignored arguments so the recorded cmd is the one the driver would launch."""
    import subprocess
    d = os.path.join(ROOT, "real_slot")
    os.makedirs(d, exist_ok=True)
    child = os.path.join(d, "fake_child.py")
    open(child, "w", encoding="utf-8").write(FAKE_CHILD)
    a = RD.parse_args(["--run_id", "realslot"])
    spec = RD.scene_specs(a)["base"]
    out = {}
    for name, where, stop in (("inside", "inside", False), ("outside", "outside", False), ("stopped", "inside", True)):
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
        slot_args[slot_args.index("--lock") + 1] = os.path.join(d, "test.lock")
        slot_args[slot_args.index("--registry") + 1] = os.path.join(d, "test_registry.json")
        r = subprocess.run(slot_args + ["--", sys.executable, child, log, where] + cmd[i + 1:], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180, cwd=d)
        assert "usage:" not in r.stderr and "error:" not in r.stderr, r.stderr[-800:]
        rec = json.load(open(os.path.join(adir, "slot.json"), encoding="utf-8"))
        exp = RD.expect_for(a, "x", 20000, DR, "base", spec, aid, 20.0, adir)
        v = RL.validate_attempt(adir, log, exp)
        sc = {c["name"]: c["ok"] for c in v["checks"] if c["name"].startswith("slot_") or c["name"] == "usd_isolate_patched"}
        out[name] = {"rc": r.returncode, "state": rec.get("state_at_release"), "usd_final": rec.get("usd_final"),
                     "outside": rec.get("usd_outside_root"), "failed_slot_checks": sorted(k for k, ok in sc.items() if not ok)}
        if name == "inside":
            assert r.returncode == 0 and rec["slot_rc"] == 0 and rec["child_rc"] == 0 and rec["state_at_release"] == "scene_built", out[name]
            assert len(rec["usd_final"]) == 1 and rec["usd_outside_root"] == [] and rec["conflicts"] == {} and rec["attempt"] == aid
            assert all(sc.values()) and len(sc) == 11, sc  # every slot check of the validator passes on the real v2 record
        elif name == "outside":
            assert r.returncode == 94 and out[name]["failed_slot_checks"] == ["slot_rc_zero", "slot_usd_inside_root"], out[name]
        else:
            assert r.returncode == 98 and rec["state_at_release"].startswith("not launched") and not os.path.exists(log), out[name]
    FACTS["real_isaac_slot_runs"] = out
    FACTS["isaac_slot_sha256"] = RL.sha256_file(os.path.join(RL.EVAL, "isaac_slot.py"))
    FACTS["usd_isolate_run_sha256"] = RL.sha256_file(os.path.join(RL.EVAL, "usd_isolate_run.py"))


def test_validate_attempt_mutations():
    """One good synthetic attempt, then one defect at a time: each must fail exactly its own check."""
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
        exp = RD.expect_for(a, RL.sha256_file(a.checkpoint), 20000, DR, "push_lat", spec, "mut.push_lat.a1", dur, base_dir)
        assert exp["push_expected"] == 1
        v = RL.validate_attempt(base_dir, log, exp, audit_fn=RG.audit, probe_fn=RG.probe)
        assert v["ok"], [c for c in v["checks"] if not c["ok"]]

        def mutate(name, fn, expect_failed):
            d = os.path.join(RL.OUT_RAND, "mut", "push_lat", f"m_{name}")
            shutil.copytree(base_dir, d)
            lg = os.path.join(RL.OUT_RAND, f"mut__m_{name}.log")
            shutil.copy(log, lg)
            # the copy is its own attempt folder: its USD root is <copy>/usd, and its slot record says so
            edit_json(d, "slot.json", lambda j: j.update(usd_root=RL._norm(os.path.join(d, "usd"))))
            exp_d = dict(exp, usd_root=os.path.join(d, "usd"))
            fn(d, lg)
            vv = RL.validate_attempt(d, lg, exp_d, audit_fn=RG.audit, probe_fn=RG.probe)
            failed = sorted(c["name"] for c in vv["checks"] if not c["ok"])
            assert failed == sorted(expect_failed), (name, failed)
            if name == "push_late":  # timing prediction is a warning, the attempt still counts
                assert vv["ok"] and vv["warnings"] == ["push_fire_states_as_predicted"], vv["warnings"]
            else:
                assert not vv["ok"], name
            return failed

        def edit_json(d, fn_name, f):
            p = os.path.join(d, fn_name)
            j = json.load(open(p, encoding="utf-8"))
            f(j)
            json.dump(j, open(p, "w", encoding="utf-8"))

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
        res["traceback"] = mutate("traceback", lambda d, lg: append_log(lg, "Traceback (most recent call last):"), ["log_no_traceback"])
        res["fail_line"] = mutate("fail_line", lambda d, lg: append_log(lg, "[RAND] FAIL X"), ["log_no_fail_line"])
        res["no_done"] = mutate("no_done", lambda d, lg: open(lg, "w").write("nothing\n"), ["log_done_line_this_attempt"])
        res["two_done"] = mutate("two_done", lambda d, lg: append_log(lg, "[RAND] done scene=push_lat attempt=mut.push_lat.a1"), ["log_done_line_this_attempt"])
        # isaac_slot v2 record: one condition broken at a time
        def slot_edit(f):
            return lambda d, lg: edit_json(d, "slot.json", f)
        res["slot_other_attempt"] = mutate("slot_other_attempt", slot_edit(lambda j: j.update(attempt="mut.push_lat.a0")), ["slot_attempt_is_this_attempt"])
        res["slot_rc_94"] = mutate("slot_rc_94", slot_edit(lambda j: j.update(slot_rc=94)), ["slot_rc_zero"])
        res["slot_child_rc"] = mutate("slot_child_rc", slot_edit(lambda j: j.update(child_rc=3)), ["slot_child_rc_zero"])
        res["slot_not_built"] = mutate("slot_not_built", slot_edit(lambda j: j.update(state_at_release="convert_timeout")), ["slot_scene_built"])
        res["slot_two_usd"] = mutate("slot_two_usd", slot_edit(lambda j: j.update(usd_final=["20261013_190000_1234", "20261013_190001_7"])), ["slot_one_usd_folder"])
        res["slot_no_usd"] = mutate("slot_no_usd", slot_edit(lambda j: j.update(usd_final=[])), ["slot_one_usd_folder"])
        res["slot_usd_outside"] = mutate("slot_usd_outside", slot_edit(lambda j: j.update(usd_outside_root=["20261013_190000_1234"])), ["slot_usd_inside_root"])
        res["slot_v1_record"] = mutate("slot_v1_record", slot_edit(lambda j: j.pop("usd_outside_root")), ["slot_usd_inside_root"])
        res["slot_conflict"] = mutate("slot_conflict", slot_edit(lambda j: j.update(conflicts={"x": ["y"]})), ["slot_no_conflicts"])
        res["slot_other_root"] = mutate("slot_other_root", slot_edit(lambda j: j.update(usd_root="c:/tmp")), ["slot_usd_root_is_this_attempt"])
        res["slot_not_isolated"] = mutate("slot_not_isolated", slot_edit(lambda j: j.update(cmd=[x for x in j["cmd"] if not x.endswith("usd_isolate_run.py")])), ["slot_cmd_isolated"])
        res["slot_other_script"] = mutate("slot_other_script", slot_edit(lambda j: j.update(cmd=[x for x in j["cmd"] if not x.endswith("q_rand.py")])), ["slot_cmd_isolated"])
        res["isolate_missing"] = mutate("isolate_missing", lambda d, lg: os.remove(os.path.join(d, "usd", "isolate_state.json")), ["usd_isolate_patched"])
        res["isolate_unpatched"] = mutate("isolate_unpatched", lambda d, lg: edit_json(os.path.join(d, "usd"), "isolate_state.json", lambda j: j.update(patched_by="")), ["usd_isolate_patched"])
        res["slot_missing"] = mutate("slot_missing", lambda d, lg: os.remove(os.path.join(d, "slot.json")),
                                     ["slot_record_exists", "slot_attempt_is_this_attempt", "slot_rc_zero", "slot_child_rc_zero", "slot_scene_built",
                                      "slot_one_usd_folder", "slot_usd_inside_root", "slot_no_conflicts", "slot_usd_root_is_this_attempt", "slot_cmd_isolated"])
        res["guard_stop"] = mutate("guard_stop", lambda d, lg: edit_json(d, "guard.json", lambda j: j.update(stopped_by_guard=True)), ["guard_record"])
        res["stale_result"] = mutate("stale_result", lambda d, lg: edit_json(d, "result.json", lambda j: j.update(attempt_id="old")), ["result_matches_request"])
        res["other_ckpt"] = mutate("other_ckpt", lambda d, lg: edit_json(d, "result.json", lambda j: j.update(checkpoint_sha256="0" * 64)), ["result_matches_request"])
        res["short_record"] = mutate("short_record", lambda d, lg: RL.write_record(os.path.join(d, "record.csv"), synth_rows(T - 1)), ["record_csv"])
        res["cmd_error"] = mutate("cmd_error", lambda d, lg: edit_json(d, "result.json", lambda j: j["checks_run"].update(obs_single_cmd_vs_target_max_abs=0.1)), ["command_seen_by_policy"])
        res["teacher_leak"] = mutate("teacher_leak", lambda d, lg: edit_json(d, "result.json", lambda j: j["checks_pre"].update(teacher_input_randomized_max_abs_action_change=0.2)), ["student_path_only"])
        res["material"] = mutate("material", lambda d, lg: edit_json(d, "result.json", lambda j: j["material_readback"]["robot_tensor"].update(static_max=1.3)), ["robot_material_readback_equals_request"])

        def push_out(j):
            e = [x for x in j["push"]["events"] if x["applied"]][0]
            e["dv_world_requested"][1] = 0.45
            e["dv_world_measured"][1] = 0.45
        res["push_range"] = mutate("push_range", lambda d, lg: edit_json(d, "result.json", push_out), ["push_world_components_in_training_range"])

        def push_meas(j):
            [x for x in j["push"]["events"] if x["applied"]][0]["dv_world_measured"][1] = 0.2
        res["push_measured"] = mutate("push_measured", lambda d, lg: edit_json(d, "result.json", push_meas), ["push_measured_equals_requested"])

        def push_missing(j):
            for x in j["push"]["events"]:
                x["applied"] = False
        res["push_missing"] = mutate("push_missing", lambda d, lg: edit_json(d, "result.json", push_missing), ["push_count"])

        def push_late(j):
            j["push"]["events"][0]["state_j"] += 1
        res["push_late"] = mutate("push_late", lambda d, lg: edit_json(d, "result.json", push_late), ["push_fire_states_as_predicted"])
        res["web_black_frame"] = mutate("web_black_frame", lambda d, lg: replace_web(d, [black() if i == 77 else good(i) for i in range(n30)]), ["frame_gate_web_all_frames"])
        res["web_50fps"] = mutate("web_50fps", lambda d, lg: replace_web(d, [good(i) for i in range(n30)], fps=50), ["web_h264_720p_30fps"])

        def master_sky(d, lg):
            p = os.path.join(d, "push_lat_master.mp4")
            os.remove(p)
            write_video(p, [sky() if 100 <= i < 130 else good(i) for i in range(T + 1)])
        res["master_sky"] = mutate("master_sky", master_sky, ["frame_gate_master_all_frames"])

        def no_faststart(d, lg):
            import subprocess
            p = os.path.join(d, "push_lat_web.mp4")
            tmp = os.path.join(d, "tmp.mp4")
            os.replace(p, tmp)
            subprocess.run([RG.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", tmp, "-c", "copy", p], check=True)
            os.remove(tmp)
        res["web_no_faststart"] = mutate("web_no_faststart", no_faststart, ["web_faststart"])
        res["no_still"] = mutate("no_still", lambda d, lg: shutil.rmtree(os.path.join(d, "stills")), ["stills"])
        FACTS["validate_mutations_caught"] = sorted(res)
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
        assert "isaac_slot.py --watch_log" in c and "--lock" in c and "isaac_convert.lock" in c and "isaac_usd_registry.json" in c
        sd = ",".join([RL.OUT_RAND, os.path.join(RL.EVAL, "out_branch"), os.path.join(RL.EVAL, "out_uncr")])
        assert f"--scan_dirs {sd} " in c and "gpu_guard.py --gpu 1 --min_free_mib 4096" in c
        assert f"--usd_root {os.path.join(p_['dir'], 'usd')} --attempt {p_['attempt_id']} " in c, c
        assert f"--stop_file {os.path.join(RL.OUT_RAND, 'STOP')} --deadline 0.0 -- " in c
        assert "usd_isolate_run.py " + os.path.join(RL.HERE, "q_rand.py") + " --scene" in c  # isolation wraps q_rand directly
        assert "/_eval/out/" not in c.replace("\\", "/") and "handover" not in c
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


def test_no_dashes_in_sources():
    bad = {}
    for f in ("q_rand.py", "rand_lib.py", "rand_gate.py", "rand_overlay.py", "rand_driver.py", "test_rand_scenes.py", "README-rand-scenes.md"):
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            t = open(p, encoding="utf-8").read()
            n = t.count("\u2014") + t.count("\u2013") + t.count("\u2212")
            if n:
                bad[f] = n
    assert not bad, bad


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
               "code_sha256": {f: RL.sha256_file(os.path.join(HERE, f)) for f in ("q_rand.py", "rand_lib.py", "rand_gate.py", "rand_overlay.py", "rand_driver.py", "test_rand_scenes.py")}}
    with open(os.path.join(ROOT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({"passed": summary["passed"], "total": summary["total"], "results": os.path.join(ROOT, "results.json")}))
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
