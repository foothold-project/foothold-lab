"""v29-14: EX42_PERCEPTION_GRADNORM, a record of the perception gradient norm before the clip, the clip threshold and the number of clipped steps.
Record only: the training calculation is bit-identical. CPU only, real StartRunner on the fake env."""
from __future__ import annotations

import random
import re

import numpy as np
import torch
from torch import nn

from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


REAL_CLIP = nn.utils.clip_grad_norm_


def _runner(seed=3):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    r = StartRunner(FakeStartEnv(num_envs=8, seed=seed), train_cfg(24, {"microbatch_envs": 4}), log_dir=None, device="cpu")
    r.disable_logs = False
    return r


def _learn(monkeypatch, forward):
    """learn(1) with clip_grad_norm_ wrapped: the real clip runs, `forward` decides what the caller gets back. Returns (runner, real norms)."""
    real = REAL_CLIP
    norms = []
    r = _runner()
    ids = {id(p) for p in r.perception.parameters()}

    def wrapped(params, max_norm, *a, **k):
        params = list(params)
        total = real(params, max_norm, *a, **k)
        if params and id(params[0]) in ids:                   # the PPO update clips the policy too: only the perception calls count
            norms.append(float(total))
            return forward(total)
        return total

    monkeypatch.setattr(nn.utils, "clip_grad_norm_", wrapped)
    r.learn(1)
    return r, norms


def test_the_line_reports_the_real_pre_clip_norm_and_the_training_is_bit_identical(monkeypatch, capsys):
    _runner().learn(1)                                        # the first run of a process differs from later ones (warm-up state), so it is not compared
    capsys.readouterr()
    a, norms = _learn(monkeypatch, lambda t: t)
    out = capsys.readouterr().out
    line = [ln for ln in out.splitlines() if ln.startswith("EX42_PERCEPTION_GRADNORM")]
    assert len(line) == 1
    m = re.match(r"EX42_PERCEPTION_GRADNORM it=(\d+) n=(\d+) mean=([\d.]+) max=([\d.]+) clip_threshold=([\d.]+) clipped=(\d+)$", line[0])
    assert m, line[0]
    n, mean, mx, thr, clipped = int(m[2]), float(m[3]), float(m[4]), float(m[5]), int(m[6])
    assert n == len(norms) > 0 and thr == 1.0
    assert abs(mean - sum(norms) / len(norms)) < 1.0e-4 and abs(mx - max(norms)) < 1.0e-4
    assert clipped == sum(1 for x in norms if x > 1.0)

    # the same run, but the caller gets a constant back instead of the norm: if the record fed back into the calculation, the weights would differ
    b, _ = _learn(monkeypatch, lambda t: torch.tensor(0.0))
    capsys.readouterr()
    sa, sb = a.perception.state_dict(), b.perception.state_dict()
    assert sa.keys() == sb.keys() and all(torch.equal(sa[k], sb[k]) for k in sa)
    pa, pb = a.alg.policy.state_dict(), b.alg.policy.state_dict()
    assert all(torch.equal(pa[k], pb[k]) for k in pa)
