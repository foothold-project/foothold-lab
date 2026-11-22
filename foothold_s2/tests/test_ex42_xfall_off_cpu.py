"""EX42_X_FALL_DOWN_OFF_KINDS (lead 2026-11-22 22:13): the fall step-down of terrain_promotion x_fall_down is taken off the named
columns only. Known answers: command 0.3 m/s forward for 20 s (summed command per resample 1.5 · old down below 0.5 x 1.5 x 4 x 0.9 = 2.7 m),
tile 8 m (up above x 4 m), distances 2.9 / 3.1 / 4.1 m with and without a fall, on a balance-beam column and a gap column."""
import types

import pytest
import torch

from foothold_s2.curriculum import ex41, rules

TABLE = [{"family": "A", "kind": "balance_beams"}, {"family": "A", "kind": "gaps"}, {"family": "A", "kind": "flat"}]
KINDS = ("A/balance_beams", "A/gaps")
DIST = [2.9, 3.1, 4.1, 2.9, 3.1, 4.1]
FELL = [True, True, True, False, False, False]


def _moves(col, monkeypatch, off=None):
    if off is None:
        monkeypatch.delenv("EX42_X_FALL_DOWN_OFF_KINDS", raising=False)
    else:
        monkeypatch.setenv("EX42_X_FALL_DOWN_OFF_KINDS", off)
    for attr in ("_announced", "_fall_off_announced"):
        if hasattr(ex41.x_progress_rule, attr):
            delattr(ex41.x_progress_rule, attr)
    n = len(DIST)
    env = types.SimpleNamespace(_ex42_column_table=TABLE, termination_manager=types.SimpleNamespace(terminated=torch.tensor(FELL)))
    terrain = types.SimpleNamespace(terrain_types=torch.full((n,), col, dtype=torch.long))
    term = types.SimpleNamespace(max_x=torch.tensor(DIST), ep_steps=torch.full((n,), 1000))
    ids = torch.arange(n)
    rule = ex41.x_progress_rule(env, terrain, term, ids, KINDS, 0.5, True, fall_down=True)
    cmd = torch.tensor([[1.5, 0.0]] * n)
    return rules.judge_free(torch.tensor(DIST), cmd, size_x=8.0, resample_s=4.0, **rule).tolist()


def test_default_unset_is_todays_rule(monkeypatch):
    # fall short of 4 m steps down; 4.1 m steps up even after a fall; no fall and no up = stay
    assert _moves(0, monkeypatch) == [-1, -1, 1, 0, 0, 1]
    assert _moves(1, monkeypatch) == [-1, -1, 1, 0, 0, 1]


def test_empty_value_is_todays_rule(monkeypatch):
    assert _moves(0, monkeypatch, "") == _moves(0, monkeypatch)


def test_beams_off_keeps_gaps(monkeypatch, capsys):
    assert _moves(0, monkeypatch, "A/balance_beams") == [0, 0, 1, 0, 0, 1]      # beam column: no fall step-down
    assert "EX42_X_FALL_DOWN_OFF where=start kinds=A/balance_beams columns=1/3" in capsys.readouterr().out
    assert _moves(1, monkeypatch, "A/balance_beams") == [-1, -1, 1, 0, 0, 1]     # gap column: unchanged


def test_old_down_still_applies_when_off(monkeypatch):
    global DIST
    keep = DIST
    try:
        DIST = [2.5] * 6                                                           # below 2.7 m: the legged_gym distance rule
        assert _moves(0, monkeypatch, "A/balance_beams") == [-1] * 6
    finally:
        DIST = keep


def test_unknown_kind_refused(monkeypatch):
    with pytest.raises(ValueError, match="outside terrain_promotion"):
        _moves(0, monkeypatch, "A/flat")
