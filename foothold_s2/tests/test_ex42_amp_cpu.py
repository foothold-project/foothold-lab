"""AMP reference cutting and discriminator (plan AMP-PLAN-1126 steps 1-2): known-answer cases, no Kit, no trace files."""
import numpy as np
import torch

from foothold_s2.runners import ex42_amp_disc as amp
from foothold_s2.tools import ex42_amp_reference as ref


def test_label_walk_stop_stand_and_segments():
    wall = np.arange(200) * 0.02
    stick = np.zeros((200, 3))
    stick[20:60, 1] = 0.5                                  # walk 0.8 s, then zero stick
    kind = ref.label(stick, wall)
    assert (kind[20:60] == 0).all()
    assert (kind[60:60 + 74] == 1).all() and kind[60 + 76] == 2   # stop for 1.5 s after the last moving row
    assert (kind[:20] == 2).all()
    wall2 = wall.copy()
    wall2[100:] += 1.0                                     # a time gap starts a new segment
    seg = ref.segments(wall2, kind)
    assert seg[19] != seg[20] and seg[99] != seg[100] and seg[100] == seg[101]


def test_grad_penalty_is_on_the_normalised_input():
    disc = amp.AmpDiscriminator(2, (8,), torch.zeros(2), torch.tensor([0.05, 1.0]))
    x = torch.randn(16, 2)
    xn = disc.normalize(x).requires_grad_(True)
    (g,) = torch.autograd.grad(disc.net(xn).sum(), xn)
    assert torch.allclose(amp.grad_penalty(disc, x), g.square().sum(-1).mean())


def test_discriminator_separates_reference_from_noise_and_reward_range():
    torch.manual_seed(0)
    n = 4000
    t = torch.rand(n, 1) * 6.28
    xr = torch.cat([torch.sin(t), torch.cos(t), torch.sin(t + 0.1), torch.cos(t + 0.1)], 1)   # a circle: correlated columns
    xp = torch.randn(n, 4) * xr.std(0) + xr.mean(0)                                         # same per-column moments, no structure
    disc = amp.AmpDiscriminator(4, (64, 64), xr.mean(0), xr.std(0))
    opt = torch.optim.Adam(disc.parameters(), lr=1e-3)
    for _ in range(300):
        i = torch.randint(n, (256,))
        amp.disc_step(disc, opt, xr[i], xp[i])
    with torch.no_grad():
        dr, dp = disc(xr), disc(xp)
    assert float(dr.mean()) > 0.5 and float(dp.mean()) < -0.3
    r = amp.style_reward(torch.linspace(-3, 3, 61))
    assert float(r.min()) == 0.0 and float(r.max()) == 1.0
