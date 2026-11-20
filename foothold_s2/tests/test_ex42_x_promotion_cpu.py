"""CPU tests for the plan-switched level-up rule of the sparse kind columns (x progress instead of max_dist). Default: off, today's rule untouched."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
import torch

from foothold_s2.curriculum import ex41, rules

ROOT = Path(__file__).resolve().parents[2]


def _old_judge(max_dist, cmd_sum, size_x=8.0, resample_s=4.0, factor=0.9, eps=1.0e-9):
    """The pre-change body of judge_free, copied here as the reference."""
    norm = torch.linalg.norm(cmd_sum, dim=1)
    out = torch.zeros(len(max_dist), dtype=torch.long)
    active = norm > eps
    up = active & (max_dist > torch.as_tensor(size_x, dtype=max_dist.dtype) / 2.0)
    down = active & (max_dist < 0.5 * norm * resample_s * factor) & ~up
    out[up] = 1
    out[down] = -1
    return out


def test_without_the_new_arguments_judge_free_is_the_old_function_on_a_grid_of_inputs():
    g = torch.Generator().manual_seed(0)
    for size in (8.0, 12.0, torch.tensor([8.0, 12.0, 9.0, 12.0, 8.0, 12.0])):
        d, c = torch.rand(6, generator=g) * 12, torch.randn(6, 2, generator=g)
        c[2] = 0.0
        assert torch.equal(rules.judge_free(d, c, size_x=size), _old_judge(d, c, size_x=size))
        assert torch.equal(rules.judge_free(d, c, size_x=size, progress_x=None, x_mask=None), _old_judge(d, c, size_x=size))


def test_a_masked_env_levels_up_on_x_progress_and_an_unmasked_env_keeps_max_dist():
    d = torch.tensor([7.0, 7.0, 7.0, 3.0])                         # 12 m tile: the old line is 6 m
    x = torch.tensor([2.0, 7.0, 2.0, 2.0])                         # the masked env 0 wandered sideways (far but not forward)
    m = torch.tensor([True, True, False, True])
    c = torch.tensor([[1.0, 0.0]] * 4) * 3.0                        # the old down line is 0.5 x 3 x 4 x 0.9 = 5.4 m: 7 m holds, 3 m goes down
    out = rules.judge_free(d, c, size_x=12.0, progress_x=x, x_mask=m)
    assert out.tolist()[:3] == [0, 1, 1]                           # env 0: no up (x 2 < 6) · env 1: up · env 2 unmasked: up by max_dist 7 > 6
    assert rules.judge_free(d, c, size_x=12.0).tolist()[0] == 1    # without the rule env 0 would have levelled up
    assert out.tolist()[3] == -1                                   # a masked env that went nowhere still goes down by the old line
    assert rules.judge_free(d, c, size_x=12.0, progress_x=x, x_mask=m, x_fraction=0.1).tolist()[0] == 1       # a 10 % line is 1.2 m: x 2 clears it


def test_forward_only_leaves_a_sideways_or_backward_command_episode_out_of_the_masked_columns():
    d, x = torch.tensor([7.0, 7.0, 7.0, 0.1]), torch.tensor([7.0, 7.0, 7.0, 0.1])
    m = torch.tensor([True, True, True, True])
    c = torch.tensor([[4.0, 0.0], [0.0, 4.0], [-4.0, 0.0], [4.0, 0.0]])
    out = rules.judge_free(d, c, size_x=12.0, progress_x=x, x_mask=m, forward_only=True)
    assert out.tolist() == [1, 0, 0, -1]                           # sideways and backward: not judged · the forward one that went nowhere still goes down
    assert rules.judge_free(d, c, size_x=12.0, progress_x=x, x_mask=m).tolist()[1:3] == [1, 1]


@pytest.mark.parametrize("bad", [dict(x_mask=None), dict(x_mask=torch.ones(2, dtype=torch.bool), x_fraction=0.0), dict(x_mask=torch.ones(2, dtype=torch.bool), x_fraction=1.5)])
def test_the_x_rule_refuses_a_missing_mask_or_a_fraction_outside_zero_one(bad):
    with pytest.raises(ValueError):
        rules.judge_free(torch.ones(2), torch.ones(2, 2), size_x=12.0, progress_x=torch.ones(2), **bad)


def test_the_plan_cell_is_absent_by_default_and_validated_when_present():
    none = types.SimpleNamespace(document={})
    assert ex41.terrain_promotion_cell(none) is None
    good = types.SimpleNamespace(document={"terrain_promotion": {"x_progress_kinds": ["B/beam", "B/gap"]}})
    assert ex41.terrain_promotion_cell(good) == {"x_progress_kinds": ("B/beam", "B/gap"), "x_progress_fraction": 0.5, "forward_only": False, "x_fall_down": False}
    for cell in ({}, {"x_progress_kinds": []}, {"x_progress_kinds": ["beam"]}, {"x_progress_kinds": ["B/beam", "B/beam"]},
                 {"x_progress_kinds": ["B/beam"], "x_progress_fraction": 0}, {"x_progress_kinds": ["B/beam"], "forward_only": 1},
                 {"x_progress_kinds": ["B/beam"], "extra": 1}, ["B/beam"]):
        with pytest.raises(ValueError):
            ex41.terrain_promotion_cell(types.SimpleNamespace(document={"terrain_promotion": cell}))


def _env_cfg():
    return types.SimpleNamespace(scene=types.SimpleNamespace(terrain=types.SimpleNamespace(max_init_terrain_level=None)),
                                 curriculum=types.SimpleNamespace(),
                                 commands=types.SimpleNamespace(base_velocity=types.SimpleNamespace(track_x_progress=False)))


@pytest.fixture
def fake_isaac(monkeypatch):
    mod = types.ModuleType("isaaclab.managers")
    mod.CurriculumTermCfg = lambda func, params: types.SimpleNamespace(func=func, params=params)
    monkeypatch.setitem(sys.modules, "isaaclab", types.ModuleType("isaaclab"))
    monkeypatch.setitem(sys.modules, "isaaclab.managers", mod)


def test_registration_without_the_cell_is_exactly_the_old_one(fake_isaac):
    cfg = _env_cfg()
    receipt = ex41.prepare_terrain_cfg(cfg, types.SimpleNamespace(document={}), initial_policy="performance", initial_level_cap=5)
    assert cfg.curriculum.terrain_levels.params == {"command_name": "base_velocity", "resample_s": 4., "world_frame": True,
                                                    "initial_policy": "performance", "initial_level_cap": 5}
    assert cfg.commands.base_velocity.track_x_progress is False
    assert set(receipt) == {"policy", "max_init_terrain_level", "promotion_enabled", "registered_performance_term", "world_frame", "initial_policy", "initial_level_cap"}


def test_registration_with_the_cell_adds_the_three_parameters_the_x_tracking_and_the_receipt(fake_isaac):
    cfg = _env_cfg()
    plan = types.SimpleNamespace(document={"terrain_promotion": {"x_progress_kinds": ["B/beam"], "x_progress_fraction": 0.5, "forward_only": True}})
    receipt = ex41.prepare_terrain_cfg(cfg, plan, initial_policy="performance", initial_level_cap=5)
    p = cfg.curriculum.terrain_levels.params
    assert p["x_progress_kinds"] == ("B/beam",) and p["x_progress_fraction"] == 0.5 and p["x_progress_forward_only"] is True
    assert cfg.commands.base_velocity.track_x_progress is True and receipt["x_progress_promotion"]["forward_only"] is True


def _term(max_x, ep_steps=1):
    return types.SimpleNamespace(max_x=max_x, ep_steps=torch.full((4,), float(ep_steps)))


def test_the_runtime_mask_follows_the_column_of_each_env_and_refuses_what_it_cannot_check():
    table = [{"family": "A", "kind": "stones"}, {"family": "B", "kind": "beam"}, {"family": "B", "kind": "gap"}]
    env = types.SimpleNamespace(_ex42_column_table=table)
    terrain = types.SimpleNamespace(terrain_types=torch.tensor([0, 1, 2, 1]))
    ids = torch.arange(4)
    rule = ex41.x_progress_rule(env, terrain, _term(torch.arange(4.0)), ids, ("B/beam",), 0.5, False)
    assert rule["x_mask"].tolist() == [False, True, False, True] and rule["progress_x"].tolist() == [0.0, 1.0, 2.0, 3.0]
    with pytest.raises(ValueError, match="not in the mesh"):
        ex41.x_progress_rule(env, terrain, _term(torch.zeros(4)), ids, ("B/nothing",), 0.5, False)
    with pytest.raises(ValueError, match="not in the mesh"):
        ex41.x_progress_rule(env, terrain, _term(None), ids, ("B/beam",), 0.5, False)                      # the command term does not track x
    early = types.SimpleNamespace()                                                                        # first reset: no table yet, no episode has run
    assert ex41.x_progress_rule(early, terrain, _term(torch.zeros(4), ep_steps=0), ids, ("B/beam",), 0.5, False) == {}
    with pytest.raises(ValueError, match="column table"):
        ex41.x_progress_rule(early, terrain, _term(torch.zeros(4), ep_steps=3), ids, ("B/beam",), 0.5, False)


def test_default_off_in_the_sources():
    text = (ROOT / "foothold_s2/commands/mixed_command.py").read_text(encoding="utf-8")
    assert "track_x_progress: bool = False" in text and "if getattr(cfg, \"track_x_progress\", False) else None" in text
    assert "        if self.max_x is not None:\n            self.max_x = torch.maximum(" in text                 # nothing extra is computed when off
    entry = (ROOT / "foothold_s2/scripts/ex42_training_entry.py").read_text(encoding="utf-8")
    assert "x_progress" not in entry and entry.count("terrain_promotion") == 4                                # the training entry only carries the plan cell through the stage-zero view (the stage start path)
    assert "terrain_promotion" not in (ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8")


def test_the_real_plan_loader_accepts_the_cell_and_the_plan_sha_moves(tmp_path):
    """The cell is an ordinary top-level key of the plan file: EX42Plan.load takes it, and (being a plan edit) it changes the plan sha256."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    table = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    for sibling in table.parent.glob("*.yaml"):
        (tmp_path / sibling.name).write_bytes(sibling.read_bytes())
    base = EX42Plan.load(tmp_path / table.name)
    assert ex41.terrain_promotion_cell(base) is None
    with (tmp_path / table.name).open("a", encoding="utf-8") as f:
        f.write("\nterrain_promotion:\n  x_progress_kinds: [B/beam, B/gap]\n  x_progress_fraction: 0.5\n  forward_only: false\n")
    changed = EX42Plan.load(tmp_path / table.name)
    assert ex41.terrain_promotion_cell(changed)["x_progress_kinds"] == ("B/beam", "B/gap") and changed.sha256 != base.sha256


def test_a_fall_short_of_the_x_fraction_steps_a_masked_env_down_and_nothing_else_changes():
    d = torch.tensor([7.0, 7.0, 7.0, 7.0, 7.0, 7.0])               # 12 m tile: the up line is 6 m of x progress, the old down line (command 3 m/s) is 5.4 m of distance
    x = torch.tensor([2.0, 2.0, 2.0, 7.0, 2.0, 2.0])               # env 0..2 wandered sideways (7 m of distance, 2 m of x); env 3 got 7 m of x
    m = torch.tensor([True, True, False, True, True, True])
    fell = torch.tensor([True, False, True, True, True, True])
    c = torch.tensor([[1.0, 0.0]] * 5 + [[0.0, 1.0]]) * 3.0        # env 5: a sideways command episode
    out = rules.judge_free(d, c, size_x=12.0, progress_x=x, x_mask=m, fell=fell, forward_only=True)
    assert out.tolist() == [-1, 0, 1, 1, -1, 0]                    # fell short -> down · did not fall -> stays · unmasked: old rule (up by distance) · cleared the line -> up even though it fell · sideways: not judged
    same = rules.judge_free(d, c, size_x=12.0, progress_x=x, x_mask=m, forward_only=True)
    assert same.tolist() == [0, 0, 1, 1, 0, 0]                     # without fell the function is the one before this change
    assert torch.equal(rules.judge_free(d, c, size_x=12.0, fell=fell), rules.judge_free(d, c, size_x=12.0))      # fell is ignored without progress_x (no mask)


def test_the_plan_cell_takes_x_fall_down_only_as_a_bool_and_defaults_to_off():
    base = {"x_progress_kinds": ["B/beam"], "x_progress_fraction": 0.5, "forward_only": True}
    off = ex41.terrain_promotion_cell(types.SimpleNamespace(document={"terrain_promotion": base}))
    on = ex41.terrain_promotion_cell(types.SimpleNamespace(document={"terrain_promotion": {**base, "x_fall_down": True}}))
    assert off["x_fall_down"] is False and on["x_fall_down"] is True
    with pytest.raises(ValueError, match="x_fall_down"):
        ex41.terrain_promotion_cell(types.SimpleNamespace(document={"terrain_promotion": {**base, "x_fall_down": 1}}))


def test_the_runtime_rule_carries_the_termination_flags_only_when_asked_and_registration_announces_it(fake_isaac):
    table = [{"family": "A", "kind": "stones"}, {"family": "B", "kind": "beam"}]
    manager = types.SimpleNamespace(terminated=torch.tensor([True, False, True, False]))
    env = types.SimpleNamespace(_ex42_column_table=table, termination_manager=manager)
    terrain = types.SimpleNamespace(terrain_types=torch.tensor([0, 1, 1, 1]))
    ids = torch.arange(4)
    assert "fell" not in ex41.x_progress_rule(env, terrain, _term(torch.arange(4.0)), ids, ("B/beam",), 0.5, True)
    assert ex41.x_progress_rule(env, terrain, _term(torch.arange(4.0)), ids, ("B/beam",), 0.5, True, True)["fell"].tolist() == [True, False, True, False]
    with pytest.raises(ValueError, match="termination manager"):
        ex41.x_progress_rule(types.SimpleNamespace(_ex42_column_table=table), terrain, _term(torch.arange(4.0)), ids, ("B/beam",), 0.5, True, True)
    cfg = _env_cfg()
    plan = types.SimpleNamespace(document={"terrain_promotion": {"x_progress_kinds": ["B/beam"], "x_progress_fraction": 0.5, "forward_only": True, "x_fall_down": True}})
    ex41.prepare_terrain_cfg(cfg, plan, initial_policy="performance", initial_level_cap=5)
    assert cfg.curriculum.terrain_levels.params["x_progress_fall_down"] is True
