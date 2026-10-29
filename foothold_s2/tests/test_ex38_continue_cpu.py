"""Known-input checks for EX-38 continuation, prestart, and W15 table."""

from __future__ import annotations

import hashlib
from datetime import datetime
from importlib.metadata import version
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch
import rsl_rl
import rsl_rl.utils

EXPECTED_PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
assert Path(sys.executable).resolve() == EXPECTED_PYTHON.resolve(), f"use {EXPECTED_PYTHON} for this test"
assert version("rsl-rl-lib") == "3.1.2"
assert "site-packages" in Path(rsl_rl.__file__).parts
assert hasattr(rsl_rl.utils, "store_code_state")

from foothold_s2 import basic_gait_ex38_continue as ex38
from foothold_s2 import prestart_check
from foothold_s2 import w15_one_table
from foothold_s2.sol23f_contract import TASKS, check_resume_parent, validate_launch
from foothold_s2.rewards.basic_gait_bundle import E1_CANDIDATE, scheduled_lin_vel_z_weight
from foothold_s2.runners.start_runner import CKPT_FORMAT


def parent_fixture(tmp_path: Path, iteration=3001) -> tuple[Path, str]:
    run = tmp_path / "main" / "EX-38-basic-e1rew_20261029_030422_76136"
    run.mkdir(parents=True)
    checkpoint = run / f"model_{iteration}.pt"
    state = {"format": CKPT_FORMAT, "sol23f": {"variant": "SB_map_switch", "depth_delay_ticks": 1},
             "iter": iteration, **{key: {} for key in (
                 "model_state_dict", "optimizer_state_dict", "perception_state_dict",
                 "perception_optimizer_state_dict", "adasmpl", "env_state", "rng")}}
    torch.save(state, checkpoint)
    sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {"run": {"name": "EX-38-basic-e1rew"},
                "modes": {"basic_ex38": True, "basic_reward_schedule_start_iteration": 1501,
                          "basic_reward_bundle": {"lin_vel_z_schedule": True, "weights": E1_CANDIDATE},
                          "command_settings": {"command_mode": "basic_gait", "basic_new_share": 0.30,
                                               "clock_scatter": True},
                          "seed": 42, "p_map_off": 0.1, "basic_terrain_cfg_difference": "fixed L0..2",
                          "depth_camera_enabled": True, "perception_training_enabled": True,
                          "fast_gt_only": False},
                "checkpoints": {checkpoint.name: sha}}
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run / "train_start_status.json").write_text(json.dumps({"state": "stopped_saved", "iter": iteration,
                                                    "checkpoint": str(checkpoint), "sha256": sha}), encoding="utf-8")
    return checkpoint, sha


def test_ex38_completed_parent_and_relative_schedule(tmp_path):
    checkpoint, sha = parent_fixture(tmp_path)
    args, row = ex38.prepare("cuda:1", str(checkpoint), sha, "2026-10-30T12:30:00+09:00",
                            str(tmp_path / "new_runs"))
    assert row["first_update"] == 3002 and row["last_update"] == 4501
    assert row["additional_updates"] == 1500 and row["schedule_at_parent"] == 0.0
    assert row["parent"]["sha256"] == sha and row["reward_schedule_start_iteration"] == 1501
    assert row["reward_schedule_at_first_update"] == scheduled_lin_vel_z_weight(3002, start_iteration=1501) == 0.0
    assert "--basic-ex38-continue-parent-sha" in args
    assert prestart_check.inspect_args(args)["max_iterations"] == 4502
    assert prestart_check.inspect_args(args)["basic_ex38_continue_parent_sha"] == sha
    assert ex38.check_parent(str(checkpoint), sha)["completed_update"] == 3001
    assert check_resume_parent(SimpleNamespace(resume_from=str(checkpoint), basic_ex38=True,
                                               basic_ex38_continue_parent_sha=sha,
                                               max_iterations=4502, smoke_updates=None,
                                               basic_extend_arm=None)) == 3001
    parser = prestart_check.actual_parser()
    ns, _ = parser.parse_known_args(["--task", TASKS["SB"], "--variant", "SB", *args])
    now = datetime.fromisoformat("2026-10-29T17:00:00+09:00").timestamp()
    assert validate_launch(ns, now=now, verify_parent=True) > now
    ns.max_iterations = 4501
    assert validate_launch(ns, now=now, verify_parent=True) > now
    for over_budget in (4503, 6001, 20001):
        ns.max_iterations = over_budget
        with pytest.raises(ValueError, match="at most 4502"):
            validate_launch(ns, now=now, verify_parent=True)


def test_ex38_parent_mutations_caught(tmp_path):
    checkpoint, sha = parent_fixture(tmp_path)
    earlier, earlier_sha = parent_fixture(tmp_path / "other", iteration=3000)
    with pytest.raises(ValueError, match="iteration"):
        ex38.check_parent(str(earlier), earlier_sha)
    with pytest.raises(ValueError, match="SHA256"):
        ex38.check_parent(str(checkpoint), "0" * 64)
    manifest_path = checkpoint.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["modes"]["basic_reward_schedule_start_iteration"] = 3002
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="settings differ"):
        ex38.check_parent(str(checkpoint), sha)
    manifest["modes"]["basic_reward_schedule_start_iteration"] = 1501
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (checkpoint.parent / "train_start_status.json").write_text(json.dumps({"state": "running", "iter": 3001,
                                                                "checkpoint": str(checkpoint), "sha256": sha}), encoding="utf-8")
    with pytest.raises(ValueError, match="completed receipt"):
        ex38.check_parent(str(checkpoint), sha)


def _summary(alive: int, vx: float, displacement: float) -> dict:
    return {"per_env": [{"alive_at_end": i < alive, "vx_abs_error_mean_alive_mps": vx,
                          "vy_abs_error_mean_alive_mps": 0.2, "wz_abs_error_mean_alive_radps": 0.1,
                          "world_xy_displacement_m": displacement if i < alive else None}
                         for i in range(64)]}


def test_w15_table_measured_missing_and_cross_device_width(tmp_path):
    root = tmp_path / "a" / "m1750"
    for device, survived in (("gpu0", 60), ("gpu1", 62)):
        out = root / f"attempt_{device}" / "map64"
        out.mkdir(parents=True)
        data = {"command_suite": "extended", "checkpoint_iter": 1750,
                "terrain_tiles": [{"env": i} for i in range(64)],
                "checkpoint_sha256": "a" * 64, "eval_seed": 42,
                "terrain_hash": "b" * 64, "source_sha256": "c" * 64,
                "run_identity": {"gpu_uuid": device},
                "modes": {"eval_gt": {"spin+1.2": _summary(survived, .3, 1.0)}},
                "sequences": {}}
        (out / "map_modes.json").write_text(json.dumps(data), encoding="utf-8")
    rows = []
    for iteration, path in w15_one_table._files(tmp_path / "a"):
        rows += w15_one_table.read_receipt("EX-36A", iteration, path)
    assert len(rows) == 64
    measured = [r for r in rows if r["mode"] == "eval_gt" and r["command"] == "spin+1.2"]
    assert [r["survived"] for r in measured] == [60, 62]
    assert [r["device"] for r in measured] == ["gpu0", "gpu1"]
    collapsed = w15_one_table.collapse(rows)
    spin = [r for r in collapsed if r["mode"] == "eval_gt" and r["command"] == "spin+1.2"]
    assert len(spin) == 1 and spin[0]["repeat_survival_width"] == 2 / 64
    altered = dict(measured[1], repeat_identity=("different", 42, "b" * 64, "c" * 64))
    with pytest.raises(ValueError, match="repeat sources differ"):
        w15_one_table.collapse([measured[0], altered])
    assert all("envs" not in r for r in rows if r["command"] == "back0.5")


def test_prestart_real_modules_and_negative_argparse(tmp_path):
    args = ["--headless", "--device", "cuda:1", "--num_envs", "3072", "--seed", "42",
            "--run_name", "EX-38-basic-e1rew", "--end-by", "2026-10-30T12:30:00+09:00",
            "--max_iterations", "3002", "--basic-ex38", "--basic-joint-acc-weight=-1e-7",
            "--kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache"]
    path = tmp_path / "launch_args.txt"
    path.write_text("\n".join(args) + "\n", encoding="utf-8")
    assert prestart_check.check(path, git_check=False)["state"] == "prestart_pass"
    path.write_text("\n".join(a.replace("--basic-joint-acc-weight=-1e-7", "--basic-joint-acc-weight\n-1e-7")
                               for a in args), encoding="utf-8")
    with pytest.raises(SystemExit):
        prestart_check.check(path, git_check=False)
