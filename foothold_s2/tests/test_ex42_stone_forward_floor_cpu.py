"""E2 o2 (DESIGN-E2-NEXT-RUN-1118 3.2): an env on stepping stones gets no forward command below 0.3 m/s; the other terrain is as before.

The switch is `EX42_STONE_FWD_FLOOR` in e2.env (plan and approvals stay as they are). The real MixedVelocityCommand, its sampler, the real plan row
and view reader, the real stage runtime and the real record function are used (only Isaac's CommandTerm base is a double, see e1f_term).
"""
from __future__ import annotations

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import PLAN, e1f_term

N = 3072


def _term(monkeypatch, floor):
    if floor is None:
        monkeypatch.delenv("EX42_STONE_FWD_FLOOR", raising=False)
    else:
        monkeypatch.setenv("EX42_STONE_FWD_FLOOR", floor)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N)
    raw = command._env
    kind = raw._ex42_column_table[0]
    raw._ex42_column_table = [kind, {"family": kind["family"], "kind": "stepping_stones_low"}]    # column 0 = continuous (as the fixture), column 1 = stones
    runtime.command_allocation.column_continuous = torch.tensor([True, False])                   # a stones column is not a continuous one (env_stage 0)
    raw.scene.terrain.terrain_types = (torch.arange(N) % 3 == 0).long()                           # every third env is on stones
    return command, runtime


def _draw(command):
    command.time_left[:] = 4.0
    command.gen.manual_seed(7)
    command._resample_command(torch.arange(N))
    return command.vel_command_b.clone(), command.slot_current.clone(), command.is_flag_env.clone()


def test_on_the_stone_envs_have_no_forward_command_below_the_floor_and_the_rest_still_do(monkeypatch):
    command, _ = _term(monkeypatch, "0.3")
    cmd, slot, flag = _draw(command)
    stone = command._stone_env_all()
    fwd = (slot == 0) & ~flag
    assert int((fwd & stone).sum()) > 100 and int((fwd & ~stone).sum()) > 200
    assert float(cmd[fwd & stone, 0].min()) >= 0.3
    assert int((cmd[fwd & ~stone, 0] < 0.3).sum()) > 30                       # the E1F row's low_forward_fraction is still in force off the stones
    summary = command.stone_floor_summary()
    assert summary[0] == 0.3 and summary[1] == int(stone.sum()) and summary[2] == N
    assert summary[3] == int((fwd & stone).sum()) and summary[4] == 0 and summary[6] > 30 and summary[7] >= 0.3


def test_the_other_terrain_is_bit_for_bit_the_draw_without_the_cell_and_only_slow_stone_forwards_change(monkeypatch):
    on, _ = _term(monkeypatch, "0.3")
    cmd_on, slot_on, flag_on = _draw(on)
    off, _ = _term(monkeypatch, None)
    cmd_off, slot_off, flag_off = _draw(off)
    stone = on._stone_env_all()
    assert torch.equal(slot_on, slot_off) and torch.equal(flag_on, flag_off)
    slow_stone_fwd = (slot_off == 0) & ~flag_off & stone & (cmd_off[:, 0] < 0.3)
    assert int(slow_stone_fwd.sum()) > 20
    assert torch.equal(cmd_on[~slow_stone_fwd], cmd_off[~slow_stone_fwd])
    assert bool((cmd_on[slow_stone_fwd, 0] >= 0.3).all()) and torch.equal(cmd_on[slow_stone_fwd, 1:], cmd_off[slow_stone_fwd, 1:])


def test_without_the_variable_the_cell_is_off_and_draws_nothing_extra(monkeypatch):
    command, runtime = _term(monkeypatch, None)
    assert runtime.plan.stages[0].stone_forward_floor is None and command.stone_floor_summary() is None
    state = command.gen.get_state().clone()
    command.time_left[:] = 4.0
    command._resample_command(torch.arange(N))
    after_off = command.gen.get_state().clone()
    again, _ = _term(monkeypatch, None)
    again.gen.set_state(state)
    again.time_left[:] = 4.0
    again._resample_command(torch.arange(N))
    assert torch.equal(again.gen.get_state(), after_off)                    # same stream consumption, so nothing was drawn for the cell


@pytest.mark.parametrize("bad", ["abc", "nan", "0.05", "0.7", "-0.3"])
def test_a_bad_value_refuses_the_start(monkeypatch, bad):
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    monkeypatch.setenv("EX42_STONE_FWD_FLOOR", bad)
    with pytest.raises(ValueError, match="EX42_STONE_FWD_FLOOR"):
        te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")


def test_a_floor_without_the_column_table_is_an_error_not_a_silent_off(monkeypatch):
    command, _ = _term(monkeypatch, "0.3")
    del command._env._ex42_column_table
    with pytest.raises(ValueError, match="column table"):
        command._resample_command(torch.arange(8))


def test_the_receipt_line_names_the_floor_and_the_counts_and_prints_off_when_unset(monkeypatch, capsys):
    from foothold_s2.runners import start_runner as sr

    class Fix:
        disable_logs = False

        def __init__(self, command):
            self._term = command

        def _command_term(self):
            return self._term

    command, _ = _term(monkeypatch, "0.3")
    _draw(command)
    sr.StartRunner._command_cells_log(Fix(command), 1)
    line = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_STONE_FWD_FLOOR")]
    assert len(line) == 1 and "floor=0.3 stone_envs=1024 of=3072" in line[0] and "stone_below_floor=0" in line[0] and "stone_fwd_min=0." in line[0]
    off, _ = _term(monkeypatch, None)
    sr.StartRunner._command_cells_log(Fix(off), 1)
    assert [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_STONE_FWD_FLOOR")] == ["EX42_STONE_FWD_FLOOR it=1 floor=off"]


def test_sampler_floor_must_be_below_the_top_of_the_forward_range(monkeypatch):
    command, runtime = _term(monkeypatch, "0.3")
    from dataclasses import replace
    stage = replace(runtime.plan.stages[0], stone_forward_floor=9.0)
    with pytest.raises(ValueError, match="below the top"):
        mc.resample_stage(mc.make_generator(1), 16, stage, torch.zeros(16), torch.ones(16, dtype=torch.bool))


def test_the_e2_entry_view_carries_the_floor_from_the_environment_variable_and_other_stages_stay_off_without_it(monkeypatch):
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    monkeypatch.setenv("EX42_STONE_FWD_FLOOR", "0.3")
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
    assert view.stages[0].stone_forward_floor == 0.3
    monkeypatch.delenv("EX42_STONE_FWD_FLOOR")
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
    assert view.stages[0].stone_forward_floor is None
