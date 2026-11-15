"""Go2 모델 L0 (17 §9): 종아리 DCMotor 토크식 · 관절 이름 분할. 설치된 Isaac Lab 소스를 CPU 에서 그대로 실행해 대조한다."""

import ast
import os
import re
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.robots import go2_params as gp

ACTUATOR_PD = "C:/isaac/IsaacLab/source/isaaclab/isaaclab/actuators/actuator_pd.py"
URDF = "C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf"


def _installed_clip_effort():
    """설치 DCMotor._clip_effort 소스를 AST 로 꺼내 그대로 실행 가능한 함수로 만든다 (Kit 불필요)."""
    if not os.path.isfile(ACTUATOR_PD):
        pytest.skip("설치된 Isaac Lab 없음")

    tree = ast.parse(open(ACTUATOR_PD, encoding="utf-8").read())

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DCMotor":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "_clip_effort":
                    module = ast.Module(body=[fn], type_ignores=[])
                    ns = {"torch": torch}
                    exec(compile(ast.fix_missing_locations(module), ACTUATOR_PD, "exec"), ns)
                    return ns["_clip_effort"]

    raise AssertionError("DCMotor._clip_effort 를 못 찾았습니다")


def _dummy_motor(effort_limit, saturation, velocity_limit, joint_vel):
    qd = torch.as_tensor(joint_vel, dtype=torch.float32).clone()

    return SimpleNamespace(_joint_vel=qd, _saturation_effort=saturation, effort_limit=effort_limit,
                           velocity_limit=velocity_limit,
                           _vel_at_effort_lim=velocity_limit * (1 + effort_limit / saturation))


def test_calf_torque_curve_matches_astra_table():
    vel = torch.tensor([0.0, 7.85, 15.70, 20.00])
    plus = gp.calf_clip(torch.full((4,), 100.0), vel)
    minus = gp.calf_clip(torch.full((4,), -100.0), vel)
    assert plus.tolist() == pytest.approx([45.43, 22.715, 0.0, -12.443], abs=1e-3)
    assert minus.tolist() == pytest.approx([-45.43] * 4, abs=1e-3)


def test_negative_control_hip_velocity_limit_30_gives_plus_21_67_at_15_70():
    out = gp.dc_motor_clip(torch.tensor([100.0]), torch.tensor([15.70]), 45.43, 45.43, 30.0)
    # 17 §9 는 +21.67 이라 적었고 식으로 계산하면 45.43 x (1 - 15.70 / 30) = 21.655 다 (문서 반올림 0.015 차이).
    assert float(out[0]) == pytest.approx(21.655, abs=0.005)
    assert float(out[0]) == pytest.approx(21.67, abs=0.02)


def test_my_formula_equals_the_installed_dcmotor_source_on_a_grid():
    fn = _installed_clip_effort()
    vel = torch.linspace(-40.0, 40.0, 161)
    eff = torch.linspace(-120.0, 120.0, 161)
    grid_v, grid_e = torch.meshgrid(vel, eff, indexing="ij")
    for params in (gp.CALF, gp.HIP_THIGH):
        motor = _dummy_motor(params["effort_limit"], params["saturation_effort"], params["velocity_limit"],
                             grid_v.clone())
        installed = fn(motor, grid_e)
        mine = gp.dc_motor_clip(grid_e, grid_v, params["effort_limit"], params["saturation_effort"],
                                params["velocity_limit"])
        assert torch.allclose(installed, mine, atol=1e-5)


def test_installed_source_reproduces_astra_table_for_calf():
    fn = _installed_clip_effort()
    vel = torch.tensor([0.0, 7.85, 15.70, 20.00])
    motor = _dummy_motor(45.43, 45.43, 15.70, vel)
    assert fn(motor, torch.full((4,), 100.0)).tolist() == pytest.approx([45.43, 22.715, 0.0, -12.443], abs=1e-3)
    motor = _dummy_motor(45.43, 45.43, 15.70, vel)
    assert fn(motor, torch.full((4,), -100.0)).tolist() == pytest.approx([-45.43] * 4, abs=1e-3)


def test_joint_regex_splits_the_twelve_real_urdf_joints_into_8_and_4():
    if not os.path.isfile(URDF):
        pytest.skip("URDF 없음")

    names = [j.get("name") for j in ET.parse(URDF).getroot().iter("joint") if j.get("type") == "revolute"]
    assert len(names) == 12, names
    hip_thigh = [n for n in names if any(re.fullmatch(p, n) for p in gp.HIP_THIGH_JOINTS)]
    calf = [n for n in names if any(re.fullmatch(p, n) for p in gp.CALF_JOINTS)]
    assert len(hip_thigh) == 8 and len(calf) == 4
    assert set(hip_thigh) | set(calf) == set(names) and not (set(hip_thigh) & set(calf))


def test_urdf_calf_values_are_the_frozen_ones():
    if not os.path.isfile(URDF):
        pytest.skip("URDF 없음")

    calf_limits = [j.find("limit") for j in ET.parse(URDF).getroot().iter("joint") if "calf" in j.get("name", "")
                   and j.get("type") == "revolute"]
    assert len(calf_limits) == 4
    for lim in calf_limits:
        assert float(lim.get("effort")) == pytest.approx(gp.CALF["effort_limit"], abs=0.01)
        assert float(lim.get("velocity")) == pytest.approx(gp.CALF["velocity_limit"], abs=0.01)


def test_pie_ranges_are_the_approved_ones():
    assert gp.PIE["base_mass_add_kg"] == (-1.0, 2.0)
    assert gp.PIE["friction"] == (0.2, 1.2)
    assert gp.PIE["gain_scale"] == (0.9, 1.1)
