"""Known-input CPU contracts for the EX-39 heading pair; no Kit or GPU."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.basic_gait_ex39 import prepare
from foothold_s2.commands import mixed_core as mc
from foothold_s2.eval.map_mode_cells import (
    assert_heading_off_for_fixed_eval, commands, disable_heading_for_fixed_eval, SEQUENCES,
)
from foothold_s2.prestart_check import actual_parser, inspect_args
from foothold_s2.rewards.basic_gait_bundle import (
    four_foot_contact_at_stop, scheduled_lin_vel_z_weight, thigh_calf_pos_penalty_l1,
)
from foothold_s2.sol23f_contract import EX39_PARENT_SHA256, validate_launch


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


def test_shares_and_eval_support():
    shares = mc.ex39_shares()
    assert sum(shares.values()) == pytest.approx(1.0)
    assert len(shares) == 13
    assert shares["forward"] == .30 and shares["reverse"] == .12
    assert sum(v for k, v in shares.items() if k.startswith("diag_")) == pytest.approx(.06)
    for cmd in list(commands("extended").values()) + [x for phases in SEQUENCES.values() for x in phases]:
        vx, vy, wz = cmd
        assert (vx == 0 or .3 <= vx <= 1.5 or -1.0 <= vx <= -.2)
        assert (vy == 0 or .2 <= abs(vy) <= .6)
        assert (wz == 0 or .5 <= abs(wz) <= 1.5)


def test_100k_realized_slots_and_heading_only_difference():
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


def test_parent_hash_and_arm_rejected():
    with pytest.raises(ValueError, match="SHA"):
        prepare("A", "cuda:0", str(PARENT), "0" * 64, END_BY, ROOT)
    with pytest.raises(ValueError, match="accepts"):
        prepare("C", "cuda:0", str(PARENT), EX39_PARENT_SHA256, END_BY, ROOT)
