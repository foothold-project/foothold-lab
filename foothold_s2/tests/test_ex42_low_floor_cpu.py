"""CG:380: continuous L0~2 envs >= 30 % of the continuous envs (LowLevelFloor), and the boundary_log recorder
(learned_cells). The level update is Isaac Lab's installed update_env_origins; terrain objects are plain tensors. No Kit.
"""
from __future__ import annotations

import ast
import json
import math
import pathlib
import types

import pytest
import torch
import yaml

from foothold_s2 import ex42_learned_cells as lc
from foothold_s2.commands.mixed_core import EX39_SLOTS
from foothold_s2.terrains import ex42_exposure as ex

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
IMPORTER = pathlib.Path("/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_importer.py")
needs_isaac = pytest.mark.skipif(not IMPORTER.is_file(), reason="Isaac Lab source missing")
TABLE = [{"family": "A", "kind": f"c{i}"} for i in range(10)] + [{"family": "B", "kind": f"s{i}"} for i in range(4)]
SPEC = {"floors": {"continuous_low_level_floor": {"levels": [0, 2], "fraction_of_continuous": 0.30}}}


def _installed_update():
    tree = ast.parse(IMPORTER.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "update_env_origins")
    fn.decorator_list = []
    mod = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {"torch": torch}
    exec(compile(mod, str(IMPORTER), "exec"), ns)
    return ns["update_env_origins"]


def _terrain(num_envs=3072, start_level=5):
    cols = len(TABLE)
    t = types.SimpleNamespace(
        terrain_origins=torch.randn(10, cols, 3), max_terrain_level=10,
        terrain_levels=torch.full((num_envs,), start_level), terrain_types=torch.arange(num_envs) % cols,
        env_origins=torch.zeros(num_envs, 3))
    t.update_env_origins = types.MethodType(_installed_update(), t)
    return t


def _apply(terrain, floor=True):
    spec = ex.low_level_floor(SPEC, TABLE, "E1F") if floor else None
    return ex.apply_exposure(terrain, [1.0] * len(TABLE), [5] * len(TABLE), low_floor=spec,
                             generator=torch.Generator().manual_seed(0))


def _share_low(terrain):
    cont = torch.tensor([r["family"] == "A" for r in TABLE])[terrain.terrain_types]
    return float(((terrain.terrain_levels <= 2) & cont).sum() / cont.sum())


@needs_isaac
def test_the_floor_is_met_at_the_start_and_held_while_every_env_is_pushed_up():
    t = _terrain()
    receipt = _apply(t)
    assert receipt["low_level_floor"]["low_level_envs"] >= receipt["low_level_floor"]["required"] > 0
    g = torch.Generator().manual_seed(1)
    for _ in range(40):
        ids = torch.randperm(3072, generator=g)[:600]
        t.update_env_origins(ids, torch.ones(600, dtype=torch.bool), torch.zeros(600, dtype=torch.bool))
        assert _share_low(t) >= 0.30 - 1e-9
    assert t.low_level_floor.receipt()["reassigned_total"] > 0


@needs_isaac
def test_without_the_floor_the_same_pushing_empties_the_low_levels():
    t = _terrain()
    _apply(t, floor=False)
    g = torch.Generator().manual_seed(1)
    for _ in range(40):
        ids = torch.randperm(3072, generator=g)[:600]
        t.update_env_origins(ids, torch.ones(600, dtype=torch.bool), torch.zeros(600, dtype=torch.bool))
    assert _share_low(t) == 0.0                                            # the E1 behaviour the reviewer measured


@needs_isaac
def test_only_envs_that_are_being_reset_are_moved_and_non_continuous_columns_are_left_alone():
    t = _terrain()
    _apply(t)
    before_levels, before_types = t.terrain_levels.clone(), t.terrain_types.clone()
    ids = torch.arange(0, 3072, 7)
    t.update_env_origins(ids, torch.ones(len(ids), dtype=torch.bool), torch.zeros(len(ids), dtype=torch.bool))
    others = torch.ones(3072, dtype=torch.bool)
    others[ids] = False
    assert torch.equal(t.terrain_levels[others], before_levels[others])
    assert torch.equal(t.terrain_types, before_types)
    sparse = torch.tensor([r["family"] != "A" for r in TABLE])[t.terrain_types]
    assert bool((t.terrain_levels[sparse] == 5).all())                     # family B stays on its cap level


@needs_isaac
def test_a_shortfall_with_no_resetting_continuous_env_stays_visible_and_nothing_else_moves():
    t = _terrain()
    _apply(t)
    t.terrain_levels[:] = 5                                                 # everyone high again
    b_only = torch.nonzero(~torch.tensor([r["family"] == "A" for r in TABLE])[t.terrain_types]).flatten()[:20]
    moved = t.low_level_floor.enforce(b_only)
    assert moved == 0 and t.low_level_floor.last_deficit > 0


def _origin_share(terrain):
    """Independent of the floor object: match every env_origins row back to its terrain_origins level."""
    cont = torch.tensor([r["family"] == "A" for r in TABLE])[terrain.terrain_types]
    levels = []
    for env in range(terrain.env_origins.shape[0]):
        col = terrain.terrain_origins[:, int(terrain.terrain_types[env])]
        levels.append(int((col - terrain.env_origins[env]).abs().amax(dim=-1).argmin()))
    levels = torch.tensor(levels)
    return float(((levels <= 2) & cont).sum() / cont.sum()), levels


@needs_isaac
def test_the_floor_moves_the_real_origins_to_l0_2_cells_not_only_the_level_table():
    t = _terrain()
    _apply(t)
    g = torch.Generator().manual_seed(2)
    for _ in range(25):
        ids = torch.randperm(3072, generator=g)[:600]
        t.update_env_origins(ids, torch.ones(600, dtype=torch.bool), torch.zeros(600, dtype=torch.bool))
    share, origin_levels = _origin_share(t)
    assert share >= 0.30 - 1e-9
    assert bool((origin_levels == t.terrain_levels).all())                  # table and origin agree for every env
    receipt = t.low_level_floor.receipt()
    assert receipt["origin_low_level_envs"] >= receipt["origin_required"] > 0
    assert receipt["origin_level_table_mismatch"] == 0 and receipt["origin_unmatched_envs"] == 0
    assert math.isclose(receipt["origin_share_of_continuous"], share, abs_tol=1e-6)
    assert sum(receipt["origin_per_level_continuous"]) == receipt["continuous_envs"]


@needs_isaac
def test_a_floor_that_only_edits_the_level_table_is_caught_by_the_origin_receipt(monkeypatch):
    t = _terrain()
    _apply(t)
    t.low_level_floor.refresh = lambda ids: None                            # the fake floor: table moves, origin stays
    g = torch.Generator().manual_seed(3)
    for _ in range(25):
        ids = torch.randperm(3072, generator=g)[:600]
        t.update_env_origins(ids, torch.ones(600, dtype=torch.bool), torch.zeros(600, dtype=torch.bool))
    assert _share_low(t) >= 0.30 - 1e-9                                     # the level table claims the floor
    share, _ = _origin_share(t)
    receipt = t.low_level_floor.receipt()
    assert share < 0.30 and receipt["origin_share_of_continuous"] < 0.30    # the origins do not
    assert receipt["origin_level_table_mismatch"] > 0
    assert receipt["origin_low_level_envs"] < receipt["origin_required"]


def test_origins_outside_the_mesh_are_counted_as_unmatched_and_never_as_low():
    cols = len(TABLE)
    t = types.SimpleNamespace(terrain_origins=torch.randn(10, cols, 3), terrain_levels=torch.zeros(20, dtype=torch.long),
                              terrain_types=torch.zeros(20, dtype=torch.long), env_origins=torch.full((20, 3), 99.0))
    floor = ex.LowLevelFloor(t, ex.low_level_floor(SPEC, TABLE, "E1F"), lambda ids: None)
    r = floor.origin_counts()
    assert r["origin_unmatched_envs"] == 20 and r["origin_low_level_envs"] == 0 and r["origin_share_of_continuous"] == 0.0


def test_floor_spec_comes_from_the_stage_row_and_is_validated():
    assert ex.low_level_floor({"floors": {}}, TABLE, "E1") is None
    spec = ex.low_level_floor(SPEC, TABLE, "E1F")
    assert spec["levels"] == [0, 2] and spec["fraction"] == 0.30 and spec["continuous"][0] and not spec["continuous"][-1]
    for bad in ({"levels": [2, 0], "fraction_of_continuous": 0.3}, {"levels": [0, 2], "fraction_of_continuous": 1.2},
                {"levels": [0], "fraction_of_continuous": 0.3}, {"levels": [0, 2.0], "fraction_of_continuous": 0.3}):
        with pytest.raises(ValueError, match="malformed"):
            ex.low_level_floor({"floors": {"continuous_low_level_floor": bad}}, TABLE, "E1F")
    with pytest.raises(ValueError, match="family A"):
        ex.low_level_floor(SPEC, [{"family": "B", "kind": "x"}], "E1F")


def test_the_plan_holds_the_floor_from_e1f_on_and_not_before():
    stages = yaml.safe_load(PLAN.read_text())["stages"]
    ids = [r["id"] for r in stages]
    first = ids.index("E1F")
    for index, row in enumerate(stages):
        spec = row["terrain"]["floors"].get("continuous_low_level_floor")
        assert (spec is not None) == (index >= first), row["id"]
        if spec is not None:
            assert spec["levels"] == [0, 2] and math.isclose(spec["fraction_of_continuous"], 0.30)


# ---- boundary_log recorder -------------------------------------------------------------------------------------
def _recorder(n=8, start=0):
    return lc.LearnedCellRecorder(n, 4, EX39_SLOTS, stage_id="E1F", plan_sha256="a" * 64, start_iteration=start)


def _slot(name):
    return EX39_SLOTS.index(name)


def test_finished_episodes_are_counted_by_column_band_group_and_assigned_mode_from_the_pre_step_state():
    r = _recorder()
    levels = torch.tensor([0, 2, 3, 5, 6, 9, 1, 4])
    types = torch.tensor([0, 0, 1, 1, 2, 2, 3, 3])
    slots = torch.tensor([_slot("forward"), _slot("diag_fwd_left"), _slot("reverse"), _slot("spin_left"),
                          _slot("stand"), _slot("side_right"), _slot("forward"), _slot("walk_right")])
    flag = torch.tensor([False, False, False, False, False, False, True, False])
    r.pre_step(levels, types, slots, flag)
    done = torch.tensor([1, 1, 1, 1, 1, 1, 1, 0])
    map_off = torch.tensor([0, 1, 0, 0, 1, 0, 0, 1])
    assert r.post_step(done, map_off, iteration=5) == 7
    cells = {(c, b, g, m): n for c, b, g, m, n in r.snapshot(5)["cells"]}
    assert cells == {(0, 0, "forward", "map_on_adaptive"): 1, (0, 0, "forward", "map_off"): 1,
                     (1, 3, "reverse", "map_on_adaptive"): 1, (1, 3, "turn_left", "map_on_adaptive"): 1,
                     (2, 6, "stand", "map_off"): 1, (2, 6, "side_right", "map_on_adaptive"): 1,
                     (3, 0, "flag", "map_on_adaptive"): 1}
    assert r.snapshot(5)["total"] == 7


def test_an_episode_counts_once_and_only_when_it_started_inside_the_window():
    r = _recorder(n=2, start=10)
    args = (torch.tensor([1, 1]), torch.tensor([0, 0]), torch.tensor([0, 0]), torch.tensor([False, False]))
    r.episode_start[1] = 4                                                  # began before the window opened
    r.pre_step(*args)
    assert r.post_step(torch.tensor([1, 1]), torch.tensor([0, 0]), iteration=11) == 1
    assert r.excluded_started_before_window == 1
    r.pre_step(*args)                                                       # the next episode of env 1 starts at 11
    assert r.post_step(torch.tensor([0, 1]), torch.tensor([0, 0]), iteration=12) == 1
    assert r.snapshot(12)["total"] == 2 and int(r.serial[0]) == 1 and int(r.serial[1]) == 2


def test_post_step_without_a_pre_step_is_refused():
    with pytest.raises(RuntimeError, match="pre_step"):
        _recorder().post_step(torch.zeros(8), torch.zeros(8), 1)


def test_the_boundary_file_is_written_atomically_then_the_window_restarts_and_ranks_fold(tmp_path):
    ranks = []
    for rank in (0, 1):
        r = lc.LearnedCellRecorder(4, 4, EX39_SLOTS, stage_id="E1F", plan_sha256="b" * 64, rank=rank, world_size=2)
        r.pre_step(torch.tensor([0, 1, 4, 7]), torch.tensor([0, 1, 2, 3]), torch.zeros(4, dtype=torch.long),
                   torch.zeros(4, dtype=torch.bool))
        r.post_step(torch.ones(4), torch.zeros(4), 3)
        path = r.write(tmp_path, 250, [{"family": "A", "kind": "k"}] * 4)
        assert path.name == f"learned_cells_250_rank{rank}.json" and not list(tmp_path.glob("*.tmp"))
        assert r.snapshot(251)["total"] == 0 and r.window_from == 250       # a new window
        ranks.append(json.loads(path.read_text()))
    folded = lc.fold_cells(ranks)
    assert sum(folded.values()) == 8 and folded[(0, 0, "forward", "map_on_adaptive")] == 2
    ranks[1]["window"]["to_it"] = 500
    with pytest.raises(ValueError, match="differ"):
        lc.fold_cells(ranks)
