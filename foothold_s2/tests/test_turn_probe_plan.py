"""우회전 probe 시행표 · 요약 · Kit 스크립트 소스 대조 (CPU 만)."""

import ast
import subprocess
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import turn_probe_logic as L
from foothold_s2.eval import turn_probe_plan as P

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "foothold_s2/eval/turn_probe.py"
SH = ROOT / "foothold_s2/run_turn_probe.sh"


def test_protocols_cover_independent_sequential_and_reversed_order_with_right_turn_negative():
    p = P.PROTOCOLS

    assert set(p) == {"indep_right", "indep_left", "fwd_then_right", "left_then_right", "right_then_left"}
    assert p["indep_right"]["cmd"] == (0, 0, -1.2) and p["indep_left"]["cmd"] == (0, 0, 1.2) and p["indep_right"]["pre"] is None
    assert p["fwd_then_right"]["pre"][0] == 0.5 and p["left_then_right"]["pre"][2] > 0 and p["right_then_left"]["pre"][2] < 0
    assert (P.RECORD_S, P.PRE_S) == (8.0, 4.0)


@pytest.mark.parametrize("name,kind", [("FL_foot", "foot"), ("RR_calf", "calf"), ("FR_thigh", "thigh"), ("RL_hip", "hip"), ("base", "base"), ("Head_upper", "head"), ("imu_link", "other")])
def test_link_classes(name, kind):
    assert P.classify_link(name) == kind


def test_yaw_follow_uses_alive_time_only():
    wz = np.array([1.2, 1.2, -5.0, -5.0])
    alive = np.array([True, True, False, False])

    assert P.yaw_follow(wz, alive, 1.2) == pytest.approx(1.0)
    assert np.isnan(P.yaw_follow(wz, np.zeros(4, bool), 1.2))


def _proto(follow, verdict="반증"):
    j = {h: {"verdict": verdict} for h in ("joint_limit", "actuator", "foot_support", "posture")}

    return {"judge": [j, j], "follow": [follow, follow]}


def test_summary_separates_contexts_forward_and_left_turn_are_not_merged():
    per = {"indep_right": _proto(0.8), "indep_left": _proto(0.9), "fwd_then_right": _proto(0.1), "left_then_right": _proto(0.78), "right_then_left": _proto(0.9)}
    s = P.summarize(per)

    assert s["order"]["right_after_forward"]["verdict"] == "지지"           # 전진 뒤에서만 정체
    assert s["order"]["right_after_left_turn"]["verdict"] == "반증"         # 좌회전 뒤 우회전은 정상: 중앙값으로 섞으면 이 정체가 흐려진다
    assert s["order"]["left_after_right_turn"]["verdict"] == "반증" and s["side_asymmetry_independent"] == pytest.approx(0.1)
    assert s["protocols"]["indep_right"]["joint_limit"] == {"반증": 2}
    same = {k: _proto(0.1) for k in per}

    assert P.summarize(same)["order"]["right_after_forward"]["verdict"] == "반증"


def test_summary_without_the_needed_protocols_is_unconfirmed():
    s = P.summarize({"indep_right": _proto(0.8)})

    assert s["order"]["right_after_forward"]["verdict"] == "미확인" and s["side_asymmetry_independent"] is None


def test_kit_script_is_valid_python_and_uses_names_that_exist():
    src = PROBE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    plan_names = {n.name for n in ast.parse(Path(P.__file__).read_text(encoding="utf-8")).body if isinstance(n, (ast.FunctionDef,))} | {"PROTOCOLS", "RECORD_S", "PRE_S"}
    logic_names = {n.name for n in ast.parse(Path(L.__file__).read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef)}
    used_p = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "P"}
    used_l = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "L"}

    assert used_p <= plan_names and used_l <= (logic_names | {"HZ"}), (used_p - plan_names, used_l - logic_names)
    for must in ("computed_torque", "applied_torque", "joint_pos_target", "joint_pos_limits", "soft_joint_pos_limits", "net_forces_w", "TURNPROBE_DONE", "raw.scene.update = _update", "x23_tasks", "_saturation_effort", "velocity_limit", "act_limits", "L.thresholds()", "L.module_blob_sha()", "terrain_levels_per_env", "joint_effort_limits_sim_NOT_USED"):
        assert must in src
    assert '"effort_limit": effort' not in src
    assert src.index("rec.on = record") < src.index("env.step(policy(obs))"), "기록 켜기는 step 앞"


def test_robot_data_names_used_by_the_probe_exist_in_the_installed_isaaclab():
    data = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation_data.py")

    if not data.exists():
        pytest.skip("Isaac Lab 소스 없음")
    text = data.read_text(encoding="utf-8")

    for name in ("computed_torque", "applied_torque", "joint_pos_target", "joint_pos_limits", "soft_joint_pos_limits", "joint_stiffness", "joint_damping", "joint_effort_limits", "root_ang_vel_b", "root_lin_vel_b", "body_lin_vel_w", "body_pos_w"):
        assert re_has(text, name), name


def re_has(text, name):
    return (f"def {name}" in text) or (f"{name}:" in text)


def test_run_script_shape_and_lf():
    raw = SH.read_bytes()

    assert b"\r" not in raw
    s = raw.decode("utf-8")
    assert "foothold_s2.eval.turn_probe" in s and "TURNPROBE_DONE" in s and "--map-mode" in s
    r = subprocess.run([r"C:\Program Files\Git\bin\bash.exe", "-n", str(SH)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)

    assert r.returncode == 0, r.stderr


def test_scene_update_hook_accepts_the_keyword_call_isaaclab_makes():
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    hook = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_update")

    assert hook.args.vararg is not None and hook.args.kwarg is not None            # scene.update(dt=physics_dt) 키워드 호출(첫 Kit 실행에서 TypeError 였다)


def test_hook_signature_matches_the_installed_isaaclab_scene_update_and_call_site():
    root = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab")
    if not root.exists():
        pytest.skip("Isaac Lab 소스 없음")
    scene_tree = ast.parse((root / "scene/interactive_scene.py").read_text(encoding="utf-8"))
    cls = next(n for n in scene_tree.body if isinstance(n, ast.ClassDef) and n.name == "InteractiveScene")
    upd = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "update")
    env_src = (root / "envs/manager_based_rl_env.py").read_text(encoding="utf-8")

    assert [a.arg for a in upd.args.args] == ["self", "dt"] and "self.scene.update(dt=self.physics_dt)" in env_src
    probe_tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    hook_def = next(n for n in ast.walk(probe_tree) if isinstance(n, ast.FunctionDef) and n.name == "_update")
    calls = []
    ns = {"_orig_update": lambda *a, **k: calls.append((a, k)), "rec": type("R", (), {"on": False})()}
    exec(compile(ast.Module(body=[hook_def], type_ignores=[]), "hook", "exec"), ns)
    ns["_update"](dt=0.005)                                                  # ManagerBasedRLEnv.step 이 하는 호출 그대로
    ns["_update"](0.005)

    assert calls == [((), {"dt": 0.005}), ((0.005,), {})]


def test_summary_leaves_out_fallen_envs_and_reports_how_many():
    j = {h: {"verdict": "반증"} for h in ("joint_limit", "actuator", "foot_support", "posture")}
    jf = {h: {"verdict": "지지"} for h in ("joint_limit", "actuator", "foot_support", "posture")}
    per = {"indep_right": {"judge": [j, jf, j, jf], "follow": [0.1, 0.9, 0.12, 0.8], "kept": [True, False, True, False]}}
    s = P.summarize(per)["protocols"]["indep_right"]

    assert s["n_env"] == 2 and s["n_total"] == 4 and s["n_excluded_fallen"] == 2 and s["follow_median"] == pytest.approx(0.11) and s["joint_limit"] == {"반증": 2}
    none = P.summarize({"indep_right": {"judge": [j], "follow": [0.5], "kept": [False]}})["protocols"]["indep_right"]

    assert none["n_env"] == 0 and np.isnan(none["follow_median"]) and none["joint_limit"] == {}
    with pytest.raises(ValueError, match="kept"):
        P.summarize({"indep_right": {"judge": [j, j], "follow": [0.1, 0.1], "kept": [True]}})


def test_probe_script_applies_fixed_terrain_checks_offset_and_filters_fallen_envs():
    src = PROBE.read_text(encoding="utf-8")

    assert '"--fixed-terrain"' in src and "probe_tiles.apply_to(raw)" in src and "START_OFFSET_MAX_M = 0.5" in src and "고정 지형 칸이 reset 뒤에 바뀌었다" in src
    assert src.index("probe_tiles.apply_to(raw)") < src.index("origin = raw.scene.env_origins.clone()") < src.index("offset = (robot.data.root_pos_w")
    assert "kept = pre_alive_end & alive_end" in src and '"kept": kept.tolist()' in src and "kept=kept" in src and '"fixed_terrain": None' in src
    assert "return obs, torch.stack(alive_hist, dim=1).cpu().numpy(), alive.cpu().numpy()" in src


def test_probe_shell_script_passes_the_fixed_terrain_flag_by_default():
    text = SH.read_text(encoding="utf-8")

    assert '$FIXED --headless' in text and 'FIXED="${FIXED_TERRAIN_FLAG---fixed-terrain}"' in text and "\r" not in text
