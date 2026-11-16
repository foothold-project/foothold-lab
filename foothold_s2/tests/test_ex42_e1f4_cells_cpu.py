"""E1F / E2 follow-up (lead 2026-11-16 10:40): three things on top of the new composition.

(1) Pc (slow_hold_range_s) can be switched at a boundary through the segment adjust file (EX42_SEGMENT_ADJUST): null = off, a pair = on,
    inside the row's own fence `slow_hold_fence_s`; without a file the plan row's [6, 8] stays; the record says source plan | adjust_file.
(2) EX42_PERCEPTION_V_BIAS_FLAG: est vx before the correction minus the real vx, flag (heading) envs only, per band of the real |vx|; record only.
(3) The E2 row carries the E1F low-speed cells as they are; the E1 row has none of the new cells (its bytes and its weight hash do not move).
Everything goes through the real plan loader, the real stage builder and the real segment start."""
from __future__ import annotations

import ast
import json
import pathlib
import types

import pytest
import torch
import yaml

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2" / "curriculum" / "ex42-approvals.yaml"
NOTE = {"decided_at": "2026-11-16T12:00+09:00", "reason": "two or more rungs down at m250", "evidence": "boundary 250 sheet"}


@pytest.fixture
def plan():
    return EX42Plan.load(PLAN)


def view(plan, stage_id):
    source = te.load_ex42_stage_zero_source(plan)
    return te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "b" * 64}, ex42_plan=plan, stage_id=stage_id)


def row(plan, stage_id):
    return next(r for r in plan.document["stages"] if r["id"] == stage_id)


def document(plan, stage_id, **segments):
    return {"schema": adj.SCHEMA, "stage_id": stage_id, "plan_sha256": plan.sha256,
            "segments": {key.lstrip("b"): value for key, value in segments.items()}}


def start(plan, stage_id, tmp_path, k, doc=None, write=True):
    v, path = view(plan, stage_id), None
    if doc is not None:
        path = tmp_path / f"adjust_{stage_id}_{k}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
    record = adj.start_segment(v, plan, stage_id, boundary_index=k, path=str(path) if path else None, log_dir=str(tmp_path), write=write)
    return v, record


# ---------- (1) Pc through the boundary file ----------

@pytest.mark.parametrize("stage_id", ["E1F", "E2"])
def test_without_a_file_the_plan_row_value_stays_and_is_recorded_as_plan(plan, tmp_path, stage_id):
    v, record = start(plan, stage_id, tmp_path, 0)
    assert v.stages[0].slow_hold_range_s == (6.0, 8.0)
    assert record["slow_hold_range_s"] == {"source": "plan", "entry": None, "value": [6.0, 8.0],
                                           "decided_at": None, "reason": None, "evidence": None}


@pytest.mark.parametrize("stage_id", ["E1F", "E2"])
def test_a_null_entry_turns_it_off_and_a_pair_inside_the_fence_turns_it_on(plan, tmp_path, stage_id):
    v, record = start(plan, stage_id, tmp_path, 1, document(plan, stage_id, b1={**NOTE, "slow_hold_range_s": None}))
    assert v.stages[0].slow_hold_range_s is None                                  # off: the sampler sees no range
    assert record["slow_hold_range_s"]["source"] == "adjust_file" and record["slow_hold_range_s"]["value"] is None
    assert record["slow_hold_range_s"]["entry"] == 1 and record["slow_hold_range_s"]["reason"] == NOTE["reason"]
    (tmp_path / "x").mkdir()
    v, record = start(plan, stage_id, tmp_path / "x", 1, document(plan, stage_id, b1={**NOTE, "slow_hold_range_s": [5, 7.5]}))
    assert v.stages[0].slow_hold_range_s == (5.0, 7.5) and record["slow_hold_range_s"]["value"] == [5.0, 7.5]


@pytest.mark.parametrize("bad", [[2.0, 7.0], [6.0, 13.0], [8.0, 6.0], [0.0, 6.0], [-1.0, 6.0], [5.0, 31.0], [6.0], [6.0, 7.0, 8.0],
                                 "6-8", 7.0, True, [True, 7.0], [float("nan"), 7.0], [6.0, float("inf")], {"lo": 6, "hi": 8}])
def test_a_value_outside_the_fence_or_not_a_pair_is_refused(plan, tmp_path, bad):
    with pytest.raises(ValueError, match="slow_hold_range_s"):
        start(plan, "E1F", tmp_path, 1, document(plan, "E1F", b1={**NOTE, "slow_hold_range_s": bad}))


def test_the_fence_edges_are_inside_and_the_fence_comes_from_the_row(plan, tmp_path):
    v, _ = start(plan, "E1F", tmp_path, 1, document(plan, "E1F", b1={**NOTE, "slow_hold_range_s": [4.0, 12.0]}))
    assert v.stages[0].slow_hold_range_s == (4.0, 12.0)
    row(plan, "E1F")["slow_hold_fence_s"] = [5.0, 9.0]                             # a narrower fence in the row refuses what was fine
    try:
        (tmp_path / "n").mkdir()
        with pytest.raises(ValueError, match="leaves the approved fence"):
            start(plan, "E1F", tmp_path / "n", 1, document(plan, "E1F", b1={**NOTE, "slow_hold_range_s": [4.0, 12.0]}))
        row(plan, "E1F").pop("slow_hold_fence_s")                                 # no fence: no entry at all
        with pytest.raises(ValueError, match="no slow_hold_fence_s"):
            start(plan, "E1F", tmp_path, 1, document(plan, "E1F", b1={**NOTE, "slow_hold_range_s": None}))
    finally:
        row(plan, "E1F")["slow_hold_fence_s"] = [4.0, 12.0]


def test_the_e1_row_has_no_cell_no_fence_and_takes_no_entry(plan, tmp_path):
    e1 = row(plan, "E1")
    assert "slow_hold_range_s" not in e1 and "slow_hold_fence_s" not in e1
    v, record = start(plan, "E1", tmp_path, 0)
    assert v.stages[0].slow_hold_range_s is None and "slow_hold_range_s" not in record      # the record of every other run keeps its shape
    (tmp_path / "e").mkdir()
    with pytest.raises(ValueError, match="no slow_hold_fence_s"):
        start(plan, "E1", tmp_path / "e", 1, document(plan, "E1", b1={**NOTE, "slow_hold_range_s": [6, 8]}))


def test_a_later_start_must_agree_with_what_the_earlier_segment_recorded(plan, tmp_path):
    doc = document(plan, "E1F", b1={**NOTE, "slow_hold_range_s": None})
    start(plan, "E1F", tmp_path, 1, doc)                                          # leaves segment_commands_b1.json: Pc off
    v, record = start(plan, "E1F", tmp_path, 2, doc, write=False)
    assert v.stages[0].slow_hold_range_s is None and record["slow_hold_range_s"]["entry"] == 1
    other = document(plan, "E1F", b1={**NOTE, "slow_hold_range_s": [6, 8]})
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        start(plan, "E1F", tmp_path, 2, other, write=False)


def test_an_entry_names_only_a_boundary_the_run_has_reached(plan, tmp_path):
    with pytest.raises(ValueError, match="before the run reached it"):
        start(plan, "E1F", tmp_path, 1, document(plan, "E1F", b2={**NOTE, "slow_hold_range_s": None}))


def test_the_off_range_reaches_the_sampler(plan, tmp_path, monkeypatch):
    """The stage the sampler reads is the one the segment start put on the view: off there means no hold in the command term."""
    from dataclasses import replace
    from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

    command, _, _ = e1f_term(monkeypatch, {})
    v, _ = start(plan, "E1F", tmp_path, 1, document(plan, "E1F", b1={**NOTE, "slow_hold_range_s": None}))
    stages = command.stage_runtime.plan.stages
    stages[0] = replace(stages[0], slow_hold_range_s=v.stages[0].slow_hold_range_s)
    command.vel_command_b[:] = torch.tensor([0.2, 0.0, 0.0])
    command.time_left[:] = 4.0
    command._apply_slow_hold(torch.arange(command.num_envs))
    assert bool((command.time_left == 4.0).all()) and not bool(command.slow_hold.any())


def test_the_hold_log_line_says_where_the_range_came_from(capsys):
    from foothold_s2.runners import start_runner as sr

    class Term:
        def slow_hold_summary(self):
            return 3, 7.0

    def line(record):
        fix = types.SimpleNamespace(_command_term=lambda: Term(), disable_logs=False, env=types.SimpleNamespace(num_envs=10),
                                    ex42_segment_commands=record)
        sr.StartRunner._slow_hold_log(fix, 50)
        return capsys.readouterr().out.strip()

    assert line({"slow_hold_range_s": {"source": "plan"}}).endswith("mean_time_left=7.00 source=plan")
    assert line({"slow_hold_range_s": {"source": "adjust_file"}}).endswith("source=adjust")
    assert line({}).endswith("source=none")                                         # a stage without the cell


# ---------- (2) the flag-env bias line ----------

def _flag_fix(heading, vel_x, est_vx):
    n = len(heading)
    from foothold_s2.runners import start_runner as sr
    est = torch.zeros(n, 51)
    est[:, sr.VX_CORR_VX_COL] = torch.tensor(est_vx)
    vel = torch.zeros(n, 3)
    vel[:, 0] = torch.tensor(vel_x)
    term = types.SimpleNamespace(heading=torch.tensor(heading))
    fix = types.SimpleNamespace(_command_term=lambda: term, disable_logs=False, pcfg={"est_mode": "learned"})
    return fix, est, vel


def test_flag_bias_known_answer_per_real_speed_band(capsys):
    from foothold_s2.runners import start_runner as sr

    #            env: 0     1     2     3     4     5    6 (not flag)
    heading = [True, True, True, True, True, True, False]
    vel_x = [0.05, 0.10, 0.17, 0.25, 0.40, -0.50, 0.10]          # env 2 sits between the 0.15 edge and 0.2: a moved edge changes its band
    est_vx = [0.07, 0.14, 0.18, 0.31, 0.45, -0.40, 0.90]
    fix, est, vel = _flag_fix(heading, vel_x, est_vx)
    sr.StartRunner._vflag_collect(fix, est, vel)
    sr.StartRunner._vflag_finish(fix, 49)
    assert capsys.readouterr().out == ""                                           # only every 50 updates
    sr.StartRunner._vflag_collect(fix, est, vel)
    sr.StartRunner._vflag_finish(fix, 50)
    out = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_PERCEPTION_V_BIAS_FLAG")]
    # the speed env (6) is not counted; bands by |real vx|: 0~0.15 holds envs 0 and 1, 0.15~0.3 envs 2 and 3, 0.3~ envs 4 and 5
    assert out == ["EX42_PERCEPTION_V_BIAS_FLAG it=50 band=0~0.15 n=2 mean=+0.03000",
                   "EX42_PERCEPTION_V_BIAS_FLAG it=50 band=0.15~0.3 n=2 mean=+0.03500",
                   "EX42_PERCEPTION_V_BIAS_FLAG it=50 band=0.3~ n=2 mean=+0.07500"]


def test_an_empty_band_prints_null_and_a_run_without_flag_envs_prints_n0(capsys):
    from foothold_s2.runners import start_runner as sr

    fix, est, vel = _flag_fix([False, False], [0.1, 0.2], [0.2, 0.3])
    sr.StartRunner._vflag_collect(fix, est, vel)
    sr.StartRunner._vflag_finish(fix, 100)
    out = capsys.readouterr().out.splitlines()
    assert out == [f"EX42_PERCEPTION_V_BIAS_FLAG it=100 band={b} n=0 mean=null" for b in ("0~0.15", "0.15~0.3", "0.3~")]


def test_the_flag_record_does_not_touch_the_training_numbers():
    """It reads est and vel and keeps only its own accumulator: inputs are unchanged and the function assigns nothing else."""
    from foothold_s2.runners import start_runner as sr

    fix, est, vel = _flag_fix([True, True, False], [0.1, 0.2, 0.3], [0.3, 0.1, 0.5])
    est.requires_grad_(True)
    est0, vel0 = est.detach().clone(), vel.clone()
    sr.StartRunner._vflag_collect(fix, est, vel)
    assert torch.equal(est.detach(), est0) and torch.equal(vel, vel0) and est.grad is None
    assert not fix._vflag_acc.requires_grad and set(vars(fix)) == {"_command_term", "disable_logs", "pcfg", "_vflag_acc"}
    tree = ast.parse(pathlib.Path(sr.__file__).read_text(encoding="utf-8"))
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in ("_vflag_collect", "_vflag_finish")):
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                assert node.attr == "_vflag_acc", (fn.name, node.attr)           # the only attribute it ever writes
    src = pathlib.Path(sr.__file__).read_text(encoding="utf-8")
    assert "self._vflag_collect(est, vel)" in src and "self._vflag_finish(it)" in src


# ---------- (3) E2 carries the E1F cells ----------

CELLS = ("low_forward_fraction", "low_side_fraction", "slow_hold_range_s", "slow_hold_fence_s", "slow_track_heading",
         "live_monitor", "live_adjustment")


def test_e2_has_every_e1f_cell_with_the_same_value_and_the_e1f_vector(plan):
    e1f, e2 = row(plan, "E1F"), row(plan, "E2")
    for name in CELLS:
        assert name in e2 and e2[name] == e1f[name], name
    assert e2["low_forward_fraction"] == 0.5 and e2["low_side_fraction"] == 0.4 and e2["slow_hold_range_s"] == [6.0, 8.0]
    assert e2["shares"] == e1f["shares"] and e2["commands"]["shares"] == e1f["commands"]["shares"]
    assert e2["shares"]["side_left"] == e2["shares"]["side_right"] == 0.09
    assert e2["live_adjustment"]["command_limits"] == {"low_forward_fraction": [0.2, 0.5], "low_side_fraction": [0.0, 0.5]}


def test_e2_stage_view_reads_the_cells_through_the_real_builder(plan):
    stage = view(plan, "E2").stages[0]
    assert (stage.low_forward_fraction, stage.low_side_fraction, stage.slow_hold_range_s) == (0.5, 0.4, (6.0, 8.0))
    assert adj.stage_slow_track_heading(plan, "E2") is True
    from foothold_s2.commands import ex42_shares
    assert ex42_shares.read_contract(plan, "E2")["shares"] == row(plan, "E1F")["shares"]
    assert adj.stage_low_forward(plan, "E3") is None and adj.stage_low_side(plan, "E3") is None      # E3 and later are untouched
    assert adj.stage_slow_hold(plan, "E3") == (False, None)
    for stage_id in ("E3", "E4", "E5", "M", "E6a", "E6b"):
        assert not set(CELLS) & set(row(plan, stage_id)), stage_id


def test_the_e2_live_adjustment_block_loads_and_is_pinned_to_the_same_limits_file(plan):
    from foothold_s2.ex42_live_adjust import limits_from_plan
    limits = limits_from_plan(row(plan, "E2")["live_adjustment"])
    assert limits["commands"]["low_side_fraction"] == (0.0, 0.5)


def test_the_e2_approval_text_agrees_with_the_e2_row(plan):
    """E2 moves terrain exposure only. Its approval carries no share or low-speed claim, so the E1F -> E2 share delta is zero on both sides, and the
    stage validator for E2 still holds on the changed plan (required_values / required_stage_values are the ones the row declares)."""
    approvals = yaml.safe_load(APPROVALS.read_text(encoding="utf-8"))
    cell = approvals["stage_e2_authorization"]
    assert "shares_delta" not in cell["boundary"] and cell["boundary"]["axis"] == "terrain_exposure"
    contract = row(plan, "E2")["authorization_contract"]
    assert contract["required_stage_values"] == {} and "boundary.shares_delta" not in contract["required_values"]
    assert row(plan, "E2")["shares"] == row(plan, "E1F")["shares"]
    from foothold_s2.curriculum import ex42_prep
    assert callable(ex42_prep.validate_stage_e2_authorization)


def test_e1_row_is_unchanged_by_the_new_cells(plan):
    e1 = row(plan, "E1")
    assert not {"low_side_fraction", "slow_hold_range_s", "slow_hold_fence_s"} & set(e1)
    assert e1["low_forward_fraction"] == 0.5 and e1["live_adjustment"]["command_limits"] == {"low_forward_fraction": [0.2, 0.5]}
