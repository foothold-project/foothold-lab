from __future__ import annotations

import json
import sys
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
    assert len(stage.stage_cases()) == 51
    assert len(set(stage.stage_cases())) == 51


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


def test_dispatcher_admitted_clip_ignores_absent_legacy_board(tmp_path, monkeypatch):
    """A queue item reaches its one-clip recorder without the removed board."""
    class ReachedRecorder(Exception):
        pass

    a = args(out=tmp_path / "out", source_root=tmp_path, recorder=tmp_path / "record.py",
             composer=tmp_path / "compose.py", python=Path(sys.executable),
             device="cuda:1", gpu_jobs_config=tmp_path / "missing" / "jobs.json",
             playlist_root=tmp_path / "playlists", plan_only=False)
    monkeypatch.setattr(stage, "validate_checkpoint", lambda _: (a.checkpoint, "a" * 64))
    monkeypatch.setattr(stage, "validate_sources", lambda *unused: {"source_head": "b" * 40})
    monkeypatch.setattr(stage, "stage_spec", lambda *unused: {"command_name": a.case})
    monkeypatch.setattr(stage, "recorder_argv", lambda *unused: (_ for _ in ()).throw(ReachedRecorder))
    with pytest.raises(ReachedRecorder):
        stage.run(a)
    assert not a.gpu_jobs_config.exists()
    assert (a.out / "attempts").is_dir()
    assert not (a.out / "stage_video.lock").exists()


def test_stage_cli_accepts_legacy_argument_without_board(tmp_path, monkeypatch, capsys):
    def planned(a):
        assert a.gpu_jobs_config == tmp_path / "absent.json"
        return {"state": "planned"}

    monkeypatch.setattr(stage, "run", planned)
    paths = ["--checkpoint", "--source-root", "--recorder", "--composer", "--python",
             "--out", "--playlist-root"]
    argv = [token for name in paths for token in (name, str(tmp_path / name[2:]))]
    argv += ["--gpu-jobs-config", str(tmp_path / "absent.json"), "--iteration", "750",
             "--stage-name", "S2a", "--suite", "W57", "--case", "fwd0.5",
             "--mode", "eval_gt", "--plan-only"]
    assert stage.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "planned"
