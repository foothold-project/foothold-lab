"""lead 11/26 09:35: EX42_PARENT_POLICY_EMA=1 makes the new-stage parent load put the averaged policy weights the parent
checkpoint carries (policy_ema.shadow.policy) into the policy. Unset = model_state_dict as before. Either way the load prints
EX42_PARENT_POLICY_SOURCE=<ema|online> actor0_sha=<12>. A real StartRunner makes the checkpoint and a real policy takes the load;
the optimizers and the perception are the stubs of the other parent-load tests."""

from __future__ import annotations

import pytest
import torch

from foothold_s2.runners import start_runner
from foothold_s2.runners.start_runner import StartRunner, tensor_sha12
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg
from foothold_s2.tests.test_ex42_e0_launch_cpu import _loader_runner

N = 8
LOCAL, CUMULATIVE = 3, 6003


def _trained(tmp_path):
    torch.manual_seed(3)
    r = StartRunner(FakeStartEnv(num_envs=N, seed=3), train_cfg(24, {"microbatch_envs": 4, "map_input": "reconstruction"}), log_dir=None, device="cpu")
    torch.manual_seed(9)
    r.learn(LOCAL)
    path = tmp_path / f"model_{LOCAL}.pt"
    r.save(str(path))
    return torch.load(path, map_location="cpu", weights_only=False)


def _load(checkpoint, capsys):
    torch.manual_seed(77)
    fresh = StartRunner(FakeStartEnv(num_envs=N, seed=77), train_cfg(24, {"microbatch_envs": 4, "map_input": "reconstruction"}), log_dir=None, device="cpu")
    runner = _loader_runner(float(checkpoint["map_switch"]["p_map_off"]), {**start_runner.MODE_DEFAULTS, **(checkpoint.get("perception_cfg") or {})})
    runner.alg.policy = fresh.alg.policy
    runner.__dict__["_pin_perception_lr"] = lambda *_a, **_k: None
    checkpoint = {**checkpoint, "iter": LOCAL, "ex41_pose_commands": True, "ex41_critic_mirror": False}
    receipt = {"state": "parent_verified_for_stage_e1f", "parent_local_update": LOCAL, "parent_cumulative_update": CUMULATIVE,
               "actor_input_dim": 98, "critic_input_dim": 666,
               "ex41_environment_state_restored": False, "ex41_curriculum_state_restored": False}
    capsys.readouterr()
    runner.load_ex42_stage_zero_parent(checkpoint, receipt, stage_e1=True, stage_id="E1F", parent_local_update=LOCAL,
                                       parent_cumulative_update=CUMULATIVE, parent_mirror=False)
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith("EX42_PARENT_POLICY_SOURCE="))
    return runner.alg.policy, line


def test_unset_loads_model_state_dict_and_on_loads_the_parent_average_with_its_actor_sha(tmp_path, capsys, monkeypatch):
    checkpoint = _trained(tmp_path)
    shadow = checkpoint["policy_ema"]["shadow"]["policy"]
    online = checkpoint["model_state_dict"]
    assert not torch.equal(shadow["actor.0.weight"], online["actor.0.weight"])       # the average moved away from the raw weights

    monkeypatch.delenv(start_runner.PARENT_POLICY_EMA_ENV, raising=False)
    policy, line = _load(checkpoint, capsys)
    assert line == "EX42_PARENT_POLICY_SOURCE=online actor0_sha=%s" % tensor_sha12(online["actor.0.weight"])
    for key, value in policy.state_dict().items():
        assert torch.equal(value, online[key]), key                                  # unset: the raw weights, bit for bit

    monkeypatch.setenv(start_runner.PARENT_POLICY_EMA_ENV, "1")
    policy, line = _load(checkpoint, capsys)
    assert line == "EX42_PARENT_POLICY_SOURCE=ema actor0_sha=%s" % tensor_sha12(shadow["actor.0.weight"])
    for key, value in policy.state_dict().items():
        assert torch.equal(value, shadow.get(key, online[key])), key                 # on: the average (buffers stay the saved ones)


def test_on_without_a_usable_average_or_with_another_value_is_refused(tmp_path, capsys, monkeypatch):
    checkpoint = _trained(tmp_path)
    monkeypatch.setenv(start_runner.PARENT_POLICY_EMA_ENV, "1")
    with pytest.raises(ValueError, match="no policy_ema.shadow.policy"):
        _load({k: v for k, v in checkpoint.items() if k != "policy_ema"}, capsys)
    shadow = dict(checkpoint["policy_ema"]["shadow"]["policy"])
    shadow.pop("actor.0.weight")
    bad = {**checkpoint, "policy_ema": {**checkpoint["policy_ema"], "shadow": {**checkpoint["policy_ema"]["shadow"], "policy": shadow}}}
    with pytest.raises(ValueError, match="does not match the policy"):
        _load(bad, capsys)
    monkeypatch.setenv(start_runner.PARENT_POLICY_EMA_ENV, "2")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        _load(checkpoint, capsys)
