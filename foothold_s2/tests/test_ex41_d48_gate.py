"""Known-input D48/R23 gates for EX-41 clips and D102 playlists."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval.ex41_d48_gate import check_receipt, expected_name
from foothold_s2.eval.ex41_stage_video import publish_playlists


def make_receipt(tmp_path: Path, schema: str, *, done: bool = False,
                 stage_suite: str = "W57") -> dict:
    row: dict = {"schema": schema, "checkpoint_sha256": "c" * 64,
                 "video_rule_version": "v3.5"}
    if schema == "foothold-ex41-stage-video/1":
        row.update(suite=stage_suite,
                   case="fwd0.5" if stage_suite == "W57" else "stairs_side_left",
                   map_mode="eval_gt",
                   iteration=750, own_result="fail" if done else "success",
                   composer_sha256="d" * 64)
        capture = tmp_path / "attempt" / "EX41-capture"
        row["attempt_dir"] = str(capture.parent)
    elif schema == "foothold-ex41-w78-video-receipt/1":
        row.update(combination_id="L5_a030_eval_gt_stairs_fwd", local_iteration=750,
                   own_result="fail" if done else "success")
        capture = tmp_path / "attempt" / "EX41-capture"
        row["attempt_dir"] = str(capture.parent)
    else:
        row.update(kind="pyramid_stairs", level=0, iteration=750, map_mode="eval_gt",
                   outcome="fail" if done else "success")
        capture = tmp_path / "capture"
        row["capture"] = str(capture)
    capture.mkdir(parents=True)
    np.savez(capture / "review_feet.npz", done=np.array([False, done]))
    video = tmp_path / expected_name(row)
    video.write_bytes(b"known video bytes")
    row.update(video=str(video), video_sha256=hashlib.sha256(video.read_bytes()).hexdigest())
    return row


@pytest.mark.parametrize("schema", [
    "foothold-ex41-stage-video/1",
    "foothold-ex41-w78-video-receipt/1",
    "foothold-ex41-a-push-video/1",
])
@pytest.mark.parametrize("done", [False, True])
def test_each_video_route_uses_its_own_termination(tmp_path, schema, done):
    row = make_receipt(tmp_path, schema, done=done)
    check_receipt(row)
    row["own_result" if schema != "foothold-ex41-a-push-video/1" else "outcome"] = (
        "success" if done else "fail")
    with pytest.raises(ValueError, match="D48/R23"):
        check_receipt(row)


def test_w80_stage_name_and_own_result(tmp_path):
    row = make_receipt(tmp_path, "foothold-ex41-stage-video/1", stage_suite="W80")
    check_receipt(row)
    assert "pyramid_stairs_inv_L2" in Path(row["video"]).name


def test_syntactically_valid_but_borrowed_fail_result_is_rejected(tmp_path):
    row = make_receipt(tmp_path, "foothold-ex41-stage-video/1")
    row["own_result"] = "fail"
    wrong = tmp_path / expected_name(row)
    wrong.write_bytes(Path(row["video"]).read_bytes())
    row["video"] = str(wrong)
    with pytest.raises(ValueError, match="own capture"):
        check_receipt(row)


def test_playlist_rejects_wrong_name_before_any_publication(tmp_path):
    row = make_receipt(tmp_path, "foothold-ex41-stage-video/1")
    wrong = tmp_path / "styled.mp4"
    wrong.write_bytes(Path(row["video"]).read_bytes())
    row["video"] = str(wrong)
    out = tmp_path / "out"
    receipts = out / "receipts"
    receipts.mkdir(parents=True)
    (receipts / "stage.json").write_text(json.dumps(row), encoding="utf-8")
    playlist = tmp_path / "_playlists"
    playlist.mkdir()
    args = argparse.Namespace(playlist_root=playlist, checkpoint_sha="c" * 64,
                              iteration=750, w78_out=None, push_out=None)
    with pytest.raises(ValueError, match="D48/R23"):
        publish_playlists(args, out, {"composer_sha256": "d" * 64})
    assert list(playlist.iterdir()) == []
    failures = list((out / "d48_name_failures").glob("*.json"))
    assert len(failures) == 1
    assert json.loads(failures[0].read_text(encoding="utf-8"))["state"] == "technical_failure"


def test_playlist_rejects_supplemental_name_before_any_publication(tmp_path):
    out = tmp_path / "out"
    (out / "receipts").mkdir(parents=True)
    stage = make_receipt(tmp_path / "stage", "foothold-ex41-stage-video/1")
    (out / "receipts" / "stage.json").write_text(json.dumps(stage), encoding="utf-8")
    push_out = tmp_path / "push"
    push_out.mkdir()
    push = make_receipt(tmp_path / "push_capture", "foothold-ex41-a-push-video/1")
    wrong = push_out / "styled.mp4"
    wrong.write_bytes(Path(push["video"]).read_bytes())
    push["video"] = str(wrong)
    (push_out / "eval_gt.json").write_text(json.dumps(push), encoding="utf-8")
    playlist = tmp_path / "_playlists"
    playlist.mkdir()
    args = argparse.Namespace(playlist_root=playlist, checkpoint_sha="c" * 64,
                              iteration=750, w78_out=None, push_out=push_out)
    with pytest.raises(ValueError, match="D48/R23"):
        publish_playlists(args, out, {"composer_sha256": "d" * 64})
    assert list(playlist.iterdir()) == []
    assert len(list((out / "d48_name_failures").glob("*.json"))) == 1
