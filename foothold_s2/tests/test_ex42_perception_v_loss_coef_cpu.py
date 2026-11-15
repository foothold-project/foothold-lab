"""v29-9 (P-v): PERCEPTION_V_LOSS_COEF multiplies only the velocity term of the perception loss l_ie (default 1.0 = off, bit identical).
CPU only, no fake cfg: the real StartRunner on the fake env (real collect -> replay), the real StartPerception.sequence_loss on a real replay
batch (loop and the fast a1 path), and the real update_perception logging. The coefficient is read at call time from
foothold_s2.models.start_perception, so monkeypatching that module is the real switch."""
from __future__ import annotations

import pathlib

import pytest
import torch

from foothold_s2.models import start_perception as sp
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _runner(seed=3):
    torch.manual_seed(seed)
    cfg = train_cfg(24, {"microbatch_envs": 4})
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), cfg, log_dir=None, device="cpu")


def _batch(runner):
    runner.learn(1)
    return dict(runner.replay.gather(torch.arange(runner.env.num_envs)))


def _eps(b):
    return torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, generator=torch.Generator().manual_seed(5))


def _params(perception):
    return {n: p for n, p in perception.named_parameters() if p.requires_grad}


def _loss_and_grads(runner, b, eps, impl, coef):
    """res of one real sequence_loss at the given coefficient, and the gradient of res['loss'] per parameter (None -> zeros)."""
    old = sp.PERCEPTION_V_LOSS_COEF
    sp.PERCEPTION_V_LOSS_COEF = coef
    try:
        runner.perception.zero_grad(set_to_none=True)
        res = runner.perception.sequence_loss(b, eps=eps, impl=impl)
        res["loss"].backward()
        grads = {n: (p.grad.detach().clone() if p.grad is not None else torch.zeros_like(p)) for n, p in _params(runner.perception).items()}
        return {k: v for k, v in res.items() if torch.is_tensor(v)}, grads
    finally:
        sp.PERCEPTION_V_LOSS_COEF = old


def _v_grads(runner, b, eps, impl):
    """gradient of the plain (unscaled) v term alone."""
    runner.perception.zero_grad(set_to_none=True)
    res = runner.perception.sequence_loss(b, eps=eps, impl=impl)
    res["v"].backward()
    return {n: (p.grad.detach().clone() if p.grad is not None else torch.zeros_like(p)) for n, p in _params(runner.perception).items()}


def test_default_is_off_and_the_off_term_is_the_same_object():
    assert sp.PERCEPTION_V_LOSS_COEF == 1.0
    x = torch.randn(())
    assert sp.v_loss_term(x) is x
    sp.PERCEPTION_V_LOSS_COEF = 5.0
    try:
        assert torch.equal(sp.v_loss_term(x), 5.0 * x)
    finally:
        sp.PERCEPTION_V_LOSS_COEF = 1.0


@pytest.mark.parametrize("impl", ["loop", "a1"])
def test_coef_one_is_bit_identical_to_the_old_formula_and_old_gradient(impl):
    r = _runner()
    b = _batch(r)
    eps = _eps(b)
    res, g1 = _loss_and_grads(r, b, eps, impl, 1.0)
    old_l_ie = res["kl"] + res["o_next"] + res["v"] + res["hf"] + res["hb"]
    assert torch.equal(res["l_ie"], old_l_ie)
    assert torch.equal(res["loss"], res["l_tr"] + old_l_ie)
    # the same real call a second time gives the same gradient bits (deterministic CPU path), so "coef 1.0 == the pre-change path" is checkable
    _, g1b = _loss_and_grads(r, b, eps, impl, 1.0)
    assert all(torch.equal(g1[n], g1b[n]) for n in g1)


@pytest.mark.parametrize("impl", ["loop", "a1"])
def test_coef_five_scales_only_the_v_term_in_l_ie_and_in_the_gradient(impl):
    r = _runner()
    b = _batch(r)
    eps = _eps(b)
    res1, g1 = _loss_and_grads(r, b, eps, impl, 1.0)
    res5, g5 = _loss_and_grads(r, b, eps, impl, 5.0)
    gv = _v_grads(r, b, eps, impl)
    # the logged terms are the values before the multiplication, unchanged by the coefficient
    for k in ("v", "kl", "o_next", "hf", "hb", "l_tr"):
        assert torch.equal(res1[k], res5[k]), k
    assert torch.allclose(res5["l_ie"], res5["kl"] + res5["o_next"] + 5.0 * res5["v"] + res5["hf"] + res5["hb"], rtol=1e-6, atol=1e-8)
    assert torch.allclose(res5["loss"] - res1["loss"], 4.0 * res1["v"], rtol=1e-5, atol=1e-7)
    # gradient: grad(loss_5) = grad(loss_1) + 4 * grad(v), parameter by parameter
    some_v_grad = False
    for n in g1:
        want = g1[n] + 4.0 * gv[n]
        assert torch.allclose(g5[n], want, rtol=1e-4, atol=1e-7), n
        some_v_grad = some_v_grad or bool(gv[n].abs().max() > 0)
    assert some_v_grad
    # parameters that only the non-v terms reach (the map and foot decoders) get exactly the same gradient
    dec = [n for n in g1 if ".dec_b." in n or ".dec_f." in n]
    assert dec and all(gv[n].abs().max() == 0 for n in dec)
    assert all(torch.equal(g1[n], g5[n]) for n in dec)


def test_runner_logs_the_unscaled_v_loss_and_the_scaled_l_ie():
    old = sp.PERCEPTION_V_LOSS_COEF
    out = {}
    try:
        for coef in (1.0, 5.0):
            sp.PERCEPTION_V_LOSS_COEF = coef
            r = _runner()
            r.learn(1)
            out[coef] = dict(r.last_perception_losses)
    finally:
        sp.PERCEPTION_V_LOSS_COEF = old
    for coef, d in out.items():
        want = d["kl"] + d["o_next"] + coef * d["v"] + d["hf"] + d["hb"]
        assert d["l_ie"] == pytest.approx(want, rel=1e-5, abs=1e-8), coef  # the logged l_ie carries the coefficient, the logged v does not
    assert out[5.0]["l_ie"] - (out[5.0]["kl"] + out[5.0]["o_next"] + out[5.0]["hf"] + out[5.0]["hb"]) == pytest.approx(5.0 * out[5.0]["v"], rel=1e-4)


def test_start_record_line_prints_the_coefficient(capsys):
    old = sp.PERCEPTION_V_LOSS_COEF
    sp.PERCEPTION_V_LOSS_COEF = 5.0
    try:
        r = _runner()
        capsys.readouterr()
        r._pin_perception_lr("start")
        text = capsys.readouterr().out
    finally:
        sp.PERCEPTION_V_LOSS_COEF = old
    assert "EX42_PERCEPTION_V_LOSS_COEF where=start value=5\n" in text
    assert "EX42_PERCEPTION_LR where=start" in text
