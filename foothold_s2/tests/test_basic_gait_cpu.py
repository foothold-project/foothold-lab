"""기본 보행 준비판의 10만 표본, 명령 계약, 기존 선택값 불변 CPU 시험."""

from types import SimpleNamespace

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.runners.contracts import basic_gait_contract_bad, contract_bad_fn
from foothold_s2.sol23f_contract import TASKS, command_settings, validate_launch


def _args(**changes):
    data = dict(variant="SB", task=TASKS["SB"], agent="rsl_rl_cfg_entry_point",
                distributed=False, map_input="reconstruction", max_wall_s=3600,
                end_by="2099-01-01T00:00:00+00:00", num_envs=3072, seed=42,
                max_iterations=1501, force_gt=False, smoke_updates=None,
                resume_from=None, p_map_off=0.1, command_mode="basic_gait",
                clock_scatter="on", basic_new_share=None)
    data.update(changes)
    return SimpleNamespace(**data)


@pytest.mark.parametrize("share", [0.30, 0.15])
def test_100k_real_sampler_ratios_ranges_and_contract(share):
    params = mc.CommandParams(basic_mode=True, basic_new_share=share)
    out = mc.resample_free_modes(mc.make_generator(42), 100_000, params, 0)
    expected = mc.basic_shares(share)
    assert len(mc.BASIC_SLOTS) == len(expected) == 9
    assert sum(expected) == pytest.approx(1.0)
    for i, want in enumerate(expected):
        actual = float((out["slot"] == i).float().mean())
        assert actual == pytest.approx(want, abs=0.005), (mc.BASIC_SLOTS[i], actual, want)
    c = out["cmd"]
    assert c.shape == (100_000, 3) and not basic_gait_contract_bad(c).any()
    assert (c[out["slot"] == 6, 0] < 0).all()
    assert (c[out["slot"] == 7, 1] > 0).all()
    assert (c[out["slot"] == 8, 1] < 0).all()
    assert out["stand"].sum() == (out["slot"] == 5).sum()
    assert out["spin"].sum() == ((out["slot"] == 3) | (out["slot"] == 4)).sum()
    assert int(mc.new_task_mask(c, params).sum()) > 0


def test_contract_rejects_known_invalid_commands_and_preserves_old_modes():
    good = torch.tensor([[0, 0, 0], [-0.2, 0, 0], [0, 0.5, 0],
                         [0.3, 0, 0.2], [0, 0, -1.2]])
    bad = torch.tensor([[-0.1, 0, 0], [0, 0.6, 0], [-0.3, 0, 0.2],
                        [0.5, 0.2, 0], [0, 0, 1.3], [float("nan"), 0, 0]])
    assert not basic_gait_contract_bad(good).any()
    assert basic_gait_contract_bad(bad).all()
    assert contract_bad_fn("basic_gait_v1") is basic_gait_contract_bad
    assert command_settings(_args(command_mode="start", clock_scatter="off")) == {
        "command_mode": "start", "command_contract": "start", "clock_scatter": False}
    assert command_settings(_args(command_mode="s2a")) == {
        "command_mode": "s2a", "command_contract": "walkturn_v1", "clock_scatter": True}
    a = mc.resample_free_modes(mc.make_generator(4), 100, mc.CommandParams(start_mode=True), 0)["cmd"]
    b = mc.resample_start(mc.make_generator(4), 100, mc.CommandParams(start_mode=True))["cmd"]
    assert torch.equal(a, b)


def test_new_mode_validation_and_parameterized_share():
    validate_launch(_args(), verify_parent=False)
    validate_launch(_args(basic_new_share=0.15), verify_parent=False)
    validate_launch(_args(smoke_updates=10), verify_parent=False)
    settings = command_settings(_args(basic_new_share=0.15))
    assert settings["command_contract"] == "basic_gait_v1"
    assert settings["basic_shares"]["forward"] == pytest.approx(0.55)
    assert settings["basic_shares"]["reverse"] == pytest.approx(0.05)
    for bad in (-0.01, float("nan"), 0.71):
        with pytest.raises(ValueError, match="basic_new_share"):
            validate_launch(_args(basic_new_share=bad), verify_parent=False)
    with pytest.raises(ValueError, match="requires"):
        validate_launch(_args(command_mode="start", basic_new_share=0.15), verify_parent=False)
    with pytest.raises(ValueError, match="SB variant only"):
        validate_launch(_args(variant="B", task=TASKS["B"]), verify_parent=False)
