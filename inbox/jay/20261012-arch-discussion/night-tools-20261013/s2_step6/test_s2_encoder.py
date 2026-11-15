"""CPU known answers for MLP and attention map encoders using real E1 parent weights."""
from __future__ import annotations

import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "s2_step2" / "base_step1"))
import s2_policy as P
from s2_encoder_policy import S2EncoderChoice, encoder_budget


def check(label, good):
    print(("PASS" if good else "FAIL") + " " + label, flush=True)
    if not good:
        raise AssertionError(label)


def policy(parent, mode, name):
    return S2EncoderChoice(parent, mode, map_encoder=name, map_init_seed=0,
                           attn_embed_dim=32, attn_num_heads=4, attn_dropout=0.0).eval()


def test_all():
    torch.set_num_threads(2)
    parent, meta = P.load_parent_cpu()
    obs = {"policy": torch.randn(3, meta["dims"]["policy"]),
           "critic": torch.randn(3, meta["dims"]["critic"]),
           "single_obs": torch.randn(3, meta["dims"]["single_obs"])}
    zero = torch.zeros(3, 374)
    a = policy(parent, "A", "mlp")
    b = policy(parent, "B", "mlp")
    aa = policy(parent, "A", "attn")
    ba = policy(parent, "B", "attn")
    check("mlp_same_374_128_64", [p.shape for p in b.map_encoder.parameters()] ==
          [torch.Size([128, 374]), torch.Size([128]), torch.Size([64, 128]), torch.Size([64])])
    check("mlp_A_B_same_seed", all(torch.equal(a.state_dict()[k], b.state_dict()[k]) for k in a.state_dict()))
    with torch.no_grad():
        ref = parent.act_inference(obs)
        for pol, mp in ((a, zero), (b, torch.randn(3, 374)), (aa, zero), (ba, torch.randn(3, 374))):
            o = {**obs, "map": mp}
            check("parent_initial_action_"+pol.mode+"_"+pol.map_encoder_name,
                  torch.equal(pol.act_inference(o), ref))
            check("encoder_shape_"+pol.mode+"_"+pol.map_encoder_name,
                  pol.map_encoder(pol.map_input(o)).shape == (3, 64))
    for pol in (a, aa):
        try:
            pol.act_inference({**obs, "map": torch.ones(3, 374)})
        except ValueError:
            check("A_information_block_"+pol.map_encoder_name, True)
        else:
            check("A_information_block_"+pol.map_encoder_name, False)
    try:
        S2EncoderChoice(parent, "B", map_encoder="unknown", map_init_seed=0,
                        attn_embed_dim=32, attn_num_heads=4, attn_dropout=0.)
    except ValueError:
        check("unknown_encoder_rejected", True)
    else:
        check("unknown_encoder_rejected", False)
    optimizer, control = P.make_optimizer(ba, meta["last_lr"], encoder_mode="full_freeze")
    check("student_frozen_map_trainable", not any(p.requires_grad for p in ba.student_moe_encoder.parameters()) and
          all(p.requires_grad for p in ba.map_encoder.parameters()) and
          {g["name"] for g in optimizer.param_groups} == {"map_encoder", "actor", "critic", "std"})
    check("encoder_control_compatible", control.encoder_mode == "full_freeze" and control.completed_updates == 0)
    check("actor_map_columns_zero", int(torch.count_nonzero(ba.actor_in_map.weight)) == 0 and
          ba.actor_first_layer_weight().shape == (512, 141))
    mb, ab = encoder_budget(b), encoder_budget(ba)
    check("encoder_budget_measured", mb["encoder_parameters"] == 56256 and
          ab["encoder_parameters"] > 0 and ab["affine_attention_macs_lower_bound_per_observation"] > 0)
    try:
        ba.load_checkpoint_bundle(b.checkpoint_bundle())
    except ValueError:
        check("checkpoint_encoder_name_guard", True)
    else:
        check("checkpoint_encoder_name_guard", False)
    print("BUDGET", mb, ab, flush=True)


if __name__ == "__main__":
    test_all()
