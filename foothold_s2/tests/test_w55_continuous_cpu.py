"""D68 scratch EX-40 known inputs and mutations, without Isaac or GPU."""

from __future__ import annotations

import copy
import ast
import hashlib
import inspect
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml

from foothold_s2.commands.mixed_core import EX39_SLOTS, apply_stage_heading, make_generator, resample_stage
from foothold_s2.curriculum.continuous import Plan, Runtime, command_bad
from foothold_s2.curriculum.ex40_dr import dr_scale
from foothold_s2.ex40_kit_smoke import check as check_kit_smoke
from foothold_s2.ex40_launch import BASELINE, TABLE, build_args, receipt
from foothold_s2.prestart_check import actual_parser
from foothold_s2.rewards.basic_gait_bundle import (
    apply_ex40_stand_settings, stand_penalty_values, scheduled_lin_vel_z_weight,
)


def _mutated(tmp_path, change):
    doc = yaml.safe_load(TABLE.read_text(encoding="utf-8"))
    change(doc)
    path = tmp_path / "mutant.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def test_scratch_stages_and_baseline_pins(tmp_path):
    plan = Plan(TABLE, arm="A")
    assert [(s.id, s.fixed_update) for s in plan.stages] == [
        ("B0", 0), ("B1", 1501), ("B2", 3001), ("B3a", 4501),
        ("B3b", 5001), ("B3c", 5501), ("D", 6001), ("T0", 7501)]
    assert plan.parent_sha256 is None
    assert hashlib.sha256((BASELINE / "env.yaml").read_bytes()).hexdigest() == plan.baseline_env_yaml_sha256
    assert hashlib.sha256((BASELINE / "agent.yaml").read_bytes()).hexdigest() == plan.baseline_agent_yaml_sha256
    assert plan.stages[0].rewards == {
        "track_ang_vel": 1.0, "track_lin_vel": 2.0, "joint_acc": -1e-7,
        "hip_pos_penalty": -.05, "thigh_calf_pos_l1": -.01,
        "four_foot_contact_at_stop": .1, "stand_gap": -.2, "stand_load": -.1}
    assert plan.stages[0].shares == {"forward": .72, "spin_left": .09,
                                     "spin_right": .09, "stand": .10}
    assert plan.stages[1].rewards == plan.stages[0].rewards
    assert not plan.stages[-1].force_gt
    with pytest.raises(ValueError, match="scratch"):
        Plan(_mutated(tmp_path, lambda d: d.update(parent_update=1500)), arm="A")
    with pytest.raises(ValueError, match="sum to 100"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][0]["shares"].update(forward=.8)), arm="A")
    with pytest.raises(ValueError, match="B0 reward terms incomplete"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][0]["adds"]["rewards"].pop(
            "stand_gap")), arm="A")
    with pytest.raises(ValueError, match="range narrows"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][2]["ranges"].update(
            reverse_vx=[-.7, -.2])), arm="A")


def test_b0_commands_are_start_distribution_plus_stand():
    plan = Plan(TABLE, arm="B")
    n = 100_000
    out = resample_stage(make_generator(0), n, plan.stages[0], torch.zeros(n))
    assert not command_bad(out["cmd"], out["slot"], out["heading"],
                           torch.zeros(n, dtype=torch.long), plan).any()
    counts = torch.bincount(out["slot"], minlength=len(EX39_SLOTS)).float() / n
    for slot, frac in plan.stages[0].shares.items():
        assert abs(float(counts[EX39_SLOTS.index(slot)]) - frac) < .01
    fwd = out["slot"] == EX39_SLOTS.index("forward")
    assert .48 < float(out["heading"][fwd].float().mean()) < .52
    assert not out["heading"][~fwd].any()
    assert torch.all(out["cmd"][out["slot"] == EX39_SLOTS.index("stand")] == 0)
    broken = out["cmd"].clone()
    broken[0, 1] = .3
    bad = command_bad(broken, out["slot"], out["heading"],
                      torch.zeros(n, dtype=torch.long), plan)
    assert bad[0] and int(bad.sum()) == 1


def test_heading_caps_and_b2_target_spin():
    plan = Plan(TABLE, arm="B")
    out = apply_stage_heading(torch.zeros((2, 3)), torch.ones(2, dtype=torch.bool),
        torch.zeros(2, dtype=torch.bool), torch.full((2,), 3.14159265), torch.zeros(2),
        torch.tensor([0, EX39_SLOTS.index("spin_left")]), torch.tensor([0, 2]), plan.stages)
    assert torch.allclose(out[:, 2], torch.tensor([0.5, 1.5]))
    sampled = resample_stage(make_generator(4), 100_000, plan.stages[2], torch.zeros(100_000))
    spin = (sampled["slot"] == EX39_SLOTS.index("spin_left")) | (
        sampled["slot"] == EX39_SLOTS.index("spin_right"))
    assert .27 < sampled["heading"][spin].float().mean().item() < .33


class _Manager:
    def __init__(self):
        self.weights = {name: SimpleNamespace(weight=0.0) for name in
                        ("track_ang_vel", "track_lin_vel", "joint_acc",
                         "basic_hip_pos_penalty_l1", "ex39_thigh_calf_pos_l1",
                         "ex39_four_foot_stop", "ex40_stand_gap", "ex40_stand_load")}

    def get_term_cfg(self, name):
        return self.weights[name]

    def set_term_cfg(self, name, cfg):
        self.weights[name] = cfg


def test_b0_to_b1_reward_and_reset_boundary(tmp_path):
    plan = Plan(TABLE, arm="A", smoke_boundaries=(3, 6, 9, 12, 15))
    runtime = Runtime(plan, 4, "cpu", tmp_path)
    manager = _Manager()
    runner = SimpleNamespace(env=SimpleNamespace(unwrapped=SimpleNamespace(reward_manager=manager)),
                             adasmpl=SimpleNamespace(force_gt=True, p=1.0), pcfg={"force_gt": True},
                             perception=SimpleNamespace(cfg=SimpleNamespace(force_gt=True)))
    runtime.attach(runner, SimpleNamespace())
    runtime.start()
    assert runtime.active == 0 and runner.basic_lin_vel_z_schedule is False
    runtime.on_update_start(1)
    assert runtime.active == 0
    runtime.on_update_start(2)
    assert runtime.active == 0
    runtime.on_update_start(3)
    assert runtime.active == 1 and runner.basic_lin_vel_z_schedule is True
    assert runner.basic_lin_vel_z_start_iteration == 3
    assert scheduled_lin_vel_z_weight(3, start_iteration=3) == -2
    assert scheduled_lin_vel_z_weight(753, start_iteration=3) == -1
    assert scheduled_lin_vel_z_weight(1503, start_iteration=3) == 0
    assert manager.weights["track_ang_vel"].weight == 1.0
    assert manager.weights["basic_hip_pos_penalty_l1"].weight == -.05
    assert manager.weights["ex39_thigh_calf_pos_l1"].weight == -.01
    assert runtime.env_stage.tolist() == [0, 0, 0, 0]
    runtime.on_reset(torch.tensor([1, 3]))
    assert runtime.env_stage.tolist() == [0, 1, 0, 1]
    rows = [json.loads(line) for line in (tmp_path / "stage_log.jsonl").read_text().splitlines()]
    assert [(r["to"], r["iteration"]) for r in rows if r["event"] == "stage_enter"] == [
        ("B0", 0), ("B1", 3)]
    with pytest.raises(ValueError, match="scratch"):
        Runtime(plan, 1, "cpu", tmp_path / "bad").start("0" * 64)


def test_actual_parser_and_scratch_receipt(tmp_path):
    for smoke, final in ((True, 18), (False, 8001)):
        args = build_args(arm="A", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                          log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=smoke)
        parsed, unknown = actual_parser().parse_known_args([
            "--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB", *args])
        assert parsed.max_iterations == final and parsed.resume_from is None
        assert parsed.clock_scatter == "off" and unknown[-1].startswith("--kit_args=")
        row = receipt(args)
        assert row["start"] == "scratch" and row["parent"] is None
        assert row["stand_reward"] == {"four_foot_contact": .1, "gap": -.2, "load": -.1}
        assert row["stage_boundaries"]["B0"] == 0
        if not smoke:
            assert row["stage_boundaries"]["D"] == 6001
            assert row["stage_boundaries"]["T0"] == 7501
            bad_length = list(args)
            bad_length[bad_length.index("--max_iterations") + 1] = "6501"
            with pytest.raises(ValueError, match="m8000"):
                receipt(bad_length)
    with pytest.raises(ValueError, match="resume needs both"):
        receipt(args + ["--resume_from", str(BASELINE / "agent.yaml")])
    bad = _mutated(tmp_path, lambda d: d.update(baseline_env_yaml_sha256="0" * 64))
    with pytest.raises(ValueError, match="saved configuration SHA"):
        build_args(arm="A", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                   log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=False, table=bad)


def test_first_reset_wiring_precedes_real_wrapper_reset():
    train = (TABLE.parent.parent / "scripts" / "train_sol23f_common.py").read_text(encoding="utf-8")
    wrapper = Path("C:/isaac/IsaacLab/source/isaaclab_rl/isaaclab_rl/rsl_rl/vecenv_wrapper.py")
    installed = wrapper.read_text(encoding="utf-8")
    assert "self.env.reset()" in installed
    assert train.index("command_term.stage_runtime = continuous") < train.index(
        "env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)")
    assert "cmd_cfg.seed = 0 if curriculum_plan else agent_cfg.seed" in train
    assert "and curriculum_plan is None" in train
    ast.parse(train)


def test_stand_penalty_known_forces_ramp_and_npz():
    gap = torch.tensor([[0.005, 0.005, 0.005, 0.005],
                        [0.055, 0.005, 0.005, 0.005]])
    mass = torch.tensor([20.0, 20.0])
    force = torch.tensor([[49.05] * 4, [0.0, 49.05, 49.05, 49.05]])
    stop = torch.tensor([True, True])
    elapsed = torch.tensor([0.5, 0.25])
    g, l = stand_penalty_values(gap, force, mass, stop, elapsed)
    assert torch.allclose(g, torch.tensor([0.0, -0.1]))
    assert torch.allclose(l, torch.tensor([0.0, -0.05]))
    _, moving = stand_penalty_values(gap, force, mass, torch.zeros_like(stop), elapsed)
    assert torch.equal(moving, torch.zeros_like(moving))
    import numpy as np

    path = Path("C:/Users/AI-WS01/s2_lab/rr_probe_20261030_lead01/data/rr_stance.npz")
    with np.load(path) as raw:
        for prefix, expected_key, expected in (("parent_normal", "load", -0.06458),
                                               ("ex38_normal", "gap", -0.27339)):
            valid = raw[f"{prefix}_valid"].astype(bool) & (np.arange(150)[:, None] >= 50)
            force_n = raw[f"{prefix}_foot_force_xyz_n"][valid, :, 2]
            gap_m = raw[f"{prefix}_sole_gap_m"][valid]
            mass_kg = raw[f"{prefix}_body_mass_kg"][valid].sum(axis=1)
            n = len(mass_kg)
            calc = stand_penalty_values(torch.from_numpy(gap_m).float(),
                torch.from_numpy(force_n).float(), torch.from_numpy(mass_kg).float(),
                torch.ones(n, dtype=torch.bool), torch.full((n,), 0.5))
            value = calc[0 if expected_key == "gap" else 1].mean().item()
            assert abs(value - expected) < 0.01


def test_support_ray_hits_vertically_below_rolled_foot():
    # RayCasterCfg is Kit-only, so inspect the actual config function without
    # importing Isaac. The installed GridPatternCfg points straight down.
    cfg_tree = ast.parse(inspect.getsource(apply_ex40_stand_settings))
    calls = [node for node in ast.walk(cfg_tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == "RayCasterCfg"]
    assert len(calls) == 1
    alignment = next(kw.value.value for kw in calls[0].keywords if kw.arg == "ray_alignment")
    assert alignment == "yaw"
    installed = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py")
    source = installed.read_text(encoding="utf-8")
    yaw_branch = source.split('elif self.cfg.ray_alignment == "yaw":', 1)[1].split(
        'elif self.cfg.ray_alignment == "base":', 1)[0]
    assert "quat_apply_yaw" in yaw_branch
    assert "ray_directions_w = self.ray_directions[env_ids]" in yaw_branch
    pattern_cfg = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/patterns/patterns_cfg.py")
    assert "direction: tuple[float, float, float] = (0.0, 0.0, -1.0)" in (
        pattern_cfg.read_text(encoding="utf-8"))

    # Foot prim at (1,2,0.3), collision-center x offset -0.002 m, roll 30 deg.
    # Yaw-only start and vertical direction meet z=0 at that foot's ray XY.
    foot_pos = torch.tensor([1.0, 2.0, 0.3])
    foot_ray_xy = torch.tensor([1.0 - 0.002, 2.0])
    yaw_start = foot_pos + torch.tensor([-0.002, 0.0, 20.0])
    vertical = torch.tensor([0.0, 0.0, -1.0])
    yaw_hit = yaw_start + yaw_start[2] * vertical
    assert torch.equal(yaw_hit[:2], foot_ray_xy)
    assert yaw_hit[2] == 0
    # Full base alignment rotates the 20 m start and the ray; its hit drifts
    # 0.3*tan(30 deg) in y, enough to intersect a neighboring stair.
    base_hit_xy = foot_ray_xy + torch.tensor([0.0, 0.3 * math.tan(math.pi / 6)])
    assert base_hit_xy[1] - foot_ray_xy[1] > 0.17


def test_gate_two_eligible_passes_fail_override_and_resume(tmp_path):
    table = _mutated(tmp_path, lambda d: d.update(promotion="gate", shadow_gate=False))
    plan = Plan(table, arm="A")
    scores = tmp_path / "scores"
    scores.mkdir()
    run = Runtime(plan, 2, "cpu", tmp_path / "log", scores)
    run.start()

    def score(update, verdict):
        checkpoint = tmp_path / f"model_{update}.pt"
        checkpoint.write_bytes(f"checkpoint {update}".encode())
        row = {"format": "foothold-ex40-score/2", "from": "B0", "to": "B1",
               "effective_schedule_sha256": plan.effective_sha256,
               "checkpoint": str(checkpoint), "checkpoint_iteration": update,
               "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
               "created_at": "2026-10-30T18:00:00+09:00", "verdict": verdict}
        (scores / f"score_{update}.json").write_text(json.dumps(row), encoding="utf-8")
        run.on_checkpoint(update, checkpoint)

    score(250, "PASS")
    score(500, "PASS")
    assert run.pending_gate is None and len(run.passes) == 1
    score(750, "FAIL")
    assert run.pending_gate is None and not run.passes
    score(1000, "PASS")
    assert run.pending_gate is None
    state = run.state_dict()
    resumed = Runtime(plan, 2, "cpu", tmp_path / "resume", scores, segment_index=1)
    resumed.load_state_dict(state)
    assert len(resumed.passes) == 1
    score(1250, "PASS")
    assert run.pending_gate is not None
    score(1260, "FAIL")
    run.on_update_start(1261)
    assert run.active == 0 and run.pending_gate is None
    score(1500, "PASS")
    score(1750, "PASS")
    run.on_update_start(1751)
    assert run.active == 1 and run.stage_entry_iteration == 1751
    assert resumed.active == 0


def test_actual_consumption_counts_before_reset(tmp_path):
    plan = Plan(TABLE, arm="A")
    run = Runtime(plan, 2, "cpu", tmp_path)
    sensor = SimpleNamespace(find_bodies=lambda names: (list(range(4)), names),
        data=SimpleNamespace(net_forces_w=torch.tensor([
            [[0., 0., 2.]] * 4, [[0., 0., 0.]] * 4])))
    robot = SimpleNamespace(data=SimpleNamespace(heading_w=torch.tensor([-0.2, 0.2]),
        root_pos_w=torch.tensor([[0., -1., 0.], [0., 1., 0.]]),
        joint_pos_target=torch.zeros((2, 12)), joint_pos=torch.zeros((2, 12))))
    term = SimpleNamespace(slot_current=torch.zeros(2, dtype=torch.long))

    class Scene:
        sensors = {"contact_forces": sensor}
        terrain = SimpleNamespace(env_origins=torch.zeros((2, 3)))

        def __getitem__(self, key):
            return robot

    raw = SimpleNamespace(scene=Scene(), num_envs=2,
        command_manager=SimpleNamespace(get_term=lambda key: term))
    run.runner = SimpleNamespace(env=SimpleNamespace(unwrapped=raw),
        pstate=SimpleNamespace(map_off=torch.zeros(2, dtype=torch.bool),
                               use_gt=torch.ones(2, dtype=torch.bool)))
    run.record_pre_step()
    run.record_post_step(torch.tensor([True, False]))
    run.flush_consumption(0)
    rows = [json.loads(line) for line in (tmp_path / "stage_log.jsonl").read_text().splitlines()]
    row = rows[-1]
    assert row["steps"][0][0][0] == 2 and row["done"][0][0][0] == 1
    assert row["contact_steps"][0][0][0] == [1, 1, 1, 1]
    assert row["side_steps_done"][0][0][1] == 1
    assert row["raw_samples"][0]["joint_target_rad"][0] == [0.0] * 12


def test_kit_receipt_known_good_and_mutations(tmp_path):
    args = build_args(arm="B", device="cuda:1", end_by="2026-11-05T12:00:00+09:00",
                      log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=True)
    launch = receipt(args)
    assert launch["intentional_baseline_differences"] == [
        "S-B10 대비 의도된 차이 1: 지형 승급 판정 세계 좌표(결정 8)",
        "S-B10 대비 의도된 차이 2: 지형 자동 승급 끔(L0~2 고정, 팀장 결정 대기)"]
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(launch), encoding="utf-8")
    run_log = tmp_path / "run.log"
    run_log.write_text("Learning iteration 17/18\n", encoding="utf-8")
    run = tmp_path / "output" / "smoke" / "EX-40-B-kit-smoke_20261030_1"
    (run / "params").mkdir(parents=True)
    plan = Plan(TABLE, arm="B", smoke_boundaries=(3, 6, 9, 12, 15))
    baseline = yaml.load((BASELINE / "env.yaml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    expected_curriculum = copy.deepcopy(baseline["curriculum"])
    expected_curriculum["terrain_levels"] = "null"
    rewards = {key: {"weight": float(value["weight"])} for key, value in baseline["rewards"].items()}
    rewards.update({actual: {"weight": plan.stages[0].rewards[source]} for source, actual in
                    (("hip_pos_penalty", "basic_hip_pos_penalty_l1"),
                     ("thigh_calf_pos_l1", "ex39_thigh_calf_pos_l1"),
                     ("four_foot_contact_at_stop", "ex39_four_foot_stop"),
                     ("stand_gap", "ex40_stand_gap"), ("stand_load", "ex40_stand_load"))})
    for key in ("track_ang_vel", "track_lin_vel", "joint_acc"):
        rewards[key]["weight"] = plan.stages[0].rewards[key]
    env_yaml = run / "params" / "env.yaml"
    env_yaml.write_text(yaml.safe_dump({"commands": {"base_velocity": {
        "params": {"curriculum_mode": True}, "flag_stride": 0, "dynamic_flags": False,
        "seed": 0, "resampling_time_range": baseline["commands"]["base_velocity"]["resampling_time_range"]}},
        "rewards": rewards, "events": baseline["events"], "curriculum": expected_curriculum,
        "scene": {"terrain": {"terrain_generator": baseline["scene"]["terrain"]["terrain_generator"],
                                "max_init_terrain_level": 2},
                  **{f"ex40_support_{i}": {"prim_path": f"Robot/{name}_foot",
                       "ray_alignment": "yaw", "offset": {"pos": [-.002, 0, 20]}}
                     for i, name in enumerate(("FL", "FR", "RL", "RR"))}}}),
        encoding="utf-8")
    sensor_row = {"stand_foot_total": 100, "hit_valid_count": 100,
                  "hit_valid_ratio": 1.0, "flat_stand_valid_foot_count": 0,
                  "flat_gap_p50_mm": None, "flat_columns": [],
                  "hit_valid_count_by_foot": [25] * 4,
                  "gap_valid_count_by_foot": [25] * 4,
                  "gap_p5_p50_p95_mm_by_foot": [[5.0] * 3 for _ in range(4)],
                  "hit_invalid_by_foot": [0] * 4,
                  "force_nonfinite_by_foot": [0] * 4,
                  "gap_nonfinite_by_foot": [0] * 4,
                  "hit_origin_samples": [{"row": 0, "foot": 0, "hit_z_m": 1.0,
                                          "terrain_origin_z_m": 1.0,
                                          "hit_minus_origin_z_m": 0.0}]}
    def ex40_dr_row(update, active=False):
        scale = dr_scale(update)
        max_steps = math.floor(scale * .015 / .005 + 1e-9)
        event_count = 1 if active else 0
        histogram = [1] + [0] * max_steps
        return {"update": update, "scale": scale,
            "observation_noise": {"mode": "fixed", "multiplier": 1.0},
            "actual_samples": {key: {"count": event_count,
                                      "min": 0.0 if active else None,
                                      "max": 0.0 if active else None,
                                      "mean": 0.0 if active else None}
                for key in ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier",
                            "motor_effort_limit", "motor_saturation_effort", "push_velocity_delta")},
            "delay_readback": {"count": 1, "reset_sample_count": 1,
                "observed_min_substeps": 0, "observed_max_substeps": 0,
                "max_allowed_substeps": max_steps, "current_histogram": histogram,
                "reset_sample_histogram": histogram, "max_seconds": scale * .015,
                "configured_max_seconds": scale * .015, "observed_max_seconds": 0.0,
                "reset_sampled_delay_ms": [0.0], "physics_dt_seconds": .005},
            "realized_state": {key: {"count": 1} for key in
                ("base_com_offset_m", "delay_substeps", "motor.stiffness", "motor.damping",
                 "motor.effort_limit", "motor.saturation_effort")},
            "pending_values": ["push_velocity"]}

    def train_row(i, sensor):
        return {"it": i, "ex40_stand_sensor": sensor, "ex40_dr": ex40_dr_row(i)}

    (run / "train_extra.jsonl").write_text("\n".join(
        json.dumps(train_row(i, sensor_row)) for i in range(18)) + "\n",
        encoding="utf-8")
    probe_rows = [ex40_dr_row(i, active=True) for i in (0, 4500, 6001)]
    (run / "ex40_dr_schedule_smoke.json").write_text(json.dumps(
        {"format": "ex40-dr-kit-smoke/1", "probes": [{"it": row["update"], "ex40_dr": row}
            for row in probe_rows]}), encoding="utf-8")
    (run / "manifest.json").write_text(json.dumps({"modes": {"contract": "basic_gait_ex40",
        "continuous_curriculum": {"sha256": plan.sha256,
                                  "effective_schedule_sha256": plan.effective_sha256,
                                      "arm": "B", "terrain_curriculum": "fixed_l02"},
            "terrain_policy": {"policy": "fixed_l02", "max_init_terrain_level": 2,
                               "promotion_enabled": False}}}), encoding="utf-8")
    terrain_levels = torch.zeros(3072, dtype=torch.long)
    terrain_types = torch.zeros(3072, dtype=torch.long)
    terrain_sha = hashlib.sha256(terrain_levels.numpy().tobytes() + terrain_types.numpy().tobytes()).hexdigest()
    terrain_receipt = {"policy": "fixed_l02", "max_init_terrain_level": 2,
        "promotion_enabled": False, "num_envs": 3072, "actual_counts_by_level": [3072] + [0] * 9,
        "level_min": 0, "level_max": 0, "terrain_labels_sha256": terrain_sha}
    (run / "curriculum_start_receipt.json").write_text(json.dumps({"start": "scratch",
        "segment_index": 0, "parent_checkpoint": None, "terrain": terrain_receipt,
        "num_envs": 3072, "env_seed": 42, "command_seed": 0,
        "stand_reward": {"four_foot_contact": .1, "gap": -.2, "load": -.1}}), encoding="utf-8")
    events = []
    for i, stage in enumerate(plan.stages):
        row = {"event": "stage_enter", "to": stage.id, "iteration": stage.fixed_update,
               "curriculum_sha256": plan.sha256,
               "effective_schedule_sha256": plan.effective_sha256}
        if i:
            row.update(shares=stage.shares, ranges=stage.ranges, force_gt=stage.force_gt,
                       pending_envs=3072, changed={"rewards_added": stage.adds.get("rewards", {})})
        else:
            row["changed"] = stage.adds
        events.append(row)
        if i:
            events.extend(({"event": "env_reset_applied", "to": stage.id,
                            "changed_envs": 4, "remaining_old_envs": 3068,
                            "map_source_policy": "forced_gt" if stage.force_gt else "AdaSmpl_pred_eligible",
                            "adasmpl_p": 1.0},
                           {"event": "stage_command_consumed", "to": stage.id,
                            "sampled_envs": 4, "slot_counts": {slot: (4 if slot == "forward" else 0)
                                                                  for slot in EX39_SLOTS},
                            "heading_count": 0, "command_bad_count": 0},
                           {"event": "stage_map_consumed", "to": stage.id,
                            "reset_envs": 4, "force_gt_runtime": stage.force_gt,
                            "use_gt_envs": 4, "adasmpl_p": 1.0}))
    stage_log = run / "stage_log.jsonl"
    stage_log.write_text("\n".join(json.dumps(r) for r in events) + "\n", encoding="utf-8")
    torch.save({"continuous_curriculum": {"terrain_receipt": terrain_receipt}}, run / "model_17.pt")
    checkpoint_sha = hashlib.sha256((run / "model_17.pt").read_bytes()).hexdigest()
    (run / "train_start_status.json").write_text(json.dumps({"state": "done", "iter": 17,
        "sha256": checkpoint_sha}), encoding="utf-8")
    checked = check_kit_smoke(receipt_path, run_log, 0)
    assert checked["state"] == "PASS"
    assert checked["intentional_baseline_differences"] == launch["intentional_baseline_differences"]
    missing_marker = json.loads(receipt_path.read_text(encoding="utf-8"))
    missing_marker.pop("stand_sensor_evidence")
    receipt_path.write_text(json.dumps(missing_marker), encoding="utf-8")
    with pytest.raises(ValueError, match="sensor evidence marker"):
        check_kit_smoke(receipt_path, run_log, 0)
    receipt_path.write_text(json.dumps(launch), encoding="utf-8")
    invalid_sensor = {**sensor_row, "hit_valid_count_by_foot": [100] * 4}
    (run / "train_extra.jsonl").write_text("\n".join(
        json.dumps(train_row(i, invalid_sensor)) for i in range(18)) + "\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="per-foot valid counts"):
        check_kit_smoke(receipt_path, run_log, 0)
    (run / "train_extra.jsonl").write_text("\n".join(
        json.dumps(train_row(i, sensor_row)) for i in range(18)) + "\n",
        encoding="utf-8")
    good_env = yaml.safe_load(env_yaml.read_text(encoding="utf-8"))
    for changed in ("promotion_enabled", "max_init_terrain_level", "terrain_count"):
        wrong_curriculum = copy.deepcopy(good_env)
        if changed == "promotion_enabled":
            wrong_curriculum["curriculum"]["terrain_levels"] = {"params": {}}
        elif changed == "max_init_terrain_level":
            wrong_curriculum["scene"]["terrain"]["max_init_terrain_level"] = 1
        else:
            terrain_generator = wrong_curriculum["scene"]["terrain"]["terrain_generator"]
            terrain_generator["num_rows"] = int(terrain_generator["num_rows"]) + 1
        env_yaml.write_text(yaml.safe_dump(wrong_curriculum), encoding="utf-8")
        with pytest.raises(ValueError):
            check_kit_smoke(receipt_path, run_log, 0)
    env_yaml.write_text(yaml.safe_dump(good_env), encoding="utf-8")
    good_start = json.loads((run / "curriculum_start_receipt.json").read_text(encoding="utf-8"))
    for changed in ("promotion_enabled", "level_distribution"):
        bad_start = copy.deepcopy(good_start)
        if changed == "promotion_enabled":
            bad_start["terrain"]["promotion_enabled"] = True
        else:
            bad_start["terrain"]["actual_counts_by_level"][0] -= 1
            bad_start["terrain"]["actual_counts_by_level"][3] = 1
            bad_start["terrain"]["level_max"] = 3
        (run / "curriculum_start_receipt.json").write_text(json.dumps(bad_start), encoding="utf-8")
        with pytest.raises(ValueError, match="actual terrain distribution or disabled promotion"):
            check_kit_smoke(receipt_path, run_log, 0)
    (run / "curriculum_start_receipt.json").write_text(json.dumps(good_start), encoding="utf-8")
    bad_manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    bad_manifest["modes"]["terrain_policy"]["promotion_enabled"] = True
    (run / "manifest.json").write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest does not prove fixed L0..L2"):
        check_kit_smoke(receipt_path, run_log, 0)
    bad_manifest["modes"]["terrain_policy"]["promotion_enabled"] = False
    (run / "manifest.json").write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="child failed"):
        check_kit_smoke(receipt_path, run_log, 1)
    bad = copy.deepcopy(events)
    next(r for r in bad if r["event"] == "env_reset_applied" and r["to"] == "B2")["changed_envs"] = 0
    stage_log.write_text("\n".join(json.dumps(r) for r in bad) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="positive reset adoption"):
        check_kit_smoke(receipt_path, run_log, 0)
    stage_log.write_text("\n".join(json.dumps(r) for r in events) + "\n", encoding="utf-8")
    wrong = yaml.safe_load(env_yaml.read_text(encoding="utf-8"))
    wrong["rewards"]["track_ang_vel"]["weight"] = 99.0
    env_yaml.write_text(yaml.safe_dump(wrong), encoding="utf-8")
    with pytest.raises(ValueError, match="B0 reward"):
        check_kit_smoke(receipt_path, run_log, 0)
    wrong["rewards"]["track_ang_vel"]["weight"] = 1.0
    wrong["events"]["physics_material"]["params"]["num_buckets"] = "1"
    env_yaml.write_text(yaml.safe_dump(wrong), encoding="utf-8")
    with pytest.raises(ValueError, match="B0 events"):
        check_kit_smoke(receipt_path, run_log, 0)
