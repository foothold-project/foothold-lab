"""Flag envs turn first (plan cell `flag_turn_first_rad`, E2 row; lead 2026-11-17): far off the flag -> in-place turn, near -> walk + small wz.
The flag state machine, the contract and the plan reader are the real ones; no Isaac."""
from __future__ import annotations

import math
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.runners.contracts import flag_contract_bad
from foothold_s2.scripts import ex42_training_entry as te

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def _state(angles, v=0.8, dist=3.0):
    """Robots at the origin facing +x; flag at the given bearing angle (rad) and distance."""
    a = torch.as_tensor(angles, dtype=torch.float32)
    flags = torch.stack([dist * torch.cos(a), dist * torch.sin(a)], dim=1)[:, None, :]
    st = mc.FlagState.new(flags)
    st.v[:] = v
    return st, torch.zeros(len(a), 2), torch.zeros(len(a))


def _cmd(angles, turn_first, v=0.8):
    st, pos, yaw = _state(angles, v)
    return mc.flag_step(st, pos, yaw, 0.02, mc.CommandParams(), turn_first)


def test_off_by_default_the_command_is_the_old_one():
    old = _cmd([0.9, -1.4, 0.2], None)
    assert torch.allclose(old, mc.flag_step(*_state([0.9, -1.4, 0.2]), 0.02, mc.CommandParams()))
    assert old[0, 0] > 0 and old[1, 0] != 0                       # far off the flag and still walking: that is what the cell changes


def test_far_off_turns_in_place_and_near_walks_with_a_small_wz():
    out = _cmd([0.9, -1.4, 0.2, -0.3, 0.6], 0.5)
    assert torch.allclose(out[0, :2], torch.zeros(2)) and out[0, 2] == pytest.approx(0.9)       # 0.9 rad > 0.5: in place, wz = clip(angle)
    assert torch.allclose(out[1, :2], torch.zeros(2)) and out[1, 2] == pytest.approx(-1.0)      # clip at flag_wz_clip, sign follows the side
    for row, angle in ((2, 0.2), (3, -0.3)):                                                      # inside the threshold: walk, direction x v, wz = angle
        assert torch.linalg.norm(out[row, :2]) == pytest.approx(0.8, abs=1e-5) and out[row, 2] == pytest.approx(angle, abs=1e-5)
    assert torch.allclose(out[4, :2], torch.zeros(2)) and out[4, 2] == pytest.approx(0.6)       # 0.6 > 0.5


def test_the_threshold_is_the_boundary_and_slow_spin_envs_are_not_touched():
    inside, outside = _cmd([0.49], 0.5), _cmd([0.51], 0.5)
    assert torch.linalg.norm(inside[0, :2]) > 0.5 and torch.linalg.norm(outside[0, :2]) == 0
    st, pos, yaw = _state([1.2, 1.2], v=0.1)                       # v < flag_spin_threshold: the spin branch (0, 0, spin_wz) stays
    st.spin_wz[:] = 0.7
    out = mc.flag_step(st, pos, yaw, 0.02, mc.CommandParams(), 0.5)
    assert torch.allclose(out[:, :2], torch.zeros(2, 2)) and torch.allclose(out[:, 2], torch.full((2,), 0.7))


def test_contract_accepts_the_turn_form_only_when_the_cell_is_on():
    p = mc.CommandParams()
    kw = dict(vmax=1.0, spin_threshold=p.flag_spin_threshold, spin_wz=p.flag_spin_wz, wz_clip=p.flag_wz_clip)
    c = torch.tensor([[0.0, 0.0, 1.0], [0.0, 0.0, 0.6]])
    on = flag_contract_bad(c, turn_first=True, **kw)
    assert not on.any()
    # spin_wz is 1.2 >= wz_clip 1.0, so the turn form is already inside the old domain: the cell must not widen it past wz_clip
    assert flag_contract_bad(torch.tensor([[0.0, 0.0, 1.1]]), turn_first=True, **kw).item() is False
    assert flag_contract_bad(torch.tensor([[0.0, 0.0, 1.3]]), turn_first=True, **kw).item() is True
    assert flag_contract_bad(torch.tensor([[0.3, 0.0, 1.0]]), turn_first=True, **kw).item() is False   # an ordinary walking form


def test_the_real_command_stream_stays_inside_the_contract_with_the_cell_on():
    n = 512
    gen = mc.make_generator(5)
    torch.manual_seed(5)
    p = mc.CommandParams()
    st = mc.FlagState.new(torch.rand(n, 4, 2) * 6.0 - 3.0)
    pos, yaw = torch.rand(n, 2) * 6.0 - 3.0, torch.rand(n) * 6.28 - 3.14
    mc.flag_resample(st, torch.arange(n), gen, p)
    bad = 0
    for _ in range(200):
        c = mc.flag_step(st, pos, yaw, 0.02, p, 0.5)
        bad += int(flag_contract_bad(c, vmax=p.flag_vmax, spin_threshold=p.flag_spin_threshold, spin_wz=p.flag_spin_wz,
                                     wz_clip=p.flag_wz_clip, turn_first=True).sum())
        yaw = yaw + 0.02 * c[:, 2]
        pos = pos + 0.02 * mc.world_cmd_step(yaw, c[:, :2])
    assert bad == 0


def test_the_plan_cell_is_on_the_e2_row_only_and_reaches_the_stage():
    plan = EX42Plan.load(PLAN)
    cells = {r["id"]: r.get("flag_turn_first_rad") for r in plan.document["stages"]}
    assert cells["E2"] == 0.5 and cells["E1F"] is None and cells["E1"] is None
    scopes = {r["id"]: r.get("flag_turn_first_scope") for r in plan.document["stages"]}
    assert scopes["E2"] == "first" and scopes["E1F"] is None and scopes["E1"] is None
    source = te.load_ex42_stage_zero_source(plan)
    for stage_id, want in (("E2", 0.5), ("E1F", None)):
        stage = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id=stage_id).stages[0]
        assert stage.flag_turn_first_rad == want


@pytest.mark.parametrize("bad", [0.0, -1.0, 4.0, True, "0.5", float("nan")])
def test_a_bad_cell_value_is_refused(bad):
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    next(r for r in plan.document["stages"] if r["id"] == "E2")["flag_turn_first_rad"] = bad      # the loaded document, in memory only
    with pytest.raises(ValueError, match="flag_turn_first_rad"):
        te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")


def test_turning_mask_matches_the_branch():
    st, pos, yaw = _state([0.0, 0.3, 0.9, -1.2])
    mc.flag_step(st, pos, yaw, 0.02, mc.CommandParams(), 0.5)
    assert st.turning.tolist() == [False, False, True, True]
    st2, pos2, yaw2 = _state([0.9])
    mc.flag_step(st2, pos2, yaw2, 0.02, mc.CommandParams(), None)
    assert st2.turning.tolist() == [False]


def test_log_lines_start_and_fraction(capsys):
    """The start line says the cell is on (or off) and the 50-update line carries flag_turn_fraction from the term's counters."""
    from types import SimpleNamespace
    from foothold_s2.runners.start_runner import StartRunner

    class Term:                                       # the real term needs Kit; its counters are two floats
        _turn_sum, _turn_cnt = 3.0, 12.0

        def flag_turn_summary(self):
            frac, count = self._turn_sum / self._turn_cnt, self._turn_cnt
            self._turn_sum = self._turn_cnt = 0.0
            return (stage.flag_turn_first_rad or None), frac, count
    stage = SimpleNamespace(flag_turn_first_rad=0.5)
    term = Term()
    runner = SimpleNamespace(disable_logs=False, _command_term=lambda: term)
    StartRunner._flag_turn_log(runner, 7)           # first update: start line only (not a multiple of 50)
    StartRunner._flag_turn_log(runner, 8)           # nothing
    term._turn_sum, term._turn_cnt = 3.0, 12.0
    StartRunner._flag_turn_log(runner, 50)
    out = capsys.readouterr().out.splitlines()
    assert out == ["EX42_FLAG_TURN_FIRST where=start rad=0.5 scope=all",                                        # the fake term has no split record: scope all, zeros
                   "EX42_FLAG_TURN_FIRST it=50 rad=0.5 flag_turn_fraction=0.2500 steps=12 scope=all first_flag_fraction=0.0000 first_flag_steps=0 later_flags_fraction=0.0000 later_flags_steps=0"]
    stage.flag_turn_first_rad = None
    term._turn_sum, term._turn_cnt = 0.0, 1.0
    runner2 = SimpleNamespace(disable_logs=False, _command_term=lambda: term)
    StartRunner._flag_turn_log(runner2, 1)
    assert capsys.readouterr().out.strip() == "EX42_FLAG_TURN_FIRST where=start rad=off"


# ---- 2026-11-18: flag_turn_first_scope (first | all): turn the body first toward the FIRST flag only, then walk straight through the next ones

def _two_flags(second_idx, angle=1.0, v=0.8):
    """One robot at the origin facing +x; both flags 3 m away at bearing `angle`; the robot is already heading for flag number `second_idx`."""
    flags = torch.tensor([[3.0 * math.cos(angle), 3.0 * math.sin(angle)]] * 2)[None]
    st = mc.FlagState.new(flags)
    st.v[:] = v
    st.idx[:] = second_idx
    return st, torch.zeros(1, 2), torch.zeros(1)


def test_scope_first_turns_in_place_on_the_first_flag_and_walks_straight_toward_the_second_at_the_same_angle():
    p = mc.CommandParams()
    first = mc.flag_step(*_two_flags(0), 0.02, p, 0.5, "first")
    assert torch.allclose(first[0, :2], torch.zeros(2)) and first[0, 2] == pytest.approx(1.0)      # 1.0 rad off the first flag: in place
    second = mc.flag_step(*_two_flags(1), 0.02, p, 0.5, "first")
    assert torch.linalg.norm(second[0, :2]) == pytest.approx(0.8, abs=1e-5) and second[0, 2] == pytest.approx(1.0)   # 1.0 rad off the second: straight + small wz
    assert second[0, 0] > 0 and second[0, 1] > 0                                                      # direction x v toward the flag, not zero
    again = mc.flag_step(*_two_flags(1), 0.02, p, 0.5, "all")                                          # all = today's behaviour: the second flag turns in place too
    assert torch.allclose(again[0, :2], torch.zeros(2))


def test_scope_first_keeps_the_backoff_and_slow_spin_branches_and_the_record_splits_first_and_later():
    p = mc.CommandParams()
    st, pos, yaw = _two_flags(1)
    st.backoff_left[:] = 1.0
    st.backoff_v[:] = 0.2
    st.passed[:] = 1
    out = mc.flag_step(st, pos, yaw, 0.02, p, 0.5, "first")
    assert out[0, 2] == 0.0 and not bool(st.turning.any())                                            # backing off: wz 0, no turn record
    st, pos, yaw = _two_flags(1, v=0.1)
    st.spin_wz[:] = 0.7
    out = mc.flag_step(st, pos, yaw, 0.02, p, 0.5, "first")
    assert torch.allclose(out[0], torch.tensor([0.0, 0.0, 0.7]))                                       # v < 0.3 spin branch as before
    st, pos, yaw = _two_flags(0)
    mc.flag_step(st, pos, yaw, 0.02, p, 0.5, "first")
    assert bool(st.turning[0]) and bool(st.turning_first[0])
    st, pos, yaw = _two_flags(1)
    mc.flag_step(st, pos, yaw, 0.02, p, 0.5, "first")
    assert not bool(st.turning[0]) and not bool(st.turning_first[0])
    with pytest.raises(ValueError, match="turn_scope"):
        mc.flag_step(*_two_flags(0), 0.02, p, 0.5, "second")


def test_the_real_e2_plan_row_turns_scope_first_on_and_a_bad_scope_is_refused():
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    stage = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2").stages[0]
    assert stage.flag_turn_first_rad == 0.5 and stage.flag_turn_first_scope == "first"
    e1f = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1F").stages[0]
    assert e1f.flag_turn_first_rad is None and e1f.flag_turn_first_scope == "all"
    for bad in ("second", "", True, 1):
        next(r for r in plan.document["stages"] if r["id"] == "E2")["flag_turn_first_scope"] = bad
        with pytest.raises(ValueError, match="flag_turn_first_scope"):
            te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")


def test_the_real_term_reads_the_scope_from_the_running_row_and_the_log_line_splits_first_and_later_flags(monkeypatch, capsys):
    from dataclasses import replace

    from foothold_s2.runners import start_runner as sr
    from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

    command, runtime, _ = e1f_term(monkeypatch, {}, n=64)
    assert command._flag_turn_first_scope() == "all" and command._flag_turn_first_rad() is None           # the E1F row: off
    runtime.plan.stages[0] = replace(runtime.plan.stages[0], flag_turn_first_rad=0.5, flag_turn_first_scope="first")
    assert command._flag_turn_first_scope() == "first" and command._flag_turn_first_rad() == 0.5
    command._turn_first_sum, command._turn_first_cnt, command._turn_rest_sum, command._turn_rest_cnt = 30.0, 40.0, 0.0, 60.0
    command._turn_sum, command._turn_cnt = 30.0, 100.0

    class Fix:
        disable_logs = False

        def _command_term(self):
            return command

    sr.StartRunner._flag_turn_log(Fix(), 50)
    out = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_FLAG_TURN_FIRST")]
    assert out[0] == "EX42_FLAG_TURN_FIRST where=start rad=0.5 scope=first"
    assert out[1] == ("EX42_FLAG_TURN_FIRST it=50 rad=0.5 flag_turn_fraction=0.3000 steps=100 scope=first "
                      "first_flag_fraction=0.7500 first_flag_steps=40 later_flags_fraction=0.0000 later_flags_steps=60")


# ---- the official flag eval (ex42_flag_eval) reads the same cell: --flag-turn-first off (default, as judged so far) | plan (the E2 row)

def test_eval_resolver_off_by_default_and_plan_reads_the_real_e2_row_and_refuses_a_silent_off():
    from foothold_s2.eval import ex42_flag_turn_first as ft

    plan = EX42Plan.load(PLAN)
    assert ft.resolve("off", plan.document) is None
    assert ft.resolve("plan", plan.document) == {"rad": 0.5, "scope": "first"}
    with pytest.raises(ValueError, match="no valid flag_turn_first_rad"):
        ft.resolve("plan", plan.document, "E1F")                                  # a row without the cell: an error, never a silent off
    with pytest.raises(ValueError, match="must be one of"):
        ft.resolve("both", plan.document)


def test_eval_path_with_the_flag_spin_threshold_0_turns_first_only_on_the_first_flag(monkeypatch):
    from foothold_s2.eval import ex42_flag_turn_first as ft
    from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

    command, _runtime, _ = e1f_term(monkeypatch, {}, n=64)
    assert command._flag_turn_first_rad() is None and command._flag_turn_first_scope() == "all"             # no override: the eval as judged so far
    command.flag_turn_first_override = ft.resolve("plan", EX42Plan.load(PLAN).document)                     # what ex42_flag_eval does with --flag-turn-first plan
    rad, scope = command._flag_turn_first_rad(), command._flag_turn_first_scope()
    assert (rad, scope) == (0.5, "first")
    p = mc.CommandParams(flag_spin_threshold=0.0, flag_vmax=1.0)                                            # the eval's params (ex42_flag_eval sets the threshold to 0)
    first = mc.flag_step(*_two_flags(0), 0.02, p, rad, scope)
    second = mc.flag_step(*_two_flags(1), 0.02, p, rad, scope)
    assert torch.allclose(first[0, :2], torch.zeros(2)) and first[0, 2] == pytest.approx(1.0)               # 1.0 rad off the first flag: turn only
    assert torch.linalg.norm(second[0, :2]) == pytest.approx(0.8, abs=1e-5)                                  # 1.0 rad off the second: straight
    command.flag_turn_first_override = None
    assert command._flag_turn_first_rad() is None


def test_the_eval_script_wires_the_flag_turn_first_option_into_the_term_and_the_receipt():
    import ast

    src = (Path(__file__).resolve().parents[1] / "eval" / "ex42_flag_eval.py").read_text(encoding="utf-8")
    ast.parse(src)
    for needle in ('"--flag-turn-first"', 'default="off"', "ex42_flag_turn_first.resolve(args.flag_turn_first, plan, args.flag_turn_first_row)",
                   "term.flag_turn_first_override = turn_first", '"flag_turn_first": turn_first'):
        assert needle in src, needle
