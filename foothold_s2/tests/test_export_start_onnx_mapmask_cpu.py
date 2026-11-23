"""Known-input parity for the shared map-on/off step graph."""

import torch
from torch import nn

from foothold_s2.deploy import export_start_onnx as base
from foothold_s2.deploy.export_start_onnx_mapmask import MaskedStepNet
from foothold_s2.models.start_perception import PerceptionCfg, StartPerception


def test_mask_values_match_the_two_original_torch_paths_and_mixed_batch():
    torch.manual_seed(1123)
    perception = StartPerception(PerceptionCfg(map_input="reconstruction")).eval()
    actor = nn.Sequential(nn.Linear(98, 12)).eval()
    vx = (True, .009, .3)
    shared = MaskedStepNet(perception, actor, vx).eval()
    old = base.StepNet(perception, actor, vx).eval()
    inputs = tuple(x.clone() for x in base.example_inputs(b=2))
    depth = list(inputs)
    depth[2] = torch.rand_like(depth[2])
    inputs = tuple(depth)
    with torch.inference_mode():
        for mask_value in (0.0, 1.0):
            perception.ie.mask_map_tokens = bool(mask_value)
            reference = old(*inputs)
            output = shared(*inputs, torch.full((2, 1), mask_value))
            for a, b in zip(output, reference):
                torch.testing.assert_close(a, b, rtol=0, atol=1e-6)
        perception.ie.mask_map_tokens = False
        on = old(*inputs)
        perception.ie.mask_map_tokens = True
        off = old(*inputs)
        mixed = shared(*inputs, torch.tensor([[0.0], [1.0]]))
    assert torch.max(torch.abs(on[4] - off[4])).item() > 1e-7
    for output_index in range(len(mixed)):
        torch.testing.assert_close(mixed[output_index][0], on[output_index][0], rtol=0, atol=1e-6)
        torch.testing.assert_close(mixed[output_index][1], off[output_index][1], rtol=0, atol=1e-6)
