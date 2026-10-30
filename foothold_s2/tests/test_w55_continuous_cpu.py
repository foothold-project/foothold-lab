"""D68 scratch EX-40 known inputs and mutations, without Isaac or GPU."""

from __future__ import annotations

import copy
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml

from foothold_s2.commands.mixed_core import EX39_SLOTS, make_generator, resample_stage
from foothold_s2.curriculum.continuous import Plan, Runtime, command_bad
from foothold_s2.ex40_kit_smoke import check as check_kit_smoke
from foothold_s2.ex40_launch import BASELINE, TABLE, build_args, receipt
from foothold_s2.prestart_check import actual_parser


def _mutated(tmp_path, change):
    doc = yaml.safe_load(TABLE.read_text(encoding="utf-8"))
    change(doc)
    path = tmp_path / "mutant.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def test_scratch_stages_and_baseline_pins(tmp_path):
    plan = Plan(TABLE, arm="A")
    assert [(s.id, s.fixed_update) for s in plan.stages] == [
        ("B0", 0), ("B1", 1501), ("B2", 3001), ("B3", 4501), ("T0", 5501)]
    assert plan.parent_sha256 is None
    assert hashlib.sha256((BASELINE / "env.yaml").read_bytes()).hexdigest() == plan.baseline_env_yaml_sha256
    assert hashlib.sha256((BASELINE / "agent.yaml").read_bytes()).hexdigest() == plan.baseline_agent_yaml_sha256
    assert plan.stages[0].rewards == {}
    assert plan.stages[0].shares == {"forward": .72, "spin_left": .09,
                                     "spin_right": .09, "stand": .10}
    assert "four_foot_contact_at_stop" not in plan.stages[1].rewards
    assert not plan.stages[-1].force_gt
    with pytest.raises(ValueError, match="scratch"):
        Plan(_mutated(tmp_path, lambda d: d.update(parent_update=1500)), arm="A")
    with pytest.raises(ValueError, match="sum to 100"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][0]["shares"].update(forward=.8)), arm="A")
    with pytest.raises(ValueError, match="reward additions incomplete"):
        Plan(_mutated(tmp_path, lambda d: d["stages"][1]["adds"]["rewards"].update(
            four_foot_contact_at_stop=.1)), arm="A")
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
    assert not out["heading"].any()
    assert torch.all(out["cmd"][out["slot"] == EX39_SLOTS.index("stand")] == 0)
    broken = out["cmd"].clone()
    broken[0, 1] = .3
    bad = command_bad(broken, out["slot"], out["heading"],
                      torch.zeros(n, dtype=torch.long), plan)
    assert bad[0] and int(bad.sum()) == 1


class _Manager:
    def __init__(self):
        self.weights = {name: SimpleNamespace(weight=0.0) for name in
                        ("track_ang_vel", "track_lin_vel", "joint_acc",
                         "basic_hip_pos_penalty_l1", "ex39_thigh_calf_pos_l1")}

    def get_term_cfg(self, name):
        return self.weights[name]

    def set_term_cfg(self, name, cfg):
        self.weights[name] = cfg


def test_b0_to_b1_reward_and_reset_boundary(tmp_path):
    plan = Plan(TABLE, arm="A", smoke_boundaries=(2, 5, 8, 11))
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
    assert runtime.active == 1 and runner.basic_lin_vel_z_schedule is True
    assert runner.basic_lin_vel_z_start_iteration == 1501
    assert manager.weights["track_ang_vel"].weight == 1.0
    assert manager.weights["basic_hip_pos_penalty_l1"].weight == -.05
    assert manager.weights["ex39_thigh_calf_pos_l1"].weight == -.01
    assert runtime.env_stage.tolist() == [0, 0, 0, 0]
    runtime.on_reset(torch.tensor([1, 3]))
    assert runtime.env_stage.tolist() == [0, 1, 0, 1]
    rows = [json.loads(line) for line in (tmp_path / "stage_log.jsonl").read_text().splitlines()]
    assert [(r["to"], r["iteration"]) for r in rows if r["event"] == "stage_enter"] == [
        ("B0", 0), ("B1", 2)]
    with pytest.raises(ValueError, match="scratch"):
        Runtime(plan, 1, "cpu", tmp_path / "bad").start("0" * 64)


def test_actual_parser_and_scratch_receipt(tmp_path):
    for smoke, final in ((True, 13), (False, 6001)):
        args = build_args(arm="A", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                          log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=smoke)
        parsed, unknown = actual_parser().parse_known_args([
            "--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB", *args])
        assert parsed.max_iterations == final and parsed.resume_from is None
        assert parsed.clock_scatter == "off" and unknown[-1].startswith("--kit_args=")
        row = receipt(args)
        assert row["start"] == "scratch" and row["parent"] is None
        assert row["stand_reward"] == "undecided_disabled"
        assert row["stage_boundaries"]["B0"] == 0
    with pytest.raises(ValueError, match="without --resume_from"):
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


def test_kit_receipt_known_good_and_mutations(tmp_path):
    args = build_args(arm="B", device="cuda:1", end_by="2026-11-05T12:00:00+09:00",
                      log_root=tmp_path / "output", score_dir=tmp_path / "scores", smoke=True)
    launch = receipt(args)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(launch), encoding="utf-8")
    run_log = tmp_path / "run.log"
    run_log.write_text("Learning iteration 12/13\n", encoding="utf-8")
    run = tmp_path / "output" / "smoke" / "EX-40-B-kit-smoke_20261030_1"
    (run / "params").mkdir(parents=True)
    plan = Plan(TABLE, arm="B", smoke_boundaries=(2, 5, 8, 11))
    baseline = yaml.load((BASELINE / "env.yaml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    rewards = {key: {"weight": float(value["weight"])} for key, value in baseline["rewards"].items()}
    rewards.update({key: {"weight": 0.0} for key in
                    ("basic_hip_pos_penalty_l1", "ex39_thigh_calf_pos_l1", "ex39_four_foot_stop")})
    env_yaml = run / "params" / "env.yaml"
    env_yaml.write_text(yaml.safe_dump({"commands": {"base_velocity": {
        "params": {"curriculum_mode": True}, "flag_stride": 0, "dynamic_flags": False,
        "seed": 0, "resampling_time_range": baseline["commands"]["base_velocity"]["resampling_time_range"]}},
        "rewards": rewards, "events": baseline["events"], "curriculum": baseline["curriculum"],
        "scene": {"terrain": {"terrain_generator": baseline["scene"]["terrain"]["terrain_generator"]}}}),
        encoding="utf-8")
    (run / "manifest.json").write_text(json.dumps({"modes": {"contract": "basic_gait_ex40",
        "continuous_curriculum": {"sha256": plan.sha256,
                                  "effective_schedule_sha256": plan.effective_sha256,
                                  "arm": "B"}}}), encoding="utf-8")
    (run / "curriculum_start_receipt.json").write_text(json.dumps({"start": "scratch",
        "num_envs": 3072, "env_seed": 42, "command_seed": 0,
        "stand_reward": "undecided_disabled"}), encoding="utf-8")
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
    (run / "model_12.pt").write_bytes(b"known model")
    (run / "train_start_status.json").write_text(json.dumps({"state": "done", "iter": 12,
        "sha256": hashlib.sha256(b"known model").hexdigest()}), encoding="utf-8")
    assert check_kit_smoke(receipt_path, run_log, 0)["state"] == "PASS"
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
    wrong["rewards"]["track_ang_vel"]["weight"] = .5
    wrong["events"]["physics_material"]["params"]["num_buckets"] = "1"
    env_yaml.write_text(yaml.safe_dump(wrong), encoding="utf-8")
    with pytest.raises(ValueError, match="B0 events"):
        check_kit_smoke(receipt_path, run_log, 0)
