"""CPU scoring and evidence checks for the EX-42 E1F flag cells."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


MODES = ("eval_gt", "eval_pred", "probe_prop_only")
COUNTS = {"flag_one": 1, "flag_four": 4}


def contract(plan: dict) -> dict:
    cells = plan["evaluation"]["flag_cells"]
    judges, records, specs = cells.get("judge_cases"), cells.get("record_cases"), cells.get("case_specs")
    if (not isinstance(judges, list) or not isinstance(records, list) or
            not isinstance(specs, dict) or not judges or
            set(specs) != set(judges + records) or len(judges + records) != len(specs)):
        raise ValueError("E1F flag cell list incomplete")
    for name, spec in specs.items():
        if (not isinstance(spec, dict) or spec.get("count") not in COUNTS or
                spec.get("map_mode") not in MODES or
                name != f"{spec['count']}_{spec['map_mode']}" or
                spec.get("role") != ("judge" if name in judges else "record_only") or
                (name in judges) != (spec["map_mode"] != "probe_prop_only")):
            raise ValueError("E1F flag cell identity or role differs")
    if set(specs) != {f"{count}_{mode}" for count in COUNTS for mode in MODES}:
        raise ValueError("E1F flag one/four x three-mode coverage differs")
    for key in ("reach_radius_m", "stop_hold_s", "stop_speed_mps", "seconds", "flag_speed_mps"):
        value = cells.get(key)
        if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"E1F flag {key} missing or invalid")
    if cells["stop_hold_s"] > cells["seconds"]:
        raise ValueError("E1F flag stop hold exceeds evaluation window")
    if cells.get("repeat_seeds") != [42, 42, 43, 44, 45]:
        raise ValueError("E1F flag five-repeat seed contract differs")
    return cells


def score_trace(trace: dict, spec: dict, cells: dict) -> dict:
    """A last target needs 0.3 m proximity and 0.5 s quiet without a reset."""
    pos = np.asarray(trace["root_pos_w"], dtype=np.float64)
    vel = np.asarray(trace["root_vel_w"], dtype=np.float64)
    alive = np.asarray(trace["alive"], dtype=bool)
    flags = np.asarray(trace["flags_w"], dtype=np.float64)
    dt = float(trace["dt"])
    steps, envs = alive.shape
    count = COUNTS[spec["count"]]
    if (envs != 64 or pos.shape != (steps, envs, 3) or vel.shape != (steps, envs, 3)
            or flags.shape != (envs, count, 2) or steps < 1 or not math.isfinite(dt) or dt <= 0
            or any(not np.isfinite(array).all() for array in (pos, vel, flags))):
        raise ValueError("E1F flag trace shape, denominator or finiteness differs")
    if abs(steps * dt - cells["seconds"]) > dt / 2:
        raise ValueError("E1F flag trace does not cover the approved full duration")
    if np.any(np.diff(alive.astype(np.int8), axis=0) > 0):
        raise ValueError("E1F flag trace resurrects an env after a reset")
    need = math.ceil(cells["stop_hold_s"] / dt)
    if need > steps:
        raise ValueError("E1F flag trace shorter than stop window")
    radius = cells["reach_radius_m"]
    speed = cells["stop_speed_mps"]
    rows = []
    for env in range(envs):
        active = alive[:, env]
        index = 0
        reached_at = []
        stop_run = 0
        stop_done = False
        for step in range(steps):
            if not active[step]:
                break
            if index < count and np.linalg.norm(pos[step, env, :2] - flags[env, index]) <= radius:
                reached_at.append(step)
                index += 1
            if index == count:
                near = np.linalg.norm(pos[step, env, :2] - flags[env, -1]) <= radius
                quiet = np.linalg.norm(vel[step, env, :2]) <= speed
                stop_run = stop_run + 1 if near and quiet else 0
                stop_done |= stop_run >= need
        survives = bool(active[-1])
        success = bool(survives and index == count and stop_done)
        rows.append({"env": env, "reached_count": index, "reach_steps": reached_at,
                     "stopped_half_second": bool(stop_done), "survival": survives,
                     "success": success})
    return {"envs": envs, "valid_count": envs, "success_count": sum(row["success"] for row in rows),
            "survival_count": sum(row["survival"] for row in rows), "per_env": rows}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_evidence(folder: Path, *, plan: dict, plan_sha256: str,
                  checkpoint_sha256: str, seed: int, count: str) -> dict:
    """Recompute all three map modes from the saved trace, then return indexed rows."""
    cells = contract(plan)
    folder = Path(folder)
    receipt = json.loads((folder / "flag_cells.json").read_text(encoding="utf-8-sig"))
    wanted = {f"{count}_{mode}" for mode in MODES}
    if (count not in COUNTS or receipt.get("format") != "foothold-ex42-flag-eval/1"
            or receipt.get("state") != "done" or receipt.get("plan_sha256") != plan_sha256
            or receipt.get("checkpoint_sha256") != checkpoint_sha256 or receipt.get("seed") != seed
            or receipt.get("envs") != 64 or receipt.get("count") != count
            or set(receipt.get("cases", {})) != wanted):
        raise ValueError("E1F flag receipt identity or coverage differs")
    output = {}
    for case_id in sorted(wanted):
        spec = cells["case_specs"][case_id]
        trace_path = folder / f"{case_id}.npz"
        raw_path = folder / f"{case_id}.json"
        indexed = receipt["cases"][case_id]
        if (indexed.get("trace_file") != str(trace_path) or indexed.get("trace_sha256") != _sha(trace_path)
                or indexed.get("raw_file") != str(raw_path) or indexed.get("raw_sha256") != _sha(raw_path)):
            raise ValueError("E1F flag raw path or SHA differs")
        raw = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        if (raw.get("case_id") != case_id or any(raw.get(key) != value for key, value in spec.items())
                or raw.get("trace_sha256") != indexed["trace_sha256"]):
            raise ValueError("E1F flag case identity differs")
        with np.load(trace_path, allow_pickle=False) as arrays:
            calculated = score_trace({key: arrays[key] for key in arrays.files}, spec, cells)
            from foothold_s2.eval.fixed_terrain import assignment_sha256, fixed_assignment
            levels, types = fixed_assignment(64, 10, 23)
            origins = arrays["env_origins_w"]
            if (not np.array_equal(arrays["terrain_levels"], levels)
                    or not np.array_equal(arrays["terrain_types"], types)
                    or origins.shape != (64, 3) or not np.isfinite(origins).all()
                    or not np.allclose(arrays["flags_w"],
                                       origins[:, None, :2] +
                                       np.asarray([.5 + j for j in range(COUNTS[count])])[None, :, None]
                                       * np.asarray([1., 0.])[None, None, :], atol=1e-5, rtol=0)
                    or raw.get("fixed_terrain", {}).get("assignment_sha256") != assignment_sha256(levels, types)
                    or raw.get("fixed_terrain", {}).get("cols") != 23):
                raise ValueError("E1F flag terrain assignment or target coordinates differ")
        if any(raw.get(key) != calculated[key] for key in calculated):
            raise ValueError("E1F flag score differs from trace")
        if any(indexed.get(key) != raw.get(key) for key in ("envs", "valid_count", "success_count", "survival_count")):
            raise ValueError("E1F flag indexed count differs")
        if spec["role"] == "judge":
            output[case_id] = {key: raw[key] for key in ("case_id", "envs", "valid_count", "success_count", "survival_count")}
            output[case_id].update(raw_file=str(raw_path), raw_sha256=_sha(raw_path))
    return output


def summarize_repeats(roots: list[Path], *, plan: dict, plan_sha256: str,
                      checkpoint_sha256: str) -> dict:
    """Five full two-count runs, including repeated seed 42, with no missing cell."""
    cells = contract(plan)
    seeds = cells["repeat_seeds"]
    if len(roots) != len(seeds) or len({str(Path(root).resolve()) for root in roots}) != len(seeds):
        raise ValueError("E1F flag calibration needs five distinct output directories")
    samples = []
    by_case = {case: {"success_count": [], "survival_count": []} for case in cells["judge_cases"]}
    for root, seed in zip(roots, seeds):
        root = Path(root)
        record = {"seed": seed, "receipts": {}}
        for count in COUNTS:
            folder = root / count
            receipt_path = folder / "flag_cells.json"
            result = read_evidence(folder, plan=plan, plan_sha256=plan_sha256,
                                   checkpoint_sha256=checkpoint_sha256, seed=seed, count=count)
            record["receipts"][count] = {"path": str(receipt_path), "sha256": _sha(receipt_path)}
            for case, row in result.items():
                for metric in ("success_count", "survival_count"):
                    by_case[case][metric].append(row[metric])
        samples.append(record)
    if any(len(values) != 5 for metrics in by_case.values() for values in metrics.values()):
        raise ValueError("E1F flag five-repeat cell coverage incomplete")
    widths = {case: {metric: max(values) - min(values) for metric, values in metrics.items()}
              for case, metrics in by_case.items()}
    return {"format": "foothold-ex42-flag-calibration/1", "seeds": seeds,
            "checkpoint_sha256": checkpoint_sha256, "source_plan_sha256": plan_sha256,
            "repeat_receipts": samples, "repeat_width": widths,
            "counts": by_case}
