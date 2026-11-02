"""A stage-end playlist cannot adopt a video from a different rule revision."""
from __future__ import annotations

import json

import pytest

from foothold_s2.eval import ex40_v3_recompose as batch
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION


def test_existing_video_requires_v3_composer_and_source_sha(tmp_path):
    capture = tmp_path / "raw" / "ex40_m6000" / "EX40-stairs"
    capture.mkdir(parents=True)
    (capture / "review.mp4").write_bytes(b"original")
    (capture / "review_feet.npz").write_bytes(b"feet")
    (capture / "review.json").write_text(json.dumps({"label": capture.name}), encoding="utf-8")
    files = {name: batch.sha256(capture / name) for name in
             ("review.mp4", "review_feet.npz", "review.json")}
    (capture / "review.done").write_text(json.dumps({"format": "d51-capture-receipt/1",
                                                    "name": capture.name, "files": files}), encoding="utf-8")
    batch.verify_raw(capture)
    video = tmp_path / "out" / "ex40_m6000" / "EX40-stairs.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"styled")
    receipt = {"capture": str(capture), "sha256": batch.sha256(video),
               "capture_receipt_sha256": batch.sha256(capture / "review.done"),
               "frames": 1, "video_rule_version": VIDEO_RULE_VERSION,
               "composer_sha256": "a" * 64}
    video.with_suffix(".json").write_text(json.dumps(receipt), encoding="utf-8")
    video.with_suffix(".audit.json").write_text(json.dumps({"pass": True, "frames": 1}), encoding="utf-8")
    batch.verify_composite(capture, video, "a" * 64)
    row = {"capture": str(capture), "video": str(video), "model_dir": "ex40_m6000",
           "own_result": "success"}
    playlist = tmp_path / "_playlists"
    assert batch.publish_playlists([row], playlist_root=playlist,
                                   expected_by_model={"ex40_m6000": 1},
                                   composer_sha="a" * 64)[str(playlist / "EX40-m06000-all.m3u8")] == 1
    receipt.pop("video_rule_version")
    video.with_suffix(".json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="video_rule_hold"):
        batch.publish_playlists([row], playlist_root=playlist,
                                expected_by_model={"ex40_m6000": 1}, composer_sha="a" * 64)


def test_partial_stage_is_hold_without_playlist(tmp_path):
    result = batch.publish_playlists([], playlist_root=tmp_path / "_playlists",
                                     expected_by_model={"ex40_m6000": 2}, composer_sha="a" * 64)
    assert result == {"ex40_m6000": "HOLD: missing valid v3.2 videos"}
    assert not (tmp_path / "_playlists").exists()
