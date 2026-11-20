"""EX42_SLOW_PROGRESS_CAP_FRAC (planner BOUNDARY-E2R2-M250-PREP 21 · lead 1121 05:51): slow_progress 의 포화 자리를 명령의 k 배로. CPU · Isaac 없음.
꺼짐 (안 정함) 이면 식 · 설정 · 읽기 확인이 옛 것과 같아야 한다."""
from __future__ import annotations

import types

import pytest
import torch

from foothold_s2.rewards import ex42_slow_progress as sp

BAND = dict(speed_min=0.1, speed_max=0.3, taper_from=0.25)


def _old(vel_xy, cmd_xy, cmd_wz):
    """a21de1d24 (r6) 의 식을 그대로 옮긴 것: 꺼짐 비트 대조용."""
    speed = torch.linalg.vector_norm(cmd_xy, dim=-1)
    active = (speed >= 0.1) & (speed < 0.3) & (cmd_wz.abs() < 1e-6)
    safe_vel = torch.where(active[:, None], vel_xy, torch.zeros_like(vel_xy))
    safe_speed = speed.clamp_min(0.1)
    along = (safe_vel * cmd_xy).sum(-1) / safe_speed
    value = torch.maximum(torch.minimum(along, safe_speed), -safe_speed) / safe_speed
    value = value * ((0.3 - speed) / (0.3 - 0.25)).clamp(0.0, 1.0)
    return torch.where(active, value, torch.zeros_like(speed))


def _grid():
    g = torch.Generator().manual_seed(0)
    cmd = torch.cat([torch.rand(2000, 2, generator=g) * 0.6 - 0.3, torch.tensor([[0.1, 0.0], [0.3, 0.0], [0.5, 0.0], [0.2, 0.0]])])
    vel = torch.rand(len(cmd), 2, generator=g) * 0.8 - 0.4
    wz = torch.where(torch.rand(len(cmd), generator=g) < 0.2, torch.full((len(cmd),), 0.3), torch.zeros(len(cmd)))
    return vel, cmd, wz


def test_off_is_the_old_formula_bit_for_bit():
    vel, cmd, wz = _grid()
    assert torch.equal(sp.slow_progress_value(vel, cmd, wz, **BAND), _old(vel, cmd, wz))
    assert sp.read_cap_frac({}) is None and sp.read_cap_frac({sp.ENV_CAP: ""}) is None


def _row(cmd, k):
    speeds = torch.tensor([0.0, 0.05, 0.08, 0.09, 0.095, 0.10, 0.106, 0.11, 0.12, 0.2, 0.3, 0.45, 0.5, 0.6])
    vel = torch.stack([speeds, torch.zeros_like(speeds)], 1)
    c = torch.tensor([[cmd, 0.0]]).expand(len(speeds), 2)
    return speeds, sp.slow_progress_value(vel, c, torch.zeros(len(speeds)), cap_frac=k, **BAND)


def test_k09_shape_on_commands_0_1_0_3_0_5():
    s, old = _row(0.1, None)
    s, new = _row(0.1, 0.9)
    at = {round(float(v), 3): (float(a), float(b)) for v, a, b in zip(s, old, new)}
    assert at[0.09] == pytest.approx((0.9, 1.0))                  # 0.09 m/s already pays the full value under k 0.9
    assert at[0.1] == pytest.approx((1.0, 1.0)) and at[0.12] == pytest.approx((1.0, 1.0))   # beyond the command nothing changes (both 1)
    assert at[0.05] == pytest.approx((0.5, 0.5 / 0.9)) and at[0.0] == (0.0, 0.0)
    for v in (0.0, 0.05, 0.08, 0.09, 0.095):
        assert at[v][1] >= at[v][0]                                # below the command the k form pays at least as much: the extra pay for overspeed ends at 0.09
    for cmd in (0.3, 0.5):                                         # outside the slow band (speed_max 0.3): the term is 0 with or without k
        _, a = _row(cmd, None)
        _, b = _row(cmd, 0.9)
        assert torch.equal(a, torch.zeros_like(a)) and torch.equal(b, a)
    s2, b = _row(0.2, 0.9)                                       # inside the band: saturation at 0.18 for a 0.2 command
    at2 = {round(float(v), 3): float(x) for v, x in zip(s2, b)}
    assert at2[0.2] == pytest.approx(1.0) and at2[0.12] == pytest.approx(0.12 / 0.18) and at2[0.3] == pytest.approx(1.0)


def test_backwards_is_clipped_at_minus_one_and_bad_k_refuses():
    vel = torch.tensor([[-0.5, 0.0]]); cmd = torch.tensor([[0.1, 0.0]])
    assert float(sp.slow_progress_value(vel, cmd, torch.zeros(1), cap_frac=0.9, **BAND)[0]) == pytest.approx(-1.0)
    for bad in ("1.0", "0.4", "x", "nan", "1.2"):
        with pytest.raises(ValueError, match="EX42_SLOW_PROGRESS_CAP_FRAC"):
            sp.read_cap_frac({sp.ENV_CAP: bad})
    with pytest.raises(ValueError, match="cap_frac"):
        sp.slow_progress_value(vel, cmd, torch.zeros(1), cap_frac=1.0, **BAND)


class Term:
    def __init__(self, func=None, weight=0.0, params=None):
        self.func, self.weight, self.params = func, weight, dict(params or {})


def _cfg():
    """The reward terms apply_reward_params reads (the env config of an E stage), the two slow terms are registered by it."""
    return types.SimpleNamespace(rewards=types.SimpleNamespace(track_lin_vel=Term(params={"std": 0.35}), track_ang_vel=Term(params={"std": 0.5}),
                                                                ex41_feet_air_time=Term(params={"threshold": 0.5}), ex41_foot_slip=Term(), ex41_zero_yaw=Term()))


def test_entry_apply_reward_params_puts_k_on_the_term_only_when_set(monkeypatch, capsys):
    from foothold_s2.commands import ex42_segment_adjust as sa
    monkeypatch.delenv(sp.ENV_CAP, raising=False)
    off = _cfg(); out_off = sa.apply_reward_params(off, None, term_cfg_class=Term)
    assert "cap_frac" not in off.rewards.ex42_slow_progress.params and "slow_progress_cap_frac" not in out_off
    monkeypatch.setenv(sp.ENV_CAP, "0.9")
    on = _cfg(); out_on = sa.apply_reward_params(on, None, term_cfg_class=Term)
    assert on.rewards.ex42_slow_progress.params["cap_frac"] == 0.9 and out_on["slow_progress_cap_frac"] == {"before": 1.0, "after": 0.9}
    assert {k: v for k, v in out_on.items() if k != "slow_progress_cap_frac"} == out_off             # every other cell as before
    p_on = dict(on.rewards.ex42_slow_progress.params); p_on.pop("cap_frac")
    assert p_on == off.rewards.ex42_slow_progress.params and on.rewards.ex42_slow_progress.func is sp.slow_progress_term
    assert "EX42_SLOW_PROGRESS_CAP where=start cap_frac=0.9 term=ex42_slow_progress" in capsys.readouterr().out


def test_readback_refuses_a_live_term_without_the_asked_k(monkeypatch):
    from foothold_s2.commands import ex42_segment_adjust as sa
    monkeypatch.setenv(sp.ENV_CAP, "0.9")
    cfg = _cfg(); sa.apply_reward_params(cfg, None, term_cfg_class=Term)

    class Manager:
        def __init__(self, rewards):
            self.rewards = rewards

        def get_term_cfg(self, name):
            if not hasattr(self.rewards, name):
                raise ValueError(name)
            return getattr(self.rewards, name)

    env = types.SimpleNamespace(unwrapped=types.SimpleNamespace(reward_manager=Manager(cfg.rewards)))
    got = sa.reward_readback(env, None)
    assert got["slow_progress_cap_frac"] == 0.9
    cfg.rewards.ex42_slow_progress.params.pop("cap_frac")
    with pytest.raises(ValueError, match="cap_frac|CAP_FRAC"):
        sa.reward_readback(env, None)
