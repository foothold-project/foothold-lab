"""CPU gate for using split W78 evidence in EX-42.

The gate reads receipts only. It cannot enqueue work or start Kit. A different
source or an unmeasured numeric difference stays HOLD.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


IDENTITY = ("checkpoint_sha256", "checkpoint_iter", "eval_seed", "envs",
            "levels", "start_angles_deg", "dt_s", "dr_off", "curriculum_off")
ROW_IDENTITY = ("case", "requested_kinds", "terrain_assignment_sha256",
                "terrain_tiles", "phase_steps")


def _numbers(value: Any, prefix: str = "") -> dict[str, float]:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if key in ("raw_file", "raw_sha256"):
                continue
            result.update(_numbers(child, f"{prefix}/{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, child in enumerate(value):
            result.update(_numbers(child, f"{prefix}/{index}"))
        return result
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError(f"nonfinite W78 number at {prefix}")
        return {prefix: float(value)}
    return {}


def _source(receipt: dict) -> dict:
    source = receipt.get("run_identity", {})
    if not isinstance(source, dict) or not source.get("code_head"):
        raise ValueError("W78 run_identity.code_head missing")
    hashes = receipt.get("source_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("W78 source_sha256 missing")
    return {"code_head": source["code_head"], "source_sha256": hashes}


def _row(receipt: dict, mode: str, key: str) -> dict:
    value = receipt.get("modes", {}).get(mode, {}).get(key)
    if not isinstance(value, dict):
        raise ValueError(f"W78 row missing: {mode}/{key}")
    return value


def _denominators(row: dict):
    """Return the sample basis for each recorded kind and env, or None if incomplete."""
    per_env, by_kind = row.get("per_env"), row.get("by_terrain_kind")
    if not isinstance(per_env, list) or not isinstance(by_kind, dict):
        return None
    try:
        envs = [(sample["env"], sample["kind"], sample["level"],
                 sample["alive_samples"], sample["drag_den"],
                 sample["closed_swing_count"], sample["open_swing_count"],
                 [(phase["alive_samples"], phase["scheduled_samples"])
                  for phase in sample["movement_phases"]]) for sample in per_env]
        kinds = {kind: (sample["env_count"], sample["phase_movement_valid_envs"],
                        sample["drag_den"], sample["closed_swing_count"],
                        sample["open_swing_count"])
                 for kind, sample in by_kind.items()}
        tiles = [(tile["env"], tile["kind"], tile["level"])
                 for tile in row["terrain_tiles"]]
    except (KeyError, TypeError, ValueError):
        return None
    if sorted((env, kind, level) for env, kind, level, *_ in envs) != sorted(tiles):
        return None
    if set(kinds) != {kind for _, kind, _ in tiles}:
        return None
    return {"per_env": envs, "by_kind": kinds}


def compare_split(full: dict, units: list[dict], *, repeats: list[dict] = ()) -> dict:
    """Accept only exact values or differences bounded by same-code repeats.

    The repeated full receipts must be separately measured with the same code,
    checkpoint and cell coverage. No default tolerance is invented here.
    """
    if full.get("state") != "done" or not units:
        raise ValueError("completed full and split W78 receipts required")
    source = _source(full)
    differences = []
    paired_rows = []
    for unit in units:
        if unit.get("state") != "done" or _source(unit) != source:
            return {"state": "HOLD", "reason": "source_or_completion_differs"}
        if any(field not in unit or field not in full or unit[field] != full[field]
               for field in IDENTITY):
            return {"state": "HOLD", "reason": "sample_contract_differs"}
        modes, cases = unit.get("mode_selection"), unit.get("case_selection")
        if not isinstance(modes, list) or not isinstance(cases, list) or len(modes) != 1 or len(cases) != 1:
            raise ValueError("one mode and one case per split receipt required")
        mode, case = modes[0], cases[0]
        keys = [key for key in unit.get("modes", {}).get(mode, {}) if key.endswith("_" + case)]
        if len(keys) != len(full.get("levels", [])) * len(full.get("start_angles_deg", [])):
            return {"state": "HOLD", "reason": "split_coverage_differs"}
        for key in keys:
            full_row, unit_row = _row(full, mode, key), _row(unit, mode, key)
            if any(field not in full_row or field not in unit_row
                   or full_row[field] != unit_row[field] for field in ROW_IDENTITY):
                return {"state": "HOLD", "reason": "terrain_or_phase_identity_differs"}
            paired_rows.append((mode, key, full_row, unit_row))
            left, right = _numbers(full_row), _numbers(unit_row)
            if left.keys() != right.keys():
                return {"state": "HOLD", "reason": "numeric_fields_differ"}
            differences.extend({"cell": f"{mode}/{key}{field}", "full": value,
                                "split": right[field], "abs_difference": abs(value - right[field])}
                               for field, value in left.items() if value != right[field])
    for repeat in repeats:
        if repeat.get("state") != "done" or _source(repeat) != source or any(
                field not in repeat or field not in full or repeat[field] != full[field]
                for field in IDENTITY):
            return {"state": "HOLD", "reason": "repeat_identity_differs"}
        for mode, key, full_row, unit_row in paired_rows:
            repeat_row = _row(repeat, mode, key)
            if any(field not in repeat_row or repeat_row[field] != full_row[field]
                   for field in ROW_IDENTITY):
                return {"state": "HOLD", "reason": "repeat_terrain_or_phase_differs"}
            full_den, unit_den, repeat_den = (_denominators(row)
                                               for row in (full_row, unit_row, repeat_row))
            if any(value is None for value in (full_den, unit_den, repeat_den)):
                return {"state": "HOLD", "reason": "repeat_denominator_missing"}
            if full_den != unit_den or full_den != repeat_den:
                return {"state": "HOLD", "reason": "repeat_denominator_differs"}
    if not differences:
        return {"state": "PASS", "numeric_differences": 0, "basis": "exact"}
    if len(repeats) < 2:
        return {"state": "HOLD", "reason": "repeat_width_missing",
                "numeric_differences": len(differences)}
    outside = []
    for difference in differences:
        mode, rest = difference["cell"].split("/", 1)
        key, *field_parts = rest.split("/")
        field = "/" + "/".join(field_parts)
        values = [_numbers(_row(row, mode, key)).get(field) for row in (full, *repeats)]
        if any(value is None for value in values):
            return {"state": "HOLD", "reason": "repeat_field_missing"}
        width = max(values) - min(values)
        if difference["abs_difference"] > width:
            outside.append({**difference, "measured_width": width})
    return {"state": "HOLD" if outside else "PASS",
            "reason": "beyond_repeat_width" if outside else "within_measured_repeat_width",
            "numeric_differences": len(differences), "outside_count": len(outside),
            "outside_examples": outside[:8], "repeat_count": len(repeats)}


def unit_queue_admission(queue: dict, unit_id: int) -> dict:
    """Check that the dispatcher can yield a split unit to GPU1 P1 work."""
    rows = queue.get("items")
    if not isinstance(rows, list):
        raise ValueError("queue items missing")
    unit = next((row for row in rows if row.get("id") == unit_id), None)
    if (not unit or unit.get("gpu") != 1 or unit.get("priority") not in (2, 3)
            or unit.get("kind") != "eval"):
        raise ValueError("W78 unit must be GPU1 evaluation below P1")
    if unit.get("state") not in ("대기", "실행"):
        raise ValueError("W78 queue item is not pending or running")
    higher = [row.get("id") for row in rows if row.get("gpu") == 1
              and row.get("priority") == 1 and row.get("state") in ("대기", "실행")]
    return {"state": "yield_to_P1" if higher else "eligible", "unit_id": unit_id,
            "higher_priority_ids": higher}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only EX42 W78 split evidence gate")
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument("--unit", type=Path, action="append", required=True)
    parser.add_argument("--repeat", type=Path, action="append", default=[])
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--unit-id", type=int)
    args = parser.parse_args(argv)
    read = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
    result = compare_split(read(args.full), [read(path) for path in args.unit],
                           repeats=[read(path) for path in args.repeat])
    if args.queue is not None or args.unit_id is not None:
        if args.queue is None or args.unit_id is None:
            parser.error("--queue and --unit-id must be paired")
        result["queue"] = unit_queue_admission(read(args.queue), args.unit_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
