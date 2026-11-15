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

from foothold_s2.ex39_kit_probe import capture_finish, check_first_forward_heading, slot_snapshot
from foothold_s2.ex39_kit_smoke import (arm_environment, check_evaluation,
                                         check_paired_command_resamples, check_training,
                                         device_plan, launch_parallel, sha256, training_env)
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


def test_first_heading_wz_uses_live_yaw_not_zero_after_resample(tmp_path):
    from foothold_s2.commands.mixed_core import heading_wz

    psi = torch.tensor([0.0, 0.0])
    yaw = torch.tensor([0.08, -0.12])
    observed = heading_wz(psi, yaw, 0.5, 2.0)
    assert observed.tolist() == pytest.approx([-0.04, 0.06])
    detail = {"env_count": 2, "observed_abs_max": float(observed.abs().max()),
              "expected_abs_max": float(observed.abs().max()), "error_abs_max": 0.0,
              "heading_error_abs_max": 0.12}
    assert check_first_forward_heading(detail) is detail
    for key, value in (("error_abs_max", 2e-5), ("observed_abs_max", 0.11)):
        bad = {**detail, key: value}
        with pytest.raises(AssertionError, match="heading wz"):
            check_first_forward_heading(bad)

    _put(tmp_path / "ex39_kit_probe.json", {"arm": "B", "checks": {}, "result": "PASS"})
    term = SimpleNamespace(ex39_first_forward_heading_wz_detail={**detail, "error_abs_max": 2e-5},
                           ex39_first_forward_heading_wz_max=detail["observed_abs_max"])
    raw = SimpleNamespace(command_manager=SimpleNamespace(get_term=lambda name: term),
                          reward_manager=SimpleNamespace(get_term_cfg=lambda name: SimpleNamespace(weight=0.0)),
                          _ex39_kit_foot_smoke=[{"four_foot_mean": 0.012}] * 8)
    with pytest.raises(AssertionError, match="heading wz"):
        capture_finish(raw, tmp_path)
    failed = json.loads((tmp_path / "ex39_kit_probe.json").read_text(encoding="utf-8"))
    assert failed["result"] == "FAIL"
    assert failed["first_forward_heading_wz_detail"]["error_abs_max"] == 2e-5
    assert len(failed["first_eight_reward_step_four_foot"]) == 8


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


def test_gpu_device_plan_and_isolated_kit_temp_dirs(tmp_path):
    assert device_plan(["cuda:0", "cuda:1"]) == {"A": "cuda:0", "B": "cuda:1"}
    assert device_plan(["cuda:0"]) == {"A": "cuda:0", "B": "cuda:0"}
    for bad in (["cuda:1"], ["cuda:1", "cuda:0"], ["cuda:0", "cuda:0"]):
        with pytest.raises(ValueError, match="device"):
            device_plan(bad)
    a = arm_environment({}, tmp_path / "a", "2026-10-30T15:00:00+09:00")
    b = arm_environment({}, tmp_path / "b", "2026-10-30T15:00:00+09:00")
    assert a["TEMP"] == a["TMP"] == a["TMPDIR"]
    assert b["TEMP"] == b["TMP"] == b["TMPDIR"]
    assert a["TEMP"] != b["TEMP"]
    assert Path(a["TEMP"]).is_dir() and Path(b["TEMP"]).is_dir()


def test_parallel_launch_staggers_30_seconds_without_killing_children(tmp_path):
    events = []

    class Child:
        def __init__(self, arm):
            self.arm = arm

        def wait(self):
            events.append(("wait", self.arm))
            return 0

    def fake_popen(cmd, **kwargs):
        arm = cmd[2]
        events.append(("start", arm, cmd[3], kwargs["env"]["TEMP"]))
        kwargs["stdout"].write(f"receipt={arm}\n")
        kwargs["stdout"].flush()
        return Child(arm)

    specs = []
    for arm, device in (("A", "cuda:0"), ("B", "cuda:1")):
        root = tmp_path / arm
        env = arm_environment({}, root, "2026-10-30T15:00:00+09:00")
        specs.append((arm, ["bash", "run_ex39.sh", arm, device], tmp_path, env))
    results = launch_parallel(specs, popen=fake_popen, sleep=lambda s: events.append(("sleep", s)))
    assert events[:3][0][:3] == ("start", "A", "cuda:0")
    assert events[1] == ("sleep", 30)
    assert events[2][:3] == ("start", "B", "cuda:1")
    assert events[0][3] != events[2][3]
    assert results == {"A": ("receipt=A\n", 0), "B": ("receipt=B\n", 0)}


@pytest.mark.parametrize("bad", [
    ["--basic-stage", "smoke", "--max_iterations", "3004"],
    ["--smoke-updates", "2", "--basic-stage", "main", "--max_iterations", "4502"],
    ["--smoke-updates", "2", "--smoke-updates", "2", "--basic-stage", "smoke", "--max_iterations", "3004"],
])
def test_smoke_argv_contract_rejects_missing_main_and_duplicate(bad):
    with pytest.raises(ValueError, match="EX-39 smoke launch"):
        check_args(bad)


@pytest.mark.parametrize("arm,device", [("A", "cuda:0"), ("B", "cuda:1")])
def test_actual_run_ex39_bash_dry_has_child_smoke_args(tmp_path, arm, device):
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
           device, str(parent), EX39_PARENT_SHA256]
    proc = subprocess.run(cmd, cwd=root, env=env, text=True, capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    match = re.search(r"^receipt=(.+)$", proc.stdout, re.MULTILINE)
    assert match and "DRY: training not started" in proc.stdout
    receipt = Path(match.group(1).strip())
    row = check_file(receipt.parent / "launch_args.txt")
    assert row["observed"] == {"--smoke-updates": "2", "--basic-stage": "smoke", "--max_iterations": "3004"}
    args_text = (receipt.parent / "launch_args.txt").read_text(encoding="utf-8")
    assert f"--device\n{device}\n" in args_text
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
