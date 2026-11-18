"""o4 candidate (lead 11/18 18:34): PERCEPTION_STONE_TR_WEIGHT multiplies only the stone envs' TRNet loss (default 1.0 = off, bit identical).
CPU only: the real StartRunner on the fake env (real collect -> replay), the real sequence_loss on a real replay batch (loop and the fast paths)."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.models import start_perception as sp
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


def _runner(seed=3):
    torch.manual_seed(seed)
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), train_cfg(24, {"microbatch_envs": 4}), log_dir=None, device="cpu")


def _batch(runner):
    runner.learn(1)
    return dict(runner.replay.gather(torch.arange(runner.env.num_envs)))


def _eps(b):
    return torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, generator=torch.Generator().manual_seed(5))


def _tr(runner, b, eps, impl, weight):
    old = sp.PERCEPTION_STONE_TR_WEIGHT
    sp.PERCEPTION_STONE_TR_WEIGHT = weight
    try:
        res = runner.perception.sequence_loss(b, eps=eps, impl=impl)
        return float(res["tr"]), float(res["loss"])
    finally:
        sp.PERCEPTION_STONE_TR_WEIGHT = old


def _stone(b, envs):
    t, n = b["obs"].shape[:2]
    m = torch.zeros(t, n, dtype=torch.bool)
    m[:, envs] = True
    return m


def test_default_is_off_the_buffer_has_no_stone_key_and_the_marker_changes_nothing():
    assert sp.PERCEPTION_STONE_TR_WEIGHT == 1.0
    r = _runner()
    b = _batch(r)
    assert "stone_env" not in r.replay.data                                       # off: the replay is the old replay
    eps = _eps(b)
    base = _tr(r, b, eps, "loop", 1.0)
    marked = dict(b, stone_env=_stone(b, [0, 1, 2]))
    assert _tr(r, marked, eps, "loop", 1.0) == base                               # w = 1.0: bit identical even when a marker is present
    assert _tr(r, marked, eps, "a1", 1.0) == _tr(r, b, eps, "a1", 1.0)


def test_only_stone_envs_get_five_times_the_weight():
    r = _runner()
    b = _batch(r)
    eps = _eps(b)
    n = b["obs"].shape[1]
    sub = lambda idx: {k: (v[:, idx] if k not in ("h_prop0", "h_terr0") else v[idx]) for k, v in b.items()}      # envs are independent in the TRNet term
    tr_all, _ = _tr(r, b, eps, "loop", 1.0)
    one = torch.tensor([0]); rest = torch.arange(1, n)
    eps_one, eps_rest = eps[:, one], eps[:, rest]
    tr_one, _ = _tr(r, sub(one), eps_one, "loop", 1.0)
    tr_rest, _ = _tr(r, sub(rest), eps_rest, "loop", 1.0)
    assert tr_all == pytest.approx((tr_one + (n - 1) * tr_rest) / n, rel=1e-5)     # the decomposition the weighted value is checked against
    got, _ = _tr(r, dict(b, stone_env=_stone(b, [0])), eps, "loop", 5.0)
    assert got == pytest.approx((5.0 * tr_one + (n - 1) * tr_rest) / n, rel=1e-5)
    none, _ = _tr(r, dict(b, stone_env=_stone(b, [])), eps, "loop", 5.0)
    assert none == pytest.approx(tr_all, rel=1e-5)                                # no stone env: the same value as off (up to summation order)


@pytest.mark.parametrize("impl", ["a1", "a2", "a3"])
def test_loop_and_fast_paths_agree_with_the_weight_on(impl):
    r = _runner()
    b = _batch(r)
    eps = _eps(b)
    marked = dict(b, stone_env=_stone(b, [0, 3, 5]))
    ref = _tr(r, marked, eps, "loop", 5.0)
    new = _tr(r, marked, eps, impl, 5.0)
    assert new[0] == pytest.approx(ref[0], rel=1e-4) and new[1] == pytest.approx(ref[1], rel=1e-4)


def test_replay_keeps_stone_env_only_when_asked():
    from foothold_s2.runners.perception_replay import PerceptionReplay

    assert "stone_env" not in PerceptionReplay(4, 3, "cpu").data
    rep = PerceptionReplay(4, 3, "cpu", with_stone=True)
    assert rep.data["stone_env"].shape == (3, 4) and rep.gather(torch.arange(2))["stone_env"].shape == (3, 2)
    with pytest.raises(ValueError):
        rep.add_pre({"depth2": torch.zeros(4, 2, 60, 60), "hist": torch.zeros(4, 10, 45), "tick": torch.zeros(4, dtype=torch.bool), "first": torch.zeros(4, dtype=torch.bool)},
                    torch.zeros(4, 45), torch.zeros(4, 32, 16), torch.zeros(4, 100), torch.zeros(4, 3), torch.zeros(4, dtype=torch.bool))
