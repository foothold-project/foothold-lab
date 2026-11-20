"""v29-11: the later-stage parent load (E1F on) reads the averaged perception weights when the parent checkpoint has them.

The evaluation adapter scores a graduated checkpoint with perception_ema when it is there (eval/adapters.py), so the stage that starts from it
must start from the same weights. A real StartPerception carries the weights; only the policy and the optimizers are stubs (as in the
other parent-load tests)."""

from __future__ import annotations

import pytest
import torch

from foothold_s2.eval.adapters import load_s2_runner
from foothold_s2.runners import start_runner
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg
from foothold_s2.tests.test_ex42_e0_launch_cpu import _loader_runner

N = 8
LOCAL, CUMULATIVE = 3, 6003


def _trained(tmp_path, monkeypatch, decay):
    monkeypatch.setattr(start_runner, "PERCEPTION_EMA_DECAY", decay)
    torch.manual_seed(3)
    r = StartRunner(FakeStartEnv(num_envs=N, seed=3), train_cfg(24, {"microbatch_envs": 4, "map_input": "reconstruction"}), log_dir=None, device="cpu")
    torch.manual_seed(9)
    r.learn(LOCAL)
    path = tmp_path / f"model_{LOCAL}_{decay}.pt"
    r.save(str(path))
    return torch.load(path, map_location="cpu", weights_only=False), path


def _receipt(stage_id):
    return {"state": f"parent_verified_for_stage_{stage_id.lower()}", "parent_local_update": LOCAL, "parent_cumulative_update": CUMULATIVE,
            "actor_input_dim": 98, "critic_input_dim": 666,
            "ex41_environment_state_restored": False, "ex41_curriculum_state_restored": False}


def _load(checkpoint, stage_id, capsys, monkeypatch):
    """a fresh loader runner whose perception module is a real StartPerception with other weights than the checkpoint"""
    monkeypatch.setattr(start_runner, "PERCEPTION_EMA_DECAY", 0.0)
    torch.manual_seed(77)
    fresh = StartRunner(FakeStartEnv(num_envs=N, seed=77), train_cfg(24, {"microbatch_envs": 4, "map_input": "reconstruction"}), log_dir=None, device="cpu")
    runner = _loader_runner(float(checkpoint["map_switch"]["p_map_off"]), {**start_runner.MODE_DEFAULTS, **(checkpoint.get("perception_cfg") or {})})
    runner.perception = fresh.perception
    runner.__dict__["_pin_perception_lr"] = lambda *_a, **_k: None
    checkpoint = {**checkpoint, "iter": LOCAL, "ex41_pose_commands": True, "ex41_critic_mirror": False}
    capsys.readouterr()
    kw = {"stage_e1": True, "stage_id": stage_id, "parent_local_update": LOCAL, "parent_cumulative_update": CUMULATIVE, "parent_mirror": False} if stage_id else {"stage_e1": True}
    rc = _receipt(stage_id) if stage_id else {**_receipt("e1"), "state": "parent_verified_for_stage_e1", "parent_local_update": 250, "parent_cumulative_update": 13250}
    if not stage_id:
        checkpoint = {**checkpoint, "iter": 250}
    runner.load_ex42_stage_zero_parent(checkpoint, rc, **kw)
    return runner.perception, capsys.readouterr().out


def test_a_later_stage_loads_the_averaged_weights_the_evaluation_reads_and_prints_the_source(tmp_path, capsys, monkeypatch):
    checkpoint, path = _trained(tmp_path, monkeypatch, 0.98)
    assert checkpoint.get("perception_ema") is not None
    perception, out = _load(checkpoint, "E1F", capsys, monkeypatch)
    assert "EX42_PARENT_PERCEPTION_SOURCE=ema" in out
    capsys.readouterr()
    evaluated, _ = load_s2_runner(FakeStartEnv(num_envs=2), train_cfg(24), str(path), "cpu")
    assert "EVAL_PERCEPTION_SOURCE=ema" in capsys.readouterr().out
    online = checkpoint["perception_state_dict"]
    differs = False
    for key, value in evaluated.perception.state_dict().items():
        assert torch.equal(perception.state_dict()[key], value), key            # the same weights, bit for bit (buffers too)
        differs |= not torch.equal(value, online[key])
    assert differs                                                              # and they are not the online weights


def test_without_the_key_the_load_is_the_online_weights_as_before(tmp_path, capsys, monkeypatch):
    checkpoint, _ = _trained(tmp_path, monkeypatch, 0.0)
    assert "perception_ema" not in checkpoint
    perception, out = _load(checkpoint, "E1F", capsys, monkeypatch)
    assert "EX42_PARENT_PERCEPTION_SOURCE=online" in out and "(" not in out.split("EX42_PARENT_PERCEPTION_SOURCE=")[1].splitlines()[0]
    for key, value in checkpoint["perception_state_dict"].items():
        assert torch.equal(perception.state_dict()[key], value), key


def test_the_first_stage_parent_load_without_a_stage_id_stays_online_even_with_the_key(tmp_path, capsys, monkeypatch):
    checkpoint, _ = _trained(tmp_path, monkeypatch, 0.98)
    perception, out = _load(checkpoint, None, capsys, monkeypatch)
    assert "EX42_PARENT_PERCEPTION_SOURCE=online" in out
    for key, value in checkpoint["perception_state_dict"].items():
        assert torch.equal(perception.state_dict()[key], value), key


def test_an_unusable_key_falls_back_to_the_online_weights_and_says_why(tmp_path, capsys, monkeypatch):
    checkpoint, _ = _trained(tmp_path, monkeypatch, 0.98)
    bad = dict(checkpoint)
    bad["perception_ema"] = {"decay": 0.98, "shadow": {"perception": {}}}
    perception, out = _load(bad, "E1F", capsys, monkeypatch)
    assert "EX42_PARENT_PERCEPTION_SOURCE=online (" in out
    for key, value in checkpoint["perception_state_dict"].items():
        assert torch.equal(perception.state_dict()[key], value), key
