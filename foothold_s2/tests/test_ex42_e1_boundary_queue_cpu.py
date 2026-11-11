from __future__ import annotations

import hashlib
import json
from pathlib import Path

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


def _build(tmp_path: Path, *, e1_ended: bool = True, through: int = 1000):
    run = tmp_path / "e1"
    _e1_run(run, through=through)
    return build_queue_plan(repo=ROOT, e1_run=run, plan_path=PLAN, approvals_path=APPROVALS,
                           e1_ended=e1_ended, mesh_check=lambda _path: {"mesh_sha256": E0_MESH_SHA},
                           landing_mesh_check=lambda _path: {"mesh_sha256": LANDING_SHA},
                           python_path=Path(__file__).resolve(), queue_path=tmp_path / "queue.json",
                           mesh_root_path=tmp_path / "s2_lab")


def test_e1_front_queue_is_exact_ordered_p1_and_never_mutates_queue(tmp_path):
    result = _build(tmp_path)
    assert result["queue_mutated"] is False
    assert result["kit_started"] is False and result["training_started"] is False
    assert result["registration_allowed_after_fixed_checkout"] is True
    assert [row["iteration"] for row in result["jobs"]] == [250, 500, 750, 1000]
    assert [row["gpu"] for row in result["jobs"]] == [0, 1, 0, 1]
    assert [row["priority"] for row in result["jobs"]] == [1] * 4
    assert len(result["jobs"][0]["d44_judge_cases"]) == 6
    assert len(result["jobs"][0]["d44_record_cases"]) == 3
    for index, job in enumerate(result["jobs"]):
        argv = job["eval_argv"]
        assert argv[argv.index("--p1-stage-id") + 1] == "E1"
        assert argv[argv.index("--device") + 1] == f"cuda:{index % 2}"
        assert argv[argv.index("--expected-mesh-sha256") + 1] == E0_MESH_SHA
        assert "--sha-from-manifest" in argv and "--execute" in argv
        assert job["queue_add_argv"][job["queue_add_argv"].index("--queue") + 1] == result["queue"]
        assert "queue add" in job["queue_add_shell"]
        if index:
            assert job["wait_present"] == [result["jobs"][index - 1]["marker"]]
            assert job["wait_present"][0] in job["queue_add_argv"]
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
        for job in result["jobs"]:
            assert dispatch.main(job["queue_add_argv"][2:]) == 0
    persisted = json.loads(Path(result["queue"]).read_text(encoding="utf-8"))
    assert len(persisted["items"]) == 4
    assert persisted["items"][0].get("wait_present") is None
    assert persisted["items"][1]["wait_present"] == [result["jobs"][0]["marker"]]
    assert persisted["items"][3]["wait_present"] == [result["jobs"][2]["marker"]]


def test_e1_queue_refuses_before_end_or_without_all_manifest_checkpoints(tmp_path):
    with pytest.raises(ValueError, match="explicit confirmation"):
        _build(tmp_path / "not-ended", e1_ended=False)
    with pytest.raises(ValueError, match="at least 1000"):
        _build(tmp_path / "incomplete", through=750)


def test_queue_preparation_refuses_unlocked_checkout_and_wrong_mesh_identity(tmp_path):
    run = tmp_path / "e1"
    _e1_run(run)
    with pytest.raises(ValueError, match="locked read-only"):
        build_queue_plan(repo=ROOT, e1_run=run, plan_path=PLAN, approvals_path=APPROVALS,
                         e1_ended=True, require_locked=True,
                         mesh_check=lambda _path: {"mesh_sha256": E0_MESH_SHA},
                         landing_mesh_check=lambda _path: {"mesh_sha256": LANDING_SHA},
                         python_path=Path(__file__).resolve(), queue_path=tmp_path / "queue.json",
                         mesh_root_path=tmp_path / "s2_lab")
    with pytest.raises(ValueError, match="combined mesh"):
        build_queue_plan(repo=ROOT, e1_run=run, plan_path=PLAN, approvals_path=APPROVALS,
                         e1_ended=True, mesh_check=lambda _path: {"mesh_sha256": "0" * 64},
                         landing_mesh_check=lambda _path: {"mesh_sha256": LANDING_SHA},
                         python_path=Path(__file__).resolve(), queue_path=tmp_path / "queue.json",
                         mesh_root_path=tmp_path / "s2_lab")


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
