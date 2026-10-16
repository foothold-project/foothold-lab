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


def evidence(usd_root, asset_path, robot_refs, *, max_entries, case_rows=None):
    root = Path(usd_root).resolve(strict=True)
    if type(max_entries) is not int or max_entries < 1:
        raise UsdEvalHold("conversion_cap")
    state_path, assigned_path = root / "isolate_state.json", root / "assigned.jsonl"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in assigned_path.read_text(encoding="utf-8").splitlines() if line]
    count = state.get("conversions")
    successes = state.get("conversion_successes")
    if (state.get("version") != "v3" or state.get("expect_conversions") != "any" or
        Path(state.get("root", "")).resolve() != root or
        type(count) is not int or not 1 <= count <= max_entries or len(rows) != count or
        type(successes) is not int or not 0 <= successes <= count or
        state.get("conversion_cap") != max_entries or
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
    links = []
    if case_rows is not None:
        by_arm = {r.get("case_id", "") + ":" + r.get("arm", ""): r for r in case_rows
                  if r.get("executed") and not r.get("missing_reason")}
        for output in outputs:
            row = output["assigned"]
            case_arm = row.get("case_arm")
            if case_arm not in by_arm or type(row.get("n")) is not int:
                raise UsdEvalHold("converter_case_arm_missing")
            actual_refs = [str(Path(p).resolve()) for p in by_arm[case_arm]["usd_robot_references"]]
            output_paths = {item["path"] for item in output["files"]}
            if not output_paths.intersection(actual_refs):
                raise UsdEvalHold("converter_usd_robot_reference_mismatch")
            links.append({"case_arm": case_arm, "entry": row["n"],
                          "generated_usd": sorted(output_paths), "robot_references": actual_refs})
    return {"state_sha256": sha(state_path), "assigned_sha256": sha(assigned_path),
            "converter_entries": count, "converter_successes": successes,
            "cap": max_entries, "outputs": outputs, "case_arm_links": links,
            "robot_references": refs, "environment_created": True,
            "conversion_counter_meaning": "constructor_entries_not_success"}
