"""low_side_fraction (lead 2026-11-16 01:51): the share of the side commands drawn with |vy| in [0.1, 0.3].

Off (0 or no cell) is the old sampler bit for bit; 0.5 puts about 0.5 of the side commands below 0.3 against 0.2/0.7 = 0.286 of
the E1 range [0.1, 0.8] (a factor of about 1.75)."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest
import torch

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.commands import mixed_core as mc
from foothold_s2.ex42_live_adjust import limits_from_plan, validate_request
from foothold_s2.tests.test_ex42_segment_adjust_cpu import LOW_NOTE, document, plan, source, view  # noqa: F401

N = 400_000


def _draw(stage, seed=21):
    out = mc.resample_stage(mc.make_generator(seed), N, stage, torch.zeros(N))
    side = torch.isin(out["slot"], torch.tensor([mc.EX39_SLOTS.index("side_left"), mc.EX39_SLOTS.index("side_right")]))
    return out, side


def _share_below(stage):
    out, side = _draw(stage)
    vy = out["cmd"][side, 1].abs()
    return float((vy < 0.3).float().mean()), float(vy.min()), float(vy.max())


def test_off_is_the_old_sampler_bit_for_bit(view):
    stage = view.stages[0]
    assert stage.low_side_fraction == 0.0
    a, _ = _draw(stage)
    b, _ = _draw(replace(stage, low_side_fraction=0.0))
    for key in ("cmd", "slot", "stand", "spin", "heading", "psi_star"):
        assert torch.equal(a[key], b[key])


def test_on_moves_the_side_share_below_03_by_about_one_point_seven_five(view):
    """Uniform [0.1, 0.8]: 0.2/0.7 = 0.2857 below 0.3. With 0.5: 0.5 + 0.5 * 0 = 0.5. Ratio 1.75. About 0.08 million side draws
    (0.18 share of 400k envs x 2 slots) give a standard error near 0.002, so 0.01 is five standard errors."""
    stage = view.stages[0]
    base_share, _, _ = _share_below(stage)
    on_share, low, high = _share_below(replace(stage, low_side_fraction=0.5))
    assert abs(base_share - 0.2 / 0.7) < 0.01
    assert abs(on_share - 0.5) < 0.01 and 0.1 <= low and high <= 0.8 + 1e-6
    assert 1.65 < on_share / base_share < 1.85
    out_on, side_on = _draw(replace(stage, low_side_fraction=0.5))
    out_off, side_off = _draw(stage)
    assert float(side_on.float().mean()) == pytest.approx(float(side_off.float().mean()), abs=0.004)   # the slot shares do not move


def test_the_plan_row_cell_and_the_fence(plan, view, tmp_path):
    limits = adj.reward_limits()
    assert limits["command_cells"]["low_side_fraction"] == (0.0, 0.5)
    row = next(r for r in plan.document["stages"] if r["id"] == "E1")
    assert adj.stage_low_side(plan, "E1", limits) is None                        # the shipped E1 row has no cell: off
    row["low_side_fraction"] = 0.5
    try:
        assert adj.stage_low_side(plan, "E1", limits) == 0.5
        row["low_side_fraction"] = 0.6
        with pytest.raises(ValueError, match="low_side_fraction must be a number inside the approved limits"):
            adj.stage_low_side(plan, "E1", limits)
        row["low_side_fraction"] = True
        with pytest.raises(ValueError, match="low_side_fraction"):
            adj.stage_low_side(plan, "E1", limits)
    finally:
        row.pop("low_side_fraction")


def test_an_adjust_file_entry_sets_and_records_it_and_a_later_start_must_agree(plan, view, tmp_path):
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(document(plan, b1={**LOW_NOTE, "low_side_fraction": 0.5})), encoding="utf-8")
    record = adj.start_segment(view, plan, "E1", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=True)
    assert view.stages[0].low_side_fraction == 0.5
    assert record["low_side_fraction"]["value"] == 0.5 and record["low_side_fraction"]["source"] == "adjust_file"
    assert record["low_side_fraction"]["entry"] == 1 and len(record["low_side_fraction"]["limits_sha256"]) == 64
    assert "low_forward_fraction" not in record or record["low_forward_fraction"]["value"] != 0.5    # the other cell did not move
    # the next segment starts from the same file: it must say what segment 1 ran with
    again = adj.start_segment(view, plan, "E1", boundary_index=2, path=str(path), log_dir=str(tmp_path), write=False)
    assert again["low_side_fraction"]["value"] == 0.5
    bad = tmp_path / "adjust2.json"
    bad.write_text(json.dumps(document(plan, b1={**LOW_NOTE, "low_side_fraction": 0.3})), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        adj.start_segment(view, plan, "E1", boundary_index=2, path=str(bad), log_dir=str(tmp_path), write=False)
    over = tmp_path / "adjust3.json"
    over.write_text(json.dumps(document(plan, b1={**LOW_NOTE, "low_side_fraction": 0.7})), encoding="utf-8")
    with pytest.raises(ValueError, match="inside the approved limits"):
        adj.start_segment(view, plan, "E1", boundary_index=1, path=str(over), log_dir=str(tmp_path / "x"), write=False)


def test_a_record_without_the_cell_has_the_old_shape(plan, view, tmp_path):
    record = adj.start_segment(view, plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path), write=False)
    assert "low_side_fraction" not in record


def test_the_live_adjustment_accepts_the_key_inside_the_plan_limits(plan):
    config = next(r for r in plan.document["stages"] if r["id"] == "E1")["live_adjustment"]
    limits = limits_from_plan(config)
    assert limits["commands"]["low_side_fraction"] == (0.0, 0.5)
    ok = validate_request({"decided_by": "t", "decided_at": "t", "evidence": "t", "commands": {"low_side_fraction": 0.5}}, limits)
    assert ok["commands"] == {"low_side_fraction": 0.5}
    with pytest.raises(ValueError, match="outside approved limit"):
        validate_request({"decided_by": "t", "decided_at": "t", "evidence": "t", "commands": {"low_side_fraction": 0.6}}, limits)
    with pytest.raises(ValueError, match="cells unknown"):
        validate_request({"decided_by": "t", "decided_at": "t", "evidence": "t", "commands": {"low_side": 0.5}}, limits)


def test_the_live_apply_replaces_the_running_stage(plan, view):
    from types import SimpleNamespace
    from foothold_s2.ex42_live_adjust import apply_values, live_values
    runtime = SimpleNamespace(plan=SimpleNamespace(stages=[view.stages[0]]), stage_config=None, command_stats=None,
                              env=SimpleNamespace(reward_manager=None))
    apply_values(runtime, {"commands": {"low_side_fraction": 0.5}})
    assert runtime.plan.stages[0].low_side_fraction == 0.5 and runtime.stage_config.low_side_fraction == 0.5
    assert live_values(runtime, {"commands": {"low_side_fraction": 0.5}})["commands"] == {"low_side_fraction": 0.5}


def test_the_plan_row_cell_reaches_the_stage_and_needs_a_low_side_range(plan, source):
    from foothold_s2.scripts import ex42_training_entry as te
    row = next(r for r in plan.document["stages"] if r["id"] == "E1")
    row["low_side_fraction"] = 0.5
    try:
        view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1")
        assert view.stages[0].low_side_fraction == 0.5
        row["low_side_fraction"] = 2
        with pytest.raises(ValueError, match="low_side_fraction invalid"):
            te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1")
    finally:
        row.pop("low_side_fraction")


def test_the_treatment_fingerprint_changes_only_when_the_cell_is_used():
    import inspect
    from foothold_s2 import ex42_e1_v2
    text = inspect.getsource(ex42_e1_v2)
    assert text.count('actual["low_side_fraction"]') == 2             # both paths add it only when present
