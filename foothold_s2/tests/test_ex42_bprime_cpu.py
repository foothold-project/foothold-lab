"""CPU contracts for the opt-in EX-42 first-flag bearing experiment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.commands import ex42_bprime as bp
from foothold_s2.runners.ex42_bprime_transfer import optimizer_state, policy_state
from foothold_s2.runners.ex41_critic_mirror import mirror_critic
from foothold_s2.runners.start_runner import StartRunner


def test_bearing_first_flag_and_command_turn_without_scripted_wz():
    flags = torch.tensor([[[0., 2.]], [[0., 2.]], [[2., 0.]]])
    index = torch.tensor([0, 1, 0])
    count = torch.ones(3, dtype=torch.long)
    pos = torch.zeros(3, 2)
    yaw = torch.zeros(3)
    bearing = bp.first_flag_bearing(flags, index, count, pos, yaw,
                                    torch.tensor([True, True, False]))
    assert torch.equal(bearing[0], torch.tensor([1., 0., 1.]))
    assert torch.equal(bearing[1:], torch.zeros(2, 3))
    command = torch.tensor([[0.5, 0., 1.], [0.5, 0., 1.], [0.5, 0., 1.]])
    got, turn = bp.command_for_learned_turn(command, bearing, 0.25)
    assert turn.tolist() == [True, False, False]
    assert torch.equal(got[0], torch.zeros(3))
    assert torch.equal(got[1:], command[1:])
    assert torch.equal(bp.heading_alignment_reward(bearing), torch.tensor([0.5, 0., 0.]))


def test_bprime_default_off_and_explicit_threshold():
    assert bp.read_config({}) is None
    assert bp.read_config({"EX42_BPRIME": "0"}) is None
    assert bp.read_config({"EX42_BPRIME": "1"}) == {"turn_rad": 0.25, "heading_weight": 1.0}
    with pytest.raises(ValueError):
        bp.read_config({"EX42_BPRIME_TURN_RAD": "0.25"})
    with pytest.raises(ValueError):
        bp.read_config({"EX42_BPRIME": "1", "EX42_BPRIME_TURN_RAD": "0.025"})


def test_ppo_observation_appends_only_three_bearing_columns():
    class Term:
        cfg = SimpleNamespace(bprime_turn_rad=0.25)

        @staticmethod
        def flag_bearing_obs():
            return torch.tensor([[0., 0., 0.], [1., 1., 0.]])

    raw = TensorDict({"policy": torch.zeros(2, 45), "depth": torch.zeros(2, 60, 60),
                      "gt_map": torch.zeros(2, 512), "gt_feet": torch.zeros(2, 100),
                      "base_vel": torch.zeros(2, 3), "contacts": torch.zeros(2, 4),
                      "critic": torch.zeros(2, 52), "pose_cmd": torch.zeros(2, 2)}, [2])
    runner = StartRunner.__new__(StartRunner)
    runner.pcfg = {"est_mode": "zero", "critic_mode": "clean52"}
    runner.ex41_pose_commands = True
    runner.ex42_bprime = True
    runner._command_term = lambda: Term()
    obs = runner._ppo_obs(raw, torch.zeros(2, 51))
    assert obs["actor_in"].shape == (2, 101)
    assert obs["critic_in"].shape == (2, 669)
    assert torch.equal(obs["actor_in"][:, -3:], Term.flag_bearing_obs())
    assert torch.equal(obs["critic_in"][:, -3:], Term.flag_bearing_obs())
    runner.ex42_bprime = False
    old = runner._ppo_obs(raw, torch.zeros(2, 51))
    assert old["actor_in"].shape == (2, 98) and old["critic_in"].shape == (2, 666)
    assert torch.equal(obs["actor_in"][:, :-3], old["actor_in"])
    assert torch.equal(obs["critic_in"][:, :-3], old["critic_in"])


def test_zero_column_transfer_preserves_parent_output_and_adam_moments():
    torch.manual_seed(42)
    parent = {"actor.0.weight": torch.randn(512, 98),
              "critic.0.weight": torch.randn(512, 666),
              "actor.0.bias": torch.randn(512)}
    target = {"actor.0.weight": torch.zeros(512, 101),
              "critic.0.weight": torch.zeros(512, 669),
              "actor.0.bias": torch.zeros(512)}
    widened = policy_state(parent, target)
    assert torch.equal(widened["actor.0.weight"][:, :98], parent["actor.0.weight"])
    assert torch.count_nonzero(widened["actor.0.weight"][:, 98:]) == 0
    old_actor = torch.nn.Linear(98, 512)
    new_actor = torch.nn.Linear(101, 512)
    old_actor.weight.data.copy_(parent["actor.0.weight"])
    new_actor.weight.data.copy_(widened["actor.0.weight"])
    old_actor.bias.data.copy_(parent["actor.0.bias"])
    new_actor.bias.data.copy_(parent["actor.0.bias"])
    x = torch.randn(64, 98)
    y = new_actor(torch.cat((x, torch.zeros(64, 3)), -1))
    assert torch.equal(old_actor(x), y), (old_actor(x) - y).abs().max()
    # The zero columns preserve the parent output, but a nonzero bearing must
    # leave a gradient so the first-flag response can be learned.
    new_actor.zero_grad(set_to_none=True)
    learn_input = torch.cat((x[:4], torch.tensor([[1., 0., 1.]] * 4)), -1)
    new_actor(learn_input).sum().backward()
    assert torch.count_nonzero(new_actor.weight.grad[:, 98:]) > 0
    old_opt = {"param_groups": [{"params": [0, 1, 2], "lr": 1.0e-4}],
               "state": {0: {"step": torch.tensor(17.), "exp_avg": parent["actor.0.weight"].clone(),
                              "exp_avg_sq": parent["actor.0.weight"].square()},
                         1: {"step": torch.tensor(17.), "exp_avg": parent["critic.0.weight"].clone(),
                             "exp_avg_sq": parent["critic.0.weight"].square()}}}
    new_opt = {"param_groups": [{"params": [0, 1, 2], "lr": 1.0e-3}], "state": {}}
    got = optimizer_state(old_opt, new_opt, list(parent), list(target))
    assert got["param_groups"][0]["lr"] == 1.0e-4
    assert got["state"][0]["step"].item() == 17
    assert torch.equal(got["state"][0]["exp_avg"][:, :98], old_opt["state"][0]["exp_avg"])
    assert torch.count_nonzero(got["state"][0]["exp_avg"][:, 98:]) == 0
    assert torch.count_nonzero(got["state"][1]["exp_avg_sq"][:, 666:]) == 0


def test_mirror_of_new_critic_bearing_is_an_involution():
    x = torch.randn(3, 669)
    y = mirror_critic(x)
    assert torch.equal(y[:, -3:], x[:, -3:] * torch.tensor([1., 1., -1.]))
    assert torch.equal(mirror_critic(y), x)
