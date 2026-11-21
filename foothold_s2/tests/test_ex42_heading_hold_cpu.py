"""ex42_heading_hold: integrated heading error while the turn command is zero, off by default (EX42_HEADING_HOLD,
lead 2026-11-21 17:21). CPU only."""
from __future__ import annotations

import math
import types
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.rewards import ex42_heading_hold as hh

ROOT = Path(__file__).resolve().parents[2]
MANAGER = Path("/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py")


def test_value_is_minus_the_wrapped_heading_error_only_where_the_turn_command_is_zero():
    yaw = torch.tensor([0.3, -0.2, 3.1, 0.3, 0.3])
    psi0 = torch.tensor([0.0, 0.0, -3.1, 0.0, 0.0])
    cmd = torch.tensor([[0.1, 0, 0], [0.5, 0, 0], [0.0, 0, 0], [0.5, 0, 0.4], [0.5, 0, 0]])
    excluded = torch.tensor([False, False, False, False, True])
    v = hh.heading_hold_value(yaw, cmd, psi0, excluded=excluded)
    assert v[0] == pytest.approx(-0.3) and v[1] == pytest.approx(-0.2)
    assert v[2] == pytest.approx(-(2 * math.pi - 6.2), abs=1e-5)          # across +-pi: 0.083 rad, not 6.2
    assert v[3] == 0.0 and v[4] == 0.0                                       # turning env · flag/heading env
    assert hh.heading_hold_value(yaw, cmd, yaw)[:3].abs().max() == 0.0       # held heading: 0


def test_psi0_is_taken_again_when_the_command_changes_or_the_episode_starts():
    s = hh.HeadingHoldState(3, "cpu")
    cmd = torch.tensor([[0.2, 0, 0], [0.2, 0, 0], [0.0, 0, 0]])
    assert s.update(torch.tensor([0.1, 0.2, 0.3]), cmd, torch.zeros(3, dtype=torch.bool)).all()   # first call takes all
    assert not s.update(torch.tensor([0.5, 0.5, 0.5]), cmd, torch.zeros(3, dtype=torch.bool)).any()
    assert s.psi0.tolist() == pytest.approx([0.1, 0.2, 0.3])
    cmd2 = cmd.clone(); cmd2[1, 0] = 0.3
    took = s.update(torch.tensor([0.6, 0.7, 0.8]), cmd2, torch.tensor([False, False, True]))
    assert took.tolist() == [False, True, True] and s.psi0.tolist() == pytest.approx([0.1, 0.7, 0.8])


def _env(cmd, yaw, heading, flag, step):
    term = types.SimpleNamespace(heading=heading, is_flag_env=flag, stand=torch.zeros_like(flag))
    return types.SimpleNamespace(num_envs=len(yaw), episode_length_buf=torch.full((len(yaw),), step),
                                 command_manager=types.SimpleNamespace(get_command=lambda n: cmd, get_term=lambda n: term),
                                 scene={"robot": types.SimpleNamespace(data=types.SimpleNamespace(heading_w=yaw))})


def test_the_term_holds_psi0_on_the_env_and_leaves_flag_and_heading_envs_alone():
    cmd = torch.tensor([[0.1, 0, 0], [0.5, 0, 0], [0.5, 0, 0], [0.5, 0, 0]])
    heading = torch.tensor([False, False, True, False]); flag = torch.tensor([False, False, False, True])
    env = _env(cmd, torch.zeros(4), heading, flag, 1)
    assert hh.heading_hold_term(env, "base_velocity").tolist() == [0.0] * 4          # first step: psi0 = yaw
    env.scene["robot"].data.heading_w = torch.tensor([0.2, -0.4, 0.9, 0.9]); env.episode_length_buf[:] = 2
    assert hh.heading_hold_term(env, "base_velocity").tolist() == pytest.approx([-0.2, -0.4, 0.0, 0.0])
    with pytest.raises(ValueError, match="heading and is_flag_env masks"):
        broken = _env(cmd, torch.zeros(4), heading, flag, 1)
        broken.command_manager.get_term = lambda n: types.SimpleNamespace(heading=heading)
        hh.heading_hold_term(broken, "base_velocity")


class _Cfg:
    def __init__(self, func=None, weight=0.0, params=None):
        self.func, self.weight, self.params = func, weight, dict(params or {})


def _env_cfg():
    return types.SimpleNamespace(rewards=types.SimpleNamespace(track_lin_vel=_Cfg(weight=2.0, params={"std": 0.5}),
                                                                track_ang_vel=_Cfg(weight=1.0, params={"std": 0.5}),
                                                                ex41_feet_air_time=_Cfg(params={"name": "feet_air_time"})))


def test_switch_off_leaves_the_env_config_as_it_was_and_switch_on_registers_at_weight_0(monkeypatch):
    row = adj.stage_rewards(EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml"), "E1")
    monkeypatch.delenv(hh.ENV_SWITCH, raising=False)
    off = _env_cfg(); out_off = adj.apply_reward_params(off, {"rewards": {"values": row}}, _Cfg)
    assert not hasattr(off.rewards, hh.TERM)
    monkeypatch.setenv(hh.ENV_SWITCH, "0")
    zero = _env_cfg(); assert adj.apply_reward_params(zero, {"rewards": {"values": row}}, _Cfg) == out_off
    assert sorted(vars(zero.rewards)) == sorted(vars(off.rewards))                      # same terms with the switch at 0
    monkeypatch.setenv(hh.ENV_SWITCH, "1")
    on = _env_cfg(); out_on = adj.apply_reward_params(on, {"rewards": {"values": row}}, _Cfg)
    term = on.rewards.ex42_heading_hold
    assert term.weight == 0.0 and term.func is hh.heading_hold_term and out_on == out_off
    assert term.params == {"command_name": "base_velocity", "include_stand": True}
    assert hh.register(on, _Cfg) is False                                                # no second term
    monkeypatch.setenv(hh.ENV_SWITCH, "yes")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        hh.register(_env_cfg(), _Cfg)


def test_the_start_weight_comes_from_the_env_value_and_prints_one_line(monkeypatch, capsys):
    monkeypatch.setenv(hh.ENV_SWITCH, "1"); monkeypatch.setenv(hh.WEIGHT_ENV, "0.5")
    cfg = _env_cfg(); assert hh.register(cfg, _Cfg) is True
    assert cfg.rewards.ex42_heading_hold.weight == 0.5
    assert "EX42_HEADING_HOLD where=start weight=0.5 " in capsys.readouterr().out
    for bad in ("-0.1", "nan", "inf", "x"):
        monkeypatch.setenv(hh.WEIGHT_ENV, bad)
        with pytest.raises(ValueError, match=hh.WEIGHT_ENV):
            hh.register(_env_cfg(), _Cfg)
    monkeypatch.setenv(hh.ENV_SWITCH, "0"); monkeypatch.setenv(hh.WEIGHT_ENV, "0.5")
    with pytest.raises(ValueError, match="is set but EX42_HEADING_HOLD is not 1"):        # a weight without the switch is a mistake
        hh.register(_env_cfg(), _Cfg)


@pytest.mark.skipif(not MANAGER.is_file(), reason="Isaac Lab source not on this machine")
def test_the_installed_reward_manager_skips_a_weight_0_term():
    text = MANAGER.read_text(encoding="utf-8")
    assert "if term_cfg.weight == 0.0:" in text and "continue" in text[text.index("if term_cfg.weight == 0.0:"):][:200]
