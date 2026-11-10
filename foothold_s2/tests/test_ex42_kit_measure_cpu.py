from __future__ import annotations

import importlib.util
import json

from foothold_s2.curriculum.ex42_manifest import RECEIPT_FORMAT, assemble_manifest
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_kit_measure as km


def _plan():
    return EX42Plan.load(km.DEFAULT_TABLE)


def _expected():
    return _plan().document["terrain_manifest_contract"]["kind_count_by_family"]


def test_modules_called_exist():
    for name in ("foothold_s2.curriculum.ex42_manifest", "foothold_s2.terrains.ex42",
                 "foothold_s2.terrains.rough_go2_cfg", "foothold_s2.terrains.sparse_terrains",
                 "foothold_s2.scripts.ex42_manifest_build"):
        assert importlib.util.find_spec(name) is not None, name


def test_coverage_reports_missing_generators_and_does_not_invent_declarations():
    report = km.coverage(_expected(), km.buildable_kinds(), {})
    for family in ("B", "C", "D"):
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
