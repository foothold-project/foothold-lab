"""EX-38 launch and relative reward schedule known-input CPU checks."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2 import basic_gait_launch
from foothold_s2 import sol23f_contract
from foothold_s2.rewards.basic_gait_bundle import (
    E1_CANDIDATE, scheduled_lin_vel_z_weight, set_lin_vel_z_weight,
)


END = "2026-10-29T12:30:00+09:00"


def ex38_args(tmp_path: Path) -> list[str]:
    parent = tmp_path / "model_1500.pt"
    parent.write_bytes(b"known fixture, SHA mocked only in this isolated CPU test")
    return basic_gait_launch.build_args(
        "parent", "cuda:0", END, 0.30, str(parent),
        log_root=str(tmp_path / "basic_gait_runs"), stage="main", ex38=True,
    )


def actual_train_parser() -> argparse.ArgumentParser:
    """Execute the real train_sol23f_common parser declarations, stopping before Kit."""
    source = Path(__file__).resolve().parents[1] / "scripts" / "train_sol23f_common.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    declarations = []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "parser" for target in node.targets)):
            declarations.append(node)
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Attribute)
              and isinstance(node.value.func.value, ast.Name)
              and node.value.func.value.id == "parser" and node.value.func.attr == "add_argument"):
            declarations.append(node)
    namespace = {"argparse": argparse}
    exec(compile(ast.Module(body=declarations, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["parser"]


def test_ex38_receipt_pins_parent_rewards_perception_and_deadline(tmp_path, monkeypatch):
    expected = basic_gait_launch.PARENT_SHA256
    monkeypatch.setattr(basic_gait_launch, "sha256_file", lambda _p: expected)
    monkeypatch.setattr(sol23f_contract, "file_sha256", lambda _p: expected)
    args = ex38_args(tmp_path)
    row = basic_gait_launch.receipt("parent", args)
    assert row["parent_sha256"] == expected
    assert row["run_name"] == "EX-38-basic-e1rew"
    assert row["args"]["end-by"] == END
    assert row["args"]["max_iterations"] == "20001"
    assert row["first_update"] == 1501
    assert row["reward_schedule_start_iteration"] == 1501
    assert row["reward_schedule_span_updates"] == 1500
    assert row["env_seed"] == row["command_seed"] == 42
    assert row["depth_camera_enabled"] and row["perception_training_enabled"]
    assert not row["fast_gt_only"] and "--fast-gt-only" not in args
    assert "--basic-ex38" in args and "--basic-lin-vel-z-schedule" in args
    assert row["args"]["kit_args"] == basic_gait_launch.KIT_CACHE_VALUE
    for name, flag in (
        ("track_ang_vel", "--basic-track-ang-weight"),
        ("track_lin_vel", "--basic-track-lin-weight"),
        ("joint_acc", "--basic-joint-acc-weight"),
        ("hip_pos_penalty", "--basic-hip-pos-weight"),
    ):
        value = next((part.split("=", 1)[1] for part in args if part.startswith(flag + "=")), None)
        if value is None:
            value = args[args.index(flag) + 1]
        assert float(value) == E1_CANDIDATE[name]


def test_generated_launch_args_pass_actual_training_parser_without_kit(tmp_path, monkeypatch, capsys):
    expected = basic_gait_launch.PARENT_SHA256
    monkeypatch.setattr(basic_gait_launch, "sha256_file", lambda _p: expected)
    monkeypatch.setattr(sol23f_contract, "file_sha256", lambda _p: expected)
    parent = tmp_path / "model_1500.pt"
    parent.write_bytes(b"known CPU fixture")
    basic_gait_launch.main([
        "parent", "cuda:0", "--parent", str(parent), "--end-by", END,
        "--share", "0.30", "--log-root", str(tmp_path / "runs"),
        "--stage", "main", "--ex38", "--print-args",
    ])
    launch_args = capsys.readouterr().out.splitlines()
    parser = actual_train_parser()
    prefix = ["--task", sol23f_contract.TASKS["SB"], "--variant", "SB"]
    parsed, unknown = parser.parse_known_args(prefix + launch_args)
    assert parsed.basic_joint_acc_weight == -1e-7
    assert parsed.basic_hip_pos_weight == -0.05
    assert parsed.basic_ex38 and parsed.basic_lin_vel_z_schedule
    assert "--headless" in unknown  # AppLauncher flags are intentionally not executed here.
    old_args = list(launch_args)
    old_args[old_args.index("--basic-joint-acc-weight=-1e-7")] = "--basic-joint-acc-weight"
    old_args.insert(old_args.index("--basic-joint-acc-weight") + 1, "-1e-7")
    with pytest.raises(SystemExit):
        parser.parse_known_args(prefix + old_args)


def test_ex38_wrong_reward_or_parent_or_stage_caught(tmp_path, monkeypatch):
    args = ex38_args(tmp_path)
    monkeypatch.setattr(sol23f_contract, "file_sha256", lambda _p: basic_gait_launch.PARENT_SHA256)
    bad = list(args)
    bad[bad.index("--basic-track-ang-weight") + 1] = "0.5"
    with pytest.raises(ValueError, match="EX-38 requires"):
        basic_gait_launch.receipt("parent", bad, check_sha=False)
    monkeypatch.setattr(sol23f_contract, "file_sha256", lambda _p: "0" * 64)
    with pytest.raises(ValueError, match="pinned S-B10"):
        basic_gait_launch.receipt("parent", args)
    with pytest.raises(ValueError, match="EX-38 requires"):
        basic_gait_launch.build_args("scratch", "cuda:0", END, 0.30, None,
                                     log_root=str(tmp_path), stage="main", ex38=True)


def test_ex38_reward_schedule_starts_at_its_first_update_and_binds_manager():
    assert [scheduled_lin_vel_z_weight(i, start_iteration=1501)
            for i in (1500, 1501, 2251, 3001, 15000)] == [-2.0, -2.0, -1.0, 0.0, 0.0]
    assert scheduled_lin_vel_z_weight(750) == -1.0  # existing EX-36 absolute default

    class Manager:
        def __init__(self):
            self.term = SimpleNamespace(weight=-2.0)
            self.values = []

        def get_term_cfg(self, name):
            assert name == "lin_vel_z"
            return self.term

        def set_term_cfg(self, name, term):
            assert name == "lin_vel_z"
            self.values.append(term.weight)

    manager = Manager()
    env = SimpleNamespace(unwrapped=SimpleNamespace(reward_manager=manager))
    for it in (1501, 2251, 3001):
        set_lin_vel_z_weight(env, it, start_iteration=1501)
    assert manager.values == [-2.0, -1.0, 0.0]
