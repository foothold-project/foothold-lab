"""Known-input CPU guards for the EX40 C-layer GPU1 transfer."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from unittest.mock import patch

from foothold_s2.eval import c_layer_gpu1_remainder as moved


def test_registered_transfer_has_exact_27_to_81_split() -> None:
    root = Path("D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34")
    manifest = json.loads((root / "remaining.json").read_text(encoding="utf-8"))
    assert len(manifest["completed_source_receipts"]) == 27
    assert len(manifest["remaining_cells"]) == 81
    assert len(set(manifest["remaining_cells"])) == 81
    assert set(manifest["remaining_cells"]).isdisjoint(manifest["completed_source_receipts"])


def test_p1_marker_yields_before_any_capture(tmp_path: Path) -> None:
    manifest = {"new_out": str(tmp_path), "remaining_cells": ["gaps_L0_eval_gt"]}
    plan = {"composer_sha256": "a" * 64}
    with patch.object(moved, "load_manifest", return_value=(manifest, plan)), \
         patch.object(moved, "gate", return_value={"admit_next_unit": False,
                                                   "reason": "ex41_p1_active"}), \
         patch.object(moved, "checked_success", side_effect=AssertionError("capture entered")):
        result = moved.run_next(tmp_path / "manifest.json", "ignored")
    assert result["state"] == "yielded_to_ex41_p1"


def test_27_seconds_plus_ten_percent_is_hard_boundary() -> None:
    assert moved.SLOWDOWN_LIMIT_S == 29.700000000000003
    guard = moved.RollingUpdateGuard()
    below = [guard.add(i, 29.7) for i in range(1, 11)]
    assert not moved.exceeds_slowdown(below)
    above = guard.add(11, 29.71)
    assert moved.exceeds_slowdown([above])


def test_rolling_ten_ignores_one_spike() -> None:
    guard = moved.RollingUpdateGuard()
    updates = [guard.add(i, 27.0) for i in range(1, 10)]
    updates.append(guard.add(10, 31.0))
    assert updates[-1]["rolling10_mean_s"] == 27.4
    assert not moved.exceeds_slowdown(updates)
    assert max(row["update_s"] for row in updates) == 31.0


def test_rolling_ten_stops_sustained_slowdown() -> None:
    guard = moved.RollingUpdateGuard()
    updates = [guard.add(i, 29.8) for i in range(1, 11)]
    assert moved.exceeds_slowdown(updates)


def test_fewer_than_ten_valid_updates_continues_with_recorded_short_window() -> None:
    guard = moved.RollingUpdateGuard()
    updates = [guard.add(i, 31.0) for i in range(1, 10)]
    assert updates[-1]["window_count"] == 9
    assert updates[-1]["rolling10_mean_s"] is None
    assert not moved.exceeds_slowdown(updates)
    gap = guard.add(11, 31.0)
    assert gap["window_reset"] is True and gap["window_count"] == 1
    assert not moved.exceeds_slowdown([gap])


def test_actual_stop_receipt_would_not_stop_on_rolling_mean() -> None:
    source = Path("D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/SLOWDOWN_HOLD.json")
    recorded = json.loads(source.read_text(encoding="utf-8"))
    guard = moved.RollingUpdateGuard()
    updates = [guard.add(row["iter"], row["update_s"]) for row in recorded["during"]]
    assert max(row["update_s"] for row in recorded["during"]) > moved.SLOWDOWN_LIMIT_S
    assert not moved.exceeds_slowdown(updates)
    assert updates[-1]["rolling10_mean_s"] < moved.SLOWDOWN_LIMIT_S


def test_stale_training_status_cannot_admit_capture(tmp_path: Path) -> None:
    status = tmp_path / "train_start_status.json"
    status.write_text(json.dumps({"state": "running", "iter": 10,
                                  "iter_s": 27.0, "pid": os.getpid()}), encoding="utf-8")
    assert moved.train_sample(status)["iter"] == 10
    stale = time.time() - 601
    os.utime(status, (stale, stale))
    assert moved.train_sample(status) is None


def test_own_queue_yields_to_p1_then_continues_one_cell(tmp_path: Path) -> None:
    manifest = {"new_out": str(tmp_path / "out")}
    states = iter([{"state": "yielded_to_ex41_p1"}, {"state": "pending"},
                   {"state": "remaining_complete_or_technical_hold"}])
    pauses = []
    with patch.object(moved, "load_manifest", return_value=(manifest, {})):
        result = moved.run_remaining(tmp_path / "manifest.json", "ignored",
                                     run_one=lambda *_: next(states), sleep=pauses.append)
    assert result["state"] == "remaining_complete_or_technical_hold"
    assert pauses == [30]
    assert not (tmp_path / "gpu1_remainder.lock").exists()
    rows = [json.loads(line) for line in (tmp_path / "gpu1_remainder_loop.jsonl").read_text().splitlines()]
    assert [row["state"] for row in rows] == ["yielded_to_ex41_p1", "pending",
                                               "remaining_complete_or_technical_hold"]


def test_own_queue_stops_after_first_over_10_percent(tmp_path: Path) -> None:
    manifest = {"new_out": str(tmp_path / "out")}
    with patch.object(moved, "load_manifest", return_value=(manifest, {})):
        result = moved.run_remaining(tmp_path / "manifest.json", "ignored",
                                     run_one=lambda *_: {"state": "ex41_slowdown_hold",
                                                         "during": [{"update_s": 29.71}]},
                                     sleep=lambda _: (_ for _ in ()).throw(AssertionError("slept")))
    assert result["state"] == "ex41_slowdown_hold"
    assert not (tmp_path / "gpu1_remainder.lock").exists()


def test_four_policy_failures_skip_to_next_cell(tmp_path: Path) -> None:
    out = tmp_path / "out"
    for ordinal in range(1, 5):
        attempt = out / "attempts" / "gaps_L0_eval_gt" / f"{ordinal:02d}"
        attempt.mkdir(parents=True)
        (attempt / "closed.json").write_text('{"state":"validated","result":"fail"}')
    manifest = {"new_out": str(out), "training_status": str(tmp_path / "status.json"),
                "remaining_cells": ["gaps_L0_eval_gt", "boxes_L0_eval_gt"]}
    plan = {"jobs": [{"kind": kind, "level": 0, "map_mode": "eval_gt",
                      "seeds": [42, 43, 44, 45]} for kind in ("gaps", "boxes")]}
    with patch.object(moved, "load_manifest", return_value=(manifest, plan)), \
         patch.object(moved, "gate", return_value={"admit_next_unit": True}), \
         patch.object(moved, "checked_success", return_value=None), \
         patch.object(moved, "train_sample", return_value=None):
        result = moved.run_next(tmp_path / "manifest.json", "ignored")
    assert result == {"state": "training_status_hold", "cell": "boxes_L0_eval_gt"}


def test_two_policy_failures_exhaust_without_third_seed(tmp_path: Path) -> None:
    out = tmp_path / "out"
    for ordinal in (1, 2):
        attempt = out / "attempts" / "gaps_L0_eval_gt" / f"{ordinal:02d}"
        attempt.mkdir(parents=True)
        (attempt / "closed.json").write_text('{"state":"validated","result":"fail"}')
    manifest = {"new_out": str(out), "training_status": str(tmp_path / "status.json"),
                "remaining_cells": ["gaps_L0_eval_gt", "boxes_L0_eval_gt"]}
    plan = {"jobs": [{"kind": kind, "level": 0, "map_mode": "eval_gt",
                     "seeds": [42, 43]} for kind in ("gaps", "boxes")]}
    with patch.object(moved, "load_manifest", return_value=(manifest, plan)), \
         patch.object(moved, "gate", return_value={"admit_next_unit": True}), \
         patch.object(moved, "checked_success", return_value=None), \
         patch.object(moved, "train_sample", return_value=None):
        result = moved.run_next(tmp_path / "manifest.json", "ignored")
    assert result == {"state": "training_status_hold", "cell": "boxes_L0_eval_gt"}


def test_technical_failure_does_not_spend_policy_seed(tmp_path: Path) -> None:
    out = tmp_path / "out"
    attempt = out / "attempts" / "gaps_L0_eval_gt" / "01"
    attempt.mkdir(parents=True)
    (attempt / "closed.json").write_text('{"state":"failed"}')
    (attempt / "failure.json").write_text('{}')
    manifest = {"new_out": str(out), "training_status": str(tmp_path / "status.json"),
                "remaining_cells": ["gaps_L0_eval_gt"]}
    plan = {"jobs": [{"kind": "gaps", "level": 0, "map_mode": "eval_gt",
                     "seeds": [42, 43]}]}
    with patch.object(moved, "load_manifest", return_value=(manifest, plan)), \
         patch.object(moved, "gate", return_value={"admit_next_unit": True}), \
         patch.object(moved, "checked_success", return_value=None), \
         patch.object(moved, "train_sample", return_value=None):
        result = moved.run_next(tmp_path / "manifest.json", "ignored")
    assert result == {"state": "training_status_hold", "cell": "gaps_L0_eval_gt"}
