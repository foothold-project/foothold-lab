"""Known-input CPU contracts for the EX-39 heading pair; no Kit or GPU."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.runners.reward_split import RewardSplit, split_stats


def test_ex39_reward_split_all_slots_and_flag():
    from foothold_s2.commands.mixed_core import EX39_SLOTS

    slot = torch.tensor([*range(13), -1])
    flag = slot == -1
    cmd = torch.tensor([
        [0.5, 0, 0], [0.5, 0, 0.3], [0.5, 0, -0.3], [0, 0, 1.5],
        [0, 0, -1.5], [0, 0, 0], [-1.0, 0, 0], [0, 0.6, 0],
        [0, -0.6, 0], [0.5, 0.4, 0], [0.5, -0.4, 0],
        [-0.5, 0.4, 0], [-0.5, -0.4, 0], [0.5, 0, 0],
    ])
    out = split_stats(torch.ones(1, 14, 1), ["track_lin_vel"], cmd[None, :, 0],
                      cmd[None, :, 2], cmd[None], torch.zeros(1, 14),
                      vy=cmd[None, :, 1], basic_mode=True, ex39_mode=True,
                      slots=slot[None], flag_env=flag[None], heading=torch.zeros(1, 14, dtype=torch.bool))
    assert tuple(out["by_command_slot"]) == EX39_SLOTS
    assert all(v["env_steps"] == 1 for v in out["by_command_slot"].values())
    assert out["flag_env_steps"] == 1
    assert out["env_steps"] == 14


def test_ex39_reward_split_attached_pre_reset_slot_and_heading():
    cmd = torch.tensor([[0.5, 0.4, 0.0], [0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])
    term = SimpleNamespace(vel_command_b=cmd.clone(), slot_current=torch.tensor([9, 3, 0]),
                           is_flag_env=torch.tensor([False, False, True]),
                           heading=torch.tensor([False, True, False]))
    data = SimpleNamespace(root_lin_vel_b=torch.tensor([[0.4, 0.3, 0], [0, 0, 0], [0.4, 0, 0]]),
                           root_ang_vel_b=torch.zeros(3, 3))
    rm = SimpleNamespace(active_terms=["track_lin_vel"], _step_reward=torch.ones(3, 1))
    rm.compute = lambda: rm._step_reward.sum(-1)
    env = SimpleNamespace(reward_manager=rm, scene={"robot": SimpleNamespace(data=data)},
                          command_manager=SimpleNamespace(get_term=lambda _: term),
                          reset_buf=torch.tensor([True, False, False]))
    record = RewardSplit(basic_mode=True, ex39_mode=True)
    record.attach(env)
    rm.compute()
    record.add()
    term.slot_current[:] = 5
    term.vel_command_b.zero_()
    out = record.summary()
    assert out["by_command_slot"]["diag_fwd_left"]["env_steps"] == 1
    assert out["by_command_slot"]["spin_left"]["following_env_steps"] == 1
    assert out["flag_env_steps"] == 1
    assert out["reset_env_steps"] == 1


@pytest.mark.parametrize("bad_slot", [-1, 13])
def test_ex39_reward_split_rejects_invalid_free_slot(bad_slot):
    cmd = torch.tensor([[[0.5, 0.4, 0.0]]])
    with pytest.raises(ValueError, match="invalid command slot"):
        split_stats(torch.ones(1, 1, 1), ["track_lin_vel"], cmd[:, :, 0], cmd[:, :, 2], cmd,
                    vy=cmd[:, :, 1], basic_mode=True, ex39_mode=True,
                    slots=torch.tensor([[bad_slot]]), flag_env=torch.tensor([[False]]),
                    heading=torch.tensor([[False]]))

from foothold_s2.basic_gait_ex39 import prepare
from foothold_s2.commands import mixed_core as mc
from foothold_s2.eval.map_mode_cells import (
    assert_heading_off_for_fixed_eval, commands, disable_heading_for_fixed_eval, SEQUENCES,
)
from foothold_s2.prestart_check import actual_parser, inspect_args
from foothold_s2.rewards.basic_gait_bundle import (
    four_foot_contact_at_stop, scheduled_lin_vel_z_weight, thigh_calf_pos_penalty_l1,
)
from foothold_s2.sol23f_contract import EX39_PARENT_SHA256, budget_iterations, validate_launch
from foothold_s2.sol23f_contract import command_settings
from foothold_s2.runners.contracts import command_sample_bad, basic_gait_contract_bad


PARENT = Path("C:/Users/AI-WS01/s2_lab/basic_gait_runs/main/EX-38-basic-e1rew_20261029_123840_163180/model_3001.pt")
ROOT = "C:/Users/AI-WS01/s2_lab/basic_gait_runs/ex39"
END_BY = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()


def _args(arm="A", updates=1500, levels=3):
    return prepare(arm, "cuda:0", str(PARENT), EX39_PARENT_SHA256,
                   END_BY, ROOT, updates, levels)[0]


def _parsed(args):
    parsed, unknown = actual_parser().parse_known_args(
        ["--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB", *args])
    assert unknown[:2] == ["--headless", "--device"]
    parsed.agent = "rsl_rl_cfg_entry_point"
    parsed.distributed = False
    parsed.map_input = None
    parsed.resume = False
    return parsed


def _slot_can_emit(cmd):
    vx, vy, wz = cmd
    return any((
        .3 <= vx <= 1.5 and vy == 0 and wz == 0,
        .3 <= vx <= .8 and vy == 0 and .2 <= wz <= .5,
        .3 <= vx <= .8 and vy == 0 and -.5 <= wz <= -.2,
        vx == vy == 0 and .5 <= wz <= 1.5,
        vx == vy == 0 and -1.5 <= wz <= -.5,
        vx == vy == wz == 0,
        -1.0 <= vx <= -.2 and vy == wz == 0,
        vx == wz == 0 and .2 <= vy <= .6,
        vx == wz == 0 and -.6 <= vy <= -.2,
        .3 <= vx <= .6 and .2 <= vy <= .5 and wz == 0,
        .3 <= vx <= .6 and -.5 <= vy <= -.2 and wz == 0,
        -.6 <= vx <= -.3 and .2 <= vy <= .5 and wz == 0,
        -.6 <= vx <= -.3 and -.5 <= vy <= -.2 and wz == 0,
    ))


def test_shares_and_eval_support_by_whole_slot():
    shares = mc.ex39_shares()
    assert sum(shares.values()) == pytest.approx(1.0)
    assert len(shares) == 13
    assert shares["forward"] == .30 and shares["reverse"] == .12
    assert sum(v for k, v in shares.items() if k.startswith("diag_")) == pytest.approx(.06)
    for cmd in list(commands("extended").values()) + [x for phases in SEQUENCES.values() for x in phases]:
        assert _slot_can_emit(cmd), cmd
    assert not _slot_can_emit((1.0, 0.5, 0.0))


def test_first_and_repeated_resamples_keep_shared_rng_and_nonheading_commands():
    n = 100_000
    yaw = torch.linspace(-3.0, 3.0, n)
    a = mc.resample_ex39(mc.make_generator(42), n, "A", yaw)
    b = mc.resample_ex39(mc.make_generator(42), n, "B", yaw)
    assert torch.equal(a["slot"], b["slot"])
    for i, (name, expected) in enumerate(mc.ex39_shares().items()):
        realized = (a["slot"] == i).float().mean().item()
        assert abs(realized - expected) < .004, (name, realized)
    assert not a["heading"].any()
    assert torch.equal(a["cmd"][~b["heading"]], b["cmd"][~b["heading"]])
    fwd = b["slot"] == 0
    spin = (b["slot"] == 3) | (b["slot"] == 4)
    assert abs((b["heading"] & fwd).float().mean().item() - .15) < .004
    assert abs((b["heading"] & spin).float().mean().item() - .06) < .004
    assert torch.equal(b["psi_star"][b["heading"] & fwd], yaw[b["heading"] & fwd])
    assert torch.all(b["cmd"][b["heading"] & spin, :2] == 0)
    assert torch.all(b["cmd"][b["heading"] & spin, 2] == 0)
    ga, gb = mc.make_generator(42), mc.make_generator(42)
    for count in (3072, 19, 1, 3072):
        yaw_next = torch.linspace(-2., 2., count)
        aa = mc.resample_ex39(ga, count, "A", yaw_next)
        bb = mc.resample_ex39(gb, count, "B", yaw_next)
        assert torch.equal(aa["slot"], bb["slot"])
        assert torch.equal(aa["cmd"][~bb["heading"]], bb["cmd"][~bb["heading"]])
        assert torch.equal(ga.get_state(), gb.get_state())
        assert torch.equal(mc.scatter_clock(ga, count), mc.scatter_clock(gb, count))
        assert torch.equal(ga.get_state(), gb.get_state())


@pytest.mark.parametrize("arm", ["A", "B"])
def test_actual_ex39_rollout_commands_use_ex39_contract(arm):
    """The runner checks commands after heading has rewritten wz, before env.step."""
    assert command_settings(_parsed(_args(arm)))["command_contract"] == "basic_gait_ex39"
    n = 100_000
    yaw = torch.linspace(-3.0, 3.0, n)
    sample = mc.resample_ex39(mc.make_generator(42), n, arm, yaw)
    command = mc.apply_heading(sample["cmd"], sample["heading"], sample["stand"],
                               sample["psi_star"], -yaw, mc.CommandParams(basic_mode=True, ex39_arm=arm))
    assert not command_sample_bad("basic_gait_ex39", command, sample["heading"]).any()
    # The first Kit failure was a legitimate EX-39 spin outside the old contract.
    assert basic_gait_contract_bad(command).any()
    assert (command[:, 2].abs() > 1.2).any()
    if arm == "B":
        assert (sample["heading"] & (sample["slot"] == 0)).any()
        assert (sample["heading"] & (sample["slot"] == 3)).any()


def test_ex39_contract_rejects_out_of_slot_values_and_spoofed_heading():
    commands = torch.tensor([[0., 0., -1.484276], [-1., 0., 0.], [0., .6, 0.],
                             [.7, .3, 0.], [.4, 0., 1.9], [.4, 0., 1.9], [0., 0., 2.01],
                             [float("nan"), 0., 0.]])
    headings = torch.tensor([False, False, False, False, False, True, True, False])
    assert command_sample_bad("basic_gait_ex39", commands, headings).tolist() == [
        False, False, False, True, True, False, True, True]
    with pytest.raises(ValueError, match="heading"):
        command_sample_bad("basic_gait_ex39", commands)


def test_rewards_known_input():
    asset = SimpleNamespace(data=SimpleNamespace(
        joint_pos=torch.tensor([[1., -2.], [0., 0.]]),
        default_joint_pos=torch.zeros(2, 2)))
    force = torch.tensor([[[0., 0., 2.]] * 4, [[0., 0., 2.]] * 3 + [[0., 0., 0.]]])
    # A minimal mapping keeps the test independent of Isaac imports.
    class Scene:
        sensors = {"contact_forces": SimpleNamespace(data=SimpleNamespace(net_forces_w=force))}
        def __getitem__(self, _):
            return asset
    env = SimpleNamespace(scene=Scene(), command_manager=SimpleNamespace(
        get_command=lambda _: torch.tensor([[0., 0., 0.], [0., 0., 0.]])))
    cfg = SimpleNamespace(name="robot", joint_ids=[0, 1])
    scfg = SimpleNamespace(name="contact_forces", body_ids=[0, 1, 2, 3])
    assert thigh_calf_pos_penalty_l1(env, cfg).tolist() == [3.0, 0.0]
    assert four_foot_contact_at_stop(env, "base_velocity", scfg).tolist() == [1.0, 0.0]
    assert scheduled_lin_vel_z_weight(3002, start_iteration=1501) == 0


def test_heading_eval_cannot_rewrite_fixed_wz():
    term = SimpleNamespace(params=mc.CommandParams(basic_mode=True, ex39_arm="B"),
                           heading=torch.tensor([True, True]), psi_star=torch.tensor([2., -2.]))
    with pytest.raises(RuntimeError, match="heading"):
        assert_heading_off_for_fixed_eval(term)
    disable_heading_for_fixed_eval(term)
    assert term.params.ex39_arm is None
    assert_heading_off_for_fixed_eval(term)
    cmd = torch.tensor([[0., 0., 1.2], [0., 0., -1.2]])
    assert torch.equal(mc.apply_heading(cmd, term.heading, torch.zeros(2, dtype=torch.bool),
                                        term.psi_star, torch.zeros(2), term.params), cmd)


def test_real_parent_parser_and_contract():
    a = _args()
    row = inspect_args(a)
    assert row["basic_ex39_arm"] == "A" and row["max_iterations"] == 4502
    parsed = _parsed(a)
    validate_launch(parsed, verify_parent=True)
    for bad in (4503, 6001, 20001):
        parsed.max_iterations = bad
        with pytest.raises(ValueError):
            validate_launch(parsed, verify_parent=False)


def test_three_thousand_level_four_and_arm_b():
    row = inspect_args(_args("B", 3000, 4))
    assert row["basic_ex39_arm"] == "B" and row["max_iterations"] == 6002
    a = _parsed(_args("B", 3000, 4))
    validate_launch(a, verify_parent=False)
    a.basic_ex39_level_count = 3
    with pytest.raises(ValueError):
        validate_launch(a, verify_parent=False)


def test_isolated_two_update_kit_smoke_uses_real_parent_and_parser():
    args, receipt = prepare("B", "cuda:0", str(PARENT), EX39_PARENT_SHA256,
                            END_BY, "C:/Users/AI-WS01/s2_lab/basic_gait_runs/ex39b_kit_smoke/try01",
                            kit_smoke_updates=2)
    parsed = _parsed(args)
    assert inspect_args(args)["max_iterations"] == 3004
    assert parsed.basic_stage == "smoke" and parsed.smoke_updates == 2
    assert budget_iterations(parsed) == 3004
    validate_launch(parsed, verify_parent=True)
    assert receipt["planned_main_max_iterations"] == 4502
    parsed.max_iterations = 3005
    with pytest.raises(ValueError):
        validate_launch(parsed, verify_parent=False)


def test_a_b_training_argv_differs_only_in_heading_selector_and_run_name():
    a = _args("A")
    b = _args("B")
    assert len(a) == len(b)
    differences = [(a[i - 1], a[i], b[i]) for i in range(1, len(a)) if a[i] != b[i]]
    assert differences == [
        ("--run_name", "EX-39A-basic-heading", "EX-39B-basic-heading"),
        ("--basic-ex39-arm", "A", "B"),
    ]


def test_parent_hash_and_arm_rejected():
    with pytest.raises(ValueError, match="SHA"):
        prepare("A", "cuda:0", str(PARENT), "0" * 64, END_BY, ROOT)
    with pytest.raises(ValueError, match="accepts"):
        prepare("C", "cuda:0", str(PARENT), EX39_PARENT_SHA256, END_BY, ROOT)
