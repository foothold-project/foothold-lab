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
