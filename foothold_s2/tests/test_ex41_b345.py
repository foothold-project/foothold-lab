"""D93/D101/S2c known-input checks.  No Kit or CUDA is used."""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import OBS_GROUPS, StartActorCritic
from foothold_s2.runners.ex41_critic_mirror import mirror_critic, value_loss
from foothold_s2.runners.ex41_transfer import policy_state
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


PARENT_SHA = "3a2cd2902c77b069ef1072d08e8254deadf663b56a9c95be704b07db52db2368"
W72_AUTHORIZATION = json.loads((Path(__file__).parent / "fixtures" / "ex41_authorization.json").read_text(encoding="utf-8"))


class PoseEnv(FakeStartEnv):
    def _make(self):
        raw = super()._make()
        raw["pose_cmd"] = torch.zeros(self.num_envs, 2)
        return raw


def pose_runner(mirror=False, parent_mode=False):
    perception = {"microbatch_envs": 2}
    if parent_mode:
        perception.update({"critic_mode": "clean52", "map_input": "reconstruction",
                           "force_gt": True, "p_map_off": 0.1, "map_switch_seed": 20251025,
                           "learning_rate": 0.0005, "depth_delay_ticks": None})
    cfg = train_cfg(2, perception)
    cfg["ex41_pose_commands"] = True
    cfg["ex41_critic_mirror"] = mirror
    if mirror:
        cfg["ex41_mirror_approval"] = dict(W72_AUTHORIZATION)
    return StartRunner(PoseEnv(num_envs=4), cfg, device="cpu")


def test_pose_is_appended_and_zero_stage_rejects_nonzero():
    runner = pose_runner()
    assert runner.ex41_critic_mirror is False and runner.alg.mirror_enabled is False
    raw = runner.env.get_observations()
    out = runner._ppo_obs(raw, torch.zeros(4, 51))
    assert out["actor_in"].shape == (4, 98)
    assert out["critic_in"].shape == (4, 666)
    assert torch.equal(out["actor_in"][:, :45], raw["policy"])
    assert torch.equal(out["actor_in"][:, -2:], raw["pose_cmd"])
    assert runner.perception.init_state(4, "cpu").hist.shape == (4, 10, 45)
    raw["pose_cmd"][0, 0] = 0.1
    with pytest.raises(ValueError, match="must be finite and zero"):
        runner._ppo_obs(raw, torch.zeros(4, 51))
    with pytest.raises(ValueError, match="W72 APPROVED"):
        runner.set_ex41_critic_mirror(True)
    wrong = dict(W72_AUTHORIZATION, approval_id="d" * 64)
    with pytest.raises(ValueError, match="W72 APPROVED"):
        runner.set_ex41_critic_mirror(True, wrong)
    runner.set_ex41_critic_mirror(True, dict(W72_AUTHORIZATION))
    assert runner.alg.mirror_enabled is True


def test_parent_zero_columns_bit_equal_and_adam_moments():
    path = os.environ.get("EX41_PARENT_CHECKPOINT")
    if not path or not os.path.isfile(path):
        pytest.skip("set EX41_PARENT_CHECKPOINT to the verified m7500 file")
    torch.set_num_threads(1)
    parent = torch.load(path, map_location="cpu", weights_only=False)
    runner = pose_runner(parent_mode=True)
    # The parent used a CUDA Philox generator (16-byte state).  CPU PyTorch
    # generators use a different representation, so capture the exact state
    # passed to the runtime restore without pretending CPU can execute it.
    class CapturingGenerator:
        state = None

        def set_state(self, state):
            self.state = state.clone()

    captured = CapturingGenerator()
    runner.map_switch_gen = captured
    # Test the actual parent and the strict SHA gate, without restoring an EX-40 env.
    with pytest.raises(ValueError, match="SHA256"):
        runner.load_ex41_parent(path, "0" * 64)
    receipt = runner.load_ex41_parent(path, PARENT_SHA)
    assert torch.equal(captured.state, parent["map_switch"]["generator_state"])
    assert receipt["parent_iteration"] == 7500 and runner.current_learning_iteration == 7500
    assert runner.alg.learning_rate == parent["ppo_learning_rate"]
    target = runner.alg.policy.state_dict()
    expanded = policy_state(parent["model_state_dict"], target)
    loaded_adam = runner.alg.optimizer.state_dict()
    source_adam = parent["optimizer_state_dict"]
    names = [name for name, _ in runner.alg.policy.named_parameters()]
    for old_id, new_id, name in zip(source_adam["param_groups"][0]["params"],
                                    loaded_adam["param_groups"][0]["params"], names, strict=True):
        for key in ("exp_avg", "exp_avg_sq"):
            old_moment = source_adam["state"][old_id][key]
            new_moment = loaded_adam["state"][new_id][key]
            if name in ("actor.0.weight", "critic.0.weight"):
                assert torch.equal(new_moment[:, :-2], old_moment)
                assert torch.count_nonzero(new_moment[:, -2:]) == 0
            else:
                assert torch.equal(new_moment, old_moment)
    for name in ("actor.0.weight", "critic.0.weight"):
        assert torch.count_nonzero(expanded[name][:, -2:]) == 0
        assert torch.equal(expanded[name][:, :-2], parent["model_state_dict"][name])
    old_obs = TensorDict({"actor_in": torch.randn(4, 96), "critic_in": torch.randn(4, 664)}, batch_size=[4])
    old = StartActorCritic(old_obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False)
    old.load_state_dict(parent["model_state_dict"])
    new_obs = old_obs.clone()
    new_obs["actor_in"] = torch.cat([old_obs["actor_in"], torch.zeros(4, 2)], -1)
    new_obs["critic_in"] = torch.cat([old_obs["critic_in"], torch.zeros(4, 2)], -1)
    with torch.no_grad():
        assert torch.equal(old.act_inference(old_obs), runner.alg.policy.act_inference(new_obs))
        assert torch.equal(old.evaluate(old_obs), runner.alg.policy.evaluate(new_obs))
        assert torch.equal(old.std, runner.alg.policy.std)
    assert all(torch.equal(parent["perception_state_dict"][k], v) for k, v in runner.perception.state_dict().items())
    # Before an update, nonzero new inputs are intentionally inert.  After a
    # gradient step they must become consumable without moving perception.
    nonzero = new_obs.clone()
    nonzero["actor_in"][:, -2:] = torch.tensor([0.1, -0.2])
    nonzero["critic_in"][:, -2:] = torch.tensor([0.1, -0.2])
    assert not torch.equal(nonzero["actor_in"], new_obs["actor_in"])
    runner.alg.optimizer.zero_grad()
    loss = runner.alg.policy.act_inference(nonzero).square().sum() + runner.alg.policy.evaluate(nonzero).square().sum()
    loss.backward()
    assert runner.alg.policy.actor[0].weight.grad[:, -2:].abs().sum() > 0
    assert runner.alg.policy.critic[0].weight.grad[:, -2:].abs().sum() > 0
    runner.alg.optimizer.step()
    with torch.no_grad():
        assert not torch.equal(runner.alg.policy.act_inference(nonzero), runner.alg.policy.act_inference(new_obs))


def test_mirror_known_components_and_involution():
    x = torch.arange(666, dtype=torch.float32).unsqueeze(0)
    y = mirror_critic(x)
    assert torch.equal(mirror_critic(y), x)
    assert y[0, 0] == -x[0, 0] and y[0, 1] == x[0, 1]
    assert y[0, 7] == -x[0, 7] and y[0, 8] == -x[0, 8]
    assert y[0, 9] == -x[0, 12] and y[0, 10] == x[0, 13]
    assert y[0, 48] == x[0, 49] and y[0, 50] == x[0, 51]
    assert y[0, 52] == x[0, 67] and y[0, 564] == x[0, 593]
    assert y[0, 664] == x[0, 664] and y[0, 665] == -x[0, 665]
    with pytest.raises(ValueError, match="666"):
        mirror_critic(x[:, :-1])


def test_value_mirror_does_not_require_false_old_mirrored_value():
    v = torch.tensor([[2.0]], requires_grad=True)
    old, returns = torch.tensor([[0.0]]), torch.tensor([[1.0]])
    original = value_loss(v, old, returns, 0.2, True)
    mirrored = (v - returns).square().mean()
    assert original.item() == 1.0 and mirrored.item() == 1.0
    ((original + mirrored) / 2).backward()
    assert v.grad.item() == pytest.approx(2.0)


def test_critic_mirror_runs_one_real_ppo_update_with_expected_loss_keys():
    torch.set_num_threads(1)
    runner = pose_runner(mirror=True)
    runner.alg.num_learning_epochs = 1
    runner.alg.num_mini_batches = 2
    captured = {}
    original = runner.alg.update

    def update():
        captured.update(original())
        return captured

    runner.alg.update = update
    runner.learn(1)
    assert runner.current_learning_iteration >= 0
    assert {"value_function", "value_mirror", "surrogate", "entropy"} <= set(captured)
    assert all(torch.isfinite(torch.tensor(value)) for value in captured.values())


