"""Replaceable S2 map encoder, CPU import only. This is not an AME-2 reproduction."""
from __future__ import annotations

import sys
from pathlib import Path

import torch
from torch import nn

_BASE = Path(__file__).resolve().parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))
import s2_map_obs as M
from s2_policy import S2MapActorCritic


class AttentionMapEncoder(nn.Module):
    """Point height/mask/xy, global pooled context, one query and multihead attention."""

    def __init__(self, *, embed_dim: int, num_heads: int, dropout: float, output_dim: int):
        super().__init__()
        if type(embed_dim) is not int or type(num_heads) is not int or embed_dim <= 0 or num_heads <= 0 or embed_dim % num_heads:
            raise ValueError("bad_attention_shape")
        if type(dropout) not in (int, float) or not 0 <= dropout < 1:
            raise ValueError("bad_dropout")
        if output_dim != 64:
            raise ValueError("map_latent_dim_must_be_64")
        self.point = nn.Sequential(nn.Linear(4, embed_dim), nn.ELU(), nn.Linear(embed_dim, embed_dim), nn.ELU())
        self.global_net = nn.Sequential(nn.Linear(2*embed_dim, embed_dim), nn.ELU())
        self.attn = nn.MultiheadAttention(embed_dim, num_heads, dropout=dropout, batch_first=True)
        self.out = nn.Linear(2*embed_dim, output_dim)
        self.register_buffer("xy", M.grid_ray_xy_body(), persistent=False)
        if self.xy.shape != (187, 2):
            raise ValueError("unexpected_grid")

    def forward(self, flat: torch.Tensor) -> torch.Tensor:
        if flat.ndim != 2 or flat.shape[1] != M.MAP_DIM:
            raise ValueError("map_shape")
        n = flat.shape[0]
        height, mask = flat[:, :187], flat[:, 187:]
        xy = self.xy.to(device=flat.device, dtype=flat.dtype).expand(n, -1, -1)
        local = self.point(torch.cat((height.unsqueeze(-1), mask.unsqueeze(-1), xy), dim=-1))
        global_feature = self.global_net(torch.cat((local.mean(dim=1), local.max(dim=1).values), dim=-1))
        # Invalid positions remain numeric tokens. Masking all A positions would create NaNs.
        weighted, _ = self.attn(global_feature.unsqueeze(1), local, local, need_weights=False)
        return self.out(torch.cat((global_feature, weighted.squeeze(1)), dim=-1))


class S2EncoderChoice(S2MapActorCritic):
    """Copied policy interface. map_encoder and every architectural choice are explicit."""

    def __init__(self, parent: nn.Module, mode: str, *, map_encoder: str, map_init_seed: int,
                 attn_embed_dim: int, attn_num_heads: int, attn_dropout: float):
        if map_encoder not in ("mlp", "attn"):
            raise ValueError("unknown_map_encoder")
        super().__init__(parent, mode, map_dim=M.MAP_DIM, map_hidden_dims=(128,),
                         map_latent_dim=64, map_init_seed=map_init_seed, guard_a_constant=True)
        self.map_encoder_name = map_encoder
        self.encoder_spec = {"name": map_encoder, "seed": map_init_seed, "embed_dim": attn_embed_dim,
                             "num_heads": attn_num_heads, "dropout": attn_dropout, "map_dim": 374, "latent_dim": 64}
        if map_encoder == "attn":
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(map_init_seed)
                self.map_encoder = AttentionMapEncoder(embed_dim=attn_embed_dim, num_heads=attn_num_heads,
                                                       dropout=attn_dropout, output_dim=64)

    def checkpoint_bundle(self) -> dict:
        return {"encoder_spec": self.encoder_spec.copy(), "state_dict": self.state_dict()}

    def load_checkpoint_bundle(self, bundle: dict) -> None:
        if bundle.get("encoder_spec") != self.encoder_spec:
            raise ValueError("encoder_checkpoint_incompatible")
        self.load_state_dict(bundle["state_dict"], strict=True)


def encoder_budget(policy: S2EncoderChoice) -> dict:
    """Parameters exact; MAC estimate covers affine projections and one-query QK/AV only."""
    params = sum(p.numel() for p in policy.map_encoder.parameters())
    if policy.map_encoder_name == "mlp":
        macs = 374*128 + 128*64
    else:
        d = policy.encoder_spec["embed_dim"]
        n = 187
        macs = n*(4*d + d*d) + 2*d*d + n*(3*d*d) + d*d + 2*n*d + 2*d*64
    return {"encoder_parameters": params, "affine_attention_macs_lower_bound_per_observation": macs,
            "scope": "linear projections and QK/AV; excludes nonlinear, pooling, layer implementation overhead"}
