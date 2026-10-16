"""Evaluation-only multi-conversion evidence for the unchanged v3 USD wrapper."""
from __future__ import annotations

import json
from pathlib import Path

from s2_eval_cpu import sha


class UsdEvalHold(RuntimeError):
    pass


def _inside(path, root):
    value = Path(path).resolve()
    return root in value.parents


def evidence(usd_root, asset_path, robot_refs, *, max_entries):
    root = Path(usd_root).resolve(strict=True)
    if type(max_entries) is not int or max_entries < 1:
        raise UsdEvalHold("conversion_cap")
    state_path, assigned_path = root / "isolate_state.json", root / "assigned.jsonl"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in assigned_path.read_text(encoding="utf-8").splitlines() if line]
    count = state.get("conversions")
    if (state.get("version") != "v3" or state.get("expect_conversions") != "any" or
        Path(state.get("root", "")).resolve() != root or
        type(count) is not int or not 1 <= count <= max_entries or len(rows) != count or
        state.get("blocked") != [] or state.get("warnings") != []):
        raise UsdEvalHold("usd_isolation_state_or_count")
    outputs = []
    for row in rows:
        if (row.get("kind") not in ("assigned", "explicit_inside") or
            Path(row.get("asset_path", "")).resolve() != Path(asset_path).resolve() or
            not _inside(row.get("usd_dir", ""), root)):
            raise UsdEvalHold("usd_assignment_asset_or_root")
        folder = Path(row["usd_dir"])
        files = sorted(p for p in folder.rglob("*.usd*") if p.is_file())
        if not files:
            raise UsdEvalHold("usd_output_missing")
        outputs.append({"assigned": row, "files": [{"path": str(p), "sha256": sha(p)} for p in files]})
    if not robot_refs:
        raise UsdEvalHold("robot_reference_missing")
    refs = []
    for item in sorted(set(robot_refs)):
        if not _inside(item, root) or not Path(item).is_file():
            raise UsdEvalHold("robot_reference_outside_or_missing")
        refs.append({"path": str(Path(item).resolve()), "sha256": sha(item)})
    return {"state_sha256": sha(state_path), "assigned_sha256": sha(assigned_path),
            "converter_entries": count, "cap": max_entries, "outputs": outputs,
            "robot_references": refs, "environment_created": True,
            "conversion_counter_meaning": "constructor_entries_not_success"}
