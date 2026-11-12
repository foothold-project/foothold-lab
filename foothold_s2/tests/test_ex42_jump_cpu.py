"""J0~J4 (DESIGN-JUMP v0.2 s2.2): the jump stages in the EX-42 table, their closed approval cells, the family F entry
contract (mesh families, kind_task, column kinds) and the exposure of every J stage on a table with F columns.
The F generator is the analyst's `foothold_s2.terrains.jump_preset` (#710); kind names, stage openings and level dims are read
from it, never retyped. No Kit, no GPU."""
from __future__ import annotations

import copy

import numpy as np
import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import (
    JUMP_SHARE_CAP, JUMP_STAGE_IDS, RUNTIME_STAGE_IDS, STAGE_IDS, EX42Plan, authorization_validators)
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.terrains import ex42_exposure as ex
from foothold_s2.terrains import jump_preset
from foothold_s2.terrains.ex42_k_ladder import ladder_terrain
from foothold_s2.tests.test_ex42_exposure_cpu import PLAN, REAL

needs_mesh = pytest.mark.skipif(not (REAL / "terrain_mesh.npz").is_file(), reason="real mesh missing")
APPROVALS = PLAN.parent / "ex42-approvals.yaml"
F_KINDS = list(jump_preset.KINDS)
UP_LOW, DOWN_LOW, GAP, UP_HIGH = F_KINDS


def _doc():
    return yaml.safe_load(PLAN.read_text(encoding="utf-8-sig"))


def _rows():
    return {row["id"]: row for row in _doc()["stages"]}


def test_the_table_carries_j0_to_j4_after_e6b_all_disabled_and_the_ex42_runtime_list_is_unchanged():
    ids = [row["id"] for row in _doc()["stages"]]
    assert ids == list(STAGE_IDS + JUMP_STAGE_IDS) and ids[9] == "E6b"
    assert RUNTIME_STAGE_IDS[-1] == "E6b" and len(RUNTIME_STAGE_IDS) == 11            # EX-42 itself is not extended
    assert EX42Plan.load(PLAN).runtime_stage_ids == RUNTIME_STAGE_IDS                 # the approved DR schedule has no J scale
    rows = _rows()
    for sid in JUMP_STAGE_IDS:
        assert rows[sid]["enabled"] is False and rows[sid]["jump"] is True and "assumption" in rows[sid]
        assert "parent" not in rows[sid]                                              # the parent pin is written by materialize
    chain = ["E6b", *JUMP_STAGE_IDS]
    for before, sid in zip(chain, chain[1:]):
        assert rows[sid]["authorization_contract"]["source_stage_ids"] == [before]
        assert rows[sid]["authorization_contract"]["required_values"]["prerequisites.predecessor_exit.stage_id"] == before


def test_the_approval_cells_are_closed_so_no_jump_stage_can_start_by_itself():
    approvals = yaml.safe_load(APPROVALS.read_text(encoding="utf-8-sig"))
    plan = EX42Plan.load(PLAN)
    validators = authorization_validators(plan)
    for sid in JUMP_STAGE_IDS:
        cell = approvals[f"stage_{sid.lower()}_authorization"]
        assert cell["approved"] is False and cell["decision_id"] is None and cell["extension_authorized"] is False
        assert cell["scope"]["stage_id"] == sid and cell["scope"]["later_stages_authorized"] is False
        with pytest.raises(ValueError, match="missing or not approved"):
            validators[sid](APPROVALS, None)


def test_the_ladders_are_the_design_dimensions_and_each_stage_opens_only_its_own_kinds():
    rows = _rows()
    ladder = rows["J0"]["terrain"]["jump_ladder"]
    assert set(ladder) == set(jump_preset.LEVEL_VALUES_M)
    for kind, spec in ladder.items():                                                 # dims come from the generator, not from prep
        assert spec["levels"] == pytest.approx(list(jump_preset.LEVEL_VALUES_M[kind])), kind
        assert spec["opens_in"] == jump_preset.STAGES[kind], kind
    assert {k: v["axis"] for k, v in ladder.items()} == {UP_LOW: "height", DOWN_LOW: "height", GAP: "width", UP_HIGH: "height"}
    for spec in ladder.values():
        assert spec["levels"] == sorted(set(spec["levels"]))
    assert set(rows["J0"]["terrain"]["kind_task"]) == {"F"} and set(rows["J0"]["terrain"]["kind_task"]["F"]) == set(F_KINDS)
    opened = {sid: [r["kind"] for r in rows[sid]["terrain"][f"exposure_at_{sid}"]["positive"] if r.get("family") == "F"]
              for sid in JUMP_STAGE_IDS}
    assert opened == {"J0": [], "J1": [], "J2": [UP_LOW], "J3": [UP_LOW, DOWN_LOW, GAP], "J4": [UP_LOW, DOWN_LOW, GAP, UP_HIGH]}
    for sid, kinds in opened.items():                                                 # nothing is exposed before its generator stage
        assert all(jump_preset.STAGES[k] <= sid for k in kinds), (sid, kinds)
    for sid in JUMP_STAGE_IDS:                                                       # a new jump kind starts at its lowest level
        for rule in rows[sid]["terrain"][f"exposure_at_{sid}"]["positive"]:
            if rule.get("family") == "F":
                assert rule["level_cap"] == 0 and rule["share"] in (0.05, 0.015)
    assert rows["J2"]["terrain"]["k_ladder"]["order"] == [{"family": "F", "kind": DOWN_LOW, "level_cap": 0}]


def test_height_and_gap_never_rise_at_one_boundary_and_the_plan_refuses_a_table_that_does():
    doc = _doc()
    for sid in JUMP_STAGE_IDS:
        axes = _rows()[sid]["boundary_axes"]
        assert not {"jump_height_cap", "jump_gap_cap"} <= set(axes)
    cases = {"J2": ("boundary_axes", ["jump_height_cap", "jump_gap_cap"], "same boundary|boundary axes"),
             "J3": ("enabled", True, "disabled"),
             "J1": ("boundary_axes", ["terrain_level"], "boundary axes")}
    for sid, (key, value, message) in cases.items():
        bad = copy.deepcopy(doc)
        next(r for r in bad["stages"] if r["id"] == sid)[key] = value
        with pytest.raises(ValueError, match=message):
            _load(bad)
    over = copy.deepcopy(doc)
    rules = next(r for r in over["stages"] if r["id"] == "J4")["terrain"]["exposure_at_J4"]["positive"]
    next(r for r in rules if r.get("kind") == UP_HIGH)["share"] = JUMP_SHARE_CAP
    with pytest.raises(ValueError, match="over 0.2"):
        _load(over)


def _load(doc):
    import tempfile
    from pathlib import Path
    folder = Path(tempfile.mkdtemp())
    for source in PLAN.parent.iterdir():
        if source.is_file():
            (folder / source.name).write_bytes(source.read_bytes())
    (folder / PLAN.name).write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return EX42Plan.load(folder / PLAN.name)


def test_the_mesh_families_are_six_for_the_jump_stages_and_five_for_the_rest():
    assert entry.required_mesh_families("E6b") == tuple("ABCDE") and entry.required_mesh_families("E0") == tuple("ABCDE")
    for sid in JUMP_STAGE_IDS:
        assert entry.required_mesh_families(sid) == tuple("ABCDEF")
    from foothold_s2.runners.map_switch import NON_A_FAMILIES
    assert "F" in NON_A_FAMILIES                                                      # F is a non-A family for the map switch


def test_kind_task_adds_family_f_for_the_jump_stages_only_and_f_kinds_gate_the_push_off():
    plan = EX42Plan.load(PLAN)
    assert "F" not in entry._kind_task(plan, "E6b") and "F" not in entry._kind_task(plan)
    for sid in JUMP_STAGE_IDS:
        merged = entry._kind_task(plan, sid)
        assert set(merged["F"]) == set(F_KINDS) and "stones" in merged["B"]            # E0's kinds stay
        assert entry.e0_push_off_kinds(plan, sid)["F"] == set(F_KINDS)
    assert "F" not in entry.e0_push_off_kinds(plan)
    doc = _doc()
    del next(r for r in doc["stages"] if r["id"] == "J0")["terrain"]["kind_task"]
    with pytest.raises(ValueError, match="family F kinds"):
        entry._kind_task(_load(doc), "J2")


def test_family_f_columns_are_named_from_the_generator_module():
    assert cr.family_column_kinds("F", 4) == F_KINDS
    assert [r["kind"] for r in cr.build_column_table(["F"] * 4, {})] == F_KINDS
    assert cr.FAMILY_KIND_SOURCES["F"] == ("foothold_s2.terrains.jump_preset", "KINDS")
    assert cr.kind_ranges_of("F") == dict(jump_preset.RESET_RANGES)


def test_the_plans_f_kinds_are_the_generators_kinds():
    plan_kinds = {r["kind"] for sid in JUMP_STAGE_IDS for r in _rows()[sid]["terrain"][f"exposure_at_{sid}"]["positive"]
                  if r.get("family") == "F"}
    assert plan_kinds == set(F_KINDS) and set(_rows()["J0"]["terrain"]["kind_task"]["F"]) == set(F_KINDS)


@needs_mesh
@pytest.mark.parametrize("stage", JUMP_STAGE_IDS)
def test_every_jump_stage_resolves_on_a_table_with_f_columns_inside_the_share_floors_at_every_boundary(stage):
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    families = [str(v) for v in data["column_family"]] + ["F"] * 4
    table = cr.build_column_table(families)
    rows = _rows()
    base = {**rows[stage]["terrain"], "kind_task": entry._kind_task(EX42Plan.load(PLAN), stage)}
    boundaries = 2 if rows[stage]["terrain"].get("k_ladder") else 0
    for k in range(boundaries + 1):
        terrain, _ = ladder_terrain(base, stage, k)
        exposure, caps = ex.exposure_by_column(terrain, table, stage)
        shares = ex.column_shares(terrain, table, stage)
        sparse = sum(s for s in shares if s)
        jump = sum(s for s, row in zip(shares, table) if row["family"] == "F" and s)
        assert 0.0 < sparse <= 0.571 + 1e-9 and 1.0 - sparse >= 0.429 - 1e-9, (stage, k, sparse)
        assert jump <= JUMP_SHARE_CAP + 1e-9, (stage, k, jump)
        assert sum(ex.env_counts(6144, exposure)[1].tolist()) == 6144
        for column, row in enumerate(table):
            if row["family"] == "F":
                assert caps[column] == 0                                              # a jump kind starts at its lowest level


@pytest.fixture
def adopted():
    saved = {k: dict(v) for k, v in entry.E_STAGE_SPECS.items()}
    yield
    entry.E_STAGE_SPECS.clear()
    entry.E_STAGE_SPECS.update(saved)
    entry.E_STAGES.clear()
    entry.E_STAGES.update({k: (v["updates"], v["parent_local"], v["parent_cumulative"]) for k, v in saved.items()})


def test_a_jump_stage_with_a_parent_pin_is_startable_and_the_launcher_builds_its_dry_and_real_commands(tmp_path, adopted):
    """The shipped table has no parent pin for J (materialize writes it from the finished predecessor). With a pin the stage
    table adopts it, the launcher builds the --ex42_stage_dry_run command and the real command from the pair, and an
    approval that is still closed does not stop the build (the closed cell stops the hand-off, see the cells test)."""
    from foothold_s2.scripts import ex42_stage_launcher as L
    from foothold_s2.tests.test_ex42_stage_launcher_cpu import _env, _flag
    doc = _doc()
    row = next(r for r in doc["stages"] if r["id"] == "J2")
    row["parent"] = {"cumulative_update": 32000, "manifest_local_update": 20000, "sha256": "ab" * 32,
                     "checkpoint_key": "model_20000"}
    plan = tmp_path / "ex42-prep.yaml"
    plan.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    approvals = tmp_path / "ex42-approvals.yaml"
    approvals.write_bytes(APPROVALS.read_bytes())
    table = entry.adopt_plan_stage_table(plan)
    assert "J2" in table and "J1" not in table and table["J2"]["critic_mirror"] is True and table["J2"]["updates"] == 2000
    assert entry._stage_caps("J2") == {2000, 3000, 4000}
    env = _env(tmp_path, stage="J2")
    env.update(EX42_AUTO_PLAN=str(plan), EX42_AUTO_APPROVALS=str(approvals))
    for dry in (True, False):
        argv, _, summary = L.build(env, dry_run=dry, now=0)
        assert _flag(argv, "--ex42_stage") == "J2" and _flag(argv, "--max_iterations") == "2000"
        assert ("--ex42_stage_dry_run" in argv) is dry and _flag(argv, "--ex42_plan") == str(plan)
    assert summary["updates"] == 2000


# ---- the chain order: J sits outside the EX-42 sequence, so E6b has no following stage (reviewer: handoff block) ----
def _gate_and_manifest(tmp_path, iteration, judgment="PASS"):
    import hashlib
    import json
    tmp_path.mkdir(parents=True, exist_ok=True)
    data = b"boundary save"
    (tmp_path / f"model_{iteration}.pt").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"checkpoints": {f"model_{iteration}.pt": digest}, "progress": {"completed_updates": iteration}}))
    measured = tmp_path / "ex42_score.json"
    measured.write_text(json.dumps({"maintenance_judgement": "PASS"}))
    gate = tmp_path / "p1.json"
    gate.write_text(json.dumps({"judgment": judgment, "checkpoint_sha256": digest, "measurement": str(measured),
                                "measurement_sha256": hashlib.sha256(measured.read_bytes()).hexdigest()}))
    return gate, manifest


def _document_order_without_j():
    return [r["id"] for r in _doc()["stages"] if r["id"] not in JUMP_STAGE_IDS]


def test_every_runtime_stage_is_followed_by_the_next_runtime_stage_and_e6b_by_none_in_both_callers(tmp_path):
    from foothold_s2 import ex42_eval_once as once
    from foothold_s2 import ex42_stage_handoff as handoff
    plan = EX42Plan.load(PLAN)
    order = _document_order_without_j()
    assert list(plan.runtime_stage_ids)[1:] == order and order[-1] == "E6b"
    for i, sid in enumerate(order):
        expected = order[i + 1] if i + 1 < len(order) else None
        assert plan.following_stage_id(sid) == expected, sid
        minimum = _rows()[sid]["minimum_updates"]
        gate, manifest = _gate_and_manifest(tmp_path / sid, minimum)
        notice = once.next_stage_notice(plan, sid, minimum, {"judgment": "PASS", "checkpoint_sha256": "a" * 64})
        decision = handoff.decide_next_stage(plan, APPROVALS, sid, minimum, gate, manifest)
        assert notice["next_stage_id"] == expected and (decision is None or decision["next_stage_id"] == expected), sid
        if sid != "E6b":
            assert notice["state"] == "next_stage_ready_for_approval"
    assert plan.following_stage_id("J0") == "J1" and plan.following_stage_id("J4") is None


def test_e6b_pass_at_its_minimum_goes_on_with_the_same_stage_never_to_the_closed_j0(tmp_path):
    from foothold_s2 import ex42_eval_once as once
    from foothold_s2 import ex42_stage_handoff as handoff
    from foothold_s2.tests.test_ex42_table_authorization_cpu import fixture
    (tmp_path / "fx").mkdir()
    plan, approvals, _ = fixture(tmp_path / "fx", "E6b")
    from copy import deepcopy
    from dataclasses import replace
    doc = deepcopy(plan.document)
    row = next(r for r in doc["stages"] if r["id"] == "E6b")
    row["parent"] = {"sha256": "b" * 64, "manifest_local_update": 1500, "cumulative_update": 20000, "checkpoint_key": "model_1500.pt"}
    plan = replace(plan, document=doc)
    minimum = row["minimum_updates"]
    gate, manifest = _gate_and_manifest(tmp_path / "run", minimum)
    decision = handoff.decide_next_stage(plan, approvals, "E6b", minimum, gate, manifest)
    assert decision["next_stage_id"] is None and decision["action"] != "launch"
    assert decision["state"] != "next_stage_ready_for_approval" and decision.get("target_stage") in (None, "E6b")
    assert decision["action"] == "continue", decision
    notice = once.next_stage_notice(plan, "E6b", minimum, {"judgment": "PASS", "checkpoint_sha256": "a" * 64})
    assert notice["next_stage_id"] is None and notice["state"] == "not_ready"


def test_a_jump_mesh_family_in_a_non_jump_stage_is_refused_and_a_jump_stage_needs_it(monkeypatch, tmp_path):
    from foothold_s2.terrains import ex42_mesh_mount as mount
    families = {"now": list("ABCDEF")}
    from foothold_s2 import ex42_stage_mesh                    # the pinned-mesh guard has its own tests (test_ex42_stage_mesh_cpu)
    monkeypatch.setattr(ex42_stage_mesh, "pinned_stage_mesh", lambda document, stage: None)
    monkeypatch.setattr(mount, "expected_sha_from_manifest", lambda path: "0" * 64)
    monkeypatch.setattr(mount, "load_combined_mesh", lambda npz, sha: {"column_family": np.array(families["now"])})
    plan = EX42Plan.load(PLAN)
    for sid in ("E0", "E3", "E6b"):
        with pytest.raises(ValueError, match="only the jump stages use"):
            entry.prepare_e0_env_cfg(None, plan, tmp_path, sid)
    families["now"] = list("ABCDE")
    with pytest.raises(ValueError, match="lacks families.*F"):
        entry.prepare_e0_env_cfg(None, plan, tmp_path, "J2")
