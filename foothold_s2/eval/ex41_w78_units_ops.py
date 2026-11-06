"""Queue isolated EX-41 W78 mode/case units and compare them with the full receipt.

This module never starts Kit directly.  The live dispatcher owns admission and its lock.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from foothold_s2.eval.ex41_w78_merge import CASES, MODES, merge

PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
DISPATCHER = Path("D:/mai-wt/foothold-lab/lead-dispatch-measure/_out/tools/gpu_jobs/dispatch.py")
QUEUE = Path("D:/mai-tmp/gpu/queue.json")
ROOT = Path(__file__).resolve().parents[2]
KIT_CACHE = "--kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache"
PROOF = (("eval_gt", "stairs_side_left"), ("probe_prop_only", "flat_fwd1.0"))


def unit_argv(checkpoint: Path, out: Path, mode: str, case: str) -> list[str]:
    if mode not in MODES or case not in CASES:
        raise ValueError(f"unknown W78 unit: {mode}/{case}")
    return [str(PYTHON), "-m", "foothold_s2.eval.eval_map_modes",
            "--task", "FootholdS2-Go2-S2-SB-v0", "--checkpoint", str(checkpoint),
            "--envs", "64", "--modes", "eval_gt,probe_prop_only,eval_pred",
            "--fixed-terrain", "--eval-seed", "42", "--terrain-skill-v2",
            "--terrain-skill-v2-cases", case, "--terrain-skill-v2-modes", mode,
            "--terrain-levels", "2,5", "--stair-start-angles-deg", "0,30,60,90",
            "--terrain-set", "default", "--out", str(out), "--device", "cuda:1",
            "--headless", KIT_CACHE]


def register(checkpoint: Path, root: Path, units: tuple[tuple[str, str], ...]) -> list[int]:
    checkpoint = checkpoint.resolve(strict=True)
    if not PYTHON.is_file() or not DISPATCHER.is_file():
        raise FileNotFoundError("pinned interpreter or live dispatcher missing")
    ids = []
    for mode, case in units:
        out = root / mode / case
        title = f"EX41 W78 unit {checkpoint.stem} {mode} {case}"
        q = json.loads(QUEUE.read_text(encoding="utf-8-sig"))
        matches = [item for item in q["items"] if item["title"] == title]
        if matches:
            if len(matches) != 1 or matches[0].get("argv") != unit_argv(checkpoint, out, mode, case):
                raise ValueError(f"queue identity differs: {title}")
            ids.append(matches[0]["id"])
            continue
        if out.exists():
            raise FileExistsError(f"unit output already exists without queue identity: {out}")
        cmd = [str(PYTHON), str(DISPATCHER), "queue", "add", "--title", title,
               "--priority", "2", "--gpu", "1", "--owner", "scripter",
               "--kind", "eval", "--cwd", str(ROOT),
               "--argv-json", json.dumps(unit_argv(checkpoint, out, mode, case)),
               "--done-file", str(out / "terrain_skill_v2.json")]
        result = subprocess.run(cmd, text=True, capture_output=True, encoding="utf-8", check=True)
        token = result.stdout.strip().split()[-1]
        ids.append(int(token))
    return ids


def register_merge(checkpoint: Path, root: Path) -> int:
    output = root / "terrain_skill_v2.json"
    title = f"EX41 W78 merge {checkpoint.stem}"
    argv = [str(PYTHON), "-m", "foothold_s2.eval.ex41_w78_units_ops", "merge",
            "--checkpoint", str(checkpoint), "--root", str(root), "--out", str(output)]
    q = json.loads(QUEUE.read_text(encoding="utf-8-sig"))
    matches = [item for item in q["items"] if item["title"] == title]
    if matches:
        if len(matches) != 1 or matches[0].get("argv") != argv:
            raise ValueError(f"queue identity differs: {title}")
        return matches[0]["id"]
    result = subprocess.run([
        str(PYTHON), str(DISPATCHER), "queue", "add", "--title", title,
        "--priority", "2", "--gpu", "1", "--owner", "scripter", "--kind", "eval",
        "--cwd", str(ROOT), "--argv-json", json.dumps(argv), "--done-file", str(output),
    ], text=True, capture_output=True, encoding="utf-8", check=True)
    return int(result.stdout.strip().split()[-1])


def numeric_leaves(value, prefix=""):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"raw_sha256", "raw_file"}:
                continue
            yield from numeric_leaves(child, f"{prefix}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from numeric_leaves(child, f"{prefix}/{index}")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield prefix, value


def compare(full: Path, root: Path, units=PROOF) -> dict:
    baseline = json.loads(full.read_text(encoding="utf-8"))
    differences = []
    checked = 0
    for mode, case in units:
        part = json.loads((root / mode / case / "terrain_skill_v2.json").read_text(encoding="utf-8"))
        if part.get("state") != "done" or part.get("checkpoint_sha256") != baseline.get("checkpoint_sha256"):
            raise ValueError(f"unit identity or completion differs: {mode}/{case}")
        if part.get("case_selection") != [case] or part.get("mode_selection") != [mode]:
            raise ValueError(f"unit selector differs: {mode}/{case}")
        for key in ("envs", "eval_seed", "levels", "start_angles_deg", "dt_s", "dr_off",
                    "curriculum_off"):
            if part.get(key) != baseline.get(key):
                raise ValueError(f"unit configuration differs at {key}: {mode}/{case}")
        expected_rows = {f"L{level}_a{angle:03d}_{case}" for level in (2, 5)
                         for angle in (0, 30, 60, 90)}
        if set(part["modes"][mode]) != expected_rows:
            raise ValueError(f"unit coverage differs: {mode}/{case}")
        for key, new_row in part["modes"][mode].items():
            if not key.endswith("_" + case):
                raise ValueError(f"unexpected unit row {key}")
            old = dict(numeric_leaves(baseline["modes"][mode][key]))
            new = dict(numeric_leaves(new_row))
            if old.keys() != new.keys():
                differences.append({"unit": f"{mode}/{case}", "row": key,
                                    "field": "numeric_keys", "old": len(old), "new": len(new)})
            for path in old.keys() & new.keys():
                checked += 1
                if old[path] != new[path]:
                    differences.append({"unit": f"{mode}/{case}", "row": key,
                                        "field": path, "old": old[path], "new": new[path]})
    return {"state": "same" if not differences else "different", "checked_numeric_values": checked,
            "differences": differences, "difference_count": len(differences)}


def merge_if_complete(root: Path, checkpoint: Path, output: Path) -> dict:
    missing = [f"{mode}/{case}" for mode in MODES for case in CASES
               if not (root / mode / case / "terrain_skill_v2.json").is_file()]
    if missing:
        return {"state": "pending", "missing": missing}
    return merge(root, checkpoint, output)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("proof-register", "compare", "all-register", "merge"))
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--full", type=Path)
    p.add_argument("--proof-root", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    if a.action == "proof-register":
        result = {"queue_ids": register(a.checkpoint, a.root, PROOF)}
    elif a.action == "compare":
        if a.full is None:
            p.error("compare requires --full")
        result = compare(a.full, a.root)
    elif a.action == "all-register":
        if a.full is None or a.proof_root is None:
            p.error("all-register requires --full and --proof-root for the m750 proof")
        proof = compare(a.full, a.proof_root)
        if proof["state"] != "same":
            raise ValueError("m750 known-input proof differs, no further registration")
        result = {"queue_ids": register(a.checkpoint, a.root,
                                        tuple((m, c) for m in MODES for c in CASES))}
        result["merge_queue_id"] = register_merge(a.checkpoint, a.root)
    else:
        if a.out is None:
            p.error("merge requires --out")
        result = merge_if_complete(a.root, a.checkpoint, a.out)
    if a.action == "merge" and result.get("state") == "done":
        result = {"state": "done", "out": str(a.out), "parts": len(result["parts"]),
                  "modes": {mode: len(rows) for mode, rows in result["modes"].items()}}
    elif a.action == "compare":
        result = {**result, "differences": result["differences"][:20]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result.get("state") != "different" else 1


if __name__ == "__main__":
    raise SystemExit(main())
