"""E2 -> E3 hand-off (lead 2026-11-16 11:09): the two evidence items the E3 row needed and nobody produced.

(1) boundary_axis: a row with several boundary axes gets the entry axis the PLAN registered before any result (row `boundary.entry_axis`,
    only when it is inside the row's `boundary_axes`); a one-axis row is as before; otherwise no axis is written and materialize refuses.
(2) prerequisites.kind_opening_order_recorded: a fingerprint file of the kind opening order the row registered in the plan
    (`terrain.k_ladder.order`). It says "the order was written down before the results", NOT "these kinds opened": the kinds that actually
    opened are the exposure receipt's `ladder_outcomes` (a different record, made while the stage runs). A bindings manifest that names the
    key wins.
produce() runs for real; only the checks of the predecessor's own exit (validate_source_exit) and the budget lineage are replaced, they need a
real GPU evaluation and belong to the E2 judge and the hand-off tests."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_stage_evidence as evidence
from foothold_s2.curriculum.ex42_prep import EX42Plan

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = ROOT / "foothold_s2" / "curriculum"
SOURCE_OF = {"E3": "E2", "E4": "E3", "E5": "E4"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A copy of the shipped plan and approvals, a predecessor PASS gate with its eval receipt and mesh, a calibration file."""
    plans = tmp_path / "plan"
    shutil.copytree(CURRICULUM, plans, ignore=shutil.ignore_patterns("__pycache__"))          # the plan names its sibling files
    run = tmp_path / "run"
    run.mkdir()
    npz = run / "terrain_mesh.npz"
    npz.write_bytes(b"mesh bytes of the predecessor evaluation")
    manifest = run / "mesh_manifest.json"
    manifest.write_text(json.dumps({"mesh_sha256": "m" * 64, "mesh_file_sha256": sha(npz)}), encoding="utf-8")
    checkpoint = "c" * 64
    (run / "eval_receipt.json").write_text(json.dumps({"state": "done", "checkpoint_sha256": checkpoint,
                                                       "ex42_mesh": {"mesh_npz": str(npz), "manifest": str(manifest), "mesh_sha256": "m" * 64}}),
                                           encoding="utf-8")
    calibration = plans / "calibration.json"                         # a real E2 plan carries the inherited calibration pin; the template has none
    calibration.write_text(json.dumps({"fixture": "calibration"}), encoding="utf-8")
    document = yaml.safe_load((plans / "ex42-prep.yaml").read_text(encoding="utf-8"))
    document["evaluation"]["flag_cells"]["calibration"] = {"path": "calibration.json", "sha256": sha(calibration)}
    (plans / "ex42-prep.yaml").write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
    gate = run / "p1_score.json"
    monkeypatch.setattr(evidence, "validate_source_exit", lambda *a, **k: None)           # needs a real GPU evaluation
    import foothold_s2.ex42_stage_handoff as handoff
    monkeypatch.setattr(handoff, "measured_budget", lambda *a, **k: {"limit": 1, "used": 0, "basis": "fixture"})

    class World:
        pass

    w = World()
    w.plan_path, w.run, w.gate, w.calibration, w.checkpoint, w.tmp = plans / "ex42-prep.yaml", run, gate, calibration, checkpoint, tmp_path

    def make_gate(source_stage):
        plan = EX42Plan.load(w.plan_path)
        gate.write_text(json.dumps({"state": "complete", "judgment": "PASS", "plan_sha256": plan.sha256, "stage_id": source_stage,
                                    "checkpoint_sha256": checkpoint}), encoding="utf-8")
        return gate

    def mutate(change):
        """Edit the plan copy (the gate then names the new plan sha)."""
        document = yaml.safe_load(w.plan_path.read_text(encoding="utf-8"))
        change({row["id"]: row for row in document["stages"]})
        w.plan_path.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def run_produce(target, out_name="out", bindings=None):
        make_gate(SOURCE_OF[target])
        path = None
        if bindings is not None:
            path = w.tmp / "bindings.json"
            path.write_text(json.dumps({target: bindings}), encoding="utf-8")
        return evidence.produce(template_path=w.plan_path, source_path=w.plan_path, target=target, gate_path=gate,
                                manifest_path=w.run / "manifest.json", output_dir=w.tmp / out_name, bindings_path=path)

    w.make_gate, w.mutate, w.produce = make_gate, mutate, run_produce
    return w


def body(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def row_of(w, stage_id):
    return next(r for r in yaml.safe_load(w.plan_path.read_text(encoding="utf-8"))["stages"] if r["id"] == stage_id)


# ---------- (1) boundary_axis ----------

@pytest.mark.parametrize("target, axis", [("E3", "terrain_kind_level_cap"), ("E4", "terrain_exposure"), ("E5", "terrain_exposure")])
def test_a_multi_axis_row_gets_the_axis_its_plan_registered_as_entry_axis(world, target, axis):
    row = row_of(world, target)
    assert len(row["boundary_axes"]) > 1 and row["boundary"]["entry_axis"] == axis       # the registered value, not a choice made here
    assert body(world.produce(target))["boundary_axis"] == axis


def test_an_entry_axis_outside_the_row_axes_or_missing_writes_no_axis(world):
    world.mutate(lambda rows: rows["E3"]["boundary"].update(entry_axis="posture_height"))
    assert "boundary_axis" not in body(world.produce("E3", "outside"))
    world.mutate(lambda rows: rows["E3"].pop("boundary"))
    assert "boundary_axis" not in body(world.produce("E3", "missing"))


def test_a_one_axis_row_is_written_exactly_as_before(world):
    world.mutate(lambda rows: rows["E4"].update(boundary_axes=["terrain_exposure"]))
    out = world.produce("E4")
    document = body(world.tmp / "out" / Path(out).name)
    assert document["boundary_axis"] == "terrain_exposure" and set(document) == {
        "format", "target_stage", "source_stage", "source_plan_sha256", "gate_sha256", "checkpoint_sha256", "bindings", "budget_observed",
        "boundary_axis"}
    assert set(document["bindings"]) == {"prerequisites.calibration_sha256", "prerequisites.predecessor_exit.evaluation_mesh_sha256"}            # no kind-order file for a row that does not ask for it
    assert not list((world.tmp / "out").glob("kind_opening_order_*"))


# ---------- (2) kind_opening_order_recorded ----------

def test_the_opening_order_file_is_the_plan_order_and_its_sha_is_the_binding_value(world):
    out = Path(world.produce("E3"))
    document = body(out)
    ref = document["bindings"]["prerequisites.kind_opening_order_recorded"]
    order = row_of(world, "E3")["terrain"]["k_ladder"]["order"]
    record = body(ref["path"])
    expected = hashlib.sha256(json.dumps(order, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    assert record["order"] == order and record["order_sha256"] == expected == body(ref["path"])["order_sha256"]
    assert ref["pointer"] == "order_sha256" and ref["sha256"] == sha(ref["path"]) and len(order) == 12
    assert record["format"] == evidence.KIND_ORDER_FORMAT and record["target_stage"] == "E3"


def test_the_same_inputs_give_the_same_file_and_a_different_order_gives_a_different_sha(world):
    first = body(body(world.produce("E3", "one"))["bindings"]["prerequisites.kind_opening_order_recorded"]["path"])
    again = world.produce("E3", "one")                                                       # same folder again: identical, not "differs"
    assert body(body(again)["bindings"]["prerequisites.kind_opening_order_recorded"]["path"]) == first
    world.mutate(lambda rows: rows["E3"]["terrain"]["k_ladder"]["order"].reverse())
    swapped = body(body(world.produce("E3", "two"))["bindings"]["prerequisites.kind_opening_order_recorded"]["path"])
    assert swapped["order_sha256"] != first["order_sha256"] and swapped["order"] == list(reversed(first["order"]))


def test_an_existing_order_file_that_differs_is_never_overwritten(world):
    world.produce("E3", "keep")
    target = world.tmp / "keep" / "kind_opening_order_E3.json"
    target.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="never overwrite"):
        world.produce("E3", "keep")


def test_a_bindings_manifest_that_names_the_key_wins_and_no_file_is_written(world):
    given = world.tmp / "recorded_elsewhere.json"
    given.write_text(json.dumps({"kind_order": "supplied-by-the-manifest"}), encoding="utf-8")
    document = body(world.produce("E3", "manifest", bindings={
        "prerequisites.kind_opening_order_recorded": {"path": str(given), "sha256": sha(given), "pointer": "kind_order"}}))
    assert document["bindings"]["prerequisites.kind_opening_order_recorded"]["path"] == str(given)
    assert not (world.tmp / "manifest" / "kind_opening_order_E3.json").exists()


def test_a_row_without_a_registered_order_is_refused_and_publishes_nothing(world):
    world.mutate(lambda rows: rows["E3"]["terrain"]["k_ladder"].pop("order"))
    with pytest.raises(ValueError, match="registers no kind opening order"):
        world.produce("E3", "none")
    assert not (world.tmp / "none").exists()


def test_the_comment_and_the_names_say_what_the_record_is_not():
    """The wording is part of the contract: recorded-in-the-plan, not the kinds that opened (ladder_outcomes)."""
    doc = evidence.kind_opening_order_file.__doc__
    assert "BEFORE any result" in doc and "ladder_outcomes" in doc and "does not say: which kinds actually" in doc


def test_the_shipped_approval_cell_stays_null_and_is_filled_by_materialize_not_by_the_template():
    approvals = yaml.safe_load((CURRICULUM / "ex42-approvals.yaml").read_text(encoding="utf-8"))
    assert approvals["stage_e3_authorization"]["prerequisites"]["kind_opening_order_recorded"] is None
    assert approvals["stage_e3_authorization"]["boundary"]["axis"] is None             # both are filled in the materialized copy
    source = (ROOT / "foothold_s2" / "ex42_stage_materialize.py").read_text(encoding="utf-8")
    assert "_put(cell,key,value)" in source and "cell['boundary']['axis']=axis" in source


# ---------- the real E3 materialize path (chain: real E1F -> E2 materialize, then an E2 PASS gate) ----------

from foothold_s2.tests.test_ex42_auto_handoff_cpu import e1f_exit, known, ready      # noqa: E402,F401  (fixtures)


@pytest.fixture
def e2_exit(e1f_exit, tmp_path, monkeypatch):
    """The E2 plan really materialized from the E1F exit, and an E2 PASS gate at update 250. What stays replaced: the E2 judge's own verdict
    (validate_source_exit / validate_score_pair need a GPU evaluation) and the budget lineage."""
    from foothold_s2 import ex42_stage_handoff as handoff
    from foothold_s2 import ex42_stage_materialize as sm

    source, approval, manifest, gate, bindings = e1f_exit
    env = {"EX42_MATERIALIZE_TEMPLATE_PLAN": str(source.path), "EX42_MATERIALIZE_TEMPLATE_APPROVALS": str(approval),
           "EX42_MATERIALIZE_EVIDENCE_DIR": str(tmp_path / "generated"), "EX42_MATERIALIZE_OUT_ROOT": str(tmp_path / "transitions"),
           "EX42_MATERIALIZE_BINDINGS_FILE": str(bindings)}
    decision = handoff.decide_next_stage(source.path, approval, "E1F", 500, gate, manifest, materialize=handoff.materializer_from_env(env))
    assert decision["action"] == "launch" and decision["target_stage"] == "E2", decision
    e2_plan, e2_approvals = EX42Plan.load(decision["plan"]), Path(decision["approvals"])
    run = tmp_path / "e2-run"
    run.mkdir()
    checkpoint = run / "model_250.pt"
    checkpoint.write_bytes(b"CPU fixture E2 m250")
    parent_manifest = run / "manifest.json"
    parent_manifest.write_text(json.dumps({"progress": {"completed_updates": 250}, "checkpoints": {checkpoint.name: sha(checkpoint)}}), encoding="utf-8")
    mesh = json.loads((gate.parent / "eval_receipt.json").read_text(encoding="utf-8"))["ex42_mesh"]
    (run / "eval_receipt.json").write_text(json.dumps({"state": "running", "checkpoint_sha256": sha(checkpoint), "ex42_mesh": mesh}), encoding="utf-8")
    e2_gate = run / "p1_score.json"
    e2_gate.write_text(json.dumps({"state": "complete", "judgment": "PASS", "plan_sha256": e2_plan.sha256, "stage_id": "E2",
                                   "checkpoint_iteration": 250, "checkpoint_sha256": sha(checkpoint)}), encoding="utf-8")
    monkeypatch.setattr(evidence, "validate_source_exit", lambda *a, **k: None)
    monkeypatch.setattr(sm, "validate_source_exit", lambda *a, **k: None)
    monkeypatch.setattr(sm, "validate_score_pair", lambda **k: None)
    monkeypatch.setattr(handoff, "measured_budget", lambda *a, **k: {"limit": 20000, "used": 0, "basis": "fixture"})

    class Exit:
        pass

    x = Exit()
    x.plan, x.approvals, x.manifest, x.gate, x.tmp = e2_plan, e2_approvals, parent_manifest, e2_gate, tmp_path
    return x


def _materialize_e3(x, evidence_path, name):
    from foothold_s2 import ex42_stage_materialize as sm
    return sm.materialize(plan=x.plan.path, source_plan=x.plan.path, approvals=x.approvals, target="E3", parent_manifest=x.manifest,
                          gate_receipt=x.gate, evidence=evidence_path, budget_limit=20000, budget_used=0, budget_basis="fixture",
                          out=x.tmp / "e3-out" / name)


def test_e3_materializes_from_the_produced_evidence_and_the_approval_cell_is_filled_by_it(e2_exit):
    out = evidence.produce(template_path=e2_exit.plan.path, source_path=e2_exit.plan.path, target="E3", gate_path=e2_exit.gate,
                           manifest_path=e2_exit.manifest, output_dir=e2_exit.tmp / "e3-evidence")
    made = _materialize_e3(e2_exit, out, "ok")
    approvals = yaml.safe_load(Path(made["approvals"]).read_text(encoding="utf-8"))["stage_e3_authorization"]
    order = row_of_plan(e2_exit.plan, "E3")["terrain"]["k_ladder"]["order"]
    expected = hashlib.sha256(json.dumps(order, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    assert approvals["boundary"]["axis"] == "terrain_kind_level_cap"
    assert approvals["prerequisites"]["kind_opening_order_recorded"] == expected               # the template's null was filled in the copy
    # the shipped template is untouched (its sha is the plan sha the S4 rehearsal pins)
    assert sha(CURRICULUM / "ex42-prep.yaml") == EX42Plan.load(CURRICULUM / "ex42-prep.yaml").sha256
    from foothold_s2.curriculum.ex42_prep import EX42Plan as P, validate_stage_authorization
    plan = P.load(made["plan"])
    proof = validate_stage_authorization(plan, made["approvals"], approvals["scope"]["parent_sha256"], stage_id="E3")
    assert proof["state"].startswith("stage_e3")


def row_of_plan(plan, stage_id):
    return next(r for r in plan.document["stages"] if r["id"] == stage_id)


def test_without_the_entry_axis_materialize_refuses_with_the_old_message(e2_exit):
    out = evidence.produce(template_path=e2_exit.plan.path, source_path=e2_exit.plan.path, target="E3", gate_path=e2_exit.gate,
                           manifest_path=e2_exit.manifest, output_dir=e2_exit.tmp / "e3-evidence")
    document = json.loads(Path(out).read_text(encoding="utf-8"))
    document.pop("boundary_axis")                                                          # what the evidence looked like before this change
    stripped = Path(out).with_name("E3_no_axis.json")
    stripped.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="multi-axis boundary needs a declared allowed axis"):
        _materialize_e3(e2_exit, stripped, "no-axis")


def test_without_the_order_binding_evidence_cannot_even_be_produced(e2_exit, monkeypatch):
    monkeypatch.setattr(evidence, "kind_opening_order_file", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not be needed")))
    monkeypatch.setattr(evidence, "KIND_ORDER_KEY", "prerequisites.something_else")           # the producer no longer knows the key
    with pytest.raises(ValueError, match="missing measured producers: prerequisites.kind_opening_order_recorded"):
        evidence.produce(template_path=e2_exit.plan.path, source_path=e2_exit.plan.path, target="E3", gate_path=e2_exit.gate,
                         manifest_path=e2_exit.manifest, output_dir=e2_exit.tmp / "e3-evidence-none")
