from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from foothold_s2.scripts import ex42_kit_measure as km
from foothold_s2.scripts import ex42_mesh_build as mb
from foothold_s2.terrains.ex42_combined import combine_family_parts, family_column_summary


class Mesh:
    def __init__(self, x0, x1, y0, y1):
        self.vertices = np.array([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]], float)
        self.faces = np.array([[0, 1, 2], [0, 2, 3]])


def part(name, rows, cols, size=8.0, centre=True):
    """Mimic the Isaac generator: rows along x, columns along y, mesh centred."""
    x0, y0 = -size * rows / 2, -size * cols / 2
    origins = np.zeros((rows, cols, 3))
    for r in range(rows):
        for c in range(cols):
            origins[r, c] = (x0 + (r + 0.5) * size, y0 + (c + 0.5) * size, 0.0)
    return {"name": name, "mesh": Mesh(x0, x0 + size * rows, y0, y0 + size * cols), "origins": origins}


def test_find_spec_for_called_modules():
    for m in ("foothold_s2.terrains.ex42_combined", "foothold_s2.scripts.ex42_mesh_build",
              "foothold_s2.terrains.jeplo_preset", "foothold_s2.terrains.rough_go2_cfg"):
        assert importlib.util.find_spec(m) is not None


def test_join_keeps_origins_inside_their_part_and_touching_without_overlap():
    a, c, e = part("A", 10, 50), part("C", 10, 7, size=9.0), part("E", 10, 4)
    out = combine_family_parts([a, c, e])
    assert out["origins"].shape == (10, 61, 3)
    assert family_column_summary(out["column_family"]) == {"A": 50, "C": 7, "E": 4}
    # the first part is not moved; later parts start where the previous ended
    assert out["offsets"]["A"] == 0.0
    ys = out["vertices"][:, 1]
    assert ys.min() == pytest.approx(-8.0 * 50 / 2)
    assert ys.max() == pytest.approx(-8.0 * 50 / 2 + 8.0 * 50 + 9.0 * 7 + 8.0 * 4)
    # origin column order is A then C then E and increasing along y
    assert (np.diff(out["origins"][0, :, 1]) > 0).all()
    assert out["column_family"][0] == "A" and out["column_family"][-1] == "E"
    # faces of later parts index into the concatenated vertices
    assert out["faces"].max() == len(out["vertices"]) - 1


def test_join_rejects_row_mismatch_and_origins_outside_mesh():
    with pytest.raises(ValueError):
        combine_family_parts([part("A", 10, 5), part("C", 9, 5)])
    bad = part("A", 10, 5)
    bad["origins"][0, 0, 1] += 1000.0
    with pytest.raises(ValueError):
        combine_family_parts([bad])
    with pytest.raises(ValueError):
        combine_family_parts([])


def test_partial_mesh_aggregates_never_use_the_final_key_names():
    values = {"peak_memory_gib": 1.5, "generation_seconds": 2.5, "ray_count_per_second": 1e8}
    name, payload = mb.aggregate_files(["A", "C", "E"], values)
    assert name == "aggregate_partial_mesh.json"
    assert not set(mb.AGGREGATE_KEYS) & set(payload) and payload["valid_for_manifest"] is False
    assert payload["families_missing"] == ["B", "D"]    # partial: only A C E given
    name, payload = mb.aggregate_files(list(mb.ALL_FAMILIES), values)
    assert name == "aggregate_measurements.json" and set(payload) == set(mb.AGGREGATE_KEYS)
    with pytest.raises(ValueError):
        mb.aggregate_files(list(mb.ALL_FAMILIES), {**values, "ray_count_per_second": 0})


def test_ray_grids_match_declared_counts():
    assert len(mb.grid_offsets(17, 11)) == mb.HEIGHT_SCAN_RAYS == 187
    assert len(mb.grid_offsets(60, 60)) == mb.DEPTH_RAYS == 3600


def test_family_a_is_the_full_thirteen_and_plan_shows_it():
    report = km.coverage(km._expected() if hasattr(km, "_expected") else
                         {"A": 13, "continuous": 7, "C": 7, "E": 4, "B": 12, "D": 3},
                         km.buildable_kinds(), {})
    assert report["A"]["generator_in_repo"] == 13 and report["A"]["generator_missing"] == 0
    assert report["C"]["generator_in_repo"] == 7 and report["E"]["generator_in_repo"] == 4
    assert report["B"]["generator_in_repo"] == 0 and report["D"]["generator_in_repo"] == 3
