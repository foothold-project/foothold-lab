"""v28g candidate: low-speed weight on the perception velocity loss (PERCEPTION_V_LOWSPEED_WEIGHT, default 1.0 = off) and the always-on
per-speed-band record of (estimate - truth). CPU only: the real StartRunner on the fake env (its real collect -> replay -> update_perception
path), no fake cfg. The weight is read at call time from foothold_s2.models.start_perception, so monkeypatching that module is the real switch."""
from __future__ import annotations

import hashlib
import pathlib

import pytest
import torch
import torch.nn.functional as F

from foothold_s2.models import start_perception as sp
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN_SHA = "1f4ff70d8820e2e754ed1120b821fafb22a04e40d7f84f1ff0a9a9cfedff8a92"
APPROVALS_SHA = "80a6079b5d77f6f65e7be71c120982f8e7f1379666bc890f68e2c267a7d10696"
OLD_KEYS = {"l_tr", "l_ie", "kl", "o_next", "v", "hf", "hb"}


def _runner(seed=3):
    torch.manual_seed(seed)
    cfg = train_cfg(24, {"microbatch_envs": 4})
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), cfg, log_dir=None, device="cpu")


def _batch(runner, speed=None):
    """a real replay batch of the real runner after a real collection. speed: None keeps the stored base_vel,
    otherwise every sample's truth is set to (speed, 0, 0)."""
    runner.learn(1)
    b = runner.replay.gather(torch.arange(runner.env.num_envs))
    b = dict(b)
    if speed is not None:
        b["base_vel"] = torch.zeros_like(b["base_vel"])
        b["base_vel"][..., 0] = speed
    return b


def _eps(b):
    return torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, generator=torch.Generator().manual_seed(5))


def test_defaults_are_off_and_the_records_are_on():
    assert sp.PERCEPTION_V_LOWSPEED_WEIGHT == 1.0
    assert sp.PERCEPTION_V_LOWSPEED_THRESHOLD == 0.3
    assert sp.PERCEPTION_V_BAND_EDGES == (0.0, 0.05, 0.15, 0.3, float("inf"))


def test_off_is_bit_identical_to_mse_loss_and_on_is_the_weighted_mean():
    g = torch.Generator().manual_seed(1)
    est, gt = torch.randn(64, 3, generator=g), torch.randn(64, 3, generator=g) * 0.3
    assert torch.equal(sp.velocity_loss(est, gt), F.mse_loss(est, gt))
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        err = ((est - gt) ** 2).mean(-1)
        low = gt[:, :2].norm(dim=-1) < 0.3
        assert low.any() and (~low).any()
        want = (err * torch.where(low, 3.0, 1.0)).sum() / 64
        assert torch.allclose(sp.velocity_loss(est, gt), want, atol=1e-7)
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0


def test_threshold_is_strictly_below_and_uses_the_truth_xy_norm_not_the_estimate_or_z():
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        gt = torch.tensor([[0.2999, 0.0, 5.0], [0.3, 0.0, 0.0], [0.21, 0.21, 0.0]])    # z is large in row 0 and must not count; row 2 has xy norm 0.297
        est = gt + 1.0                                                                  # same error everywhere, so the weights show in the mean
        per = ((est - gt) ** 2).mean(-1)
        want = (per * torch.tensor([3.0, 1.0, 3.0])).sum() / 3
        assert torch.allclose(sp.velocity_loss(est, gt), want, atol=1e-7)
        est2 = gt + torch.tensor([[1.0, 1.0, 1.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]) + 50.0 * torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        assert torch.allclose(sp.velocity_loss(est2, gt), (((est2 - gt) ** 2).mean(-1) * torch.tensor([3.0, 1.0, 3.0])).sum() / 3, atol=1e-5)
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0


def test_band_sums_have_the_sign_est_minus_truth_and_half_open_bands():
    gt = torch.tensor([[0.0, 0.0, 0.0], [0.05, 0.0, 0.0], [0.1, 0.0, 0.0], [0.15, 0.0, 0.0], [0.29, 0.0, 0.0], [0.3, 0.0, 0.0], [1.0, 0.0, 0.0]])
    est = gt + torch.tensor([0.04, -0.02, 0.0])
    s = sp.velocity_band_sums(est, gt)
    assert s.shape == (4, 3)
    assert s[:, 2].tolist() == [1.0, 2.0, 2.0, 2.0]                     # [0,0.05) [0.05,0.15) [0.15,0.3) [0.3,inf): 0.05 -> band 1, 0.15 -> band 2, 0.3 -> band 3
    assert torch.allclose(s[:, 0] / s[:, 2], torch.full((4,), 0.04), atol=1e-6)
    assert torch.allclose(s[:, 1] / s[:, 2], torch.full((4,), -0.02), atol=1e-6)
    rec = sp.velocity_band_records(s, 1)
    assert rec["v_n_0p00_0p05"] == 1.0 and rec["v_n_0p30_inf"] == 2.0
    assert abs(rec["v_bias_x_0p05_0p15"] - 0.04) < 1e-6 and abs(rec["v_bias_y_0p15_0p30"] + 0.02) < 1e-6
    assert sp.velocity_band_records(None, 3) == {}
    empty = sp.velocity_band_records(sp.velocity_band_sums(torch.zeros(1, 3) + 1, torch.ones(1, 3) * 2), 2)
    assert empty["v_n_0p00_0p05"] == 0.0 and "v_bias_x_0p00_0p05" not in empty and empty["v_n_0p30_inf"] == 0.5


@pytest.mark.parametrize("impl", ["loop", "a1", "a2", "a3"])
def test_real_runner_batch_the_weight_changes_the_velocity_loss_only_when_low_speed_samples_exist(impl):
    r = _runner()
    low = _batch(r, speed=0.1)
    eps = _eps(low)
    off = r.perception.sequence_loss(low, eps=eps, impl=impl)
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        on = r.perception.sequence_loss(low, eps=eps, impl=impl)
        assert float(on["v"]) == pytest.approx(3.0 * float(off["v"]), rel=1e-4)          # every sample is low speed, so the loss is exactly 3x
        assert float(on["l_ie"]) - float(off["l_ie"]) == pytest.approx(2.0 * float(off["v"]), rel=1e-3)
        for k in ("kl", "o_next", "hf", "hb", "l_tr"):
            assert float(on[k]) == pytest.approx(float(off[k]), rel=1e-6)                 # nothing else moves
        high = dict(low)
        high["base_vel"] = torch.zeros_like(low["base_vel"])
        high["base_vel"][..., 0] = 1.0
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0
        off_h = r.perception.sequence_loss(high, eps=eps, impl=impl)
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
        on_h = r.perception.sequence_loss(high, eps=eps, impl=impl)
        assert float(on_h["v"]) == float(off_h["v"])                                      # no low-speed sample: the same number, bit for bit
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0


def test_off_state_velocity_loss_is_what_the_old_code_computed_in_every_implementation():
    r = _runner()
    b = _batch(r)
    eps = _eps(b)
    ref = r.perception.sequence_loss(b, eps=eps, impl="loop")
    for impl in ("a1", "a2", "a3"):
        new = r.perception.sequence_loss(b, eps=eps, impl=impl)
        assert abs(float(new["v"]) - float(ref["v"])) <= 1e-5, impl


def test_the_four_implementations_agree_with_the_weight_on_loss_gradient_and_band_sums():
    r = _runner()
    b = _batch(r)
    eps = _eps(b)
    params = [q for q in r.perception.parameters()]
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        ref = r.perception.sequence_loss(b, eps=eps, impl="loop")
        g_ref = torch.autograd.grad(ref["loss"], params, allow_unused=True)
        assert float(ref["_v_band"][:, 2].sum()) == b["obs"].shape[0] * b["obs"].shape[1]
        for impl in ("a1", "a2", "a3"):
            new = r.perception.sequence_loss(b, eps=eps, impl=impl)
            for k in ("v", "l_ie", "loss"):
                assert abs(float(ref[k]) - float(new[k])) <= 1e-4, (impl, k)
            assert torch.allclose(ref["_v_band"], new["_v_band"], atol=1e-4), impl
            g_new = torch.autograd.grad(new["loss"], params, allow_unused=True)
            assert max(float((u - v).abs().max()) for u, v in zip(g_ref, g_new) if u is not None) <= 1e-4, impl
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0


def test_the_weight_changes_the_gradient_of_a_real_batch_but_not_the_state_dict_layout():
    r = _runner()
    b = _batch(r, speed=0.1)
    eps = _eps(b)
    params = [q for q in r.perception.parameters()]
    keys = {k: tuple(v.shape) for k, v in r.perception.state_dict().items()}
    g_off = torch.autograd.grad(r.perception.sequence_loss(b, eps=eps, impl="loop")["loss"], params, allow_unused=True)
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        g_on = torch.autograd.grad(r.perception.sequence_loss(b, eps=eps, impl="loop")["loss"], params, allow_unused=True)
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0
    assert any(not torch.equal(u, v) for u, v in zip(g_off, g_on) if u is not None)
    assert {k: tuple(v.shape) for k, v in r.perception.state_dict().items()} == keys           # checkpoints keep the same keys and shapes


def test_a_real_update_perception_adds_the_band_keys_and_keeps_every_old_key():
    r = _runner()
    r.learn(2)
    rec = r.last_perception_losses
    assert OLD_KEYS <= set(rec)
    new = set(rec) - OLD_KEYS
    assert new, "no band key was recorded"
    assert all(k.startswith("v_n_") or k.startswith("v_bias_x_") or k.startswith("v_bias_y_") for k in new), new
    assert {f"v_n_{t}" for t in ("0p00_0p05", "0p05_0p15", "0p15_0p30", "0p30_inf")} <= new
    n_total = sum(rec[k] for k in new if k.startswith("v_n_"))
    assert n_total == pytest.approx(24 * 8 / r.pcfg["num_mini_batches"], rel=1e-6)            # per optimizer update: every sample of the mini-batch falls in exactly one band
    assert all(isinstance(v, float) and v == v for v in rec.values())                            # status writes round(v, 5): plain finite floats


def test_the_records_do_not_depend_on_the_weight_and_the_weight_does_not_change_old_keys_shape():
    r_off = _runner()
    r_off.learn(1)
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        r_on = _runner()
        r_on.learn(1)
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0
    assert set(r_on.last_perception_losses) == set(r_off.last_perception_losses)


def test_the_ppo_optimizer_and_policy_are_not_touched_by_the_weight():
    r = _runner()
    r.learn(1)
    a_before = {k: v.clone() for k, v in r.alg.policy.state_dict().items()}
    lr_before = r.alg.learning_rate
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        r.update_perception()
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = 1.0
    assert all(torch.equal(a_before[k], v) for k, v in r.alg.policy.state_dict().items())
    assert r.alg.learning_rate == lr_before


def test_plan_and_approvals_are_not_touched():
    from foothold_s2.curriculum.ex42_prep import EX42Plan

    assert EX42Plan.load(ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml").sha256 == PLAN_SHA
    assert hashlib.sha256((ROOT / "foothold_s2" / "curriculum" / "ex42-approvals.yaml").read_bytes()).hexdigest() == APPROVALS_SHA
