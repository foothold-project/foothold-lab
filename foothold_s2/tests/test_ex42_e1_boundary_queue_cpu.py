from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from foothold_s2.scripts.ex42_e1_boundary_queue import BOUNDARIES, build_queue_plan
from foothold_s2.scripts.ex42_p1_queue_item import run_item


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"
E0_MESH_SHA = "88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95"
LANDING_SHA = "baa59af3347c53c2cdeae674ddc873f26d4b9e38cffdbce4a4dc73cf94febb82"


def _e1_run(path: Path, *, through: int = 1000) -> None:
    path.mkdir(parents=True)
    checksums = {}
    for iteration in BOUNDARIES:
        if iteration > through:
            continue
        checkpoint = path / f"model_{iteration}.pt"
        checkpoint.write_bytes(f"checkpoint {iteration}".encode())
        checksums[checkpoint.name] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (path / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": through}, "checkpoints": checksums,
    }), encoding="utf-8")


def _build(tmp_path: Path, *, e1_ended: bool = True, through: int = 1000,
           repo: Path = ROOT, require_locked: bool = False):
    run = tmp_path / "e1"
    _e1_run(run, through=through)
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    approval_sha = EX42Plan.load(PLAN).document["stage_zero"]["approval_sha256"]
    lines = []
    for rank in range(2):
        lines.append("EX42_STAGE_E1_PREFLIGHT " + json.dumps({
            "stage_id": "E1", "rank": rank, "world_size": 2,
            "output_dir": str(run) if rank == 0 else str(run / "rank1"),
            "approval": {"approvals_sha256": approval_sha}}))
        # Real exposure rows have no rank, stage_id, or world_size fields.
        lines.append("EX42_E0_EXPOSURE " + json.dumps({
            "envs": 3072, "exposed_columns": [0], "level_caps": [5],
            "start": "parent_env_state"}))
    (run / "torchrun.stdout.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    baseline = run / "w09-flag-baseline.json"
    baseline.write_text('{"state":"measured","source":"W09"}\n', encoding="utf-8")
    mesh_dir = tmp_path / "s2_lab" / "ex42_mesh_1111" / "seed42_E0_c333"
    mesh_dir.mkdir(parents=True)
    mesh_npz = mesh_dir / "terrain_mesh.npz"
    mesh_npz.write_bytes(b"seed42 E0 mesh bytes")
    (mesh_dir / "mesh_manifest.json").write_text(
        json.dumps({"format": "foothold-ex42-combined-mesh/1", "seed": 42,
                    "mesh_sha256": E0_MESH_SHA,
                    "mesh_file_sha256": hashlib.sha256(mesh_npz.read_bytes()).hexdigest()}), encoding="utf-8")
    return build_queue_plan(repo=repo, e1_run=run, plan_path=PLAN, approvals_path=APPROVALS,
                           evaluation_plan_path=PLAN, e1_ended=e1_ended,
                           require_clean=require_locked, require_locked=require_locked,
                           training_log_path=run / "torchrun.stdout.log",
                           mesh_check=lambda _path: {"mesh_sha256": E0_MESH_SHA, "mesh_npz": str(mesh_npz)},
                           landing_mesh_check=lambda _path: {"mesh_sha256": LANDING_SHA},
                           python_path=sys.executable, queue_path=tmp_path / "queue.json",
                           mesh_root_path=tmp_path / "s2_lab", w09_baseline_path=baseline)


def test_e1_front_queue_is_exact_ordered_p1_and_never_mutates_queue(tmp_path):
    result = _build(tmp_path)
    assert result["queue_mutated"] is False
    assert result["kit_started"] is False and result["training_started"] is False
    assert result["registration_allowed_after_fixed_checkout"] is True
    assert result["primary_execution"] == "direct_two_gpu_sequential_chain"
    assert [row["iteration"] for row in result["jobs"]] == [250, 500, 750, 1000]
    assert [row["gpu"] for row in result["jobs"]] == [1, 1, 1, 1]
    assert [(row["device"], row["split_device"]) for row in result["jobs"]] == [("cuda:1", "cuda:0")] * 4
    assert [row["priority"] for row in result["jobs"]] == [1] * 4
    assert len(result["jobs"][0]["d44_judge_cases"]) == 6
    assert len(result["jobs"][0]["d44_record_cases"]) == 3
    for index, job in enumerate(result["jobs"]):
        argv = job["eval_argv"]
        assert argv[argv.index("--p1-stage-id") + 1] == "E1"
        assert argv[argv.index("--device") + 1] == "cuda:1"
        assert argv[argv.index("--split-device") + 1] == "cuda:0"
        assert argv[argv.index("--expected-mesh-sha256") + 1] == E0_MESH_SHA
        assert "--sha-from-manifest" in argv and "--execute" in argv
    fallback = result["fallback_queue_add_argv"]
    assert fallback[fallback.index("--gpu") + 1] == "1"
    assert fallback[fallback.index("--queue") + 1] == result["queue"]
    assert "--done-file" not in fallback
    chain_argv = json.loads(fallback[fallback.index("--argv-json") + 1])
    assert chain_argv[-2] == "--w09-baseline"
    assert chain_argv[-1] == result["w09_baseline"]
    assert chain_argv[chain_argv.index("--training-log") + 1] == result["training_log"]
    assert chain_argv[chain_argv.index("--evaluation-plan") + 1] == result["evaluation_plan_path"]
    assert "ex42_e1_boundary_chain" in " ".join(chain_argv)
    assert chain_argv[chain_argv.index("--p1-done") + 1] == result["chain_done"]
    assert result["cancel_targets"][0]["id"] == 4
    assert result["cancel_targets"][0]["reason"].endswith("lead cancels")
    assert result["d44_landing_mesh_sha256"] == LANDING_SHA
    assert result["d44_landing_mesh_dir"] != result["mesh_dir"]
    from unittest.mock import patch
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "dispatch_test_import", ROOT / "_out/tools/gpu_jobs/dispatch.py")
    dispatch = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(dispatch)
    with patch.object(dispatch, "require_linux_profile", lambda _profile: None):
        assert dispatch.main(fallback[2:]) == 0
    persisted = json.loads(Path(result["queue"]).read_text(encoding="utf-8"))
    assert len(persisted["items"]) == 1
    assert persisted["items"][0]["gpu"] == 1
    assert persisted["items"][0].get("done_files", []) == []


def test_e1_queue_refuses_before_end_or_without_all_manifest_checkpoints(tmp_path):
    with pytest.raises(ValueError, match="explicit confirmation"):
        _build(tmp_path / "not-ended", e1_ended=False)
    with pytest.raises(ValueError, match="at least 1000"):
        _build(tmp_path / "incomplete", through=750)


def test_queue_preparation_refuses_unlocked_checkout_and_wrong_mesh_identity(tmp_path):
    run = tmp_path / "e1"
    _e1_run(run)
    (run / "torchrun.stdout.log").write_text("test log\n", encoding="utf-8")
    with pytest.raises(ValueError, match="locked read-only"):
        build_queue_plan(repo=ROOT, e1_run=run, plan_path=PLAN, approvals_path=APPROVALS,
                         evaluation_plan_path=PLAN, training_log_path=run / "torchrun.stdout.log",
                         e1_ended=True, require_locked=True,
                         mesh_check=lambda _path: {"mesh_sha256": E0_MESH_SHA},
                         landing_mesh_check=lambda _path: {"mesh_sha256": LANDING_SHA},
                         python_path=Path(__file__).resolve(), queue_path=tmp_path / "queue.json",
                         mesh_root_path=tmp_path / "s2_lab")
    with pytest.raises(ValueError, match="combined mesh"):
        build_queue_plan(repo=ROOT, e1_run=run, plan_path=PLAN, approvals_path=APPROVALS,
                         evaluation_plan_path=PLAN, training_log_path=run / "torchrun.stdout.log",
                         e1_ended=True, mesh_check=lambda _path: {"mesh_sha256": "0" * 64},
                         landing_mesh_check=lambda _path: {"mesh_sha256": LANDING_SHA},
                         python_path=Path(__file__).resolve(), queue_path=tmp_path / "queue.json",
                         mesh_root_path=tmp_path / "s2_lab")


def test_queue_preparation_accepts_checkout_locked_by_real_lock_checkout(tmp_path):
    repo = tmp_path / "fixed-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "CPU test"], check=True)
    for relative in ("foothold_s2/ex42_eval_once.py",
                     "foothold_s2/curriculum/ex42-prep.yaml",
                     "_out/tools/gpu_jobs/dispatch.py"):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# tracked lock target\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "foothold_s2", "_out"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)

    locked = subprocess.run([sys.executable, str(ROOT / "_out/tools/ex41/lock_checkout.py"),
                             "lock", str(repo)], check=True, text=True, capture_output=True)
    assert "0 writable" in locked.stdout
    result = _build(tmp_path / "real-lock-run", repo=repo, require_locked=True)
    assert result["primary_execution"] == "direct_two_gpu_sequential_chain"
    assert result["repo"] == str(repo.resolve())


def test_queue_item_publishes_dependency_marker_only_after_complete_p1(tmp_path):
    out = tmp_path / "m250"
    out.mkdir()
    marker = tmp_path / "m250.done.json"
    argv = ["python", "-m", "fake-eval", "--out", str(out)]

    def complete(_argv, check):
        assert check is False
        for name, payload in {
            "eval_receipt.json": {"state": "done"},
            "p1_score.json": {"state": "complete", "stage_id": "E1", "checkpoint_iteration": 250,
                              "checkpoint_sha256": "a" * 64},
            "ex42_score.json": {"stage_id": "E1", "checkpoint_iteration": 250,
                                "checkpoint_sha256": "a" * 64},
        }.items():
            (out / name).write_text(json.dumps(payload), encoding="utf-8")
        return type("Proc", (), {"returncode": 0})()

    assert run_item(evaluator_argv=argv, iteration=250, marker=marker, popen=complete) == 0
    assert json.loads(marker.read_text()) == {"state": "done", "iteration": 250,
                                              "checkpoint_sha256": "a" * 64}

    marker.unlink()
    assert run_item(evaluator_argv=argv, iteration=250, marker=marker,
                    popen=lambda *_a, **_k: type("Proc", (), {"returncode": 5})()) == 5
    assert not marker.exists()


def test_queue_item_rc0_without_matching_receipts_does_not_release_next_boundary(tmp_path):
    out = tmp_path / "m500"
    out.mkdir()
    marker = tmp_path / "m500.done.json"
    argv = ["python", "-m", "fake-eval", "--out", str(out)]

    def broken(_argv, check):
        (out / "eval_receipt.json").write_text('{"state":"done"}', encoding="utf-8")
        (out / "p1_score.json").write_text(
            '{"state":"complete","stage_id":"E1","checkpoint_iteration":499,"checkpoint_sha256":"a"}',
            encoding="utf-8")
        (out / "ex42_score.json").write_text(
            '{"stage_id":"E1","checkpoint_iteration":500,"checkpoint_sha256":"a"}', encoding="utf-8")
        return type("Proc", (), {"returncode": 0})()

    with pytest.raises(ValueError, match="without matching complete evidence"):
        run_item(evaluator_argv=argv, iteration=500, marker=marker, popen=broken)
    assert not marker.exists()


def test_direct_chain_runs_both_gpus_in_checkpoint_order_and_writes_e1f_evidence(tmp_path):
    from foothold_s2.scripts.ex42_e1_boundary_chain import execute_chain
    jobs = [{"iteration": iteration, "eval_argv": ["python", "eval", str(iteration)],
             "marker": str(tmp_path / f"m{iteration}.done"),
             "output": str(tmp_path / f"m{iteration}")}
            for iteration in BOUNDARIES]
    plan = {"primary_execution": "direct_two_gpu_sequential_chain", "queue_mutated": False,
            "source_head": "abc", "plan_sha256": "p", "approvals_sha256": "a", "e1_run": "/e1",
            "chain_receipt": str(tmp_path / "chain.json"), "log_dir": str(tmp_path / "logs"),
            "p1_done_path": str(tmp_path / "chain.p1-done.json"),
            "repo": str(ROOT), "jobs": jobs, "w09_baseline": str(tmp_path / "w09.json"),
                "evidence_path": str(tmp_path / "evidence.json"), "plan_path": str(PLAN),
                "parent_manifest": str(tmp_path / "manifest.json"), "gate_receipt": str(tmp_path / "p1.json"),
                "training_log": str(tmp_path / "train.log"),
                "evaluation_plan_path": str(PLAN),
                "evaluation_mesh_path": str(tmp_path / "mesh.npz")}
    calls = []

    def item_runner(*, evaluator_argv, iteration, marker, popen):
        calls.append((iteration, evaluator_argv))
        Path(marker).write_text("ok", encoding="utf-8")
        return 0

    evidence_calls = []
    def evidence_writer(**kwargs):
        evidence_calls.append(kwargs)
        Path(kwargs["out_path"]).write_text('{"applied_level_cap":5}', encoding="utf-8")
        return {"applied_level_cap": 5}

    Path(plan["w09_baseline"]).write_text('{"state":"measured"}\n', encoding="utf-8")
    row = execute_chain(plan, item_runner=item_runner, evidence_writer=evidence_writer)
    assert [iteration for iteration, _ in calls] == list(BOUNDARIES)
    assert row["state"] == "complete" and row["evidence_state"] == "ready"
    assert len(evidence_calls) == 1 and [x["iteration"] for x in row["completed"]] == list(BOUNDARIES)
    assert evidence_calls[0]["evaluation_plan_path"] == plan["evaluation_plan_path"]
    assert json.loads(Path(plan["chain_receipt"]).read_text())["state"] == "complete"
    marker = json.loads(Path(plan["p1_done_path"]).read_text())
    assert marker["completed_iterations"] == list(BOUNDARIES)


def test_chain_waits_for_w09_then_materializes_without_rerunning_p1(tmp_path):
    from foothold_s2.scripts.ex42_e1_boundary_chain import execute_chain, materialize_only

    jobs = [{"iteration": iteration, "eval_argv": ["python", "eval", str(iteration)],
             "marker": str(tmp_path / f"m{iteration}.done"), "output": str(tmp_path / f"m{iteration}")}
            for iteration in BOUNDARIES]
    baseline = tmp_path / "w09.json"
    evidence_path = tmp_path / "evidence.json"
    receipt_path = tmp_path / "chain.json"
    plan = {"primary_execution": "direct_two_gpu_sequential_chain", "queue_mutated": False,
            "source_head": "abc", "plan_sha256": "p", "approvals_sha256": "a", "e1_run": "/e1",
            "chain_receipt": str(receipt_path), "log_dir": str(tmp_path / "logs"),
            "p1_done_path": str(tmp_path / "chain.p1-done.json"),
            "repo": str(ROOT), "jobs": jobs, "w09_baseline": str(baseline),
            "evidence_path": str(evidence_path), "plan_path": str(PLAN),
            "parent_manifest": str(tmp_path / "manifest.json"), "gate_receipt": str(tmp_path / "p1.json"),
            "training_log": str(tmp_path / "train.log"),
            "evaluation_plan_path": str(PLAN),
            "evaluation_mesh_path": str(tmp_path / "mesh.npz")}
    p1_calls = []

    def item_runner(*, evaluator_argv, iteration, marker, popen):
        p1_calls.append(iteration)
        Path(marker).write_text("ok", encoding="utf-8")
        return 0

    row = execute_chain(plan, item_runner=item_runner)
    assert row["state"] == "p1_complete_waiting_w09_baseline"
    assert row["evidence_state"] == "waiting_for_w09_baseline"
    assert json.loads(Path(plan["p1_done_path"]).read_text())["state"] == "complete"
    assert p1_calls == list(BOUNDARIES)
    assert [item["iteration"] for item in json.loads(receipt_path.read_text())["completed"]] == list(BOUNDARIES)

    baseline.write_text('{"state":"measured"}\n', encoding="utf-8")
    materialize_calls = []

    def evidence_writer(**kwargs):
        materialize_calls.append(kwargs)
        Path(kwargs["out_path"]).write_text('{"applied_level_cap":5}', encoding="utf-8")
        return {"applied_level_cap": 5}

    finished = materialize_only(
        receipt_path=receipt_path, source_plan_path=PLAN,
        parent_manifest_path=plan["parent_manifest"], gate_receipt_path=plan["gate_receipt"],
        training_log_path=plan["training_log"], evaluation_mesh_path=plan["evaluation_mesh_path"],
        w09_baseline_path=baseline, evidence_out=evidence_path,
        evaluation_plan_path=plan["evaluation_plan_path"], evidence_writer=evidence_writer)
    assert finished["state"] == "complete" and finished["evidence_state"] == "ready"
    assert len(materialize_calls) == 1
    assert materialize_calls[0]["evaluation_plan_path"] == plan["evaluation_plan_path"]
    assert p1_calls == list(BOUNDARIES)


def test_direct_chain_stops_at_first_failed_boundary_and_records_blocking_receipt(tmp_path):
    from foothold_s2.scripts.ex42_e1_boundary_chain import execute_chain
    jobs = [{"iteration": iteration, "eval_argv": ["python", "eval", str(iteration)],
             "marker": str(tmp_path / f"m{iteration}.done"), "output": str(tmp_path / f"m{iteration}")}
            for iteration in BOUNDARIES]
    plan = {"primary_execution": "direct_two_gpu_sequential_chain", "queue_mutated": False,
            "source_head": "abc", "plan_sha256": "p", "approvals_sha256": "a", "e1_run": "/e1",
            "chain_receipt": str(tmp_path / "chain.json"), "log_dir": str(tmp_path / "logs"),
            "p1_done_path": str(tmp_path / "chain.p1-done.json"),
            "repo": str(ROOT), "jobs": jobs, "w09_baseline": str(tmp_path / "w09.json"),
            "evidence_path": str(tmp_path / "evidence.json"), "plan_path": str(PLAN),
            "parent_manifest": str(tmp_path / "manifest.json"), "gate_receipt": str(tmp_path / "p1.json"),
            "training_log": str(tmp_path / "train.log"),
            "evaluation_mesh_path": str(tmp_path / "mesh.npz")}
    calls = []

    def item_runner(*, evaluator_argv, iteration, marker, popen):
        calls.append(iteration)
        return 5 if iteration == 500 else 0

    row = execute_chain(plan, item_runner=item_runner)
    assert calls == [250, 500]
    assert row["state"] == "failed" and row["failed_iteration"] == 500
    assert not Path(plan["p1_done_path"]).exists()
    assert json.loads(Path(plan["chain_receipt"]).read_text())["state"] == "failed"
