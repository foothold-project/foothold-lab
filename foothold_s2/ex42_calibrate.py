"""Five repeat EX-42 evaluations on one E0 mesh; plan by default, Kit only with --execute."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

from foothold_s2.ex42_score import digest
from foothold_s2.eval.ex42_mesh_eval import EVAL_COLS, preflight

SEEDS = (42, 42, 43, 44, 45)
SCORE_GROUPS = ("map64", "stand", "axis_v2")
ITEM_RULES = {
    "survival": (("map64", "alive_at_end"),),
    "tracking_vx_vy": (("map64", "vx_abs_error_median_mps"), ("map64", "vy_abs_error_median_mps")),
    "tracking_wz": (("map64", "wz_abs_error_median_radps"),),
    "command_projection": (("map64", "command_projection_median_m"),),
    "per_foot_contact": (("stand", "per_foot_contact_fraction_median"), ("axis_v2", "duty_by_foot_median")),
    "gait_phase_and_duty": (("axis_v2", "phase_from_FL_cycle_median"), ("axis_v2", "duty_by_foot_median")),
    "foot_drag_m": (("axis_v2", "foot_drag_proxy_m_by_foot_median"),),
    "yaw_integral": (("axis_v2", "yaw_signed_accum_median_rad"),
                     ("axis_v2", "yaw_by_terrain_kind")),
    "W57_spin_survival": (("map64", "alive_at_end"),),
}


def _numeric_leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _numeric_leaves(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _numeric_leaves(child, (*path, str(index)))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError(f"nonfinite calibration value at {'/'.join(path)}")
        yield "/".join(path), float(value)


def _null_leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _null_leaves(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _null_leaves(child, (*path, str(index)))
    elif value is None:
        yield "/".join(path)


def summarize(scores, receipts, mesh_sha256, checkpoint_sha256, *, eval_cols=EVAL_COLS):
    if len(scores) != 5 or len(receipts) != 5:
        raise ValueError("calibration needs exactly five evaluations")
    heads = {row.get("source_git_head") for row in receipts}
    if None in heads or len(heads) != 1:
        raise ValueError("calibration evaluation source HEAD differs")
    for i, (score, receipt) in enumerate(zip(scores, receipts)):
        if (receipt.get("state") != "done" or receipt.get("eval_seed") != SEEDS[i]
                or receipt.get("checkpoint_sha256") != checkpoint_sha256
                or receipt.get("ex42_mesh", {}).get("mesh_sha256") != mesh_sha256
                or receipt.get("ex42_mesh", {}).get("eval_cols") != (None if eval_cols == 76 else eval_cols)
                or score.get("checkpoint_sha256") != checkpoint_sha256
                or score.get("conditions", {}).get("eval_seed") != SEEDS[i]):
            raise ValueError(f"calibration repeat {i} source, mesh, seed, or completion differs")
    groups = [{name: score[name] for name in SCORE_GROUPS} for score in scores]
    metrics = [dict(_numeric_leaves(group)) for group in groups]
    nulls = [set(_null_leaves(group)) for group in groups]
    numeric_keys = set().union(*(set(row) for row in metrics))
    all_keys = numeric_keys | {key for missing in nulls for key in missing
                               if not any(path.startswith(key + "/") for path in numeric_keys)}
    missing_by_repeat = {key: [i for i, row in enumerate(metrics) if key not in row]
                         for key in sorted(all_keys) if any(key not in row for row in metrics)}
    keys = all_keys - set(missing_by_repeat)
    if not keys:
        raise ValueError("calibration has no metric measured in all repetitions")
    widths = {key: {"same_seed_width": abs(metrics[0][key] - metrics[1][key]),
                    "all_seed_width": max(row[key] for row in metrics) - min(row[key] for row in metrics),
                    "values": [row[key] for row in metrics]}
              for key in sorted(keys)}
    items = {}
    for item, rules in ITEM_RULES.items():
        def matches(key):
            if item == "W57_spin_survival" and "/spin" not in key:
                return False
            return any(key.startswith(group + "/") and leaf in key.split("/")
                       for group, leaf in rules)

        selected = {key: row for key, row in widths.items() if matches(key)}
        if not selected:
            missing = sorted(key for key in missing_by_repeat if matches(key))
            if not missing:
                raise ValueError(f"calibration item {item} has no measured numeric metric")
            items[item] = {"state": "missing_in_repeat", "metric_count": 0,
                           "max_same_seed_width": None, "max_all_seed_width": None,
                           "metric_paths": [], "missing_paths": missing}
            continue
        items[item] = {"state": "measured", "metric_count": len(selected),
                       "max_same_seed_width": max(row["same_seed_width"] for row in selected.values()),
                       "max_all_seed_width": max(row["all_seed_width"] for row in selected.values()),
                       "metric_paths": sorted(selected)}
    items["parent_cumulative_drop"] = {"state": "requires_parent_checkpoint", "metric_count": 0}
    items["calibration_repeat_width"] = {"state": "derived_by_item", "metric_count": len(widths),
                                          "item_paths": sorted(ITEM_RULES)}
    return {"format": "foothold-ex42-calibration/1", "state": "measured_unjudged",
            "seeds": list(SEEDS), "mesh_sha256": mesh_sha256,
            "checkpoint_sha256": checkpoint_sha256, "source_git_head": heads.pop(),
            "eval_cols": eval_cols,
            "comparison_scope": "historical_76_reference" if eval_cols == 76 else "a23_parent_matched",
            "same_seed_pair": [0, 1], "stand_terrain": "plane z=0, existing EX-42 stance protocol",
            "item_widths": items, "metric_widths": widths,
            "missing_by_repeat": missing_by_repeat,
            "note": "range is descriptive, no performance PASS threshold inferred"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--mesh-dir", type=Path, required=True)
    parser.add_argument("--expected-mesh-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--summarize-only", action="store_true",
                        help="read five completed evaluations without starting Kit")
    parser.add_argument("--summary-output", type=Path,
                        help="new output JSON for --summarize-only; never overwrite the evaluation folder")
    parser.add_argument("--historical-76-reference", action="store_true",
                        help="label the old 76-column exploratory run; not the A23 parent comparison")
    args = parser.parse_args(argv)
    if args.summarize_only and args.execute:
        parser.error("--summarize-only and --execute are mutually exclusive")
    if args.summarize_only != bool(args.summary_output):
        parser.error("--summarize-only requires --summary-output, and vice versa")
    if args.historical_76_reference and not args.summarize_only:
        parser.error("--historical-76-reference requires --summarize-only")
    if not args.checkpoint.is_file() or digest(args.checkpoint) != args.expected_sha256:
        parser.error("m13000 checkpoint missing or SHA differs")
    mesh = preflight(args.mesh_dir)
    if mesh["mesh_sha256"] != args.expected_mesh_sha256:
        parser.error("E0 combined mesh SHA differs from the operator pin")
    if args.summarize_only:
        scores, receipts = [], []
        eval_cols = 76 if args.historical_76_reference else EVAL_COLS
        for i in range(len(SEEDS)):
            folder = args.out / f"repeat_{i:02d}"
            score_path, receipt_path = folder / "ex42_score.json", folder / "eval_receipt.json"
            map_path = folder / "map64" / "map_modes.json"
            if not all(path.is_file() for path in (score_path, receipt_path, map_path)):
                raise ValueError(f"calibration repeat {i} is incomplete")
            cell = json.loads(map_path.read_text(encoding="utf-8"))
            if cell.get("fixed_terrain", {}).get("cols") != eval_cols:
                raise ValueError(f"calibration repeat {i} fixed terrain columns differ")
            scores.append(json.loads(score_path.read_text(encoding="utf-8")))
            receipts.append(json.loads(receipt_path.read_text(encoding="utf-8")))
        result = summarize(scores, receipts, mesh["mesh_sha256"], args.expected_sha256,
                           eval_cols=eval_cols)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"state": result["state"], "calibration": str(args.summary_output),
                          "comparison_scope": result["comparison_scope"]}))
        return 0
    commands = [[sys.executable, "-m", "foothold_s2.ex42_eval_once", "--checkpoint", str(args.checkpoint),
                 "--expected-sha256", args.expected_sha256, "--mesh-dir", str(args.mesh_dir),
                 "--eval-seed", str(seed), "--out", str(args.out / f"repeat_{i:02d}"),
                 "--device", args.device, "--execute"] for i, seed in enumerate(SEEDS)]
    if not args.execute:
        print(json.dumps({"state": "plan", "mesh_sha256": mesh["mesh_sha256"],
                          "seeds": list(SEEDS), "commands": commands}))
        return 0
    if args.out.exists():
        raise ValueError("calibration needs a fresh output directory")
    args.out.mkdir(parents=True)
    scores, receipts = [], []
    for cmd in commands:
        subprocess.run(cmd, check=True)
        folder = Path(cmd[cmd.index("--out") + 1])
        receipts.append(json.loads((folder / "eval_receipt.json").read_text(encoding="utf-8")))
        scores.append(json.loads((folder / "ex42_score.json").read_text(encoding="utf-8")))
    result = summarize(scores, receipts, mesh["mesh_sha256"], args.expected_sha256)
    (args.out / "calibration.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"state": result["state"], "calibration": str(args.out / "calibration.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
