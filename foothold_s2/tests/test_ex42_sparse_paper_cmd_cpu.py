"""EX-42 A sparse columns in START's command form (EX42_SPARSE_PAPER_CMD · lead 2026-11-22 07:44 ledger ef5bf2b33 · planner 07:43).

The real MixedVelocityCommand, its sampler, the real plan row, stage runtime and the real command-contract check are used (only Isaac's
CommandTerm base is a double, see e1f_term; the same harness as the stone forward floor test). CPU only.
"""
from __future__ import annotations

import json

import pytest
import torch

from foothold_s2.commands import ex42_sparse_cmd as sc
from foothold_s2.curriculum.continuous import command_bad
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

N = 3072


@pytest.fixture(autouse=True)
def fresh_counts():
    for k in sc._COUNTS:
        sc._COUNTS[k] = 0
    sc._STARTED["done"] = False


def _term(monkeypatch, on):
    if on:
        monkeypatch.setenv(sc.ENV_SWITCH, "1")
    else:
        monkeypatch.delenv(sc.ENV_SWITCH, raising=False)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N)
    raw = command._env
    kind = raw._ex42_column_table[0]
    raw._ex42_column_table = [kind, {"family": "A", "kind": "balance_beams"}, {"family": "A", "kind": "gaps"}, {"family": "B", "kind": "beam"}]
    runtime.command_allocation.column_continuous = torch.tensor([True, False, False, False])
    raw.scene.terrain.terrain_types = (torch.arange(N) % 4).long()       # col 0 continuous · 1 A beams · 2 A gaps · 3 B beam
    return command, runtime


def _draw(command):
    command.time_left[:] = 4.0
    command.gen.manual_seed(7)
    command._resample_command(torch.arange(N))
    return command.vel_command_b.clone(), command.slot_current.clone(), command.is_flag_env.clone(), command.heading.clone()


def test_sparse_envs_get_forward_or_turn_in_place_only_and_pass_the_contract(monkeypatch, capsys):
    command, runtime = _term(monkeypatch, True)
    cmd, slot, flag, heading = _draw(command)
    cols = command._env.scene.terrain.terrain_types
    sparse = ((cols == 1) | (cols == 2)) & ~flag
    fwd, turn = sparse & (slot == 0), sparse & ((slot == 3) | (slot == 4))
    assert int(fwd.sum()) > 300 and int(turn.sum()) > 30 and int((fwd | turn).sum()) == int(sparse.sum())   # nothing else on sparse columns
    assert float(cmd[fwd, 0].min()) >= 0.3 and float(cmd[fwd, 0].max()) <= 1.5 and bool((cmd[fwd, 1:] == 0).all())
    assert bool((cmd[turn, :2] == 0).all()) and float(cmd[turn, 2].abs().min()) >= 0.15 and float(cmd[turn, 2].abs().max()) <= 1.2
    assert bool(((slot[turn] == 3) == (cmd[turn, 2] > 0)).all()) and not bool(heading[sparse].any())
    share = float(turn.sum()) / float(sparse.sum())
    assert 0.12 < share < 0.28                                                  # P(v < 0.3) with v ~ U[0, 1.5] = 0.2
    other = ~sparse & ~flag
    assert int((other & (slot != 0) & (slot != 3) & (slot != 4)).sum()) > 300    # continuous and B columns keep the stage mix (side, back, ...)
    bad = command_bad(cmd, slot, heading, runtime.env_stage, runtime.plan)
    assert not bool(bad[sparse].any())                                          # the run's command contract accepts every sparse command
    out = capsys.readouterr().out
    assert "EX42_SPARSE_PAPER_CMD where=start columns=2 of=4" in out and "outside_stage_mix=1" in out
    s = sc.summary()
    assert s["sparse_draws"] == int(sparse.sum()) and s["turn"] == int(turn.sum()) and s["forward"] == int(fwd.sum())
    beam = (cols == 1) & ~flag
    assert s["beam_draws"] == int(beam.sum()) and s["beam_turn"] == int((beam & turn).sum())   # balance_beams counted on its own (lead 07:46)
    json.dumps(s, allow_nan=False)


def test_off_draws_nothing_extra_and_the_commands_are_the_old_ones(monkeypatch):
    off, _ = _term(monkeypatch, False)
    state = off.gen.get_state().clone()
    cmd_off, slot_off, flag_off, _ = _draw(off)
    after_off = off.gen.get_state().clone()
    again, _ = _term(monkeypatch, False)
    again.gen.set_state(state)
    cmd_again, slot_again, _, _ = _draw(again)
    assert torch.equal(again.gen.get_state(), after_off) and torch.equal(cmd_again, cmd_off) and torch.equal(slot_again, slot_off)
    assert sc.summary() is None
    on, _ = _term(monkeypatch, True)
    cmd_on, slot_on, flag_on, _ = _draw(on)
    cols = on._env.scene.terrain.terrain_types
    sparse = ((cols == 1) | (cols == 2)) & ~flag_on
    assert torch.equal(flag_on, flag_off)
    assert torch.equal(cmd_on[~sparse & ~flag_on], cmd_off[~sparse & ~flag_on])   # non-sparse envs: the same commands bit for bit
    assert not torch.equal(cmd_on[sparse], cmd_off[sparse])


def test_shares_record_carries_the_counts(monkeypatch, tmp_path):
    from foothold_s2.commands.ex42_shares import CommandShares
    command, runtime = _term(monkeypatch, True)
    _draw(command)
    alloc = runtime.command_allocation
    assert isinstance(alloc, CommandShares)
    alloc.write(tmp_path, 50, None, plan_sha="x" * 64, stage_id="E1F")
    doc = json.loads(next(tmp_path.glob("command_shares_50_rank*.json")).read_text())
    assert doc["sparse_paper_cmd"]["sparse_draws"] == sc._COUNTS["sparse_draws"] > 0 and doc["sparse_paper_cmd"]["beam_draws"] > 0


def test_switch_values():
    import os
    os.environ[sc.ENV_SWITCH] = "yes"
    try:
        with pytest.raises(ValueError):
            sc.enabled()
    finally:
        del os.environ[sc.ENV_SWITCH]
