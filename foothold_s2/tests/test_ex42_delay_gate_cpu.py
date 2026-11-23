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
        self._offset = torch.zeros(env.num_envs, 12)
        self.processed_actions = self._offset.clone()


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
    monkeypatch.setenv("RANK", "0")

    def run():
        cfg = NS(events=NS(), observations=NS(), actions=NS(joint_pos=_JointCfg()))
        rewards = dict(track_ang_vel=1.0, track_lin_vel=2.0,
                       joint_acc=-1e-7, hip_pos_penalty=-.05)
        plan = NS(domain_randomization={"full_ranges": {
            "base_com": {"x": [0, 0]}, "actuator_gains": [1, 1],
            "motor_strength": [1, 1], "delay_s": [0, .015],
            "push_velocity": {"x": [0, 0]}}, "push_interval_s": [10, 15]},
            stages=[NS(rewards=rewards)], stand_cfg={}, initial_dr_scale=.5)
        receipt = prepare_ex41_env_cfg(cfg, plan)
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
