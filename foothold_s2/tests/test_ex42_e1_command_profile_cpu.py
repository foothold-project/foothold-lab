"""E1 command reinforcement (CG E.2 E1 "명령 범위" · "명령 몫", v0.17k): the stage's own shares, ranges and the turn
overlay on reverse / side / diagonal commands reach the sampler and the per-step command check."""
from __future__ import annotations

import copy
import types
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import ex42_shares
from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum import continuous
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
SLOT = {name: i for i, name in enumerate(mc.EX39_SLOTS)}
MOVING = ("reverse", "side_left", "side_right", "diag_fwd_left", "diag_fwd_right", "diag_back_left", "diag_back_right")
N = 200_000


@pytest.fixture(scope="module")
def plan():
    return EX42Plan.load(PLAN)


@pytest.fixture(scope="module")
def source(plan):
    return te.load_ex42_stage_zero_source(plan)


def view(plan, source, stage_id):
    return te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan,
                                             stage_id=stage_id).stages[0]


def sample(stage, seed=7):
    gen = mc.make_generator(seed)
    return mc.resample_stage(gen, N, stage, torch.zeros(N))


def rows(out, *names):
    return torch.isin(out["slot"], torch.tensor([SLOT[n] for n in names]))


def test_e1_takes_its_own_profile_and_e0_keeps_stage_zero(plan, source):
    e1, e0 = view(plan, source, "E1"), view(plan, source, "E0")
    assert e0 is source[1] and e0.turn_overlay is None and e0.ranges["side_vy_abs"] == (0.2, 0.6)
    assert e1.turn_overlay == (0.25, 0.2, 0.6)
    assert e1.ranges == {"forward_vx": (0.1, 1.5), "walk_vx": (0.3, 1.2), "walk_wz_abs": (0.1, 1.0), "spin_wz_abs": (0.15, 1.5),
                         "reverse_vx": (-1.3, -0.2), "side_vy_abs": (0.1, 0.8), "diag_vx_abs": (0.3, 0.6), "diag_vy_abs": (0.2, 0.5)}
    assert (e1.shares["forward"], e1.shares["side_left"], e1.shares["side_right"]) == (0.19, 0.09, 0.09)
    assert {k: v for k, v in e1.shares.items() if k not in ("forward", "side_left", "side_right")} == \
        {k: v for k, v in e0.shares.items() if k not in ("forward", "side_left", "side_right")}
    assert abs(sum(e1.shares.values()) - 1.0) < 1e-9 and e1.rewards == e0.rewards and e1.heading_cfg == e0.heading_cfg


def test_the_sampler_draws_the_widened_ranges_and_the_new_shares(plan, source):
    out = sample(view(plan, source, "E1"))
    cmd = out["cmd"]
    side, walk, spin = rows(out, "side_left", "side_right"), rows(out, "walk_left", "walk_right"), rows(out, "spin_left", "spin_right")
    vy = cmd[side, 1].abs()
    assert 0.1 <= float(vy.min()) < 0.12 and 0.78 < float(vy.max()) <= 0.8             # stage zero stopped at 0.2 .. 0.6
    assert 0.3 <= float(cmd[walk, 0].min()) and 1.18 < float(cmd[walk, 0].max()) <= 1.2
    assert 0.1 <= float(cmd[walk, 2].abs().min()) < 0.12 and float(cmd[walk, 2].abs().max()) <= 1.0
    assert 0.15 <= float(cmd[spin, 2].abs().min()) < 0.17 and float(cmd[spin, 2].abs().max()) <= 1.5
    share = lambda *names: float(rows(out, *names).float().mean())   # noqa: E731
    assert abs(share("forward") - 0.19) < 0.004 and abs(share("side_left") - 0.09) < 0.003 and abs(share("side_right") - 0.09) < 0.003
    assert abs(share("reverse") - 0.14) < 0.004 and abs(share("stand") - 0.10) < 0.003


def test_a_quarter_of_the_reverse_side_and_diagonal_commands_also_turn(plan, source):
    out = sample(view(plan, source, "E1"))
    cmd = out["cmd"]
    moving = rows(out, *MOVING)
    turning = cmd[:, 2] != 0
    assert abs(float((turning & moving).sum() / moving.sum()) - 0.25) < 0.01
    wz = cmd[turning & moving, 2]
    assert 0.2 <= float(wz.abs().min()) and float(wz.abs().max()) <= 0.6
    assert abs(float((wz > 0).float().mean()) - 0.5) < 0.02                              # both directions
    for name in MOVING:                                                                  # every slot of the three kinds
        assert abs(float((turning & rows(out, name)).sum() / rows(out, name).sum()) - 0.25) < 0.03
    assert not bool(cmd[rows(out, "stand"), 2].any()) and not bool(cmd[rows(out, "forward"), 2].any())


def test_a_stage_without_the_overlay_keeps_its_random_stream(plan, source):
    e1 = view(plan, source, "E1")
    plain = replace(e1, turn_overlay=None)
    a, b = sample(plain), sample(e1)
    assert torch.equal(a["slot"], b["slot"]) and torch.equal(a["cmd"][:, :2], b["cmd"][:, :2])
    same = a["cmd"][:, 2] == b["cmd"][:, 2]
    assert bool(same[~rows(b, *MOVING)].all()) and not bool(a["cmd"][rows(a, *MOVING), 2].any())
    again = sample(e1)
    assert torch.equal(again["cmd"], b["cmd"])                                           # the overlay is seeded too


def _bad(cmd, slot, stage):
    n = len(slot)
    return continuous.command_bad(torch.tensor(cmd, dtype=torch.float32), torch.tensor(slot), torch.zeros(n, dtype=torch.bool),
                                  torch.zeros(n, dtype=torch.long), types.SimpleNamespace(stages=[stage]))


def test_the_step_check_accepts_the_overlay_only_inside_its_range_and_only_when_registered(plan, source):
    e1, e0 = view(plan, source, "E1"), view(plan, source, "E0")
    out = sample(e1)
    assert not bool(continuous.command_bad(out["cmd"], out["slot"], out["heading"], torch.zeros(N, dtype=torch.long),
                                           types.SimpleNamespace(stages=[e1])).any())
    cmds = [[-0.5, 0.0, 0.4], [-0.5, 0.0, -0.6], [-0.5, 0.0, 0.7], [-0.5, 0.0, 0.1], [0.0, 0.5, 0.3], [0.0, 0.9, 0.0],
            [0.4, 0.3, -0.25], [0.5, 0.0, 0.4]]
    slots = [SLOT["reverse"]] * 4 + [SLOT["side_left"]] * 2 + [SLOT["diag_fwd_left"], SLOT["forward"]]
    assert _bad(cmds, slots, e1).tolist() == [False, False, True, True, False, True, False, True]
    # stage zero: no overlay, side up to 0.6 only
    assert _bad(cmds, slots, e0).tolist() == [True, True, True, True, True, True, True, True]
    assert _bad([[-0.5, 0.0, 0.0], [0.0, 0.5, 0.0]], [SLOT["reverse"], SLOT["side_left"]], e0).tolist() == [False, False]


def _doc(plan, change):
    doc = copy.deepcopy(plan.document)
    change(next(row for row in doc["stages"] if row["id"] == "E1")["commands"])
    return types.SimpleNamespace(document=doc)


def test_the_profile_reader_returns_none_without_a_cell_and_validated_values_with_one(plan):
    assert ex42_shares.stage_commands(plan, "E0") is None and ex42_shares.stage_commands(plan, "J0") is None      # rows with no cell
    profile = ex42_shares.stage_commands(plan, "E1")
    assert profile["turn_overlay"] == (0.25, 0.2, 0.6) and profile["ranges"]["walk_vx"] == (0.3, 1.2)
    assert set(profile["shares"]) == set(mc.EX39_SLOTS)


@pytest.mark.parametrize("change,match", [
    (lambda c: c.pop("turn_overlay"), "exactly shares, ranges and turn_overlay"),
    (lambda c: c.update(extra=1), "exactly shares, ranges and turn_overlay"),
    (lambda c: c["shares"].update(forward=0.23), "sum to 1"),
    (lambda c: c["shares"].pop("stand"), "13 free slots"),
    (lambda c: c["shares"].update(flag=0.0), "13 free slots"),
    (lambda c: c["shares"].update(forward=True), "13 free slots"),
    (lambda c: c["ranges"].update(side_fast=[0.8, 1.0]), "stage-zero range keys"),
    (lambda c: c["ranges"].pop("diag_vy_abs"), "stage-zero range keys"),
    (lambda c: c["ranges"].update(side_vy_abs=[0.8, 0.1]), "low < high"),
    (lambda c: c["ranges"].update(side_vy_abs=[-0.1, 0.8]), "low < high"),
    (lambda c: c["ranges"].update(walk_vx=(0.3, 1.2, 2.0)), "low < high"),
    (lambda c: c["turn_overlay"].update(fraction=0.0), "fraction in"),
    (lambda c: c["turn_overlay"].update(fraction=1.5), "fraction in"),
    (lambda c: c["turn_overlay"].update(wz_abs=[0.0, 0.6]), "fraction in"),
    (lambda c: c["turn_overlay"].update(wz_abs=[0.6, 0.2]), "fraction in"),
    (lambda c: c["turn_overlay"].update(slots=["forward"]), "fraction in"),
])
def test_a_malformed_profile_is_refused(plan, change, match):
    with pytest.raises(ValueError, match=match):
        ex42_shares.stage_commands(_doc(plan, change), "E1")


# ---- adjustment limits (decisions.tsv 2026-11-12 14:23): the plan is frozen once E1 starts, so the lines are in the row ----

def _limits(plan, change):
    doc = copy.deepcopy(plan.document)
    change(next(s for s in doc["stages"] if s["id"] == "E1"))
    return types.SimpleNamespace(document=doc)


def test_e1_limits_are_the_approved_lines_and_the_start_profile_is_inside(plan):
    limits = ex42_shares.command_adjust_limits(plan, "E1")
    assert limits["ranges"]["side_vy_abs"] == (0.1, 1.0) and limits["ranges"]["walk_vx"] == (0.3, 1.5)
    assert limits["turn_overlay"] == (0.4, 0.2, 0.8)
    assert (limits["shares"]["forward"], limits["shares"]["side_left"], limits["shares"]["side_right"]) == \
        ((0.13, 0.23), (0.07, 0.12), (0.07, 0.12))
    base = ex42_shares.stage_commands(plan, "E1")
    named = {"side_vy_abs", "walk_vx"}                      # every other cell may only stay or narrow
    assert all(limits["ranges"][k] == v for k, v in base["ranges"].items() if k not in named)
    assert all(limits["shares"][k] == (v, v) for k, v in base["shares"].items() if k not in ("forward", "side_left", "side_right"))
    assert 2 * 0.12 + 0.13 + sum(v for k, v in base["shares"].items() if k not in ("forward", "side_left", "side_right")) == pytest.approx(1.0)
    assert ex42_shares.command_adjust_limits(plan, "E1F") is None and ex42_shares.command_adjust_limits(plan, "E0") is None


@pytest.mark.parametrize("change, match", [
    (lambda row: row["command_adjust_limits"]["ranges"].update(side_vy_abs=[0.1, 0.7]), "start outside"),      # start 0.8 above the line
    (lambda row: row["command_adjust_limits"]["ranges"].update(side_vy_abs=[0.2, 1.0]), "start outside"),      # the slow floor moved
    (lambda row: row["command_adjust_limits"]["shares"].update(side_left=[0.07, 0.08]), "start outside"),
    (lambda row: row["command_adjust_limits"]["turn_overlay"].update(fraction_max=0.2), "start outside"),
    (lambda row: row["command_adjust_limits"]["turn_overlay"].update(wz_abs=[0.3, 0.8]), "start outside"),
    (lambda row: row["command_adjust_limits"]["ranges"].update(side_vy=[0.1, 1.0]), "unknown cell or a malformed"),
    (lambda row: row["command_adjust_limits"]["shares"].update(flag=[0.0, 0.1]), "unknown cell or a malformed"),
    (lambda row: row["command_adjust_limits"]["ranges"].update(walk_vx=[1.5, 0.3]), "unknown cell or a malformed"),
    (lambda row: row["command_adjust_limits"]["turn_overlay"].update(fraction_max=1.5), "unknown cell or a malformed"),
    (lambda row: row["command_adjust_limits"].update(rewards={}), "exactly ranges, turn_overlay, shares"),
    (lambda row: row.pop("commands"), "needs a commands profile"),
])
def test_a_malformed_limits_cell_is_refused(plan, change, match):
    with pytest.raises(ValueError, match=match):
        ex42_shares.command_adjust_limits(_limits(plan, change), "E1")


def test_the_start_refuses_a_plan_whose_limits_cell_is_malformed(plan, source):
    broken = _limits(plan, lambda row: row["command_adjust_limits"]["ranges"].update(side_vy_abs=[0.1, 0.7]))
    with pytest.raises(ValueError, match="start outside"):
        te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=broken, stage_id="E1")
