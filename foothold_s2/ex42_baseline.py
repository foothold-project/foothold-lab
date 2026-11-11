"""Build the pinned E0 parent baseline from five A23 calibration measurements."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(calibration: dict, calibration_sha256: str) -> dict:
    if (calibration.get("format") != "foothold-ex42-calibration/1" or
            calibration.get("state") != "measured_unjudged" or
            calibration.get("comparison_scope") != "a23_parent_matched" or
            calibration.get("eval_cols") != 23 or
            calibration.get("seeds") != [42, 42, 43, 44, 45]):
        raise ValueError("E0 baseline requires the five completed A23 parent measurements")
    metrics = {}
    for path, row in sorted(calibration["metric_widths"].items()):
        values = row["values"]
        if len(values) != 5 or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError(f"E0 baseline has incomplete or nonfinite values: {path}")
        width = row["all_seed_width"]
        if type(width) not in (int, float) or not math.isfinite(width) or width < 0:
            raise ValueError(f"E0 baseline has invalid repeat width: {path}")
        if not math.isclose(width, max(values) - min(values), rel_tol=0, abs_tol=1e-9):
            raise ValueError(f"E0 baseline repeat width differs from five values: {path}")
        base = float(median(values))
        item = {"parent_median": base, "repeat_width": width}
        if "/foot_drag_proxy_m_by_foot_median/" in path:
            item["rise_limit_m"] = max(0.25 * base, 2 * width)
        metrics[path] = item
    items = {}
    for name, row in calibration["item_widths"].items():
        if row["state"] == "measured":
            paths = row["metric_paths"]
            if len(paths) != row["metric_count"] or any(path not in metrics for path in paths):
                raise ValueError(f"E0 baseline item coverage differs: {name}")
            items[name] = {"state": "measured", "metric_paths": paths}
        else:
            items[name] = {"state": row["state"], "metric_paths": []}
    missing = calibration["missing_by_repeat"]
    if any(path in metrics or indices != [0, 1, 2, 3, 4] for path, indices in missing.items()):
        raise ValueError("E0 baseline all-null inventory differs")
    return {"format": "foothold-ex42-e0-baseline/1", "calibration_sha256": calibration_sha256,
            "checkpoint_sha256": calibration["checkpoint_sha256"],
            "mesh_sha256": calibration["mesh_sha256"], "source_git_head": calibration["source_git_head"],
            "comparison_scope": calibration["comparison_scope"], "seeds": calibration["seeds"],
            "eval_cols": calibration["eval_cols"], "metrics": metrics, "items": items,
            "all_null_metrics": missing}


def serialized(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    actual = sha256(args.calibration)
    if actual != args.expected_sha256:
        raise ValueError("E0 calibration SHA differs")
    result = build(json.loads(args.calibration.read_text(encoding="utf-8")), actual)
    if args.out.exists():
        raise ValueError("E0 baseline output already exists")
    args.out.write_text(serialized(result), encoding="utf-8")


if __name__ == "__main__":
    main()
