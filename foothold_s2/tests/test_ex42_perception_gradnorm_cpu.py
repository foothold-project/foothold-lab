"""EX42_PERCEPTION_GRADNORM: a record only. It reads the return value of the existing clip call and, on the first mini-batch, the gradient
of the v term (as it enters l_ie, coefficient included) with torch.autograd.grad; neither may change training."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.models import start_perception as sp
from foothold_s2.tests.test_ex42_perception_v_loss_coef_cpu import _runner


def _state(r):
    return ({n: p.detach().clone() for n, p in r.perception.named_parameters()},
            {i: {k: v.detach().clone() for k, v in s.items() if torch.is_tensor(v)} for i, s in enumerate(r.perception_optimizer.state.values())},
            torch.get_rng_state().clone())


def _same(a, b):
    return (all(torch.equal(a[0][n], b[0][n]) for n in a[0]) and a[1].keys() == b[1].keys()
            and all(torch.equal(a[1][i][k], b[1][i][k]) for i in a[1] for k in a[1][i]) and torch.equal(a[2], b[2]))


@pytest.mark.parametrize("impl", ["loop", "a1", "a3"])
def test_the_record_does_not_change_the_update_bit_for_bit(impl, monkeypatch):
    """Only update_perception is run twice from one saved state (a whole learn() is not bit-repeatable with impl a3 on CPU, with or
    without this change: two plain runs differ). Same replay, same weights, same optimizer state, same RNG."""
    import copy
    r = _runner()
    r.pcfg["replay_impl"] = impl
    r.learn(1)
    saved = (copy.deepcopy(r.perception.state_dict()), copy.deepcopy(r.perception_optimizer.state_dict()), torch.get_rng_state().clone())

    def run(disabled):
        r.perception.load_state_dict(saved[0])
        r.perception_optimizer.load_state_dict(copy.deepcopy(saved[1]))
        torch.set_rng_state(saved[2])
        if disabled:        # the v-term gradient call replaced by "nothing"; the clip return value is read in both
            monkeypatch.setattr(torch.autograd, "grad", lambda outs, ins, **kw: [None] * len(ins))
        else:
            monkeypatch.undo()
        r.update_perception()
        return _state(r), r.last_perception_gradnorm
    on, rec_on = run(False)
    off, rec_off = run(True)
    monkeypatch.undo()
    assert _same(on, off)
    assert rec_on["first_v_term"] > 0.0 and rec_off["first_v_term"] == 0.0
    assert rec_on["total_mean"] == rec_off["total_mean"] and rec_on["total_max"] == rec_off["total_max"]


def test_the_v_term_norm_scales_with_the_coefficient_and_the_line_is_one_line(capsys):
    out = {}
    old = sp.PERCEPTION_V_LOSS_COEF
    try:
        for coef in (5.0, 20.0):
            sp.PERCEPTION_V_LOSS_COEF = coef
            r = _runner()
            capsys.readouterr()
            r.learn(1)
            text = capsys.readouterr().out
            lines = [x for x in text.splitlines() if x.startswith("EX42_PERCEPTION_GRADNORM ")]
            assert len(lines) == 1 and "it=0 " in lines[0] and "clipped=" in lines[0] and "first_v_term=" in lines[0]
            out[coef] = r.last_perception_gradnorm
    finally:
        sp.PERCEPTION_V_LOSS_COEF = old
    g5, g20 = out[5.0], out[20.0]
    assert g5["clip"] == 1.0 and g5["n"] >= 1 and g5["total_max"] >= g5["total_mean"] > 0
    assert g20["first_v_term"] / g5["first_v_term"] == pytest.approx(4.0, rel=1e-4)       # same state and batch: the first mini-batch is identical
