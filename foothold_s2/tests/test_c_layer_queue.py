"""Known-input CPU checks for the D46 C-layer planner and one-clip runner."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from foothold_s2.eval import c_layer_queue as q
from foothold_s2.eval import video_style


KINDS = {
    "continuous": ["pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
                   "hf_pyramid_slope", "hf_pyramid_slope_inv", "stage_stairs"],
    "sparse": ["stepping_stones_low", "stepping_stones_high", "balance_beams",
               "stepping_beams", "gaps"],
}


def fixture(tmp_path: Path):
    checkpoint = tmp_path / "model_8000.pt"
    recorder = tmp_path / "record.py"
    source = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    for path, value in ((checkpoint, b"checkpoint"), (recorder, b"recorder")):
        path.write_bytes(value)
    np.savez(source, env=np.arange(8), kind=np.array(["random_rough"] * 7 + ["boxes"]),
             terrain_level=np.array([0] * 7 + [2]), terrain_col=np.array([0] * 7 + [4]),
             alive_end=np.array([True] * 7 + [False]), body_vx_integral_m=np.array([5.0] * 8))
    label = video_style.capture_name("EX40", "boxes", 2, 7, 8000, segment="eval_gt")
    row = {"kind": "boxes", "level": 2, "map_mode": "eval_gt", "role": "fail",
           "env_id": 7, "label": label, "selection_source": "evaluation",
           "selection_result": "fail", "selection_path": str(source),
           "selection_sha256": q.sha256(source), "capture_provenance": "evaluation_replay",
           "policy": {"experiment": "SB", "source_profile": "W15", "source_root": str(tmp_path),
                      "terrain_set": "fixed64", "seed": 42, "checkpoint_sha256": q.sha256(checkpoint),
                      "envs": 8, "map_mode": "eval_gt", "env_id": 7, "kind": "boxes", "col": 4},
           "selection_success_fwd_m": 3.0, "own_success_fwd_m": 3.0,
           "recorder_argv": ["python", str(recorder), "--policy", "{policy}",
                             "--checkpoint", str(checkpoint), "--label", "{label}", "--mp4", "{mp4}"]}
    plan = {"status": "approved_canon", "canon_label": "EX40", "iteration": 8000,
            "kinds": KINDS, "checkpoint": str(checkpoint), "checkpoint_sha256": q.sha256(checkpoint),
            "recorder": str(recorder), "recorder_sha256": q.sha256(recorder), "jobs": [row]}
    return plan, row


def test_inventory_and_missing_selection(tmp_path):
    plan, _ = fixture(tmp_path)
    result = q.validate_plan(plan)
    assert result["expected"] == 432 and result["ready"] == 1 and result["missing"] == 431
    plan["jobs"].append(dict(plan["jobs"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        q.validate_plan(plan)


def test_wrong_checkpoint_or_selection_is_rejected(tmp_path):
    plan, row = fixture(tmp_path)
    plan["checkpoint_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        q.validate_plan(plan)
    plan, row = fixture(tmp_path)
    row["policy"]["map_mode"] = "eval_pred"
    with pytest.raises(ValueError, match="map mode"):
        q.validate_plan(plan)


def test_own_result_and_eval_result_get_separate_name(tmp_path, monkeypatch):
    plan, row = fixture(tmp_path)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "ffprobe":
            return subprocess.CompletedProcess(argv, 0, '{"streams":[{"nb_read_frames":"300"}]}', "")
        mp4 = Path(argv[argv.index("--mp4") + 1])
        mp4.write_bytes(b"fake video for CPU validator")
        mp4.with_name("review.json").write_text(json.dumps({
            "checkpoint_sha256": plan["checkpoint_sha256"], "label": row["label"],
            "selected_environment": {"env_id": 7, "kind": "boxes", "level": 2},
            "map_modes": {"map_mode": {"requested": "eval_gt"}}, "style": {"style_id": video_style.STYLE_ID},
            "frames": 300, "fps": 25, "duration_s": 12.0, "resets": 0}), encoding="utf-8")
        np.savez(mp4.with_name("review_feet.npz"), t=np.arange(600) * .02,
                 dt=.02, done=np.zeros(600, dtype=bool), vx=np.ones(600))
        mp4.with_name("review.done").write_text(json.dumps({
            "format": "d51-capture-receipt/1", "name": row["label"],
            "checkpoint_sha256": plan["checkpoint_sha256"],
            "recorder_sha256": plan["recorder_sha256"],
            "env": 7, "kind": "boxes", "level": 2, "map_mode": "eval_gt",
            "files": {name: q.sha256(mp4.with_name(name)) for name in (
                "review.mp4", "review.json", "review_feet.npz")},
        }), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(q.subprocess, "run", fake_run)
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[])
    assert result["state"] == "candidate_captured"
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    assert receipt["own_result"] == "success" and receipt["selection_result"] == "fail"
    assert receipt["video"].endswith("-success-evalfail.mp4")
    assert receipt["canonical"] is False and receipt["state"] == "candidate"
    assert len(calls) == 2
    assert q.run_one(plan, out=out, high_priority_markers=[])["state"] == "listed_jobs_have_candidate_receipts"
    attempt_mp4 = Path(receipt["attempt_dir"]) / "review.mp4"
    attempt_mp4.with_name("review.done").unlink()
    with pytest.raises(ValueError, match="capture artifact missing"):
        q.verify_attempt(attempt_mp4, row, plan, ffprobe="ffprobe")


def test_higher_priority_yields_before_capture(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    marker = tmp_path / "PRIORITY_BUSY"
    marker.write_text("evaluation", encoding="utf-8")

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("capture launched despite higher priority")

    monkeypatch.setattr(q.subprocess, "run", should_not_run)
    assert q.run_one(plan, out=tmp_path / "out", high_priority_markers=[marker])["state"] == "yielded_to_higher_priority"


def test_failed_attempt_has_separate_evidence_and_is_retryable(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    monkeypatch.setattr(q.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 9))
    out = tmp_path / "out"
    first = q.run_one(plan, out=out, high_priority_markers=[])
    second = q.run_one(plan, out=out, high_priority_markers=[])
    assert first["state"] == second["state"] == "capture_failed"
    assert first["attempt_dir"] != second["attempt_dir"]
    assert len(list((out / "attempts").rglob("child.log"))) == 2
    assert not list(out.glob("*.mp4"))


def test_own_termination_is_fail_even_if_evaluation_succeeded(tmp_path):
    _, row = fixture(tmp_path)
    row["role"] = row["selection_result"] = "success"
    npz = tmp_path / "capture_feet.npz"
    done = np.zeros(600, dtype=bool)
    done[120] = True
    np.savez(npz, t=np.arange(600) * .02, dt=.02, done=done, vx=np.ones(600))
    assert q.actual_result({"resets": 1}, npz, row) == "fail"
    with pytest.raises(ValueError, match="reset count"):
        q.actual_result({"resets": 0}, npz, row)
