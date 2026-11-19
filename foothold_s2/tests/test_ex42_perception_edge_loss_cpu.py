"""Edge-weighted reconstruction loss (PERCEPTION_EDGE_WEIGHT, default 1.0 = off): the L_TR cell errors are multiplied by a weight on the cells next to a >= 0.2 m height step
of the true map. CPU only: the formula on hand-built maps, and the real StartRunner on the fake env (its real collect -> replay -> sequence_loss path, every replay impl).
The weight and the step are read at call time from foothold_s2.models.start_perception, so monkeypatching that module is the real switch."""
from __future__ import annotations

import pytest
import torch
import torch.nn.functional as F

from foothold_s2.models import start_perception as sp
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

OLD_KEYS = {"l_tr", "l_ie", "kl", "o_next", "v", "hf", "hb"}


def _flat(n=2, h=-0.3):
    return torch.full((n, sp.MAP_X, sp.MAP_Y), h)


def _on(weight=3.0, step=0.2):
    sp.PERCEPTION_EDGE_WEIGHT, sp.PERCEPTION_EDGE_STEP_M = weight, step


def _off():
    sp.PERCEPTION_EDGE_WEIGHT, sp.PERCEPTION_EDGE_STEP_M = 1.0, 0.2


def test_defaults_are_off_and_the_step_is_twenty_centimetres():
    assert sp.PERCEPTION_EDGE_WEIGHT == 1.0 and sp.PERCEPTION_EDGE_STEP_M == 0.2


def test_the_mask_marks_both_cells_of_a_step_and_only_steps_at_or_above_the_threshold():
    g = _flat(3)
    g[0, 10:, :] += 0.25                      # a 0.25 m riser across the map between rows 9 and 10
    g[1, 10:, :] += 0.15                      # a 0.15 m riser: below the threshold
    g[2, 5, 7] = -1.0                         # one missed-ray cell (-1) in a flat floor: its four neighbours differ by 0.7 m
    m = sp.edge_cell_mask(g)
    assert m.shape == g.shape and m.dtype == torch.bool
    assert m[0, 9].all() and m[0, 10].all() and int(m[0].sum()) == 2 * sp.MAP_Y     # both sides of the step, nothing else
    assert not m[1].any()
    assert int(m[2].sum()) == 5 and m[2, 5, 7] and m[2, 4, 7] and m[2, 6, 7] and m[2, 5, 6] and m[2, 5, 8]
    exact = _flat(1); exact[0, 10:, :] += 0.2
    assert sp.edge_cell_mask(exact)[0, 9].all()                                    # the step itself counts (>=)
    steep = _flat(1); steep[0, :, 8:] += 0.5                                       # a step along the other axis (columns 7 | 8)
    ms = sp.edge_cell_mask(steep)
    assert ms[0, :, 7].all() and ms[0, :, 8].all() and int(ms.sum()) == 2 * sp.MAP_X
    assert not sp.edge_cell_mask(_flat(2)).any()                                   # a flat map has none (map border is not an edge)


def test_the_mask_takes_a_flattened_512_map_and_a_custom_step():
    g = _flat(2)
    g[0, 10:, :] += 0.25
    assert torch.equal(sp.edge_cell_mask(g.reshape(2, -1)), sp.edge_cell_mask(g).reshape(2, -1))
    assert not sp.edge_cell_mask(g, step_m=0.3).any() and sp.edge_cell_mask(g, step_m=0.1).any()


def _tensors(seed=1):
    gen = torch.Generator().manual_seed(seed)
    hb = _flat(4)
    hb[:, 12:, :] += 0.3
    hb[1, :, 4] -= 0.5
    return torch.randn(4, sp.MAP_X, sp.MAP_Y, generator=gen) * 0.2 + hb, torch.randn(4, sp.MAP_X, sp.MAP_Y, generator=gen) * 0.1 + hb, hb


def test_off_is_bit_identical_to_the_old_formula_and_on_is_the_weighted_cell_mean():
    rough, refined, hb = _tensors()
    old = F.mse_loss(rough, hb) + F.l1_loss(refined, hb)
    assert torch.equal(sp.loss_tr(rough, refined, hb), old)
    _on(3.0)
    try:
        edge = sp.edge_cell_mask(hb).float()
        assert 0.0 < float(edge.mean()) < 1.0
        w = 1.0 + 2.0 * edge
        want = (w * (rough - hb) ** 2).mean() + (w * (refined - hb).abs()).mean()
        got = sp.loss_tr(rough, refined, hb)
        assert torch.allclose(got, want, atol=1e-7) and float(got) > float(old)
        flat = _flat(4)                                                           # no edge anywhere: weights are all 1, same value as off
        assert torch.allclose(sp.loss_tr(rough, refined, flat), F.mse_loss(rough, flat) + F.l1_loss(refined, flat), atol=1e-7)
        _on(1.0001)
        assert float(sp.loss_tr(rough, refined, hb)) == pytest.approx(float(old), rel=1e-3)
    finally:
        _off()


def test_the_weight_scales_only_the_edge_cells_error():
    rough, refined, hb = _tensors()
    err = torch.zeros_like(hb)
    mask = sp.edge_cell_mask(hb)
    err[mask] = 0.1                                                               # error only on edge cells
    _on(5.0)
    try:
        on = float(sp.loss_tr(hb + err, hb + err, hb))
    finally:
        _off()
    off = float(sp.loss_tr(hb + err, hb + err, hb))
    assert on == pytest.approx(5.0 * off, rel=1e-5)                               # the same error on edge cells is 5x
    err2 = torch.zeros_like(hb)
    err2[~mask] = 0.1                                                             # error only off the edges: unchanged
    _on(5.0)
    try:
        on2 = float(sp.loss_tr(hb + err2, hb + err2, hb))
    finally:
        _off()
    assert on2 == pytest.approx(float(sp.loss_tr(hb + err2, hb + err2, hb)), rel=1e-6)


def _runner(seed=3):
    torch.manual_seed(seed)
    cfg = train_cfg(24, {"microbatch_envs": 4})
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), cfg, log_dir=None, device="cpu")


def _batch_with_edges(runner):
    runner.learn(1)
    b = dict(runner.replay.gather(torch.arange(runner.env.num_envs)))
    gm = b["gt_map"].clone().reshape(*b["gt_map"].shape[:2], sp.MAP_X, sp.MAP_Y)
    gm[..., 14:, :] += 0.3                                                        # a 0.3 m riser in every sample of the real batch
    b["gt_map"] = gm.reshape(b["gt_map"].shape)
    return b


def test_every_replay_impl_gives_the_same_l_tr_with_the_weight_on_and_the_off_value_is_untouched():
    r = _runner()
    b = _batch_with_edges(r)
    eps = torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, generator=torch.Generator().manual_seed(5))
    off = {i: float(r.perception.sequence_loss(b, eps=eps, impl=i)["l_tr"]) for i in ("loop", "a1", "a2", "a3")}
    _on(3.0)
    try:
        on = {i: float(r.perception.sequence_loss(b, eps=eps, impl=i)["l_tr"]) for i in ("loop", "a1", "a2", "a3")}
    finally:
        _off()
    assert max(off.values()) - min(off.values()) < 1e-4 and max(on.values()) - min(on.values()) < 1e-4
    assert on["loop"] > off["loop"]


def test_the_weight_moves_the_trnet_gradient_only_and_changes_no_old_key_or_shape():
    r = _runner()
    b = _batch_with_edges(r)
    eps = torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, generator=torch.Generator().manual_seed(5))
    tr = [p for p in r.perception.trnet.parameters() if p.requires_grad]
    ie = [p for p in r.perception.ie.parameters() if p.requires_grad]
    g_off = torch.autograd.grad(r.perception.sequence_loss(b, eps=eps, impl="loop")["loss"], tr + ie, allow_unused=True)
    _on(3.0)
    try:
        g_on = torch.autograd.grad(r.perception.sequence_loss(b, eps=eps, impl="loop")["loss"], tr + ie, allow_unused=True)
    finally:
        _off()
    n = len(tr)
    assert any(not torch.equal(u, v) for u, v in zip(g_off[:n], g_on[:n]) if u is not None)           # TR-Net gradient changes
    assert all(torch.equal(u, v) for u, v in zip(g_off[n:], g_on[n:]) if u is not None)                # I-E gradient does not (gradient border)


def test_a_real_update_perception_runs_with_the_weight_on_and_keeps_the_record_keys():
    r_off = _runner()
    r_off.learn(1)
    _on(3.0)
    try:
        r_on = _runner()
        r_on.learn(1)
    finally:
        _off()
    assert OLD_KEYS <= set(r_on.last_perception_losses) and set(r_on.last_perception_losses) == set(r_off.last_perception_losses)
    assert all(isinstance(v, float) and v == v for v in r_on.last_perception_losses.values())


def test_the_announce_line_names_the_weight_and_the_step(capsys):
    r = _runner()
    r.perception_optimizer.param_groups                                            # built
    r._pin_perception_lr("test")
    out = capsys.readouterr().out
    assert "EX42_PERCEPTION_EDGE where=test weight=1 step_m=0.2" in out
