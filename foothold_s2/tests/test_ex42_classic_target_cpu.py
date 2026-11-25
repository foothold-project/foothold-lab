"""CPU tests for EX42_CLASSIC_TARGET (lead 2026-11-26 00:26): known-answer gait traces, mask, switch and registration."""
import math
import types

import pytest
import torch

from foothold_s2.rewards import ex42_classic_target as ct


def _env(monkeypatch, on="1", params=""):
    monkeypatch.setenv(ct.ENV_SWITCH, on)
    if params:
        monkeypatch.setenv(ct.PARAMS_ENV, params)
    else:
        monkeypatch.delenv(ct.PARAMS_ENV, raising=False)


def _trace(period_steps, swing_steps, hip_amp, n_steps=400):
    """One env, four feet in a trot (FL+RR, FR+RL half a period apart); hip = hip_amp/2 * sin over the cycle."""
    hips, contacts = [], []
    for k in range(n_steps):
        c, h = [], []
        for leg in range(4):
            phase = (k + (0 if leg in (0, 3) else period_steps // 2)) % period_steps
            c.append(phase >= swing_steps)
            h.append(0.5 * hip_amp * math.sin(2 * math.pi * phase / period_steps))
        hips.append(torch.tensor([h]))
        contacts.append(torch.tensor([c]))
    return hips, contacts


def _run(period_steps, swing_steps, hip_amp, p=None):
    p = p or dict(ct.DEFAULTS)
    tr = ct.CycleTracker(1, "cpu")
    hips, contacts = _trace(period_steps, swing_steps, hip_amp)
    hv, fv, ncyc = 0.0, 0.0, 0
    for k, (h, c) in enumerate(zip(hips, contacts)):
        done, cyc, rng = tr.step(h, c, torch.tensor([k == 0]), p["min_swing_steps"])
        hv += float(ct.hip_value(done, rng, p["hip_target"]).sum())
        fv += float(ct.freq_value(done, cyc, p["step_hz"]).sum())
        ncyc += int(done.sum())
    return hv, fv, ncyc


def test_classic_cadence_and_narrow_hip_score_about_zero():
    # 1.4 Hz -> 0.714 s = 35.7 steps; 36 steps gives 0.72 s (error 0.006 s), hip range 0.05 = target
    hv, fv, ncyc = _run(36, 18, 0.05)
    assert ncyc > 30
    assert hv == pytest.approx(0.0, abs=1e-9)
    assert fv / ncyc < 1e-4


def test_candidate_cadence_and_wide_hip_are_penalised():
    # candidate: 1.6 Hz (31 steps = 0.62 s) and front hip range 0.13 rad
    hv, fv, ncyc = _run(31, 15, 0.13)
    per_cycle_freq = fv / ncyc
    assert per_cycle_freq == pytest.approx((0.62 - 1 / 1.4) ** 2, rel=0.05)
    # only the two front feet are scored for the hip; range of a sine sampled at 31 steps is close to 0.13
    assert hv > 0
    front_cycles = ncyc / 2
    assert hv / front_cycles == pytest.approx((0.13 - 0.05) ** 2, rel=0.15)


def test_rear_hip_is_not_scored():
    done = torch.tensor([[False, False, True, True]])
    rng = torch.full((1, 4), 0.3)
    assert float(ct.hip_value(done, rng, 0.05)) == 0.0
    done = torch.tensor([[True, False, False, False]])
    assert float(ct.hip_value(done, rng, 0.05)) == pytest.approx(0.25 ** 2)


def test_first_cycle_after_reset_and_long_cycles_not_scored():
    tr = ct.CycleTracker(1, "cpu")
    hip = torch.zeros(1, 4)
    air = torch.zeros(1, 4, dtype=torch.bool)
    ground = torch.ones(1, 4, dtype=torch.bool)
    tr.step(hip, ground, torch.tensor([True]), 3)
    for _ in range(5):
        tr.step(hip, air, torch.tensor([False]), 3)
    done, _, _ = tr.step(hip, ground, torch.tensor([False]), 3)
    assert not done.any()                    # first touchdown after reset opens the first cycle only
    for _ in range(120):                     # 2.4 s stand still, then step
        tr.step(hip, ground, torch.tensor([False]), 3)
    for _ in range(5):
        tr.step(hip, air, torch.tensor([False]), 3)
    done, cyc, _ = tr.step(hip, ground, torch.tensor([False]), 3)
    assert done.all() and float(cyc[0, 0]) > ct.MAX_CYCLE_S
    assert float(ct.freq_value(done, cyc, 1.4).sum()) == 0.0


def test_short_swing_is_not_a_touchdown():
    tr = ct.CycleTracker(1, "cpu")
    hip = torch.zeros(1, 4)
    air = torch.zeros(1, 4, dtype=torch.bool)
    ground = torch.ones(1, 4, dtype=torch.bool)
    tr.step(hip, ground, torch.tensor([True]), 3)
    tr.step(hip, air, torch.tensor([False]), 3)
    tr.step(hip, air, torch.tensor([False]), 3)
    done, _, _ = tr.step(hip, ground, torch.tensor([False]), 3)
    assert not done.any() and not tr.started.any()


def test_command_mask():
    cmd = torch.tensor([[0.3, 0.0, 0.0], [0.6, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.3, 0.0, 0.0], [0.0, 0.02, 0.0]])
    stand = torch.tensor([False, False, False, False, True, False])
    got = ct.command_mask(cmd, stand, 0.5, 0.05).tolist()
    assert got == [True, False, False, True, False, False]


def test_switch_and_params(monkeypatch):
    _env(monkeypatch, on="")
    assert not ct.enabled()
    _env(monkeypatch, on="", params="w_hip=-1")
    with pytest.raises(ValueError):
        ct.enabled()
    _env(monkeypatch, on="2")
    with pytest.raises(ValueError):
        ct.enabled()
    _env(monkeypatch, params="w_pitch=0.5")
    with pytest.raises(ValueError):
        ct.params()
    _env(monkeypatch, params="nope=1")
    with pytest.raises(ValueError):
        ct.params()
    _env(monkeypatch, params="w_pitch=-0.5,step_hz=1.4")
    p = ct.params()
    assert p["w_pitch"] == -0.5 and p["w_hip"] == -150.0


def test_register_three_terms_and_off_registers_nothing(monkeypatch, capsys):
    class Term:
        def __init__(self, func, weight, params):
            self.func, self.weight, self.params = func, weight, params

    class Entity:
        def __init__(self, name, **kw):
            self.name, self.kw = name, kw

    _env(monkeypatch, on="")
    cfg = types.SimpleNamespace(rewards=types.SimpleNamespace())
    assert ct.register(cfg, Term, Entity) is False and not vars(cfg.rewards)
    _env(monkeypatch)
    assert ct.register(cfg, Term, Entity) is True
    r = cfg.rewards
    assert (r.ex42_classic_hip_range.weight, r.ex42_classic_pitch.weight, r.ex42_classic_step_freq.weight) == (-150.0, -0.9, -60.0)
    assert r.ex42_classic_pitch.params["sensor_cfg"].kw["body_names"] == list(ct.FEET)
    assert "EX42_CLASSIC_TARGET where=start w_hip=-150 w_pitch=-0.9 w_freq=-60" in capsys.readouterr().out
    with pytest.raises(ValueError):
        ct.register(cfg, Term, Entity)
