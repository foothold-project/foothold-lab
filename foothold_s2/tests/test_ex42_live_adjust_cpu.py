"""Known-answer update-boundary adjustment and failure guards. No Kit."""
from dataclasses import dataclass
import hashlib
import json
from types import SimpleNamespace

import pytest

from foothold_s2.ex42_live_adjust import LiveAdjustment, SCHEMA


@dataclass
class Stage:
    low_forward_fraction: float = .2


class Manager:
    def __init__(self):
        self.terms = {
            "track_lin_vel": SimpleNamespace(weight=2., params={"std": .5}),
            "track_ang_vel": SimpleNamespace(weight=1., params={"std": .5}),
            "ex41_feet_air_time": SimpleNamespace(weight=0., params={"threshold": .5}),
            "ex41_foot_slip": SimpleNamespace(weight=-.15, params={}),
            "ex41_zero_yaw": SimpleNamespace(weight=-1., params={}),
            "ex42_slow_track": SimpleNamespace(weight=0., params={"sigma": .5, "speed_min": .1, "speed_max": .3}),
            "ex42_slow_progress": SimpleNamespace(weight=0., params={}),
        }

    def get_term_cfg(self, name):
        return self.terms[name]

    def set_term_cfg(self, name, cfg):
        self.terms[name] = cfg


def _setup(tmp_path, *, iteration=2, rewards=None, commands=None, monitor=None):
    from foothold_s2.commands.ex42_segment_adjust import REWARD_LIMITS
    segment = tmp_path / "segment.yaml"
    segment.write_bytes(REWARD_LIMITS.read_bytes())
    config = {"segment_reward_limits_sha256": hashlib.sha256(segment.read_bytes()).hexdigest(),
              "extra_reward_limits": {"zero_yaw": [-2, -.5], "feet_air_time_threshold": [.04, .5],
                                      "slow_track": [0, .3], "slow_track_sigma": [.5, .5],
                                      "slow_track_speed_min": [.1, .1], "slow_track_speed_max": [.3, .3]},
              "command_limits": {"low_forward_fraction": [.2, .5]}}
    entry = {"decided_by": "lead", "decided_at": "2026-11-14T00:09+09:00", "evidence": "m250/m500 sheet"}
    if rewards is not None:
        entry["rewards"] = rewards
    if commands is not None:
        entry["commands"] = commands
    if monitor is not None:
        entry["monitor"] = monitor
    file = tmp_path / "adjust.json"
    file.write_text(json.dumps({"schema": SCHEMA, "stage_id": "E1", "plan_sha256": "a" * 64,
                                "changes": {str(iteration): entry}}))
    stage = Stage()
    runtime = SimpleNamespace(stage_id="E1", env=SimpleNamespace(reward_manager=Manager()),
                              plan=SimpleNamespace(stages=[stage]), stage_config=stage, command_stats=None,
                              live_metrics=SimpleNamespace(stage={"slow_forward": "learning", "side_left": "learning",
                                                                  "side_right": "learning"}))
    controller = LiveAdjustment(runtime, config, plan_sha256="a" * 64, path=file, log_dir=tmp_path,
                                segment_limits_path=segment)
    return controller, runtime, file


def test_repeated_plan_reward_fence_must_equal_segment_file(tmp_path):
    from foothold_s2.ex42_live_adjust import limits_from_plan
    from foothold_s2.commands.ex42_segment_adjust import REWARD_LIMITS
    config = {"segment_reward_limits_sha256": hashlib.sha256(REWARD_LIMITS.read_bytes()).hexdigest(),
              "extra_reward_limits": {"zero_yaw": [-2, -.5], "feet_air_time_threshold": [.04, .5],
                                      "slow_track": [0, .4], "slow_track_sigma": [.5, .5],
                                      "slow_track_speed_min": [.1, .1], "slow_track_speed_max": [.3, .3]},
              "command_limits": {"low_forward_fraction": [.2, .5]}}
    with pytest.raises(ValueError, match="slow_track differs from segment fence"):
        limits_from_plan(config)


def test_two_cells_apply_at_one_update_and_durable_receipt(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2, "track_lin_vel_std": .35},
                             commands={"low_forward_fraction": .5})
    assert ctl.on_update_start(1) is None
    record = ctl.on_update_start(2)
    assert record["before"]["rewards"]["slow_track"] == 0
    assert record["after"]["rewards"]["slow_track"] == .2
    assert runtime.env.reward_manager.get_term_cfg("track_lin_vel").params["std"] == .35
    assert runtime.plan.stages[0].low_forward_fraction == .5
    assert (tmp_path / "ex42_update_adjust_m2.json").is_file()
    assert ctl.on_update_start(3) is None  # old request is linked to its receipt


def test_outside_limit_rejected_and_training_can_continue(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .31})
    result = ctl.on_update_start(2)
    assert result["kind"] == "rejected"
    assert runtime.env.reward_manager.get_term_cfg("ex42_slow_track").weight == 0
    assert (tmp_path / "ex42_update_adjust_rejected_m2.json").is_file()


def test_slow_progress_is_pinned_at_zero_until_approved(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_progress": 0.0})
    record = ctl.on_update_start(2)
    assert record["after"]["rewards"]["slow_progress"] == 0.0
    assert runtime.env.reward_manager.get_term_cfg("ex42_slow_progress").weight == 0.0
    outside = tmp_path / "outside"
    outside.mkdir()
    rejected, _, _ = _setup(outside, rewards={"slow_progress": 0.001})
    assert rejected.on_update_start(2)["kind"] == "rejected"


def test_new_forward_share_limit_is_exactly_point_five(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, commands={"low_forward_fraction": .50001})
    assert ctl.on_update_start(2)["kind"] == "rejected"
    assert runtime.plan.stages[0].low_forward_fraction == .2


def test_one_rank_readback_mismatch_rejected_before_rollout(tmp_path, monkeypatch):
    ctl, _, _ = _setup(tmp_path, rewards={"slow_track": .2})
    monkeypatch.setattr(ctl, "_all_readbacks", lambda actual: [actual, {**actual, "after": {"wrong": 1}}])
    with pytest.raises(RuntimeError, match="rank readback differs"):
        ctl.on_update_start(2)
    assert not (tmp_path / "ex42_update_adjust_m2.json").exists()


def test_changed_value_without_receipt_stops_before_next_update(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    ctl.on_update_start(2)
    runtime.env.reward_manager.get_term_cfg("ex42_slow_track").weight = .3
    with pytest.raises(RuntimeError, match="without a receipt"):
        ctl.on_update_start(3)


def test_unchanged_cell_outside_limit_stops_before_next_rollout(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    ctl.on_update_start(2)
    runtime.env.reward_manager.get_term_cfg("ex42_slow_progress").weight = .25
    with pytest.raises(RuntimeError, match="slow_progress.*outside approved limit"):
        ctl.on_update_start(3)


def test_resume_rejects_out_of_limit_receipt_before_applying_it(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    ctl.on_update_start(2)
    path = tmp_path / "ex42_update_adjust_m2.json"
    receipt = json.loads(path.read_text())
    receipt["after"]["rewards"]["slow_progress"] = .25
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="slow_progress.*outside approved limit"):
        ctl._restore()
    assert runtime.env.reward_manager.get_term_cfg("ex42_slow_progress").weight == 0


def test_receipt_removed_stops_and_past_entry_cannot_be_rewritten(tmp_path):
    ctl, _, file = _setup(tmp_path, rewards={"slow_track": .2})
    ctl.on_update_start(2)
    original = json.loads(file.read_text())
    original["changes"]["2"]["rewards"]["slow_track"] = .3
    file.write_text(json.dumps(original))
    assert ctl.on_update_start(3)["kind"] == "rejected"
    (tmp_path / "ex42_update_adjust_m2.json").unlink()
    with pytest.raises(RuntimeError, match="without a receipt"):
        ctl.on_update_start(4)


def test_explicit_stage_change_records_evidence_and_round_trips(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, monitor={"slow_forward": "consolidating"})
    receipt = ctl.on_update_start(2)
    assert runtime.live_metrics.stage["slow_forward"] == "consolidating"
    assert receipt["evidence"] == "m250/m500 sheet"
    assert receipt["after"]["monitor"] == {"slow_forward": "consolidating"}
