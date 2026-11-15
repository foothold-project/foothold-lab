"""Merge completed, resumable W78 mode/case work units into one validated receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MODES = ("eval_gt", "eval_pred", "probe_prop_only")
CASES = ("stairs_fwd", "stairs_side_left", "stairs_side_right", "stairs_back",
         "stairs_fwd_turn_return", "stairs_fwd_back_return", "slope_fwd1.0",
         "flat_fwd1.0", "flat_fwd1.0_heading", "stairs_fwd_stop_back")
LEVELS = (2, 5)
ANGLES = (0, 30, 60, 90)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge(root: Path, checkpoint: Path, output: Path) -> dict:
    root, checkpoint, output = Path(root).resolve(), Path(checkpoint).resolve(strict=True), Path(output)
    merged = None
    for mode in MODES:
        for case in CASES:
            part_path = root / mode / case / "terrain_skill_v2.json"
            part = json.loads(part_path.read_text(encoding="utf-8"))
            if (part.get("schema") != "foothold-terrain-skill-v2/1"
                    or part.get("state") != "done"
                    or part.get("checkpoint_sha256") != sha256(checkpoint)
                    or part.get("checkpoint_iter") != int(checkpoint.stem.split("_")[-1])
                    or part.get("case_selection") != [case]
                    or part.get("mode_selection") != [mode]
                    or set(part.get("modes", {})) != {mode}):
                raise ValueError(f"W78 unit receipt identity/coverage differs: {mode}/{case}")
            if merged is None:
                merged = dict(part)
                merged["modes"] = {name: {} for name in MODES}
                merged["case_selection"] = list(CASES)
                merged["mode_selection"] = list(MODES)
                merged["w78_min_lr_ratio"] = {}
                merged["parts"] = []
            for key in ("checkpoint_sha256", "checkpoint_iter", "eval_seed", "envs", "levels",
                        "start_angles_deg", "dt_s", "dr_off", "curriculum_off"):
                if part.get(key) != merged.get(key):
                    raise ValueError(f"W78 unit configuration differs at {key}")
            rows = part["modes"][mode]
            expected = {f"L{level}_a{angle:03d}_{case}" for level in LEVELS for angle in ANGLES}
            if set(rows) != expected:
                raise ValueError(f"W78 unit has incomplete level/angle coverage: {mode}/{case}")
            for row_key, row in rows.items():
                row = dict(row)
                raw_name = row.get("raw_file")
                raw = (part_path.parent / raw_name).resolve(strict=True)
                if raw.parent != part_path.parent.resolve() or sha256(raw) != row.get("raw_sha256"):
                    raise ValueError(f"W78 unit raw NPZ missing or changed: {mode}/{case}/{row_key}")
                row["raw_file"] = raw.relative_to(root).as_posix()
                merged["modes"][mode][row_key] = row
            merged["parts"].append({"mode": mode, "case": case,
                                    "path": str(part_path), "sha256": sha256(part_path)})
    if merged is None:
        raise ValueError("no W78 work units found")
    for mode in MODES:
        rows = merged["modes"][mode]
        for level in LEVELS:
            for angle in ANGLES:
                for kind in ("pyramid_stairs", "pyramid_stairs_inv"):
                    left = rows[f"L{level}_a{angle:03d}_stairs_side_left"]["by_terrain_kind"][kind]["movement_ratio_median"]
                    right = rows[f"L{level}_a{angle:03d}_stairs_side_right"]["by_terrain_kind"][kind]["movement_ratio_median"]
                    merged["w78_min_lr_ratio"][f"L{level}_a{angle:03d}_{mode}_{kind}"] = {
                        "left": left, "right": right,
                        "min_lr_ratio": min(left, right) if left is not None and right is not None else None,
                        "definition": "minimum of signed left and right movement ratios; no threshold"}
    merged["state"] = "done"
    merged["aggregation"] = "30 independent resumable mode/case units"
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(merged, ensure_ascii=False, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(output)
    return merged


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    merge(args.root, args.checkpoint, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
