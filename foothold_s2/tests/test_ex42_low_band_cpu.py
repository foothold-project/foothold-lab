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


def test_on_fills_each_band_from_fast_rows_only_and_passes_the_contract(monkeypatch, capsys):
    """Lead 2026-11-23 revision: every band is 0 ~ 0.10, the share comes only from rows above their range midpoint, slow rows are kept."""
    off, _ = _term(monkeypatch, 0)
    cmd_off, slot_off, flag_off, _ = _draw(off)
    command, runtime = _term(monkeypatch, 0.5)
    stage = runtime.plan.stages[int(runtime.env_stage[0])]
    b, mid = lb.bands(stage.ranges), lb.midpoints(stage.ranges)
    assert set(b.values()) == {0.10}
    cmd, slot, flag, heading = _draw(command)
    assert torch.equal(slot, slot_off) and torch.equal(flag, flag_off)
    names = command.slot_names
    free = ~flag
    sel = lambda pred: free & torch.tensor([pred(names[int(i)]) if 0 <= int(i) < len(names) else False for i in slot.tolist()])
    axis = {"forward": (sel(lambda s: s == "forward"), 0), "reverse": (sel(lambda s: s == "reverse"), 0),
            "side": (sel(lambda s: s.startswith("side_")), 1), "spin": (sel(lambda s: s.startswith("spin_")) & ~heading, 2)}
    changed = (cmd != cmd_off).any(dim=1)
    for key, (rows, i) in axis.items():
        fast = rows & (cmd_off[:, i].abs() > mid[key])
        slow = rows & ~fast
        assert int(fast.sum()) > 50 and int(slow.sum()) > 50, key
        assert not bool(changed[slow].any()), key                       # rows at or below the midpoint are never moved
        moved = fast & changed
        frac = float(moved.sum()) / float(fast.sum())
        assert 0.35 < frac < 0.65, (key, frac)                          # about SHARE (0.5) of the fast rows
        v = cmd[moved, i]
        assert float(v.abs().max()) <= 0.10 and float(v.abs().max()) > 0.08 and float(v.abs().min()) < 0.02, key   # 0 ~ 0.10 covered
        assert bool((torch.sign(v) == torch.sign(cmd_off[moved, i])).all() | (v == 0).all()), key                  # sign kept
    assert not bool(changed[free & ~(axis["forward"][0] | axis["reverse"][0] | axis["side"][0] | sel(lambda s: s.startswith("spin_")))].any())
    bad = command_bad(cmd, slot, heading, runtime.env_stage, runtime.plan)
    assert not bool(bad[free].any())                                     # the run's contract accepts the band while on
    assert "EX42_LOW_BAND where=start share=0.5" in capsys.readouterr().out
    s = lb.summary()
    assert s["spin"] == int((axis["spin"][0] & changed).sum()) and s["side"] == int((axis["side"][0] & changed).sum())


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
