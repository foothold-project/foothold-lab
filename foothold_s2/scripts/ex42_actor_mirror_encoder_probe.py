"""CPU probe of map-flip sensitivity inside the EX-42 actor mirror mask.

The 32 maps are synthetic height fields with range below 2 cm. This tests a
trained encoder's sensitivity; it is not a measurement of live terrain maps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from foothold_s2.models.start_perception import PerceptionCfg, StartPerception
from foothold_s2.runners.ex42_actor_mirror import flat_map_mask


def measure(checkpoint: Path, *, samples: int = 32, seed: int = 23, span_m: float = 0.019) -> dict:
    if samples < 1 or not 0 < span_m < 0.02:
        raise ValueError("samples must be positive and span_m must lie strictly between 0 and 0.02")
    checkpoint = checkpoint.resolve(strict=True)
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = StartPerception(PerceptionCfg()).eval()
    model.load_state_dict(state["perception_state_dict"], strict=True)
    generator = torch.Generator().manual_seed(seed)
    hprop = torch.randn(samples, 128, generator=generator) * 0.1
    maps = torch.rand(samples, 32, 16, generator=generator) * span_m
    if not bool(flat_map_mask(maps).all()):
        raise ValueError("probe map fell outside the actor mirror mask")
    with torch.inference_mode():
        original = model.ie.estimate(hprop, maps)
        reflected = model.ie.estimate(hprop, maps.flip(-1))
    components = {}
    for key in ("v", "zf", "zb"):
        delta = (original[key] - reflected[key]).abs()
        rms = original[key].square().mean().sqrt()
        components[key] = {"max_abs_delta": float(delta.max()), "rms": float(rms),
                           "max_delta_over_rms": float(delta.max() / rms)}
    return {"format": "ex42-actor-mirror-encoder-probe/1", "checkpoint": str(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "synthetic_maps": True, "samples": samples, "seed": seed, "span_m": span_m,
            "masked_samples": int(flat_map_mask(maps).sum()), "components": components}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--span-m", type=float, default=0.019)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = measure(args.checkpoint, samples=args.samples, seed=args.seed, span_m=args.span_m)
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
