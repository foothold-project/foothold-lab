"""CPU contract tests for EX-41 W78 video request publication."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from foothold_s2.eval import ex41_w78_video_request as request


def make_run(tmp_path: Path, iteration: int = 6250) -> tuple[Path, Path, str]:
    root = tmp_path / "run"
    root.mkdir()
    checkpoint = root / f"model_{iteration}.pt"
    checkpoint.write_bytes(b"known checkpoint bytes")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": iteration},
        "checkpoints": {checkpoint.name: digest},
    }), encoding="utf-8")
    return root, checkpoint, digest


def test_request_has_exact_stage_checkpoint_and_12_canonical_w78_ids(tmp_path):
    root, checkpoint, digest = make_run(tmp_path)
    path = request.write_request(root, checkpoint, 6250, "S2a")
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["schema"] == "foothold-ex41-w78-video-request/1"
    assert row["checkpoint_path"] == str(checkpoint.resolve())
    assert row["checkpoint_sha256"] == digest
    assert row["local_iteration"] == 6250
    assert row["stage_name"] == "S2a"
    assert row["combinations"] == request.expected_combinations()
    assert len(row["combinations"]) == 12
    assert row["combinations"] == [
        f"L5_a{angle:03d}_{mode}_stairs_fwd"
        for angle in (0, 30, 60, 90)
        for mode in ("eval_gt", "eval_pred", "probe_prop_only")
    ]
    payload = {key: value for key, value in row.items() if key != "request_id"}
    expected_id = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()
    assert row["request_id"] == expected_id


def test_identical_request_is_idempotent_and_never_replaces_evidence(tmp_path):
    root, checkpoint, _ = make_run(tmp_path)
    first = request.write_request(root, checkpoint, 6250, "S2a")
    before = first.read_bytes()
    second = request.write_request(root, checkpoint, 6250, "S2a")
    assert second == first
    assert second.read_bytes() == before


@pytest.mark.parametrize("mutate, message", [
    (lambda root, cp: (cp.write_bytes(b"altered"), None), "manifest"),
    (lambda root, cp: (root.joinpath("manifest.json").write_text("{}", encoding="utf-8"), None), "manifest"),
])
def test_wrong_or_missing_manifest_sha_is_rejected(tmp_path, mutate, message):
    root, checkpoint, _ = make_run(tmp_path)
    mutate(root, checkpoint)
    with pytest.raises(ValueError, match=message):
        request.build_request(root, checkpoint, 6250, "S2a")


def test_iteration_stage_and_external_checkpoint_mismatches_are_rejected(tmp_path):
    root, checkpoint, _ = make_run(tmp_path)
    with pytest.raises(ValueError, match="filename"):
        request.build_request(root, checkpoint, 6249, "S2a")
    with pytest.raises(ValueError, match="stage_name"):
        request.build_request(root, checkpoint, 6250, "")
    external = tmp_path / "model_6250.pt"
    external.write_bytes(checkpoint.read_bytes())
    with pytest.raises(ValueError, match="inside"):
        request.build_request(root, external, 6250, "S2a")


def test_request_schema_rejects_missing_or_changed_combination(tmp_path):
    root, checkpoint, _ = make_run(tmp_path)
    row = request.build_request(root, checkpoint, 6250, "S2a")
    row["combinations"] = row["combinations"][:-1]
    with pytest.raises(ValueError, match="combinations"):
        request.request_bytes(row)


def test_stage_transition_request_requires_exact_completed_checkpoint(tmp_path):
    root, checkpoint, _ = make_run(tmp_path, 250)

    class Runtime:
        last_checkpoint = {"iteration": 250, "path": str(checkpoint)}

    held = request.publish_stage_end_request(
        root, Runtime(), stage_name="S2a", next_stage="S2b", boundary_iteration=501)
    assert held["state"] == "held"
    assert held["expected_iteration"] == 500
    assert not (root / request.REQUEST_DIR).exists()

    Runtime.last_checkpoint = {"iteration": 500, "path": str(checkpoint)}
    # The filename and manifest still say 250, so this must remain a hold.
    held = request.publish_stage_end_request(
        root, Runtime(), stage_name="S2a", next_stage="S2b", boundary_iteration=501)
    assert held["state"] == "held"

    checkpoint500 = root / "model_500.pt"
    checkpoint500.write_bytes(b"stage end")
    digest = hashlib.sha256(checkpoint500.read_bytes()).hexdigest()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["checkpoints"][checkpoint500.name] = digest
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    Runtime.last_checkpoint = {"iteration": 500, "path": str(checkpoint500), "sha256": digest}
    published = request.publish_stage_end_request(
        root, Runtime(), stage_name="S2a", next_stage="S2b", boundary_iteration=501)
    assert published["state"] == "published"
    assert json.loads(Path(published["path"]).read_text(encoding="utf-8"))["stage_name"] == "S2a"


def test_final_stage_request_uses_finished_checkpoint_only(tmp_path):
    root, checkpoint, _ = make_run(tmp_path, 6250)

    class Runtime:
        last_checkpoint = {"iteration": 6250, "path": str(checkpoint)}

    result = request.publish_stage_end_request(
        root, Runtime(), stage_name="T0_prime", next_stage=None, boundary_iteration=6250)
    assert result["state"] == "published"
    row = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert row["stage_name"] == "T0_prime"
    assert row["local_iteration"] == 6250
