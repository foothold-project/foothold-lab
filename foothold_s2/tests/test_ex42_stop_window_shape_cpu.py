"""S2b E2 transition shaping, using the real stage-zero command runtime on CPU."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace as NS

import pytest
import torch

from foothold_s2.commands import ex42_shares
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.rewards import ex42_stop_window_shape as shape
from foothold_s2.rewards.basic_gait_bundle import ex40_stand_gap, ex40_stand_load, four_foot_contact_at_stop
from foothold_s2.tests.test_ex42_small_noise_lowspeed_cpu import _alg, _runner
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import consumed_bad
from foothold_s2.tests.test_ex42_stop_bundle_cpu import N, ROBOT, SENSOR, _env, _draw


@pytest.fixture(autouse=True)
def gate(monkeypatch):
    shape._COUNTS.clear()
    monkeypatch.setenv(shape.ENV_SWITCH, "1")
    monkeypatch.setenv("EX42_STOP_NOISE_WINDOW_S", "1.0")
    monkeypatch.delenv(shape.PARAMS_ENV, raising=False)


def _transition(monkeypatch):
    command, raw, data = _env(monkeypatch, stage_id="E2")
    command.reset(torch.arange(N))
    assert not command.stop_from_move.any()
    _draw(command, seed=7)
    active = shape.window_mask(raw, "base_velocity", 1.0)
    assert int(active.sum()) > 20
    assert int((command.stop_from_move & (raw.scene.terrain.terrain_types == 1)).sum()) > 0
    return command, raw, data, active


def test_foot_x_reward_uses_default_pose_and_only_the_transition_window(monkeypatch):
    command, raw, data, active = _transition(monkeypatch)
    ref = shape.default_foot_x(data.joint_names if hasattr(data, "joint_names") else raw.scene.robot.joint_names,
                               data.default_joint_pos)
    assert ref[0].tolist() == pytest.approx([0.1763, 0.1763, -0.2723, -0.2723], abs=2e-4)
    data.body_pos_w[:, :, 0] = ref
    reward = shape.ex42_stop_window_x(raw, "base_velocity", ROBOT, 1.0, 0.08)
    assert bool((reward[active] == 1).all()) and bool((reward[~active] == 0).all())
    data.body_pos_w[:, :, 0] += 0.08
    shifted = shape.ex42_stop_window_x(raw, "base_velocity", ROBOT, 1.0, 0.08)
    assert torch.allclose(shifted[active], torch.full_like(shifted[active], 0.36787944), atol=2e-6)
    command.stop_elapsed_s[:] = 1.0
    assert bool((shape.ex42_stop_window_x(raw, "base_velocity", ROBOT, 1.0, 0.08) == 0).all())
    row = shape.summary()
    assert row["window_env_steps"] == 2 * int(active.sum())
    assert row["x_reward_mean"] == pytest.approx((1 + 0.36787944) / 2, abs=1e-6)


def test_three_real_stand_only_terms_are_zero_only_inside_window(monkeypatch):
    command, raw, data, active = _transition(monkeypatch)
    command.stop_elapsed_s[:] = 0.6
    config = {"gap_weight": -0.2, "load_weight": -0.1, "load_fraction": 0.05, "ramp_s": 0.5}
    data.body_quat_w = torch.zeros(N, 4, 4)
    data.body_quat_w[..., 0] = 1.0
    def identity_quat_apply(quat, vec):
        assert bool((quat[:, 0] == 1).all()) and bool((quat[:, 1:] == 0).all())
        return vec
    monkeypatch.setitem(sys.modules, "isaaclab.utils.math", NS(quat_apply=identity_quat_apply))
    for i in range(4):
        hits = torch.zeros(N, 1, 3)
        hits[:, 0, 2] = -0.022 - 0.055
        raw.scene.sensors[f"ex40_support_{i}"] = NS(data=NS(ray_hits_w=hits))
    raw._ex40_total_mass_kg = torch.full((N,), 12.0)
    raw.scene.sensors["contact_forces"].data.net_forces_w[:, 0, 2] = 1.5  # contact > 1 N, load < 5 % body weight
    cfg = NS(rewards=NS(
        ex39_four_foot_stop=NS(func=four_foot_contact_at_stop, weight=0.1),
        ex40_stand_gap=NS(func=ex40_stand_gap, weight=-0.2),
        ex40_stand_load=NS(func=ex40_stand_load, weight=-0.1)))
    ctor = lambda **kw: NS(**kw)  # RewardTermCfg constructor stand-in; functions and command term are real
    entity = lambda name, **kw: NS(name=name, body_ids=[0, 1, 2, 3], **kw)
    assert shape.register(cfg, ctor, entity, stage_id="E2")
    for name in shape.PENALTIES:
        term = getattr(cfg.rewards, name)
        assert getattr(term.func, "ex42_stop_window_shape", False)
        kwargs = {"command_name": "base_velocity", "sensor_cfg": SENSOR}
        if name != "ex39_four_foot_stop":
            kwargs.update(asset_cfg=ROBOT, config=config)
        original = term.func.__wrapped__(raw, **kwargs)
        wrapped = term.func(raw, **kwargs)
        assert bool((wrapped[active] == 0).all())
        assert torch.equal(wrapped[~active], original[~active])
        assert bool((original[active].abs() > 0).any())
    assert cfg.rewards.ex42_stop_window_x.weight == 0.1


def test_actual_e2_sampler_share_and_transition_rate(monkeypatch):
    plan = EX42Plan.load("foothold_s2/curriculum/ex42-prep.yaml")
    contract = ex42_shares.read_contract(plan, "E2")
    assert contract["shares"]["stand"] == pytest.approx(0.15)
    assert sum(contract["shares"].values()) == pytest.approx(1.0)
    command, raw, _, _ = _transition(monkeypatch)
    continuous = raw.scene.terrain.terrain_types == 0
    count = 0
    for _ in range(5):
        before = command.stand.clone()
        command._resample_command(torch.arange(N))
        assert not bool(consumed_bad(command, command.stage_runtime).any())
        count += int((~before & command.stand & continuous).sum())
    per_20s = count / int(continuous.sum())
    assert 0.45 < per_20s < 0.80  # expected near 0.6 for five 4 s resamples


def test_rank_local_transition_receipt_uses_real_command_clock(monkeypatch, tmp_path):
    command, raw, data, active = _transition(monkeypatch)
    ref = shape.default_foot_x(raw.scene.robot.joint_names, data.default_joint_pos)
    data.body_pos_w[:, :, 0] = ref
    command._update_command()
    shape.ex42_stop_window_x(raw, "base_velocity", ROBOT, 1.0, 0.08)
    row = shape.summary()
    assert row["moving_to_stop"] == int(active.sum())
    assert row["continuous_env_steps"] == N // 2
    assert row["moving_to_stop_per_env_20s"] == pytest.approx(int(active.sum()) * 20 / ((N // 2) * raw.step_dt))
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"test checkpoint")
    alloc = command.stage_runtime.command_allocation
    alloc.write(tmp_path, 250, checkpoint, plan_sha="a" * 64, stage_id="E2")
    receipt = json.loads((tmp_path / "command_shares_250_rank0.json").read_text())
    assert receipt["stop_window_shape"] == row


def test_shape_and_noise_use_the_same_real_e2_window(monkeypatch):
    command, raw, data, active = _transition(monkeypatch)
    data.body_pos_w[:, :, 0] = shape.default_foot_x(raw.scene.robot.joint_names, data.default_joint_pos)
    reward = shape.ex42_stop_window_x(raw, "base_velocity", ROBOT, 1.0, 0.08)
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner.env = raw
    runner._apply_small_noise()
    obs = torch.zeros(N, 12)
    obs[:, 6:8] = command.command[:, :2]
    runner._step_small_noise(obs)
    assert torch.equal(reward > 0, active)
    assert torch.equal(runner._stop_noise_window_mask(1.0), active)
    assert bool((alg.storage.noise_scale_env[active] == 1).all())


def test_off_gate_preserves_sampler_bytes_and_generator(monkeypatch):
    monkeypatch.delenv(shape.ENV_SWITCH)
    monkeypatch.delenv("EX42_STOP_NOISE_WINDOW_S")
    plan = EX42Plan.load("foothold_s2/curriculum/ex42-prep.yaml")
    original = ex42_shares.read_contract(plan, "E2")
    a, _, _ = _env(monkeypatch, stage_id="E2")
    _draw(a, seed=7)
    cmd, slots, rng = a.command.clone(), a.slot_current.clone(), a.gen.get_state().clone()
    monkeypatch.setenv(shape.ENV_SWITCH, "0")
    b, _, _ = _env(monkeypatch, stage_id="E2")
    _draw(b, seed=7)
    assert torch.equal(b.command, cmd) and torch.equal(b.slot_current, slots) and torch.equal(b.gen.get_state(), rng)
    assert ex42_shares.read_contract(plan, "E2") == original
    cfg = NS(rewards=NS())
    assert shape.register(cfg, stage_id="E2") is False and vars(cfg.rewards) == {}


@pytest.mark.parametrize("value", ["window=0", "x_width=0", "x_weight=0", "stand_share=0.95", "bad=1", "window=nan"])
def test_bad_params_fail(monkeypatch, value):
    monkeypatch.setenv(shape.PARAMS_ENV, value)
    with pytest.raises(ValueError):
        shape.params()


def test_gate_requires_noise_and_e2(monkeypatch):
    cfg = NS(rewards=NS())
    with pytest.raises(ValueError, match="scoped to E2"):
        shape.register(cfg, stage_id="E3")
    monkeypatch.delenv("EX42_STOP_NOISE_WINDOW_S")
    with pytest.raises(ValueError, match="needs EX42_STOP_NOISE_WINDOW_S"):
        shape.register(cfg, stage_id="E2")
