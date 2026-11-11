"""EX-42 maintenance measurements. Missing evidence or baseline yields HOLD."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import yaml

from foothold_s2.eval.axis_v2_cells import case_specs
from foothold_s2.eval.ex42_foot_metrics import FOOT_ORDER, per_env as foot_per_env
from foothold_s2.eval.map_mode_cells import commands as expected_commands
from foothold_s2.experiment_registry import load_experiment, source_path

ROOT = Path(__file__).resolve().parents[1]
MODES = ("eval_gt", "probe_prop_only", "eval_pred")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def config(path=None):
    definition = load_experiment("EX-42")
    path = Path(path) if path else source_path(definition, "score_config")
    cfg = _json(path)
    plan = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text(encoding="utf-8-sig"))
    ids = [row["id"] for row in plan["maintenance"]["items"]]
    if (cfg.get("format") != "foothold-ex42-score-config/1" or
            cfg.get("status") not in ("measurement_ready_baseline_unpinned", "e0_parent_baseline_pinned") or
            cfg.get("maintenance_ids") != ids or
            cfg.get("verdict_when_baseline_absent") != "HOLD" or
            cfg.get("modes") != list(MODES)):
        raise ValueError("EX-42 score config disagrees with maintenance plan")
    if cfg["status"] == "e0_parent_baseline_pinned":
        from foothold_s2.ex42_e0_judge import load_baseline, validate_measured_q4
        pin = cfg.get("baseline")
        measured = plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        if not isinstance(pin, dict) or not isinstance(measured, dict):
            raise ValueError("EX-42 E0 parent baseline or q4 measured values missing")
        baseline = load_baseline(ROOT, cfg, digest)
        if (measured.get("baseline_sha256") != pin["sha256"] or
                measured.get("calibration_sha256") != baseline["calibration_sha256"] or
                measured.get("parent_checkpoint_sha256") != baseline["checkpoint_sha256"]):
            raise ValueError("EX-42 E0 score config and prep measured pin differ")
        validate_measured_q4(baseline, measured,
                             plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["assumed"])
    elif cfg.get("baseline") is not None:
        raise ValueError("EX-42 unpinned score config has a baseline")
    return cfg, path


def _receipt_raw(folder, row, name, sha_field):
    path = folder / name
    if not path.is_file() or row.get(sha_field) != digest(path):
        raise ValueError(f"EX-42 raw receipt missing or SHA differs: {path}")
    return path


def _median(values, label):
    if not values:
        return None
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError(f"EX-42 {label} has nonfinite or nonnumeric evidence")
    return float(np.median(values))


def measure(checkpoint, evaluation, config_path=None, *, expected_seed=None,
            expected_mesh_sha256=None, stage_id=None):
    """Read durable Kit artifacts; never infer a pass from an EX-41 score."""
    cfg, cfg_path = config(config_path)
    seed = cfg["eval_seed"] if expected_seed is None else expected_seed
    if type(seed) is not int or seed < 0:
        raise ValueError("EX-42 evaluation seed must be a nonnegative integer")
    checkpoint, evaluation = Path(checkpoint).resolve(strict=True), Path(evaluation)
    checkpoint_sha = digest(checkpoint)
    map_dir = evaluation / "map64"
    map_row = _json(map_dir / "map_modes.json")
    if expected_mesh_sha256 and map_row.get("ex42_mesh", {}).get("mesh_sha256") != expected_mesh_sha256:
        raise ValueError("EX-42 map64 combined mesh SHA differs")
    if expected_mesh_sha256:
        from foothold_s2.eval.ex42_mesh_eval import validate_eval_cell

        validate_eval_cell(map_row, map_row["ex42_mesh"])
    if (map_row.get("checkpoint_sha256") != checkpoint_sha or
            map_row.get("envs") != cfg["envs"] or map_row.get("steps") != cfg["steps"] or
            map_row.get("eval_seed") != seed or
            map_row.get("command_suite") != cfg["map_command_suite"] or
            not map_row.get("dr_off") or not map_row.get("curriculum_off") or
            set(map_row.get("modes", {})) != set(MODES)):
        raise ValueError("EX-42 map64 conditions or checkpoint differ")
    commands = map_row.get("commands", {})
    if (commands != {key: list(value) for key, value in expected_commands("extended").items()} or
            any(set(map_row["modes"][mode]) != set(commands) for mode in MODES)):
        raise ValueError("EX-42 map64 extended 13-command coverage incomplete")
    out = {"format": "foothold-ex42-maintenance-score/1", "checkpoint": str(checkpoint),
           "checkpoint_sha256": checkpoint_sha, "score_config_sha256": digest(cfg_path),
           "maintenance_source_sha256": digest(ROOT / cfg["maintenance_source"]),
           "baseline": None, "judgement": "HOLD", "reason": "EX-42 maintenance baseline and repeat width not pinned",
           "conditions": {"envs": cfg["envs"], "steps": cfg["steps"],
                          "eval_seed": seed, "modes": list(MODES)},
           "map64": {}, "stand": {}, "axis_v2": {}, "maintenance_items": {}}
    for mode in MODES:
        out["map64"][mode] = {}
        for case, entry in map_row["modes"][mode].items():
            rows = entry["per_env"]
            if len(rows) != cfg["envs"] or any(r.get("env") != i for i, r in enumerate(rows)):
                raise ValueError(f"EX-42 map64 {mode}/{case} per-env coverage differs")
            def median(key):
                values = [r[key] for r in rows if r.get(key) is not None]
                return _median(values, f"map64 {mode}/{case}/{key}")
            out["map64"][mode][case] = {
                "alive_at_end": sum(bool(r["alive_at_end"]) for r in rows),
                "vx_abs_error_median_mps": median("vx_abs_error_mean_alive_mps"),
                "vy_abs_error_median_mps": median("vy_abs_error_mean_alive_mps"),
                "wz_abs_error_median_radps": median("wz_abs_error_mean_alive_radps"),
                "command_projection_median_m": median("command_xy_projection_integral_m"),
            }
    for mode in MODES:
        folder = evaluation / f"stand_{mode}"
        row = _json(folder / "stand.json")
        if (row.get("format") != "foothold-ex40-stand/1" or row.get("mode") != mode or
                row.get("checkpoint_sha256") != checkpoint_sha or row.get("envs") != cfg["envs"] or
                row.get("conditions", {}).get("seed") != seed or
                len(row.get("per_env", [])) != cfg["envs"] or
                row.get("seconds") != cfg["stand_seconds"] or
                row.get("skip_seconds") != cfg["stand_skip_seconds"] or
                row.get("contact_force_n") != cfg["stand_contact_n"]):
            raise ValueError(f"EX-42 stand {mode} conditions differ")
        _receipt_raw(folder, row, "stand_raw.npz", "raw_sha256")
        feet = row.get("feet")
        if tuple(feet or ()) != FOOT_ORDER:
            raise ValueError("EX-42 stand foot order differs")
        out["stand"][mode] = {"alive_at_end": sum(bool(r["alive_at_end"]) for r in row["per_env"]),
                              "per_foot_contact_fraction_median": {
                                  foot: _median([r["feet"][foot]["contact_fraction_gt1n"]
                                                 for r in row["per_env"]], f"stand {mode}/{foot}")
                                  for foot in FOOT_ORDER}}
    axis_dir = evaluation / "axis_v2"
    axis = _json(axis_dir / "axis_v2.json")
    if expected_mesh_sha256 and axis.get("ex42_mesh", {}).get("mesh_sha256") != expected_mesh_sha256:
        raise ValueError("EX-42 W57 combined mesh SHA differs")
    if expected_mesh_sha256:
        from foothold_s2.eval.ex42_mesh_eval import validate_eval_cell

        validate_eval_cell(axis, axis["ex42_mesh"], fixed_level=cfg["axis_fixed_level"])
    marker = axis.get("ex42_maintenance", {})
    if (axis.get("schema") != "foothold-axis-v2/1" or axis.get("checkpoint_sha256") != checkpoint_sha or
            axis.get("envs") != cfg["envs"] or axis.get("steps") != cfg["steps"] or
            axis.get("eval_seed") != seed or axis.get("fixed_level") != cfg["axis_fixed_level"] or
            not axis.get("dr_off") or not axis.get("curriculum_off") or
            tuple(axis.get("foot_order", ())) != FOOT_ORDER or
            marker.get("schema") != "foothold-ex42-foot-xy/1" or
            set(axis.get("modes", {})) != set(MODES)):
        raise ValueError("EX-42 W57 axis conditions or foot speed marker differ")
    expected_cases = {spec["name"] for spec in case_specs()}
    for mode in MODES:
        if set(axis["modes"][mode]) != expected_cases:
            raise ValueError(f"EX-42 W57 {mode} case coverage differs")
        out["axis_v2"][mode] = {}
        for case, row in axis["modes"][mode].items():
            raw = _receipt_raw(axis_dir, row, row["raw_file"], "raw_sha256")
            with np.load(raw, allow_pickle=False) as z:
                for key in ("alive", "contact", "foot_xy_speed_mps", "dt"):
                    if key not in z:
                        raise ValueError(f"EX-42 W57 raw lacks {key}: {raw}")
                if z["alive"].shape != (cfg["steps"], cfg["envs"]) or not math.isclose(
                        float(z["dt"]), axis["dt_s"], rel_tol=0, abs_tol=1e-9):
                    raise ValueError(f"EX-42 W57 raw shape or dt differs: {raw}")
                feet = foot_per_env(z["alive"], z["contact"], z["foot_xy_speed_mps"], float(z["dt"]))
            if len(feet) != cfg["envs"] or len(row.get("per_env", [])) != cfg["envs"]:
                raise ValueError("EX-42 W57 per-env coverage differs")
            valid = [r for r in feet if r["valid_steps"]]
            out["axis_v2"][mode][case] = {
                "alive_at_end": row["alive_at_end"],
                "yaw_signed_accum_median_rad": row.get("yaw_final_minus_start_median_rad"),
                "yaw_by_terrain_kind": row["by_terrain_kind"],
                "stop_complete_envs": row.get("stop_complete_envs"),
                "duty_by_foot_median": [_median([r["duty_by_foot"][i] for r in valid],
                                                 f"duty {mode}/{case}/{i}") for i in range(4)],
                "phase_from_FL_cycle_median": [_median(vals, f"phase {mode}/{case}/{i}") for i, vals in enumerate(
                    ([r["phase_from_FL_cycle"][i] for r in valid
                      if r["phase_from_FL_cycle"][i] is not None] for i in range(4)))],
                "foot_drag_proxy_m_by_foot_median": [_median([r["foot_drag_proxy_m_by_foot"][i]
                                            for r in valid], f"drag {mode}/{case}/{i}") for i in range(4)],
                "raw_file": str(raw), "raw_sha256": row["raw_sha256"]}
    sources = {
        "survival": "map64.*.*.alive_at_end",
        "tracking_vx_vy": "map64.*.*.vx_abs_error_median_mps/vy_abs_error_median_mps",
        "tracking_wz": "map64.*.*.wz_abs_error_median_radps",
        "command_projection": "map64.*.*.command_projection_median_m",
        "per_foot_contact": "stand.*.per_foot_contact_fraction_median + axis_v2.*.*.duty_by_foot_median",
        "gait_phase_and_duty": "axis_v2.*.*.phase_from_FL_cycle_median/duty_by_foot_median",
        "foot_drag_m": "axis_v2.*.*.foot_drag_proxy_m_by_foot_median",
        "yaw_integral": "axis_v2.*.*.yaw_signed_accum_median_rad/yaw_by_terrain_kind",
        "W57_spin_survival": "map64.*.spin+1.2/spin-1.2.alive_at_end",
        "parent_cumulative_drop": None,
        "calibration_repeat_width": None,
    }
    for item in cfg["maintenance_ids"]:
        out["maintenance_items"][item] = {
            "evidence": sources[item],
            "state": "measured_unjudged" if sources[item] else "missing_parent_or_repeat_evidence",
            "judgement": "HOLD",
        }
    out["maintenance_items"]["W57_spin_survival"]["by_mode_and_direction"] = {
        mode: {case: out["map64"][mode][case]["alive_at_end"]
               for case in ("spin+1.2", "spin-1.2")} for mode in MODES}
    if cfg["status"] == "e0_parent_baseline_pinned" and stage_id == "E0":
        from foothold_s2.ex42_e0_judge import judge, load_baseline
        baseline = load_baseline(ROOT, cfg, digest)
        baseline["_sha256"] = cfg["baseline"]["sha256"]
        plan = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text(encoding="utf-8-sig"))
        measured = plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        out = judge(out, baseline, measured)
    elif cfg["status"] == "e0_parent_baseline_pinned" and stage_id == "E1":
        from foothold_s2.ex42_e0_judge import load_baseline
        from foothold_s2.ex42_e1_judge import judge_e1, previous_e1_score
        baseline = load_baseline(ROOT, cfg, digest)
        baseline["_sha256"] = cfg["baseline"]["sha256"]
        plan = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text(encoding="utf-8-sig"))
        measured = plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        prior = previous_e1_score(checkpoint, evaluation,
                                  plan["evaluation"]["interval_updates"], digest(cfg_path))
        out = judge_e1(out, baseline, measured, plan, previous=prior)
    elif cfg["status"] == "e0_parent_baseline_pinned":
        out["reason"] = "E0 baseline is pinned; this stage requires its own judgment policy"
    return out
