"""Compare pinned D44 landing definitions on the same completed Kit traces.

This is a decision aid. It never rewrites a Kit receipt or issues a gate verdict.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import numpy as np

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval.ex42_eval_tile_mesh import source_tile

BOUNDARIES = (250, 500, 750, 1000)
SOURCE_PATH = "foothold_s2/eval/ex42_d44_cells.py"
FIELDS = ("iteration", "case_id", "task", "map_mode", "role", "status", "valid_count",
          "survival_count", "old_success", "proposed_success", "added_envs", "removed_envs",
          "old_success_envs", "proposed_success_envs", "trace_sha256", "original_score_sha256")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _scorer(repo: Path, commit: str) -> tuple[dict, str]:
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("D44 scorer must be pinned to a full commit SHA")
    proc = subprocess.run(["git", "show", f"{commit}:{SOURCE_PATH}"], cwd=repo,
                          capture_output=True, check=True)
    source = proc.stdout
    namespace = {"__name__": f"_d44_{commit}", "__file__": SOURCE_PATH}
    exec(compile(source, f"{commit}:{SOURCE_PATH}", "exec"), namespace)
    return namespace, hashlib.sha256(source).hexdigest()


def compare_trace(trace: dict, *, spec: dict, anchors: dict, settings: dict,
                  old_summarize, proposed_summarize, dt: float) -> dict:
    old = old_summarize(trace, spec=spec, anchors=anchors, settings=settings, dt=dt)
    proposed = proposed_summarize(trace, spec=spec, anchors=anchors, settings=settings, dt=dt)
    if (old["envs"] != proposed["envs"] or old["valid_count"] != proposed["valid_count"]
            or old["survival_count"] != proposed["survival_count"]):
        raise ValueError("D44 definitions changed a denominator or survival count")
    old_success = {row["env"] for row in old["per_env"] if row["success"]}
    proposed_success = {row["env"] for row in proposed["per_env"] if row["success"]}
    return {"valid_count": old["valid_count"], "survival_count": old["survival_count"],
            "old_success": old["success_count"], "proposed_success": proposed["success_count"],
            "added_envs": sorted(proposed_success - old_success),
            "removed_envs": sorted(old_success - proposed_success),
            "old_success_envs": sorted(old_success),
            "proposed_success_envs": sorted(proposed_success)}


def build(run: Path, out: Path, *, evaluation_plan: Path, repo: Path,
          old_commit: str, proposed_commit: str) -> dict:
    run = run.resolve(strict=True)
    out = out.resolve()
    if run == out or run in out.parents:
        raise ValueError("D44 comparison output must be outside the live run")
    policy = EX42Plan.load(evaluation_plan.resolve(strict=True))
    old, old_sha = _scorer(repo, old_commit)
    proposed, proposed_sha = _scorer(repo, proposed_commit)
    old_settings = old["contract"](policy.document)
    if old_settings != proposed["contract"](policy.document):
        raise ValueError("D44 contracts differ; this comparison only permits scorer changes")
    manifest, tile = source_tile(Path(old_settings["source_mesh_dir"]))
    if manifest["mesh_sha256"] != old_settings["source_mesh_sha256"]:
        raise ValueError("D44 source mesh SHA differs from plan")
    rows = []
    sources = {}
    for iteration in BOUNDARIES:
        folder = run / "eval" / "scores" / f"m{iteration}" / "d44"
        receipt_path = folder / "d44_cells.json"
        if not receipt_path.is_file():
            rows.extend({"iteration": iteration, "case_id": case_id,
                         "task": spec["task"], "map_mode": spec["map_mode"],
                         "role": spec["role"], "status": "KIT_RAW_MISSING"}
                        for case_id, spec in old_settings["case_specs"].items())
            continue
        receipt = _read(receipt_path)
        if (receipt.get("state") != "done" or receipt.get("format") != "foothold-ex42-d44-eval/1"
                or receipt.get("plan_sha256") != policy.sha256 or receipt.get("seed") != 42
                or receipt.get("envs") != 64
                or receipt.get("checkpoint_sha256") != _sha(run / f"model_{iteration}.pt")
                or receipt.get("source_mesh_sha256") != manifest["mesh_sha256"]
                or set(receipt.get("cases", {})) != set(old_settings["case_specs"])):
            raise ValueError(f"D44 m{iteration} Kit receipt identity or coverage differs")
        sources[str(iteration)] = {"kit_receipt": str(receipt_path),
                                   "kit_receipt_sha256": _sha(receipt_path),
                                   "checkpoint_sha256": receipt["checkpoint_sha256"]}
        for case_id, spec in old_settings["case_specs"].items():
            case_path = folder / f"{case_id}.json"
            trace_path = folder / f"{case_id}.npz"
            index = receipt["cases"][case_id]
            case = _read(case_path)
            if (_sha(case_path) != index["raw_sha256"] or _sha(trace_path) != index["trace_sha256"]
                    or case.get("trace_sha256") != index["trace_sha256"]
                    or Path(case.get("trace_file", "")).resolve() != trace_path.resolve()
                    or any(case.get(key) != spec[key] for key in ("task", "map_mode", "role"))):
                raise ValueError(f"D44 m{iteration} {case_id} raw lineage differs")
            with np.load(trace_path, allow_pickle=False) as arrays:
                compared = compare_trace({name: arrays[name] for name in arrays.files},
                                         spec=spec, anchors=tile["anchors_local_m"],
                                         settings=old_settings, old_summarize=old["summarize"],
                                         proposed_summarize=proposed["summarize"], dt=float(arrays["dt"]))
            if (compared["valid_count"] != case.get("valid_count")
                    or compared["survival_count"] != case.get("survival_count")
                    or compared["old_success"] != case.get("success_count")):
                raise ValueError(f"D44 m{iteration} {case_id} old scorer differs from Kit score")
            rows.append({"iteration": iteration, "case_id": case_id, "task": spec["task"],
                         "map_mode": spec["map_mode"], "role": spec["role"],
                         "status": "COMPARED", **compared, "trace_sha256": index["trace_sha256"],
                         "original_score_sha256": index["raw_sha256"]})
        if _sha(receipt_path) != sources[str(iteration)]["kit_receipt_sha256"]:
            raise ValueError(f"D44 m{iteration} Kit receipt changed during comparison")
    out.mkdir(parents=True, exist_ok=True)
    csv_path, json_path = out / "d44_old_vs_proposed.csv", out / "d44_old_vs_proposed.json"
    with (out / f".{csv_path.name}.{os.getpid()}.tmp").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value) if isinstance(value, list) else value
                             for key, value in row.items()})
    (out / f".{csv_path.name}.{os.getpid()}.tmp").replace(csv_path)
    summary = {"format": "foothold-ex42-d44-definition-comparison/1", "decision": "NONE",
               "measured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "run": str(run), "evaluation_plan": {"path": str(policy.path), "sha256": policy.sha256},
               "source_mesh_sha256": manifest["mesh_sha256"],
               "old_scorer": {"commit": old_commit, "source_sha256": old_sha},
               "proposed_scorer": {"commit": proposed_commit, "source_sha256": proposed_sha},
               "source_receipts": sources, "rows": rows,
               "completed_iterations": sorted(int(key) for key in sources),
               "missing_iterations": [number for number in BOUNDARIES if str(number) not in sources]}
    json_tmp = out / f".{json_path.name}.{os.getpid()}.tmp"
    json_tmp.write_text(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                        encoding="utf-8")
    json_tmp.replace(json_path)
    return {"csv": str(csv_path), "json": str(json_path),
            "completed_iterations": summary["completed_iterations"],
            "missing_iterations": summary["missing_iterations"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evaluation-plan", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--old-commit", required=True)
    parser.add_argument("--proposed-commit", required=True)
    args = parser.parse_args(argv)
    try:
        result = build(args.run, args.out, evaluation_plan=args.evaluation_plan,
                       repo=args.repo, old_commit=args.old_commit,
                       proposed_commit=args.proposed_commit)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(5, f"EX42_D44_DUAL_COMPARE_ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
