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


def _terrain():
    caps = {"A/gaps": 2, "B/gap": 2, "C/gap": 2, "B/beam": 2, "A/balance_beams": 2}
    rules = [{"family": "A", "kinds_of": "continuous", "exposure": 1.0, "level_cap": 5}]
    rules += [{"family": k.split("/")[0], "kind": k.split("/")[1], "share": 0.088, "level_cap": c} for k, c in caps.items()]
    return {"exposure_at_E2": {"default": {"exposure": 0.0, "level_cap": 0}, "positive": rules}, "kind_level_cap": {"end": 5, "step_per_boundary": 1}}


def test_kind_caps_bake_the_runs_moves_and_lower_only_the_named_kinds(tmp_path):
    run = tmp_path / "run" / "eval" / "scores" / "m500"
    run.mkdir(parents=True)
    (run / "ladder_outcomes_list.json").write_text(json.dumps([{"B/beam": {"first_window_pass": True}}, {"B/beam": {"first_window_pass": True}, "A/gaps": {"first_window_pass": False}}]))
    terrain, report = rd.set_kind_caps(_terrain(), tmp_path / "run", 2, {"A/gaps": 1, "B/gap": 1, "C/gap": 1, "A/balance_beams": 1})
    assert report["baked"]["B/beam"] == 4 and report["start"]["B/beam"] == 2        # two passes: +1 +1
    assert rd.rule_caps(terrain) == {"A/gaps": 1, "B/gap": 1, "C/gap": 1, "B/beam": 4, "A/balance_beams": 1}
    assert terrain["exposure_at_E2"]["positive"][0]["level_cap"] == 5 and terrain["kind_level_cap"] == {"end": 5, "step_per_boundary": 1}
    assert report["lowered"]["A/gaps"] == {"from": 2, "to": 1}


def test_kind_caps_refuse_raising_unknown_kinds_and_missing_evidence(tmp_path):
    with pytest.raises(ValueError, match="lowering only"):
        rd.set_kind_caps(_terrain(), None, 0, {"A/gaps": 3})
    with pytest.raises(ValueError, match="no such single-kind"):
        rd.set_kind_caps(_terrain(), None, 0, {"A/nothing": 1})
    (tmp_path / "eval" / "scores" / "m500").mkdir(parents=True)
    (tmp_path / "eval" / "scores" / "m500" / "ladder_outcomes_list.json").write_text("[{}]")
    with pytest.raises(ValueError, match="need 2"):
        rd.set_kind_caps(_terrain(), tmp_path, 2, None)
    unchanged, report = rd.set_kind_caps(_terrain(), None, 0, None)
    assert unchanged == _terrain() and report["lowered"] == {}


# ---- kind shares (lead 11/20 18:08): the second door C/box and a graduated kind at 0.03, the bundle staying 0.44 ----
SOURCE_V1 = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_record/e2_handoff_20261120_170553_v1/materialized_E2")
needs_v1 = pytest.mark.skipif(not (SOURCE_V1 / "ex42-prep.yaml").is_file() or not (MESH / "terrain_manifest.json").is_file(),
                              reason="the E2 v1 materialized folder is not on this machine")


def _v1_terrain():
    caps = {"A/gaps": 1, "B/gap": 2, "C/gap": 2, "B/beam": 2, "A/balance_beams": 1}
    share = {"A/gaps": 0.14, "B/gap": 0.0533, "C/gap": 0.0533, "B/beam": 0.0534, "A/balance_beams": 0.14}
    rules = [{"family": "A", "kinds_of": "continuous", "exposure": 1.0, "level_cap": 5}]
    rules += [{"family": k.split("/")[0], "kind": k.split("/")[1], "share": share[k], "level_cap": c} for k, c in caps.items()]
    return {"exposure_at_E2": {"default": {"exposure": 0.0, "level_cap": 0}, "positive": rules}, "kind_level_cap": {"end": 5, "step_per_boundary": 1}}


def test_a_new_kind_row_and_moved_shares_keep_the_bundle_at_0_44():
    terrain, report = rd.set_kind_shares(_v1_terrain(), {"A/gaps": 0.09, "A/balance_beams": 0.09, "C/box": 0.10}, {"C/box": 4})
    assert report["added"] == {"C/box": 4} and report["total"] == pytest.approx(0.44, abs=1e-9)
    assert rd.rule_caps(terrain)["C/box"] == 4 and rd.rule_shares(terrain)["C/box"] == 0.10
    assert rd.rule_shares(terrain)["B/gap"] == 0.0533                       # untouched kinds keep their value
    assert terrain["exposure_at_E2"]["positive"][0]["kinds_of"] == "continuous" and _v1_terrain()["exposure_at_E2"]["positive"][-1]["kind"] == "balance_beams"   # the input is not mutated


def test_a_graduated_kind_goes_to_0_03_and_the_freed_share_must_be_named():
    terrain, report = rd.set_kind_shares(_v1_terrain(), {"A/gaps": 0.03, "B/gap": 0.0533 + 0.11}, None)
    assert rd.rule_shares(terrain)["A/gaps"] == 0.03 and report["total"] == pytest.approx(0.44, abs=1e-9)
    with pytest.raises(ValueError, match="name the receiving kind"):
        rd.set_kind_shares(_v1_terrain(), {"A/gaps": 0.03}, None)


def test_kind_share_refusals():
    with pytest.raises(ValueError, match="no such single-kind"):
        rd.set_kind_shares(_v1_terrain(), {"C/box": 0.1}, None)
    with pytest.raises(ValueError, match="must not be a row already"):
        rd.set_kind_shares(_v1_terrain(), None, {"A/gaps": 3})
    with pytest.raises(ValueError, match="a share between"):
        rd.set_kind_shares(_v1_terrain(), {"A/gaps": -0.01}, None)
    with pytest.raises(ValueError, match="level cap"):
        rd.set_kind_shares(_v1_terrain(), None, {"C/box": 2.5})


@needs_v1
def test_the_e2_v1_reentry_with_c_box_reads_through_the_launch_side_readers(tmp_path):
    """Rehearsal of the boundary hand-over: the running E2 v1 plan, a checkpoint of its run (fake files), C/box added at cap 4 and the first door giving up 0.10."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan, authorization_validators
    from foothold_s2.ex42_stage_judges import adapter_for
    run, sha = _fake_run(tmp_path, 250)
    out = tmp_path / "draft"
    shares = {"A/gaps": 0.09, "A/balance_beams": 0.09, "C/box": 0.10}
    record = rd.draft(SOURCE_V1, run, 250, MESH, out, keep_mesh=True, kind_shares=shares, add_kinds={"C/box": 4})
    plan = EX42Plan.load(out / "ex42-prep.yaml")
    assert plan.sha256 == record["new_plan_sha256"] != record["source_plan_sha256"] and record["kind_shares"]["total"] == pytest.approx(0.44, abs=1e-9)
    row = next(r for r in plan.document["stages"] if r["id"] == "E2")
    assert row["parent"]["sha256"] == sha and row["parent"]["manifest_local_update"] == 250
    assert rd.rule_caps(row["terrain"])["C/box"] == 4 and rd.rule_shares(row["terrain"])["C/box"] == 0.10
    assert authorization_validators(plan)["E2"](out / "ex42-approvals.yaml", sha)["scope"]["parent_sha256"] == sha
    assert adapter_for(plan.document, "E2") is not None
    old = yaml.safe_load((SOURCE_V1 / "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    for a, b in zip(old["stages"], plan.document["stages"]):
        if a["id"] != "E2":
            assert a == b
    with pytest.raises(ValueError, match="name the receiving kind"):
        rd.draft(SOURCE_V1, run, 250, MESH, tmp_path / "bad", keep_mesh=True, kind_shares={"A/gaps": 0.03})
    assert not (tmp_path / "bad").exists()


def test_the_sum_is_held_to_the_bundle_0_44_itself_and_a_zero_share_row_is_refused():
    with pytest.raises(ValueError, match="share 0"):
        rd.set_kind_shares(_v1_terrain(), None, {"C/box": 4})                                 # --add-kind alone leaves a zero row
    bad = _v1_terrain()
    bad["exposure_at_E2"]["positive"][1]["share"] = 0.10                                      # a source that is already off the bundle (0.40)
    with pytest.raises(ValueError, match="bundle is 0.440000"):
        rd.set_kind_shares(bad, {"B/gap": 0.0533}, None)                                      # keeping the wrong sum is not enough


def test_drop_kind_takes_the_row_out_and_the_bundle_falls_by_its_share_and_the_exposure_builder_still_builds():
    """E2 r2 m250 (lead 11/20 21:1x): B/gap, C/gap, B/beam out of the plan (a share-0 row is refused), first doors untouched: 0.44 -> 0.28."""
    terrain = _v1_terrain()
    out, report = rd.set_kind_shares(terrain, None, None, ["B/gap", "C/gap", "B/beam"])
    after = rd.rule_shares(out)
    assert sorted(after) == ["A/balance_beams", "A/gaps"] and after["A/gaps"] == before_first_door(terrain, "A/gaps")
    assert report["dropped"] == {"B/gap": 0.0533, "C/gap": 0.0533, "B/beam": 0.0534} and report["total"] == pytest.approx(0.28, abs=1e-9)
    assert rd.rule_caps(out) == {"A/gaps": 1, "A/balance_beams": 1}                       # the caps of the kept rows are unchanged
    assert [r for r in out["exposure_at_E2"]["positive"] if "kinds_of" in r]                # the continuous weight rule stays: it takes 1 - 0.28


def before_first_door(terrain, kind):
    return rd.rule_shares(terrain)[kind]


def test_drop_kind_refuses_a_kind_that_is_not_a_row_or_is_also_given_a_share_and_keeps_the_sum_honest():
    with pytest.raises(ValueError, match="no such single-kind share row"):
        rd.set_kind_shares(_v1_terrain(), None, None, ["C/box"])
    with pytest.raises(ValueError, match="cannot also be added or given a share"):
        rd.set_kind_shares(_v1_terrain(), {"B/gap": 0.05}, None, ["B/gap"])
    with pytest.raises(ValueError, match="name the receiving kind"):
        rd.set_kind_shares(_v1_terrain(), {"A/gaps": 0.20}, None, ["B/gap"])          # one dropped, the rest not summing to 0.44 - 0.0533


def test_drop_kind_from_a_source_that_already_dropped_rows_keeps_its_own_total_as_the_base():
    """First-door split (lead 11/20 23:04): the new OUT's plan holds only A/gaps + A/balance_beams (0.28). Dropping one of them takes the sparse total to its own
    share, the freed share goes to the continuous columns. The old strict 0.44 bundle rule still holds without a drop."""
    base, _ = rd.set_kind_shares(_v1_terrain(), None, None, ["B/gap", "C/gap", "B/beam"])
    out, report = rd.set_kind_shares(base, None, None, ["A/balance_beams"])
    assert sorted(rd.rule_shares(out)) == ["A/gaps"] and report["total"] == pytest.approx(rd.rule_shares(base)["A/gaps"], abs=1e-9)
    assert rd.rule_caps(out) == {"A/gaps": 1} and [r for r in out["exposure_at_E2"]["positive"] if "kinds_of" in r]
    with pytest.raises(ValueError, match="bundle is 0.440000"):
        rd.set_kind_shares(base, {"A/gaps": 0.14}, None)                                      # no drop: still the strict 0.44 rule on a 0.28 source
    with pytest.raises(ValueError, match="no such single-kind share row"):
        rd.set_kind_shares(out, None, None, ["A/balance_beams"])                              # already gone


def test_shrink_to_continuous_lowers_shares_only_when_asked_and_gives_the_rest_to_the_continuous_columns():
    """rv (lead 2026-11-21 13:28): from the 0.28 plan, A/gaps 0.01 + A/balance_beams 0.01 with --shrink-to-continuous; without the flag the strict rule holds."""
    base, _ = rd.set_kind_shares(_v1_terrain(), None, None, ["B/gap", "C/gap", "B/beam"])
    small = {"A/gaps": 0.01, "A/balance_beams": 0.01}
    with pytest.raises(ValueError, match="bundle is 0.440000"):
        rd.set_kind_shares(base, small, None)                                                 # no flag: refused as before
    out, report = rd.set_kind_shares(base, small, None, shrink=True)
    assert rd.rule_shares(out) == small and report["total"] == pytest.approx(0.02) and report["shrunk_to_continuous"] == pytest.approx(0.26)
    assert rd.rule_caps(out) == rd.rule_caps(base) and [r for r in out["exposure_at_E2"]["positive"] if "kinds_of" in r]      # caps and the continuous rule kept
    for bad in ({"A/gaps": 0.2, "A/balance_beams": 0.01}, {"A/gaps": 0.14, "A/balance_beams": 0.14}):
        with pytest.raises(ValueError, match="only lowers"):
            rd.set_kind_shares(base, bad, None, shrink=True)                                  # raising or keeping the total is not a shrink
    with pytest.raises(ValueError, match="cannot also be added|needs --kind-share values only"):
        rd.set_kind_shares(base, small, None, ["A/gaps"], shrink=True)


def test_shrink_with_add_kind_opens_a_small_new_row_in_one_call():
    """lead 2026-11-21 20:17: D/crawl at a small share in the same call as --shrink-to-continuous (the 0.44 rule refused it; a second draft
    from a draft double-counted the parent's cumulative updates)."""
    base, _ = rd.set_kind_shares(_v1_terrain(), None, None, ["B/gap", "C/gap", "B/beam", "A/gaps"])      # a beams-only 0.14 plan (rx2)
    assert rd.rule_shares(base) == {"A/balance_beams": pytest.approx(0.14)}
    out, rep = rd.set_kind_shares(base, {"D/crawl": 0.04}, {"D/crawl": 2}, shrink=True)
    assert rd.rule_shares(out) == {"A/balance_beams": pytest.approx(0.14), "D/crawl": pytest.approx(0.04)} and rep["from_continuous"] == pytest.approx(0.04)
    out2, rep2 = rd.set_kind_shares(base, {"A/balance_beams": 0.10, "D/crawl": 0.04}, {"D/crawl": 2}, shrink=True)
    assert rd.rule_shares(out2) == {"A/balance_beams": pytest.approx(0.10), "D/crawl": pytest.approx(0.04)} and rep2["from_continuous"] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="give the new rows a share|share 0"):
        rd.set_kind_shares(base, {"A/balance_beams": 0.10}, {"D/crawl": 2}, shrink=True)
    with pytest.raises(ValueError, match="only lowers the shares of existing rows"):
        rd.set_kind_shares(base, {"A/balance_beams": 0.2, "D/crawl": 0.04}, {"D/crawl": 2}, shrink=True)
    with pytest.raises(ValueError, match="passes the 0.44 bundle"):
        rd.set_kind_shares(base, {"D/crawl": 0.31}, {"D/crawl": 2}, shrink=True)
    with pytest.raises(ValueError, match="bundle is"):
        rd.set_kind_shares(base, {"D/crawl": 0.04}, {"D/crawl": 2})                           # without the flag: the strict rule as before


E1F_RUN = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261116_190816/main/EX-42-B-E1F_20261116_190817")
FIRST_E2 = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_record/e2_handoff_20261120_193344_r2/materialized_E2")


def test_no_flags_takes_the_flag_slot_out_and_keeps_the_sum_at_1():
    shares = {"forward": 0.17, "stand": 0.1, "side_left": 0.63, "flag": 0.1}
    out, report = rd.drop_flag_share(shares)
    assert out["flag"] == 0.0 and abs(sum(out.values()) - 1.0) < 1e-8 and out["forward"] == pytest.approx(0.17 / 0.9) and report["flag_before"] == 0.1
    with pytest.raises(ValueError, match="nothing to take out"):
        rd.drop_flag_share({**shares, "flag": 0.0})


def test_parent_from_source_refuses_a_self_parent_or_another_file(tmp_path):
    row = {"parent": {"source_stage_id": "E2", "manifest_local_update": 250, "checkpoint_key": "model_250.pt", "sha256": "0" * 64, "cumulative_update": 15750}}
    with pytest.raises(ValueError, match="another stage"):
        rd.source_parent_pin(row, tmp_path, 250)
    row["parent"]["source_stage_id"] = "E1F"
    with pytest.raises(ValueError, match="not model_300.pt"):
        rd.source_parent_pin(row, tmp_path, 300)
    run, _ = _fake_run(tmp_path)                       # a run whose model_250 is not the pinned file
    with pytest.raises(ValueError, match="has not published|is not the source parent pin"):
        rd.source_parent_pin(row, run, 250)


@pytest.mark.skipif(not (E1F_RUN / "model_250.pt").is_file() or not (FIRST_E2 / "ex42-prep.yaml").is_file(), reason="canonical 3 run not here")
def test_rx2pz_draft_keeps_the_canonical_parent_drops_every_sparse_row_and_the_flags(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan, authorization_validators
    out = tmp_path / "pz"
    rec = rd.draft(FIRST_E2, E1F_RUN, 250, MESH, out, keep_mesh=True, parent_from_source=True, no_flags=True,
                   drop_kinds=["A/gaps", "B/gap", "C/gap", "B/beam", "A/balance_beams"])
    plan = EX42Plan.load(out / "ex42-prep.yaml")
    row = next(r for r in plan.document["stages"] if r["id"] == "E2")
    assert row["parent"]["source_stage_id"] == "E1F" and row["parent"]["sha256"].startswith("13caeb4ae52d") and row["parent"]["cumulative_update"] == 15500
    assert [r.get("kinds_of") for r in row["terrain"]["exposure_at_E2"]["positive"]] == ["continuous"]
    assert row["shares"]["flag"] == 0.0 and rec["command_shares"]["flag_before"] == 0.1
    assert e_stage_table(plan.document["stages"])["E2"]["previous"] == "E1F"
    assert authorization_validators(plan)["E2"](out / "ex42-approvals.yaml", row["parent"]["sha256"])["scope"]["parent_sha256"] == row["parent"]["sha256"]


@pytest.mark.skipif(not (E1F_RUN / "model_250.pt").is_file() or not (FIRST_E2 / "ex42-prep.yaml").is_file(), reason="canonical 3 run not here")
def test_relocate_mesh_keeps_the_bytes_and_moves_only_the_directory(tmp_path):
    import shutil
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    moved = tmp_path / "mesh"; shutil.copytree(MESH, moved)
    rec = rd.draft(FIRST_E2, E1F_RUN, 250, MESH, tmp_path / "pz", keep_mesh=True, parent_from_source=True, relocate_mesh=moved)
    plan = EX42Plan.load(tmp_path / "pz" / "ex42-prep.yaml")
    assert pinned_stage_mesh(plan.document, "E2")["directory"] == str(moved.resolve()) and rec["relocated_mesh"]["to"] == str(moved.resolve())
    (moved / "mesh_manifest.json").write_text("{}")                                     # other bytes: refused
    with pytest.raises(Exception):
        rd.draft(FIRST_E2, E1F_RUN, 250, MESH, tmp_path / "pz2", keep_mesh=True, parent_from_source=True, relocate_mesh=moved)
    with pytest.raises(ValueError, match="goes with --keep-mesh|already exists"):
        rd.draft(FIRST_E2, E1F_RUN, 250, MESH, tmp_path / "pz3", parent_from_source=True, relocate_mesh=MESH)
