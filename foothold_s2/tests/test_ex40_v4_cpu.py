"""EX-40 v4 verifier counterexamples and sensor receipts, CPU only."""

from __future__ import annotations

import hashlib
import json
import math
from types import SimpleNamespace as NS

import pytest
import torch
import yaml

from foothold_s2.commands.mixed_core import stop_elapsed_after_resample
from foothold_s2.curriculum.continuous import Plan, Runtime
from foothold_s2.ex40_kit_smoke import _check_stand_sensor
from foothold_s2.ex40_launch import TABLE
from foothold_s2.rewards.basic_gait_bundle import (
    StandSensorEvidence, scheduled_lin_vel_z_weight, set_lin_vel_z_weight,
    stand_penalty_values,
)


class Manager:
    def __init__(self):
        self.weights = {}

    def get_term_cfg(self, name):
        return self.weights.setdefault(name, NS(weight=-2.0 if name == "lin_vel_z" else 0.0))

    def set_term_cfg(self, name, cfg):
        self.weights[name] = cfg


def attached(runtime):
    runner = NS(env=NS(unwrapped=NS(reward_manager=Manager())),
                adasmpl=NS(force_gt=True, p=1.0), pcfg={"force_gt": True},
                perception=NS(cfg=NS(force_gt=True)))
    runtime.attach(runner, NS())
    return runner


def gate_plan(tmp_path):
    doc = yaml.safe_load(TABLE.read_text(encoding="utf-8"))
    doc.update(promotion="gate", shadow_gate=False)
    path = tmp_path / "gate.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return Plan(path, arm="A")


def score(root, scores, plan, update, verdict):
    checkpoint = root / f"model_{update}.pt"
    checkpoint.write_bytes(f"checkpoint {update}".encode())
    row = {"format": "foothold-ex40-score/2", "from": "B0", "to": "B1",
           "effective_schedule_sha256": plan.effective_sha256,
           "checkpoint": str(checkpoint), "checkpoint_iteration": update,
           "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
           "created_at": "2026-10-30T18:00:00+09:00", "verdict": verdict}
    (scores / f"{update}_{verdict}.json").write_text(json.dumps(row), encoding="utf-8")


def test_b1_schedule_origin_survives_all_stages_and_resume(tmp_path):
    plan = Plan(TABLE, arm="B")
    runtime = Runtime(plan, 2, "cpu", tmp_path / "fixed")
    runner = attached(runtime)
    runtime.start()
    expected = [(1501, -2.0), (2251, -1.0), (3001, 0.0),
                (4501, 0.0), (5501, 0.0), (6000, 0.0)]
    for update, value in expected:
        runtime.on_update_start(update)
        assert runtime.b1_entry_iteration == runner.basic_lin_vel_z_start_iteration == 1501
        assert set_lin_vel_z_weight(runner.env, update, runner.basic_lin_vel_z_start_iteration) == pytest.approx(value)
        if update == 3001:
            restored = Runtime(plan, 2, "cpu", tmp_path / "resumed")
            resumed_runner = attached(restored)
            restored.load_state_dict(runtime.state_dict())
            restored.on_update_start(3002)
            assert restored.b1_entry_iteration == resumed_runner.basic_lin_vel_z_start_iteration == 1501
            assert set_lin_vel_z_weight(resumed_runner.env, 3002, 1501) == 0
    with pytest.raises(ValueError, match="B1 schedule origin"):
        bad = runtime.state_dict()
        bad.pop("b1_entry_iteration")
        Runtime(plan, 2, "cpu", tmp_path / "bad").load_state_dict(bad)


def test_gate_b1_origin_is_actual_first_entry(tmp_path):
    plan = gate_plan(tmp_path)
    scores = tmp_path / "scores"
    scores.mkdir()
    runtime = Runtime(plan, 2, "cpu", tmp_path / "log", scores)
    runner = attached(runtime)
    runtime.start()
    score(tmp_path, scores, plan, 500, "PASS")
    score(tmp_path, scores, plan, 750, "PASS")
    runtime.on_update_start(900)
    assert runtime.active == 1 and runtime.b1_entry_iteration == 900
    assert runner.basic_lin_vel_z_start_iteration == 900
    assert scheduled_lin_vel_z_weight(1650, start_iteration=900) == -1


def test_gate_late_old_passes_and_stale_cache_and_null_hold(tmp_path):
    plan = gate_plan(tmp_path)
    scores = tmp_path / "scores"
    scores.mkdir()
    runtime = Runtime(plan, 2, "cpu", tmp_path / "log", scores)
    runtime.start()
    score(tmp_path, scores, plan, 900, "FAIL")
    runtime.on_update_start(900)
    score(tmp_path, scores, plan, 500, "PASS")
    score(tmp_path, scores, plan, 750, "PASS")
    runtime.on_update_start(901)
    assert runtime.active == 0 and runtime.pending_gate is None
    assert runtime.latest_score["checkpoint_iteration"] == 900
    assert runtime.latest_score["verdict"] == "FAIL"

    second = tmp_path / "second"
    second.mkdir()
    second_scores = second / "scores"
    second_scores.mkdir()
    stale = Runtime(plan, 2, "cpu", second / "log", second_scores)
    stale.start()
    score(second, second_scores, plan, 500, "PASS")
    stale.on_update_start(500)
    score(second, second_scores, plan, 1250, "PASS")
    stale.on_update_start(1250)
    assert stale.active == 0 and stale.pending_gate is None

    third = tmp_path / "third"
    third.mkdir()
    third_scores = third / "scores"
    third_scores.mkdir()
    malformed = Runtime(plan, 2, "cpu", third / "log", third_scores)
    malformed.start()
    (third_scores / "null.json").write_text("null", encoding="utf-8")
    malformed.on_update_start(500)
    assert malformed.active == 0 and malformed.pending_gate is None
    rows = [json.loads(line) for line in (third / "log" / "stage_log.jsonl").read_text().splitlines()]
    assert any(row.get("event") == "gate_hold" and row.get("training_continues") is True
               for row in rows)


def test_gate_rechecks_cached_checkpoint_before_promotion(tmp_path):
    plan = gate_plan(tmp_path)
    scores = tmp_path / "scores"
    scores.mkdir()
    runtime = Runtime(plan, 2, "cpu", tmp_path / "log", scores)
    runtime.start()
    score(tmp_path, scores, plan, 500, "PASS")
    score(tmp_path, scores, plan, 750, "PASS")
    runtime._scan_scores(750)
    assert runtime.pending_gate is not None
    (tmp_path / "model_500.pt").write_bytes(b"changed after cached PASS")
    runtime.on_update_start(751)
    assert runtime.active == 0 and runtime.pending_gate is None


@pytest.mark.parametrize("verdict", ["FAIL", "HOLD"])
def test_gate_same_update_and_timestamp_conflicting_fail_holds(tmp_path, verdict):
    plan = gate_plan(tmp_path)
    scores = tmp_path / "scores"
    scores.mkdir()
    runtime = Runtime(plan, 2, "cpu", tmp_path / "log", scores)
    runtime.start()
    score(tmp_path, scores, plan, 500, "PASS")
    score(tmp_path, scores, plan, 750, "PASS")
    runtime._scan_scores(750)
    assert runtime.pending_gate is not None
    score(tmp_path, scores, plan, 750, verdict)
    runtime.on_update_start(751)
    assert runtime.active == 0 and runtime.pending_gate is None
    assert runtime.latest_score["verdict"] == "HOLD"


def test_episode_side_cohort_carries_steps_done_and_contact(tmp_path):
    runtime = Runtime(Plan(TABLE, arm="A"), 1, "cpu", tmp_path)
    sensor = NS(find_bodies=lambda names: (list(range(4)), names),
                data=NS(net_forces_w=torch.tensor([[[0., 0., 2.]] * 4])))
    robot = NS(data=NS(heading_w=torch.tensor([-.2]),
                        root_pos_w=torch.tensor([[0., -1., 0.]]),
                        joint_pos_target=torch.zeros((1, 12)), joint_pos=torch.zeros((1, 12))))

    class Scene:
        sensors = {"contact_forces": sensor}
        terrain = NS(env_origins=torch.zeros((1, 3)))

        def __getitem__(self, key):
            return robot

    raw = NS(scene=Scene(), num_envs=1,
             command_manager=NS(get_term=lambda name: NS(slot_current=torch.zeros(1, dtype=torch.long))))
    runtime.runner = NS(env=NS(unwrapped=raw),
                        pstate=NS(map_off=torch.zeros(1, dtype=torch.bool),
                                  use_gt=torch.ones(1, dtype=torch.bool)))
    runtime.record_pre_step()
    runtime.record_post_step(torch.tensor([False]))
    robot.data.heading_w[:] = .2
    robot.data.root_pos_w[:, 1] = 1.0
    runtime.record_pre_step()
    runtime.record_post_step(torch.tensor([True]))
    runtime.flush_consumption(0)
    row = json.loads((tmp_path / "stage_log.jsonl").read_text().splitlines()[-1])
    assert row["side_steps_done"][0] == [[2, 1], [0, 0], [0, 0], [0, 0]]
    assert row["side_contact_steps"][0] == [[2] * 4, [0] * 4, [0] * 4, [0] * 4]


def test_nonfinite_foot_is_excluded_and_counted_without_stopping():
    gap = torch.tensor([[float("inf"), .055, .005, .005],
                        [float("inf"), .005, .005, .005]])
    force = torch.tensor([[49.05, float("nan"), 49.05, 49.05],
                          [float("nan"), 49.05, 49.05, 49.05]])
    stop = torch.tensor([True, False])
    g, l = stand_penalty_values(gap, force, torch.tensor([20., float("nan")]),
                                stop, torch.tensor([.5, float("nan")]))
    assert g.tolist() == pytest.approx([-.2, 0.])
    assert torch.equal(l, torch.zeros(2))
    evidence = StandSensorEvidence((0,))
    evidence.add(gap, torch.tensor([[float("inf"), 1., 1., 1.],
                                    [float("inf"), 1., 1., 1.]]), force, stop,
                 torch.zeros(2, dtype=torch.long), torch.zeros(2))
    row = evidence.summary()
    assert row["stand_foot_total"] == 4 and row["hit_valid_count"] == 3
    assert row["hit_invalid_by_foot"] == [1, 0, 0, 0]
    assert row["force_nonfinite_by_foot"] == [0, 1, 0, 0]
    assert row["flat_stand_valid_foot_count"] == 3


def test_gap_and_load_masks_are_independent():
    gap = torch.tensor([[.055, float("nan"), .005, .005]])
    force = torch.tensor([[float("nan"), 0., 49.05, 49.05]])
    gap_reward, load_reward = stand_penalty_values(
        gap, force, torch.tensor([20.]), torch.tensor([True]), torch.tensor([.5]))
    assert gap_reward.item() == pytest.approx(-.2)
    assert load_reward.item() == pytest.approx(-.1)


def test_stand_sensor_quantiles_keep_each_foot_column():
    evidence = StandSensorEvidence(())
    gap = torch.tensor([[.001, .002, .003, .004], [.001, .002, .003, .004]])
    evidence.add(gap, torch.ones_like(gap), torch.ones_like(gap),
                 torch.ones(2, dtype=torch.bool), torch.zeros(2, dtype=torch.long),
                 torch.zeros(2))
    row = evidence.summary()
    assert row["flat_columns"] == [] and row["flat_stand_valid_foot_count"] == 0
    assert row["gap_p5_p50_p95_mm_by_foot"] == [
        pytest.approx([value] * 3) for value in (1., 2., 3., 4.)]
    evidence.add(torch.tensor([[float("nan"), .002, .003, .004]]),
                 torch.ones((1, 4)), torch.ones((1, 4)),
                 torch.ones(1, dtype=torch.bool), torch.zeros(1, dtype=torch.long),
                 torch.zeros(1))
    row = evidence.summary()
    assert row["gap_p5_p50_p95_mm_by_foot"][0] is None
    assert row["gap_p5_p50_p95_mm_by_foot"][1:] == [
        pytest.approx([value] * 3) for value in (2., 3., 4.)]


def test_stand_to_stand_resample_keeps_ramp_and_move_to_stand_restarts():
    previous = torch.tensor([True, False, True])
    current = torch.tensor([True, True, False])
    elapsed = torch.tensor([.4, .4, .4])
    assert torch.equal(stop_elapsed_after_resample(previous, current, elapsed),
                       torch.tensor([.4, 0., 0.]))


def test_yaw_ray_and_full_pitch_center_can_straddle_stair_edge():
    ray_x = -.002
    center_x = -.002 * math.cos(math.pi / 3)
    edge_x = -.0015
    assert ray_x < edge_x < center_x
    assert center_x - ray_x == pytest.approx(.001)
    assert .002 * (1 - math.cos(math.pi / 3)) == pytest.approx(.001)


def test_new_kit_sensor_gate_requires_ratio_per_foot_gap_and_schema(tmp_path):
    good = {"stand_foot_total": 100, "hit_valid_count": 100, "hit_valid_ratio": 1.0,
            "flat_stand_valid_foot_count": 0, "flat_gap_p50_mm": None,
            "flat_columns": [], "hit_valid_count_by_foot": [25] * 4,
            "gap_valid_count_by_foot": [25] * 4,
            "gap_p5_p50_p95_mm_by_foot": [[5.] * 3 for _ in range(4)],
            "hit_invalid_by_foot": [0] * 4, "force_nonfinite_by_foot": [0] * 4,
            "gap_nonfinite_by_foot": [0] * 4,
            "hit_origin_samples": [{"row": 0, "foot": 0,
                                    "hit_z_m": 1., "terrain_origin_z_m": 1.,
                                    "hit_minus_origin_z_m": 0.}]}

    def write(row):
        (tmp_path / "train_extra.jsonl").write_text("\n".join(
            json.dumps({"it": i, "ex40_stand_sensor": row}) for i in range(15)) + "\n",
            encoding="utf-8")

    write(good)
    assert _check_stand_sensor(tmp_path)["updates"] == 15
    write({**good, "hit_valid_count": 98, "hit_valid_ratio": .98,
           "hit_valid_count_by_foot": [23, 25, 25, 25],
           "gap_valid_count_by_foot": [23, 25, 25, 25],
           "hit_invalid_by_foot": [2, 0, 0, 0]})
    with pytest.raises(ValueError, match="ray hit"):
        _check_stand_sensor(tmp_path)
    write({**good, "gap_p5_p50_p95_mm_by_foot": [[5.] * 3, [5.] * 3,
                                                  [5., 11., 11.], [5.] * 3]})
    with pytest.raises(ValueError, match="foot 2 gap p50"):
        _check_stand_sensor(tmp_path)
    write({**good, "hit_valid_count_by_foot": [100] * 4})
    with pytest.raises(ValueError, match="per-foot valid counts"):
        _check_stand_sensor(tmp_path)
    write({**good, "hit_valid_count": 101, "hit_valid_ratio": 1.01})
    with pytest.raises(ValueError, match="counts or ratio"):
        _check_stand_sensor(tmp_path)
    write({**good, "hit_origin_samples": [{}]})
    with pytest.raises(ValueError, match="sample invalid"):
        _check_stand_sensor(tmp_path)
    write({**good, "gap_p5_p50_p95_mm_by_foot": [[float("nan")] * 3] + [[5.] * 3] * 3})
    with pytest.raises(ValueError, match="foot 0 gap p50"):
        _check_stand_sensor(tmp_path)
    write({**good, "force_nonfinite_by_foot": [1, 0, 0, 0]})
    with pytest.raises(ValueError, match="fault counters"):
        _check_stand_sensor(tmp_path)
    write({**good, "gap_nonfinite_by_foot": [1, 0, 0, 0]})
    with pytest.raises(ValueError, match="fault counters"):
        _check_stand_sensor(tmp_path)
    write({**good, "hit_invalid_by_foot": []})
    with pytest.raises(ValueError, match="fault counters"):
        _check_stand_sensor(tmp_path)

    no_stand = {**good, "stand_foot_total": 0, "hit_valid_count": 0,
                "hit_valid_ratio": None, "flat_stand_valid_foot_count": 0,
                "flat_gap_p50_mm": None, "hit_origin_samples": [],
                "hit_valid_count_by_foot": [0] * 4,
                "gap_valid_count_by_foot": [0] * 4,
                "gap_p5_p50_p95_mm_by_foot": [None] * 4}
    (tmp_path / "train_extra.jsonl").write_text("\n".join(
        json.dumps({"it": i, "ex40_stand_sensor": good if i == 14 else no_stand})
        for i in range(15)) + "\n", encoding="utf-8")
    assert _check_stand_sensor(tmp_path)["aggregate_hit_valid_ratio"] == 1.0
