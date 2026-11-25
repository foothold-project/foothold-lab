"""EX-42 AMP style discriminator (plan AMP-PLAN-1126 step 2; Peng 2021 AMP, Escontrela 2022 LSGAN form).

A separate network used only while training: it never enters the actor, critic or ONNX export, and a checkpoint keeps it under
its own top-level key (amp_disc), so ex42_policy_signature_gate stays "same".

    input   transition (s_t, s_t+1) of the 30-wide state of ex42_amp_reference (q - stand pose, dq, gyro, grav) = 60
    norm    fixed mean / std of the reference transitions (not updated while training)
    net     MLP [512, 256] ELU -> 1
    loss    LSGAN: reference -> +1, policy -> -1, plus gradient penalty on the reference side (weight GP_WEIGHT)
    reward  style = max(0, 1 - 0.25 (D - 1)^2), in [0, 1]

No Kit import.
"""
from __future__ import annotations

import torch
from torch import nn

STATE_DIM = 30
HIDDEN = (512, 256)
GP_WEIGHT = 10.0


class AmpDiscriminator(nn.Module):
    def __init__(self, in_dim: int = 2 * STATE_DIM, hidden=HIDDEN, mean: torch.Tensor | None = None, std: torch.Tensor | None = None):
        super().__init__()
        layers, d = [], in_dim
        for h in hidden:
            layers += [nn.Linear(d, h), nn.ELU()]
            d = h
        layers.append(nn.Linear(d, 1))
        self.net = nn.Sequential(*layers)
        self.register_buffer("mean", torch.zeros(in_dim) if mean is None else mean.detach().clone().float())
        self.register_buffer("std", torch.ones(in_dim) if std is None else std.detach().clone().float().clamp_min(1e-3))

    def normalize(self, x: torch.Tensor) -> torch.Tensor:
        return (x - self.mean) / self.std

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(self.normalize(x)).squeeze(-1)


def lsgan_loss(d_ref: torch.Tensor, d_pol: torch.Tensor) -> torch.Tensor:
    return (d_ref - 1.0).square().mean() + (d_pol + 1.0).square().mean()


def grad_penalty(disc: AmpDiscriminator, x_ref: torch.Tensor) -> torch.Tensor:
    """Gradient penalty with respect to the NORMALISED input (a raw-input gradient is scaled by 1/std: a q column with std 0.05 would
    weigh 400 times more and the net could not learn at all)."""
    x = disc.normalize(x_ref.detach()).requires_grad_(True)
    d = disc.net(x).squeeze(-1)
    (g,) = torch.autograd.grad(d.sum(), x, create_graph=True)
    return g.square().sum(dim=-1).mean()


def style_reward(d: torch.Tensor) -> torch.Tensor:
    return (1.0 - 0.25 * (d - 1.0).square()).clamp_min(0.0)


def disc_step(disc: AmpDiscriminator, opt: torch.optim.Optimizer, x_ref: torch.Tensor, x_pol: torch.Tensor,
              gp_weight: float = GP_WEIGHT) -> dict:
    d_ref, d_pol = disc(x_ref), disc(x_pol)
    loss = lsgan_loss(d_ref, d_pol)
    gp = grad_penalty(disc, x_ref)
    opt.zero_grad(set_to_none=True)
    (loss + gp_weight * gp).backward()
    opt.step()
    return {"d_loss": float(loss), "gp": float(gp), "D_ref": float(d_ref.mean()), "D_pol": float(d_pol.mean())}
