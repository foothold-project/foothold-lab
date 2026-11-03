"""Verify real Isaac m6000 traces with ORT CPU and assemble start-demo handoff.

The capture source is immutable.  The destination must not exist; a partial
comparison never publishes a parity claim or a handoff checksum list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import onnxruntime as ort

from foothold_s2.deploy.capture_ex40_real20 import CASES, INPUTS, MODES, OUTPUTS, EXPECTED_SHA


TOLERANCE = 1e-4
MODE_ALIAS = {"eval_pred": "reconstruction", "probe_prop_only": "off", "eval_gt": "gt"}
ONNX_NAMES = {"map_on": "start-demo_map_on.onnx", "map_off": "start-demo_map_off.onnx"}
SHAS = {"map_on": "81c7e079516058ee6243f6edd11efa8f0da239c6cc86fbca791bda5bcd82f110",
        "map_off": "5d1b7bf39aa0d9fb8ae33bf33dad82902165d53679ccd7ec5df727a0b70fe037"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_trace(path: Path) -> list[dict[str, np.ndarray]]:
    rows = []
    with np.load(path, allow_pickle=False) as data:
        expected = {f"step{k:02d}_{name}" for k in range(20) for name in (*INPUTS, *OUTPUTS)}
        if set(data.files) != expected:
            raise AssertionError(f"real trace fields differ: {path}")
        for k in range(20):
            row = {name: data[f"step{k:02d}_{name}"].copy() for name in (*INPUTS, *OUTPUTS)}
            if not all(np.isfinite(value).all() for value in row.values()):
                raise AssertionError(f"nonfinite real trace: {path} step{k}")
            rows.append(row)
    return rows


def compare_trace(session, rows: list[dict], tolerance: float = TOLERANCE) -> dict:
    """Run 20 steps, replacing each recorded hidden input with ORT's prior output."""
    if len(rows) != 20:
        raise AssertionError("real trace must have 20 steps")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("invalid tolerance")
    errors = {name: 0.0 for name in OUTPUTS}
    hidden = None
    for k, row in enumerate(rows):
        feed = {name: row[name].copy() for name in INPUTS}
        if k:
            feed["h_prop"], feed["h_terr"] = hidden
        outputs = session.run(list(OUTPUTS), feed)
        hidden = outputs[1], outputs[2]
        for name, got in zip(OUTPUTS, outputs):
            want = row[name]
            if got.shape != want.shape or not np.isfinite(got).all() or not np.isfinite(want).all():
                raise AssertionError(f"step{k} {name} shape or finite mismatch")
            error = float(np.max(np.abs(got - want)))
            errors[name] = max(errors[name], error)
            if error > tolerance:
                raise AssertionError(f"step{k} {name} max_abs={error} > {tolerance}")
    return errors


def compact_json_row(row: dict, names: tuple[str, ...]) -> dict:
    return {name: row[name].reshape(-1).tolist() for name in names}


def package(capture_dir: Path, source_onnx: Path, source_contract: Path,
            output: Path, contract_md: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    capture = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    if capture.get("format") != "ex40-real20-capture/1" or capture.get("checkpoint_sha256") != EXPECTED_SHA:
        raise AssertionError("capture identity differs")
    src_contract = json.loads(source_contract.read_text(encoding="utf-8"))
    if (src_contract.get("checkpoint_sha256") != EXPECTED_SHA
            or src_contract.get("inputs") != list(INPUTS)
            or src_contract.get("outputs") != list(OUTPUTS)):
        raise AssertionError("source ONNX contract differs")
    sessions = {}
    for graph in ONNX_NAMES:
        source = source_onnx / f"foothold-start-m6000_{graph}.onnx"
        if sha256(source) != SHAS[graph]:
            raise AssertionError(f"{graph} ONNX SHA differs")
        session = ort.InferenceSession(str(source), providers=["CPUExecutionProvider"])
        if ([item.name for item in session.get_inputs()] != list(INPUTS)
                or [item.name for item in session.get_outputs()] != list(OUTPUTS)):
            raise AssertionError("ONNX names or order differ")
        sessions[graph] = session
    results = {}
    traces = {}
    for case, level, col in CASES:
        for mode in MODES:
            key = f"{case}/{mode}"
            record = capture.get("cases", {}).get(key)
            path = capture_dir / f"{case}_{mode}.npz"
            if record is None or Path(record["path"]).resolve() != path.resolve() or sha256(path) != record["sha256"]:
                raise AssertionError(f"missing or changed capture: {key}")
            if (record["level"], record["terrain_kind"]) != (level, capture["terrain_columns"][col]):
                raise AssertionError(f"terrain mismatch: {key}")
            if record["use_gt_steps"] != (20 if mode == "eval_gt" else 0):
                raise AssertionError(f"map selection mismatch: {key}")
            rows = load_trace(path)
            if not bool(rows[0]["first_after_reset"][0]):
                raise AssertionError(f"missing first flag: {key}")
            graph = "map_off" if mode == "probe_prop_only" else "map_on"
            results[key] = compare_trace(sessions[graph], rows)
            traces[key] = rows
    output.mkdir(parents=True)
    for graph, name in ONNX_NAMES.items():
        shutil.copyfile(source_onnx / f"foothold-start-m6000_{graph}.onnx", output / name)
        if sha256(output / name) != SHAS[graph]:
            raise AssertionError("copied ONNX changed")
    shutil.copyfile(contract_md, output / "CONTRACT.md")
    flat_arrays = {}
    for mode in MODES:
        alias = MODE_ALIAS[mode]
        rows = traces[f"flat/{mode}"]
        graph = "map_off" if mode == "probe_prop_only" else "map_on"
        payload = {"format": "start-demo-test-vectors/1", "model": "start-demo",
                   "checkpoint_sha256": EXPECTED_SHA,
                   "onnx": {ONNX_NAMES[graph]: SHAS[graph]}, "map_mode": alias,
                   "steps": 20, "tolerance": TOLERANCE, "state_feedback": True,
                   "inputs": [compact_json_row(row, INPUTS) for row in rows],
                   "expected": [compact_json_row(row, OUTPUTS) for row in rows],
                   "input_shapes": {item.name: item.shape for item in sessions[graph].get_inputs()},
                   "input_types": {item.name: item.type for item in sessions[graph].get_inputs()}}
        (output / f"test_vectors_flat20_{alias}.json").write_text(
            json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        arrays = {f"step{k:02d}_{name}": row[name] for k, row in enumerate(rows)
                  for name in (*INPUTS, *OUTPUTS)}
        np.savez_compressed(output / f"test_vectors_flat20_{alias}.npz", **arrays)
        flat_arrays.update({f"{alias}_{key}": value for key, value in arrays.items()})
    # README names a plain default vector file; the explicit three-mode files
    # remain the authoritative sets for map-mode-specific app tests.
    shutil.copyfile(output / "test_vectors_flat20_reconstruction.json",
                    output / "test_vectors_flat20.json")
    np.savez_compressed(output / "test_vectors_flat20.npz", **flat_arrays)
    parity = {"format": "start-demo-parity/1", "checkpoint_sha256": EXPECTED_SHA,
              "synthetic": json.loads((source_onnx / "comparison.json").read_text(encoding="utf-8")),
              "real": {"source_capture": str(capture_dir / "capture.json"),
                       "capture_sha256": sha256(capture_dir / "capture.json"),
                       "cases": results, "steps_per_case": 20,
                       "state_feedback": True,
                       "max_abs": max(v for row in results.values() for v in row.values()),
                       "tolerance": TOLERANCE, "passed": True}}
    (output / "parity.json").write_text(json.dumps(parity, indent=2) + "\n", encoding="utf-8")
    contract = dict(src_contract)
    contract["format"] = "start-demo-onnx/1"
    contract["model"] = "start-demo"
    contract["artifacts"] = {key: {"name": name, "sha256": SHAS[key],
                                   "bytes": (output / name).stat().st_size}
                             for key, name in ONNX_NAMES.items()}
    contract["input_shapes"] = {item.name: item.shape for item in sessions["map_on"].get_inputs()}
    contract["input_types"] = {item.name: item.type for item in sessions["map_on"].get_inputs()}
    contract["test_vectors"] = {alias: f"test_vectors_flat20_{alias}.json"
                                for alias in MODE_ALIAS.values()}
    contract["default_test_vectors"] = "test_vectors_flat20.json"
    (output / "contract.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    lines = [f"{sha256(path)}  {path.name}" for path in sorted(output.iterdir()) if path.name != "SHA256SUMS"]
    (output / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return parity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--source-onnx", type=Path, required=True)
    parser.add_argument("--source-contract", type=Path, required=True)
    parser.add_argument("--contract-md", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = package(args.capture_dir, args.source_onnx, args.source_contract,
                     args.output, args.contract_md)
    print(json.dumps({"real_max_abs": result["real"]["max_abs"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
