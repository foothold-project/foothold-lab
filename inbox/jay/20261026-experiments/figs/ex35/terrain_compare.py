"""CPU aggregation of paired EX-35 terrain arrays, with source identity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


PARENT = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/sb10_eval_x27j/m1500")
CHILD = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval_x27k/m2000")
EARLIER_CHILD = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval_x27j/m2000")
LEVEL_DIRS = {"L0~2": "map64", "L6": "hardlevel/L6", "L9": "hardlevel/L9"}
MODES = {"켬": "eval_gt", "가림": "probe_prop_only", "복원": "eval_pred"}
COMMANDS = ("fwd0.5", "fwd1.0")
EXPECTED_CODE = "84deb79336896b6e77916e7479cbace06ee8ab53"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_array(path: Path, *, require_identity: bool = True) -> dict:
    with np.load(path, allow_pickle=False) as z:
        needed = {"env", "kind", "terrain_level", "terrain_col", "body_vx_integral_m",
                  "alive_end", "assignment_sha256"}
        if require_identity:
            needed.add("run_identity")
        assert needed <= set(z.files), f"incomplete array: {path}"
        row = {key: np.asarray(z[key]).copy() for key in needed}
    row["identity"] = json.loads(str(row.pop("run_identity"))) if require_identity else None
    row["assignment"] = str(row.pop("assignment_sha256"))
    return row


def assert_pair(parent: dict, child: dict) -> None:
    assert parent["assignment"] == child["assignment"]
    for key in ("env", "kind", "terrain_level", "terrain_col"):
        assert np.array_equal(parent[key], child[key]), f"paired {key} mismatch"
    assert len(parent["env"]) == 64 and np.array_equal(parent["env"], np.arange(64))
    a, b = parent["identity"].copy(), child["identity"].copy()
    assert a.pop("checkpoint_sha256") != b.pop("checkpoint_sha256")
    assert a == b and a["code_head"] == EXPECTED_CODE
    assert a["code_dirty_files"] == 0 and a["device"] == "cuda:0" and a["eval_seed"] == 42
    for row in (parent, child):
        assert np.isfinite(row["body_vx_integral_m"]).all()
        assert len(row["alive_end"]) == 64


def collect(parent_root: Path = PARENT, child_root: Path = CHILD,
            earlier_child_root: Path = EARLIER_CHILD) -> dict:
    rows = []
    source_paths = {}
    missing = []
    kinds_by_level = {}
    assignments = {}
    for level, directory in LEVEL_DIRS.items():
        for mode_label, mode in MODES.items():
            for command in COMMANDS:
                if mode == "eval_pred" and level != "L0~2":
                    missing.append(f"{level}/{mode_label}/{command}")
                    for kind in kinds_by_level[level]:
                        rows.append({"level": level, "kind": kind, "mode": mode_label,
                                     "command": command, "measured": False})
                    continue
                relative = Path("map64_eval_pred" if mode == "eval_pred" else directory) / f"env_arrays_{mode}_{command}.npz"
                parent_path, child_path = parent_root / relative, child_root / relative
                assert parent_path.exists() and child_path.exists(), f"paired array absent: {relative}"
                # map64_eval_pred is an L0~2 measurement only.
                assert mode != "eval_pred" or level == "L0~2"
                parent, child = load_array(parent_path), load_array(child_path)
                assert_pair(parent, child)
                assigned = assignments.setdefault(level, parent["assignment"])
                assert parent["assignment"] == assigned
                kinds = sorted(str(kind) for kind in np.unique(parent["kind"]))
                assert len(kinds) == 7
                assert kinds_by_level.setdefault(level, kinds) == kinds
                for label, path in (("parent", parent_path), ("child", child_path)):
                    source_paths[f"terrain_{label}_{level}_{mode}_{command}"] = str(path)
                for kind in kinds:
                    selector = parent["kind"] == kind
                    n = int(selector.sum())
                    assert 2 <= n <= 15
                    rows.append({
                        "level": level, "kind": kind, "mode": mode_label, "command": command,
                        "measured": True,
                        "n": n,
                        "parent_median_m": float(np.median(parent["body_vx_integral_m"][selector])),
                        "child_median_m": float(np.median(child["body_vx_integral_m"][selector])),
                        "parent_alive": int(parent["alive_end"][selector].sum()),
                        "child_alive": int(child["alive_end"][selector].sum()),
                    })
    assert len(rows) == 126 and sum(row["measured"] for row in rows) == 98 and len(missing) == 4
    assert len({tuple(v) for v in kinds_by_level.values()}) == 1
    # A separate, same-checkpoint rerun supports the survival fluctuation example.
    relative = Path("hardlevel/L9/env_arrays_probe_prop_only_fwd1.0.npz")
    earlier_path, current_path = earlier_child_root / relative, child_root / relative
    earlier, current = load_array(earlier_path, require_identity=False), load_array(current_path)
    for key in ("env", "kind", "terrain_level", "terrain_col"):
        assert np.array_equal(earlier[key], current[key])
    assert earlier["assignment"] == current["assignment"]
    earlier_meta_path = earlier_path.with_name("map_modes.json")
    current_meta_path = current_path.with_name("map_modes.json")
    earlier_meta = json.loads(earlier_meta_path.read_text(encoding="utf-8-sig"))
    current_meta = json.loads(current_meta_path.read_text(encoding="utf-8-sig"))
    assert earlier_meta["checkpoint_sha256"] == current_meta["checkpoint_sha256"] == current["identity"]["checkpoint_sha256"]
    assert earlier_meta["eval_seed"] == current_meta["eval_seed"] == 42
    source_name = "foothold_s2.eval.eval_map_modes"
    boxes = earlier["kind"] == "boxes"
    repeat = {"level": "L9", "kind": "boxes", "mode": "가림", "command": "fwd1.0",
              "n": int(boxes.sum()), "earlier_alive": int(earlier["alive_end"][boxes].sum()),
              "current_alive": int(current["alive_end"][boxes].sum()),
              "earlier_source_sha": earlier_meta["source_sha256"][source_name],
              "current_source_sha": current_meta["source_sha256"][source_name]}
    source_paths["terrain_child_earlier_L9_probe_prop_only_fwd1.0"] = str(earlier_path)
    source_paths["terrain_child_earlier_L9_meta"] = str(earlier_meta_path)
    source_paths["terrain_child_current_L9_meta"] = str(current_meta_path)
    summary_path = parent_root.parent / "parent_vs_m2000.md"
    if summary_path.exists():
        source_paths["terrain_original_comparison"] = str(summary_path)
    return {"rows": rows, "missing": missing, "assignments": assignments,
            "code_head": current["identity"]["code_head"],
            "repeat": repeat, "source_paths": source_paths,
            "source_sha256": {key: sha(Path(path)) for key, path in source_paths.items()}}
