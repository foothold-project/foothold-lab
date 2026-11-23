"""EX-42 low-speed band commands (lead 2026-11-23 12:34): through the real command term entry (_resample_command), on covers the band of
each axis and passes the run's contract, off draws nothing extra and gives the old commands bit for bit."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.commands import ex42_low_band as lb
from foothold_s2.curriculum.continuous import command_bad
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

N = 3072


@pytest.fixture(autouse=True)
def fresh():
    for k in lb._COUNTS:
        lb._COUNTS[k] = 0
    lb._STARTED["done"] = False


def _term(monkeypatch, share):
    if share:
        monkeypatch.setenv(lb.ENV_SWITCH, str(share))
    else:
        monkeypatch.delenv(lb.ENV_SWITCH, raising=False)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N)
    return command, runtime


def _draw(command, seed=7):
    command.time_left[:] = 4.0
    command.gen.manual_seed(seed)
    command._resample_command(torch.arange(N))
    return command.vel_command_b.clone(), command.slot_current.clone(), command.is_flag_env.clone(), command.heading.clone()


def test_on_fills_each_band_and_passes_the_contract(monkeypatch, capsys):
    command, runtime = _term(monkeypatch, 0.5)
    stage = runtime.plan.stages[int(runtime.env_stage[0])]
    b = lb.bands(stage.ranges)
    cmd, slot, flag, heading = _draw(command)
    names = command.slot_names
    free = ~flag
    sel = lambda pred: free & torch.tensor([pred(names[int(i)]) if 0 <= int(i) < len(names) else False for i in slot.tolist()])
    fwd, rev = sel(lambda s: s == "forward") & ~heading, sel(lambda s: s == "reverse")
    side, spin = sel(lambda s: s.startswith("side_")), sel(lambda s: s.startswith("spin_")) & ~heading
    in_band = {"forward": fwd & (cmd[:, 0] < b["forward"]), "reverse": rev & (cmd[:, 0] > -b["reverse"]),
               "side": side & (cmd[:, 1].abs() < b["side"]), "spin": spin & (cmd[:, 2].abs() < b["spin"])}
    for key, mask in in_band.items():
        total = {"forward": fwd, "reverse": rev, "side": side, "spin": spin}[key]
        assert int(total.sum()) > 50, key
        frac = float(mask.sum()) / float(total.sum())
        assert 0.35 < frac < 0.65, (key, frac)                       # about SHARE (0.5) of each slot moved into its band
    assert float(cmd[in_band["forward"], 0].min()) >= 0.0 and float(cmd[in_band["reverse"], 0].max()) <= 0.0
    lo, hi = float(cmd[in_band["forward"], 0].min()), float(cmd[in_band["forward"], 0].max())
    assert lo < 0.2 * b["forward"] and hi > 0.8 * b["forward"]           # the band is covered, not one value
    bad = command_bad(cmd, slot, heading, runtime.env_stage, runtime.plan)
    assert not bool(bad[free].any())                                     # the run's contract accepts the band while on
    assert "EX42_LOW_BAND where=start share=0.5" in capsys.readouterr().out
    s = lb.summary()
    fwd_all = sel(lambda s: s == "forward")                              # forward rows with a heading target also move (their wz is the heading's)
    assert s["forward"] == int((fwd_all & (cmd[:, 0] < b["forward"])).sum()) and s["spin"] == int(in_band["spin"].sum())


def test_off_is_bit_for_bit_and_contract_still_rejects_the_band(monkeypatch):
    off, runtime = _term(monkeypatch, 0)
    state = off.gen.get_state().clone()
    cmd_off, slot_off, flag_off, heading_off = _draw(off)
    after = off.gen.get_state().clone()
    again, _ = _term(monkeypatch, 0)
    again.gen.set_state(state)
    cmd_again, slot_again, _, _ = _draw(again)
    assert torch.equal(again.gen.get_state(), after) and torch.equal(cmd_again, cmd_off) and torch.equal(slot_again, slot_off)
    assert lb.summary() is None
    # a band value is out of contract while off (the gate is what opens it)
    fwd = (~flag_off) & (slot_off == off.slot_names.index("forward")) & ~heading_off
    i = int(torch.nonzero(fwd)[0])
    forged = cmd_off.clone(); forged[i, 0] = 0.0 + 1e-3
    stage = runtime.plan.stages[int(runtime.env_stage[i])]
    if float(stage.ranges["forward_vx"][0]) > 1e-3 + 1e-5:
        assert bool(command_bad(forged, slot_off, heading_off, runtime.env_stage, runtime.plan)[i])


def test_switch_values(monkeypatch):
    for v, want in (("", False), ("0", False), ("0.1", True), ("1", True)):
        monkeypatch.setenv(lb.ENV_SWITCH, v)
        assert lb.enabled() is want
    for v in ("x", "-0.1", "1.5"):
        monkeypatch.setenv(lb.ENV_SWITCH, v)
        with pytest.raises(ValueError):
            lb.enabled()
