"""CPU EX-40 checkpoint score, with the continuous.py score/2 identity contract."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from foothold_s2.curriculum.continuous import Plan
from foothold_s2.eval.map_mode_cells import EX40_B3_COMMANDS, commands


class EvidenceHold(ValueError):
    """Required evidence is absent or internally inconsistent."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def config(path: Path) -> dict:
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    if (row.get("format") != "foothold-ex40-score-config/1"
            or row.get("device") != "cuda:1" or row.get("envs") != 64
            or list(row.get("stages", {})) != ["B0", "B1", "B2", "B3a", "B3b", "B3c", "T0"]
            or row.get("checkpoint_stride") != 250):
        raise ValueError("EX-40 score config identity or 64-env contract differs")
    all_commands = set(commands("extended"))
    for stage in row["stages"].values():
        if (not set(stage["judge_commands"]) <= all_commands
                or not set(stage["judge_modes"]) <= {"eval_gt", "probe_prop_only", "eval_pred"}
                or not stage["judge_modes"]
                or not set(stage.get("relative_commands", [])) <= set(EX40_B3_COMMANDS)):
            raise ValueError("EX-40 stage command or map mode invalid")
    return row


def require_shadow_plan(plan: Plan, cfg: dict) -> None:
    """D72 scores must follow the exact seven fixed stages without auto-promotion."""
    if ([item.id for item in plan.stages] != list(cfg["stages"])
            or plan.promotion != "fixed" or not plan.shadow_gate):
        raise ValueError("D72 score requires seven fixed stages and shadow_gate true")


def _finite(value, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise EvidenceHold(f"{label} missing or nonfinite")
    return float(value)


def _map_rows(path: Path, checkpoint: Path, config_row: dict, *, extra: bool = False,
              wanted_extra: set[str] | None = None) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    suite = "ex40_b3" if extra else "extended"
    wanted = (wanted_extra if wanted_extra is not None else set(EX40_B3_COMMANDS)) if extra else set(commands("extended"))
    command_values = commands(suite)
    if (data.get("checkpoint_sha256") != sha256(checkpoint)
            or data.get("checkpoint_iter") != int(checkpoint.stem.split("_")[-1])
            or data.get("envs") != config_row["envs"]
            or data.get("steps") != config_row["map_steps"]
            or data.get("command_suite") != suite
            or not wanted <= set(data.get("commands", {}))
            or data.get("eval_seed") != config_row["eval_seed"]
            or set(data.get("modes", {})) != {"eval_gt", "probe_prop_only", "eval_pred"}
            or not data.get("fixed_terrain")
            or len(data.get("terrain_tiles", [])) != 64
            or sorted(item.get("env") for item in data["terrain_tiles"]) != list(range(64))):
        raise EvidenceHold("map64 checkpoint, command, mode, or terrain receipt differs")
    for name in wanted:
        if tuple(data["commands"][name]) != command_values[name]:
            raise EvidenceHold(f"map64 {name} command value differs")
    for mode_name, mode in data["modes"].items():
        if not wanted <= set(mode):
            raise EvidenceHold("map64 command cases incomplete")
        for name in wanted:
            case = mode[name]
            if (case.get("env_count") != 64 or len(case.get("per_env", [])) != 64
                    or type(case.get("alive_envs_at_end")) is not int
                    or tuple(case.get("command", [])) != command_values[name]
                    or case.get("policy_steps_x_envs") != 64 * config_row["map_steps"]
                    or case.get("gt_used") != (64 * config_row["map_steps"]
                                               if mode_name == "eval_gt" else 0)
                    or sorted(item.get("env") for item in case["per_env"]) != list(range(64))):
                raise EvidenceHold(f"map64 {name} env evidence incomplete")
    return data


def _stand_rows(path: Path, checkpoint: Path, mode: str, cfg: dict) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if (data.get("format") != "foothold-ex40-stand/1"
            or data.get("checkpoint_sha256") != sha256(checkpoint)
            or data.get("mode") != mode or data.get("envs") != 64
            or data.get("seconds") != cfg["stand_seconds"]
            or data.get("skip_seconds") != cfg["stand_skip_seconds"]
            or data.get("contact_force_n") != cfg["stand"]["contact_force_n"]
            or data.get("conditions", {}).get("ground") != "plane z=0"
            or len(data.get("per_env", [])) != 64):
        raise EvidenceHold(f"flat stance {mode} source or shape differs")
    if sha256(path.parent / "stand_raw.npz") != data.get("raw_sha256"):
        raise EvidenceHold(f"flat stance {mode} raw SHA differs")
    if [row.get("env") for row in data["per_env"]] != list(range(64)):
        raise EvidenceHold("flat stance env IDs incomplete")
    return data["per_env"]


def _tracking(case: dict, command: tuple[float, float, float]) -> dict:
    fields = ("vx_abs_error_mean_alive_mps", "vy_abs_error_mean_alive_mps",
              "wz_abs_error_mean_alive_radps")
    selected = [field for field, value in zip(fields, command) if value]
    if not selected:
        return {}
    rows = case["per_env"]
    out = {}
    for field in selected:
        values = [_finite(row.get(field), field) for row in rows if row.get("samples_alive", 0) > 0]
        if len(values) < 60:
            raise EvidenceHold(f"{field} has fewer than 60 measured envs")
        out[field] = statistics.median(values)
    return out


def _stand_pass(row: dict, cfg: dict) -> bool:
    if row.get("valid_samples_after_1s", 0) < 1:
        return False
    speed = _finite(row.get("body_speed_mean_mps"), "body speed")
    yaw = _finite(row.get("abs_yaw_speed_mean_radps"), "yaw speed")
    if set(row.get("feet", {})) != {"FL_foot", "FR_foot", "RL_foot", "RR_foot"}:
        raise EvidenceHold("flat stance four-foot evidence incomplete")
    passed = bool(row.get("alive_at_end")) and speed <= cfg["body_speed_mean_mps_max"] and (
        yaw <= cfg["abs_yaw_speed_mean_radps_max"])
    for foot in row["feet"].values():
        contact = _finite(foot.get("contact_fraction_gt1n"), "contact")
        load = _finite(foot.get("mean_fz_over_mg"), "load")
        gap = _finite(foot.get("sole_gap_p95_m"), "gap")
        passed &= (contact >= cfg["contact_fraction_min_by_foot"]
                   and load >= cfg["mean_fz_over_mg_min_by_foot"]
                   and gap <= cfg["sole_gap_p95_m_max_by_foot"])
    return passed


def judge(checkpoint: Path, stage: str, evidence_dir: Path, config_path: Path,
          table_path: Path, arm: str, baseline: dict | None = None) -> tuple[dict, dict]:
    """Return score/2 and first-stage survival basis. Missing evidence is HOLD."""
    cfg = config(config_path)
    plan = Plan(table_path, arm=arm)
    stages = [item.id for item in plan.stages]
    if stage not in stages or stage not in cfg["stages"]:
        raise ValueError("unknown EX-40 stage")
    iteration = int(checkpoint.stem.split("_")[-1])
    if checkpoint.name != f"model_{iteration}.pt" or not checkpoint.is_file():
        raise ValueError("checkpoint path or iteration invalid")
    stage_cfg = cfg["stages"][stage]
    baseline = dict(baseline or {})
    problems, cells, new_baseline = [], {}, dict(baseline)
    source_paths = {}
    try:
        main_path = evidence_dir / "map64" / "map_modes.json"
        main = _map_rows(main_path, checkpoint, cfg)
        source_paths["map64"] = str(main_path)
        all_commands = commands("extended")
        for mode in stage_cfg["judge_modes"]:
            for name in stage_cfg["judge_commands"]:
                case = main["modes"][mode][name]
                alive = case["alive_envs_at_end"]
                if not 0 <= alive <= 64:
                    raise EvidenceHold("map64 survival outside 0 to 64")
                tracking = _tracking(case, all_commands[name])
                key = f"{mode}/{name}"
                if key not in new_baseline:
                    new_baseline[key] = alive
                if new_baseline[key] - alive > cfg["survival_drop_hold"]:
                    problems.append({"kind": "HOLD", "cell": key, "reason": "stage_first_checkpoint_survival_drop"})
                if alive < cfg["survival_min"]:
                    problems.append({"kind": "FAIL", "cell": key, "reason": "survival_below_60_of_64"})
                for field, value in tracking.items():
                    if value > cfg["tracking_error_max"]:
                        problems.append({"kind": "FAIL", "cell": key,
                                         "reason": f"{field}_above_tracking_limit"})
                cells[key] = {"alive_envs_at_end": alive, "tracking_medians": tracking}
            stand_path = evidence_dir / f"stand_{mode}" / "stand.json"
            source_paths[f"stand_{mode}"] = str(stand_path)
            stand = _stand_rows(stand_path, checkpoint, mode, cfg)
            passed = sum(_stand_pass(row, cfg["stand"]) for row in stand)
            cells[f"{mode}/flat_stand"] = {"passed_envs": passed, "envs": 64}
            if passed < cfg["stand"]["passed_envs_min"]:
                problems.append({"kind": "FAIL", "cell": f"{mode}/flat_stand",
                                 "reason": "flat_stance_below_60_of_64"})
        for mode in ({"eval_gt", "probe_prop_only", "eval_pred"} - set(stage_cfg["judge_modes"])):
            stand_path = evidence_dir / f"stand_{mode}" / "stand.json"
            source_paths[f"stand_{mode}"] = str(stand_path)
            stand = _stand_rows(stand_path, checkpoint, mode, cfg)
            cells[f"{mode}/flat_stand_record_only"] = {
                "passed_envs": sum(_stand_pass(row, cfg["stand"]) for row in stand), "envs": 64}
            for name in all_commands:
                cells[f"{mode}/{name}_record_only"] = {
                    "alive_envs_at_end": main["modes"][mode][name]["alive_envs_at_end"]}
        if stage_cfg.get("judge_walk_half"):
            for mode in stage_cfg["judge_modes"]:
                sequences = main.get("sequences", {}).get(mode, {})
                for name, phase_count in (("spin_left_to_right", 2),
                                          ("spin_right_to_left", 2),
                                          ("stop_and_restart", 4)):
                    phases = sequences.get(name, {}).get("phases", [])
                    if len(phases) != phase_count or any(
                            phase.get("env_count") != 64
                            or type(phase.get("alive_at_end")) is not int
                            for phase in phases):
                        raise EvidenceHold(f"W15 sequence {mode}/{name} incomplete")
                    cells[f"{mode}/{name}_diagnostic_only"] = {
                        "alive_by_phase": [phase["alive_at_end"] for phase in phases]}
        if stage_cfg["axis_goal"]:
            axis_path = evidence_dir / "axis_v2" / "axis_v2.json"
            axis = json.loads(axis_path.read_text(encoding="utf-8-sig"))
            source_paths["axis_v2"] = str(axis_path)
            if axis.get("checkpoint_sha256") != sha256(checkpoint) or axis.get("envs") != 64:
                raise EvidenceHold("W57 checkpoint or env receipt differs")
            for mode in stage_cfg["judge_modes"]:
                for name in cfg["axis_goal"]["cases"]:
                    case = axis["modes"][mode][name]
                    complete = case.get("stop_complete_envs")
                    error = _finite(case.get("stop_end_error_median_rad"), "goal stop error")
                    if type(complete) is not int or not 0 <= complete <= 64:
                        raise EvidenceHold("W57 goal stop completion missing")
                    cells[f"{mode}/{name}"] = {"stop_complete_envs": complete,
                                               "stop_end_error_median_rad": error}
                    if complete < cfg["axis_goal"]["complete_envs_min"] or error > cfg["axis_goal"]["stop_end_error_median_rad_max"]:
                        problems.append({"kind": "FAIL", "cell": f"{mode}/{name}",
                                         "reason": "goal_stop_threshold"})
        relative_names = set(stage_cfg.get("relative_commands", []))
        if relative_names or stage_cfg.get("judge_walk_half"):
            extra_path = evidence_dir / "map64_b3" / "map_modes.json"
            extra_names = relative_names | {"walk+0.5", "walk-0.5"}
            extra = _map_rows(extra_path, checkpoint, cfg, extra=True,
                              wanted_extra=extra_names)
            source_paths["map64_b3"] = str(extra_path)
            for mode in stage_cfg["judge_modes"]:
                for name in sorted(extra_names):
                    command = EX40_B3_COMMANDS[name]
                    case = extra["modes"][mode][name]
                    alive = case["alive_envs_at_end"]
                    if name in ("walk+0.5", "walk-0.5"):
                        tracking = _tracking(case, command)
                        key = f"{mode}/{name}"
                        if key not in new_baseline:
                            new_baseline[key] = alive
                        if new_baseline[key] - alive > cfg["survival_drop_hold"]:
                            problems.append({"kind": "HOLD", "cell": key,
                                             "reason": "stage_first_checkpoint_survival_drop"})
                        if alive < cfg["survival_min"] or any(
                                value > cfg["tracking_error_max"] for value in tracking.values()):
                            problems.append({"kind": "FAIL", "cell": key,
                                             "reason": "walk_half_survival_or_tracking_threshold"})
                        cells[key] = {"alive_envs_at_end": alive, "tracking_medians": tracking}
                        continue
                    if name not in relative_names:
                        cells[f"{mode}/{name}_record_only"] = {"alive_envs_at_end": alive}
                        continue
                    if name.startswith("slow"):
                        dt = _finite(extra.get("policy_dt_s"), "map policy dt")
                        realized = _finite(case.get("body_vx_integral_median_m"), "slow distance")
                        ratio = realized / (command[0] * extra["steps"] * dt)
                    else:
                        ratio = _finite(case.get("yaw_follow_median"), "turn follow")
                    cells[f"{mode}/{name}"] = {"alive_envs_at_end": alive, "follow_ratio": ratio}
                    if alive < cfg["survival_min"] or ratio < cfg["b3_relative_min"]:
                        problems.append({"kind": "FAIL", "cell": f"{mode}/{name}",
                                         "reason": "b3_relative_or_survival_threshold"})
        if stage == "T0":
            for name in ("fwd0.5", "fwd1.0"):
                gt = main["modes"]["eval_gt"][name]
                pred = main["modes"]["eval_pred"][name]
                gt_distance = _finite(gt.get("body_vx_integral_median_m"), "GT forward distance")
                pred_distance = _finite(pred.get("body_vx_integral_median_m"), "PRED forward distance")
                if (pred_distance < cfg["t0_pred_distance_ratio_min"] * gt_distance
                        or pred["alive_envs_at_end"] <
                        gt["alive_envs_at_end"] - cfg["t0_pred_survival_drop_max"]):
                    problems.append({"kind": "FAIL", "cell": f"eval_pred/{name}",
                                     "reason": "T0_pred_below_same_checkpoint_GT"})
    except (OSError, KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        if not isinstance(exc, EvidenceHold):
            exc = EvidenceHold(f"invalid evaluation evidence: {type(exc).__name__}: {exc}")
        problems.append({"kind": "HOLD", "cell": "evidence", "reason": str(exc)})
    verdict = "HOLD" if any(row["kind"] == "HOLD" for row in problems) else (
        "FAIL" if problems else "PASS")
    index = stages.index(stage)
    row = {"format": "foothold-ex40-score/2", "from": stage,
           "to": stages[index + 1] if index + 1 < len(stages) else None,
           "effective_schedule_sha256": plan.effective_sha256,
           "score_config_sha256": sha256(config_path),
           "checkpoint": str(checkpoint.resolve()), "checkpoint_iteration": iteration,
           "checkpoint_sha256": sha256(checkpoint),
           "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
           "verdict": verdict, "cells": cells, "problems": problems,
           "sources": source_paths, "judged_modes": stage_cfg["judge_modes"]}
    return row, new_baseline
