"""Read-only post-run receipt check for a lead-operated EX-40 Kit smoke."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import yaml

from foothold_s2.commands.mixed_core import EX39_SLOTS
from foothold_s2.curriculum.continuous import Plan
from foothold_s2.ex40_launch import BASELINE, INTENTIONAL_CURRICULUM_DIFFERENCE


REWARD_TERMS = {
    "track_ang_vel": "track_ang_vel",
    "track_lin_vel": "track_lin_vel",
    "joint_acc": "joint_acc",
    "hip_pos_penalty": "basic_hip_pos_penalty_l1",
    "thigh_calf_pos_l1": "ex39_thigh_calf_pos_l1",
    "four_foot_contact_at_stop": "ex39_four_foot_stop",
    "stand_gap": "ex40_stand_gap", "stand_load": "ex40_stand_load",
}



def _same_numbers(observed: dict, expected: dict) -> bool:
    if not isinstance(observed, dict) or set(observed) != set(expected):
        return False
    try:
        return all(math.isclose(float(observed[key]), float(value), rel_tol=0, abs_tol=1e-12)
                   for key, value in expected.items())
    except (TypeError, ValueError):
        return False


def _check_rewards(env_path: Path, plan: Plan) -> None:
    # Isaac Lab serializes resolved SceneEntityCfg slices with Python YAML tags.
    # BaseLoader reads their structure without instantiating any Python object.
    doc = yaml.load(env_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(doc, dict):
        raise ValueError("EX-40 Kit env YAML malformed")
    command = (doc.get("commands") or {}).get("base_velocity") or {}
    if str((command.get("params") or {}).get("curriculum_mode")).lower() != "true":
        raise ValueError("EX-40 Kit command curriculum mode is off")
    if str(command.get("flag_stride")) != "0" or str(command.get("dynamic_flags")).lower() != "false":
        raise ValueError("EX-40 Kit command slots require all envs to use free velocity sampling")
    rewards = doc.get("rewards") or {}
    baseline = yaml.load((BASELINE / "env.yaml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if doc.get("events") != baseline.get("events"):
        raise ValueError("D68 B0 events differs from S-B10 saved configuration")
    expected_curriculum = copy.deepcopy(baseline.get("curriculum"))
    if (not isinstance(expected_curriculum, dict)
            or not isinstance(expected_curriculum.get("terrain_levels"), dict)
            or expected_curriculum["terrain_levels"].get("params") != {}):
        raise ValueError("D68 S-B10 terrain curriculum baseline changed")
    # Decision 8 changes only the frame used to score terrain promotion.
    # BaseLoader preserves YAML booleans as the strings "true" and "false".
    expected_curriculum["terrain_levels"]["params"] = {
        "mask_new_task": "false", "world_frame": "true"}
    if doc.get("curriculum") != expected_curriculum:
        raise ValueError("D68 B0 curriculum differs from S-B10 plus decision 8")
    terrain = ((doc.get("scene") or {}).get("terrain") or {}).get("terrain_generator")
    expected_terrain = baseline["scene"]["terrain"]["terrain_generator"]
    if terrain != expected_terrain:
        raise ValueError("D68 B0 terrain generator differs from S-B10")
    if (str(command.get("seed")) != str(baseline["commands"]["base_velocity"]["seed"])
            or command.get("resampling_time_range") != baseline["commands"]["base_velocity"]["resampling_time_range"]):
        raise ValueError("D68 B0 command seed or resample interval differs from S-B10")
    for source, baseline_row in (baseline.get("rewards") or {}).items():
        row = rewards.get(source) or {}
        expected = plan.stages[0].rewards.get(source, float(baseline_row["weight"]))
        if not math.isclose(float(row.get("weight", "nan")), expected,
                            rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"D68 B0 reward differs from S-B10: {source}")
    for source, actual_name in REWARD_TERMS.items():
        row = rewards.get(actual_name) or {}
        try:
            actual = float(row["weight"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"EX-40 Kit reward weight missing: {actual_name}") from exc
        expected = plan.stages[0].rewards[source]
        if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"EX-40 Kit reward weight differs from stage table: {actual_name}")
    for i in range(4):
        ray = ((doc.get("scene") or {}).get(f"ex40_support_{i}") or {})
        if (str(ray.get("prim_path", "")).find("_foot") < 0
                or ray.get("ray_alignment") != "yaw"
                or str((ray.get("offset") or {}).get("pos", "")).find("-0.002") < 0):
            raise ValueError("EX-40 dedicated collision-center foot support ray missing")


def _check_stand_sensor(run: Path) -> dict:
    rows = [json.loads(line) for line in (run / "train_extra.jsonl").read_text(
        encoding="utf-8").splitlines()]
    if [row.get("it") for row in rows] != list(range(15)):
        raise ValueError("EX-40 stand sensor evidence needs all 15 smoke updates")
    total_hits = 0
    valid_hits = 0
    flat_samples = 0
    for row in rows:
        sensor = row.get("ex40_stand_sensor") or {}
        total = sensor.get("stand_foot_total")
        valid = sensor.get("hit_valid_count")
        ratio = sensor.get("hit_valid_ratio")
        flat_count = sensor.get("flat_stand_valid_foot_count")
        flat_p50 = sensor.get("flat_gap_p50_mm")
        if (type(total) is not int or total < 0 or type(valid) is not int
                or not 0 <= valid <= total
                or (total and (not isinstance(ratio, (int, float))
                    or not math.isfinite(ratio) or not math.isclose(
                        ratio, valid / total, abs_tol=1e-12)))
                or (not total and ratio is not None)
                or type(flat_count) is not int or flat_count < 0
                or (flat_count and (not isinstance(flat_p50, (int, float))
                    or not math.isfinite(flat_p50) or not 0 <= flat_p50 <= 10))
                or not isinstance(sensor.get("hit_origin_samples"), list)):
            raise ValueError(f"EX-40 stand ray hit or flat gap evidence failed at update {row.get('it')}")
        for key in ("hit_invalid_by_foot", "force_nonfinite_by_foot", "gap_nonfinite_by_foot"):
            counts = sensor.get(key)
            if (not isinstance(counts, list) or len(counts) != 4
                    or any(type(value) is not int or value < 0 for value in counts)):
                raise ValueError("EX-40 stand sensor fault counters malformed")
        if sum(sensor["hit_invalid_by_foot"]) != total - valid:
            raise ValueError("EX-40 stand sensor fault counters malformed")
        if valid and not sensor["hit_origin_samples"]:
            raise ValueError("EX-40 stand hit versus terrain origin samples missing")
        total_hits += total
        valid_hits += valid
        flat_samples += flat_count
    if total_hits == 0 or valid_hits / total_hits < .99 or flat_samples == 0:
        raise ValueError("EX-40 stand ray hit or flat gap evidence insufficient")
    return {"updates": 15, "aggregate_hit_valid_ratio": valid_hits / total_hits,
            "flat_stand_valid_foot_count": flat_samples,
            "flat_gap_p50_range_mm": [0, 10]}


def _check_stage_log(rows: list[dict], plan: Plan, env_count: int) -> dict[str, int]:
    physical = [row for row in rows if row.get("event") == "physical_resume_reset"]
    if physical:
        raise ValueError("D68 scratch Kit smoke must not resume a parent")
    entered = [row for row in rows if row.get("event") == "stage_enter"]
    expected = [(stage.id, stage.fixed_update) for stage in plan.stages]
    if [(row.get("to"), row.get("iteration")) for row in entered] != expected:
        raise ValueError("EX-40 Kit did not enter all planned stages at their update boundaries")
    for index, (row, stage) in enumerate(zip(entered, plan.stages)):
        if (row.get("curriculum_sha256") != plan.sha256
                or row.get("effective_schedule_sha256") != plan.effective_sha256):
            raise ValueError(f"EX-40 Kit stage hash differs: {stage.id}")
        if index == 0:
            changed = row.get("changed") or {}
            if (not _same_numbers(changed.get("rewards") or {}, stage.rewards)
                    or set(changed.get("command_slots") or []) != set(stage.shares)):
                raise ValueError("D68 Kit B0 command slots or rewards differ from stage table")
        else:
            ranges = row.get("ranges") or {}
            if (not _same_numbers(row.get("shares"), stage.shares)
                    or not isinstance(ranges, dict) or set(ranges) != set(stage.ranges)
                    or any(tuple(ranges[key]) != stage.ranges[key] for key in ranges)
                    or row.get("force_gt") is not stage.force_gt
                    or row.get("pending_envs") != env_count):
                raise ValueError(f"EX-40 Kit stage shares, ranges, or map policy differ: {stage.id}")
            if row.get("changed", {}).get("rewards_added", {}) != stage.adds.get("rewards", {}):
                raise ValueError(f"D68 Kit stage reward activation differs: {stage.id}")
    changed_by_stage = {stage.id: 0 for stage in plan.stages[1:]}
    remaining_by_stage = {stage.id: env_count for stage in plan.stages[1:]}
    current = "B0"
    for row in rows:
        if row.get("event") == "stage_enter":
            current = row["to"]
        if row.get("event") != "env_reset_applied":
            continue
        name = row.get("to")
        if name != current or name not in changed_by_stage:
            raise ValueError("EX-40 Kit reset adoption belongs to wrong stage")
        count = row.get("changed_envs")
        remaining = row.get("remaining_old_envs")
        stage = next(stage for stage in plan.stages if stage.id == name)
        policy = "forced_gt" if stage.force_gt else "AdaSmpl_pred_eligible"
        p = row.get("adasmpl_p")
        if (type(count) is not int or count <= 0
                or type(remaining) is not int or remaining != remaining_by_stage[name] - count
                or row.get("map_source_policy") != policy
                or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1):
            raise ValueError(f"EX-40 Kit positive reset adoption or map policy missing: {name}")
        changed_by_stage[name] += count
        remaining_by_stage[name] = remaining
    if any(count <= 0 for count in changed_by_stage.values()):
        raise ValueError("EX-40 Kit needs positive reset adoption in each promoted stage")
    return changed_by_stage


def _check_consumption(rows: list[dict], plan: Plan, changed_by_stage: dict[str, int]) -> dict[str, dict]:
    result = {}
    for stage in plan.stages[1:]:
        name = stage.id
        command_rows = [row for row in rows if row.get("event") == "stage_command_consumed"
                        and row.get("to") == name]
        map_rows = [row for row in rows if row.get("event") == "stage_map_consumed"
                    and row.get("to") == name]
        command_n = 0
        slot_totals = {slot: 0 for slot in EX39_SLOTS}
        for row in command_rows:
            n = row.get("sampled_envs")
            slots = row.get("slot_counts")
            if (type(n) is not int or n <= 0 or not isinstance(slots, dict)
                    or set(slots) != set(EX39_SLOTS)
                    or any(type(value) is not int or value < 0 for value in slots.values())
                    or sum(slots.values()) != n or row.get("command_bad_count") != 0
                    or type(row.get("heading_count")) is not int
                    or not 0 <= row["heading_count"] <= n
                    or (plan.arm == "A" and row["heading_count"] != 0)):
                raise ValueError(f"EX-40 Kit consumed command evidence invalid: {name}")
            command_n += n
            for slot, value in slots.items():
                slot_totals[slot] += value
        if command_n != changed_by_stage[name]:
            raise ValueError(f"EX-40 Kit reset and consumed command counts differ: {name}")
        for slot, observed in slot_totals.items():
            expected = stage.shares.get(slot, 0.0)
            if expected == 0 and observed:
                raise ValueError(f"EX-40 Kit sampled a disabled command slot: {name}/{slot}")
            # A smoke has few newly reset envs. Five binomial standard errors
            # catches a gross ratio mismatch without requiring exact random counts.
            tolerance = 5 * math.sqrt(expected * (1 - expected) / command_n) + 1 / command_n
            if abs(observed / command_n - expected) > tolerance:
                raise ValueError(f"EX-40 Kit consumed command ratio differs from stage: {name}/{slot}")
        map_n = 0
        for row in map_rows:
            n = row.get("reset_envs")
            gt = row.get("use_gt_envs")
            p = row.get("adasmpl_p")
            if (type(n) is not int or n <= 0 or type(gt) is not int or not 0 <= gt <= n
                    or row.get("force_gt_runtime") is not stage.force_gt
                    or (stage.force_gt and gt != n)
                    or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1):
                raise ValueError(f"EX-40 Kit consumed map reset evidence invalid: {name}")
            map_n += n
        if map_n < changed_by_stage[name]:
            raise ValueError(f"EX-40 Kit reset and consumed map counts differ: {name}")
        result[name] = {"reset_envs": changed_by_stage[name], "sampled_command_envs": command_n,
                        "map_reset_envs": map_n,
                        "sampled_slot_fraction": {slot: count / command_n for slot, count in slot_totals.items()
                                                  if slot in stage.shares}}
    return result


def check(receipt_path: Path, run_log: Path, rc: int) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    if receipt.get("state") != "CPU_PREPARED_NOT_LAUNCHED" or receipt.get("stage_boundaries") != {
            "B0": 0, "B1": 3, "B2": 6, "B3": 9, "T0": 12}:
        raise ValueError("EX-40 smoke launch receipt or stage boundaries differ")
    if rc != 0 or "Traceback" in run_log.read_text(encoding="utf-8", errors="replace"):
        raise ValueError("EX-40 Kit child failed or traceback present")
    root = Path(receipt["argv"][receipt["argv"].index("--basic-log-root") + 1]) / "smoke"
    runs = [p for p in root.glob(f"EX-40-{receipt['arm']}-kit-smoke_*") if p.is_dir()]
    if len(runs) != 1:
        raise ValueError("EX-40 smoke must have exactly one isolated child run")
    run = runs[0]
    args = receipt["argv"]
    table = Path(args[args.index("--curriculum") + 1])
    plan = Plan(table, arm=receipt["arm"], smoke_boundaries=(3, 6, 9, 12))
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
    modes = manifest.get("modes") or {}
    cfg = modes.get("continuous_curriculum") or {}
    if (cfg.get("sha256") != receipt.get("curriculum_sha256")
            or cfg.get("effective_schedule_sha256") != receipt.get("effective_schedule_sha256")
            or cfg.get("arm") != receipt["arm"]
            or modes.get("contract") != "basic_gait_ex40"):
        raise ValueError("EX-40 actual Kit manifest differs from CPU launch contract")
    start = json.loads((run / "curriculum_start_receipt.json").read_text(encoding="utf-8-sig"))
    if (start.get("start") != "scratch" or start.get("num_envs") != 3072
            or start.get("env_seed") != 42 or start.get("command_seed") != 0
            or start.get("stand_reward") != {"four_foot_contact": 0.1,
                                               "gap": plan.stand_cfg["gap_weight"],
                                               "load": plan.stand_cfg["load_weight"]}):
        raise ValueError("EX-40 actual Kit env/command seed or env count differs")
    if (plan.sha256 != receipt.get("curriculum_sha256")
            or plan.effective_sha256 != receipt.get("effective_schedule_sha256")):
        raise ValueError("EX-40 Kit stage table differs from pinned launch receipt")
    _check_rewards(run / "params/env.yaml", plan)
    stand_sensor = (_check_stand_sensor(run)
                    if receipt.get("stand_sensor_evidence") == "ex40-v4" else None)
    rows = [json.loads(line) for line in (run / "stage_log.jsonl").read_text(encoding="utf-8").splitlines()]
    changed_by_stage = _check_stage_log(rows, plan, start["num_envs"])
    consumed = _check_consumption(rows, plan, changed_by_stage)
    entered = [(stage.id, stage.fixed_update) for stage in plan.stages]
    status = json.loads((run / "train_start_status.json").read_text(encoding="utf-8-sig"))
    if status.get("state") != "done" or status.get("iter") != 14 or not (run / "model_14.pt").is_file():
        raise ValueError("D70 Kit smoke did not complete and save model_14")
    checkpoint_sha = hashlib.sha256((run / "model_14.pt").read_bytes()).hexdigest()
    if status.get("sha256") != checkpoint_sha:
        raise ValueError("EX-40 completed checkpoint SHA and status differ")
    return {"state": "PASS", "run_dir": str(run), "stages": entered,
            "intentional_baseline_differences": [INTENTIONAL_CURRICULUM_DIFFERENCE],
            "reset_adoptions": changed_by_stage,
            "stage_consumption": consumed,
            "shares_checked": True, "reward_weights_checked": True,
            "stand_sensor_checked": stand_sensor,
            "checkpoint": str(run / "model_14.pt"), "checkpoint_sha256": checkpoint_sha}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--run-log", type=Path, required=True)
    p.add_argument("--rc", type=int, required=True)
    a = p.parse_args(argv)
    print(json.dumps(check(a.receipt, a.run_log, a.rc), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
