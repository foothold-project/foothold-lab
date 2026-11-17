"""Isaac Lab 2.3.2 / 3.0 호환 층 (lab_compat) CPU 시험: 쿼터니언 순서 · ProxyArray · 카메라 cfg · 열 단위 reset · NavEnv 상태.
판은 환경 변수 FOOTHOLD_LAB_MAJOR 로 정한다 (Isaac 없이). 3.0 의 실제 값 (xyzw) 은 R3b 카메라 벤치와 3.0 migrating.rst 로 확인한 것."""
import math
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2 import lab_compat as lc
from foothold_s2.nav import teacher_obs as to


def yaw_quat_wxyz(yaw):
    return np.array([[math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]])


@pytest.mark.parametrize("major", [2, 3])
def test_quat_roundtrip_and_yaw(major, monkeypatch):
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", str(major))
    wxyz = yaw_quat_wxyz(0.7)
    sim = lc.quat_to_sim(wxyz)                          # 시뮬이 주는 순서
    assert (sim[0, 2] == pytest.approx(math.sin(0.35)) and sim[0, 3] == pytest.approx(math.cos(0.35))) if major == 3 else (sim == wxyz).all()
    back = lc.quat_wxyz(sim)
    assert np.allclose(back, wxyz)
    assert to.yaw_from_quat_wxyz(back)[0] == pytest.approx(0.7)


def test_yaw_is_wrong_without_the_conversion_on_3(monkeypatch):
    """허위 통과 방지: 변환 없이 xyzw 를 wxyz 함수에 넣으면 yaw 가 틀린다 (조용히 틀리는 곳이 실제로 있었다는 증거)."""
    sim = yaw_quat_wxyz(0.7)[:, [1, 2, 3, 0]]
    assert abs(to.yaw_from_quat_wxyz(sim)[0] - 0.7) > 0.1


def test_camera_cfg_quat_order(monkeypatch):
    from foothold_s2.nav.hl_student import pitch_down_quat_wxyz
    q = pitch_down_quat_wxyz(35.0)
    h = math.radians(35.0) / 2
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "3")
    assert lc.quat_cfg(q) == pytest.approx((0.0, math.sin(h), 0.0, math.cos(h)))     # xyzw
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "2")
    assert lc.quat_cfg(q) == pytest.approx((math.cos(h), 0.0, math.sin(h), 0.0))     # wxyz


def test_th_unwraps_proxy_and_passes_tensor():
    t = torch.arange(6.0).reshape(2, 3)
    assert lc.th(SimpleNamespace(torch=t)) is t
    assert lc.th(t) is t
    a = np.zeros(3)
    assert lc.th(a) is a


def test_bad_major_is_refused(monkeypatch):
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "4")
    with pytest.raises(ValueError):
        lc.lab_major()


def test_column_reset_writes_the_sim_order(monkeypatch):
    """3.0: default_root_state 의 쿼터니언도 쓰는 쿼터니언도 xyzw. yaw 0.5 rad 만 표본하면 xyzw (0, 0, sin .25, cos .25) 가 써져야 한다."""
    from foothold_s2.terrains import ex42_column_reset as cr
    n = 2
    for major, default_q, want in ((3, [0.0, 0.0, 0.0, 1.0], [0.0, 0.0, math.sin(0.25), math.cos(0.25)]),
                                   (2, [1.0, 0.0, 0.0, 0.0], [math.cos(0.25), 0.0, 0.0, math.sin(0.25)])):
        monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", str(major))
        root = torch.zeros(n, 13); root[:, 3:7] = torch.tensor(default_q)
        written = {}
        asset = SimpleNamespace(device="cpu", data=SimpleNamespace(default_root_state=root),
                                write_root_pose_to_sim=lambda pose, env_ids=None: written.setdefault("pose", pose),
                                write_root_velocity_to_sim=lambda v, env_ids=None: None)
        class Scene:
            def __getitem__(self, k):
                return asset
        scene = Scene()
        scene.terrain, scene.env_origins = SimpleNamespace(terrain_types=torch.zeros(n)), torch.zeros(n, 3)
        env = SimpleNamespace(scene=scene)
        lo = hi = torch.zeros(1, 6); lo = lo.clone(); lo[0, 5] = 0.5; hi = lo.clone()
        cr.reset_root_state_by_column(env, torch.arange(n), lo, hi, {})
        assert written["pose"][:, 3:7] == pytest.approx(torch.tensor([want] * n), abs=1e-6)


def test_nav_env_state_is_wxyz_on_3(monkeypatch):
    """NavEnv 가 읽는 몸통 쿼터니언은 어느 판에서도 wxyz 로 나와 teacher 관측 (yaw) 이 맞는다. ProxyArray 도 풀어서 읽는다."""
    from foothold_s2.nav import command_space as cs
    from foothold_s2.nav.nav_env import NavEnv
    from foothold_s2.tests.test_nav_env_cpu import PREP, FakeEnv, FakeLower

    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "3")
    fake = FakeEnv(n=2)
    sim_q = torch.tensor(yaw_quat_wxyz(0.7)[:, [1, 2, 3, 0]], dtype=torch.float32).repeat(2, 1)     # 3.0 순서
    fake.data.root_quat_w = SimpleNamespace(torch=sim_q)                                            # ProxyArray 꼴
    fake.data.root_pos_w = SimpleNamespace(torch=fake.data.root_pos_w)
    fake.data.root_lin_vel_b = SimpleNamespace(torch=fake.data.root_lin_vel_b)
    fake.data.root_ang_vel_b = SimpleNamespace(torch=fake.data.root_ang_vel_b)
    fake.data.joint_pos = SimpleNamespace(torch=fake.data.joint_pos)
    fake.data.default_joint_pos = SimpleNamespace(torch=fake.data.default_joint_pos)
    fake.sensor.data.net_forces_w = SimpleNamespace(torch=fake.sensor.data.net_forces_w)
    nav = NavEnv(fake, FakeLower(fake.n), cs.CommandSpace(cs.slots_from_stage_row(PREP, "E1F"), "clip"))
    state = nav.reset()
    assert to.yaw_from_quat_wxyz(state.quat_w) == pytest.approx([0.7, 0.7], abs=1e-5)
