"""All-column mount check logic (batches, per family/kind records, failure reasons) on fake Kit objects."""
from __future__ import annotations

import types

import numpy as np
import torch

from foothold_s2.scripts import ex42_mesh_mount_check as mc


class Mesh:
    """Floor at z=0 everywhere except a pit (z=-0.7) under the x,y box of column `pit_column`."""

    def __init__(self, origins, pit_column):
        self.origins, self.pit_column = origins, pit_column

    def at(self, pts, radius=1.0):
        out = np.zeros(len(pts))
        if self.pit_column is None:
            return out
        o = self.origins[:, self.pit_column, :2]
        for i, p in enumerate(pts):
            if (np.abs(p[None] - o) < 0.6).all(axis=1).any():
                out[i] = -0.7
        return out


def _setup(num_envs=4, cols=3, rows=10):
    origins = np.zeros((rows, cols, 3))
    for r in range(rows):
        for c in range(cols):
            origins[r, c] = (r * 20.0, c * 20.0, 0.0)
    o = torch.tensor(origins, dtype=torch.float32)

    terrain = types.SimpleNamespace(
        terrain_levels=torch.zeros(num_envs, dtype=torch.long), terrain_types=torch.zeros(num_envs, dtype=torch.long),
        env_origins=torch.zeros(num_envs, 3), terrain_origins=o)
    robot = types.SimpleNamespace(data=types.SimpleNamespace(
        root_pos_w=torch.zeros(num_envs, 3), body_pos_w=torch.zeros(num_envs, 4, 3)))
    resets = []

    def reset():
        resets.append(1)
        robot.data.root_pos_w = terrain.env_origins + torch.tensor([0.0, 0.0, 0.35])
        robot.data.body_pos_w = (terrain.env_origins[:, None, :] + torch.tensor(
            [[0.2, 0.1, 0.0], [0.2, -0.1, 0.0], [-0.2, 0.1, 0.0], [-0.2, -0.1, 0.0]])[None])

    raw = types.SimpleNamespace(num_envs=num_envs, reset=reset, scene={"robot": robot})
    env = types.SimpleNamespace(step=lambda a: None)
    return origins, terrain, raw, env, resets


def _run(pit_column):
    origins, terrain, raw, env, resets = _setup()
    data = {"column_family": ["A", "C", "C"], "origins": origins}
    table = [{"family": "A", "kind": "random_rough", "from_declaration": False, "ranges": {}},
             {"family": "C", "kind": "gap", "from_declaration": True,
              "ranges": {"x": (0.0, 0.0), "y": (0.0, 0.0), "yaw": (0.0, 0.0)}},
             {"family": "C", "kind": "flat", "from_declaration": False, "ranges": {}}]
    mesh = Mesh(origins, pit_column)
    res = mc._per_column_pass(env, raw, terrain, mesh, [0, 1, 2, 3], None, data, table, np, torch)
    return res, resets


def test_every_column_and_level_is_assigned_in_batches_and_a_clean_mesh_passes():
    res, resets = _run(None)
    assert res["levels"] == [0, 3, 6, 9] and res["checked"] == 3 * 4 == 12
    assert len(resets) == 3 and res["assignment_kept"] is True            # 12 pairs over 4 envs = 3 batches
    assert res["failed_count"] == 0 and res["by_family"] == {
        "A": {"checked": 4, "failed": 0, "failed_kinds": []}, "C": {"checked": 8, "failed": 0, "failed_kinds": []}}
    assert {(r["column"], r["level"]) for r in res["rows"]} == {(c, l) for c in range(3) for l in (0, 3, 6, 9)}


def test_a_start_over_a_pit_is_recorded_with_family_column_level_and_reason():
    res, _ = _run(pit_column=1)                                           # the C gap column starts over a pit
    assert res["failed_count"] == 4
    assert {(r["family"], r["column"]) for r in res["failed"]} == {("C", 1)}
    assert sorted(r["level"] for r in res["failed"]) == [0, 3, 6, 9]
    bad = res["failed"][0]
    assert "foot_hovers" in bad["reasons"] and bad["foot_clearance_max"] > 0.6
    assert res["by_family"]["C"]["failed"] == 4 and res["by_family"]["A"]["failed"] == 0


def test_zero_range_columns_must_start_on_their_origin():
    origins, terrain, raw, env, _ = _setup()
    data = {"column_family": ["C"], "origins": origins[:, :1]}
    table = [{"family": "C", "kind": "gap", "from_declaration": True,
              "ranges": {"x": (0.0, 0.0), "y": (0.0, 0.0)}}]
    base_reset = raw.reset

    def shifted():
        base_reset()
        raw.scene["robot"].data.root_pos_w = raw.scene["robot"].data.root_pos_w + torch.tensor([0.4, 0.0, 0.0])

    raw.reset = shifted
    res = mc._per_column_pass(env, raw, terrain, Mesh(origins, None), [0, 1, 2, 3], None, data, table, np, torch)
    assert all("zero_range_start_off_origin" in r["reasons"] for r in res["rows"])


class CurriculumTerrain(types.SimpleNamespace):
    """Fake Isaac TerrainImporter: update_env_origins really moves levels (class method)."""

    def update_env_origins(self, env_ids, move_up, move_down):
        self.terrain_levels[env_ids] += 1 * move_up - 1 * move_down
        self.env_origins[env_ids] = self.terrain_origins[self.terrain_levels[env_ids], self.terrain_types[env_ids]]


def _curriculum_setup(on_step):
    origins, terrain, raw, env, resets = _setup()
    terrain = CurriculumTerrain(**vars(terrain))
    terrain.terrain_levels = torch.zeros(4, dtype=torch.long)
    env.step = lambda action: on_step(terrain)
    return origins, terrain, raw, env


def _table3():
    return [{"family": "A", "kind": "random_rough", "from_declaration": False, "ranges": {}},
            {"family": "C", "kind": "gap", "from_declaration": False, "ranges": {}},
            {"family": "C", "kind": "flat", "from_declaration": False, "ranges": {}}]


def test_a_curriculum_move_during_step_is_recorded_not_applied_and_the_method_is_restored():
    def curriculum(terrain):
        terrain.update_env_origins(torch.tensor([0, 2]), torch.tensor([True, False]), torch.tensor([False, True]))

    origins, terrain, raw, env = _curriculum_setup(curriculum)
    data = {"column_family": ["A", "C", "C"], "origins": origins}
    res = mc._per_column_pass(env, raw, terrain, Mesh(origins, None), [0, 1, 2, 3], None, data, _table3(), np, torch)
    assert res["assignment_kept"] is True and res["assignment_change_count"] == 0
    assert res["curriculum_move_count"] == 6                      # 3 batches x 2 envs the curriculum wanted to move
    first = res["curriculum_moves_suppressed"][0]
    assert first["batch"] == 1 and first["env"] == 0 and first["wanted"] == "up" and first["phase"] == "step"
    assert first["family"] == "A" and first["kind"] == mc.column_kind(0, ["A", "C", "C"]) and first["column"] == 0 and first["level"] == 0
    assert "update_env_origins" not in terrain.__dict__           # the class method is back
    terrain.terrain_levels[:] = 0
    terrain.update_env_origins(torch.tensor([1]), torch.tensor([True]), torch.tensor([False]))
    assert terrain.terrain_levels[1].item() == 1                  # and it works again


def test_any_other_change_of_the_assignment_is_listed_with_env_cell_and_moment():
    def meddle(terrain):
        terrain.terrain_types[1] = 2

    origins, terrain, raw, env = _curriculum_setup(meddle)
    data = {"column_family": ["A", "C", "C"], "origins": origins}
    res = mc._per_column_pass(env, raw, terrain, Mesh(origins, None), [0, 1, 2, 3], None, data, _table3(), np, torch)
    assert res["assignment_kept"] is False and res["assignment_change_count"] >= 1
    change = res["assignment_changes"][0]
    assert change["when"] == "after_step" and change["env"] == 1 and change["now_column"] == 2
    assert {"assigned_column", "assigned_level", "assigned_family", "assigned_kind"} <= set(change)
