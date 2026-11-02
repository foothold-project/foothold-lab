"""W89 export wiring tests without Isaac Sim or a GPU."""
from __future__ import annotations

import torch
import pytest

from foothold_s2.deploy.export_ex40_w89 import (PerceptionActor, actor_from_checkpoint,
                                                  example_inputs, load_components)
from foothold_s2.models.start_perception import PerceptionCfg, StartPerception


def actor_state():
    layers = torch.nn.Sequential(torch.nn.Linear(96, 512), torch.nn.ELU(),
                                 torch.nn.Linear(512, 256), torch.nn.ELU(),
                                 torch.nn.Linear(256, 128), torch.nn.ELU(),
                                 torch.nn.Linear(128, 12))
    return {"actor." + name: value for name, value in layers.state_dict().items()}


def test_actor_uses_only_saved_twelve_action_mlp():
    torch.manual_seed(23)
    saved = actor_state()
    actor = actor_from_checkpoint({**saved, "critic.0.weight": torch.ones(1)})
    assert torch.equal(actor.state_dict()["0.weight"], saved["actor.0.weight"])
    assert actor(torch.zeros(1, 96)).shape == (1, 12)


def test_perception_actor_output_and_map_mask_are_real():
    torch.manual_seed(31)
    on = PerceptionActor(StartPerception(PerceptionCfg()), actor_from_checkpoint(actor_state()),
                         map_off=False).eval()
    torch.manual_seed(31)
    off = PerceptionActor(StartPerception(PerceptionCfg()), actor_from_checkpoint(actor_state()),
                          map_off=True).eval()
    inputs = example_inputs()
    with torch.no_grad():
        on_out = on(*inputs)
        off_out = off(*inputs)
    assert [tuple(t.shape) for t in on_out] == [(1, 12), (1, 128), (1, 128), (1, 32, 16)]
    assert all(torch.isfinite(t).all() for t in on_out + off_out)
    assert not torch.equal(on_out[0], off_out[0])


def test_wrong_checkpoint_sha_is_rejected_before_load(tmp_path):
    path = tmp_path / "model_6000.pt"
    path.write_bytes(b"not a checkpoint")
    with pytest.raises(ValueError, match="SHA256 differs"):
        load_components(path, "0" * 64)
