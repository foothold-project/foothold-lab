"""Known answers for named kind/level cells on the pinned combined mesh."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.eval import fixed_terrain as ft
from foothold_s2.eval.ex42_mesh_eval import validate_kind_cell


TABLE = ([{"family": "A", "kind": "rough"} for _ in range(2)]
         + [{"family": "B", "kind": "rough"}, {"family": "B", "kind": "boxes"}]
         + [{"family": "B", "kind": "rough"}])


def _raw():
    origins = torch.arange(10 * len(TABLE) * 3, dtype=torch.float).reshape(10, len(TABLE), 3)
    terrain = SimpleNamespace(terrain_origins=origins,
                              terrain_levels=torch.zeros(64, dtype=torch.long),
                              terrain_types=torch.zeros(64, dtype=torch.long))
    terrain.env_origins = origins[terrain.terrain_levels, terrain.terrain_types].clone()
    scene = SimpleNamespace(terrain=terrain, env_origins=terrain.env_origins)
    return SimpleNamespace(scene=scene)


def test_named_kind_assignment_cycles_only_matching_family_and_kind():
    levels, types = ft.kind_assignment(64, 10, TABLE, "B", "rough", 6)
    assert levels.tolist() == [6] * 64
    assert types.tolist() == [2, 4] * 32
    raw = _raw()
    record = ft.apply_kind(raw, TABLE, "B", "rough", 6)
    assert record["assignment_sha256"] == ft.assignment_sha256(levels, types)
    assert raw.scene.terrain.terrain_types.tolist() == types.tolist()
    assert torch.equal(raw.scene.terrain.env_origins, raw.scene.terrain.terrain_origins[6, raw.scene.terrain.terrain_types])
    mesh = {"column_family": [r["family"] for r in TABLE], "columns": [r["kind"] for r in TABLE]}
    result = {"envs": 64, "fixed_terrain": record,
              "terrain_tiles": [{"env": i, "column": int(types[i]), "level": 6, "kind": "rough"}
                                for i in range(64)]}
    validate_kind_cell(result, mesh, family="B", kind="rough", level=6)
    for mutation in (lambda r: r["terrain_tiles"][3].update(column=1),
                     lambda r: r["fixed_terrain"].update(assignment_sha256="0" * 64),
                     lambda r: r["fixed_terrain"].update(family="A"),
                     lambda r: r["terrain_tiles"].pop()):
        changed = deepcopy(result)
        mutation(changed)
        with pytest.raises(ValueError, match="kind evaluation"):
            validate_kind_cell(changed, mesh, family="B", kind="rough", level=6)


def test_unknown_kind_or_bad_level_cannot_silently_fall_back_to_a23():
    for family, kind, level in (("C", "rough", 0), ("B", "unknown", 0), ("B", "rough", 10)):
        with pytest.raises(ValueError):
            ft.kind_assignment(64, 10, TABLE, family, kind, level)


def test_four_foot_raw_evidence_rejects_missing_or_nonfinite_active_steps():
    alive = np.ones((3, 2), dtype=bool)
    contact = np.ones((3, 2, 4), dtype=bool)
    foot = np.zeros((3, 2, 4, 3), dtype=np.float32)
    ft.verify_kind_foot_arrays(contact, foot, alive)
    with pytest.raises(ValueError, match="foot evidence"):
        ft.verify_kind_foot_arrays(contact[:, :, :3], foot, alive)
    with pytest.raises(ValueError, match="foot evidence"):
        ft.verify_kind_foot_arrays(contact.astype(np.int8), foot, alive)
    foot[1, 0, 2, 0] = np.nan
    with pytest.raises(ValueError, match="foot evidence"):
        ft.verify_kind_foot_arrays(contact, foot, alive)
    alive[1, 0] = False
    ft.verify_kind_foot_arrays(contact, foot, alive)


def test_a_32_env_kind_cell_validates_only_against_its_own_env_count():
    mesh = {"column_family": [r["family"] for r in TABLE], "columns": [r["kind"] for r in TABLE]}
    levels, types = ft.kind_assignment(32, 10, TABLE, "B", "rough", 6)
    record = {"rows": 10, "cols": len(TABLE), "num_envs": 32, "fixed_level": 6, "family": "B", "kind": "rough",
              "assignment_sha256": ft.assignment_sha256(levels, types)}
    result = {"envs": 32, "fixed_terrain": record,
              "terrain_tiles": [{"env": i, "column": int(types[i]), "level": 6, "kind": "rough"} for i in range(32)]}
    validate_kind_cell(result, mesh, family="B", kind="rough", level=6, envs=32)
    with pytest.raises(ValueError, match="kind evaluation"):
        validate_kind_cell(result, mesh, family="B", kind="rough", level=6)          # the E2 default stays 64


def test_a_start_yaw_zero_kind_cell_must_record_the_plus_x_start_and_a_random_yaw_cell_must_not():
    mesh = {"column_family": [r["family"] for r in TABLE], "columns": [r["kind"] for r in TABLE]}
    levels, types = ft.kind_assignment(32, 10, TABLE, "B", "rough", 6)
    record = {"rows": 10, "cols": len(TABLE), "num_envs": 32, "fixed_level": 6, "family": "B", "kind": "rough",
              "assignment_sha256": ft.assignment_sha256(levels, types)}
    result = {"envs": 32, "fixed_terrain": record,
              "terrain_tiles": [{"env": i, "column": int(types[i]), "level": 6, "kind": "rough"} for i in range(32)]}
    kw = dict(family="B", kind="rough", level=6, envs=32)
    validate_kind_cell(result, mesh, **kw)                                          # no record, plan says random yaw
    validate_kind_cell({**result, "start_yaw_override": 0.0}, mesh, start_yaw_zero=True, **kw)
    for bad, flag in ((result, True), ({**result, "start_yaw_override": 0.5}, True), ({**result, "start_yaw_override": 0.0}, False)):
        with pytest.raises(ValueError, match="start yaw"):
            validate_kind_cell(bad, mesh, start_yaw_zero=flag, **kw)
