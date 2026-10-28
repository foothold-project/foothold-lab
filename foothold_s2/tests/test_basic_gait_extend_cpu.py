"""Known-input CPU checks for the EX-36 continuation and m250 W15 chain."""

import copy
import json
import os
from pathlib import Path
import subprocess

import pytest
import torch

from foothold_s2 import basic_gait_extend_eval as evaluation
from foothold_s2 import basic_gait_extend_launch as launch
from foothold_s2.basic_gait_extend_parent import check_parent, sha256_file
from foothold_s2.eval.map_mode_cells import SEQUENCES, commands


END = "2026-11-01T08:00:00+09:00"


def parent_fixture(tmp_path: Path, arm: str):
    iteration = {"A": 3000, "B": 1500}[arm]
    run_dir = tmp_path / "main" / f"EX-36{arm}-basic-share30_20261029_fixture_1"
    run_dir.mkdir(parents=True)
    checkpoint = run_dir / f"model_{iteration}.pt"
    state = {"format": "foothold-start/1", "iter": iteration,
             "sol23f": {"variant": "SB_map_switch", "force_gt": True,
                        "map_input": "reconstruction", "depth_delay_ticks": 1},
             "env_seed": 42, "model_state_dict": {"normalizer.weight": torch.ones(1)},
             "optimizer_state_dict": {"state": {0: {"step": torch.tensor(1.)}}},
             "ppo_learning_rate": 0.0002,
             "perception_state_dict": {"encoder.weight": torch.ones(1)},
             "perception_optimizer_state_dict": {"state": {0: {"step": torch.tensor(1.)}}},
             "perception_cfg": {"contract": "basic_gait_v1", "map_input": "reconstruction",
                                "force_gt": True, "p_map_off": 0.1},
             "adasmpl": {"force_gt": True, "p": 1.},
             "map_switch": {"p_map_off": 0.1, "generator_state": torch.ones(1)},
             "env_state": {"terrain_levels": torch.arange(3072) % 3,
                           "terrain_types": torch.arange(3072) % 23},
             "rng": {"torch": torch.ones(1)}}
    torch.save(state, checkpoint)
    digest = sha256_file(checkpoint)
    name = f"EX-36{arm}-basic-share30"
    start = {"stage": "main", "run_name": name, "env_seed": 42, "command_seed": 42,
             "num_envs": 3072, "terrain_policy": "fixed_l02",
             "terrain_levels_l0_l1_l2": [1024, 1024, 1024]}
    modes = {"task": "FootholdS2-Go2-S2-SB-v0", "seed": 42, "num_envs": 3072,
             "num_steps_per_env": 24, "map_input": "reconstruction", "force_gt": True,
             "p_map_off": 0.1, "command_settings": {"command_mode": "basic_gait",
             "command_contract": "basic_gait_v1", "clock_scatter": True, "basic_new_share": 0.3}}
    manifest = {"checkpoints": {checkpoint.name: digest}, "run": {"name": name},
                "modes": modes, "progress": {"completed_updates": iteration + 1}}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "basic_start_receipt.json").write_text(json.dumps(start), encoding="utf-8")
    (run_dir / "status.json").write_text(json.dumps({"state": "done", "iter": iteration}), encoding="utf-8")
    return checkpoint, digest, state


@pytest.mark.parametrize("arm,total", [("A", 3501), ("B", 2001)])
def test_parent_and_launch_preserve_state_and_total_budget(tmp_path, arm, total):
    checkpoint, digest, state = parent_fixture(tmp_path, arm)
    before = checkpoint.read_bytes()
    source = check_parent(checkpoint, arm, digest)
    assert source["completed_update"] == total - 501
    assert "optimizer_state_dict" in source["restored_by_runner"]
    args, receipt = launch.prepare(arm, "cuda:0", str(checkpoint), digest, 500, END,
                                   str(tmp_path / "extend"))
    assert args[args.index("--max_iterations") + 1] == str(total)
    assert args[args.index("--basic-extend-arm") + 1] == arm
    assert args[args.index("--seed") + 1] == "42"
    assert args[args.index("--clock_scatter") + 1] == "on"
    assert args[args.index("--p_map_off") + 1] == "0.1"
    assert args[args.index("--basic-new-share") + 1] == "0.3"
    assert receipt["first_update"] == total - 500 and receipt["last_update"] == total - 1
    assert receipt["physical_resume_identical"] is False
    assert checkpoint.read_bytes() == before
    assert state["model_state_dict"] and state["optimizer_state_dict"]


def test_parent_rejects_wrong_sha_incomplete_run_and_changed_map_state(tmp_path):
    checkpoint, digest, state = parent_fixture(tmp_path, "A")
    with pytest.raises(ValueError, match="SHA mismatch"):
        check_parent(checkpoint, "A", "0" * 64)
    status = checkpoint.parent / "status.json"
    status.write_text(json.dumps({"state": "running", "iter": 2999}), encoding="utf-8")
    with pytest.raises(ValueError, match="not complete"):
        check_parent(checkpoint, "A", digest)
    status.write_text(json.dumps({"state": "done", "iter": 3000}), encoding="utf-8")
    state = copy.deepcopy(state)
    state["map_switch"]["p_map_off"] = 0.5
    torch.save(state, checkpoint)
    manifest_path = checkpoint.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][checkpoint.name] = sha256_file(checkpoint)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="map-choice"):
        check_parent(checkpoint, "A", sha256_file(checkpoint))


def test_budget_and_wrong_arm_rejected(tmp_path):
    checkpoint, digest, _state = parent_fixture(tmp_path, "B")
    with pytest.raises(ValueError, match="filename|iteration"):
        check_parent(checkpoint, "A", digest)
    with pytest.raises(ValueError, match="budget"):
        launch.prepare("B", "cuda:1", str(checkpoint), digest, 1501, END, str(tmp_path / "extend"))
    with pytest.raises(ValueError, match="stop file"):
        launch.prepare("B", "cuda:1", str(checkpoint), digest, 1, END, str(tmp_path / "extend"),
                       str(checkpoint))


def test_shell_dry_receipt_does_not_start_training(tmp_path):
    shell = Path("C:/Program Files/Git/bin/bash.exe")
    if not shell.is_file():
        pytest.skip("Git Bash unavailable")
    checkpoint, digest, _state = parent_fixture(tmp_path, "B")
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.update(END_BY=END, BASIC_LOG_ROOT=str(tmp_path / "extend"), LIVE="0", CUDA_VISIBLE_DEVICES="")
    child = subprocess.run([str(shell), str(root / "foothold_s2/run_basic_gait_extend.sh"),
                            "B", "cuda:1", str(checkpoint), digest, "1"],
                           cwd=root, env=env, capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr
    assert "DRY: training not started" in child.stdout
    receipts = list((tmp_path / "extend" / "receipts" / "extend").glob("*/launch_receipt.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text(encoding="utf-8"))["training_started"] is False
    assert not (tmp_path / "extend" / "main").exists()


def _fake_eval(out: Path, checkpoint: Path, iteration: int):
    (out / "map64").mkdir(parents=True)
    row = {"checkpoint_iter": iteration, "checkpoint_sha256": evaluation.once.sha256_file(checkpoint),
           "command_suite": "extended", "commands": commands("extended"),
           "terrain_tiles": [{"env": i} for i in range(64)],
           "modes": {mode: {name: {} for name in commands("extended")} for mode in evaluation.once.MODES},
           "sequences": {mode: {name: {} for name in SEQUENCES} for mode in evaluation.once.MODES}}
    (out / "map64" / "map_modes.json").write_text(json.dumps(row), encoding="utf-8")
    (out / "rc.txt").write_text("\n".join([*(f"turn16_{mode} rc=0" for mode in evaluation.once.MODES),
                                           "map64 rc=0"]), encoding="utf-8")
    for mode in evaluation.once.MODES:
        (out / f"turn16_{mode}").mkdir()
        (out / f"turn16_{mode}" / "run.log").write_text("TURNPROBE_DONE\n", encoding="utf-8")


def test_sequential_m250_done_and_bad_receipt_caught(tmp_path):
    run_dir = tmp_path / "extend_run"
    run_dir.mkdir()
    for iteration in (1750, 2000):
        (run_dir / f"model_{iteration}.pt").write_bytes(f"checkpoint{iteration}".encode())
    manifest = {"run": {"name": "EX-36B-basic-extend-share30"},
                "modes": {"resume_parent": {"basic_extend": {"arm": "B", "completed_update": 1500}},
                          "basic_terrain_cfg_difference": "fixed_l02", "seed": 42, "p_map_off": 0.1},
                "checkpoints": {f"model_{iteration}.pt": sha256_file(run_dir / f"model_{iteration}.pt")
                                for iteration in (1750, 2000)},
                "progress": {"completed_updates": 2001}}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "status.json").write_text(json.dumps({"state": "done", "iter": 2000}), encoding="utf-8")
    out = tmp_path / "eval"
    assert [j["iteration"] for j in evaluation.plan(run_dir, out, "B", 2000, require_done=True)["jobs"]] == [1750, 2000]
    called = []

    def evaluator(_device, checkpoint, iteration, target):
        called.append(iteration)
        _fake_eval(target, checkpoint, iteration)

    rows = evaluation.run_chain(run_dir, out, "B", 2000, "cuda:1", "CPU-approved-fixture", evaluator=evaluator)
    assert called == [1750, 2000] and len(rows) == 2
    assert all((out / f"m{it}" / ".done").is_file() for it in called)
    evaluation.run_chain(run_dir, out, "B", 2000, "cuda:1", "CPU-approved-fixture", evaluator=evaluator)
    assert called == [1750, 2000]
    (run_dir / "model_1750.pt").write_bytes(b"mutated")
    with pytest.raises(ValueError, match="training manifest SHA"):
        evaluation.run_chain(run_dir, out, "B", 2000, "cuda:1", "CPU-approved-fixture", evaluator=evaluator)


def test_chain_rejects_running_source_and_no_authorization(tmp_path):
    assert evaluation.planned_iterations("A", 3500) == (3250, 3500)
    assert evaluation.planned_iterations("B", 2000) == (1750, 2000)
    with pytest.raises(ValueError, match="authorization"):
        evaluation.run_chain(tmp_path, tmp_path / "out", "B", 2000, "cuda:0", "")
