from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2.eval import ex41_stage_video as stage
from foothold_s2.eval.video25.record_c_layer import parse_stage_video_spec


ROOT = Path(__file__).resolve().parents[3]


def args(**changes):
    value = dict(suite="W57", case="diag-back+side-", mode="eval_pred",
                 stage_name="B0", iteration=750, checkpoint=ROOT / "model_750.pt")
    value.update(changes)
    return SimpleNamespace(**value)


def source():
    from foothold_s2.eval.w78_video_consumer import _git, sha256
    return dict(source_root=str(ROOT), source_head=_git(ROOT, "rev-parse", "HEAD"),
                source_recorder_sha256=sha256(ROOT / "foothold_s2/eval/record_sol23f.py"))


def test_all_stage_cases_and_modes_are_distinct():
    names = set()
    for suite, cases in stage.SUITES.items():
        for case in cases:
            for mode in stage.MODES:
                a = args(suite=suite, case=case, mode=mode)
                spec = stage.stage_spec(a, source(), "a" * 64)
                assert parse_stage_video_spec(spec) == spec
                names.add(stage.segment(suite, case, mode))
    assert len(stage.SUITES["W57"]) == 13
    assert len(stage.SUITES["W80"]) == 4
    assert len(names) == (13 + 4) * 3


@pytest.mark.parametrize("change", [
    {"command": [0.0, 0.0, 0.0]},
    {"map_mode": "eval_bad"},
    {"env_id": 0},
    {"col": 0},
    {"source_head": "0" * 40},
    {"duration_s": 5.0},
])
def test_stage_recorder_rejects_wrong_identity(change):
    spec = stage.stage_spec(args(), source(), "a" * 64)
    spec.update(change)
    with pytest.raises(ValueError):
        parse_stage_video_spec(spec)


def test_d102_playlist_uses_only_matching_valid_receipts(tmp_path):
    out = tmp_path / "out"
    receipts = out / "receipts"
    receipts.mkdir(parents=True)
    playlists = tmp_path / "_playlists"
    playlists.mkdir()
    video = tmp_path / "one.mp4"
    video.write_bytes(b"known video")
    row = {"schema": stage.SCHEMA, "checkpoint_sha256": "a" * 64,
           "video_rule_version": stage.VIDEO_RULE_VERSION,
           "composer_sha256": "b" * 64, "video": str(video),
           "video_sha256": stage.sha256(video), "own_result": "fail"}
    (receipts / "one.json").write_text(json.dumps(row), encoding="utf-8")
    a = SimpleNamespace(playlist_root=playlists, iteration=750, checkpoint_sha="a" * 64)
    result = stage.publish_playlists(a, out, {"composer_sha256": "b" * 64})
    assert result["all"]["count"] == result["fail"]["count"] == 1
    assert str(video) in (playlists / "EX41-m00750-fail.m3u8").read_text(encoding="utf-8")
    video.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA"):
        stage.publish_playlists(a, out, {"composer_sha256": "b" * 64})
