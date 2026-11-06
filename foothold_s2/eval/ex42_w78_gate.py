"""CPU gate for using split W78 evidence in EX-42.

The gate reads receipts only. It cannot enqueue work or start Kit. A different
source or an unmeasured numeric difference stays HOLD.
"""

from __future__ import annotations

import math
from typing import Any


IDENTITY = ("checkpoint_sha256", "checkpoint_iter", "eval_seed", "envs",
            "levels", "start_angles_deg", "dt_s", "dr_off", "curriculum_off")


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


def compare_split(full: dict, units: list[dict], *, repeats: list[dict] = ()) -> dict:
    """Accept only exact values or differences bounded by same-code repeats.

    The repeated full receipts must be separately measured with the same code,
    checkpoint and cell coverage. No default tolerance is invented here.
    """
    if full.get("state") != "done" or not units:
        raise ValueError("completed full and split W78 receipts required")
    source = _source(full)
    differences = []
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
            left, right = _numbers(_row(full, mode, key)), _numbers(_row(unit, mode, key))
            if left.keys() != right.keys():
                return {"state": "HOLD", "reason": "numeric_fields_differ"}
            differences.extend({"cell": f"{mode}/{key}{field}", "full": value,
                                "split": right[field], "abs_difference": abs(value - right[field])}
                               for field, value in left.items() if value != right[field])
    if not differences:
        return {"state": "PASS", "numeric_differences": 0, "basis": "exact"}
    if len(repeats) < 2:
        return {"state": "HOLD", "reason": "repeat_width_missing",
                "numeric_differences": len(differences)}
    for repeat in repeats:
        if repeat.get("state") != "done" or _source(repeat) != source or any(
                field not in repeat or field not in full or repeat[field] != full[field]
                for field in IDENTITY):
            return {"state": "HOLD", "reason": "repeat_identity_differs"}
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
    if not unit or unit.get("gpu") != 1 or unit.get("priority") != 2 or unit.get("kind") != "eval":
        raise ValueError("W78 unit must be GPU1 P2 evaluation")
    if unit.get("state") not in ("대기", "실행"):
        raise ValueError("W78 queue item is not pending or running")
    higher = [row.get("id") for row in rows if row.get("gpu") == 1
              and row.get("priority") == 1 and row.get("state") in ("대기", "실행")]
    return {"state": "yield_to_P1" if higher else "eligible", "unit_id": unit_id,
            "higher_priority_ids": higher}
