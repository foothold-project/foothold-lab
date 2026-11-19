"""Forward floor on the gap columns (A/gaps, B/gap, C/gap): EX42_STONE_FWD_FLOOR=0.7 + EX42_STONE_FWD_FLOOR_KINDS. The real command term and
sampler (fixture of the stone-floor test); beams, stones and continuous terrain are not touched. CPU only."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import PLAN, e1f_term

N = 3072
KINDS = "A/gaps,B/gap,C/gap"


def _term(monkeypatch, floor, kinds=KINDS):
    for name, value in (("EX42_STONE_FWD_FLOOR", floor), ("EX42_STONE_FWD_FLOOR_KINDS", kinds if floor is not None else None)):
        monkeypatch.delenv(name, raising=False) if value is None else monkeypatch.setenv(name, value)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N)
    raw = command._env
    base = raw._ex42_column_table[0]
    raw._ex42_column_table = [base, {"family": "A", "kind": "gaps"}, {"family": "B", "kind": "gap"}, {"family": "C", "kind": "gap"},
                              {"family": "B", "kind": "beam"}, {"family": "A", "kind": "stepping_stones_low"}]
    runtime.command_allocation.column_continuous = torch.tensor([True] + [False] * 5)
    raw.scene.terrain.terrain_types = (torch.arange(N) % 6).long()
    return command, runtime


def _draw(command):
    command.time_left[:] = 4.0
    command.gen.manual_seed(7)
    command._resample_command(torch.arange(N))
    return command.vel_command_b.clone(), command.slot_current.clone(), command.is_flag_env.clone()


def test_gap_column_envs_get_no_forward_command_below_0_7_and_nobody_else_is_touched(monkeypatch):
    on, _ = _term(monkeypatch, "0.7")
    cmd_on, slot, flag = _draw(on)
    off, _ = _term(monkeypatch, None)
    cmd_off, slot_off, flag_off = _draw(off)
    cols = on._env.scene.terrain.terrain_types
    gap = (cols >= 1) & (cols <= 3)
    assert torch.equal(on._stone_env_all(), gap)                         # exactly A/gaps, B/gap, C/gap (not beams, not stones, not continuous)
    fwd = (slot == 0) & ~flag
    assert torch.equal(slot, slot_off) and int((fwd & gap).sum()) > 200
    assert float(cmd_on[fwd & gap, 0].min()) >= 0.7 and float(cmd_on[fwd & gap, 0].max()) <= 1.5   # only above 0.7, up to the forward range top
    assert int((cmd_off[fwd & gap, 0] < 0.7).sum()) > 50                 # without the cell about half of them were slower
    changed = fwd & gap & (cmd_off[:, 0] < 0.7)
    assert torch.equal(cmd_on[~changed], cmd_off[~changed])              # everything else bit for bit (beam columns, stones, other slots)
    assert float(cmd_on[fwd & (cols == 4), 0].min()) < 0.7 and float(cmd_on[fwd & (cols == 5), 0].min()) < 0.7   # beam and stones keep slow commands


def test_without_the_kinds_the_cell_is_the_old_stones_only_one(monkeypatch):
    command, _ = _term(monkeypatch, "0.3", kinds="")
    cols = command._env.scene.terrain.terrain_types
    assert torch.equal(command._stone_env_all(), cols == 5)


def test_a_kind_not_in_the_table_is_an_error_not_a_silent_off(monkeypatch):
    command, _ = _term(monkeypatch, "0.7", kinds="A/gaps,D/nothing")
    with pytest.raises(ValueError, match="not in the column table"):
        command._resample_command(torch.arange(8))


@pytest.mark.parametrize("floor,kinds", [("0.95", KINDS), ("0.7", "B/gap,B/gap"), ("0.7", "gap"), ("0.7", "b/gap"), ("0.7", "")])
def test_bad_start_values_refuse(monkeypatch, floor, kinds):
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    monkeypatch.setenv("EX42_STONE_FWD_FLOOR", floor)
    monkeypatch.setenv("EX42_STONE_FWD_FLOOR_KINDS", kinds)
    if kinds == "":                                                           # kinds empty = stones only: 0.7 is above the stones limit 0.6
        with pytest.raises(ValueError, match="EX42_STONE_FWD_FLOOR invalid"):
            te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
        return
    with pytest.raises(ValueError, match="EX42_STONE_FWD_FLOOR"):
        te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")


def test_kinds_without_a_floor_refuse_and_the_view_carries_both(monkeypatch):
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    monkeypatch.delenv("EX42_STONE_FWD_FLOOR", raising=False)
    monkeypatch.setenv("EX42_STONE_FWD_FLOOR_KINDS", KINDS)
    with pytest.raises(ValueError, match="needs EX42_STONE_FWD_FLOOR"):
        te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
    monkeypatch.setenv("EX42_STONE_FWD_FLOOR", "0.7")
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
    assert view.stages[0].stone_forward_floor == 0.7 and view.stages[0].stone_forward_floor_kinds == ("A/gaps", "B/gap", "C/gap")
