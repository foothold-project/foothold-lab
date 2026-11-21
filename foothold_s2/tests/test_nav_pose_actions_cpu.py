"""HiPAN 상위 5 차원 행동 스위치 (HIPAN_POSE_ACTIONS · lead 2026-11-21 19:34 (3)): 꺼짐이면 지금과 같음 (3 칸 · 관측 2401) · 켜짐이면
5 칸 · c_prev 5 · 자세 두 칸을 원문 범위로 자름 · 보상 5 열 · 자세 영수증 없는 하위면 거절. CPU only."""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.nav import pose_actions as pa


def _reload():
    from foothold_s2.nav import hl_ppo_cfg, teacher_obs
    importlib.reload(teacher_obs)
    importlib.reload(hl_ppo_cfg)
    return hl_ppo_cfg, teacher_obs


@pytest.fixture(autouse=True)
def restore(monkeypatch):
    yield
    monkeypatch.delenv(pa.ENV_SWITCH, raising=False)
    _reload()


def test_off_is_todays_layout(monkeypatch):
    monkeypatch.delenv(pa.ENV_SWITCH, raising=False)
    cfg, to = _reload()
    assert cfg.ACTION_DIM == 3 and to.TeacherObsLayout().c_prev == 3 and to.TeacherObsLayout().total == 2401   # train.log receipt total 2401
    a = np.ones((4, 3))
    assert pa.split(a)[1] is None and np.array_equal(pa.split(a)[0], a)


def test_on_has_five_actions_and_clips_posture_to_the_paper_ranges(monkeypatch):
    monkeypatch.setenv(pa.ENV_SWITCH, "1")
    cfg, to = _reload()
    assert cfg.ACTION_DIM == 5 and to.TeacherObsLayout().c_prev == 5 and to.TeacherObsLayout().total == 2403
    v, pose = pa.split(np.array([[0.5, 0.0, 0.1, -9.0, 3.0], [0.5, 0.0, 0.1, 0.05, -0.2]]))
    assert v.shape == (2, 3) and np.allclose(pose[0], [0.1 - pa.H0, 1.0]) and np.allclose(pose[1], [0.05, -0.2])
    with pytest.raises(ValueError, match=r"\(n, 3\) or \(n, 5\)"):
        pa.split(np.ones((2, 4)))


def test_rewards_use_five_columns_when_on(monkeypatch):
    from foothold_s2.nav import hl_rewards_term as hr
    q = np.tile([1.0, 0, 0, 0], (2, 1))
    st = SimpleNamespace(applied=np.zeros((2, 5)), vel_b=np.zeros((2, 3)), yaw_rate=np.zeros(2), ang_vel_b=np.zeros((2, 3)), q=np.zeros((2, 12)),
                         q0=np.zeros(12), modified=np.zeros(2, bool), collision=np.zeros(2, bool), quat_w=q, pos_local=np.array([[0, 0, pa.H0], [0, 0, pa.H0 + 0.1]]))
    kw = dict(pos_room_xy=np.zeros((2, 2)), subgoal_xy=np.ones((2, 2)), eta=np.ones(2), v_des=np.full(2, 0.5))
    monkeypatch.delenv(pa.ENV_SWITCH, raising=False)
    _total, off = hr.reward(st, cmd_prev=np.zeros((2, 3)), cmd_prev2=np.zeros((2, 3)), **kw)
    monkeypatch.setenv(pa.ENV_SWITCH, "1")
    _total, on = hr.reward(st, cmd_prev=np.zeros((2, 5)), cmd_prev2=np.zeros((2, 5)), **kw)
    assert off["r6"][1] == pytest.approx(0.0) and on["r6"][1] != pytest.approx(0.0)        # the 0.1 m height error only counts when on


def test_nav_env_refuses_five_actions_without_a_posture_lower(monkeypatch):
    from foothold_s2.nav import nav_env
    monkeypatch.setenv(pa.ENV_SWITCH, "1")
    term = SimpleNamespace(vel_command_b=torch.zeros(2, 3))
    env = SimpleNamespace(unwrapped=SimpleNamespace(command_manager=SimpleNamespace(get_term=lambda n: term)))
    space = SimpleNamespace(hold_steps=2, pose_active=False)
    with pytest.raises(ValueError, match="posture receipt"):
        nav_env.NavEnv(env, SimpleNamespace(n=2, pose_active=False), space, fix_heading=lambda t: None, sensor_name=None)


def test_h0_is_the_measured_canon3_standing_height():
    assert pa.H0 == pytest.approx(0.3461)


def test_apply_command_hands_the_pose_to_the_lower_observation(monkeypatch):
    from foothold_s2.nav import lower_adapter as la
    raw = SimpleNamespace(num_envs=2, device="cpu")
    term = SimpleNamespace(vel_command_b=torch.zeros(2, 3), stand=torch.zeros(2, dtype=torch.bool), heading=torch.zeros(2, dtype=torch.bool),
                           is_flag_env=torch.zeros(2, dtype=torch.bool), _env=raw)
    assert torch.equal(pa.pose_obs(raw), torch.zeros(2, 2))                       # before the first command
    cmd = np.array([[0.5, 0, 0, -0.1, 0.3], [0, 0, 0, 0.02, -0.5]])
    la.apply_command(term, cmd, np.zeros(2, bool), True)
    assert torch.allclose(pa.pose_obs(raw), torch.tensor([[-0.1, 0.3], [0.02, -0.5]]))
    with pytest.raises(ValueError, match="pose columns must be zero"):
        la.apply_command(term, cmd, np.zeros(2, bool), False)


def test_the_lower_runner_takes_in_range_pose_only_with_the_switch(monkeypatch):
    from tensordict import TensorDict
    from foothold_s2.runners.start_runner import StartRunner
    raw = TensorDict({"pose_cmd": torch.tensor([[0.4 - pa.H0, 1.0], [0.1 - pa.H0, -1.0]])}, batch_size=[2])
    monkeypatch.delenv(pa.ENV_SWITCH, raising=False)
    with pytest.raises(ValueError, match="zero in this stage"):
        StartRunner._pose_command(raw)
    monkeypatch.setenv(pa.ENV_SWITCH, "1")
    assert torch.equal(StartRunner._pose_command(raw), raw["pose_cmd"])
    with pytest.raises(ValueError, match="outside the paper ranges"):
        StartRunner._pose_command(TensorDict({"pose_cmd": torch.tensor([[0.2, 0.0]])}, batch_size=[1]))


def test_pose_receipt_is_read_by_the_lower_adapter(tmp_path):
    from foothold_s2.nav import lower_adapter as la, pose_receipt as pr
    ck = tmp_path / "model_250.pt"; ck.write_bytes(b"lower")
    ev = tmp_path / "judge.md"; ev.write_text("rx2pz graduation")
    with pytest.raises(ValueError, match="--passed"):
        pr.write(ck, ev, "lead line", tmp_path / "r0.json")
    rec = pr.write(ck, ev, "lead line", tmp_path / "r.json", passed=True)
    assert la.pose_active_from_receipt(rec, la.file_sha256(ck)) and not la.pose_active_from_receipt(rec, "0" * 64)


def test_the_real_wiring_points():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = (root / "tasks/nav_env_cfg.py").read_text(encoding="utf-8")
    assert "env_cfg.observations.pose_cmd.pose_cmd.func = pose_actions.pose_obs" in cfg and "pose_receipt=pose_receipt)" in cfg
    assert 'cfg.get("lower_pose_receipt")' in (root / "nav/kit_factories.py").read_text(encoding="utf-8")


def test_hl5d_paper_knobs_are_wired_and_default_off():
    """factory v_des_max · vx_max · lower_map_mode (lead 11/21 22:01 · 원문 값 판): 없으면 옛 값 그대로 (0.3~1.0 · 1.0 · eval_gt)."""
    from pathlib import Path
    from foothold_s2.nav import command_space as cs, kit_factories as kf, rewards_hl
    root = Path(__file__).resolve().parents[1]
    src = (root / "nav/kit_factories.py").read_text(encoding="utf-8")
    assert 'v_des_range=(0.3, float(cfg["v_des_max"])) if "v_des_max" in cfg else None' in src
    assert 'map_mode=str(cfg.get("lower_map_mode", "eval_gt"))' in src and 'vx_max=float(cfg["vx_max"]) if "vx_max" in cfg else None' in src
    assert rewards_hl.V_DES_RANGE == (0.3, 1.0) and cs.VX_MAX == 1.0
    import inspect
    assert inspect.signature(kf.make_task).parameters["v_des_range"].default is None
    assert "vx_max" in (root / "tasks/nav_env_cfg.py").read_text(encoding="utf-8")
