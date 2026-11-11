"""Known-input checks for later-stage maintenance children and rank receipts."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.ex42_learned_cells_evidence import BANDS, GROUPS, MODES, read_boundary
from foothold_s2.ex42_stage_judges import retained_paper_cells


ROOT = Path(__file__).resolve().parents[2]


def _write(path, *, rank=0, size=2, cells=None):
    row = {"format": "foothold-ex42-learned-cells/1", "stage_id": "E2",
           "plan_sha256": "a" * 64, "window": {"from_it": 250, "to_it": 500},
           "rank": rank, "world_size": size,
           "axes": {"level_bands": BANDS, "groups": GROUPS, "modes": MODES, "columns": 2},
           "columns": None, "cells": cells or [[0, 0, "forward", "map_on_adaptive", 32]],
           "total": sum(cell[4] for cell in (cells or [[0, 0, "forward", "map_on_adaptive", 32]])),
           "excluded_started_before_window": 0, "duplicate_skipped": 0,
           "episodes_counted_once": True}
    row["sha256"] = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path.write_text(json.dumps(row), encoding="utf-8")


def test_retained_children_follow_plan_order_and_keep_the_off_recorded():
    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    assert retained_paper_cells(plan, "E0") == ()
    assert retained_paper_cells(plan, "E1") == ("d44",)
    for stage in ("E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b"):
        assert retained_paper_cells(plan, stage) == ("d44", "flag_cells")
    with pytest.raises(ValueError, match="stage order"):
        retained_paper_cells(plan, "E999")


def test_learned_cells_two_ranks_are_counted_but_not_promoted_without_registration(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"checkpoint")
    for rank in (0, 1):
        _write(tmp_path / f"learned_cells_500_rank{rank}.json", rank=rank)
    row = read_boundary(checkpoint, stage_id="E2", plan_sha256="a" * 64, interval=250)
    assert row["total"] == 64
    assert row["cells"] == [[0, 0, "forward", "map_on_adaptive", 64]]
    assert row["judgement"] == "HOLD" and len(row["receipts"]) == 2


def test_learned_cells_missing_tampered_and_duplicate_rank(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"checkpoint")
    assert read_boundary(checkpoint, stage_id="E2", plan_sha256="a" * 64, interval=250)["judgement"] == "HOLD"
    file = tmp_path / "learned_cells_500_rank0.json"
    _write(file)
    assert read_boundary(checkpoint, stage_id="E2", plan_sha256="a" * 64, interval=250)["ranks_present"] == [0]
    contents = json.loads(file.read_text())
    contents["total"] = 1000
    file.write_text(json.dumps(contents), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA"):
        read_boundary(checkpoint, stage_id="E2", plan_sha256="a" * 64, interval=250)


def test_learned_cells_wrong_stage_and_window_are_rejected(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"checkpoint")
    file = tmp_path / "learned_cells_500_rank0.json"
    _write(file)
    with pytest.raises(ValueError, match="identity"):
        read_boundary(checkpoint, stage_id="E3", plan_sha256="a" * 64, interval=250)
    with pytest.raises(ValueError, match="identity"):
        read_boundary(checkpoint, stage_id="E2", plan_sha256="b" * 64, interval=250)
