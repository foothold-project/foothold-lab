"""lower_obs_probe 의 계산부 CPU 시험: 중력 투영 식 · 칸 대조 · 순서가 틀리면 잡히는지."""
import numpy as np
import pytest

from foothold_s2.nav import lower_obs_probe as lp


def test_projected_gravity_known_cases():
    up = np.array([[1.0, 0, 0, 0]])
    assert lp.projected_gravity(up) == pytest.approx(np.array([[0.0, 0.0, -1.0]]))
    roll = lp.quat_wxyz_from_rpy(np.pi / 2, 0, 0)[None]               # x 축 둘레 90 도
    assert lp.projected_gravity(roll)[0] == pytest.approx([0.0, -1.0, 0.0], abs=1e-12)     # R^T g = (0, -sin, -cos)
    yaw_only = lp.quat_wxyz_from_rpy(0, 0, 1.3)[None]
    assert lp.projected_gravity(yaw_only)[0] == pytest.approx([0, 0, -1.0])
    q = lp.quat_wxyz_from_rpy(*lp.TILT_RPY)[None]
    assert np.linalg.norm(lp.projected_gravity(q)) == pytest.approx(1.0)


def _obs_for(q, jp, jd):
    n = len(q)
    o = np.zeros((n, 45))
    o[:, 3:6] = lp.projected_gravity(q); o[:, 9:21] = jp - jd
    return o


def test_compare_obs_passes_and_catches_wrong_quaternion_order():
    q = lp.quat_wxyz_from_rpy(*lp.TILT_RPY)[None].repeat(3, 0)
    jp, jd = np.full((3, 12), 0.2), np.full((3, 12), 0.1)
    kw = dict(ang_vel_b=np.zeros((3, 3)), command=np.zeros((3, 3)), joint_pos=jp, default_joint_pos=jd, joint_vel=np.zeros((3, 12)), last_action=np.zeros((3, 12)))
    good = lp.compare_obs(_obs_for(q, jp, jd), quat_wxyz=q, **kw)
    assert good["passed"] and good["n"] == 3
    swapped = q[:, [1, 2, 3, 0]]                                       # xyzw 를 wxyz 라고 읽은 경우
    bad = lp.compare_obs(_obs_for(q, jp, jd), quat_wxyz=swapped, **kw)
    assert not bad["passed"] and bad["max_abs_err"]["projected_gravity"] > 0.05
    shifted = _obs_for(q, jp, jd); shifted[:, 9:21] += 0.01
    assert not lp.compare_obs(shifted, quat_wxyz=q, **kw)["passed"]


def test_camera_cfg_rot_points_the_optical_axis_down_by_the_pitch_for_both_majors():
    """reviewer 13:38 조건 1: hl_student 카메라 rot 를 cfg 에 넣는 호출 지점. 2.x 는 wxyz · 3.0 은 xyzw 로 넣어도 같은 방향 (몸 앞축 +x 에서 아래로 35 도)."""
    import math

    from foothold_s2.lab_compat import quat_cfg
    from foothold_s2.nav import hl_student
    from foothold_s2.nav import lower_obs_probe as lp

    for major in (2, 3):
        rot = quat_cfg(hl_student.pitch_down_quat_wxyz(hl_student.CAMERA_PITCH_DEG), major)
        fwd = lp.rotate_wxyz(lp.cfg_rot_to_wxyz(rot, major), (1.0, 0.0, 0.0))
        pitch = math.degrees(math.asin(-fwd[2]))
        assert pitch == pytest.approx(hl_student.CAMERA_PITCH_DEG, abs=1e-6) and fwd[1] == pytest.approx(0.0, abs=1e-9), major
    wrong = lp.rotate_wxyz(lp.cfg_rot_to_wxyz(quat_cfg(hl_student.pitch_down_quat_wxyz(35.0), 2), 3), (1.0, 0.0, 0.0))   # 2.x 순서를 3.0 으로 읽으면 방향이 달라진다 (시험이 순서를 본다는 증거)
    assert abs(math.degrees(math.asin(-wrong[2])) - 35.0) > 1.0


def test_expected_center_depth_matches_hand_geometry_and_follows_the_body_tilt():
    import math

    from foothold_s2.nav import hl_student
    from foothold_s2.nav import lower_obs_probe as lp

    from foothold_s2.lab_compat import quat_cfg

    rot = lp.cfg_rot_to_wxyz(quat_cfg(hl_student.pitch_down_quat_wxyz(hl_student.CAMERA_PITCH_DEG), 3), 3)
    level = lp.expected_center_depth((0, 0, 0.30), (1, 0, 0, 0), 0.0, hl_student.CAMERA_POS_M, rot)
    assert level == pytest.approx((0.30 + hl_student.CAMERA_POS_M[2]) / math.sin(math.radians(35.0)), rel=1e-9)     # 손 계산: 높이 / sin(35 도)
    pitched = lp.quat_wxyz_from_rpy(0.0, math.radians(10.0), 0.0)                                                     # 몸이 앞으로 10 도 숙이면 더 아래를 본다 -> 더 가깝다
    assert lp.expected_center_depth((0, 0, 0.30), pitched, 0.0, hl_student.CAMERA_POS_M, rot) < level
    up = lp.expected_center_depth((0, 0, 0.30), lp.quat_wxyz_from_rpy(0.0, math.radians(-40.0), 0.0), 0.0, hl_student.CAMERA_POS_M, rot)
    assert up is None                                                                                                 # 코를 들어 지면을 못 보면 값 없음


def test_expected_joint_order_is_the_232_probe_manifest_order():
    import json
    from pathlib import Path

    from foothold_s2.nav import lower_obs_probe as lp

    manifest = Path(__file__).resolve().parents[2] / "sim/eval/results/20260929-axis2-ext-clips/v1/probe_manifest.json"
    if manifest.is_file():                                   # 정본 기록 (2.3.2 에서 하위 정책이 돌 때 남긴 관절 순서) 과 같아야 한다
        assert list(lp.JOINT_NAMES_232) == json.loads(manifest.read_text(encoding="utf-8"))["joint_names"]
    assert lp.JOINT_NAMES_232[:4] == ("FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint") and len(lp.JOINT_NAMES_232) == 12


def test_kit_entry_refuses_without_a_declared_lab_major(monkeypatch):
    """reviewer 13:38 권고: FOOTHOLD_LAB_MAJOR 가 없으면 Kit 진입점이 거절한다 (설치 버전을 못 읽어 조용히 2 로 떨어지는 것을 막음)."""
    from foothold_s2 import lab_compat

    monkeypatch.delenv("FOOTHOLD_LAB_MAJOR", raising=False)
    with pytest.raises(RuntimeError, match="FOOTHOLD_LAB_MAJOR"):
        lab_compat.require_declared_major()
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "4")
    with pytest.raises(RuntimeError, match="FOOTHOLD_LAB_MAJOR"):
        lab_compat.require_declared_major()
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "3")
    monkeypatch.setattr("importlib.metadata.version", lambda name: "0.54.2")
    with pytest.raises(RuntimeError, match="maps to Lab"):
        lab_compat.require_declared_major()
    monkeypatch.setattr("importlib.metadata.version", lambda name: "28.0.0")
    assert lab_compat.require_declared_major() == 3
