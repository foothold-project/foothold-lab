"""C1 E1 range cells, scored only from pinned Kit arrays and the evaluation plan."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

from foothold_s2.eval.map_mode_cells import E1_WIDE_FIXED_COMMANDS, E1_WIDE_ENDPOINT_COMMANDS

MODES = ("eval_gt", "eval_pred", "probe_prop_only")
CONTINUOUS = ("pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
              "hf_pyramid_slope", "hf_pyramid_slope_inv", "stage_stairs")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contract(plan: dict) -> dict:
    cfg = plan["evaluation"]["e1_widened"]
    if (cfg.get("format") != "foothold-ex42-e1-widened/1"
            or cfg.get("active") is not True
            or cfg.get("fixed_forward_levels") != plan["evaluation"]["fixed_levels"]
            or set(cfg.get("fixed_commands", ())) != set(E1_WIDE_FIXED_COMMANDS)
            or set(cfg.get("endpoint_commands", ())) != set(E1_WIDE_ENDPOINT_COMMANDS)
            or cfg.get("judge_modes") != list(MODES[:2])
            or cfg.get("record_modes") != [MODES[2]]
            or set(cfg.get("fixed_forward_roles", {})) != set(cfg["fixed_forward_levels"])
            or set(cfg.get("endpoint_roles", {})) != set(E1_WIDE_ENDPOINT_COMMANDS)
            or cfg.get("fixed_other_role") != "record_only"
            or cfg.get("reached_level_success_min") != plan["evaluation"]["promotion"]["success_min"]):
        raise ValueError("E1 C1 widened evaluation plan contract differs")
    return cfg


def active(score: dict, plan: dict) -> bool:
    """C1 needs an explicit evaluation plan distinct from the pinned run plan."""
    return (plan.get("evaluation", {}).get("e1_widened", {}).get("active") is True
            and bool(score.get("execution_plan_sha256"))
            and score["execution_plan_sha256"] != score.get("maintenance_source_sha256"))


def kit_commands(checkpoint, output, device, *, task, plan_path, plan, mesh_dir, seed):
    """One 475-step fixed bundle per level and one 300-step endpoint bundle."""
    from foothold_s2.machine_profile import machine_path
    cfg = contract(plan)
    if mesh_dir is None:
        raise ValueError("E1 C1 widened cells require pinned combined mesh")
    kit = ["--headless", f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]
    common = [str(machine_path("conda_python")), "-m", "foothold_s2.eval.eval_map_modes",
              "--ex42-evaluation-plan", str(plan_path), "--task", task,
              "--checkpoint", str(checkpoint), "--envs", "64",
              "--modes", ",".join(MODES), "--fixed-terrain", "--mesh-dir", str(mesh_dir),
              "--eval-seed", str(seed), "--commands", "all", "--device", device]
    result = []
    for level in cfg["fixed_forward_levels"]:
        result.append((f"wide_L{level}", [*common, "--fixed-level", str(level),
                       "--steps", "475", "--command-suite", "e1_wide_fixed",
                       "--out", str(Path(output) / "wide" / f"L{level}"), *kit]))
    result.append(("wide_endpoints", [*common, "--steps", "300",
                   "--command-suite", "e1_wide_endpoint",
                   "--out", str(Path(output) / "wide" / "endpoints"), *kit]))
    return result


def _source(path: Path, checkpoint_sha: str, seed: int, suite: str, steps: int,
            level: int | None, mesh_sha: str) -> dict | None:
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    commands = E1_WIDE_FIXED_COMMANDS if suite == "e1_wide_fixed" else E1_WIDE_ENDPOINT_COMMANDS
    if (doc.get("checkpoint_sha256") != checkpoint_sha or doc.get("eval_seed") != seed
            or doc.get("envs") != 64 or doc.get("steps") != steps
            or doc.get("command_suite") != suite
            or doc.get("commands") != {key: list(value) for key, value in commands.items()}
            or doc.get("ex42_mesh", {}).get("mesh_sha256") != mesh_sha
            or set(doc.get("modes", {})) != set(MODES)
            or not doc.get("fixed_terrain")
            or doc["fixed_terrain"].get("fixed_level") != level
            or any(set(doc["modes"][mode]) != set(commands) for mode in MODES)):
        raise ValueError(f"E1 C1 Kit source identity differs: {path}")
    from foothold_s2.eval.ex42_mesh_eval import validate_eval_cell
    validate_eval_cell(doc, doc["ex42_mesh"], fixed_level=level)
    return doc


def _geometry(plan: dict, mesh_sha: str) -> tuple[dict, dict]:
    pin = plan["evaluation"]["forward_completion_timing"]["calibration_table"]
    path = Path(pin["path"])
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    if sha(path) != pin["sha256"]:
        raise ValueError("E1 C1 geometry table SHA differs")
    table = json.loads(path.read_text(encoding="utf-8-sig"))
    if mesh_sha not in {source.get("mesh_sha256") for source in table.get("sources", {}).values()}:
        raise ValueError("E1 C1 geometry table does not cover the pinned mesh")
    rows = {(row["kind"], row["level"]): row for row in table["rows"]
            if row["family"] == "A" and row["kind"] in CONTINUOUS}
    for level in contract(plan)["fixed_forward_levels"]:
        if any((kind, level) not in rows for kind in CONTINUOUS):
            raise ValueError(f"E1 C1 geometry table misses level {level}")
    return rows, {"path": str(path), "sha256": pin["sha256"]}


def _fixed_forward(folder: Path, doc: dict, mode: str, level: int, rows: dict) -> dict:
    array_name = doc["env_arrays"][f"{mode}/fwd1.0"]
    if array_name != f"env_arrays_{mode}_fwd1.0.npz":
        raise ValueError("E1 C1 fixed array name differs")
    path = folder / array_name
    with np.load(path, allow_pickle=False) as arrays:
        x, y, alive = (arrays[key] for key in ("root_x_local_m", "root_y_local_m", "alive"))
        kinds, levels, columns = (arrays[key] for key in ("kind", "terrain_level", "terrain_col"))
        dt = float(arrays["dt"])
        if (x.shape != (475, 64) or y.shape != x.shape or alive.shape != x.shape
                or alive.dtype != bool or levels.shape != (64,) or columns.shape != (64,)
                or not np.all(levels == level)
                or str(arrays["assignment_sha256"]) != doc["fixed_terrain"]["assignment_sha256"]
                or not np.isfinite(x).all() or not np.isfinite(y).all()
                or not math.isclose(dt, .02, abs_tol=1e-8)
                or np.any(np.diff(alive.astype(np.int8), axis=0) > 0)
                or not np.array_equal(alive[-1], arrays["alive_end"])
                or not np.array_equal(alive.sum(0), arrays["alive_steps"])):
            raise ValueError("E1 C1 fixed trace differs")
        tiles = doc["terrain_tiles"]
        if len(tiles) != 64 or any(tile["kind"] != str(kinds[i]) or
                                  tile["level"] != level or tile["env"] != i or
                                  tile["column"] != int(columns[i])
                                  for i, tile in enumerate(tiles)):
            raise ValueError("E1 C1 fixed terrain assignment differs")
        per_env = []
        for i, kind in enumerate(kinds):
            if str(kind) not in CONTINUOUS:
                raise ValueError("E1 C1 fixed trace includes noncontinuous kind")
            timing = rows[(str(kind), level)]
            stop = timing["steps"]
            if not 1 <= stop <= 475 or not math.isclose(timing["dt"], dt, abs_tol=1e-8):
                raise ValueError("E1 C1 geometry step window differs")
            anchor = timing["anchors"]
            line = anchor["exit_x"] - timing["origin_m"][0]
            lo, hi = [v - timing["origin_m"][1] for v in anchor["exit_bounds_y"]]
            arrived = np.flatnonzero((x[:stop, i] >= line) & (y[:stop, i] >= lo)
                                     & (y[:stop, i] <= hi) & alive[:stop, i])
            first = int(arrived[0]) if len(arrived) else None
            hold = math.ceil(timing["hold_s"] / dt)
            success = (first is not None and first + hold < stop
                       and bool(alive[first:first + hold + 1, i].all()))
            per_env.append({"env": i, "kind": str(kind), "level": level,
                            "time_steps": stop, "first_reach_step": first,
                            "success": bool(success), "survival": bool(alive[stop - 1, i])})
    by_kind = {kind: {"envs": sum(r["kind"] == kind for r in per_env),
                      "success": sum(r["success"] for r in per_env if r["kind"] == kind),
                      "survival": sum(r["survival"] for r in per_env if r["kind"] == kind)}
               for kind in CONTINUOUS}
    return {"valid_count": 64, "success_count": sum(r["success"] for r in per_env),
            "survival_count": sum(r["survival"] for r in per_env),
            "by_kind": by_kind, "per_env": per_env,
            "raw_file": str(path), "raw_sha256": sha(path)}


def _endpoint(folder: Path, doc: dict, mode: str, case: str) -> dict:
    from foothold_s2.ex42_e1_v2 import _map_cell
    if case.startswith("side"):
        return _map_cell(folder / "map_modes.json", doc, mode, case)
    name = doc["env_arrays"][f"{mode}/{case}"]
    path = folder / name
    if Path(name).name != name:
        raise ValueError("E1 C1 endpoint array name differs")
    row = doc["modes"][mode][case]
    with np.load(path, allow_pickle=False) as arrays:
        alive = arrays["alive"]
        dt = float(arrays["dt"])
        if (alive.shape != (300, 64) or alive.dtype != bool
                or row["alive_envs_at_end"] != int(alive[-1].sum())):
            raise ValueError("E1 C1 endpoint alive evidence differs")
        wz_error = [r["wz_abs_error_mean_alive_radps"] for r in row["per_env"]]
        projection = [r["command_xy_projection_integral_m"] for r in row["per_env"]]
        speed = math.hypot(*doc["commands"][case][:2])
        if (len(wz_error) != 64 or not np.isfinite(wz_error).all()
                or (speed > 0 and not np.isfinite(projection).all())
                or (speed == 0 and any(value is not None for value in projection))):
            raise ValueError("E1 C1 endpoint per-env evidence differs")
    return {"survival": int(alive[-1].sum()), "envs": 64,
            "wz_mae_median_radps": float(np.median(wz_error)),
            "linear_R_median": float(np.median(projection) / (speed * 300 * dt)) if speed else None,
            "raw_file": str(path), "raw_sha256": sha(path)}


def read_cells(evaluation: Path, checkpoint_sha: str, seed: int, plan: dict,
               mesh_sha: str) -> dict:
    evaluation = Path(evaluation)
    cfg = contract(plan)
    rows, source = _geometry(plan, mesh_sha)
    result = {"format": cfg["format"], "checkpoint_sha256": checkpoint_sha,
              "seed": seed, "mesh_sha256": mesh_sha, "geometry": source,
              "fixed": {}, "endpoints": {}, "sources": {}}
    for level in cfg["fixed_forward_levels"]:
        folder = evaluation / "wide" / f"L{level}"
        path = folder / "map_modes.json"
        doc = _source(path, checkpoint_sha, seed, "e1_wide_fixed", 475, level, mesh_sha)
        if doc is None:
            result["fixed"][f"L{level}"] = {"state": "HOLD", "reason": "평가 열 없음"}
            continue
        result["sources"][f"L{level}"] = {"path": str(path), "sha256": sha(path)}
        result["fixed"][f"L{level}"] = {}
        for mode in MODES:
            result["fixed"][f"L{level}"][mode] = {
                "fwd1.0": _fixed_forward(folder, doc, mode, level, rows),
                **{case: {"survival_count": doc["modes"][mode][case]["alive_envs_at_end"],
                          "by_kind": doc["modes"][mode][case]["by_kind"],
                          "role": "record_only"} for case in cfg["fixed_commands"] if case != "fwd1.0"}}
    folder = evaluation / "wide" / "endpoints"
    path = folder / "map_modes.json"
    doc = _source(path, checkpoint_sha, seed, "e1_wide_endpoint", 300, None, mesh_sha)
    if doc is None:
        result["endpoints"] = {"state": "HOLD", "reason": "평가 열 없음"}
    else:
        result["sources"]["endpoints"] = {"path": str(path), "sha256": sha(path)}
        result["endpoints"] = {mode: {case: _endpoint(folder, doc, mode, case)
                                    for case in cfg["endpoint_commands"]} for mode in MODES}
    return result


def cap_from_training(checkpoint: Path, execution_sha: str, mesh_sha: str) -> int:
    """The segment-start rank receipts, not observed curriculum levels, set eligibility."""
    from foothold_s2.ex42_exposure_receipt import fold_ranks
    match = re.fullmatch(r"model_(\d+)\.pt", Path(checkpoint).name)
    if match is None or int(match.group(1)) < 250:
        raise ValueError("E1 C1 checkpoint boundary invalid")
    previous = int(match.group(1)) - 250
    paths = [Path(checkpoint).parent / f"exposure_receipt_start_{previous}_rank{rank}.json"
             for rank in (0, 1)]
    if not all(path.is_file() for path in paths):
        raise ValueError("E1 C1 segment-start exposure receipts missing")
    doc = fold_ranks([json.loads(path.read_text(encoding="utf-8-sig")) for path in paths])
    if (doc["stage_id"] != "E1" or doc["plan_sha256"] != execution_sha
            or doc["mesh_sha256"] != mesh_sha or doc["iteration"] != previous):
        raise ValueError("E1 C1 segment-start exposure identity differs")
    caps = {r["level_cap"] for r in doc["column_rows"]
            if r["family"] == "A" and r["kind"] in CONTINUOUS and r["open"]}
    if len(caps) != 1:
        raise ValueError("E1 C1 continuous exposure cap differs by column")
    return caps.pop()


def judge_cells(cells: dict, plan: dict, cap: int) -> dict:
    cfg = contract(plan)
    threshold = plan["evaluation"]["promotion"]
    linear = plan["evaluation"]["e1_exit_v2"]
    items = {}
    for mode in MODES:
        judge_mode = mode in cfg["judge_modes"]
        for level in cfg["fixed_forward_levels"]:
            role = cfg["fixed_forward_roles"][level]
            judge = judge_mode and role == "judge_if_exposed" and cap >= level
            row = cells.get("fixed", {}).get(f"L{level}", {}).get(mode, {}).get("fwd1.0")
            key = f"wide_L{level}_fwd1.0/{mode}"
            state = ("HOLD" if row is None else
                     "PASS" if row["success_count"] >= threshold["success_min"]
                     and row["survival_count"] >= threshold["survival_min"] else "FAIL")
            items[key] = {"role": "judge" if judge else "record_only",
                          "judgement": state if judge else "record",
                          "success": row["success_count"] if row else None,
                          "valid": row["valid_count"] if row else None,
                          "survival": row["survival_count"] if row else None,
                          "success_min": threshold["success_min"], "survival_min": threshold["survival_min"],
                          "cap": cap, "source_role": role}
        for case in cfg["endpoint_commands"]:
            role = cfg["endpoint_roles"][case]
            judge = judge_mode and role == "judge"
            row = cells.get("endpoints", {}).get(mode, {}).get(case)
            key = f"{case}/{mode}"
            if judge:
                if row is None:
                    state = "HOLD"
                else:
                    from foothold_s2.ex42_e1_v2 import _finite
                    ratio = _finite(row["per_env_R"], "C1 side R")
                    mae = _finite(row["per_env_mae_mps"], "C1 side MAE")
                    alive = np.asarray(row["per_env_alive_end"])
                    speed = abs(E1_WIDE_ENDPOINT_COMMANDS[case][1])
                    success = int(((ratio >= linear["R_min"]) & (ratio <= linear["R_max"])
                                   & (mae <= linear["mae_fraction"] * speed) & alive).sum())
                    state = ("PASS" if success >= linear["success_min"]
                             and row["survival"] >= linear["survival_min"]
                             and linear["R_min"] <= row["R"] <= linear["R_max"]
                             and row["mae_mps"] <= linear["mae_fraction"] * speed else "FAIL")
            else:
                state = "record"
                success = None
            items[key] = {"role": "judge" if judge else "record_only", "judgement": state,
                          "success": success if judge and row is not None else None,
                          "valid": 64 if row is not None else None,
                          "survival": row.get("survival") if row else None,
                          "success_min": linear["success_min"] if judge else None,
                          "survival_min": linear["survival_min"] if judge else None}
        left, right = (cells.get("endpoints", {}).get(mode, {}).get(case)
                       for case in ("side+0.8", "side-0.8"))
        key = f"symmetry/side0.8/{mode}"
        if judge_mode:
            symmetry = (min(left["R"], right["R"]) / max(left["R"], right["R"])
                        if left and right and min(left["R"], right["R"]) > 0 else None)
            state = ("HOLD" if symmetry is None else
                     "PASS" if symmetry >= linear["symmetry_min"] else "FAIL")
        else:
            symmetry, state = None, "record"
        items[key] = {"role": "judge" if judge_mode else "record_only",
                      "judgement": state, "S": symmetry}
    verdicts = [row["judgement"] for row in items.values() if row["role"] == "judge"]
    verdict = "FAIL" if "FAIL" in verdicts else "HOLD" if "HOLD" in verdicts or not verdicts else "PASS"
    reached = {}
    for mode in MODES:
        passed = [level for level in cfg["fixed_forward_levels"]
                  if cells.get("fixed", {}).get(f"L{level}", {}).get(mode, {}).get("fwd1.0", {}).get(
                      "success_count", -1) >= cfg["reached_level_success_min"]]
        reached[mode] = max(passed) if passed else None
    return {"judgement": verdict, "items": items, "reached_level": reached, "cap": cap}
