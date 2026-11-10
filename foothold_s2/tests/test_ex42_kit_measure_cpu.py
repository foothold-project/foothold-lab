from __future__ import annotations

import copy
import importlib.util
import sys
import types

import numpy as np
import pytest

from foothold_s2.curriculum.ex42_manifest import RECEIPT_FORMAT, assemble_manifest
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_kit_measure as km


def _plan():
    return EX42Plan.load(km.DEFAULT_TABLE)


def _expected():
    return _plan().document["terrain_manifest_contract"]["kind_count_by_family"]


def test_modules_called_exist():
    for name in ("foothold_s2.curriculum.ex42_manifest", "foothold_s2.terrains.ex42",
                 "foothold_s2.terrains.rough_go2_cfg", "foothold_s2.terrains.sparse_terrains", "foothold_s2.terrains.jeplo_preset",
                 "foothold_s2.scripts.ex42_manifest_build"):
        assert importlib.util.find_spec(name) is not None, name


def test_coverage_reports_missing_generators_and_does_not_invent_declarations():
    report = km.coverage(_expected(), km.buildable_kinds(), {})
    assert report["C"]["generator_in_repo"] == 7 and report["C"]["generator_missing"] == 0
    for family in ("B", "D"):
        assert report[family]["generator_in_repo"] == 0
        assert report[family]["generator_missing"] == _expected()[family]
    assert report["continuous"]["generator_in_repo"] == 7
    assert report["E"]["generator_in_repo"] == 4
    # nothing declared -> nothing measurable
    assert all(not r["declared_complete"] for r in report.values())
    assert all(set(r["undeclared_fields"]) == set(r["buildable_kinds"]) for r in report.values())


def test_template_is_all_null_so_nothing_is_measured_until_an_owner_fills_it():
    template = km.declarations_template(km.buildable_kinds())
    for family, kinds in template.items():
        for kind, row in kinds.items():
            assert km.declaration_gaps(row) == list(km.DECLARATION_FIELDS)


def test_partial_declaration_stays_undeclared():
    row = {name: None for name in km.DECLARATION_FIELDS}
    row["preset_id"] = "rough_go2_cfg"
    gaps = km.declaration_gaps(row)
    assert "preset_id" not in gaps and "paper_reference" in gaps and "physical_flag" in gaps


def test_incomplete_inventory_makes_partial_manifest_with_blocker():
    head = "a" * 40
    row = {
        "family": "E", "kind": "slope_steep", "preset_id": "paper_ext_v1",
        "original_dimensions_m": {"slope": 0.4}, "training_dimensions_m": {"slope": 0.7},
        "evaluation_dimensions_m": {"slope": 0.8},
        "evaluation_axis_directions": {"slope": "higher"},
        "geometry_sha256": "b" * 64, "paper_reference": "test fixture", "physical_flag": False,
        "measurement_provenance": {"source_head": head, "seed": 42, "device": "cuda:1"},
    }
    receipt = {"format": RECEIPT_FORMAT, "state": "passed", "receipt_id": "fixture",
               "family": "E", "source_head": head, "seed": 42, "device": "cuda:1",
               "kit_started": True, "training_started": False, "kinds": [row]}
    manifest = assemble_manifest(_plan(), [receipt])
    assert manifest["status"] == "partial"
    assert "per_kind_inventory_incomplete" in manifest["blockers"]
    assert any(b.startswith("aggregate_measurements_missing") for b in manifest["blockers"])


# ---- 영수증 돌연변이 방어 (reviewer-lx 00:25 고침 1: K3 K6 M3 M4 M6 M7 M8 M9)

HEAD = "a" * 40


def _row(**over):
    row = {
        "family": "E", "kind": "slope_steep", "preset_id": "paper_ext_v1",
        "original_dimensions_m": {"slope": 0.4}, "training_dimensions_m": {"slope": 0.7},
        "evaluation_dimensions_m": {"slope": 0.8},
        "evaluation_axis_directions": {"slope": "higher"},
        "geometry_sha256": "b" * 64, "paper_reference": "fixture", "physical_flag": False,
        "measurement_provenance": {"source_head": HEAD, "seed": 42, "device": "cuda:1"},
    }
    row.update(over)
    return row


def _receipt(rows, family="E", **over):
    r = {"format": RECEIPT_FORMAT, "state": "passed", "receipt_id": "fixture", "family": family,
         "source_head": HEAD, "seed": 42, "device": "cuda:1", "kit_started": True,
         "training_started": False, "kinds": rows}
    r.update(over)
    return r


@pytest.mark.parametrize("over", [
    {"geometry_sha256": "G" * 64},                    # M4 not hex
    {"geometry_sha256": "b" * 63},                    # short hash
    {"physical_flag": None},                          # M6
    {"evaluation_dimensions_m": {"slope": 0.6}},      # M7 opposite of declared direction
    {"original_dimensions_m": {}},                    # empty dimensions
    {"paper_reference": "  "},
])
def test_assemble_rejects_bad_rows(over):
    with pytest.raises(ValueError):
        assemble_manifest(_plan(), [_receipt([_row(**over)])])


def test_assemble_rejects_empty_family_receipt_and_wrong_device():     # K6
    with pytest.raises(ValueError):
        assemble_manifest(_plan(), [_receipt([])])
    with pytest.raises(ValueError):
        assemble_manifest(_plan(), [_receipt([_row()], device="cuda:0")])


def test_full_inventory_without_aggregates_is_still_partial():        # M3
    plan = _plan()
    rows, receipts = None, []
    for family, count in _expected().items():
        rows = [_row(family=family, kind=f"{family}{i}", geometry_sha256=f"{i:064x}")
                for i in range(count)]
        receipts.append(_receipt(rows, family=family, receipt_id=f"r-{family}"))
    manifest = assemble_manifest(plan, receipts)
    assert manifest["status"] == "partial"
    assert manifest["blockers"] == [
        "aggregate_measurements_missing:peak_memory_gib,generation_seconds,ray_count_per_second"]
    full = assemble_manifest(plan, receipts, aggregate_measurements={
        "peak_memory_gib": 1.0, "generation_seconds": 1.0, "ray_count_per_second": 1.0})
    assert full["status"] == "measured"


class _FakeMesh:
    def __init__(self, vertices, faces):
        self.vertices, self.faces = vertices, faces
        self.bounds = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])


def _fake_isaaclab(monkeypatch, vertices, faces):
    class Gen:
        def __init__(self, cfg):
            self.terrain_mesh = _FakeMesh(vertices, faces)
    mod = types.ModuleType("isaaclab.terrains")
    mod.TerrainGenerator = Gen
    pkg = types.ModuleType("isaaclab")
    pkg.terrains = mod
    monkeypatch.setitem(sys.modules, "isaaclab", pkg)
    monkeypatch.setitem(sys.modules, "isaaclab.terrains", mod)


class _Cfg:
    def __init__(self):
        self.sub_terrains = {}
        self.proportion = 0.0


def _measure(**over):
    from foothold_s2.curriculum.ex42_manifest import measure_kind_with_kit
    args = dict(family="E", kind="slope_steep", preset_id="p", generator_cfg=_Cfg(),
                subterrain_cfg=_Cfg(), original_dimensions_m={"s": 0.4},
                training_dimensions_m={"s": 0.7}, evaluation_dimensions_m={"s": 0.8},
                evaluation_axis_directions={"s": "higher"}, paper_reference="ref",
                physical_flag=False, source_head=HEAD, seed=42)
    args.update(over)
    return measure_kind_with_kit(**args)


def test_hash_comes_from_generated_geometry_not_from_declarations(monkeypatch):   # M8
    import hashlib
    v = np.arange(12, dtype=np.float64).reshape(4, 3)
    f = np.array([[0, 1, 2], [1, 2, 3]], dtype=np.int64)
    _fake_isaaclab(monkeypatch, v, f)
    row, _ = _measure()
    assert row["geometry_sha256"] == hashlib.sha256(v.tobytes() + f.tobytes()).hexdigest()
    row2, _ = _measure(training_dimensions_m={"s": 0.71}, evaluation_dimensions_m={"s": 0.81})
    assert row2["geometry_sha256"] == row["geometry_sha256"]      # declaration cannot move the hash
    _fake_isaaclab(monkeypatch, v + 1.0, f)
    assert _measure()[0]["geometry_sha256"] != row["geometry_sha256"]


@pytest.mark.parametrize("over", [
    {"training_dimensions_m": {"s": None}}, {"physical_flag": None},
    {"original_dimensions_m": {}}, {"paper_reference": ""},
])
def test_kit_side_refuses_undeclared_values_before_generating(monkeypatch, over):  # M9
    _fake_isaaclab(monkeypatch, np.zeros((3, 3)), np.zeros((1, 3), dtype=np.int64))
    with pytest.raises(ValueError):
        _measure(**over)


def test_measure_family_skips_undeclared_and_refuses_when_none(monkeypatch):      # K3 K6
    calls = []

    def fake_measure(**kw):
        calls.append(kw["kind"])
        return _row(kind=kw["kind"], family=kw["family"]), 0.1
    monkeypatch.setattr("foothold_s2.curriculum.ex42_manifest.measure_kind_with_kit", fake_measure)
    monkeypatch.setattr(km, "_generator_for", lambda f, k, seed=42: (object(), object()))
    monkeypatch.setattr(km, "source_head", lambda: HEAD)
    complete = {n: v for n, v in _row().items() if n in km.DECLARATION_FIELDS}
    partial = dict(complete, physical_flag=None)
    decl = {"E": {"slope_steep": complete, "slope_steep_inv": partial}}
    receipt = km.measure_family("E", decl, seed=42, device="cuda:1", receipt_id="x")
    assert calls == ["slope_steep"] and [r["kind"] for r in receipt["kinds"]] == ["slope_steep"]
    with pytest.raises(ValueError):
        km.measure_family("E", {"E": {"slope_steep": partial}}, seed=42, device="cuda:1", receipt_id="x")


def test_family_c_wiring_passes_seed(monkeypatch):
    assert km.buildable_kinds()["C"] == list(__import__("foothold_s2.terrains.jeplo_preset", fromlist=["KINDS"]).KINDS)
    seen = {}
    fake = types.ModuleType("foothold_s2.terrains.jeplo_preset")
    fake.KINDS = ("gap",)
    fake.measurement_generator = lambda kind, seed: seen.update(kind=kind, seed=seed) or ("g", "s")
    monkeypatch.setitem(sys.modules, "foothold_s2.terrains.jeplo_preset", fake)
    assert km._generator_for("C", "gap", 7) == ("g", "s") and seen == {"kind": "gap", "seed": 7}
