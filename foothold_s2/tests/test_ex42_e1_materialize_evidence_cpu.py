from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from foothold_s2.scripts.ex42_e1_materialize_evidence import build_evidence


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, row: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fixture(tmp_path: Path):
    import foothold_s2.curriculum.ex42_prep as prep
    plan = prep.EX42Plan.load(PLAN)
    approval_sha = plan.document["stage_zero"]["approval_sha256"]
    run = tmp_path / "run"
    run.mkdir()
    checkpoint = run / "model_1750.pt"
    checkpoint.write_bytes(b"known E1 checkpoint")
    cp_sha = _sha(checkpoint)
    _write(run / "manifest.json", {"progress": {"completed_updates": 1750},
                                    "checkpoints": {checkpoint.name: cp_sha}})
    measurement = _write(run / "eval/m1000/measurement.json", {
        "checkpoint_sha256": cp_sha, "judgement": "PASS",
        "maintenance_source_sha256": plan.sha256})
    gate = _write(run / "eval/m1000/p1_score.json", {
        "state": "complete", "stage_id": "E1", "judgment": "PASS", "plan_sha256": plan.sha256,
        "checkpoint_iteration": 1750, "checkpoint_sha256": cp_sha,
        "measurement": str(measurement), "measurement_sha256": _sha(measurement)})
    log = run / "torchrun.stdout.log"
    rows = []
    for rank in range(2):
        preflight = {"stage_id": "E1", "rank": rank, "world_size": 2,
                     "output_dir": str(run if rank == 0 else run / "rank1"),
                     "approval": {"approvals_sha256": approval_sha}}
        exposure = {"envs": 3072, "exposed_columns": [0, 1],
                    "level_caps": [5, 5], "start": "parent_env_state"}
        rows.extend(("EX42_STAGE_E1_PREFLIGHT " + json.dumps(preflight),
                     "EX42_E0_EXPOSURE " + json.dumps(exposure)))
    log.write_text("\n".join(rows) + "\n", encoding="utf-8")
    mesh_npz = tmp_path / "mesh" / "terrain_mesh.npz"
    mesh_npz.parent.mkdir(parents=True)
    mesh_npz.write_bytes(b"registered E0 mesh")
    mesh_sha = plan.document["assumptions_pending_lead"]["terrain_manifest_measurements"]["value"]["mesh_sha256"]
    _write(mesh_npz.parent / "mesh_manifest.json", {
        "format": "foothold-ex42-combined-mesh/1", "seed": 42,
        "mesh_sha256": mesh_sha, "mesh_file_sha256": _sha(mesh_npz)})
    baseline = _write(tmp_path / "w09_baseline.json", {"state": "measured", "threshold": 0.5})
    return plan, run, gate, log, mesh_npz, baseline, cp_sha


def test_e1f_materialize_evidence_binds_training_cap_gate_mesh_and_w09_baseline(tmp_path):
    plan, run, gate, log, mesh, baseline, cp_sha = _fixture(tmp_path)
    evidence = build_evidence(source_plan_path=PLAN, parent_manifest_path=run / "manifest.json",
                              gate_receipt_path=gate, training_log_path=log,
                              evaluation_mesh_path=mesh, w09_baseline_path=baseline)
    assert evidence["format"] == "foothold-ex42-materialize-evidence/1"
    assert evidence["source_plan_sha256"] == plan.sha256
    assert evidence["source_stage"] == "E1" and evidence["target_stage"] == "E1F"
    assert evidence["checkpoint_sha256"] == cp_sha
    assert evidence["gate_sha256"] == _sha(gate)
    assert "evaluation_plan" not in evidence  # source and measured policy are the same plan
    assert evidence["applied_level_cap"] == 5
    assert evidence["exposure_receipt"] == {"path": str(log.resolve()), "sha256": _sha(log)}
    assert evidence["bindings"]["prerequisites.flag_baseline.sha256"] == {
        "path": str(baseline.resolve()), "sha256": _sha(baseline)}
    assert evidence["bindings"]["prerequisites.predecessor_exit.evaluation_mesh_sha256"] == {
        "path": str(mesh.resolve()), "sha256": _sha(mesh)}


@pytest.mark.parametrize("iteration", [250, 1000, 1500, 1900, 3000])
def test_e1f_evidence_is_built_only_from_an_e1_exit_boundary(tmp_path, iteration):
    """CG v0.17j: E1 hands over at 1750 or at a boundary of its HOLD extensions (to 2750), never earlier or off a boundary."""
    _plan, run, gate, log, mesh, baseline, _cp_sha = _fixture(tmp_path)
    row = json.loads(gate.read_text())
    row["checkpoint_iteration"] = iteration
    gate.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="E1 exit boundary"):
        build_evidence(source_plan_path=PLAN, parent_manifest_path=run / "manifest.json",
                       gate_receipt_path=gate, training_log_path=log,
                       evaluation_mesh_path=mesh, w09_baseline_path=baseline)


@pytest.mark.parametrize("mutation", ["gate", "cap_rank", "missing_baseline", "mesh"])
def test_e1f_evidence_rejects_unbound_or_incomplete_sources(tmp_path, mutation):
    _plan, run, gate, log, mesh, baseline, _cp_sha = _fixture(tmp_path)
    if mutation == "gate":
        row = json.loads(gate.read_text())
        row["checkpoint_sha256"] = "0" * 64
        gate.write_text(json.dumps(row), encoding="utf-8")
    elif mutation == "cap_rank":
        log.write_text(log.read_text().replace('"level_caps": [5, 5]', '"level_caps": [4, 5]', 1), encoding="utf-8")
    elif mutation == "missing_baseline":
        baseline.unlink()
    elif mutation == "mesh":
        (mesh.parent / "mesh_manifest.json").write_text('{"format":"wrong","seed":42}', encoding="utf-8")
    with pytest.raises((ValueError, OSError)):
        build_evidence(source_plan_path=PLAN, parent_manifest_path=run / "manifest.json",
                       gate_receipt_path=gate, training_log_path=log,
                       evaluation_mesh_path=mesh, w09_baseline_path=baseline)


def test_e1f_evidence_separates_source_plan_from_evaluation_plan(tmp_path):
    plan, run, gate, log, mesh, baseline, cp_sha = _fixture(tmp_path)
    eval_dir = tmp_path / "evaluation-plan"
    eval_dir.mkdir()
    source_template = PLAN.parent / "ex41-fixed5000.yaml"
    (eval_dir / source_template.name).write_bytes(source_template.read_bytes())
    for dependency in ("ex42-boundary.yaml", "ex42-approvals.yaml"):
        (eval_dir / dependency).write_bytes((PLAN.parent / dependency).read_bytes())
    evaluation_plan = eval_dir / PLAN.name
    evaluation_plan.write_bytes(PLAN.read_bytes() + b"\n# D44 evaluation contract copy\n")
    evaluation_sha = _sha(evaluation_plan)
    measurement_path = Path(json.loads(gate.read_text())["measurement"])
    measured = json.loads(measurement_path.read_text())
    measured["maintenance_source_sha256"] = evaluation_sha
    _write(measurement_path, measured)
    gate_row = json.loads(gate.read_text())
    gate_row["measurement_sha256"] = _sha(measurement_path)
    gate.write_text(json.dumps(gate_row), encoding="utf-8")

    evidence = build_evidence(source_plan_path=PLAN, evaluation_plan_path=evaluation_plan,
                              parent_manifest_path=run / "manifest.json", gate_receipt_path=gate,
                              training_log_path=log, evaluation_mesh_path=mesh,
                              w09_baseline_path=baseline)
    assert evidence["source_plan_sha256"] == plan.sha256
    assert evidence["evaluation_plan"] == {
        "path": str(evaluation_plan.resolve()), "sha256": evaluation_sha}
    assert evidence["checkpoint_sha256"] == cp_sha


def test_e1f_evidence_rejects_nonpass_measurement_even_if_gate_says_pass(tmp_path):
    _plan, run, gate, log, mesh, baseline, _cp_sha = _fixture(tmp_path)
    measurement_path = Path(json.loads(gate.read_text())["measurement"])
    row = json.loads(measurement_path.read_text())
    row["judgement"] = "HOLD"
    measurement_path.write_text(json.dumps(row), encoding="utf-8")
    gate_row = json.loads(gate.read_text())
    gate_row["measurement_sha256"] = _sha(measurement_path)
    gate.write_text(json.dumps(gate_row), encoding="utf-8")
    with pytest.raises(ValueError, match="measurement checkpoint or plan identity differs"):
        build_evidence(source_plan_path=PLAN, parent_manifest_path=run / "manifest.json",
                       gate_receipt_path=gate, training_log_path=log,
                       evaluation_mesh_path=mesh, w09_baseline_path=baseline)
