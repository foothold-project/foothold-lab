"""Known-input gates for the EX-39 Kit operator script. No Kit is launched."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.ex39_kit_probe import slot_snapshot
from foothold_s2.ex39_kit_smoke import check_evaluation, check_paired_command_resamples, check_training, sha256, training_env
from foothold_s2.ex39_smoke_args import check_args, check_file
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
    (receipt.parent / "launch_args.txt").write_text(
        "--smoke-updates\n2\n--basic-stage\nsmoke\n--max_iterations\n3004\n", encoding="utf-8")
    _put(receipt.parent / "smoke_args_checked.json", {"state": "PASS"})
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
    (receipt.parent / "launch_args.txt").write_text(
        "--basic-stage\nmain\n--max_iterations\n4502\n", encoding="utf-8")
    with pytest.raises(ValueError, match="smoke-updates"):
        check_training(root, "A", stdout, 0)


def test_operator_passes_the_same_smoke_variable_as_the_shell(tmp_path):
    env = training_env({"EX39_SMOKE_UPDATES": "2"}, tmp_path, "2026-10-30T15:00:00+09:00")
    assert env["EX39_KIT_SMOKE_UPDATES"] == "2"
    assert env["EX39_REQUIRE_KIT_SMOKE"] == "1"
    assert "EX39_SMOKE_UPDATES" not in env


@pytest.mark.parametrize("bad", [
    ["--basic-stage", "smoke", "--max_iterations", "3004"],
    ["--smoke-updates", "2", "--basic-stage", "main", "--max_iterations", "4502"],
    ["--smoke-updates", "2", "--smoke-updates", "2", "--basic-stage", "smoke", "--max_iterations", "3004"],
])
def test_smoke_argv_contract_rejects_missing_main_and_duplicate(bad):
    with pytest.raises(ValueError, match="EX-39 smoke launch"):
        check_args(bad)


@pytest.mark.parametrize("arm", ["A", "B"])
def test_actual_run_ex39_bash_dry_has_child_smoke_args(tmp_path, arm):
    root = Path(__file__).resolve().parents[2]
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "foothold_s2"],
                           cwd=root, capture_output=True, text=True, check=True).stdout
    if dirty:
        pytest.skip("actual Bash DRY requires the committed clean code snapshot")
    parent = Path("C:/Users/AI-WS01/s2_lab/basic_gait_runs/main/EX-38-basic-e1rew_20261029_123840_163180/model_3001.pt")
    if not parent.is_file():
        pytest.skip("pinned parent checkpoint unavailable on this host")
    env = os.environ.copy()
    env.pop("EX39_SMOKE_UPDATES", None)
    env.update({"LIVE": "0", "END_BY": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
                "BASIC_LOG_ROOT": str(tmp_path), "EX39_KIT_SMOKE_UPDATES": "2",
                "EX39_REQUIRE_KIT_SMOKE": "1", "EX39_UPDATES": "1500", "EX39_LEVELS": "3"})
    cmd = ["C:/Program Files/Git/bin/bash.exe", str(root / "foothold_s2/run_ex39.sh"), arm,
           "cuda:0", str(parent), EX39_PARENT_SHA256]
    proc = subprocess.run(cmd, cwd=root, env=env, text=True, capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    match = re.search(r"^receipt=(.+)$", proc.stdout, re.MULTILINE)
    assert match and "DRY: training not started" in proc.stdout
    receipt = Path(match.group(1).strip())
    row = check_file(receipt.parent / "launch_args.txt")
    assert row["observed"] == {"--smoke-updates": "2", "--basic-stage": "smoke", "--max_iterations": "3004"}
    assert json.loads((receipt.parent / "smoke_args_checked.json").read_text())["state"] == "PASS"


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
