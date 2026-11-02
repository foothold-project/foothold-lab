"""Known-input CPU checks for disjoint C76 GPU execution lists."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import c_layer_gpu0_gate as gate  # noqa: E402
import c_layer_shard as shard  # noqa: E402
import make_c_layer_shards as maker  # noqa: E402


BASE = Path("D:/mai-tmp/c_layer_m6000_phase1_v2/plan_frozen_5027e4ad.json")


def test_shards_are_disjoint_and_preserve_frozen_recorder(tmp_path):
    base = json.loads(BASE.read_text(encoding="utf-8-sig"))
    out1, out0 = tmp_path / "gpu1", tmp_path / "gpu0"
    manifest = maker.build(base, tmp_path / "plans", out1, out0,
                           TOOLS / "c_layer_gpu0_gate.py", TOOLS / "c_layer_shard.py")
    assert manifest["union_cells"] == 216 and manifest["intersection_cells"] == 0
    paths = {gpu: Path(manifest["plans"][f"gpu{gpu}"]["path"]) for gpu in (0, 1)}
    plans = {gpu: json.loads(path.read_text(encoding="utf-8")) for gpu, path in paths.items()}
    a = set(shard.inspect_plan(paths[0], 0, out0)[1])
    b = set(shard.inspect_plan(paths[1], 1, out1)[1])
    assert len(a) == len(b) == 108 and not a & b and len(a | b) == 216
    assert plans[0]["recorder_sha256"] == plans[1]["recorder_sha256"] == base["recorder_sha256"]
    assert plans[0]["queue_sha256"] == plans[1]["queue_sha256"] == base["queue_sha256"]
    assert plans[1]["execution_shard"]["assigned_cells"][0] == "pyramid_stairs_L0_eval_gt"
    assert plans[0]["execution_shard"]["assigned_cells"][0] == "stage_stairs_L0_eval_gt"
    plans[0]["execution_shard"]["assigned_cells"][0] = plans[1]["execution_shard"]["assigned_cells"][0]
    paths[0].write_text(json.dumps(plans[0]), encoding="utf-8")
    with pytest.raises(ValueError, match="assigned cells differ"):
        shard.inspect_plan(paths[0], 0, out0)


def test_gpu0_p0_marker_yields_before_any_capture(tmp_path):
    marker = tmp_path / "TRAINING_BUSY"
    config = {"jobs": [{"id": "c-layer", "gpu": 0, "priority": 4}],
              "sources": {"gpu0_training_markers": [str(marker), str(tmp_path / "other")]}}
    assert gate.admission(config, "c-layer")["admit_next_unit"] is True
    marker.write_text("P0", encoding="utf-8")
    assert gate.admission(config, "c-layer")["admit_next_unit"] is False
    assert shard.priority_hold({"execution_shard": {"priority_markers": [str(marker)]}}, 0) == str(marker)


def test_gpu_temporaries_and_receipt_integrity(tmp_path):
    env0 = shard.temporary_env(0, {"PATH": "x", "CUDA_VISIBLE_DEVICES": "1"})
    env1 = shard.temporary_env(1, {"PATH": "x"})
    assert env0["TMP"] != env1["TMP"] and env0["TEMP"] == env0["TMP"]
    assert "CUDA_VISIBLE_DEVICES" not in env0 and env0["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"known completed clip")
    receipt = tmp_path / "cell_success.json"
    row = {"format": "foothold-c-layer-canonical/1", "canonical": True,
           "cell": "cell", "own_result": "success", "checkpoint_sha256": "a" * 64,
           "video": str(video), "video_sha256": shard.sha256(video)}
    receipt.write_text(json.dumps(row), encoding="utf-8")
    assert shard.completed_receipt(receipt, "cell", "a" * 64)
    video.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="corrupted"):
        shard.completed_receipt(receipt, "cell", "a" * 64)


def _failed_attempt(out: Path, cell: str, ordinal: int) -> None:
    attempt = out / "attempts" / cell / f"{ordinal:02d}"
    attempt.mkdir(parents=True)
    (attempt / "failure.json").write_text(json.dumps({"cell": cell, "ordinal": ordinal,
                                                       "seed": 42, "reason": "instance IDs missing"}), encoding="utf-8")
    (attempt / "closed.json").write_text(json.dumps({"state": "failed"}), encoding="utf-8")


def test_three_closed_failures_hold_without_spending_seed(tmp_path):
    for ordinal in (1, 2):
        _failed_attempt(tmp_path, "pit", ordinal)
    assert shard.technical_hold(tmp_path, "pit") is None
    _failed_attempt(tmp_path, "pit", 3)
    hold = shard.technical_hold(tmp_path, "pit")
    assert hold["state"] == "cell_technical_hold"
    assert hold["technical_failures"] == 3 and hold["seed_budget_spent"] == 0
    assert len(hold["failure_receipts"]) == 3
    shard.record_hold(tmp_path, hold)
    assert json.loads((tmp_path / "shard_holds" / "pit.json").read_text())["cell"] == "pit"
    (tmp_path / "attempts" / "pit" / "04").mkdir()
    assert shard.technical_hold(tmp_path, "pit") is None  # open attempt must not be skipped


def test_hold_skips_bad_cell_and_runs_next_with_state(monkeypatch, tmp_path):
    queue = tmp_path / "queue.py"
    queue.write_text("# frozen fake queue", encoding="utf-8")
    for ordinal in (1, 2, 3):
        _failed_attempt(tmp_path, "pit", ordinal)
    plan = {"queue": str(queue), "checkpoint_sha256": "a" * 64,
            "jobs": [{"recorder_argv": [sys.executable]}],
            "execution_shard": {"priority_markers": []}}
    monkeypatch.setattr(shard, "inspect_plan", lambda *_: (plan, ["pit", "next"]))
    monkeypatch.setattr(shard, "priority_hold", lambda *_: None)
    calls = []
    def fake_run(command, **_kwargs):
        calls.append(command)
        if "--run-one" not in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"expected": 216, "ready": 216}), stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"state": "capture_failed", "cell": "next"}), stderr="")
    monkeypatch.setattr(shard.subprocess, "run", fake_run)
    result = shard.run_one(tmp_path / "plan.json", tmp_path, 1)
    assert result["state"] == "capture_failed" and result["cell"] == "next"
    assert len(result["held"]) == 1 and result["held"][0]["cell"] == "pit"
    assert len(calls) == 2 and calls[1][-1] == "next"
    assert (tmp_path / "shard_holds" / "pit.json").is_file()


def test_hold_then_closed_next_has_explicit_final_state(monkeypatch, tmp_path):
    queue = tmp_path / "queue.py"
    queue.write_text("# frozen fake queue", encoding="utf-8")
    for ordinal in (1, 2, 3):
        _failed_attempt(tmp_path, "pit", ordinal)
    plan = {"queue": str(queue), "checkpoint_sha256": "a" * 64,
            "jobs": [{"recorder_argv": [sys.executable]}],
            "execution_shard": {"priority_markers": []}}
    monkeypatch.setattr(shard, "inspect_plan", lambda *_: (plan, ["pit", "next"]))
    monkeypatch.setattr(shard, "priority_hold", lambda *_: None)
    def fake_run(command, **_kwargs):
        payload = ({"state": "only_cell_closed"} if "--run-one" in command else
                   {"expected": 216, "ready": 216})
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
    monkeypatch.setattr(shard.subprocess, "run", fake_run)
    result = shard.run_one(tmp_path / "plan.json", tmp_path, 1)
    assert result["state"] == "assigned_cells_with_holds"
    assert result["held"][0]["technical_failures"] == 3
