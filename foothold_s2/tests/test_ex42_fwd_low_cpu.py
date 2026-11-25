"""E2 forward lower end (EX42_FWD_LOW) and low-speed small-noise sigma (EX42_SMALL_NOISE_LOW_SIGMA), CPU only (lead 11/26 01:23)."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.commands import ex42_fwd_low as fl
from foothold_s2.commands.mixed_core import EX39_SLOTS
from foothold_s2.curriculum.continuous import command_bad
from foothold_s2.runners import ex41_critic_mirror as mirror
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

N = 3072
FWD = EX39_SLOTS.index("forward")


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.delenv(fl.ENV_SWITCH, raising=False)
    monkeypatch.delenv(mirror.LOWSPEED_SIGMA_ENV, raising=False)
    fl._COUNTS.update({"calls": 0, "forward_rows": 0, "below_0p1": 0, "min_vx": float("inf")})


def _draw(monkeypatch, low):
    if low is not None:
        monkeypatch.setenv(fl.ENV_SWITCH, low)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N, stage_id="E2")
    command.reset()                      # reset draws once too: count only the resample below
    fl._COUNTS.update({"calls": 0, "forward_rows": 0, "below_0p1": 0, "min_vx": float("inf")})
    command.time_left[:] = 4.0
    command.gen.manual_seed(7)
    command._resample_command(torch.arange(N))
    return command, runtime


def test_value_parse():
    assert fl.value() is None
    for bad in ("0.1", "0", "x", "nan", "0.01"):
        with pytest.MonkeyPatch.context() as m:
            m.setenv(fl.ENV_SWITCH, bad)
            with pytest.raises(ValueError):
                fl.value()


def test_off_keeps_plan_range_and_no_draw_below_0p1(monkeypatch, capsys):
    command, runtime = _draw(monkeypatch, None)
    lo = runtime.plan.stages[0].ranges["forward_vx"][0]
    assert lo == pytest.approx(0.1)
    free = ~command.is_flag_env
    fwd = free & (command.slot_current == FWD) & ~command.heading
    assert float(command.vel_command_b[fwd, 0].min()) >= 0.1 - 1e-6
    assert "EX42_FWD_LOW" not in capsys.readouterr().out


def test_on_lowers_e2_forward_end_draws_below_0p1_and_passes_contract(monkeypatch, capsys):
    command, runtime = _draw(monkeypatch, "0.05")
    stage = runtime.plan.stages[0]
    assert stage.ranges["forward_vx"][0] == 0.05 and runtime.stage_config is stage
    cmd, slot, heading = command.vel_command_b, command.slot_current, command.heading
    free = ~command.is_flag_env
    fwd = free & (slot == FWD)
    vx = cmd[fwd, 0]
    assert float(vx.min()) >= 0.05 - 1e-6 and int((vx < 0.1).sum()) > 0
    assert not bool(command_bad(cmd, slot, heading, runtime.env_stage, runtime.plan, ex42_stage_id=runtime.stage_id)[free].any())
    out = capsys.readouterr().out
    assert "EX42_FWD_LOW where=start stage=E2 forward_vx_old=[0.1," in out and "forward_vx_new=[0.05," in out
    assert "EX42_FWD_LOW_MON calls=1 " in out
    s = fl.summary()
    assert s["below_0p1"] == int((vx < 0.1).sum()) and s["min_vx"] == pytest.approx(float(vx.min()))


def test_contract_still_refuses_below_the_new_end(monkeypatch):
    command, runtime = _draw(monkeypatch, "0.05")
    cmd = command.vel_command_b.clone()
    slot, heading = command.slot_current, command.heading
    pick = (~command.is_flag_env & (slot == FWD) & ~heading).nonzero().flatten()[:5]
    cmd[pick, 0] = 0.03
    assert bool(command_bad(cmd, slot, heading, runtime.env_stage, runtime.plan, ex42_stage_id=runtime.stage_id)[pick].all())


def test_on_refuses_other_stages(monkeypatch):
    monkeypatch.setenv(fl.ENV_SWITCH, "0.05")
    with pytest.raises(ValueError, match="stage E2 only"):
        fl.apply_stages([object()], "E1F")


def test_lowspeed_sigma(monkeypatch):
    assert mirror.lowspeed_sigma_scale() == mirror.SMALL_NOISE_SIGMA_SCALE == 0.2
    monkeypatch.setenv(mirror.LOWSPEED_SIGMA_ENV, "0.1")
    assert mirror.lowspeed_sigma_scale() == 0.1
    for bad in ("0", "1", "x", "inf"):
        monkeypatch.setenv(mirror.LOWSPEED_SIGMA_ENV, bad)
        with pytest.raises(ValueError):
            mirror.lowspeed_sigma_scale()
