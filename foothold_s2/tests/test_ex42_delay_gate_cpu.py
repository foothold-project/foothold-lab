"""EX-42 delay gate through the actual pre-gym cfg installer, with minimal Kit shims."""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import torch

from foothold_s2.scripts.ex41_startup import prepare_ex41_env_cfg


@dataclass
class _JointCfg:
    asset_name: str = "robot"
    joint_names: list[str] = field(default_factory=lambda: [".*"])
    scale: float = 0.25
    use_default_offset: bool = True
    offset: float = 0.0
    clip: object = None
    preserve_order: bool = False
    debug_vis: bool = False


class _KitJointBase:
    def __init__(self, cfg, env):
        self.cfg, self._env, self.device = cfg, env, "cpu"
        self.num_envs = env.num_envs
        self._offset = torch.zeros(env.num_envs, 12)
        self.processed_actions = self._offset.clone()
        self._joint_ids = list(range(12))
        self._asset = NS(data=NS(joint_pos=torch.zeros(env.num_envs, 12)),
                         set_joint_position_target=lambda target, joint_ids: setattr(self, "applied", target.clone()))

    def process_actions(self, actions):
        self.processed_actions = actions.clone()

    def reset(self, env_ids=None):
        pass


@pytest.fixture
def e2_view():
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.scripts import ex42_training_entry as entry

    plan_path = Path(__file__).resolve().parents[1] / "curriculum/ex42-prep.yaml"
    plan = EX42Plan.load(plan_path)
    source, stage = entry.load_ex42_stage_zero_source(plan)
    return entry.make_ex42_stage_zero_plan_view(
        source, stage, {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")


@pytest.fixture
def prepared(monkeypatch):
    # Only Isaac's unavailable base/config classes and unrelated rewards are
    # replaced. The production prepare_ex41_env_cfg, install_runtime_events,
    # DelayedJointPositionActionCfg and DelayedJointPositionAction execute.
    modules = {
        "isaaclab": types.ModuleType("isaaclab"),
        "isaaclab.envs": types.ModuleType("isaaclab.envs"),
        "isaaclab.envs.mdp": types.ModuleType("isaaclab.envs.mdp"),
        "isaaclab.envs.mdp.actions": types.ModuleType("isaaclab.envs.mdp.actions"),
        "isaaclab.utils": types.ModuleType("isaaclab.utils"),
        "isaaclab.managers": types.ModuleType("isaaclab.managers"),
    }
    for name, module in modules.items():
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
    modules["isaaclab.envs.mdp.actions"].JointPositionAction = _KitJointBase
    modules["isaaclab.envs.mdp.actions"].JointPositionActionCfg = _JointCfg
    modules["isaaclab.utils"].configclass = lambda cls: cls
    modules["isaaclab.managers"].SceneEntityCfg = lambda name, **kwargs: NS(name=name, **kwargs)
    modules["isaaclab.managers"].EventTermCfg = lambda **kwargs: NS(**kwargs)
    action_path = Path(__file__).resolve().parents[1] / "tasks/delayed_action.py"
    spec = importlib.util.spec_from_file_location("foothold_s2.tasks.delayed_action", action_path)
    action_module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, action_module)
    spec.loader.exec_module(action_module)

    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.basic_gait_bundle", NS(
        validate_settings=lambda weights, **kwargs: weights,
        apply_settings=lambda *args: None,
        apply_ex39_settings=lambda *args: {},
        apply_ex40_stand_settings=lambda *args: None))
    monkeypatch.setitem(sys.modules, "foothold_s2.curriculum.ex41", NS(
        prepare_terrain_cfg=lambda *args, **kwargs: {}))
    monkeypatch.setitem(sys.modules, "foothold_s2.eval.ex41_eval_loader", NS(
        prepare_ex41_env_cfg=lambda *args: {}))
    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.w86_runtime", NS(
        prepare_env_cfg=lambda *args: {}))
    monkeypatch.delenv("EX42_DELAY_MAX_S", raising=False)
    monkeypatch.delenv("EX42_DELAY_HOLD_P", raising=False)
    monkeypatch.delenv("EX42_DELAY_HOLD_STEPS", raising=False)
    monkeypatch.setenv("RANK", "0")

    def run(plan_override=None, approval=None):
        cfg = NS(events=NS(), observations=NS(), actions=NS(joint_pos=_JointCfg()))
        rewards = dict(track_ang_vel=1.0, track_lin_vel=2.0,
                       joint_acc=-1e-7, hip_pos_penalty=-.05)
        plan = NS(domain_randomization={"full_ranges": {
            "base_com": {"x": [0, 0]}, "actuator_gains": [1, 1],
            "motor_strength": [1, 1], "delay_s": [0, .015],
            "push_velocity": {"x": [0, 0]}}, "push_interval_s": [10, 15]},
            stages=[NS(rewards=rewards)], stand_cfg={}, initial_dr_scale=.5)
        receipt = prepare_ex41_env_cfg(cfg, plan_override or plan, stage_zero_approval=approval)
        return cfg, receipt

    return run, action_module


def test_off_path_matches_empty_gate_byte_for_byte(prepared, monkeypatch, capsys):
    run, _ = prepared
    cfg, receipt = run()
    first = json.dumps(receipt, sort_keys=True).encode()
    assert cfg.actions.joint_pos.max_delay_s == .015
    assert "EX42_DELAY_DR" not in capsys.readouterr().out
    monkeypatch.setenv("EX42_DELAY_MAX_S", "")
    other, second = run()
    assert other.actions.joint_pos.max_delay_s == .015
    assert json.dumps(second, sort_keys=True).encode() == first
    assert "EX42_DELAY_DR" not in capsys.readouterr().out


def test_on_path_reaches_real_delayed_action_cfg_and_four_substeps(prepared, monkeypatch, capsys):
    run, action_module = prepared
    monkeypatch.setenv("EX42_DELAY_MAX_S", "0.020")
    cfg, receipt = run()
    action_cfg = cfg.actions.joint_pos
    assert isinstance(action_cfg, action_module.DelayedJointPositionActionCfg)
    assert action_cfg.max_delay_s == receipt["events"]["delay_max_s"] == .020
    action = action_module.DelayedJointPositionAction(action_cfg, NS(num_envs=1, physics_dt=.005))
    assert action.max_delay_substeps == 4
    assert "EX42_DELAY_DR where=start max_s=0.02 plan_max_s=0.015 substeps=0..4" in capsys.readouterr().out
    monkeypatch.setenv("RANK", "1")
    run()
    assert "EX42_DELAY_DR" not in capsys.readouterr().out


@pytest.mark.parametrize("raw", ["0", "-0.1", "0.025", "nan", "inf", "bad"])
def test_invalid_gate_fails_before_install(prepared, monkeypatch, raw):
    run, _ = prepared
    monkeypatch.setenv("EX42_DELAY_MAX_S", raw)
    with pytest.raises(ValueError, match="EX42_DELAY_MAX_S"):
        run()


def test_hold_gate_reaches_real_action_config_and_both_ranks(prepared, monkeypatch, capsys):
    run, action_module = prepared
    monkeypatch.setenv("EX42_DELAY_HOLD_P", "0.05")
    monkeypatch.setenv("EX42_DELAY_HOLD_STEPS", "2-4")
    cfg, receipt = run()
    assert isinstance(cfg.actions.joint_pos, action_module.DelayedJointPositionActionCfg)
    assert (cfg.actions.joint_pos.ex42_hold_p, cfg.actions.joint_pos.ex42_hold_steps) == (.05, "2-4")
    assert receipt["events"]["hold"] == {"p": .05, "steps": "2-4"}
    assert "EX42_DELAY_HOLD where=start rank=0 p=0.05 steps=2-4" in capsys.readouterr().out
    monkeypatch.setenv("RANK", "1")
    run()
    assert "EX42_DELAY_HOLD where=start rank=1 p=0.05 steps=2-4" in capsys.readouterr().out


def test_e2_plan_view_reaches_the_real_pre_gym_action_installer(e2_view, prepared, monkeypatch):
    assert e2_view.command_contract["stage_id"] == "E2"
    monkeypatch.setenv("EX42_DELAY_HOLD_P", "0.03")
    monkeypatch.setenv("EX42_DELAY_HOLD_STEPS", "3")
    proof = {"state": "stage_e2_approval_only", "later_stages_authorized": False,
             "approvals_sha256": "a" * 64, "boundary_evaluation_interval_updates": 250,
             "scope": {"stage_id": "E2", "start_update": 0, "maximum_updates": 500,
                       "parent_sha256": "b" * 64, "later_stages_authorized": False}}
    cfg, receipt = prepared[0](e2_view, proof)
    assert cfg.actions.joint_pos.ex42_hold_p == .03
    assert cfg.actions.joint_pos.ex42_hold_steps == 3
    assert receipt["events"]["hold"] == {"p": .03, "steps": 3}


@pytest.mark.parametrize("p,steps", [("", "2"), ("0.01", ""), ("0", "3"),
                                      ("0.051", "3"), ("nan", "3"), ("bad", "3"),
                                      ("0.01", "1"), ("0.01", "5"), ("0.01", "2.5")])
def test_invalid_hold_gate_rejected(prepared, monkeypatch, p, steps):
    run, _ = prepared
    monkeypatch.setenv("EX42_DELAY_HOLD_P", p)
    monkeypatch.setenv("EX42_DELAY_HOLD_STEPS", steps)
    with pytest.raises(ValueError, match="EX42_DELAY_HOLD"):
        run()


def test_three_control_steps_hold_last_applied_target_and_reset_clears(prepared):
    _, action_module = prepared
    cfg = action_module.DelayedJointPositionActionCfg()
    cfg.max_delay_s = .015
    cfg.ex42_hold_p, cfg.ex42_hold_steps = 1.0, 3  # force trigger in action test; env gate caps p at .05
    action = action_module.DelayedJointPositionAction(cfg, NS(num_envs=2, physics_dt=.005))
    action.delay[:] = 0
    action._last_applied[:] = 7.0
    for target_value in (1.0, 2.0, 3.0):
        action.process_actions(torch.full((2, 12), target_value))
        for _ in range(4):
            action.apply_actions()
            assert torch.equal(action.applied, torch.full((2, 12), 7.0))
    assert action._ex42_hold_env_steps == 6
    assert action._ex42_total_env_steps == 6
    action.process_actions(torch.full((2, 12), 4.0))
    action.apply_actions()
    assert torch.equal(action.applied, torch.full((2, 12), 4.0))
    action.process_actions(torch.full((2, 12), 5.0))
    action._asset.data.joint_pos[0] = 9.0
    action.reset([0])
    assert not action._hold_active[0] and action._hold_left[0] == 0
    assert action._hold_active[1]
    assert torch.equal(action._last_applied[0], torch.full((12,), 9.0))


def test_random_hold_duration_is_within_two_to_four_control_steps(prepared):
    _, action_module = prepared
    cfg = action_module.DelayedJointPositionActionCfg()
    cfg.max_delay_s = .015
    cfg.ex42_hold_p, cfg.ex42_hold_steps = 1.0, "2-4"
    action = action_module.DelayedJointPositionAction(cfg, NS(num_envs=128, physics_dt=.005))
    torch.manual_seed(17)
    action.process_actions(torch.ones((128, 12)))
    assert action._hold_active.all()
    assert set(action._hold_left.tolist()).issubset({1, 2, 3})
    assert {1, 2, 3}.issubset(set(action._hold_left.tolist()))


def test_off_action_never_draws_hold_random_or_changes_targets(prepared, monkeypatch):
    _, action_module = prepared
    cfg = action_module.DelayedJointPositionActionCfg()
    cfg.max_delay_s = .015
    action = action_module.DelayedJointPositionAction(cfg, NS(num_envs=2, physics_dt=.005))
    monkeypatch.setattr(torch, "rand", lambda *args, **kwargs: pytest.fail("hold RNG used while off"))
    action.delay[:] = 2
    action.process_actions(torch.full((2, 12), 3.0))
    action.apply_actions()
    assert torch.equal(action.applied, torch.zeros((2, 12)))
    action.apply_actions()
    assert torch.equal(action.applied, torch.zeros((2, 12)))
    action.apply_actions()
    assert torch.equal(action.applied, torch.full((2, 12), 3.0))


def test_fiftieth_update_receipt_has_actual_hold_fraction(prepared, capsys):
    _, action_module = prepared
    from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback
    cfg = action_module.DelayedJointPositionActionCfg()
    cfg.max_delay_s = .015
    cfg.ex42_hold_p, cfg.ex42_hold_steps = 1.0, 2
    env = NS(num_envs=2, physics_dt=.005, scene={"robot": NS(actuators={})})
    action = action_module.DelayedJointPositionAction(cfg, env)
    env.action_manager = NS(get_term=lambda name: action)
    receipt = RuntimeReadback(env, {}, config_sha256="fixture")
    receipt.update = 50
    action._ex42_hold_env_steps = 3
    action._ex42_total_env_steps = 4
    row = receipt.summary()
    assert row["delay_hold"] == {"held_env_steps": 3, "total_env_steps": 4,
                                  "held_env_fraction": .75}
    assert "EX42_DELAY_HOLD where=update update=50 rank=0 held_env_fraction=0.750000" in capsys.readouterr().out
