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
    assert out == ["EX42_FLAG_TURN_FIRST where=start rad=0.5",
                   "EX42_FLAG_TURN_FIRST it=50 rad=0.5 flag_turn_fraction=0.2500 steps=12"]
    stage.flag_turn_first_rad = None
    term._turn_sum, term._turn_cnt = 0.0, 1.0
    runner2 = SimpleNamespace(disable_logs=False, _command_term=lambda: term)
    StartRunner._flag_turn_log(runner2, 1)
    assert capsys.readouterr().out.strip() == "EX42_FLAG_TURN_FIRST where=start rad=off"
