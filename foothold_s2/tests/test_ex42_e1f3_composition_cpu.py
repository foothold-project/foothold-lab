"""E1F new composition (lead 2026-11-16 09:26, planner 09:23): the E1F plan row carries
 (1) the shares  forward .17 walk .06 x2 spin .07 x2 stand .10 reverse .10 side .09 x2 diag .02 x2 .025 x2 flag .10  (sum 1.00)
     and the approval literal shares_delta that is the difference to the stage-zero vector,
 (2) P-side low_side_fraction 0.4 inside the fence [0, 0.5] (the limits file sha pinned by the row),
 (3) Pc slow_hold_range_s [6, 8] (the E1 row has no cell = off),
 (4) the start and record lines (EX42_COMMAND_CELLS, EX42_PERCEPTION_VX_CORR ... raw_bias_fwd01=).
Every check goes through the real plan loader and the real stage builder (make_ex42_stage_zero_plan_view)."""
from __future__ import annotations

import hashlib
import math
import pathlib

import pytest
import yaml

from foothold_s2.commands import ex42_shares
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2" / "curriculum" / "ex42-approvals.yaml"
LIMITS = ROOT / "foothold_s2" / "curriculum" / "ex42-reward-adjust-limits.yaml"

NEW_SHARES = {"forward": 0.17, "walk_left": 0.06, "walk_right": 0.06, "spin_left": 0.07, "spin_right": 0.07, "stand": 0.1,
              "reverse": 0.1, "side_left": 0.09, "side_right": 0.09, "diag_fwd_left": 0.02, "diag_fwd_right": 0.02,
              "diag_back_left": 0.025, "diag_back_right": 0.025, "flag": 0.1}


def _view(stage_id):
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    return plan, te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "b" * 64}, ex42_plan=plan,
                                                    stage_id=stage_id)


def _row(plan, stage_id):
    return next(r for r in plan.document["stages"] if r["id"] == stage_id)


def test_e1f_row_shares_are_the_new_vector_and_sum_to_one():
    plan, _ = _view("E1F")
    shares = ex42_shares.read_contract(plan, "E1F")["shares"]
    assert {k: shares[k] for k in NEW_SHARES} == NEW_SHARES and set(shares) == set(NEW_SHARES)
    assert math.isclose(math.fsum(shares.values()), 1.0, abs_tol=1e-12)
    e1 = _row(plan, "E1")["commands"]["shares"]
    assert shares["side_left"] == shares["side_right"] == e1["side_left"] == e1["side_right"] == 0.09   # the side share is not reduced (same as E1)


def test_shares_delta_is_the_difference_to_the_stage_zero_vector_in_plan_and_approvals():
    plan, _ = _view("E1F")
    zero = plan.document["stage_zero"]["shares"]
    delta = {k: round(NEW_SHARES[k] - zero.get(k, 0.0), 6) for k in NEW_SHARES if abs(NEW_SHARES[k] - zero.get(k, 0.0)) > 1e-9}
    approvals = yaml.safe_load(APPROVALS.read_text(encoding="utf-8"))
    cell = approvals["stage_e1f_authorization"]
    required = _row(plan, "E1F")["authorization_contract"]["required_values"]
    assert delta == {"flag": 0.1, "forward": -0.06, "spin_left": -0.02, "spin_right": -0.02, "reverse": -0.04,
                     "side_left": 0.02, "side_right": 0.02}
    # ex42_prep.validate_stage_authorization compares these two dictionaries for equality (ex42_prep.py required_values loop)
    assert required["boundary.shares_delta"] == cell["boundary"]["shares_delta"] == delta
    assert _row(plan, "E1F")["authorization_contract"]["required_stage_values"]["shares"] == NEW_SHARES
    assert plan.document["stage_zero"]["approval_sha256"] == hashlib.sha256(APPROVALS.read_bytes()).hexdigest()


def test_p_side_and_pc_cells_reach_the_real_e1f_stage_and_are_off_in_e1():
    plan, view = _view("E1F")
    stage = view.stages[0]
    assert stage.low_side_fraction == 0.4 and stage.slow_hold_range_s == (6.0, 8.0) and stage.low_forward_fraction == 0.5
    _, e1 = _view("E1")
    assert e1.stages[0].low_side_fraction == 0.0 and e1.stages[0].slow_hold_range_s is None
    assert "low_side_fraction" not in _row(plan, "E1") and "slow_hold_range_s" not in _row(plan, "E1")


def test_the_live_adjustment_fence_and_the_pinned_limits_file_agree():
    plan, _ = _view("E1F")
    row = _row(plan, "E1F")
    assert row["live_adjustment"]["command_limits"] == {"low_forward_fraction": [0.2, 0.5], "low_side_fraction": [0.0, 0.5]}
    assert row["live_adjustment"]["segment_reward_limits_sha256"] == hashlib.sha256(LIMITS.read_bytes()).hexdigest()
    from foothold_s2.ex42_live_adjust import limits_from_plan
    limits = limits_from_plan(row["live_adjustment"], segment_path=LIMITS)         # the real reader refuses a sha or cell mismatch
    assert limits["commands"] == {"low_forward_fraction": (0.2, 0.5), "low_side_fraction": (0.0, 0.5)}
    assert 0.0 <= row["low_side_fraction"] <= 0.5


@pytest.mark.parametrize("bad", [[6.0], [8.0, 6.0], [0.0, 8.0], [6.0, 31.0], "6-8", [6.0, True], [6.0, float("nan")]])
def test_a_malformed_slow_hold_range_refuses_the_start(bad):
    plan = EX42Plan.load(PLAN)
    _row(plan, "E1F")["slow_hold_range_s"] = bad
    source = te.load_ex42_stage_zero_source(plan)
    with pytest.raises(ValueError, match="slow_hold_range_s"):
        te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "b" * 64}, ex42_plan=plan, stage_id="E1F")


def test_start_cells_line_and_vx_corr_record_line_carry_the_new_fields(capsys):
    import torch
    from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term
    from foothold_s2.runners import start_runner as sr

    class Fix:                                                       # the pieces of StartRunner the two record functions use
        disable_logs = False

        def __init__(self, command):
            self._term = command

        def _command_term(self):
            return self._term

    import pytest as _p
    mp = _p.MonkeyPatch()
    try:
        command, runtime, _ = e1f_term(mp, {})
        fix = Fix(command)
        sr.StartRunner._command_cells_log(fix, 1)
        sr.StartRunner._command_cells_log(fix, 2)                    # not first, not a multiple of 50: silent
        sr.StartRunner._command_cells_log(fix, 50)
        out = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_COMMAND_CELLS")]
        assert out == ["EX42_COMMAND_CELLS it=1 low_side_fraction=0.4 low_forward_fraction=0.5 slow_hold_range_s=6-8",
                       "EX42_COMMAND_CELLS it=50 low_side_fraction=0.4 low_forward_fraction=0.5 slow_hold_range_s=6-8"]
        from dataclasses import replace
        command.stage_runtime.plan.stages[0] = replace(command.stage_runtime.plan.stages[0], low_side_fraction=0.2)
        fix._cells_logged = True
        sr.StartRunner._command_cells_log(fix, 100)
        assert "low_side_fraction=0.2" in capsys.readouterr().out           # the live adjustment's value, not the plan's
    finally:
        mp.undo()


def test_raw_bias_fwd01_is_the_mean_of_raw_est_minus_body_vx_over_the_fwd01_mask_before_the_correction(capsys):
    """Known answer: six envs, two of them on the FWD01 mask (|vy| small, wz 0, heading off, vx 0.08~0.12, command older than 2 s)."""
    import types

    import torch
    from foothold_s2.runners import start_runner as sr

    o = torch.zeros(6, 45)
    o[:, 6] = torch.tensor([0.10, 0.11, 0.10, 0.50, 0.10, 0.10])           # vx command
    o[:, 7] = torch.tensor([0.0, 0.0, 0.2, 0.0, 0.0, 0.0])                 # env 2: sideways
    o[:, 8] = torch.tensor([0.0, 0.0, 0.0, 0.0, 0.3, 0.0])                 # env 4: turning
    term = types.SimpleNamespace(cfg=types.SimpleNamespace(resampling_time_range=(4.0, 4.0)),
                                 time_left=torch.tensor([1.0, 1.0, 1.0, 1.0, 1.0, 3.5]),        # env 5: command only 0.5 s old
                                 heading=torch.zeros(6, dtype=torch.bool))
    est = torch.zeros(6, 51)
    est[:, sr.VX_CORR_VX_COL] = torch.tensor([0.20, 0.17, 0.9, 0.9, 0.9, 0.9])
    vel = torch.zeros(6, 3)
    vel[:, 0] = torch.tensor([0.10, 0.10, 0.0, 0.0, 0.0, 0.0])
    fix = types.SimpleNamespace(_command_term=lambda: term, disable_logs=False)
    sr.StartRunner._vxcorr_raw_fwd01(fix, o, est, vel)
    n, total = (float(x) for x in fix._vxcorr_raw_acc)
    assert n == 2.0 and total == pytest.approx((0.20 - 0.10) + (0.17 - 0.10))
    fix._vxcorr_acc = torch.tensor([3.0, 0.3, 0.2], dtype=torch.float64)
    sr.StartRunner._vxcorr_finish(fix, 50)
    line = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_PERCEPTION_VX_CORR it=50")][0]
    assert "raw_bias_fwd01=+0.08500 n_fwd01=2" in line and "est_vx_before=+0.10000" in line
