"""CPU tests for the new-OUT entry of a stage seeded from its own boundary checkpoint (E2 m550 / m750 with the beam mesh and the x level-up rule)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.scripts.ex42_training_entry import e_stage_table
from foothold_s2.tools import ex42_e2_reentry_draft as rd

SOURCE = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_record/e2_handoff_20261119_013854/materialized_E2")
MESH = Path("/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv")
needs_real = pytest.mark.skipif(not (SOURCE / "ex42-prep.yaml").is_file() or not (MESH / "terrain_manifest.json").is_file(),
                                reason="the materialized E2 folder or the beam mesh is not on this machine")


def _rows(parent_source):
    return [{"id": "E1F", "maximum_updates": 1000, "critic_mirror": True},
            {"id": "E2", "minimum_updates": 250, "maximum_updates": 1500, "extension_updates": 500, "extension_max_count": 2,
             "parent": {"source_stage_id": parent_source, "manifest_local_update": 550, "checkpoint_key": "model_550.pt",
                        "sha256": "0" * 64, "cumulative_update": 16050}}]


def test_a_parent_from_the_previous_stage_keeps_the_old_table_and_a_self_parent_names_the_stage_itself():
    old = e_stage_table(_rows("E1F"))["E2"]
    assert old["previous"] == "E1F" and old["previous_caps"] == {1000}
    new = e_stage_table(_rows("E2"))["E2"]
    assert new["previous"] == "E2" and new["previous_caps"] == {1500, 2000, 2500} and new["previous_mirror"] is True
    assert {k: v for k, v in new.items() if not k.startswith("previous")} == {k: v for k, v in old.items() if not k.startswith("previous")}


def test_the_shipped_plan_has_no_self_parent():
    plan = yaml.safe_load((Path(__file__).resolve().parents[1] / "curriculum/ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    assert all((row.get("parent") or {}).get("source_stage_id") != row["id"] for row in plan["stages"])


@needs_real
def test_the_design_sparse_kinds_are_columns_of_the_beam_mesh():
    t = json.loads((MESH / "terrain_manifest.json").read_text(encoding="utf-8-sig"))
    have = {f"{k['family']}/{k['kind']}" for k in t["kinds"] if k["family"] != "continuous"}
    assert set(rd.DEFAULT_KINDS) <= have and len(rd.DEFAULT_KINDS) == len(set(rd.DEFAULT_KINDS)) == 10


def _fake_run(tmp_path, iteration=550):
    run = tmp_path / "run"
    run.mkdir()
    (run / f"model_{iteration}.pt").write_bytes(b"checkpoint")
    sha = hashlib.sha256(b"checkpoint").hexdigest()
    (run / "manifest.json").write_text(json.dumps({"progress": {"completed_updates": iteration + 50},
                                                    "checkpoints": {f"model_{iteration}.pt": sha}}), encoding="utf-8")
    return run, sha


@needs_real
def test_the_draft_reads_through_the_launch_side_readers_and_changes_only_what_it_says(tmp_path):
    from foothold_s2.curriculum import ex41
    from foothold_s2.curriculum.ex42_prep import EX42Plan, authorization_validators
    from foothold_s2.ex42_stage_judges import adapter_for
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    run, sha = _fake_run(tmp_path)
    cell = {"x_progress_kinds": rd.DEFAULT_KINDS, "x_progress_fraction": 0.5, "forward_only": True}
    out = tmp_path / "draft"
    record = rd.draft(SOURCE, run, 550, MESH, out, promotion=cell)
    plan = EX42Plan.load(out / "ex42-prep.yaml")
    assert plan.sha256 == record["new_plan_sha256"] != record["source_plan_sha256"]
    row = next(r for r in plan.document["stages"] if r["id"] == "E2")
    assert row["parent"] == {"source_stage_id": "E2", "manifest_local_update": 550, "checkpoint_key": "model_550.pt", "sha256": sha,
                             "cumulative_update": 15500 + 550}
    assert "materialization" not in plan.document and not (out / "transition.json").exists()
    assert ex41.terrain_promotion_cell(plan)["x_progress_kinds"] == tuple(rd.DEFAULT_KINDS)
    assert pinned_stage_mesh(plan.document, "E2")["geometry_sha256"] == json.loads((MESH / "mesh_manifest.json").read_text(encoding="utf-8-sig"))["mesh_sha256"]
    assert authorization_validators(plan)["E2"](out / "ex42-approvals.yaml", sha)["scope"]["parent_sha256"] == sha
    assert adapter_for(plan.document, "E2") is not None
    assert e_stage_table(plan.document["stages"])["E2"]["previous"] == "E2"
    old = yaml.safe_load((SOURCE / "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    new = plan.document
    changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    assert changed == {"stages", "training_mesh_profiles", "stage_zero", "materialization", "terrain_promotion"}
    for a, b in zip(old["stages"], new["stages"]):
        if a["id"] != "E2":
            assert {k for k in a if a[k] != b[k]} <= {"training_mesh_profile"}
    with pytest.raises(FileExistsError):
        rd.draft(SOURCE, run, 550, MESH, out)


@needs_real
def test_a_checkpoint_the_manifest_has_not_published_is_refused(tmp_path):
    run, _ = _fake_run(tmp_path)
    with pytest.raises(ValueError, match="has not published"):
        rd.draft(SOURCE, run, 750, MESH, tmp_path / "draft")


@needs_real
def test_the_rollback_draft_keeps_the_plans_own_mesh_and_rule(tmp_path):
    run, sha = _fake_run(tmp_path)
    out = tmp_path / "rollback"
    record = rd.draft(SOURCE, run, 550, MESH, out, keep_mesh=True)
    old = yaml.safe_load((SOURCE / "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    new = yaml.safe_load((out / "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    assert record["mesh_stages"] == [] and new["training_mesh_profiles"] == old["training_mesh_profiles"] and "terrain_promotion" not in new
    assert [r.get("training_mesh_profile") for r in new["stages"]] == [r.get("training_mesh_profile") for r in old["stages"]]
    assert next(r for r in new["stages"] if r["id"] == "E2")["parent"]["sha256"] == sha
