"""Known-input CPU checks for EX-40 v7 stage boundaries and resume receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import torch
import yaml

from foothold_s2.curriculum.continuous import (
    KIT_SMOKE_BOUNDARIES, Plan, apply_terrain_policy, terrain_level_receipt,
)
from foothold_s2.ex40_continue import (
    TOTAL_ITERATIONS, build_resume_args, check_parent, consecutive_failure_action,
    newest_verified_checkpoint, source_decision, validate_deadline,
)
from foothold_s2.ex40_launch import TABLE, build_args, prepare_resume, receipt
from foothold_s2.runners.command_rng import restore_command_rng, save_command_rng


def test_v7_schedule_shares_ranges_and_boundaries():
    plan = Plan(TABLE, arm="B")
    assert [(stage.id, stage.fixed_update) for stage in plan.stages] == [
        ("B0", 0), ("B1", 1501), ("B2", 3001), ("B3a", 4501),
        ("B3b", 5001), ("B3c", 5501), ("D", 6001), ("T0", 7501)]
    for stage in plan.stages:
        assert sum(stage.shares.values()) == pytest.approx(1.0)
    b3a, b3b, b3c, d, t0 = plan.stages[3:]
    assert b3a.shares["forward"] == .25
    assert b3a.shares["walk_left"] == b3a.shares["walk_right"] == .075
    assert b3a.ranges["walk_wz_abs"] == (.2, 1.0)
    assert b3a.ranges["spin_wz_abs"] == (.5, 1.5)
    assert b3a.low_forward_fraction == 0
    assert b3b.ranges["spin_wz_abs"] == (.3, 1.5)
    assert b3b.ranges["forward_vx"] == (.3, 1.5)
    assert b3c.ranges["forward_vx"] == d.ranges["forward_vx"] == t0.ranges["forward_vx"] == (.1, 1.5)
    assert b3c.low_forward_fraction == d.low_forward_fraction == t0.low_forward_fraction == .2
    assert b3c.force_gt and d.force_gt and not t0.force_gt
    assert t0.shares == d.shares == b3c.shares and t0.ranges == d.ranges == b3c.ranges
    smoke = Plan(TABLE, arm="B", smoke_boundaries=KIT_SMOKE_BOUNDARIES)
    assert [(stage.id, stage.fixed_update) for stage in smoke.stages] == [
        ("B0", 0), ("B1", 3), ("B2", 6), ("B3a", 9), ("B3b", 12), ("B3c", 15)]
    args = build_args(arm="B", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                      log_root=Path("C:/tmp/ex40-v7-main"),
                      score_dir=Path("C:/tmp/ex40-v7-scores"), smoke=False)
    smoke_args = build_args(arm="B", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                            log_root=Path("C:/tmp/ex40-v7-smoke"),
                            score_dir=Path("C:/tmp/ex40-v7-scores"), smoke=True)
    assert args[args.index("--max_iterations") + 1] == str(TOTAL_ITERATIONS)
    assert smoke_args[smoke_args.index("--max_iterations") + 1] == "18"
    assert receipt(smoke_args)["stage_boundaries"] == {
        "B0": 0, "B1": 3, "B2": 6, "B3a": 9, "B3b": 12, "B3c": 15}


def test_fixed_l02_policy_applies_to_config_and_records_actual_levels():
    plan = Plan(TABLE, arm="B")
    cfg = NS(scene=NS(terrain=NS(max_init_terrain_level=None)),
             curriculum=NS(terrain_levels="promotion-term"))
    applied = apply_terrain_policy(cfg, plan)
    assert cfg.scene.terrain.max_init_terrain_level == 2
    assert cfg.curriculum.terrain_levels is None
    assert applied == {"policy": "fixed_l02", "max_init_terrain_level": 2,
                       "promotion_enabled": False}
    levels = torch.tensor([0, 1, 2, 0])
    types = torch.tensor([3, 3, 3, 4])
    terrain = NS(terrain_levels=levels, terrain_types=types,
                 terrain_origins=torch.zeros((10, 5, 3)))
    receipt = terrain_level_receipt(NS(scene=NS(terrain=terrain)), applied)
    assert receipt["actual_counts_by_level"] == [2, 1, 1] + [0] * 7
    assert (receipt["level_min"], receipt["level_max"], receipt["num_envs"]) == (0, 2, 4)
    terrain.terrain_levels[-1] = 3
    with pytest.raises(ValueError, match="outside L0..L2"):
        terrain_level_receipt(NS(scene=NS(terrain=terrain)), applied)


def test_auto_policy_requires_and_preserves_actual_promotion_term(tmp_path):
    path = Path(TABLE)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["terrain_curriculum"] = "auto"
    table = tmp_path / "ex40-auto.yaml"
    table.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    plan = Plan(table, arm="B")
    cfg = NS(scene=NS(terrain=NS(max_init_terrain_level=2)),
             curriculum=NS(terrain_levels="promotion-term"))
    assert apply_terrain_policy(cfg, plan) == {
        "policy": "auto", "max_init_terrain_level": 2, "promotion_enabled": True}
    cfg.curriculum.terrain_levels = None
    with pytest.raises(ValueError, match="requires the configured"):
        apply_terrain_policy(cfg, plan)


def test_command_generator_rng_round_trips_and_runner_calls_helpers():
    first = NS(gen=torch.Generator().manual_seed(12))
    torch.rand(37, generator=first.gen)
    saved = {}
    save_command_rng(first, saved)
    expected = torch.rand(5, generator=first.gen)
    resumed = NS(gen=torch.Generator().manual_seed(999))
    restore_command_rng(resumed, saved)
    assert torch.equal(torch.rand(5, generator=resumed.gen), expected)
    runner_source = (Path(__file__).parents[1] / "runners" / "start_runner.py").read_text(encoding="utf-8")
    assert "save_command_rng(command, out)" in runner_source
    assert "restore_command_rng(self._command_term(), sd)" in runner_source


def _known_checkpoint(tmp_path, iteration=5500):
    run = tmp_path / "run"
    run.mkdir()
    plan = Plan(TABLE, arm="B")
    active = max(i for i, stage in enumerate(plan.stages) if stage.fixed_update <= iteration)
    stage = plan.stages[active]
    checkpoint = run / f"model_{iteration}.pt"
    terrain_levels = torch.zeros(3072, dtype=torch.long)
    terrain_types = torch.zeros(3072, dtype=torch.long)
    terrain_sha = hashlib.sha256(terrain_levels.numpy().tobytes() + terrain_types.numpy().tobytes()).hexdigest()
    command_rng = torch.Generator().manual_seed(5).get_state()
    map_rng = torch.Generator().manual_seed(6).get_state()
    state = {
        "format": "foothold-start/1", "iter": iteration,
        "rng": {"torch": torch.tensor([1]), "numpy": ("MT",), "python": (1,)},
        "map_switch": {"p_map_off": .1, "generator_state": map_rng},
        "env_state": {"common_step_counter": iteration * 24,
                      "terrain_levels": terrain_levels,
                      "terrain_types": terrain_types,
                      "command_generator_state": command_rng},
        "continuous_curriculum": {
            "format": "foothold-w55-state/1", "plan_sha256": plan.sha256,
            "effective_sha256": plan.effective_sha256, "active": active,
            "segment_index": 0,
            "terrain_receipt": {"policy": "fixed_l02", "max_init_terrain_level": 2,
                                "promotion_enabled": False, "num_envs": 3072,
                                "actual_counts_by_level": [3072] + [0] * 9,
                                "level_min": 0, "level_max": 0,
                                "terrain_labels_sha256": terrain_sha},
            "stage_entry_iteration": stage.fixed_update,
            "b1_entry_iteration": plan.stages[1].fixed_update,
            "env_stage": torch.full((3072,), active, dtype=torch.long),
            "pending_gate": None, "seen_scores": [], "latest_score": None, "passes": []},
        "adasmpl": {"force_gt": stage.force_gt},
        "sol23f": {"variant": "SB_map_switch", "map_input": "reconstruction",
                   "force_gt": stage.force_gt},
    }
    torch.save(state, checkpoint)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {
        "schema": "foothold-manifest/1", "run": {"pid": 123, "cli_args": {
            "max_iterations": TOTAL_ITERATIONS, "curriculum_arm": "B",
            "curriculum_kit_smoke": False, "curriculum": str(TABLE)}},
        "modes": {"contract": "basic_gait_ex40", "num_envs": 3072, "seed": 42,
                  "command_settings": {"command_mode": "basic_gait"},
                  "continuous_curriculum": {"sha256": plan.sha256,
                      "effective_schedule_sha256": plan.effective_sha256,
                      "arm": "B", "promotion": "fixed", "shadow_gate": True,
                      "terrain_curriculum": "fixed_l02"},
                  "continuous_resume": {"segment_index": 0}},
        "checkpoints": {checkpoint.name: digest}}
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run, checkpoint, digest, manifest, plan


def test_newest_manifest_checkpoint_and_stage_state_verified(tmp_path):
    run, checkpoint, digest, _, _ = _known_checkpoint(tmp_path)
    row = check_parent(checkpoint, digest)
    assert row["completed_update"] == 5500
    assert row["active_stage"] == "B3b"
    assert row["remaining_updates"] == 2500
    assert newest_verified_checkpoint(run)["checkpoint_sha256"] == digest
    (run / "train_start_status.json").write_text(
        json.dumps({"state": "failed", "iter": 5500}), encoding="utf-8")
    assert source_decision(run=run, shell_finished=True, process_alive=False)["state"] == "ready_to_continue"
    assert source_decision(run=run, shell_finished=False, process_alive=True)["state"] == "waiting_for_original_exit"
    (run / "train_start_status.json").write_text(
        json.dumps({"state": "running", "iter": 5500}), encoding="utf-8")
    assert source_decision(run=run, shell_finished=False, process_alive=None)["state"] == "waiting_for_process_state"
    (run / "train_start_status.json").write_text(
        json.dumps({"state": "done", "iter": 8000}), encoding="utf-8")
    assert source_decision(run=run, shell_finished=True, process_alive=False) == {
        "state": "already_complete", "completed_update": 8000}


def test_resume_cli_is_prepared_with_sha_deadline_and_no_execution(tmp_path):
    _, checkpoint, digest, _, _ = _known_checkpoint(tmp_path)
    parent = {"checkpoint": str(checkpoint), "checkpoint_sha256": digest}
    original_args = build_args(arm="B", device="cuda:0", end_by="2026-11-05T12:00:00+09:00",
                              log_root=Path("C:/tmp/ex40-main"),
                              score_dir=Path("C:/tmp/ex40-scores"), smoke=False)
    launch = receipt(original_args)
    args = build_resume_args(launch, parent, expected_finish="2026-11-01T00:00:00+09:00",
                             end_by="2026-11-02T00:00:00+09:00")
    assert args[args.index("--resume_from") + 1] == str(checkpoint)
    assert args[args.index("--basic-ex40-parent-sha") + 1] == digest
    assert args[args.index("--max_iterations") + 1] == str(TOTAL_ITERATIONS)
    assert args[args.index("--end-by") + 1] == "2026-11-02T00:00:00+09:00"
    with pytest.raises(ValueError, match="24 hours"):
        validate_deadline("2026-11-01T00:00:00+09:00", "2026-11-01T23:59:00+09:00")


def test_resume_preparation_reuses_source_contract_and_records_segment(tmp_path):
    _, checkpoint, digest, _, _ = _known_checkpoint(tmp_path)
    log_root = tmp_path / "logs"
    score_dir = tmp_path / "scores"
    source_args = build_args(arm="B", device="cuda:0", end_by="2026-11-06T00:00:00+09:00",
                             log_root=log_root, score_dir=score_dir, smoke=False)
    source_path = tmp_path / "source_receipt.json"
    source_path.write_text(json.dumps(receipt(source_args)), encoding="utf-8")
    spec_path = tmp_path / "resume_spec.json"
    spec_path.write_text(json.dumps({
        "source_receipt": str(source_path), "checkpoint": str(checkpoint),
        "checkpoint_sha256": digest, "expected_finish": "2026-11-04T00:00:00+09:00",
    }), encoding="utf-8")

    args, prepared = prepare_resume(
        spec_path, arm="B", device="cuda:0", end_by="2026-11-05T00:00:00+09:00",
        log_root=log_root, score_dir=score_dir)
    assert args[args.index("--resume_from") + 1] == str(checkpoint.resolve())
    assert args[args.index("--basic-ex40-parent-sha") + 1] == digest
    assert args[args.index("--basic-ex40-segment-index") + 1] == "1"
    assert args[args.index("--curriculum") + 1] == str(TABLE)
    assert args[args.index("--curriculum-score-dir") + 1] == str(score_dir.resolve())
    assert prepared["start"] == "resume" and prepared["origin_start"] == "scratch"
    assert prepared["segment_index"] == 1 and prepared["parent_segment_index"] == 0
    assert prepared["terrain_curriculum"] == "fixed_l02"
    assert {"stage", "optimizer", "learning_rate", "B1_origin", "map_switch",
            "collection_update"}.issubset(prepared["resume_preserves"])


def test_retry_budget_stops_after_three_consecutive_failures():
    assert consecutive_failure_action([], True) == "record_and_review"
    assert consecutive_failure_action([{"state": "failed"}], True) == "record_and_review"
    assert consecutive_failure_action([{"state": "failed"}] * 2, True) == "stop_after_three_failures"
    assert consecutive_failure_action([{"state": "failed"}, {"state": "done"}], True) == "record_and_review"


def test_bad_checkpoint_number_and_sha_are_rejected(tmp_path):
    _, checkpoint, digest, _, _ = _known_checkpoint(tmp_path)
    with pytest.raises(ValueError, match="SHA mismatch"):
        check_parent(checkpoint, "0" * 64)
    wrong = checkpoint.with_name("model_5501.pt")
    wrong.write_bytes(checkpoint.read_bytes())
    with pytest.raises(ValueError, match="not pinned"):
        check_parent(wrong, digest)

