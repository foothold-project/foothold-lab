from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from foothold_s2.scripts.ex42_judgment_notice import forecast_next_judgment


def _checkpoint(folder: Path, iteration: int, at: datetime) -> Path:
    path = folder / f"model_{iteration}.pt"
    path.write_bytes(b"cpu fixture")
    os.utime(path, (at.timestamp(), at.timestamp()))
    return path


def _score(folder: Path, iteration: int, checkpoint: Path,
           completed_at: datetime, *, state: str = "complete") -> None:
    path = folder / f"score_{iteration}_fixture.json"
    path.write_text(json.dumps({
        "iteration": iteration,
        "checkpoint_path": str(checkpoint),
        "evaluation_state": state,
        "created_at": completed_at.isoformat(),
    }), encoding="utf-8")


def test_forecast_uses_500_boundary_and_median_observed_score_time(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    scores = tmp_path / "scores"
    checkpoints.mkdir()
    scores.mkdir()
    base = datetime(2026, 11, 6, 10, 0, tzinfo=datetime.now().astimezone().tzinfo)
    paths = {}
    for n in range(4500, 5001, 50):
        paths[n] = _checkpoint(checkpoints, n, base + timedelta(seconds=(n - 4500) * 28))
    for n, minutes in ((4500, 40), (4600, 50), (4700, 45), (4800, 55)):
        _score(scores, n, paths[n], base + timedelta(seconds=(n - 4500) * 28,
                                                       minutes=minutes))
    result = forecast_next_judgment(
        checkpoints, scores, as_of_iteration=5000,
        now=base + timedelta(seconds=500 * 28),
    )
    assert result.anchor_iteration == 5000
    assert result.target_iteration == 5500
    assert result.seconds_per_update == pytest.approx(28)
    assert result.boundary_at == base + timedelta(seconds=500 * 28 + 500 * 28)
    assert result.score_seconds == pytest.approx(47.5 * 60)
    assert result.judgment_at == result.boundary_at + timedelta(minutes=47.5)
    assert result.notice_at == result.boundary_at - timedelta(minutes=30)
    assert result.as_json(result.notice_at)["notice_line"] == (
        f"{result.judgment_at.astimezone().strftime('%H:%M')} 판단 예정 · "
        "볼 것: 유지 칸 · 실패 영상 짝"
    )


def test_historical_cutoff_excludes_future_checkpoints_and_scores(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    scores = tmp_path / "scores"
    checkpoints.mkdir()
    scores.mkdir()
    base = datetime(2026, 11, 6, 10, 0, tzinfo=datetime.now().astimezone().tzinfo)
    paths = {}
    for n in (4750, 4800, 4850, 4900, 4950, 5000, 5050, 5500):
        paths[n] = _checkpoint(checkpoints, n, base + timedelta(seconds=(n - 4750) * 30))
    _score(scores, 4950, paths[4950], base + timedelta(seconds=(4950 - 4750) * 30,
                                                       minutes=42))
    _score(scores, 5500, paths[5500], base + timedelta(seconds=(5500 - 4750) * 30,
                                                       minutes=5))
    result = forecast_next_judgment(checkpoints, scores, as_of_iteration=5000)
    assert result.anchor_iteration == 5000
    assert result.target_iteration == 5500
    assert result.score_seconds == pytest.approx(42 * 60)
    assert result.cadence_samples == 5


def test_missing_completed_score_fails_closed_instead_of_guessing(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    scores = tmp_path / "scores"
    checkpoints.mkdir()
    scores.mkdir()
    now = datetime.now().astimezone()
    _checkpoint(checkpoints, 0, now - timedelta(minutes=5))
    _checkpoint(checkpoints, 50, now)
    with pytest.raises(ValueError, match="no completed, checkpoint-matched score"):
        forecast_next_judgment(checkpoints, scores)
