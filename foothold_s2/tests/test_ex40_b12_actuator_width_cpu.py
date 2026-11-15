"""CPU replay of the EX-40 B12 two-actuator reset readback."""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest
import torch

from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback, reset_actuator_gains
from foothold_s2.robots.go2_params import CALF_JOINTS, HIP_THIGH_JOINTS


def _asset(monkeypatch):
    cfg_source = (Path(__file__).parents[1] / "robots/go2_cfg.py").read_text(encoding="utf-8")
    assert '"hip_thigh": DCMotorCfg(joint_names_expr=gp.HIP_THIGH_JOINTS' in cfg_source
    assert '"calf": DCMotorCfg(joint_names_expr=gp.CALF_JOINTS' in cfg_source
    names = [f"{leg}_{part}_joint" for leg in ("FL", "FR", "RL", "RR")
             for part in ("hip", "thigh", "calf")]
    groups = {
        "hip_thigh": [i for i, name in enumerate(names)
                      if any(re.fullmatch(pattern, name) for pattern in HIP_THIGH_JOINTS)],
        "calf": [i for i, name in enumerate(names)
                 if any(re.fullmatch(pattern, name) for pattern in CALF_JOINTS)],
    }
    assert [len(groups[key]) for key in ("hip_thigh", "calf")] == [8, 4]
    assert set(groups["hip_thigh"]).isdisjoint(groups["calf"])

    class Actuator:
        def __init__(self, indices):
            self.joint_indices = torch.tensor(indices, dtype=torch.long)
            self.stiffness = torch.full((3, len(indices)), 25.0)
            self.damping = torch.full((3, len(indices)), 0.5)

    class Asset:
        device = "cpu"
        num_joints = 12

        def __init__(self):
            self.actuators = {key: Actuator(indices) for key, indices in groups.items()}
            self.data = types.SimpleNamespace(
                default_joint_stiffness=torch.full((3, 12), 25.0),
                default_joint_damping=torch.full((3, 12), 0.5))

    class Scene(dict):
        num_envs = 3

    class Helper:
        def __call__(self, env, env_ids, asset_cfg, stiffness_distribution_params,
                     damping_distribution_params, operation, distribution):
            assert operation == "scale" and distribution == "uniform"
            for name, actuator in env.scene["robot"].actuators.items():
                ids = actuator.joint_indices
                stiff_factor = (stiffness_distribution_params[0] if name == "hip_thigh"
                                else stiffness_distribution_params[1])
                damp_factor = (damping_distribution_params[1] if name == "hip_thigh"
                               else damping_distribution_params[0])
                actuator.stiffness[env_ids] = (
                    env.scene["robot"].data.default_joint_stiffness[env_ids][:, ids] * stiff_factor)
                actuator.damping[env_ids] = (
                    env.scene["robot"].data.default_joint_damping[env_ids][:, ids] * damp_factor)

    events = types.ModuleType("isaaclab.envs.mdp.events")
    events.randomize_actuator_gains = lambda cfg, env: Helper()
    mdp = types.ModuleType("isaaclab.envs.mdp")
    mdp.events = events
    envs = types.ModuleType("isaaclab.envs")
    envs.mdp = mdp
    managers = types.ModuleType("isaaclab.managers")
    managers.EventTermCfg = lambda **kwargs: types.SimpleNamespace(**kwargs)
    for name, module in (("isaaclab", types.ModuleType("isaaclab")),
                         ("isaaclab.envs", envs), ("isaaclab.envs.mdp", mdp),
                         ("isaaclab.envs.mdp.events", events), ("isaaclab.managers", managers)):
        monkeypatch.setitem(sys.modules, name, module)
    asset = Asset()
    env = types.SimpleNamespace(scene=Scene(robot=asset), _ex40_dr_scale=1.0,
                                action_manager=types.SimpleNamespace(
                                    get_term=lambda name: types.SimpleNamespace(delay=None)),
                                physics_dt=.005)
    cfg = types.SimpleNamespace(name="robot", joint_ids=slice(None))
    return env, cfg, asset


def test_b12_two_actuators_partial_reset_and_actual_gain_readback(monkeypatch):
    env, cfg, asset = _asset(monkeypatch)
    readback = RuntimeReadback(env, {}, config_sha256="fixture")
    env._ex40_dr_scale = 1.0
    rows = torch.tensor([0, 2], dtype=torch.long)
    target = {"stiffness_scale": [.9, 1.1], "damping_scale": [.9, 1.1]}
    reset_actuator_gains(env, rows, cfg, target)
    receipt = env._ex40_dr_samples["actuator_gains"]
    assert receipt["count"] == 2 * (8 + 4) * 2 == 48
    assert receipt["target_envs"] == 2
    assert receipt["min"] == pytest.approx(.9)
    assert receipt["max"] == pytest.approx(1.1)
    assert receipt["sum"] / receipt["count"] == pytest.approx(1.0)
    summary = readback.summary()["actual_samples"]["actuator_gains"]
    assert summary == {"count": 48, "min": pytest.approx(.9),
                       "max": pytest.approx(1.1), "mean": pytest.approx(1.0),
                       "target_envs": 2}
    assert torch.equal(asset.actuators["hip_thigh"].stiffness[rows],
                       torch.full((2, 8), 22.5))
    assert torch.equal(asset.actuators["calf"].stiffness[rows],
                       torch.full((2, 4), 27.5))
    assert torch.equal(asset.actuators["hip_thigh"].damping[rows],
                       torch.full((2, 8), .55))
    assert torch.equal(asset.actuators["calf"].damping[rows],
                       torch.full((2, 4), .45))
    assert torch.equal(asset.actuators["hip_thigh"].stiffness[1], torch.full((8,), 25.0))
    assert torch.equal(asset.actuators["calf"].damping[1], torch.full((4,), .5))

    env._ex40_dr_samples = {}
    env._ex40_dr_scale = 0.0
    reset_actuator_gains(env, rows, cfg, target)
    neutral = env._ex40_dr_samples["actuator_gains"]
    assert neutral == {"count": 48, "min": 1.0, "max": 1.0,
                       "sum": 48.0, "target_envs": 2}
    assert torch.equal(asset.actuators["calf"].stiffness[rows], torch.full((2, 4), 25.0))

    env._ex40_dr_samples = {}
    env._ex40_dr_scale = .5
    reset_actuator_gains(env, rows, cfg, target)
    halfway = env._ex40_dr_samples["actuator_gains"]
    assert halfway["count"] == 48 and halfway["target_envs"] == 2
    assert halfway["min"] == pytest.approx(.95)
    assert halfway["max"] == pytest.approx(1.05)
    assert halfway["sum"] / halfway["count"] == pytest.approx(1.0)


def test_b12_nonfinite_gain_rejected(monkeypatch):
    env, cfg, asset = _asset(monkeypatch)
    rows = torch.tensor([0], dtype=torch.long)
    env._ex40_dr_gain_event = lambda *_args, **_kwargs: None
    asset.actuators["calf"].stiffness[0, 0] = float("nan")
    with pytest.raises(ValueError, match="nonfinite realized sample"):
        reset_actuator_gains(env, rows, cfg, {
            "stiffness_scale": [1.0, 1.0], "damping_scale": [1.0, 1.0]})
