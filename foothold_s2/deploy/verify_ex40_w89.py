"""Compare m6000 PyTorch and ONNX Runtime on identical CPU inputs.

Run fixtures with isaac311 (torch), then compare in a separate base Python
process (onnxruntime). Neither phase needs Isaac Sim or a GPU.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

INPUT_NAMES = ("obs45", "hist", "depth2", "h_prop", "h_terr", "depth_tick",
               "first_after_reset", "use_gt", "gt_map")
OUTPUT_NAMES = ("action", "h_prop_next", "h_terr_next", "recon_map")


def make_fixtures(checkpoint: Path, expected_sha256: str, out: Path) -> int:
    import numpy as np
    import torch

    from foothold_s2.deploy.export_ex40_w89 import (PerceptionActor, example_inputs,
                                                      load_components)

    torch.set_num_threads(1)
    torch.backends.mha.set_fastpath_enabled(False)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for mode in ("map_on", "map_off"):
        perception, actor = load_components(checkpoint, expected_sha256)
        net = PerceptionActor(perception, actor, map_off=(mode == "map_off")).eval()
        for case in ("first", "carry_no_depth", "carry_depth_gt"):
            inputs = list(example_inputs())
            inputs[6] = torch.tensor([case == "first"])
            inputs[5] = torch.tensor([case != "carry_no_depth"])
            inputs[7] = torch.tensor([case == "carry_depth_gt"])
            if case == "first":
                inputs[1] = inputs[0][:, None, :].expand(-1, 10, -1).clone()
                inputs[3] = torch.zeros_like(inputs[3])
                inputs[4] = torch.zeros_like(inputs[4])
            with torch.no_grad():
                outputs = net(*inputs)
            record = {"input_" + name: value.detach().cpu().numpy()
                      for name, value in zip(INPUT_NAMES, inputs)}
            record.update({"output_" + name: value.detach().cpu().numpy()
                           for name, value in zip(OUTPUT_NAMES, outputs)})
            path = out / f"fixture_{mode}_{case}.npz"
            if path.exists():
                raise FileExistsError(path)
            np.savez_compressed(path, **record)
            count += 1
        sequence = {}
        h_prop = torch.zeros(1, 128)
        h_terr = torch.zeros(1, 128)
        for step in range(3):
            inputs = list(example_inputs())
            inputs[0] = inputs[0] + step * 0.1
            inputs[1] = inputs[0][:, None, :].expand(-1, 10, -1).clone()
            inputs[3], inputs[4] = h_prop, h_terr
            inputs[5] = torch.tensor([step % 2 == 0])
            inputs[6] = torch.tensor([step == 0])
            inputs[7] = torch.tensor([False])
            with torch.no_grad():
                outputs = net(*inputs)
            sequence.update({f"step{step}_input_{name}": value.detach().cpu().numpy()
                             for name, value in zip(INPUT_NAMES, inputs)})
            sequence.update({f"step{step}_output_{name}": value.detach().cpu().numpy()
                             for name, value in zip(OUTPUT_NAMES, outputs)})
            h_prop, h_terr = outputs[1], outputs[2]
        np.savez_compressed(out / f"fixture_{mode}_sequence.npz", **sequence)
        count += 1
    return count


def compare(onnx_dir: Path, fixtures: Path, tolerance: float) -> dict:
    import numpy as np
    import onnxruntime as ort

    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("comparison tolerance must be positive and finite")

    contract = json.loads((onnx_dir / "contract.json").read_text(encoding="utf-8"))
    if contract["inputs"] != list(INPUT_NAMES) or contract["outputs"] != list(OUTPUT_NAMES):
        raise ValueError("W89 ONNX contract names differ")
    results = {}
    for mode in ("map_on", "map_off"):
        session = ort.InferenceSession(str(onnx_dir / f"ex40_m6000_{mode}.onnx"),
                                       providers=["CPUExecutionProvider"])
        if ([item.name for item in session.get_inputs()] != list(INPUT_NAMES)
                or [item.name for item in session.get_outputs()] != list(OUTPUT_NAMES)):
            raise ValueError("W89 ONNX graph interface differs")
        for case in ("first", "carry_no_depth", "carry_depth_gt"):
            path = fixtures / f"fixture_{mode}_{case}.npz"
            with np.load(path, allow_pickle=False) as data:
                feed = {name: data["input_" + name] for name in INPUT_NAMES}
                outputs = session.run(list(OUTPUT_NAMES), feed)
                diffs = {}
                for name, value in zip(OUTPUT_NAMES, outputs):
                    wanted = data["output_" + name]
                    if (value.shape != wanted.shape or not np.isfinite(value).all()
                            or not np.isfinite(wanted).all()):
                        raise AssertionError(f"{mode}/{case}/{name} shape or finite mismatch")
                    diff = float(np.max(np.abs(value - wanted)))
                    if not math.isfinite(diff) or diff > tolerance:
                        raise AssertionError(f"{mode}/{case}/{name} max_abs={diff} > {tolerance}")
                    diffs[name] = diff
                results[f"{mode}/{case}"] = diffs
        with np.load(fixtures / f"fixture_{mode}_sequence.npz", allow_pickle=False) as data:
            h_prop = h_terr = None
            for step in range(3):
                feed = {name: data[f"step{step}_input_{name}"] for name in INPUT_NAMES}
                if step:
                    feed["h_prop"], feed["h_terr"] = h_prop, h_terr
                outputs = session.run(list(OUTPUT_NAMES), feed)
                h_prop, h_terr = outputs[1], outputs[2]
                diffs = {}
                for name, value in zip(OUTPUT_NAMES, outputs):
                    wanted = data[f"step{step}_output_{name}"]
                    if (value.shape != wanted.shape or not np.isfinite(value).all()
                            or not np.isfinite(wanted).all()):
                        raise AssertionError(f"{mode}/sequence/{step}/{name} shape or finite mismatch")
                    diff = float(np.max(np.abs(value - wanted)))
                    if not math.isfinite(diff) or diff > tolerance:
                        raise AssertionError(f"{mode}/sequence/{step}/{name} max_abs={diff}")
                    diffs[name] = diff
                results[f"{mode}/sequence/{step}"] = diffs
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fixtures = sub.add_parser("fixtures")
    fixtures.add_argument("--checkpoint", type=Path, required=True)
    fixtures.add_argument("--expected-sha256", required=True)
    fixtures.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("compare")
    check.add_argument("--onnx-dir", type=Path, required=True)
    check.add_argument("--fixtures", type=Path, required=True)
    check.add_argument("--tolerance", type=float, default=3e-5)
    check.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "fixtures":
        print(json.dumps({"fixtures": make_fixtures(args.checkpoint, args.expected_sha256, args.out)}))
    else:
        result = compare(args.onnx_dir, args.fixtures, args.tolerance)
        payload = {"format": "foothold-ex40-w89-cpu-comparison/1",
                   "tolerance_max_abs": args.tolerance, "cases": result,
                   "max_abs": max(value for case in result.values() for value in case.values())}
        if args.report is not None:
            if args.report.exists():
                raise FileExistsError(args.report)
            args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
