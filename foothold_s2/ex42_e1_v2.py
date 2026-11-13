"""Evidence-based E1 v2 cells. Missing measurements never become a pass."""
from __future__ import annotations

import hashlib
import json
import math
import copy
import re
from pathlib import Path

import numpy as np

from foothold_s2.tools.ex42_boundary_autojudge import body_forward_per_env

MODES = ("eval_gt", "eval_pred", "probe_prop_only")
JUDGE_MODES = MODES[:2]
LOW_CASES = ("fwd0.1", "fwd0.2", "side+0.2", "side-0.2", "side+0.4", "side-0.4")
YAW_CASES = ("fwd0.5", "fwd1.0")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _finite(values, label: str):
    values = np.asarray(values, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"E1 v2 {label} has nonfinite evidence")
    return values


def _source(path: Path, checkpoint_sha: str, seed: int, modes: tuple[str, ...],
            *, level: int | None = None) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    doc = _json(path)
    if (doc.get("checkpoint_sha256") != checkpoint_sha or doc.get("eval_seed") != seed
            or doc.get("envs") != 64 or doc.get("steps") != 300
            or set(doc.get("modes", {})) != set(modes)
            or not doc.get("fixed_terrain") or doc["fixed_terrain"].get("fixed_level") != level):
        raise ValueError(f"E1 v2 source conditions differ: {path}")
    return doc


def _map_cell(path: Path, doc: dict, mode: str, case: str) -> dict:
    command = doc["commands"][case]
    speed = math.hypot(command[0], command[1])
    if speed <= 0 or command[2] != 0:
        raise ValueError(f"E1 v2 command differs: {case}")
    row = doc["modes"][mode][case]
    per_env = row["per_env"]
    name = doc["env_arrays"][f"{mode}/{case}"]
    if Path(name).name != name or len(per_env) != 64 or row.get("env_count") != 64:
        raise ValueError(f"E1 v2 env array identity differs: {case}")
    raw = path.with_name(name)
    with np.load(raw, allow_pickle=False) as z:
        alive, alive_steps = z["alive"].astype(bool), z["alive_steps"]
        dt = float(z["dt"])
        if (alive.shape != (300, 64) or not math.isclose(dt, .02, abs_tol=1e-8)
                or not np.array_equal(alive.sum(0), alive_steps)
                or not np.array_equal(z["alive_end"], alive[-1])):
            raise ValueError(f"E1 v2 alive evidence differs: {raw}")
        projection = _finite([r["command_xy_projection_integral_m"] for r in per_env], case)
        errors = _finite([r["vx_abs_error_mean_alive_mps"] if command[0] else
                          r["vy_abs_error_mean_alive_mps"] for r in per_env], case)
        if command[0]:
            # The same signed body-forward integral as #767. A dead env is still in the median;
            # it cannot count as a successful full six-second trial.
            body = _finite((z["vx"] * alive).sum(0) * dt, case)
            if not np.allclose(body, projection, rtol=2e-5, atol=1e-6):
                raise ValueError(f"E1 v2 body-forward projection differs: {raw}")
            raw_mae = (np.abs(z["vx"] - command[0]) * alive).sum(0) / np.maximum(alive_steps, 1)
            if not np.allclose(raw_mae, errors, rtol=2e-5, atol=1e-6):
                raise ValueError(f"E1 v2 body-forward MAE differs: {raw}")
        ratio = body_forward_per_env(z["vx"], alive, dt, speed) if command[0] else projection / (speed * alive.shape[0] * dt)
        if (not np.isfinite(ratio).all() or
                int(alive[-1].sum()) != row["alive_envs_at_end"] or
                any(r["env"] != i or r["samples_alive"] != int(alive_steps[i])
                    for i, r in enumerate(per_env))):
            raise ValueError(f"E1 v2 map per-env receipt differs: {raw}")
        return {"R": float(np.median(ratio)), "mae_mps": float(np.median(errors)),
                "survival": int(alive[-1].sum()),
                "command_mps": speed, "envs": 64,
                "per_env_R": ratio.tolist(), "per_env_mae_mps": errors.tolist(),
                "per_env_alive_end": alive[-1].astype(bool).tolist(),
                "raw_file": str(raw), "raw_sha256": _sha(raw)}


def _yaw_cell(path: Path, doc: dict, mode: str, case: str) -> dict:
    row = doc["modes"][mode][case]
    raw = path.with_name(Path(row["raw_file"]).name)
    if _sha(raw) != row["raw_sha256"]:
        raise ValueError(f"E1 v2 yaw raw SHA differs: {raw}")
    with np.load(raw, allow_pickle=False) as z:
        yaw, alive = _finite(z["yaw"], "yaw"), z["alive"].astype(bool)
        if (yaw.shape != alive.shape or yaw.shape != (300, 64)
                or not np.array_equal(alive, np.arange(300)[:, None] < alive.sum(0)[None, :])
                or not np.all(alive.sum(0) > 0) or z["heading_pre"].any()
                or not np.allclose(z["cmd_post"][:, :, 2][alive], 0)):
            raise ValueError(f"E1 v2 yaw conditions differ: {raw}")
        start = _finite(z["start_yaw"], "start yaw")
        unwrapped = np.unwrap(np.concatenate([start[None], yaw]), axis=0)
        counts = alive.sum(0)
        absolute = np.abs(unwrapped[counts, np.arange(64)] - unwrapped[0])
        recorded = _finite([r["yaw_signed_accum_rad"] for r in row["per_env"]], "yaw receipt")
        if not np.allclose(recorded, unwrapped[counts, np.arange(64)] - unwrapped[0], atol=3e-6):
            raise ValueError(f"E1 v2 yaw per-env receipt differs: {raw}")
        return {"median_abs_rad": float(np.median(absolute)), "p90_abs_rad": float(np.quantile(absolute, .9)),
                "survival": int(alive[-1].sum()), "envs": 64,
                "raw_file": str(raw), "raw_sha256": _sha(raw)}


def measure_cells(evaluation: Path, checkpoint_sha: str, seed: int, *, require_low: bool = True) -> dict:
    """Read exact per-env raw. Missing sources are explicit HOLD inputs, never guessed from briefs."""
    evaluation = Path(evaluation)
    result = {"format": "foothold-ex42-e1-v2-cells/1", "checkpoint_sha256": checkpoint_sha,
              "seed": seed, "low": {}, "side05": {}, "yaw": {}, "sources": {}}
    for level in (0, 5):
        path = evaluation / "e1_v2" / f"L{level}" / "map_modes.json"
        if not path.is_file():
            if require_low:
                result["low"][f"L{level}"] = {"state": "HOLD", "reason": "평가 열 없음"}
            continue
        doc = _source(path, checkpoint_sha, seed, MODES, level=level)
        if doc.get("command_suite") != "e1_v2" or set(doc.get("commands", {})) != set(LOW_CASES):
            raise ValueError("E1 v2 low command coverage differs")
        result["sources"][f"low_L{level}"] = {"path": str(path), "sha256": _sha(path)}
        result["low"][f"L{level}"] = {mode: {case: _map_cell(path, doc, mode, case)
                                             for case in LOW_CASES} for mode in MODES}
    map_path = evaluation / "map64" / "map_modes.json"
    if map_path.is_file():
        doc = _source(map_path, checkpoint_sha, seed, MODES, level=None)
        result["sources"]["map64"] = {"path": str(map_path), "sha256": _sha(map_path)}
        result["side05"] = {mode: {case: _map_cell(map_path, doc, mode, case)
                                   for case in ("side+0.5", "side-0.5")} for mode in MODES}
    axis_path = evaluation / "axis_v2" / "axis_v2.json"
    if axis_path.is_file():
        doc = _source(axis_path, checkpoint_sha, seed, MODES, level=2)
        result["sources"]["axis_v2"] = {"path": str(axis_path), "sha256": _sha(axis_path)}
        result["yaw"] = {mode: {case: _yaw_cell(axis_path, doc, mode, case)
                                for case in YAW_CASES} for mode in MODES}
    return result


def judge_cells(cells: dict, plan: dict, *, repeats: dict[int, dict] | None = None,
                previous_cells: dict | None = None,
                _ignore_near: bool = False) -> dict:
    """Judge GT and PRED per cell. OFF is retained as record only."""
    cfg = plan["evaluation"]["e1_exit_v2"]
    near = cfg["near_threshold"]
    repeats = repeats or {}
    states, rows = [], {}

    def one(name, value, bounds, *, near_width=None, earlier=None):
        if value is None:
            return {"judgement": "HOLD", "reason": "평가 열 없음"}
        violations = [value[k] < low or value[k] > high for k, low, high in bounds]
        status = "FAIL" if any(violations) else "PASS"
        near_width = near_width or {}
        close = not _ignore_near and any(
            (math.isfinite(low) and abs(value[k] - low) <= near_width[k])
            or (math.isfinite(high) and abs(value[k] - high) <= near_width[k])
            for k, low, high in bounds if k in near_width)
        # A newly passing improvement smaller than the observed repeat width
        # also needs three seeds. Other failed axes still take precedence.
        if earlier and status == "PASS" and not _ignore_near:
            close |= any(k in earlier and ((earlier[k] < low <= value[k]) or
                          (earlier[k] > high >= value[k])) and abs(value[k] - earlier[k]) <= near_width[k]
                         for k, low, high in bounds if k in near_width)
        if close and status == "PASS":
            status = "HOLD"
        return {"judgement": status, "near_threshold": close, **value,
                **({"reason": "세 시드 재측정 필요"} if close else {})}

    def counted(value):
        if value is None:
            return None
        if not all(key in value for key in ("per_env_R", "per_env_mae_mps", "per_env_alive_end")):
            # Small synthetic known-answer test inputs may provide an already counted row.
            if type(value.get("success")) is not int:
                raise ValueError("E1 v2 success denominator missing")
            return value
        ratio = _finite(value["per_env_R"], "per-env R")
        mae = _finite(value["per_env_mae_mps"], "per-env MAE")
        alive = np.asarray(value["per_env_alive_end"])
        if (ratio.shape != (64,) or mae.shape != (64,) or alive.shape != (64,)
                or alive.dtype != bool or int(alive.sum()) != value["survival"]):
            raise ValueError("E1 v2 per-env success source differs")
        success = int((alive & (ratio >= cfg["R_min"]) & (ratio <= cfg["R_max"])
                       & (mae <= cfg["mae_fraction"] * value["command_mps"])).sum())
        return {**value, "success": success}

    for mode in MODES:
        judged = mode in JUDGE_MODES
        for level in (0, 5):
            low = cells.get("low", {}).get(f"L{level}", {}).get(mode, {})
            for case in LOW_CASES:
                if not case.startswith("fwd") and case not in ("side+0.2", "side-0.2", "side+0.4", "side-0.4"):
                    continue
                row = counted(low.get(case))
                key = f"low/L{level}/{mode}/{case}"
                speed = abs(float(case[3:])) if case.startswith("fwd") else abs(float(case[5:]))
                width = ({"R": near["R_0p1"]} if case == "fwd0.1" else
                         {"R": near["R_0p2"]} if case == "fwd0.2" else {})
                bounds = [("R", cfg["R_min"], cfg["R_max"]),
                          ("mae_mps", 0, cfg["mae_fraction"] * speed),
                          ("success", cfg["success_min"], math.inf),
                          ("survival", cfg["survival_min"], math.inf)]
                earlier = (previous_cells or {}).get("low", {}).get(f"L{level}", {}).get(mode, {}).get(case)
                rows[key] = one(key, row, bounds, near_width=width, earlier=earlier) if judged else {"role": "record", **(row or {"state": "HOLD"})}
                if judged:
                    states.append(rows[key]["judgement"])
        for case in ("side+0.5", "side-0.5"):
            row = counted(cells.get("side05", {}).get(mode, {}).get(case))
            key = f"side05/{mode}/{case}"
            speed = .5
            bounds = [("R", cfg["R_min"], cfg["R_max"]), ("mae_mps", 0, cfg["mae_fraction"] * speed),
                      ("success", cfg["success_min"], math.inf), ("survival", cfg["survival_min"], math.inf)]
            rows[key] = one(key, row, bounds) if judged else {"role": "record", **(row or {"state": "HOLD"})}
            if judged:
                states.append(rows[key]["judgement"])
        for case in YAW_CASES:
            row = cells.get("yaw", {}).get(mode, {}).get(case)
            key = f"yaw/{mode}/{case}"
            bounds = [("median_abs_rad", 0, cfg["yaw_median_max_rad"]),
                      ("p90_abs_rad", 0, cfg["yaw_p90_max_rad"]),
                      ("survival", cfg["survival_min"], math.inf)]
            earlier = (previous_cells or {}).get("yaw", {}).get(mode, {}).get(case)
            rows[key] = one(key, row, bounds, near_width={"median_abs_rad": near["yaw_median_rad"],
                                                         "p90_abs_rad": near["yaw_p90_rad"]}, earlier=earlier) if judged else {"role": "record", **(row or {"state": "HOLD"})}
            if judged:
                states.append(rows[key]["judgement"])
        for level in (0, 5, "mixed012"):
            source = cells.get("side05", {}).get(mode, {}) if level == "mixed012" else cells.get("low", {}).get(f"L{level}", {}).get(mode, {})
            for speed in ((.5,) if level == "mixed012" else (.2, .4)):
                left, right = source.get(f"side+{speed}"), source.get(f"side-{speed}")
                key = f"symmetry/{level}/{mode}/{speed}"
                if left is None or right is None:
                    row = {"judgement": "HOLD", "reason": "평가 열 없음"}
                elif min(left["R"], right["R"]) <= 0:
                    row = {"judgement": "FAIL", "reason": "방향 진행 비양수"}
                else:
                    ratio = min(left["R"], right["R"]) / max(left["R"], right["R"])
                    status = "PASS" if ratio >= cfg["symmetry_min"] else "FAIL"
                    if not _ignore_near and abs(ratio - cfg["symmetry_min"]) <= near["S_0p5" if speed == .5 else "S_0p4"]:
                        if status == "PASS":
                            status = "HOLD"
                    row = {"judgement": status, "S": ratio, "near_threshold": status == "HOLD"}
                rows[key] = row if judged else {"role": "record", **row}
                if judged:
                    states.append(row["judgement"])
    if repeats and not _ignore_near:
        if set(repeats) != {7, 13}:
            raise ValueError("E1 v2 near-threshold repeat seeds must be 7 and 13")
        checked = {seed: judge_cells(raw, plan, _ignore_near=True) for seed, raw in repeats.items()}
        base = judge_cells(cells, plan, _ignore_near=True)
        for key, row in rows.items():
            if row.get("near_threshold") and row.get("judgement") == "HOLD" and row.get("role") != "record":
                three = [base["items"][key]["judgement"],
                         checked[7]["items"][key]["judgement"],
                         checked[13]["items"][key]["judgement"]]
                row["repeat_seed_judgments"] = dict(zip((42, 7, 13), three))
                row["judgement"] = "PASS" if three == ["PASS"] * 3 else "HOLD"
                row.pop("reason", None)
                if row["judgement"] == "HOLD":
                    row["reason"] = "세 시드 모두 충족하지 못함"
        states = [r["judgement"] for r in rows.values() if r.get("role") != "record"]
    verdict = "FAIL" if "FAIL" in states else "HOLD" if "HOLD" in states or not states else "PASS"
    return {"judgement": verdict, "items": rows}


def treatment(checkpoint: Path, iteration: int, plan: dict) -> dict:
    """Pin the segment that produced this boundary, never the segment started afterward."""
    if type(iteration) is not int or iteration <= 0 or iteration % 250:
        raise ValueError("E1 v2 treatment needs a completed 250-update boundary")
    root = Path(checkpoint).parent
    boundary = iteration // 250 - 1
    if boundary == 0:
        stage = next((row for row in plan["stages"] if row["id"] == "E1"), None)
        if not isinstance(stage, dict):
            raise ValueError("E1 v2 starting treatment plan row missing")
        actual = {"commands": stage["commands"], "rewards": stage["rewards"],
                  "low_forward_fraction": stage.get("low_forward_fraction")}
        fingerprint = hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"state": "complete", "source": "plan", "boundary_index": 0, "sha256": fingerprint}
    commands_path = root / f"segment_commands_b{boundary}.json"
    rewards_path = root / f"segment_rewards_b{boundary}_rank0.json"
    rank1_path = root / f"segment_rewards_b{boundary}_rank1.json"
    if not all(path.is_file() for path in (commands_path, rewards_path, rank1_path)):
        return {"state": "HOLD", "reason": "처방 실현 영수증 없음"}
    commands, rewards, rank1 = _json(commands_path), _json(rewards_path), _json(rank1_path)
    if (commands.get("boundary_index") != boundary or rewards.get("boundary_index") != boundary
            or rank1.get("boundary_index") != boundary or
            commands.get("stage_id") != "E1" or rewards.get("stage_id") != "E1" or
            rank1.get("stage_id") != "E1" or rank1.get("live") != rewards.get("live")):
        raise ValueError("E1 v2 treatment boundary identity differs")
    low = commands.get("low_forward_fraction")
    if (not isinstance(low, dict) or type(low.get("value")) not in (int, float)
            or not math.isfinite(low["value"])):
        raise ValueError("E1 v2 treatment slow-forward share missing")
    actual = {"commands": commands["commands"], "rewards": rewards["live"],
              "low_forward_fraction": low["value"]}
    fingerprint = hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"state": "complete", "source": "segment_receipt", "boundary_index": boundary, "sha256": fingerprint,
            "commands_path": str(commands_path), "commands_sha256": _sha(commands_path),
            "rewards_path": str(rewards_path), "rewards_sha256": _sha(rewards_path),
            "rank1_path": str(rank1_path), "rank1_sha256": _sha(rank1_path)}


def judge_e1_v2(score: dict, baseline: dict, measured: dict, plan: dict,
                *, previous: dict | None, checkpoint: Path, evaluation: Path, seed: int) -> dict:
    """Two consecutive, same-treatment windows. D44 stop/restart stays visible as record."""
    from foothold_s2.ex42_e1_judge import judge_e1

    if seed != plan["evaluation"]["e1_exit_v2"]["repeat_seeds"][0]:
        raise ValueError("EX-42 E1 v2 primary seed differs from approved plan")
    from foothold_s2.ex42_e1_wide import active as wide_active
    previous_plan_mismatch = (wide_active(score, plan) and previous is not None and
                              previous.get("maintenance_source_sha256") !=
                              score.get("maintenance_source_sha256"))
    if previous_plan_mismatch:
        previous = None
    if not isinstance(score.get("d44_cells"), dict):
        score = {**score, "d44_cells": {}}
    case_specs = plan["evaluation"]["paper_cells"]["stairs_landing"]["case_specs"]
    turn_cases = [case for case, spec in case_specs.items()
                  if spec["role"] == "judge" and spec["task"] in ("turn_left", "turn_right")]
    if len(turn_cases) != 4:
        raise ValueError("E1 v2 requires four signed D44 turn cells")
    legacy_plan = copy.deepcopy(plan)
    legacy_plan["evaluation"]["paper_cells"]["stairs_landing"]["judge_cases"] = turn_cases
    current_turn = {case: score["d44_cells"][case] for case in turn_cases if case in score["d44_cells"]}
    previous_turn = ({case: previous.get("d44_cells", {})[case]
                      for case in turn_cases if case in previous.get("d44_cells", {})}
                     if previous is not None else None)
    current_filtered = {**score, "d44_cells": current_turn}
    previous_filtered = {**previous, "d44_cells": previous_turn} if previous is not None else None
    result = judge_e1(current_filtered, baseline, measured, legacy_plan, previous=previous_filtered)
    result["d44_cells"] = score["d44_cells"]
    if "e1_v2_cells" not in score:
        score["e1_v2_cells"] = measure_cells(evaluation, score["checkpoint_sha256"], seed)
    result["e1_v2_cells"] = score["e1_v2_cells"]
    repeats = {}
    for repeat_seed in plan["evaluation"]["e1_exit_v2"]["repeat_seeds"][1:]:
        folder = evaluation / f"e1_v2_repeat_seed{repeat_seed}"
        if folder.exists():
            repeats[repeat_seed] = measure_cells(folder, score["checkpoint_sha256"], repeat_seed)
    previous_cells = previous.get("e1_v2_cells", {}) if previous is not None else {}
    expected_repeats = set(plan["evaluation"]["e1_exit_v2"]["repeat_seeds"][1:])
    current_v2 = judge_cells(result["e1_v2_cells"], plan,
                             repeats=repeats if set(repeats) == expected_repeats else None,
                             previous_cells=previous_cells)
    if repeats and set(repeats) != expected_repeats:
        current_v2["repeat_evidence"] = {"judgement": "HOLD", "reason": "세 시드 자료 일부 결측"}
    # The prior P1 receipt has already judged its own seed 42/7/13 bundle.
    # Rejudging seed 42 alone here would turn a valid near-threshold PASS back
    # into HOLD and make graduation impossible on the following boundary.
    prior_v2 = ((previous.get("e1_exit_v2") or {}).get("current") if previous is not None else None)
    if not isinstance(prior_v2, dict) or prior_v2.get("judgement") not in ("PASS", "HOLD", "FAIL"):
        prior_v2 = {"judgement": "HOLD", "reason": "직전 창 v2 판정 없음"}
    match = re.fullmatch(r"model_(\d+)\.pt", Path(checkpoint).name)
    if match is None:
        raise ValueError("E1 v2 checkpoint iteration missing")
    iteration = int(match.group(1))
    current_treatment = treatment(checkpoint, iteration, plan)
    # A P1 score is written before the next segment starts. Earlier scores may
    # therefore contain a legacy HOLD for a not-yet-created b<k> receipt.
    # Reconstruct that completed window from its own plan or b<k-1> receipt.
    previous_treatment = (treatment(Path(checkpoint).with_name(f"model_{iteration - 250}.pt"),
                                    iteration - 250, plan) if previous is not None and iteration > 250 else None)
    if (current_treatment["state"] != "complete" or not isinstance(previous_treatment, dict)
            or previous_treatment.get("state") != "complete"):
        treatment_state = "HOLD"
    else:
        treatment_state = "PASS" if current_treatment["sha256"] == previous_treatment.get("sha256") else "HOLD"
    result["e1_v2_treatment"] = current_treatment
    verdicts = [result["judgement"], current_v2["judgement"], prior_v2["judgement"], treatment_state]
    from foothold_s2.ex42_e1_wide import judge_cells as judge_wide, off_survival
    wide = None
    off = None
    if wide_active(score, plan):
        current_wide = judge_wide(score["e1_wide_cells"], plan, score["e1_wide_cap"])
        if previous is not None and "e1_wide_cells" in previous:
            from foothold_s2.ex42_e1_wide import read_cells as read_wide, cap_from_training
            prior_cells = read_wide(Path(previous["e1_wide_evaluation"]),
                                    previous["checkpoint_sha256"],
                                    previous["conditions"]["eval_seed"], plan,
                                    score["e1_wide_cells"]["mesh_sha256"])
            prior_cap = cap_from_training(Path(previous["checkpoint"]),
                                          previous["execution_plan_sha256"],
                                          score["e1_wide_cells"]["mesh_sha256"])
            if prior_cells != previous["e1_wide_cells"] or prior_cap != previous["e1_wide_cap"]:
                raise ValueError("E1 C1 previous window raw or cap evidence differs")
        previous_wide = ((previous.get("e1_exit_v2") or {}).get("wide_current")
                         if previous is not None else None)
        if not isinstance(previous_wide, dict) or previous_wide.get("judgement") not in ("PASS", "HOLD", "FAIL"):
            previous_wide = {"judgement": "HOLD", "reason": "직전 창 C1 판정 없음"}
        wide = {"current": current_wide, "previous": previous_wide}
        verdicts += [current_wide["judgement"], previous_wide["judgement"]]
        off = off_survival(score, plan, previous)
        verdicts.append(off["judgement"])
    overall = "FAIL" if "FAIL" in verdicts else "HOLD" if "HOLD" in verdicts else "PASS"
    result["judgement"] = overall
    result["reason"] = "E1 v2: maintenance, D44 turns, S1/S2/Y1, fixed treatment in two windows"
    result["e1_exit_v2"] = {"judgement": overall, "current": current_v2,
                           "previous": prior_v2, "treatment": {"judgement": treatment_state,
                           "current": current_treatment, "previous": previous_treatment},
                           "repeat_sources": {str(s): row["sources"] for s, row in repeats.items()},
                           **({"wide_current": wide["current"], "wide_previous": wide["previous"]}
                              if wide is not None else {}),
                           **({"off_survival": off,
                               "previous_plan_mismatch": previous_plan_mismatch} if off is not None else {}),
                           "d44_stop_restart_role": "record_only",
                           "d44_stop_restart": {case: value for case, value in score["d44_cells"].items()
                                                if case.startswith("stop_restart_")}}
    result["e1_exit"]["judgement"] = overall
    return result
