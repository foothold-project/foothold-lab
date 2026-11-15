"""v28q: the mean-action envs also get the nominal physics (runtime DR and push off on their rows) and a share of them the one point command
forward 0.1. OFF by default; the masks exist on the env only while the constant is on (never on the evaluation env). CPU only, Kit stubs."""

from __future__ import annotations

import ast
import importlib.util
import sys
import textwrap
import types
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum import ex40_dr_runtime as dr
from foothold_s2.curriculum.continuous import command_bad
from foothold_s2.runners import ex41_critic_mirror as mirror
from foothold_s2.tests.test_ex42_mean_action_cpu import N, _alg, _runner

PKG = Path(__file__).parents[1]
MASK = mirror.small_noise_mask(N, 0.25)


def test_constants_default_off_and_the_fixed_mask_is_half_of_the_mean_envs():
    assert mirror.MEAN_ACTION_ENV_DR_OFF is False
    assert mirror.MEAN_ACTION_ENV_FIXED_CMD_SHARE == 0.5 and mirror.MEAN_ACTION_ENV_FIXED_CMD_VX == 0.1
    mean = mirror.small_noise_mask(1024, 0.12)
    fixed = mirror.mean_env_fixed_cmd_mask(1024, 0.12, 0.5)
    assert bool((fixed & ~mean).sum() == 0) and int(fixed.sum()) == int(mean.sum()) // 2        # inside the mean envs, half of them
    rank = torch.nonzero(fixed[mean.nonzero().flatten()]).flatten()
    assert bool((rank.diff() == 2).all())                                                          # spread evenly: every second mean env
    assert mirror.mean_env_fixed_cmd_mask(1024, 0.12, 0.0) is None and mirror.mean_env_fixed_cmd_mask(1024, 0.0, 0.5) is None


def test_runner_puts_the_masks_on_the_env_only_while_the_constant_is_on(monkeypatch):
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner._apply_small_noise()
    assert runner.env._ex42_nominal_dr_rows is None and runner.env._ex42_fixed_cmd_rows is None       # default: nothing on the env
    monkeypatch.setattr(mirror, "MEAN_ACTION_ENV_DR_OFF", True)
    runner._apply_small_noise()
    assert torch.equal(runner.env._ex42_nominal_dr_rows, runner._mean_action)
    assert torch.equal(runner.env._ex42_fixed_cmd_rows, mirror.mean_env_fixed_cmd_mask(N, 0.12, 0.5))
    assert runner.env._ex42_fixed_cmd_vx == 0.1
    monkeypatch.setattr(mirror, "MEAN_ACTION_ENV_FIXED_CMD_SHARE", 0.0)                          # the command part has its own off value
    runner._apply_small_noise()
    assert runner.env._ex42_nominal_dr_rows is not None and runner.env._ex42_fixed_cmd_rows is None
    monkeypatch.setattr(mirror, "MEAN_ACTION_PERCEPTION_SHARE", 0.0)                             # no mean envs: nothing nominal
    runner._apply_small_noise()
    assert runner.env._ex42_nominal_dr_rows is None


def test_nominal_split_is_all_random_without_the_mask_and_a_partition_with_it():
    rows = torch.arange(N)
    rnd, nom = dr._nominal_split(SimpleNamespace(), rows)
    assert torch.equal(rnd, rows) and nom.numel() == 0
    rnd, nom = dr._nominal_split(SimpleNamespace(_ex42_nominal_dr_rows=MASK), rows[::2])
    assert torch.equal(torch.sort(torch.cat([rnd, nom]))[0], rows[::2]) and bool(MASK[nom].all()) and not bool(MASK[rnd].any())


# ---------------------------------------------------------------- motor strength

class _Motor:
    pass


def _motor_env(mask, num=N, joints=3):
    actuator = _Motor()
    actuator.effort_limit = torch.full((num, joints), 20.0)
    actuator._saturation_effort = torch.full((num, joints), 30.0)
    actuator.velocity_limit = 10.0
    actuator._vel_at_effort_lim = None
    asset = SimpleNamespace(device="cpu", actuators={"legs": actuator}, num_joints=joints)
    env = SimpleNamespace(scene={"robot": asset}, device="cpu")
    env.scene = types.SimpleNamespace(num_envs=num, __getitem__=None)
    env.scene = _Scene({"robot": asset}, num)
    env._ex40_dr_scale = 1.0
    if mask is not None:
        env._ex42_nominal_dr_rows = mask
    return env, actuator


class _Scene:
    def __init__(self, entities, num_envs):
        self.entities, self.num_envs = entities, num_envs

    def __getitem__(self, name):
        return self.entities[name]


def _stub_isaac(monkeypatch, **attrs):
    for name, mod in attrs.items():
        monkeypatch.setitem(sys.modules, name, mod)


def _motor_stub(monkeypatch):
    actuators = types.ModuleType("isaaclab.actuators")
    actuators.DCMotor = _Motor
    _stub_isaac(monkeypatch, **{"isaaclab": types.ModuleType("isaaclab"), "isaaclab.actuators": actuators})


def _run_motor(monkeypatch, mask, seed=5):
    _motor_stub(monkeypatch)
    env, actuator = _motor_env(mask)
    torch.manual_seed(seed)
    asset_cfg = SimpleNamespace(name="robot", joint_ids=slice(None))
    dr.reset_motor_strength(env, torch.arange(N), asset_cfg, (0.7, 1.3))
    return env, actuator


def test_motor_strength_of_the_nominal_rows_is_exactly_the_baseline_and_the_others_are_the_same_draws(monkeypatch):
    _, plain = _run_motor(monkeypatch, None)
    _, nominal = _run_motor(monkeypatch, MASK)
    assert not torch.equal(plain.effort_limit[MASK], torch.full_like(plain.effort_limit[MASK], 20.0))          # random without the mask
    assert torch.equal(nominal.effort_limit[MASK], torch.full_like(nominal.effort_limit[MASK], 20.0))
    assert torch.equal(nominal._saturation_effort[MASK], torch.full_like(nominal._saturation_effort[MASK], 30.0))
    assert torch.equal(nominal.effort_limit[~MASK], plain.effort_limit[~MASK])                                   # the other envs keep their draws


def test_motor_strength_without_the_mask_is_the_old_call(monkeypatch):
    env, _ = _run_motor(monkeypatch, None)
    assert not hasattr(env, "_ex42_nominal_dr_rows")


# ---------------------------------------------------------------- actuator gains

def _gain_env(mask, calls):
    actuator = SimpleNamespace(joint_indices=slice(None), stiffness=torch.full((N, 2), 10.0), damping=torch.full((N, 2), 1.0))
    asset = SimpleNamespace(device="cpu", actuators={"legs": actuator}, num_joints=2,
                            data=SimpleNamespace(default_joint_stiffness=torch.full((N, 2), 10.0), default_joint_damping=torch.full((N, 2), 1.0)))
    env = SimpleNamespace(device="cpu", _ex40_dr_scale=1.0)
    env.scene = _Scene({"robot": asset}, N)
    if mask is not None:
        env._ex42_nominal_dr_rows = mask

    def helper(env_, env_ids, asset_cfg, stiffness_distribution_params, damping_distribution_params, operation, distribution):
        ids = torch.arange(N) if env_ids is None else env_ids
        calls.append((ids.clone(), tuple(stiffness_distribution_params), tuple(damping_distribution_params)))
        actuator.stiffness[ids] = 10.0 * stiffness_distribution_params[1]
        actuator.damping[ids] = 1.0 * damping_distribution_params[1]

    env._ex40_dr_gain_event = helper
    return env, actuator


def _gain_stub(monkeypatch):
    events = types.ModuleType("isaaclab.envs.mdp.events")
    mdp = types.ModuleType("isaaclab.envs.mdp")
    mdp.events = events
    managers = types.ModuleType("isaaclab.managers")
    managers.EventTermCfg = object
    _stub_isaac(monkeypatch, **{"isaaclab": types.ModuleType("isaaclab"), "isaaclab.envs": types.ModuleType("isaaclab.envs"),
                                 "isaaclab.envs.mdp": mdp, "isaaclab.managers": managers})


def test_gains_nominal_rows_are_set_back_to_scale_one_and_the_random_rows_get_the_range(monkeypatch):
    _gain_stub(monkeypatch)
    calls = []
    env, actuator = _gain_env(MASK, calls)
    cfg = SimpleNamespace(name="robot", joint_ids=slice(None))
    dr.reset_actuator_gains(env, torch.arange(N), cfg, {"stiffness_scale": (0.8, 1.2), "damping_scale": (0.8, 1.2)})
    assert len(calls) == 2
    assert torch.equal(calls[0][0], torch.nonzero(~MASK).flatten()) and calls[0][1] == pytest.approx((0.8, 1.2)) and calls[0][2] == pytest.approx((0.8, 1.2))
    assert torch.equal(calls[1][0], torch.nonzero(MASK).flatten()) and calls[1][1] == (1.0, 1.0) and calls[1][2] == (1.0, 1.0)
    assert torch.equal(actuator.stiffness[MASK], torch.full_like(actuator.stiffness[MASK], 10.0))
    assert bool((actuator.stiffness[~MASK] > 10.0).all())


def test_gains_without_the_mask_make_the_one_old_call_with_the_env_ids_as_given(monkeypatch):
    _gain_stub(monkeypatch)
    calls = []
    env, _ = _gain_env(None, calls)
    ids = torch.arange(N)
    dr.reset_actuator_gains(env, ids, SimpleNamespace(name="robot", joint_ids=slice(None)), {"stiffness_scale": (0.8, 1.2), "damping_scale": (0.8, 1.2)})
    assert len(calls) == 1 and torch.equal(calls[0][0], ids)


# ---------------------------------------------------------------- COM

def test_com_nominal_rows_keep_the_baseline_and_only_the_random_rows_are_randomised(monkeypatch):
    coms = torch.zeros(N, 1, 7)
    seen = []

    def randomize(env, rows, com_range, asset_cfg):
        seen.append(rows.clone())
        coms[rows, 0, 0] += 0.05

    class View:
        def get_coms(self):
            return coms.clone()

        def set_coms(self, value, rows):
            coms[rows] = value[rows]

    events = types.ModuleType("isaaclab.envs.mdp.events")
    events.randomize_rigid_body_com = randomize
    mdp = types.ModuleType("isaaclab.envs.mdp")
    mdp.events = events
    _stub_isaac(monkeypatch, **{"isaaclab": types.ModuleType("isaaclab"), "isaaclab.envs": types.ModuleType("isaaclab.envs"), "isaaclab.envs.mdp": mdp})
    asset = SimpleNamespace(root_physx_view=View())
    env = SimpleNamespace(device="cpu", _ex40_dr_scale=1.0, _ex42_nominal_dr_rows=MASK)
    env.scene = _Scene({"robot": asset}, N)
    cfg = SimpleNamespace(name="robot", body_ids=[0])
    dr.reset_base_com(env, torch.arange(N), cfg, {"x": (-0.05, 0.05), "y": (-0.05, 0.05), "z": (-0.05, 0.05)})
    assert torch.equal(seen[0], torch.nonzero(~MASK).flatten())
    assert bool((coms[MASK] == 0).all()) and bool((coms[~MASK][:, 0, 0] > 0).all())
    sample = env._ex40_dr_samples["base_com_offset_m"]
    assert sample["count"] == N * 3 and sample["target_envs"] == N                  # the receipt still covers every reset row


# ---------------------------------------------------------------- push

def test_the_push_skips_the_nominal_rows(monkeypatch):
    pushed = []

    def push(env, rows, velocity_range, asset_cfg):
        pushed.append(rows.clone())
        vel[rows, 0] += 1.0

    vel = torch.zeros(N, 6)

    class View:
        def get_root_velocities(self):
            return vel

    events = types.ModuleType("isaaclab.envs.mdp.events")
    events.push_by_setting_velocity = push
    mdp = types.ModuleType("isaaclab.envs.mdp")
    mdp.events = events
    _stub_isaac(monkeypatch, **{"isaaclab": types.ModuleType("isaaclab"), "isaaclab.envs": types.ModuleType("isaaclab.envs"), "isaaclab.envs.mdp": mdp})
    asset = SimpleNamespace(device="cpu", root_physx_view=View())
    for mask, expect in ((MASK, torch.nonzero(~MASK).flatten()), (None, torch.arange(N))):
        pushed.clear()
        vel.zero_()
        env = SimpleNamespace(device="cpu", _ex40_dr_scale=1.0, _ex40_dr_samples={})
        env.scene = _Scene({"robot": asset}, N)
        if mask is not None:
            env._ex42_nominal_dr_rows = mask
        dr.interval_push(env, None, SimpleNamespace(name="robot"), {"x": (-1.0, 1.0)})
        assert torch.equal(pushed[0], expect)
        assert float(vel[:, 0][MASK].abs().sum()) == (0.0 if mask is not None else float(MASK.sum()))
        assert env._ex40_dr_samples["push_velocity_delta"]["target_envs"] == len(expect)


# ---------------------------------------------------------------- action delay (the real class, Kit stubbed)

def _delayed_module(monkeypatch):
    @dataclass
    class JointPositionActionCfg:
        pass

    class JointPositionAction:
        def __init__(self, cfg, env):
            self.cfg, self._env = cfg, env
            self.num_envs, self.device = env.num_envs, "cpu"
            self.processed_actions = torch.zeros(env.num_envs, 2)
            self._offset = 0.0
            self._asset = SimpleNamespace(data=SimpleNamespace(joint_pos=torch.zeros(env.num_envs, 2)))
            self._joint_ids = slice(None)

        def reset(self, env_ids=None):
            pass

    actions = types.ModuleType("isaaclab.envs.mdp.actions")
    actions.JointPositionAction, actions.JointPositionActionCfg = JointPositionAction, JointPositionActionCfg
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda cls: dataclass(cls)
    mdp = types.ModuleType("isaaclab.envs.mdp")
    mdp.actions = actions
    _stub_isaac(monkeypatch, **{"isaaclab": types.ModuleType("isaaclab"), "isaaclab.envs": types.ModuleType("isaaclab.envs"),
                                 "isaaclab.envs.mdp": mdp, "isaaclab.envs.mdp.actions": actions, "isaaclab.utils": utils})
    spec = importlib.util.spec_from_file_location("delayed_action_v28q_probe", PKG / "tasks" / "delayed_action.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _delay(monkeypatch, mask, seed=9):
    module = _delayed_module(monkeypatch)
    env = SimpleNamespace(num_envs=N, physics_dt=0.005, _ex40_dr_scale=1.0)
    if mask is not None:
        env._ex42_nominal_dr_rows = mask
    cfg = SimpleNamespace(max_delay_s=0.015, dr_scale_from_env=True)
    term = module.DelayedJointPositionAction(cfg, env)
    torch.manual_seed(seed)
    term.reset(None)
    return term


def test_the_action_delay_of_the_nominal_rows_is_zero_and_the_other_draws_are_unchanged(monkeypatch):
    plain, nominal = _delay(monkeypatch, None), _delay(monkeypatch, MASK)
    assert int(plain.delay[MASK].max()) > 0                                          # the plain run does delay these rows
    assert bool((nominal.delay[MASK] == 0).all()) and torch.equal(nominal.delay[~MASK], plain.delay[~MASK])
    assert int(nominal._ex40_sample_counts.sum()) == N                               # the histogram of the receipt counts every reset row
    some = _delayed_module(monkeypatch)                                              # a partial reset only touches those rows
    env = SimpleNamespace(num_envs=N, physics_dt=0.005, _ex40_dr_scale=1.0, _ex42_nominal_dr_rows=MASK)
    term = some.DelayedJointPositionAction(SimpleNamespace(max_delay_s=0.015, dr_scale_from_env=True), env)
    ids = torch.tensor([0, 1, 2, 3])
    term.reset(ids)
    assert bool((term.delay[ids][MASK[ids]] == 0).all())


# ---------------------------------------------------------------- the command term

def _pin_method():
    src = (PKG / "commands" / "mixed_command.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_pin_forward_command")
    ns = {"torch": torch}
    exec(textwrap.dedent(ast.get_source_segment(src, fn)), ns)
    return ns["_pin_forward_command"]


def _stage(forward=(0.1, 1.5), shares=("forward", "stand", "walk_left")):
    return SimpleNamespace(ranges={"forward_vx": forward, "walk_vx": (0.3, 1.2), "walk_wz_abs": (0.1, 1.0), "spin_wz_abs": (0.15, 1.5)},
                           shares={name: 1.0 for name in shares}, heading_cfg={"forward_wz_limit": 0.5, "target_wz_limit": 1.0, "gain": 1.0})


def _term(fixed, stage=None, vx=0.1):
    stage = stage or _stage()
    env = SimpleNamespace(_ex42_fixed_cmd_rows=fixed, _ex42_fixed_cmd_vx=vx)
    return SimpleNamespace(_env=env, device="cpu", slot_names=mc.EX39_SLOTS, stage_runtime=SimpleNamespace(plan=SimpleNamespace(stages=[stage])))


def _out(n=8):
    cmd = torch.tensor([[0.5, 0.0, 0.0], [0.0, 0.0, 0.8], [0.4, 0.0, 0.3], [0.0, 0.0, 0.0]] * (n // 4))
    slot = torch.tensor([0, 3, 0, 5] * (n // 4))
    heading = torch.tensor([False, False, True, False] * (n // 4))
    stand = torch.tensor([False, False, False, True] * (n // 4))
    spin = torch.tensor([False, True, False, False] * (n // 4))
    return {"cmd": cmd, "stand": stand, "spin": spin, "heading": heading, "psi_star": torch.zeros(n), "slot": slot}


def test_the_pinned_envs_get_forward_0_1_in_the_forward_slot_and_the_others_are_untouched():
    fn, out = _pin_method(), _out()
    fixed = torch.zeros(8, dtype=torch.bool)
    fixed[[1, 2, 3, 6]] = True                                                       # a spin, a heading forward, a stand, a spin
    term = _term(fixed)
    new = fn(term, torch.arange(8), 0, out)
    keep = ~fixed
    assert torch.equal(new["cmd"][fixed], torch.tensor([[0.1, 0.0, 0.0]] * 4))
    assert bool((new["slot"][fixed] == 0).all()) and not bool(new["stand"][fixed].any() | new["spin"][fixed].any() | new["heading"][fixed].any())
    for key in ("cmd", "slot", "stand", "spin", "heading"):
        assert torch.equal(new[key][keep], out[key][keep])
    assert torch.equal(out["cmd"], _out()["cmd"])                                    # the input dict is not changed in place
    bad = command_bad(new["cmd"], new["slot"], new["heading"], torch.zeros(8, dtype=torch.long), term.stage_runtime.plan)
    assert int(bad[fixed].sum()) == 0                                                # the W55 check sees a valid forward command


def test_a_group_is_pinned_by_its_own_env_ids():
    fn, out = _pin_method(), _out(4)
    fixed = torch.zeros(16, dtype=torch.bool)
    fixed[[9, 10]] = True
    new = fn(_term(fixed), torch.tensor([8, 9, 10, 11]), 0, out)
    assert torch.equal(new["cmd"][1:3], torch.tensor([[0.1, 0.0, 0.0]] * 2)) and torch.equal(new["cmd"][[0, 3]], out["cmd"][[0, 3]])


def test_nothing_changes_without_the_mask_or_when_the_stage_has_no_such_forward_command():
    fn, out = _pin_method(), _out()
    fixed = torch.ones(8, dtype=torch.bool)
    assert fn(_term(None), torch.arange(8), 0, out) is out
    assert fn(_term(fixed, _stage(shares=("walk_left", "stand"))), torch.arange(8), 0, out) is out        # no forward slot in the stage
    assert fn(_term(fixed, _stage(forward=(0.3, 1.5))), torch.arange(8), 0, out) is out                    # 0.1 is outside the forward range
    assert fn(_term(torch.zeros(8, dtype=torch.bool)), torch.arange(8), 0, out) is out
    no_slot = {k: v for k, v in out.items() if k != "slot"}
    assert fn(_term(fixed), torch.arange(8), 0, no_slot) is no_slot


def test_the_resample_calls_the_pin_before_anything_is_stored():
    src = (PKG / "commands" / "mixed_command.py").read_text(encoding="utf-8")
    body = src[src.index("    def _resample_command"):]
    assert body.index("out = self._pin_forward_command(group, index, out)") < body.index('self.vel_command_b[group] = out["cmd"]')
    assert body.index("out = self._pin_forward_command(group, index, out)") < body.index('self.new_task.on_resample(group, out["cmd"]')
    assert body.index("out = self._pin_forward_command(group, index, out)") < body.index('self.slot_counts += torch.bincount(out["slot"]')


def test_the_evaluation_path_never_sets_the_masks():
    for path in ("eval", "scripts"):
        for source in (PKG / path).rglob("*.py"):
            if "tests" in source.parts:
                continue
            assert "_ex42_nominal_dr_rows" not in source.read_text(encoding="utf-8", errors="ignore"), source
            assert "_ex42_fixed_cmd_rows" not in source.read_text(encoding="utf-8", errors="ignore"), source
