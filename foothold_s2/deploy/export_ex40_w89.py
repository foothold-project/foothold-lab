"""Export the EX-40 m6000 START perception and actor as fixed-map-mode ONNX graphs.

The caller owns history, depth-frame delay and GRU states. This export never
loads Isaac Sim or the S1-blind 495-column deployment policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from torch import nn

from foothold_s2.models.start_perception import PerceptionCfg, StartPerception


INPUT_NAMES = ("obs45", "hist", "depth2", "h_prop", "h_terr", "depth_tick",
               "first_after_reset", "use_gt", "gt_map")
OUTPUT_NAMES = ("action", "h_prop_next", "h_terr_next", "recon_map")
M6000_SHA256 = "d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PerceptionActor(nn.Module):
    def __init__(self, perception: StartPerception, actor: nn.Module, *, map_off: bool) -> None:
        super().__init__()
        self.perception = perception
        self.actor = actor
        self.perception.ie.mask_map_tokens = bool(map_off)

    def forward(self, obs45, hist, depth2, h_prop, h_terr, depth_tick,
                first_after_reset, use_gt, gt_map):
        h_prop_next, h_terr_next, out = self.perception._advance(
            h_prop, h_terr, hist, depth2, depth_tick, first_after_reset,
            use_gt, gt_map)
        est = torch.cat((out["mu"], out["v"], out["zf"], out["zb"]), dim=-1)
        action = self.actor(torch.cat((obs45, est), dim=-1))
        return action, h_prop_next, h_terr_next, out["refined"]


def actor_from_checkpoint(state: dict[str, torch.Tensor]) -> nn.Sequential:
    actor = nn.Sequential(nn.Linear(96, 512), nn.ELU(), nn.Linear(512, 256), nn.ELU(),
                          nn.Linear(256, 128), nn.ELU(), nn.Linear(128, 12))
    keys = {key.removeprefix("actor."): value for key, value in state.items()
            if key.startswith("actor.")}
    actor.load_state_dict(keys, strict=True)
    return actor.eval()


def load_components(checkpoint: Path, expected_sha256: str) -> tuple[StartPerception, nn.Sequential]:
    if not checkpoint.is_file() or sha256(checkpoint) != expected_sha256:
        raise ValueError("EX-40 checkpoint missing or SHA256 differs")
    sd = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if int(sd.get("iter", -1)) != 6000:
        raise ValueError("W89 requires the measured EX-40 m6000 checkpoint")
    cfg = sd.get("perception_cfg") or {}
    if (cfg.get("map_input") != "reconstruction" or cfg.get("est_mode") != "learned"
            or cfg.get("force_gt") is not True):
        raise ValueError("EX-40 m6000 perception contract differs")
    perception = StartPerception(PerceptionCfg(map_input="reconstruction", force_gt=True))
    perception.load_state_dict(sd["perception_state_dict"], strict=True)
    return perception.eval(), actor_from_checkpoint(sd["model_state_dict"])


def example_inputs() -> tuple[torch.Tensor, ...]:
    torch.manual_seed(6000)
    return (torch.randn(1, 45), torch.randn(1, 10, 45), torch.rand(1, 2, 60, 60),
            torch.randn(1, 128), torch.randn(1, 128),
            torch.tensor([True]), torch.tensor([False]), torch.tensor([False]),
            torch.randn(1, 32, 16))


def export(checkpoint: Path, output: Path, expected_sha256: str) -> dict:
    if not output.is_absolute():
        raise ValueError("output directory must be absolute")
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.backends.mha.set_fastpath_enabled(False)
    artifacts = {}
    for mode in ("map_on", "map_off"):
        perception, actor = load_components(checkpoint, expected_sha256)
        net = PerceptionActor(perception, actor, map_off=(mode == "map_off")).eval()
        path = output / f"ex40_m6000_{mode}.onnx"
        if path.exists():
            raise FileExistsError(path)
        with torch.no_grad():
            torch.onnx.export(net, example_inputs(), str(path), input_names=list(INPUT_NAMES),
                              output_names=list(OUTPUT_NAMES), opset_version=17,
                              dynamo=False, do_constant_folding=True)
        artifacts[mode] = {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
    contract = {"format": "foothold-ex40-w89-onnx/1", "checkpoint": str(checkpoint),
                "checkpoint_sha256": expected_sha256, "source": str(Path(__file__).resolve()),
                "source_sha256": sha256(Path(__file__)), "batch": 1,
                "inputs": list(INPUT_NAMES), "outputs": list(OUTPUT_NAMES),
                "actor_input_order": "obs45 + [mu16, v3, zf16, zb16]",
                "map_on": "use_gt=false: reconstruction; use_gt=true: diagnostic ground truth",
                "map_off": "map attention keys masked; TR-Net still runs",
                "action": "raw Isaac-order 12-vector; clip +/-17 and default_joint_pos + 0.25*action outside ONNX",
                "state": "external 10x45 history, delayed two depth frames, h_prop/h_terr 128, tick/reset flags",
                "artifacts": artifacts}
    manifest = output / "contract.json"
    manifest.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return contract


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=M6000_SHA256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export(args.checkpoint, args.output, args.expected_sha256)
    print(json.dumps({"artifacts": result["artifacts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
