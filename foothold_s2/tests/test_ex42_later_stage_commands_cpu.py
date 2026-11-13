"""The stages after E1 keep the command ranges and the turn overlay E1 trains with.

Without a `commands` cell a stage falls back to the stage-zero ranges (side speed 0.2~0.6, no turn overlay), so what
E1 reinforced (decisions.tsv 2026-11-12 12:52, 13:03) would not be sampled again from E1F on. The split between the
slots inside the continuous columns stays the row's own `shares` (with flag)."""
import json
from pathlib import Path

import pytest

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.commands import ex42_shares
from foothold_s2.commands.mixed_core import EX39_SLOTS
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
LATER = ("E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b")


@pytest.fixture(scope="module")
def plan():
    return EX42Plan.load(PLAN)


def row(plan, stage_id):
    return next(r for r in plan.document["stages"] if r["id"] == stage_id)


@pytest.mark.parametrize("stage_id", LATER)
def test_the_row_carries_the_ranges_and_the_overlay_of_e1(plan, stage_id):
    e1, cell = row(plan, "E1")["commands"], row(plan, stage_id)["commands"]
    assert cell["ranges"] == e1["ranges"] and cell["turn_overlay"] == e1["turn_overlay"]
    profile = ex42_shares.stage_commands(plan, stage_id)           # the validated reader the trainer uses
    assert profile["ranges"]["side_vy_abs"] == (0.1, 0.8) and profile["turn_overlay"] == (0.25, 0.2, 0.6)


def test_the_jump_rows_have_no_cell(plan):
    assert all(ex42_shares.stage_commands(plan, stage_id) is None for stage_id in ("J0", "J1", "J2", "J3", "J4"))


# M has no `shares` row yet (its launch path is separate), so the trainer view cannot be built for it here
@pytest.mark.parametrize("stage_id", [s for s in LATER if s != "M"])
def test_the_trainer_samples_with_those_ranges_and_the_rows_own_split(plan, stage_id):
    source = te.load_ex42_stage_zero_source(plan)
    assert source[1].ranges["side_vy_abs"] == (0.2, 0.6) and source[1].turn_overlay is None      # the stage-zero fallback
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id=stage_id)
    stage = view.stages[0]
    assert stage.ranges["side_vy_abs"] == (0.1, 0.8) and stage.ranges["walk_vx"] == (0.3, 1.2) and stage.turn_overlay == (0.25, 0.2, 0.6)
    free = ex42_shares.CommandShares(view.command_contract, stage).free_stage     # what a continuous environment draws from
    shares = row(plan, stage_id)["shares"]
    assert free.ranges == stage.ranges and free.turn_overlay == stage.turn_overlay
    assert free.shares == pytest.approx({slot: shares[slot] / (1 - shares["flag"]) for slot in EX39_SLOTS})


def test_the_ranges_are_not_adjustable_in_those_stages(plan, tmp_path):
    source = te.load_ex42_stage_zero_source(plan)
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1F")
    assert adj.adjustable_boundaries(plan, "E1F") == ()                 # no limits cell: a commands entry is refused
    commands = json.loads(json.dumps(row(plan, "E1F")["commands"]))
    document = {"schema": adj.SCHEMA, "stage_id": "E1F", "plan_sha256": plan.sha256,
                "segments": {"1": {"decided_at": "t", "reason": "r", "evidence": "e", "commands": commands}}}
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match=r"may only name boundaries \[\] for commands"):
        adj.start_segment(view, plan, "E1F", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=False)
