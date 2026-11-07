"""Dry-run reminder timing for 500-update EX-42 human reviews.
Uses numbered checkpoint mtimes and completed, iteration-matched score artifacts.
It only prints a notice and never sends messages or starts evaluations.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PureWindowsPath
from statistics import median
from typing import Iterable

_CHECKPOINT = re.compile(r"model_(\d+)\.pt\Z")


@dataclass(frozen=True)
class JudgmentForecast:
    anchor_iteration: int
    anchor_at: datetime
    target_iteration: int
    boundary_at: datetime
    score_seconds: float
    judgment_at: datetime
    notice_at: datetime
    seconds_per_update: float
    cadence_samples: int
    score_samples: int

    def as_json(self, now: datetime) -> dict:
        return {
            "schema": "foothold-ex42-judgment-forecast/1",
            "state": "dry_run",
            "anchor_iteration": self.anchor_iteration,
            "anchor_at": self.anchor_at.isoformat(timespec="seconds"),
            "target_iteration": self.target_iteration,
            "boundary_at": self.boundary_at.isoformat(timespec="seconds"),
            "score_seconds_median": round(self.score_seconds, 1),
            "judgment_at": self.judgment_at.isoformat(timespec="seconds"),
            "notice_at": self.notice_at.isoformat(timespec="seconds"),
            "seconds_per_update_median": round(self.seconds_per_update, 3),
            "cadence_samples": self.cadence_samples,
            "score_samples": self.score_samples,
            "notice_due": now >= self.notice_at,
            "notice_line": (
                f"{self.judgment_at.astimezone().strftime('%H:%M')} 판단 예정 · "
                "볼 것: 유지 칸 · 실패 영상 짝"
            ),
        }


def _local_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp).astimezone()


def _read_checkpoints(directory: Path, at_or_before: int | None) -> list[tuple[int, datetime]]:
    rows = []
    for path in directory.glob("model_*.pt"):
        match = _CHECKPOINT.fullmatch(path.name)
        if match is None:
            continue
        iteration = int(match.group(1))
        if at_or_before is not None and iteration > at_or_before:
            continue
        rows.append((iteration, _local_datetime(path.stat().st_mtime)))
    rows.sort(key=lambda row: row[0])
    if len(rows) < 2:
        raise ValueError("at least two numbered model checkpoints are required")
    if any(right[0] <= left[0] or right[1] <= left[1]
           for left, right in zip(rows, rows[1:])):
        raise ValueError("checkpoint iterations and mtimes must increase")
    return rows


def _read_score_durations(score_dir: Path, checkpoints: dict[int, datetime],
                          before_iteration: int, limit: int) -> list[float]:
    durations = []
    for path in score_dir.glob("score_*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        iteration = row.get("iteration")
        if (type(iteration) is not int or iteration >= before_iteration
                or row.get("evaluation_state") != "complete"
                or iteration not in checkpoints):
            continue
        checkpoint_path = row.get("checkpoint_path")
        if not isinstance(checkpoint_path, str):
            continue
        if PureWindowsPath(checkpoint_path).name != f"model_{iteration}.pt":
            continue
        try:
            completed = datetime.fromisoformat(row["created_at"])
        except (KeyError, TypeError, ValueError):
            completed = _local_datetime(path.stat().st_mtime)
        if completed.tzinfo is None:
            completed = completed.astimezone()
        duration = (completed.astimezone() - checkpoints[iteration]).total_seconds()
        if duration > 0:
            durations.append((iteration, duration))
    durations.sort(key=lambda row: row[0])
    if not durations:
        raise ValueError("no completed, checkpoint-matched score duration is available")
    return [seconds for _, seconds in durations[-limit:]]


def forecast_next_judgment(checkpoint_dir: str | Path, score_dir: str | Path, *,
                           as_of_iteration: int | None = None,
                           now: datetime | None = None,
                           interval: int = 500,
                           sample_window: int = 5,
                           notice_lead_minutes: int = 30) -> JudgmentForecast:
    if interval <= 0 or sample_window < 1 or notice_lead_minutes < 0:
        raise ValueError("interval/window/notice lead configuration is invalid")
    now = (now or datetime.now().astimezone()).astimezone()
    checkpoints = _read_checkpoints(Path(checkpoint_dir), as_of_iteration)
    anchor_iteration, anchor_at = checkpoints[-1]
    if anchor_iteration <= 0:
        raise ValueError("latest checkpoint iteration must be positive")
    cadence = [
        (right_at - left_at).total_seconds() / (right_it - left_it)
        for (left_it, left_at), (right_it, right_at)
        in zip(checkpoints, checkpoints[1:])
    ]
    cadence = [value for value in cadence if value > 0][-sample_window:]
    if not cadence:
        raise ValueError("no positive checkpoint cadence sample is available")

    target = (anchor_iteration // interval + 1) * interval
    boundary_at = anchor_at + timedelta(seconds=median(cadence) * (target - anchor_iteration))
    score_durations = _read_score_durations(
        Path(score_dir), dict(checkpoints), anchor_iteration, sample_window)
    score_seconds = median(score_durations)
    judgment_at = boundary_at + timedelta(seconds=score_seconds)
    notice_at = boundary_at - timedelta(minutes=notice_lead_minutes)
    return JudgmentForecast(
        anchor_iteration=anchor_iteration,
        anchor_at=anchor_at,
        target_iteration=target,
        boundary_at=boundary_at,
        score_seconds=score_seconds,
        judgment_at=judgment_at,
        notice_at=notice_at,
        seconds_per_update=median(cadence),
        cadence_samples=len(cadence),
        score_samples=len(score_durations),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--score-dir", type=Path, required=True)
    parser.add_argument("--as-of-iteration", type=int,
                        help="optional historical cutoff, useful for calibration")
    parser.add_argument("--interval", type=int, default=500)
    parser.add_argument("--sample-window", type=int, default=5)
    parser.add_argument("--notice-lead-minutes", type=int, default=30)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = forecast_next_judgment(
            args.checkpoint_dir, args.score_dir,
            as_of_iteration=args.as_of_iteration,
            interval=args.interval,
            sample_window=args.sample_window,
            notice_lead_minutes=args.notice_lead_minutes,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.as_json(datetime.now().astimezone()),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
