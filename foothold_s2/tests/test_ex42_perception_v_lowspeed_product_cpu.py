"""v29-13: the record line of PERCEPTION_V_LOWSPEED_WEIGHT and how it multiplies with PERCEPTION_V_LOSS_COEF (v29-9 P-v).
CPU only, no fake cfg: the real StartRunner on the fake env (real collect -> replay), the real StartPerception.sequence_loss on a real replay
batch (loop and the fast a1 path) and the real _pin_perception_lr record. Both constants are read at call time from
foothold_s2.models.start_perception, so monkeypatching that module is the real switch."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.models import start_perception as sp
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


def _runner(seed=3):
    torch.manual_seed(seed)
    cfg = train_cfg(24, {"microbatch_envs": 4})
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), cfg, log_dir=None, device="cpu")


def _batch(runner):
    runner.learn(1)
    return dict(runner.replay.gather(torch.arange(runner.env.num_envs)))


def _eps(b):
    return torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, generator=torch.Generator().manual_seed(5))


def _loss(runner, b, eps, impl, weight, coef):
    old = (sp.PERCEPTION_V_LOWSPEED_WEIGHT, sp.PERCEPTION_V_LOSS_COEF)
    sp.PERCEPTION_V_LOWSPEED_WEIGHT, sp.PERCEPTION_V_LOSS_COEF = weight, coef
    try:
        runner.perception.zero_grad(set_to_none=True)
        res = runner.perception.sequence_loss(b, eps=eps, impl=impl)
        res["loss"].backward()
        grads = {n: (p.grad.detach().clone() if p.grad is not None else torch.zeros_like(p))
                 for n, p in runner.perception.named_parameters() if p.requires_grad}
        return {k: v for k, v in res.items() if torch.is_tensor(v)}, grads
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT, sp.PERCEPTION_V_LOSS_COEF = old


def _truth(b, vx, vy):
    out = dict(b)
    out["base_vel"] = torch.zeros_like(b["base_vel"])
    out["base_vel"][..., 0] = vx
    out["base_vel"][..., 1] = vy
    return out


@pytest.mark.parametrize("impl", ["loop", "a1"])
def test_the_weight_and_the_coefficient_multiply_on_the_slow_axes_and_the_coefficient_alone_elsewhere(impl):
    r = _runner()
    base = _batch(r)
    eps = _eps(base)
    # every sample slow on both axes (truth 0 < 0.3): the v term of the unweighted loss is scaled by w on vx and vy and 1 on vz
    slow = _truth(base, 0.1, 0.1)
    off, _ = _loss(r, slow, eps, impl, 1.0, 1.0)
    on, _ = _loss(r, slow, eps, impl, 3.0, 5.0)
    only_w, _ = _loss(r, slow, eps, impl, 3.0, 1.0)
    only_c, _ = _loss(r, slow, eps, impl, 1.0, 5.0)
    assert float(only_w["v"]) > float(off["v"])                                   # the weight raises the logged v (post-weight, pre-coefficient)
    assert torch.equal(on["v"], only_w["v"]) and torch.equal(only_c["v"], off["v"])   # the coefficient never touches the logged v
    # l_ie carries 5 * v_weighted: the two factors multiply (5 * 3 on a slow axis, 5 * 1 on vz), nothing else moves
    rest = lambda x: x["kl"] + x["o_next"] + x["hf"] + x["hb"]
    assert float(on["l_ie"]) == pytest.approx(float(rest(on)) + 5.0 * float(on["v"]), rel=1e-5)
    assert float(only_c["l_ie"]) == pytest.approx(float(rest(only_c)) + 5.0 * float(off["v"]), rel=1e-5)
    # a batch with no slow axis (truth 1.0 on both): the weight is a no-op bit for bit, the coefficient still scales
    fast = _truth(base, 1.0, 1.0)
    f_off, g_off = _loss(r, fast, eps, impl, 1.0, 5.0)
    f_on, g_on = _loss(r, fast, eps, impl, 3.0, 5.0)
    assert torch.equal(f_off["v"], f_on["v"]) and torch.equal(f_off["l_ie"], f_on["l_ie"])
    # the gradient of the weighted path goes through (w * err).mean() instead of F.mse_loss: same maths, other graph, so last-bit float32 differences are allowed
    for n in g_off:
        scale = max(float(g_off[n].abs().max()), 1e-3)
        assert float((g_off[n] - g_on[n]).abs().max()) <= 1e-5 * scale, n


@pytest.mark.parametrize("impl", ["loop", "a1"])
def test_weight_one_and_coefficient_one_is_the_old_formula_bit_for_bit(impl):
    r = _runner()
    b = _batch(r)
    eps = _eps(b)
    res, _ = _loss(r, b, eps, impl, 1.0, 1.0)
    assert torch.equal(res["l_ie"], res["kl"] + res["o_next"] + res["v"] + res["hf"] + res["hb"])


def test_start_record_line_prints_the_weight_and_the_threshold(capsys):
    old = sp.PERCEPTION_V_LOWSPEED_WEIGHT
    sp.PERCEPTION_V_LOWSPEED_WEIGHT = 3.0
    try:
        r = _runner()
        capsys.readouterr()
        r._pin_perception_lr("start")
        text = capsys.readouterr().out
    finally:
        sp.PERCEPTION_V_LOWSPEED_WEIGHT = old
    assert "EX42_PERCEPTION_V_LOWSPEED_WEIGHT where=start value=3 threshold=0.3\n" in text
    assert "EX42_PERCEPTION_V_LOSS_COEF where=start" in text


def test_replay_fast_uses_the_same_two_functions_as_the_loop():
    import pathlib
    text = (pathlib.Path(__file__).resolve().parents[1] / "models" / "replay_fast.py").read_text(encoding="utf-8")
    assert "v_loss_term(res[\"v\"])" in text and "velocity_loss(" in text
