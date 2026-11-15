import copy
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.nav import command_space as cs

PREP = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


@pytest.fixture(scope="module")
def slots():
    return cs.slots_from_prep(PREP)


def _by(slots, name):
    return next(s for s in slots if s.name == name)


def test_slots_are_read_from_the_prep_table_with_the_w55_sign_rules(slots):
    from foothold_s2.commands.mixed_core import EX39_SLOTS

    assert tuple(s.name for s in slots) == EX39_SLOTS and len(slots) == 13
    r = yaml.safe_load(PREP.read_text(encoding="utf-8"))["stage_zero"]["ranges"]
    assert _by(slots, "forward").lo == (r["forward_vx"][0], 0, 0) and _by(slots, "forward").hi == (r["forward_vx"][1], 0, 0)
    wl, wr = _by(slots, "walk_left"), _by(slots, "walk_right")
    assert (wl.lo[2], wl.hi[2]) == (0.2, 1.0) and (wr.lo[2], wr.hi[2]) == (-1.0, -0.2)
    assert (_by(slots, "diag_back_right").lo, _by(slots, "diag_back_right").hi) == ((-0.6, -0.5, 0), (-0.3, -0.2, 0))
    assert (_by(slots, "side_right").lo[1], _by(slots, "side_right").hi[1]) == (-0.6, -0.2)


def test_changing_a_range_in_the_prep_changes_the_slots(tmp_path, slots):
    d = yaml.safe_load(PREP.read_text(encoding="utf-8"))
    d["stage_zero"]["ranges"]["side_vy_abs"] = [0.25, 0.55]
    p = tmp_path / "p.yaml"; p.write_text(yaml.safe_dump(d))
    s = _by(cs.slots_from_prep(p), "side_left")
    assert (s.lo[1], s.hi[1]) == (0.25, 0.55)


def _one(space, v, pose=None):
    return space.step(np.array([v], dtype=float), None if pose is None else np.array([pose], dtype=float))


def test_clip_mode_hand_values(slots):
    sp = cs.CommandSpace(slots, "clip")
    a = _one(sp, (0.7, 0.1, 0.3))
    assert np.allclose(a.cmd[0, :3], (0.7, 0.1, 0.3)) and not a.modified[0]
    sp.reset()
    a = _one(sp, (1.4, 0.9, 2.0))
    assert np.allclose(a.cmd[0, :3], (1.0, 0.6, 1.5)) and a.modified[0]
    sp.reset()
    a = _one(sp, (-2.0, -0.9, -2.0))
    assert np.allclose(a.cmd[0, :3], (-1.3, -0.6, -1.5))


def test_project_mode_moves_the_plan_example_to_walking_left(slots):
    sp = cs.CommandSpace(slots, "project")
    a = _one(sp, (0.7, 0.1, 0.3))
    assert np.allclose(a.cmd[0, :3], (0.7, 0.0, 0.3)) and a.modified[0] and not a.stand[0]
    sp.reset()
    a = _one(sp, (0.0, 0.0, 0.9))                       # 제자리 회전 좌
    assert np.allclose(a.cmd[0, :3], (0.0, 0.0, 0.9)) and not a.modified[0]
    sp.reset()
    a = _one(sp, (0.0, 0.0, -0.1))                      # 제자리 우 하한 -0.3 보다 작음 -> 정지와 가장 가까움
    assert a.stand[0] and np.allclose(a.cmd[0, :3], 0)


def test_vx_cap_applies_in_every_mode(slots):
    for mode, act in (("clip", (1.4, 0, 0)), ("project", (1.4, 0, 0)), ("slot", (0, 1.0, 0.0))):
        sp = cs.CommandSpace(slots, mode)
        a = sp.step(np.array([act], dtype=float))
        assert a.cmd[0, 0] == pytest.approx(1.0), mode


def test_slot_mode_hand_values_and_bad_index(slots):
    sp = cs.CommandSpace(slots, "slot")
    names = [s.name for s in slots]
    a = sp.step(np.array([[names.index("walk_left"), 0.5, 0.9]]))
    assert np.allclose(a.cmd[0, :3], (0.3 + 0.5 * 0.5, 0.0, 0.2 + 0.9 * 0.8))
    sp.reset()
    a = sp.step(np.array([[names.index("diag_back_right"), 1.0, 0.0]]))
    assert np.allclose(a.cmd[0, :3], (-0.3, -0.5, 0.0))
    sp.reset()
    a = sp.step(np.array([[names.index("side_left"), 0.25, 0.9]]))
    assert np.allclose(a.cmd[0, :3], (0.0, 0.2 + 0.25 * 0.4, 0.0))
    sp.reset()
    a = sp.step(np.array([[99, 0.5, 0.5]]))
    assert a.modified[0]
    sp.reset()
    with pytest.raises(ValueError):
        sp.step(np.array([[0, 0.5]]))


def test_command_is_held_for_five_steps_and_the_applied_value_is_returned(slots):
    sp = cs.CommandSpace(slots, "clip")
    ticks, seen = [], []
    for k in range(11):
        a = sp.step(np.array([[0.1 * (k + 1), 0, 0]]))
        ticks.append(a.ticked); seen.append(round(float(a.cmd[0, 0]), 3))
        assert np.allclose(sp.last_applied, a.cmd)
    assert ticks == [True, False, False, False, False, True, False, False, False, False, True]
    assert seen == [0.1] * 5 + [0.6] * 5 + [1.0]
    sp.reset()
    assert sp.step(np.array([[0.5, 0, 0]])).ticked


def test_pose_switch_zeroes_the_last_two_columns_unless_active(slots):
    off = _one(cs.CommandSpace(slots, "clip", pose_active=False), (0.5, 0, 0), pose=(0.1, -0.2))
    assert np.array_equal(off.cmd[0, 3:], [0, 0]) and off.pose_masked[0]
    on = _one(cs.CommandSpace(slots, "clip", pose_active=True), (0.5, 0, 0), pose=(0.1, -0.2))
    assert np.allclose(on.cmd[0, 3:], [0.1, -0.2]) and not on.pose_masked[0]
    quiet = _one(cs.CommandSpace(slots, "clip"), (0.5, 0, 0))
    assert not quiet.pose_masked[0]


def test_near_zero_command_sets_stand_and_zeroes_it(slots):
    a = _one(cs.CommandSpace(slots, "clip"), (0.04, 0.02, -0.01))
    assert a.stand[0] and np.array_equal(a.cmd[0, :3], [0, 0, 0])
    b = _one(cs.CommandSpace(slots, "clip"), (0.2, 0, 0))
    assert not b.stand[0]


def test_bad_inputs_are_refused(slots):
    with pytest.raises(ValueError):
        cs.CommandSpace(slots, "nearest")
    sp = cs.CommandSpace(slots, "clip")
    with pytest.raises(ValueError):
        sp.step(np.array([[np.nan, 0, 0]]))
    with pytest.raises(ValueError):
        sp.step(np.array([[0.1, 0, 0]]), np.array([[0.0, 0.0, 0.0]]))
    with pytest.raises(ValueError):
        cs.slots_from_prep(PREP, "evaluation")
