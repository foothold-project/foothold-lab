"""The per-step command check with flag environments (E1F and after).

The rollout check judged every env by its stage slot. A flag env follows the flag command instead
(direction to the flag x speed, plus a turn), so the first E1F update was declared invalid
(kit short launch 11/13 06:41: 302 envs, e.g. [-0.4186, -0.2026, -1.0]). Flag envs are now judged by
the flag command domain of the term's own parameters; free envs keep the slot check.

The plan row, the share contract, the slot validator and the flag command generator are the real ones.
Only the Isaac command term is a stand-in holding the same fields.
"""
from __future__ import annotations

import types
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import ex42_shares
from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum import continuous
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.runners.contracts import flag_contract_bad, flag_env_command_bad
from foothold_s2.scripts import ex42_training_entry as te

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
# tasks/s2_env_cfg.BACKOFF_PARAMS (that module imports Isaac, so the values are repeated here)
BACKOFF_PARAMS = {"backoff_prob": 0.15, "backoff_vmin": 0.1, "backoff_vmax": 0.3, "backoff_s": 2.0}
KIT_EXAMPLES = [[-0.4186458885669708, -0.20255866646766663, -1.0],
                [-0.28126952052116394, 0.3703806698322296, 1.0]]


@pytest.fixture(scope="module")
def stages():
    """The two command stages of an E1F run, built the way CommandShares.attach builds them."""
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    stage = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan,
                                              stage_id="E1F").stages[0]
    contract = ex42_shares.read_contract(plan, "E1F")
    assert contract is not None and contract["shares"]["flag"] > 0
    return [stage, ex42_shares.CommandShares(contract, stage).free_stage]


def flag_commands(params, n=512, steps=400, seed=3):
    """Commands the real flag state machine gives while robots wander among four flags."""
    gen = mc.make_generator(seed)
    torch.manual_seed(seed)
    state = mc.FlagState.new(torch.rand(n, 4, 2) * 6.0 - 3.0)
    pos, yaw = torch.rand(n, 2) * 6.0 - 3.0, torch.rand(n) * 6.28 - 3.14
    out = []
    for k in range(steps):
        if k % 50 == 0:
            mc.flag_resample(state, torch.arange(n), gen, params)
        cmd = mc.flag_step(state, pos, yaw, 0.02, params)
        out.append(cmd.clone())
        world = torch.stack([torch.cos(yaw) * cmd[:, 0] - torch.sin(yaw) * cmd[:, 1],
                             torch.sin(yaw) * cmd[:, 0] + torch.cos(yaw) * cmd[:, 1]], dim=1)
        pos, yaw = pos + world * 0.2, yaw + cmd[:, 2] * 0.2          # coarse motion: flags get reached and passed
    return torch.cat(out), state


def limits(params, vmax=None):
    return dict(vmax=params.flag_vmax if vmax is None else vmax, spin_threshold=params.flag_spin_threshold,
                spin_wz=params.flag_spin_wz, wz_clip=params.flag_wz_clip,
                backoff=(params.backoff_vmin, params.backoff_vmax) if params.backoff_prob > 0 else None)


def term(flags, params, *, dynamic=True, flag_vmax=None):
    curve = mc.RangeCurriculum()
    if flag_vmax is not None:
        curve.flag_vmax = flag_vmax
    return types.SimpleNamespace(is_flag_env=torch.tensor(flags), params=params, range_curriculum=curve,
                                 cfg=types.SimpleNamespace(dynamic_flags=dynamic))


@pytest.mark.parametrize("extra", [{}, BACKOFF_PARAMS])
def test_every_command_of_the_flag_state_machine_is_inside_the_flag_domain(extra):
    params = mc.CommandParams(**extra)
    commands, state = flag_commands(params)
    speed = torch.linalg.norm(commands[:, :2], dim=1)
    # the generator really produced each kind: walking with a turn, turning in place, all zero after the last flag
    assert bool(((speed > 0.3) & (commands[:, 2].abs() > 0.5)).any())
    assert bool(((speed == 0) & (commands[:, 2].abs() > 0.3)).any())
    assert bool((commands == 0).all(dim=1).any()) and bool((state.passed > 0).any())
    if extra:
        assert bool(((speed > 0.05) & (speed < 0.3)).any())           # backing off happened
    assert not bool(flag_contract_bad(commands, **limits(params)).any())


def test_the_two_commands_the_kit_run_stopped_on_are_flag_commands_and_slot_violations(stages):
    params = mc.CommandParams()
    commands = torch.tensor(KIT_EXAMPLES, dtype=torch.float32)
    assert not bool(flag_contract_bad(commands, **limits(params)).any())
    for slot in (-1, 0, 6):                                            # never drawn, forward, reverse: no slot takes them
        bad = continuous.command_bad(commands, torch.full((2,), slot), torch.zeros(2, dtype=torch.bool),
                                     torch.ones(2, dtype=torch.long), types.SimpleNamespace(stages=stages))
        assert bool(bad.all())


@pytest.mark.parametrize("command, backoff, bad", [
    ([0.0, 0.0, 0.0], False, False),
    ([0.0, 0.0, 1.2], False, False), ([0.0, 0.0, -1.21], False, True),              # turning in place
    ([0.6, 0.8, 1.0], False, False), ([0.6, 0.8, 1.01], False, True),               # walking: |wz| <= 1.0
    ([0.61, 0.8, 0.0], False, True), ([-1.0, 0.0, 0.0], False, False),              # walking: speed <= vmax
    ([0.18, 0.24, 0.0], False, False), ([0.17, 0.24, 0.0], False, True),            # walking: speed >= 0.3
    ([0.12, 0.16, 0.0], False, True), ([0.12, 0.16, 0.0], True, False),             # 0.2 m/s is a back-off only
    ([0.12, 0.16, 0.3], True, True), ([0.03, 0.04, 0.0], True, True),               # back-off: wz 0, speed >= 0.1
    ([float("nan"), 0.0, 0.0], False, True), ([0.5, 0.0, float("inf")], False, True),
])
def test_flag_domain_edges(command, backoff, bad):
    params = mc.CommandParams(**(BACKOFF_PARAMS if backoff else {}))
    assert bool(flag_contract_bad(torch.tensor([command]), **limits(params))[0]) is bad


def test_the_speed_limit_follows_the_flag_speed_curriculum():
    params = mc.CommandParams()
    fast = torch.tensor([[1.2, 0.0, 0.5]])
    assert bool(flag_env_command_bad(term([True], params), fast, torch.zeros(1, dtype=torch.bool))[0])
    assert not bool(flag_env_command_bad(term([True], params, flag_vmax=1.25), fast, torch.zeros(1, dtype=torch.bool))[0])


def test_backing_off_is_accepted_only_when_the_term_has_it_switched_on():
    slow = torch.tensor([[0.12, 0.16, 0.0]])                         # 0.2 m/s without a turn: a back-off and nothing else
    none = torch.zeros(1, dtype=torch.bool)
    assert bool(flag_env_command_bad(term([True], mc.CommandParams()), slow, none)[0])
    assert not bool(flag_env_command_bad(term([True], mc.CommandParams(**BACKOFF_PARAMS)), slow, none)[0])


def step_check(stages, commands, slots, flags, params, *, dynamic=True):
    """The rollout check of start_runner: the slot validator, then the flag rows by the flag domain."""
    n = len(flags)
    bad = continuous.command_bad(commands, slots, torch.zeros(n, dtype=torch.bool), torch.ones(n, dtype=torch.long),
                                 types.SimpleNamespace(stages=stages))
    return bad, flag_env_command_bad(term(flags, params, dynamic=dynamic), commands, bad)


def test_an_e1f_batch_of_free_and_flag_envs_passes_the_step_check(stages):
    params = mc.CommandParams(**BACKOFF_PARAMS)
    n = 2000
    free = mc.resample_stage(mc.make_generator(5), n, stages[1], torch.zeros(n))
    flagged, _ = flag_commands(params, n=n, steps=1)
    flags = [i % 10 == 0 for i in range(n)]                            # the registered tenth
    mask = torch.tensor(flags)
    commands = torch.where(mask[:, None], flagged, free["cmd"])
    slots = torch.where(mask, torch.full((n,), -1), free["slot"])
    slot_only, checked = step_check(stages, commands, slots, flags, params)
    assert int(slot_only.sum()) > 0 and not bool(slot_only[~mask].any())      # the defect: only flag envs were refused
    assert not bool(checked.any())
    # a flag env that kept the slot of an earlier free episode is judged the same way
    stale = torch.where(mask, torch.zeros(n, dtype=torch.long), free["slot"])
    assert not bool(step_check(stages, commands, stale, flags, params)[1].any())


def test_only_flag_rows_of_a_registered_flag_stage_change(stages):
    params = mc.CommandParams()
    commands = torch.tensor([KIT_EXAMPLES[0], KIT_EXAMPLES[0], [2.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=torch.float32)
    slots = torch.tensor([-1, 0, -1, -1])
    flags = [True, False, True, False]
    slot_only, checked = step_check(stages, commands, slots, flags, params)
    assert slot_only.tolist() == [True, True, True, False]
    assert checked.tolist() == [False, True, True, False]      # a free env with a flag-like command and a flag env outside the domain stay refused
    # without the registered flag allocation nothing changes (EX-41 and E0 · E1 have no flag envs to excuse)
    assert step_check(stages, commands, slots, flags, params, dynamic=False)[1].tolist() == slot_only.tolist()
    no_flags = step_check(stages, commands, slots, [False] * 4, params)
    assert no_flags[1].tolist() == no_flags[0].tolist()
    assert flag_env_command_bad(types.SimpleNamespace(), commands, slot_only) is slot_only


def test_the_runner_applies_the_flag_domain_right_after_the_slot_validator():
    source = (Path(__file__).resolve().parents[1] / "runners" / "start_runner.py").read_text(encoding="utf-8")
    slot_check = source.index("bad_now = command_bad(consumed, term.slot_current")
    flag_check = source.index("bad_now = flag_env_command_bad(term, consumed, bad_now)")
    assert 0 < flag_check - slot_check < 400 and source.count("flag_env_command_bad(") == 1


# ---- the real command term through the start-up resets and a stretch of steps (kit short launch 11/13 08:26) ----
# Only Isaac's CommandTerm base class is a double. The term, its sampler, the flag state machine, the E1F plan row,
# the share contract and the stage runtime are the real ones.

def e1f_term(monkeypatch, params, n=3072):
    import importlib.util
    import sys

    class Base:
        def __init__(self, cfg, env):
            self.cfg, self._env = cfg, env
            self.num_envs, self.device = env.num_envs, env.device
            self.metrics = {}
            self.time_left = torch.zeros(env.num_envs)

        def reset(self, env_ids=None):
            self._resample_command(torch.arange(self.num_envs) if env_ids is None else env_ids)
            return {}

    managers = types.ModuleType("isaaclab.managers")
    managers.CommandTerm, managers.CommandTermCfg = Base, object
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda c: c
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)
    spec = importlib.util.spec_from_file_location("_ex42_e1f_mixed", PLAN.parents[1] / "commands" / "mixed_command.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    plan = EX42Plan.load(PLAN)
    for row in plan.document["stages"]:
        if row["id"] == "E1F":                                  # the materialized plan carries the parent pin
            row["parent"] = {"manifest_local_update": 1750, "cumulative_update": 15000, "checkpoint_key": "model_1750.pt"}
    specs = te.e_stage_table(plan.document["stages"])
    monkeypatch.setattr(te, "E_STAGE_SPECS", specs)
    monkeypatch.setattr(te, "E_STAGES", {k: (v["updates"], v["parent_local"], v["parent_cumulative"])
                                         for k, v in specs.items()})
    contract = ex42_shares.read_contract(plan, "E1F")

    class Scene:
        def __getitem__(self, key):
            return self.robot

    scene = Scene()
    scene.terrain = types.SimpleNamespace(terrain_types=torch.zeros(n, dtype=torch.long), env_origins=torch.zeros(n, 3))
    scene.robot = types.SimpleNamespace(data=types.SimpleNamespace(
        root_pos_w=torch.zeros(n, 3), heading_w=torch.zeros(n), root_lin_vel_b=torch.zeros(n, 3),
        root_ang_vel_b=torch.zeros(n, 3)))
    raw = types.SimpleNamespace(
        num_envs=n, device="cpu", scene=scene, common_step_counter=0, step_dt=0.02,
        _ex42_column_table=[{"family": contract["families"][0], "kind": list(contract["continuous_kinds"])[0]}])
    cfg = types.SimpleNamespace(asset_name="robot", params={"curriculum_mode": True, **params}, seed=42, flag_stride=0,
                                dynamic_flags=True, force_flag_provider=None, flag_provider=None, flag_count=4,
                                fixed_cmd=None, clock_scatter=False, steps_per_iter=24,
                                resampling_time_range=(4.0, 4.0))
    command = module.MixedVelocityCommand(cfg, raw)
    source = te.load_ex42_stage_zero_source(plan)
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "b" * 64}, ex42_plan=plan,
                                             stage_id="E1F")
    runtime = te.EX42StageZeroRuntime(stage_zero_plan=view, plan_sha256="a" * 64, approval_sha256="b" * 64,
                                      parent_sha256="c" * 64, maximum_updates=750, push_vmax_mps=2., stage_id="E1F")
    runtime.attach_environment(raw, command)
    return command, runtime, scene.robot.data


def consumed_bad(command, runtime):
    """What start_runner computes before each env.step."""
    consumed = command.vel_command_b.clone()
    bad = continuous.command_bad(consumed, command.slot_current, command.heading, runtime.env_stage, runtime.plan)
    return flag_env_command_bad(command, consumed, bad)


@pytest.mark.parametrize("params", [{}, BACKOFF_PARAMS])
def test_a_flag_env_never_follows_the_command_of_its_earlier_free_episode(monkeypatch, params):
    command, runtime, robot = e1f_term(monkeypatch, params)
    command.reset()                                              # the wrapper's first reset
    first = command.is_flag_env.clone()
    assert not bool(consumed_bad(command, runtime).any())
    command.reset()                                              # the second start-up reset: flags are drawn again
    switched = command.is_flag_env & ~first
    assert int(switched.sum()) > 200 and int((command.is_flag_env & first).sum()) > 0
    # no compute follows a reset outside env.step: this is the command of the first action
    assert not bool(command.vel_command_b[command.is_flag_env].any())
    assert bool(command.vel_command_b[~command.is_flag_env].any())
    assert not bool(consumed_bad(command, runtime).any())

    # a stretch of steps as Isaac drives the term: step, some resets, timed resamples, the per-step command
    gen = torch.Generator().manual_seed(1)
    kinds = {"walk": 0, "spin": 0, "zero": 0, "back": 0}
    for _ in range(600):
        cmd, yaw = command.vel_command_b, robot.heading_w
        world = torch.stack([torch.cos(yaw) * cmd[:, 0] - torch.sin(yaw) * cmd[:, 1],
                             torch.sin(yaw) * cmd[:, 0] + torch.cos(yaw) * cmd[:, 1]], dim=1)
        robot.root_pos_w[:, :2] += world * 0.1                   # coarse motion so flags are reached and passed
        robot.heading_w += cmd[:, 2] * 0.1
        done = (torch.rand(command.num_envs, generator=gen) < 0.01).nonzero().flatten()
        if len(done):
            robot.root_pos_w[done] = 0.0
            robot.heading_w[done] = 0.0
            command.reset(done)
        command._update_metrics()
        command.time_left -= 0.02
        due = (command.time_left <= 0).nonzero().flatten()
        if len(due):
            command.time_left[due] = 0.5                         # shortened period: many resamples in the stretch
            command._resample_command(due)
        command._update_command()
        assert not bool(consumed_bad(command, runtime).any())
        flag = command.vel_command_b[command.is_flag_env]
        speed = torch.linalg.norm(flag[:, :2], dim=1)
        kinds["walk"] += int(((speed >= 0.3) & (flag[:, 2] != 0)).sum())
        kinds["spin"] += int(((speed == 0) & (flag[:, 2] != 0)).sum())
        kinds["zero"] += int((flag == 0).all(dim=1).sum())
        kinds["back"] += int(((speed > 0) & (speed < 0.3)).sum())
    assert kinds["walk"] > 0 and kinds["spin"] > 0 and kinds["zero"] > 0
    assert (kinds["back"] > 0) is bool(params)                   # backing off only when the term has it on
