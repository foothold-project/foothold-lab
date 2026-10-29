"""Known-input gates for the EX-39 Kit operator script. No Kit is launched."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.ex39_kit_probe import slot_snapshot
from foothold_s2.ex39_kit_smoke import check_evaluation, check_paired_command_resamples, check_training, sha256
from foothold_s2.sol23f_contract import EX39_PARENT_SHA256


def _put(path: Path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row), encoding="utf-8")


def test_realized_slot_snapshot_known_input_and_mutations():
    slots = torch.tensor([0] * 300 + [3] * 100 + [4] * 100 + [5] * 500)
    heading = torch.tensor([True] * 150 + [False] * 150 +
                           [True] * 30 + [False] * 70 +
                           [True] * 30 + [False] * 70 + [False] * 500)
    term = SimpleNamespace(slot_current=slots, heading=heading)
    row = slot_snapshot(term, "B")
    assert row["heading_envs"] == 210
    assert row["heading_forward_fraction"] == .5
    assert row["heading_spin_fraction"] == pytest.approx(.3)
    with pytest.raises(AssertionError, match="heading"):
        slot_snapshot(term, "A")
    term.heading.zero_()
    with pytest.raises(AssertionError, match="ratios"):
        slot_snapshot(term, "B")


def test_training_receipt_requires_real_probe_and_completed_checkpoint(tmp_path):
    root = tmp_path / "ex39a_kit_smoke"
    run = root / "smoke" / "EX-39A-basic-heading_1"
    cp = run / "model_3003.pt"
    cp.parent.mkdir(parents=True)
    cp.write_bytes(b"completed smoke checkpoint")
    _put(run / "train_start_status.json", {"state": "done", "iter": 3003, "sha256": sha256(cp)})
    _put(run / "basic_start_receipt.json", {"stage": "smoke", "num_envs": 3072,
                                            "terrain_levels_by_level": [1024, 1024, 1024]})
    _put(run / "ex39_kit_probe.json", {"result": "PASS", "arm": "A",
                                      "terrain_level_counts": {"0": 1024, "1": 1024, "2": 1024},
                                      "post_save_command_only_resamples": [{}, {}]})
    receipt = root / "receipts" / "launch_receipt.json"
    _put(receipt, {"arm": "A", "kit_smoke_updates": 2, "max_iterations": 3004,
                   "planned_main_max_iterations": 4502, "parent_sha256": EX39_PARENT_SHA256})
    (receipt.parent / "run.log").write_text("Learning iteration 3002/3004\n", encoding="utf-8")
    stdout = f"receipt={receipt}\n"
    assert check_training(root, "A", stdout, 0)["state"] == "PASS"
    _put(run / "ex39_kit_probe.json", {"result": "FAIL", "arm": "A",
                                      "terrain_level_counts": {"0": 1024, "1": 1024, "2": 1024},
                                      "post_save_command_only_resamples": [{}, {}]})
    with pytest.raises(ValueError, match="probe"):
        check_training(root, "A", stdout, 0)
    with pytest.raises(ValueError, match="failed"):
        check_training(root, "A", stdout, 1)


def test_evaluation_requires_actual_heading_guard_and_policy_steps(tmp_path):
    cp = tmp_path / "model_3003.pt"
    cp.write_bytes(b"checkpoint")
    out = tmp_path / "eval"
    out.mkdir()
    (out / "run.log").write_text("MAPMODE_DONE\n", encoding="utf-8")
    data = {"checkpoint_sha256": sha256(cp),
            "ex39_heading_smoke_guard": {"constructed_arm_b": True,
                                           "forced_heading_before_disable": True,
                                           "fixed_command_step_checks": 50},
            "modes": {"eval_pred": {"fwd0.5": {"policy_steps_x_envs": 400, "gt_used": 0}}}}
    _put(out / "map_modes.json", data)
    assert check_evaluation(out, cp, 0)["state"] == "PASS"
    data["ex39_heading_smoke_guard"]["fixed_command_step_checks"] = 49
    _put(out / "map_modes.json", data)
    with pytest.raises(ValueError, match="guard"):
        check_evaluation(out, cp, 0)


def test_paired_resample_requires_same_rng_slots_and_nonheading_commands(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    left = {"slot_ids": [0, 3], "heading_ids": [False, False],
            "commands": [[0.5, 0, 0], [0, 0, 1.2]], "rng_state_sha256": "a" * 64}
    right = {**left, "heading_ids": [False, True],
             "commands": [[0.5, 0, 0], [0, 0, 0]]}
    _put(a, {"post_save_command_only_resamples": [left, left]})
    _put(b, {"post_save_command_only_resamples": [right, right]})
    assert check_paired_command_resamples(a, b)["state"] == "PASS"
    bad = {**right, "slot_ids": [0, 4]}
    _put(b, {"post_save_command_only_resamples": [right, bad]})
    with pytest.raises(ValueError, match="slot"):
        check_paired_command_resamples(a, b)
