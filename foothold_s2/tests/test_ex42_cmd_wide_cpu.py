"""E2 wide commands through the real command term and consumed-command contract, CPU only."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.commands import ex42_cmd_wide as wide
from foothold_s2.commands.mixed_core import EX39_SLOTS
from foothold_s2.curriculum.continuous import command_bad
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

N = 3072


@pytest.fixture(autouse=True)
def reset_counters(monkeypatch):
    monkeypatch.delenv(wide.ENV_SWITCH, raising=False)
    monkeypatch.delenv(wide.SHARE_ENV, raising=False)
    for key in wide._COUNTS:
        wide._COUNTS[key] = 0
    wide._STARTED["done"] = False


def _term(monkeypatch, *, enabled, share="0.5"):
    monkeypatch.setenv(wide.ENV_SWITCH, "1" if enabled else "0")
    monkeypatch.setenv(wide.SHARE_ENV, share)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N, stage_id="E2")
    assert runtime.stage_id == "E2" and all(stage.id != "E2" for stage in runtime.plan.stages)
    assert runtime.plan.stages[1].ranges["diag_vx_abs"] == (0.3, 0.6)
    command.reset()  # actual stage assignment and free/flag split precede a later resample
    for key in wide._COUNTS:
        wide._COUNTS[key] = 0
    wide._STARTED["done"] = False
    return command, runtime


def _draw(command):
    command.time_left[:] = 4.0
    command.gen.manual_seed(7)
    command._resample_command(torch.arange(N))
    return (command.vel_command_b.clone(), command.slot_current.clone(),
            command.is_flag_env.clone(), command.heading.clone(), command.gen.get_state().clone())


def test_on_widens_diagonals_turns_about_half_fast_forwards_and_passes_contract(monkeypatch, capsys, tmp_path):
    command, runtime = _term(monkeypatch, enabled=True)
    cmd, slot, flag, heading, _ = _draw(command)
    free = ~flag
    diag = free & (slot >= EX39_SLOTS.index("diag_fwd_left")) & (slot <= EX39_SLOTS.index("diag_back_right"))
    fast = free & (slot == EX39_SLOTS.index("forward")) & ~heading & (cmd[:, 0] > 1.2)
    turned = fast & (cmd[:, 2] != 0)
    assert int(diag.sum()) > 100 and float(cmd[diag, 0].abs().min()) >= 0.3
    assert 1.1 < float(cmd[diag, 0].abs().max()) <= 1.2
    assert int(fast.sum()) > 40 and 0.35 < float(turned.sum()) / float(fast.sum()) < 0.65
    assert bool((cmd[turned, 2].abs() >= 0.1).all()) and bool((cmd[turned, 2].abs() <= 0.6).all())
    left_share = float((cmd[turned, 2] > 0).sum()) / int(turned.sum())
    assert 0.25 < left_share < 0.75
    assert not bool(command_bad(cmd, slot, heading, runtime.env_stage, runtime.plan,
                                ex42_stage_id=runtime.stage_id)[free].any())
    assert "EX42_CMD_WIDE where=start stage=E2 share=0.5" in capsys.readouterr().out
    s = wide.summary()
    assert s["fast_forward_rows"] == int(fast.sum()) and s["turned_forward"] == int(turned.sum())
    assert s["diag_rows"] == int(diag.sum()) and s["diag_above_old_max"] == int((diag & (cmd[:, 0].abs() > 0.6)).sum())
    runtime.command_stats.add(cmd[free], slot[free], heading[free])
    assert runtime.command_stats.take()["out_of_range"] == 0
    runtime.command_allocation.write(tmp_path, 50, None, plan_sha="a" * 64, stage_id="E2")
    import json
    receipt = json.loads(next(tmp_path.glob("command_shares_50_rank*.json")).read_text())
    assert receipt["cmd_wide"]["turned_forward"] == int(turned.sum())


def test_off_draws_nothing_and_contract_refuses_wide_values(monkeypatch):
    command, runtime = _term(monkeypatch, enabled=False)
    def unexpected_apply(*_args, **_kwargs):
        raise AssertionError("off gate called wide sampler")
    monkeypatch.setattr(wide, "apply", unexpected_apply)
    off, slot, flag, heading, state = _draw(command)
    assert wide.summary() is None
    command2, _ = _term(monkeypatch, enabled=False, share="invalid but dormant")
    again, slot2, flag2, heading2, state2 = _draw(command2)
    assert torch.equal(off, again) and torch.equal(slot, slot2)
    assert torch.equal(flag, flag2) and torch.equal(heading, heading2) and torch.equal(state, state2)
    assert not wide._STARTED["done"] and all(v == 0 for v in wide._COUNTS.values())
    forged = off.clone()
    i = int(torch.nonzero(~flag & (slot == EX39_SLOTS.index("diag_fwd_left")))[0])
    forged[i, 0] = 1.0
    j = int(torch.nonzero(~flag & (slot == EX39_SLOTS.index("forward")) & ~heading & (off[:, 0] > 1.2))[0])
    forged[j, 2] = 0.3
    bad = command_bad(forged, slot, heading, runtime.env_stage, runtime.plan,
                      ex42_stage_id=runtime.stage_id)
    assert bool(bad[i]) and bool(bad[j])
    monkeypatch.setenv(wide.ENV_SWITCH, "1")
    assert not bool(command_bad(forged, slot, heading, runtime.env_stage, runtime.plan,
                                ex42_stage_id=runtime.stage_id)[[i, j]].any())
    forged[j, 0] = 0.8  # slow forward cannot take the new turn
    assert bool(command_bad(forged, slot, heading, runtime.env_stage, runtime.plan,
                            ex42_stage_id=runtime.stage_id)[j])
    forged[j, 0] = 1.3
    forged[j, 2] = 0.05  # out of the new turn band
    assert bool(command_bad(forged, slot, heading, runtime.env_stage, runtime.plan,
                            ex42_stage_id=runtime.stage_id)[j])
    forged[j, 2] = 0.7
    assert bool(command_bad(forged, slot, heading, runtime.env_stage, runtime.plan,
                            ex42_stage_id=runtime.stage_id)[j])
    forged[j, 2] = 0.3
    forged[i, 0] = 1.21  # beyond the new diagonal upper edge
    assert bool(command_bad(forged, slot, heading, runtime.env_stage, runtime.plan,
                            ex42_stage_id=runtime.stage_id)[i])


def test_gate_only_opens_e2_and_validates_env(monkeypatch):
    monkeypatch.setenv(wide.ENV_SWITCH, "1")
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N, stage_id="E1F")
    cmd, slot, flag, heading, state = _draw(command)
    monkeypatch.setenv(wide.ENV_SWITCH, "0")
    off_command, _, _ = e1f_term(monkeypatch, {}, n=N, stage_id="E1F")
    off, off_slot, off_flag, off_heading, off_state = _draw(off_command)
    assert torch.equal(cmd, off) and torch.equal(slot, off_slot)
    assert torch.equal(flag, off_flag) and torch.equal(heading, off_heading)
    assert torch.equal(state, off_state)
    monkeypatch.setenv(wide.ENV_SWITCH, "1")
    assert wide.summary()["diag_rows"] == 0
    monkeypatch.setenv(wide.ENV_SWITCH, "maybe")
    with pytest.raises(ValueError, match=wide.ENV_SWITCH):
        wide.enabled()
    monkeypatch.setenv(wide.ENV_SWITCH, "1")
    monkeypatch.setenv(wide.SHARE_ENV, "1.2")
    with pytest.raises(ValueError, match=wide.SHARE_ENV):
        wide.share()
