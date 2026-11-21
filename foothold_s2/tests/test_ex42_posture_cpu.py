"""EX-42 하위 자세 명령 (ex42_posture · EX42_POSTURE · lead 2026-11-21 19:34): 꺼짐이면 그대로 · 켜짐이면 원문 범위의 명령 · 관측 [h - H0, roll] ·
원문 Table III 보상 둘 · runner 가 범위 안 값만 받음. CPU only."""
from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.commands import ex42_posture as ps
from foothold_s2.runners.start_runner import StartRunner

ROOT = Path(__file__).resolve().parents[2]
KEYS = ("EX42_POSTURE", "EX42_POSTURE_H_RANGE", "EX42_POSTURE_ROLL_RANGE", "EX42_POSTURE_H0", "EX42_POSTURE_HEIGHT_W", "EX42_POSTURE_ROLL_W")


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


class _Cfg:
    def __init__(self, func=None, weight=0.0, params=None):
        self.func, self.weight, self.params = func, weight, dict(params or {})


def _zero(env):
    return torch.zeros((env.num_envs, 2))


def _env(n=6, z=0.31, quat=None, hits_z=0.0, cmd=None, step=1):
    quat = torch.tensor([[1.0, 0, 0, 0]]).repeat(n, 1) if quat is None else quat
    cmd = torch.zeros((n, 3)) if cmd is None else cmd
    robot = SimpleNamespace(data=SimpleNamespace(root_pos_w=torch.column_stack([torch.zeros(n), torch.zeros(n), torch.full((n,), z)]), root_quat_w=quat))
    scanner = SimpleNamespace(data=SimpleNamespace(ray_hits_w=torch.full((n, 5, 3), hits_z)))
    scene = {"robot": robot, "height_scanner": scanner}
    env = SimpleNamespace(num_envs=n, device="cpu", episode_length_buf=torch.full((n,), step),
                          command_manager=SimpleNamespace(get_command=lambda name: cmd), scene=SimpleNamespace(**{}))
    env.scene = type("S", (), {"__getitem__": lambda self, k: scene[k], "env_origins": torch.zeros((n, 3))})()
    return env


def test_off_changes_nothing():
    assert ps.enabled() is False
    group = SimpleNamespace(pose_cmd=SimpleNamespace(func=_zero, params={}))
    assert ps.register_observation(group) is False and group.pose_cmd.func is _zero
    cfg = SimpleNamespace(rewards=SimpleNamespace(track_lin_vel=_Cfg()))
    assert ps.register_rewards(cfg, _Cfg) is False and sorted(vars(cfg.rewards)) == ["track_lin_vel"]
    raw = TensorDict({"pose_cmd": torch.tensor([[0.0, 0.1]])}, batch_size=[1])
    with pytest.raises(ValueError, match="must be finite and zero in this stage"):
        StartRunner._pose_command(raw)                                   # the old D93 zero check stays when off


def test_values_without_the_switch_are_a_mistake(monkeypatch):
    monkeypatch.setenv("EX42_POSTURE_H_RANGE", "0.2,0.3")
    with pytest.raises(ValueError, match="EX42_POSTURE is not 1"):
        ps.enabled()


def test_on_draws_paper_ranges_and_redraws_only_on_command_change_or_new_episode(monkeypatch, capsys):
    monkeypatch.setenv("EX42_POSTURE", "1")
    group = SimpleNamespace(pose_cmd=SimpleNamespace(func=_zero, params={}))
    assert ps.register_observation(group) and group.pose_cmd.func is ps.posture_command_obs
    cmd = torch.zeros((200, 3))
    env = _env(200, cmd=cmd)
    a = ps.posture_command_obs(env)
    h = a[:, 0] + ps.H0_DEFAULT
    assert a.shape == (200, 2) and h.min() >= 0.1 - 1e-6 and h.max() <= 0.4 + 1e-6
    assert a[:, 1].min() >= -1.0 and a[:, 1].max() <= 1.0 and a[:, 1].std() > 0.3
    env.episode_length_buf[:] = 5
    assert torch.equal(ps.posture_command_obs(env), a)                  # same command, same episode: same target
    cmd[:3, 0] = 0.5; env.episode_length_buf[-2:] = 1
    b = ps.posture_command_obs(env)
    assert not torch.equal(b[:3], a[:3]) and not torch.equal(b[-2:], a[-2:]) and torch.equal(b[3:-2], a[3:-2])
    cfg = SimpleNamespace(rewards=SimpleNamespace())
    assert ps.register_rewards(cfg, _Cfg)
    assert cfg.rewards.ex42_posture_height.weight == 0.2 and cfg.rewards.ex42_posture_roll.weight == 0.2
    assert "EX42_POSTURE where=start h=[0.1, 0.4] roll=[-1.0, 1.0]" in capsys.readouterr().out


def test_paper_rewards(monkeypatch):
    monkeypatch.setenv("EX42_POSTURE", "1")
    env = _env(2, z=0.36, hits_z=0.05)                                  # body 0.31 m above the scanned ground
    st = ps._state(env)
    st.target[:] = torch.tensor([[0.31, 0.0], [0.3125, 0.0]])
    r = ps.height_tracking(env)
    assert r[0] == pytest.approx(1.0) and r[1] == pytest.approx(math.exp(-0.0025 / 0.0025))
    roll = 0.2
    q = torch.tensor([[math.cos(roll / 2), math.sin(roll / 2), 0.0, 0.0]] * 2)
    env2 = _env(2, quat=q); st2 = ps._state(env2); st2.target[:, 1] = torch.tensor([0.2, 0.25])
    rr = ps.roll_tracking(env2)
    assert rr[0] == pytest.approx(1.0, abs=1e-5) and rr[1] == pytest.approx(math.exp(-0.05 / 0.05), rel=1e-4)


def test_runner_takes_in_range_values_only_when_on(monkeypatch):
    monkeypatch.setenv("EX42_POSTURE", "1")
    ok = TensorDict({"pose_cmd": torch.tensor([[0.4 - ps.H0_DEFAULT, -1.0], [0.1 - ps.H0_DEFAULT, 0.7]])}, batch_size=[2])
    assert torch.equal(StartRunner._pose_command(ok), ok["pose_cmd"])
    bad = TensorDict({"pose_cmd": torch.tensor([[0.0, 1.2]])}, batch_size=[1])
    with pytest.raises(ValueError, match="outside the posture ranges"):
        StartRunner._pose_command(bad)


@pytest.mark.parametrize("key,val", [("EX42_POSTURE_H_RANGE", "0.05,0.4"), ("EX42_POSTURE_ROLL_RANGE", "-1.5,1.0"), ("EX42_POSTURE_H_RANGE", "x"),
                                     ("EX42_POSTURE_HEIGHT_W", "-1"), ("EX42_POSTURE_H0", "nan")])
def test_bad_values_refuse(monkeypatch, key, val):
    monkeypatch.setenv("EX42_POSTURE", "1"); monkeypatch.setenv(key, val)
    with pytest.raises(ValueError):
        ps.settings()


def test_the_real_wiring_points_call_the_module():
    src = (ROOT / "foothold_s2/sensors/start_obs.py").read_text(encoding="utf-8")
    i = src.index("def apply_ex41_pose_observation")
    assert "ex42_posture.register_observation(obs.pose_cmd)" in src[i:i + 900]
    seg = (ROOT / "foothold_s2/commands/ex42_segment_adjust.py").read_text(encoding="utf-8")
    assert "ex42_posture.register_rewards(env_cfg, term_cfg_class)" in seg


CUR_KEYS = ps.CURRICULUM_KEYS


@pytest.fixture
def clean_cur(monkeypatch):
    for k in CUR_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_only_flat_and_continuous_non_flag_envs_get_a_posture(monkeypatch, clean_cur):
    monkeypatch.setenv("EX42_POSTURE", "1")
    env = _env(4)
    table = [{"family": "A", "kind": "flat"}, {"family": "A", "kind": "boxes"}, {"family": "A", "kind": "gaps"}, {"family": "B", "kind": "beam"}]
    env._ex42_column_table = table
    env.scene.terrain = SimpleNamespace(terrain_types=torch.tensor([0, 1, 2, 3]))
    flag = torch.tensor([False, True, False, False])
    env.command_manager.get_term = lambda name: SimpleNamespace(is_flag_env=flag)
    out = ps.posture_command_obs(env)
    st = ps._state(env)
    assert st.active.tolist() == [True, False, False, False]                # flag env 1 · sparse A/gaps 2 · B family 3 get posture 0
    assert torch.equal(out[1:], torch.zeros(3, 2)) and torch.equal(st.effective()[1:, 0], torch.full((3,), ps.H0_DEFAULT))


def test_curriculum_starts_narrow_widens_on_tracking_and_survives_a_resume(monkeypatch, clean_cur, tmp_path, capsys):
    monkeypatch.setenv("EX42_POSTURE", "1"); monkeypatch.setenv("EX42_POSTURE_CURRICULUM", "1")
    monkeypatch.setenv("EX42_POSTURE_CHECK_STEPS", "48"); monkeypatch.setenv("EX42_POSTURE_STATE", str(tmp_path / "pz.json"))
    n = 64
    env = _env(n, z=ps.H0_DEFAULT)
    a = ps.posture_command_obs(env)
    h = a[:, 0] + ps.H0_DEFAULT
    assert h.min() >= ps.H0_DEFAULT - 0.02 - 1e-6 and h.max() <= ps.H0_DEFAULT + 0.02 + 1e-6 and a[:, 1].abs().max() <= 0.1 + 1e-6
    st = ps._state(env)
    # the body follows the target exactly: errors 0 -> both bands widen at the first check
    env.scene["robot"].data.root_pos_w[:, 2] = st.target[:, 0]
    roll = st.target[:, 1]
    env.scene["robot"].data.root_quat_w = torch.stack([torch.cos(roll / 2), torch.sin(roll / 2), torch.zeros(n), torch.zeros(n)], 1)
    for _ in range(48):
        ps.height_tracking(env)
    line = [l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_POSTURE_CHECK")][-1]
    got = __import__("json").loads(line.split(" ", 1)[1])
    assert got["widen_h"] and got["widen_roll"] and got["med_h_err"] < 1e-4 and got["slope_h"] == pytest.approx(1.0, abs=1e-3)
    assert st.h_half == pytest.approx(0.04) and st.roll_half == pytest.approx(0.2)
    # standing at H0 whatever the target: median error ~ half of the half-width -> no widening
    env.scene["robot"].data.root_pos_w[:, 2] = ps.H0_DEFAULT
    env.episode_length_buf[:] = 1
    ps.posture_command_obs(env)
    env.episode_length_buf[:] = 5
    for _ in range(48):
        ps.height_tracking(env)
    got = __import__("json").loads([l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_POSTURE_CHECK")][-1].split(" ", 1)[1])
    assert not got["widen_h"] and st.h_half == pytest.approx(0.04)
    # a new env object (same OUT resume) reads the band back
    env2 = _env(n)
    ps.posture_command_obs(env2)
    assert ps._state(env2).h_half == pytest.approx(0.04) and ps._state(env2).roll_half == pytest.approx(0.2)


def test_curriculum_values_need_the_switch(monkeypatch, clean_cur):
    monkeypatch.setenv("EX42_POSTURE", "1"); monkeypatch.setenv("EX42_POSTURE_H_START", "0.02")
    with pytest.raises(ValueError, match="EX42_POSTURE_CURRICULUM is not 1"):
        ps.settings()
    monkeypatch.delenv("EX42_POSTURE"); monkeypatch.delenv("EX42_POSTURE_H_START"); monkeypatch.setenv("EX42_POSTURE_CURRICULUM", "1")
    with pytest.raises(ValueError, match="EX42_POSTURE is not 1"):
        ps.enabled()


def test_band_stops_at_the_paper_ranges():
    cfg = {"curriculum": True, "h": (0.1, 0.4), "roll": (-1.0, 1.0), "h0": 0.33}
    assert ps.band(cfg, 0.02, 0.1) == ((pytest.approx(0.31), pytest.approx(0.35)), (-0.1, 0.1))
    assert ps.band(cfg, 0.5, 2.0) == ((0.1, 0.4), (-1.0, 1.0))


def _quat_rpy(roll=0.0, pitch=0.0):
    cr, sr, cp, sp = math.cos(roll / 2), math.sin(roll / 2), math.cos(pitch / 2), math.sin(pitch / 2)
    return [cr * cp, sr * cp, cr * sp, -sr * sp]          # yaw 0 · (w x y z)


def test_orientation_is_pitch_only_paper_on_posture_envs_and_old_elsewhere(monkeypatch):
    """lead 11/22 03:00 · planner 02:59: 원문 r7 = -0.5 |θ_y| (pitch 만). 옛 g_x² + g_y² 는 roll 명령을 따르면 깎였다 (roll 1.0 에서 -0.71)."""
    monkeypatch.setenv("EX42_POSTURE", "1")
    q = torch.tensor([_quat_rpy(roll=1.0), _quat_rpy(pitch=0.3), _quat_rpy(roll=1.0), _quat_rpy(pitch=0.3)])
    env = _env(4, quat=q)
    g = torch.stack([torch.tensor([-math.sin(0.0), math.sin(1.0) * math.cos(0.0), -math.cos(1.0)]),
                     torch.tensor([math.sin(0.3), 0.0, -math.cos(0.3)])] * 2)            # 몸 좌표계 중력 (Isaac projected_gravity_b 꼴)
    env.scene["robot"].data.projected_gravity_b = g
    env.reward_manager = SimpleNamespace(get_term_cfg=lambda name: _Cfg(weight=-1.0))
    st = ps._state(env)
    st.active = torch.tensor([True, True, False, False])
    r = ps.posture_orientation(env)
    assert r[0] == pytest.approx(0.0, abs=1e-6)                                       # roll 1.0 을 따른 몸: 벌 0 (옛 식이면 0.71)
    assert r[1] == pytest.approx(0.5 * 0.3, rel=1e-4)                                 # pitch 0.3: 0.5 x |θ_y| (가중 -1 과 곱해 -0.15)
    assert r[2] == pytest.approx(math.sin(1.0) ** 2, rel=1e-4) and r[3] == pytest.approx(math.sin(0.3) ** 2, rel=1e-4)   # 끈 env: 옛 식 그대로
    env.reward_manager = SimpleNamespace(get_term_cfg=lambda name: _Cfg(weight=-2.0))   # 실시간 조정으로 칸 가중이 바뀌어도 원문 -0.5 를 지킴
    assert ps.posture_orientation(env)[1] * -2.0 == pytest.approx(-0.5 * 0.3, rel=1e-4)


def test_register_swaps_orientation_only_when_on(monkeypatch):
    cfg = SimpleNamespace(rewards=SimpleNamespace(flat_orientation=_Cfg(func="old", weight=-1.0)))
    assert ps.register_rewards(cfg, _Cfg) is False and cfg.rewards.flat_orientation.func == "old"
    monkeypatch.setenv("EX42_POSTURE", "1")
    assert ps.register_rewards(cfg, _Cfg) is True
    assert cfg.rewards.flat_orientation.func is ps.posture_orientation and cfg.rewards.flat_orientation.weight == -1.0
