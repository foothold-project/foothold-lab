"""v28f: the perception optimizer learning rate is pinned to start_runner.PERCEPTION_LR_OVERRIDE (1e-4) at construction and after every
restore of a saved perception optimizer (the saved param_groups carry 5e-4). The PPO optimizer and the adaptive-LR value are not touched.
CPU only: real StartRunner on the fake env, real E0 m250 for the stage-zero parent path when this machine has it."""
from __future__ import annotations

import pathlib

import pytest
import torch

from foothold_s2.runners import start_runner
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

ROOT = pathlib.Path(__file__).resolve().parents[2]
E0_RUN = pathlib.Path("/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
if not E0_RUN.is_dir():
    E0_RUN = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
needs_run = pytest.mark.skipif(not (E0_RUN / "model_250.pt").is_file(), reason="the E0 run is not on this machine")
PLAN_SHA = "1f4ff70d8820e2e754ed1120b821fafb22a04e40d7f84f1ff0a9a9cfedff8a92"
APPROVALS_SHA = "80a6079b5d77f6f65e7be71c120982f8e7f1379666bc890f68e2c267a7d10696"


def _runner(seed=3):
    torch.manual_seed(seed)
    # the real E1 process builds the runner from the saved perception_cfg, so the learning rate it hands in is the saved 5e-4
    cfg = train_cfg(24, {"microbatch_envs": 4, "learning_rate": 5e-4})
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), cfg, log_dir=None, device="cpu")


def _lrs(opt):
    return [g["lr"] for g in opt.param_groups]


def test_the_constant_is_one_value_and_on(monkeypatch):
    assert start_runner.PERCEPTION_LR_OVERRIDE == 1e-4
    assert start_runner.PERCEPTION_DEFAULTS["learning_rate"] == 5e-4          # the default table is not edited (plan and saved cfg keep 5e-4)


def test_a_new_runner_starts_at_the_pinned_lr_logs_the_optimizer_value_and_leaves_ppo_alone(capsys, monkeypatch):
    runner = _runner()
    out = capsys.readouterr().out
    assert set(_lrs(runner.perception_optimizer)) == {1e-4}
    assert "EX42_PERCEPTION_LR where=start lr=0.0001 override=0.0001" in out
    monkeypatch.setattr(start_runner, "PERCEPTION_LR_OVERRIDE", None)
    plain = _runner()
    assert set(_lrs(plain.perception_optimizer)) == {5e-4}                     # None: the old behavior (the saved / default value)
    assert "EX42_PERCEPTION_LR where=start lr=0.0005 override=None" in capsys.readouterr().out
    assert runner.alg.learning_rate == plain.alg.learning_rate and _lrs(runner.alg.optimizer) == _lrs(plain.alg.optimizer)
    for a, b in zip(runner.perception.parameters(), plain.perception.parameters()):
        assert torch.equal(a, b)                                                # only the lr differs, not the initial weights
    assert runner.pcfg["learning_rate"] == 5e-4                                 # perception_cfg saved in checkpoints is unchanged


def test_the_constant_value_is_what_gets_pinned(monkeypatch):
    monkeypatch.setattr(start_runner, "PERCEPTION_LR_OVERRIDE", 2.5e-4)
    assert set(_lrs(_runner().perception_optimizer)) == {2.5e-4}


def test_restoring_a_saved_5e4_perception_optimizer_is_pinned_again_and_ppo_lr_is_restored_as_saved(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(start_runner, "PERCEPTION_LR_OVERRIDE", None)
    old = _runner()                                                             # a saved checkpoint of the old process: perception lr 5e-4
    old.alg.learning_rate = 3e-4
    for g in old.alg.optimizer.param_groups:
        g["lr"] = 3e-4
    path = tmp_path / "model_1.pt"
    old.save(str(path))
    saved = torch.load(path, map_location="cpu", weights_only=False)
    assert {g["lr"] for g in saved["perception_optimizer_state_dict"]["param_groups"]} == {5e-4}      # precondition: the file carries 5e-4
    monkeypatch.undo()
    new = _runner()
    capsys.readouterr()
    new.load(str(path), map_location="cpu")
    out = capsys.readouterr().out
    assert set(_lrs(new.perception_optimizer)) == {1e-4}                        # load_state_dict restored 5e-4, the pin put 1e-4 back
    assert "EX42_PERCEPTION_LR where=load lr=0.0001" in out
    assert new.alg.learning_rate == 3e-4 and set(_lrs(new.alg.optimizer)) == {3e-4}      # the PPO side is exactly the saved one
    again = new.state_dict()
    assert {g["lr"] for g in again["perception_optimizer_state_dict"]["param_groups"]} == {1e-4}   # and the next save carries 1e-4


def test_load_without_the_optimizer_keeps_whatever_the_runner_has(tmp_path, monkeypatch):
    monkeypatch.setattr(start_runner, "PERCEPTION_LR_OVERRIDE", None)
    old = _runner()
    path = tmp_path / "model_1.pt"
    old.save(str(path))
    monkeypatch.undo()
    new = _runner()
    new.load(str(path), load_optimizer=False, map_location="cpu")
    assert set(_lrs(new.perception_optimizer)) == {1e-4}


@needs_run
def test_real_e0_m250_stage_zero_parent_load_ends_at_the_pinned_lr(capsys):
    from foothold_s2.scripts import ex42_training_entry as entry
    from foothold_s2.tests.test_ex42_e0_launch_cpu import _loader_runner
    from foothold_s2.tests.test_ex42_e1_entry_cpu import _approvals, TABLE
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        checkpoint, receipt = entry.inspect_ex42_stage_e1_parent(
            plan=EX42Plan.load(TABLE), approvals_path=_approvals(pathlib.Path(tmp)), parent_manifest_path=E0_RUN / "manifest.json")
    assert {g["lr"] for g in checkpoint["perception_optimizer_state_dict"]["param_groups"]} == {5e-4}   # the real parent carries 5e-4
    cfg = entry.configure_ex42_stage_zero_train_cfg({}, checkpoint, parent_path=receipt["parent_path"], parent_sha256=receipt["parent_sha256"],
                                                    updates=1750, parent_local_update=250, parent_cumulative_update=13250, stage_id="E1")
    assert cfg["perception"]["learning_rate"] == 5e-4                            # the E1 entry hands the saved 5e-4 on: only the pin changes it
    from foothold_s2.runners import start_runner as sr
    p_off = float(checkpoint["map_switch"]["p_map_off"])
    runner = _loader_runner(p_off, {**sr.MODE_DEFAULTS, **(checkpoint.get("perception_cfg") or {})})
    assert runner.perception_optimizer.param_groups[0]["lr"] == 5e-4
    runner.load_ex42_stage_zero_parent(checkpoint, receipt, stage_e1=True)
    assert [g["lr"] for g in runner.perception_optimizer.param_groups] == [1e-4]
    assert "EX42_PERCEPTION_LR where=load_ex42_stage_zero_parent lr=0.0001" in capsys.readouterr().out


def test_plan_and_approvals_are_not_touched():
    import hashlib

    from foothold_s2.curriculum.ex42_prep import EX42Plan

    assert EX42Plan.load(ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml").sha256 == PLAN_SHA
    assert hashlib.sha256((ROOT / "foothold_s2" / "curriculum" / "ex42-approvals.yaml").read_bytes()).hexdigest() == APPROVALS_SHA
