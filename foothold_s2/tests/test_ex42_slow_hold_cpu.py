"""v29-5: a slow forward command (0.1 <= |v_xy| < 0.3, no turn) is held for U(8, 12) s instead of the base 4 s.

The real MixedVelocityCommand, its sampler and the E1F stage runtime are used (only Isaac's CommandTerm base is a double,
see e1f_term). Other bands, envs with a turn, heading / spin / stand / flag envs and the evaluation settings keep the base period.
"""
from __future__ import annotations

import pytest
import torch

from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

BASE = 4.0


def glob(command):
    return command._apply_slow_hold.__func__.__globals__


def test_resample_holds_only_the_slow_band_for_8_to_12_s(monkeypatch):
    command, _, _ = e1f_term(monkeypatch, {})
    n = command.num_envs
    command.time_left[:] = BASE                                    # what Isaac's _resample sets before _resample_command
    command._resample_command(torch.arange(n))
    cmd = command.vel_command_b
    speed = torch.linalg.norm(cmd[:, :2], dim=1)
    free = ~command.is_flag_env
    band = (speed >= 0.1) & (speed < 0.3) & (cmd[:, 2].abs() <= 1e-6) & ~command.heading & ~command.spin & ~command.stand & free
    assert int(band.sum()) > 50 and int((~band).sum()) > 50       # both groups are present in the real draw
    assert bool(command.slow_hold[band].all()) and not bool(command.slow_hold[~band].any())
    held = command.time_left[band]
    assert bool((held >= 8.0).all()) and bool((held <= 12.0).all()) and float(held.std()) > 0.5
    assert bool((command.time_left[~band] == BASE).all())          # every other band, turn, heading, spin, stand, flag env
    count, mean_left = command.slow_hold_summary()
    assert count == int(band.sum()) and 9.0 < mean_left < 11.0


def test_band_edges_and_exclusions_on_given_commands(monkeypatch):
    command, _, _ = e1f_term(monkeypatch, {})
    ids = torch.arange(8)
    rows = [[0.0999, 0.0, 0.0],      # below the band
            [0.1, 0.0, 0.0],         # lower edge is inside
            [0.0, -0.2, 0.0],        # sideways slow: inside
            [0.2999, 0.0, 0.0],      # just below the upper edge: inside
            [0.3, 0.0, 0.0],         # upper edge is outside
            [0.2, 0.0, 0.5],         # a turn
            [0.2, 0.0, 0.0],         # heading env
            [0.2, 0.0, 0.0]]         # stand env
    command.vel_command_b[ids] = torch.tensor(rows)
    command.heading[:] = False
    command.spin[:] = False
    command.stand[:] = False
    command.heading[6] = True
    command.stand[7] = True
    command.time_left[ids] = BASE
    command._apply_slow_hold(ids)
    assert command.slow_hold[ids].tolist() == [False, True, True, True, False, False, False, False]
    assert command.time_left[ids][[0, 4, 5, 6, 7]].tolist() == [BASE] * 5
    assert bool((command.time_left[ids][[1, 2, 3]] >= 8.0).all())


@pytest.mark.parametrize("off", [None, 0, (0.0, 0.0)])
def test_off_changes_nothing_and_draws_nothing(monkeypatch, off):
    command, _, _ = e1f_term(monkeypatch, {})
    monkeypatch.setitem(glob(command), "SLOW_HOLD_RANGE_S", off)
    command.vel_command_b[:] = torch.tensor([0.2, 0.0, 0.0])
    command.time_left[:] = BASE
    state = command.gen.get_state().clone()
    command._apply_slow_hold(torch.arange(command.num_envs))
    assert bool((command.time_left == BASE).all()) and not bool(command.slow_hold.any())
    assert torch.equal(command.gen.get_state(), state) or off == (0.0, 0.0)


@pytest.mark.parametrize("what", ["eval_period", "fixed_cmd"])
def test_evaluation_settings_are_not_touched(monkeypatch, what):
    command, _, _ = e1f_term(monkeypatch, {})
    if what == "eval_period":
        command.cfg.resampling_time_range = (1.0e9, 1.0e9)       # ex42_task_eval, d44, flag eval
    else:
        command.cfg.fixed_cmd = (0.2, 0.0, 0.0)
    command.vel_command_b[:] = torch.tensor([0.2, 0.0, 0.0])
    command.time_left[:] = 6.0
    command._apply_slow_hold(torch.arange(command.num_envs))
    assert bool((command.time_left == 6.0).all()) and not bool(command.slow_hold.any())
