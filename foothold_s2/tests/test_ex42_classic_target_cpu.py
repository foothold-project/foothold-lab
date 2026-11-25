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
    hv, fv, ncyc = _run(36, 18, 0.06)
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
    assert hv / front_cycles == pytest.approx((0.13 - 0.06) ** 2, rel=0.15)


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
    assert "EX42_CLASSIC_TARGET where=start w_hip=-150 w_pitch=-0.9 w_freq=-60 hip_target=0.06 hip_vy_max=0.05 hip_wz_max=0.1" in capsys.readouterr().out
    with pytest.raises(ValueError):
        ct.register(cfg, Term, Entity)


def test_pitch_weight_zero_is_accepted_and_not_registered(monkeypatch):
    class Term:
        def __init__(self, func, weight, params):
            self.weight = weight

    class Entity:
        def __init__(self, name, **kw):
            pass

    _env(monkeypatch, params="w_pitch=0,w_hip=-230,w_freq=-95")
    cfg = types.SimpleNamespace(rewards=types.SimpleNamespace())
    assert ct.register(cfg, Term, Entity)
    assert not hasattr(cfg.rewards, "ex42_classic_pitch")
    assert (cfg.rewards.ex42_classic_hip_range.weight, cfg.rewards.ex42_classic_step_freq.weight) == (-230.0, -95.0)


def test_straight_mask_side_and_turn_rows_not_scored_for_hip():
    # forward, backward, side 0.3, turn 1.0, walk-turn 0.5/0.8, tiny vy 0.04 with wz 0.05
    cmd = torch.tensor([[0.3, 0.0, 0.0], [-0.3, 0.0, 0.0], [0.0, 0.3, 0.0], [0.0, 0.0, 1.0], [0.5, 0.0, 0.8], [0.3, 0.04, 0.05]])
    straight = ct.straight_mask(cmd, 0.05, 0.1)
    assert straight.tolist() == [True, True, False, False, False, True]
    done = torch.ones(6, 4, dtype=torch.bool) & straight[:, None]
    rng = torch.full((6, 4), 0.45)           # Classic side-step hip range
    v = ct.hip_value(done, rng, 0.06)
    assert v[2] == 0 and v[3] == 0 and v[4] == 0
    assert float(v[0]) == pytest.approx(2 * (0.45 - 0.06) ** 2)


def test_gk3_params_default_off_and_validated(monkeypatch):
    _env(monkeypatch)
    p = ct.params()
    assert p["hip_target_wz_slope"] == 0.0 and p["flatlike_only"] == 0.0
    for bad in ("flatlike_only=2", "hip_target_wz_slope=-0.1", "hip_target_wz_slope=2"):
        _env(monkeypatch, params=bad)
        with pytest.raises(ValueError):
            ct.params()


def test_hip_target_grows_with_turn_command():
    cmd = torch.tensor([[0.3, 0.0, 0.0], [0.3, 0.0, 0.2], [0.3, 0.0, -0.3]])
    tgt = ct.hip_target_rows(cmd, 0.06, 0.15)
    assert tgt.tolist() == pytest.approx([0.06, 0.09, 0.105])
    done = torch.tensor([[True, False, False, False]] * 3)
    rng = torch.full((3, 4), 0.10)
    got = ct.hip_value(done, rng, tgt).tolist()
    assert got == pytest.approx([0.04 ** 2, 0.01 ** 2, 0.0])
    # scalar target still works (Gk2 path)
    assert ct.hip_value(done, rng, 0.06).tolist() == pytest.approx([0.04 ** 2] * 3)


def test_flatlike_columns_keep_rough_and_slopes_only():
    table = [{"family": "A", "kind": k} for k in ("pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough", "hf_pyramid_slope",
                                                    "hf_pyramid_slope_inv", "stage_stairs", "balance_beams", "flat")]
    table.append({"family": "C", "kind": "flat"})
    assert ct.flatlike_columns(table).tolist() == [False, False, False, True, True, True, False, False, True, False]


def test_mask_flatlike_only_and_band(monkeypatch):
    import sys
    from types import SimpleNamespace as NS
    table = [{"family": "A", "kind": "pyramid_stairs"}, {"family": "A", "kind": "random_rough"}, {"family": "A", "kind": "balance_beams"}]
    cmd = torch.tensor([[0.3, 0.0, 0.0]] * 4)
    term = NS(stand=torch.zeros(4, dtype=torch.bool))
    env = NS(command_manager=NS(get_term=lambda n: term, get_command=lambda n: cmd),
             scene=NS(terrain=NS(terrain_levels=torch.tensor([0, 0, 3, 4]), terrain_types=torch.tensor([0, 1, 1, 2]))),
             _ex42_column_table=table)
    fake = NS(sparse_envs=lambda e: torch.tensor([False, False, False, True]))
    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.ex42_hip_sparse", fake)
    p = dict(ct.DEFAULTS, band_max_level=3.0)
    assert ct._mask(env, "base_velocity", p)[0].tolist() == [True, True, True, False]
    p["flatlike_only"] = 1.0
    assert ct._mask(env, "base_velocity", p)[0].tolist() == [False, True, True, False]


def test_monitor_reports_row_shares_and_in_row_reward(monkeypatch, capsys):
    _env(monkeypatch, params="w_hip=-200,w_freq=-100,w_pitch=0")
    ct._SUMS.clear()
    raw = types.SimpleNamespace()
    active = torch.tensor([True, True, False, False])
    straight = torch.tensor([True, False, False, False])
    done = torch.tensor([[True, False, False, False], [False, True, False, False], [False] * 4, [False] * 4])
    r = {"active": active, "straight": straight, "done": done, "hip_done": done & straight[:, None],
         "cycle_s": torch.full((4, 4), 0.5), "hip_range": torch.full((4, 4), 0.16), "hip_target": torch.full((4,), 0.06),
         "pitch_sq": torch.zeros(4), "cmd_xy": torch.tensor([0.2, 0.4, 0.0, 0.0])}
    ct._monitor(raw, r, ct.params())
    s = ct.summary()
    assert s["mask_row_frac"] == 0.5 and s["straight_row_frac"] == 0.25 and s["straight_env_steps"] == 1
    assert s["hip_value_per_straight_step"] == pytest.approx(0.01)            # (0.16 - 0.06)^2 on one straight row
    assert s["hip_reward_per_s_in_rows"] == pytest.approx(-2.0)
    f = (0.5 - 1 / 1.4) ** 2
    assert s["freq_value_per_mask_step"] == pytest.approx(2 * f / 2, rel=1e-4)
    assert s["freq_cycles"] == 2 and s["scored_cycles"] == 1
    assert "mask_row_frac=0.5" in capsys.readouterr().out
    ct._SUMS.clear()


def test_monitor_splits_speed_bins_with_track_and_cumulative_sums(monkeypatch):
    """lead 02:07 Gk4: |cmd_xy| < 0.3 rows apart from 0.3..0.5 rows, track_lin + track_ang inside the mask, cumulative sums."""
    _env(monkeypatch, params="w_hip=-200,w_freq=-100,w_pitch=0")
    ct._SUMS.clear()
    rm = types.SimpleNamespace(active_terms=["track_lin_vel", "x", "track_ang_vel"],
                               _step_reward=torch.tensor([[1.0, 9.0, 0.5], [2.0, 9.0, 0.25], [4.0, 9.0, 4.0], [3.0, 9.0, 3.0]]))
    raw = types.SimpleNamespace(reward_manager=rm)
    active = torch.tensor([True, True, False, True])
    straight = torch.tensor([True, True, False, False])
    done = torch.tensor([[True, False, False, False], [True, False, False, False], [False] * 4, [False, True, False, False]])
    r = {"active": active, "straight": straight, "done": done, "hip_done": done & straight[:, None],
         "cycle_s": torch.full((4, 4), 0.5), "hip_range": torch.tensor([[0.16] * 4, [0.26] * 4, [0.3] * 4, [0.3] * 4]),
         "hip_target": torch.full((4,), 0.06), "pitch_sq": torch.zeros(4), "cmd_xy": torch.tensor([0.1, 0.45, 0.2, 0.0])}
    p = ct.params()
    ct._monitor(raw, r, p)
    ct._monitor(raw, r, p)                 # two steps: cumulative sums double, per-step values stay
    s = ct.summary()
    f = (0.5 - 1 / 1.4) ** 2
    assert (s["cum_steps_lo"], s["cum_steps_hi"], s["cum_straight_lo"], s["cum_straight_hi"]) == (4, 2, 2, 2)
    assert s["cum_hip_value_lo"] == pytest.approx(2 * 0.01) and s["cum_hip_value_hi"] == pytest.approx(2 * 0.04)
    assert s["hip_reward_per_s_lo"] == pytest.approx(-2.0) and s["hip_reward_per_s_hi"] == pytest.approx(-8.0)
    assert s["cum_freq_value_lo"] == pytest.approx(4 * f, rel=1e-4) and s["cum_freq_value_hi"] == pytest.approx(2 * f, rel=1e-4)
    assert s["freq_reward_per_s_lo"] == pytest.approx(-100 * f, rel=1e-4)
    assert s["cum_track_lo"] == pytest.approx(2 * (1.5 + 6.0)) and s["cum_track_hi"] == pytest.approx(2 * 2.25)
    assert s["track_per_s_lo"] == pytest.approx(3.75) and s["track_per_s_in_mask"] == pytest.approx((15 + 4.5) / 6)
    assert s["cum_track_in_mask"] == pytest.approx(19.5)
    assert s["cum_hip_value"] == pytest.approx(0.1) and s["cum_freq_value"] == pytest.approx(6 * f, rel=1e-4)
    ct._SUMS.clear()
    raw2 = types.SimpleNamespace()        # no reward manager: track keys say None, nothing else breaks
    ct._monitor(raw2, r, p)
    assert ct.summary()["cum_track_in_mask"] is None
    ct._SUMS.clear()
