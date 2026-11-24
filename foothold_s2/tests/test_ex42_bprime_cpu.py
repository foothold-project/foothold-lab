"""CPU contracts for the opt-in EX-42 first-flag bearing experiment."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import sys

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.commands import ex42_bprime as bp
from foothold_s2.runners.ex42_bprime_transfer import optimizer_state, policy_state
from foothold_s2.runners.ex41_critic_mirror import mirror_critic
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.eval.adapters import S2Policy, load_s2_runner
from foothold_s2.eval.ex41_eval_loader import load_checkpoint_for_eval
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


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


def test_bprime_turn_exposure_counts_the_learned_branch_not_the_scripted_branch():
    index = torch.tensor([0, 0, 1, 0])
    selected = torch.ones(4, dtype=torch.bool)
    # The scripted mask is all false, but the learned B-prime branch turned twice.
    assert bp.turn_exposure_counts(index, torch.tensor([True, False, False, True]), selected) == (
        2.0, 4.0, 2.0, 3.0, 0.0, 1.0)
    assert bp.turn_exposure_counts(index, torch.tensor([False, False, True, False]), selected) == (
        1.0, 4.0, 0.0, 3.0, 1.0, 1.0)


def test_real_command_term_reports_bprime_turn_exposure(monkeypatch):
    from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

    term, _, _ = e1f_term(monkeypatch, {}, n=64)
    term.cfg.bprime_turn_rad = 0.25
    term.flag_state.idx[:4] = torch.tensor([0, 0, 1, 1])
    term.flag_state.turning = torch.zeros(64, dtype=torch.bool)
    term.flag_state.turning_first = torch.zeros(64, dtype=torch.bool)
    term.bprime_turn_mask.zero_()
    term.bprime_turn_mask[0] = True
    selected = torch.zeros(64, dtype=torch.bool)
    selected[:4] = True
    term._record_flag_turn_exposure(selected)
    assert term.flag_turn_summary() == (0.25, 0.25, 4.0)
    assert term.flag_turn_last_detail == ("first", 0.5, 2.0, 0.0, 2.0)


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


def test_real_eval_entry_loads_one_update_bprime_checkpoint(tmp_path: Path, monkeypatch):
    """The production evaluation entry must build 101/669 before loading weights."""
    class Env(FakeStartEnv):
        def __init__(self):
            super().__init__(num_envs=4)
            self._obs["pose_cmd"] = torch.zeros(4, 2)
            term = SimpleNamespace(cfg=SimpleNamespace(bprime_turn_rad=0.25),
                                   flag_bearing_obs=lambda: torch.zeros(4, 3))
            self.command_manager = SimpleNamespace(get_term=lambda _name: term)

    cfg = train_cfg(2, perception={"microbatch_envs": 4, "map_input": "reconstruction"})
    cfg.update(ex41_pose_commands=True, ex42_bprime=True, ex42_bprime_turn_rad=0.25)
    original = StartRunner(Env(), cfg, device="cpu")
    # One CPU optimizer update creates a real saved B-prime learner state.
    original.alg.optimizer.zero_grad(set_to_none=True)
    original.alg.policy.actor(torch.randn(4, 101)).square().mean().backward()
    original.alg.optimizer.step()
    original.current_learning_iteration = 1
    saved = original.state_dict()
    loaded, state = load_s2_runner(Env(), train_cfg(2), str(tmp_path / "model_1.pt"),
                                   "cpu", checkpoint_state=saved)
    assert state["ex42_bprime"] is True
    assert loaded.ex42_bprime and loaded.alg.policy.actor[0].in_features == 101
    assert loaded.alg.policy.critic[0].in_features == 669
    assert all(torch.equal(value, loaded.alg.policy.state_dict()[key])
               for key, value in saved["model_state_dict"].items())
    eval_action = S2Policy(loaded, 4, z_mode="mean", act_mode="mean", map_mode="eval_pred")(
        loaded.env.get_observations())
    assert eval_action.shape == (4, 12) and torch.isfinite(eval_action).all()

    # The before-gym.make loader prepares the actual command term's threshold.
    def zero_pose_command(_env):
        return None
    def apply(cfg):
        cfg.observations.pose_cmd = SimpleNamespace(
            pose_cmd=SimpleNamespace(func=zero_pose_command),
            enable_corruption=False, concatenate_terms=True)
    monkeypatch.setitem(sys.modules, "foothold_s2.sensors.start_obs", SimpleNamespace(
        zero_pose_command=zero_pose_command, apply_ex41_pose_observation=apply))
    env_cfg = SimpleNamespace(observations=SimpleNamespace(),
                              commands=SimpleNamespace(base_velocity=SimpleNamespace(bprime_turn_rad=None)))
    path = tmp_path / "model_1.pt"
    torch.save(saved, path)
    _, receipt = load_checkpoint_for_eval(env_cfg, path)
    assert receipt["checkpoint_bprime"] is True
    assert receipt["actor_input_width"] == 101 and receipt["critic_input_width"] == 669
    assert env_cfg.commands.base_velocity.bprime_turn_rad == 0.25


def test_eval_entry_rejects_bprime_width_or_term_mismatch(tmp_path: Path, monkeypatch):
    from foothold_s2.eval.ex41_eval_loader import load_checkpoint_for_eval
    checkpoint = {"ex41_pose_commands": True, "ex42_bprime": True,
                  "model_state_dict": {"actor.0.weight": torch.zeros(512, 98),
                                       "critic.0.weight": torch.zeros(512, 666)}}
    path = tmp_path / "wrong.pt"
    torch.save(checkpoint, path)
    cfg = SimpleNamespace(observations=SimpleNamespace(),
                          commands=SimpleNamespace(base_velocity=SimpleNamespace(bprime_turn_rad=None)))
    with pytest.raises(ValueError, match="input widths differ"):
        load_checkpoint_for_eval(cfg, path)


def test_mapmask_onnx_export_adds_bearing_after_the_existing_nine_inputs(tmp_path: Path):
    onnx = pytest.importorskip("onnx")
    from foothold_s2.deploy import export_start_onnx as base
    from foothold_s2.deploy import export_start_onnx_mapmask as masked
    from foothold_s2.models.start_perception import PerceptionCfg, StartPerception

    torch.manual_seed(24)
    perception = StartPerception(PerceptionCfg(map_input="reconstruction"))
    actor = torch.nn.Linear(101, 12)
    state = {"ex41_pose_commands": True, "ex42_bprime": True, "ex42_bprime_turn_rad": 0.25,
             "perception_cfg": {"map_input": "reconstruction", "depth_delay_ticks": 1},
             "perception_state_dict": perception.state_dict(),
             "model_state_dict": {"actor.0.weight": actor.weight.detach().clone(),
                                  "actor.0.bias": actor.bias.detach().clone()},
             "vx_corr": {"on": True, "b": 0.009, "band": 0.3, "ramp": 0.05}}
    checkpoint = tmp_path / "model_1.pt"
    torch.save(state, checkpoint)
    out = tmp_path / "export"
    spec = masked.export(checkpoint, out)
    assert [entry["name"] for entry in spec["step_inputs"]] == [
        "o", "hist", "depth2", "h_prop", "h_terr", "tick", "first", "pose", "map_mask", "flag_bearing3"]
    assert spec["actor_only"]["input"].startswith("actor_in [batch, 101]")
    assert spec["ex42_bprime_turn_rad"] == 0.25
    graph = onnx.load(out / "start_step.onnx")
    onnx.checker.check_model(graph)
    assert [input_.name for input_ in graph.graph.input] == [entry["name"] for entry in spec["step_inputs"]]
    perc, loaded_actor, _ = base.load(checkpoint)
    net = masked.MaskedStepNet(perc, loaded_actor, (True, 0.009, 0.3)).eval()
    inputs = base.example_inputs() + (torch.zeros(2, 1), torch.zeros(2, 3))
    with torch.inference_mode():
        action = net(*inputs)[0]
    assert action.shape == (2, 12) and torch.isfinite(action).all()
