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
