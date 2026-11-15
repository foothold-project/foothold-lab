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


def _runtime_parts(std=(.8, 1.0), level_cap=5):
    """A policy with a std parameter and a terrain whose three columns carry the exposure tensors apply_exposure leaves."""
    import torch
    policy = SimpleNamespace(std=torch.nn.Parameter(torch.tensor(std)))
    terrain = SimpleNamespace(terrain_origins=torch.zeros(10, 3, 3), exposure_level_caps=torch.tensor([level_cap, level_cap, 0]),
                              exposure_open_columns=torch.tensor([True, True, False]))
    return policy, terrain


def _setup(tmp_path, *, iteration=2, rewards=None, commands=None, monitor=None, runtime=None):
    from foothold_s2.commands.ex42_segment_adjust import REWARD_LIMITS
    tmp_path.mkdir(parents=True, exist_ok=True)
    segment = tmp_path / "segment.yaml"
    segment.write_bytes(REWARD_LIMITS.read_bytes())
    config = {"segment_reward_limits_sha256": hashlib.sha256(segment.read_bytes()).hexdigest(),
              "extra_reward_limits": {"zero_yaw": [-2, -.5], "feet_air_time_threshold": [.04, .5],
                                      "slow_track": [0, .3], "slow_track_sigma": [.5, .5],
                                      "slow_track_speed_min": [.1, .1], "slow_track_speed_max": [.3, .3]},
              "command_limits": {"low_forward_fraction": [.2, .5]},
              "runtime_limits": {"policy_std_cap": [0, 2], "terrain_level_cap": [5, 9]},
              "runtime_start": {"policy_std_cap": 0.0}}
    entry = {"decided_by": "lead", "decided_at": "2026-11-14T00:09+09:00", "evidence": "m250/m500 sheet"}
    if rewards is not None:
        entry["rewards"] = rewards
    if commands is not None:
        entry["commands"] = commands
    if monitor is not None:
        entry["monitor"] = monitor
    if runtime is not None:
        entry["runtime"] = runtime
    file = tmp_path / "adjust.json"
    file.write_text(json.dumps({"schema": SCHEMA, "stage_id": "E1", "plan_sha256": "a" * 64,
                                "changes": {str(iteration): entry}}))
    stage = Stage()
    policy, terrain = _runtime_parts()
    runtime = SimpleNamespace(stage_id="E1",
                              env=SimpleNamespace(reward_manager=Manager(), scene=SimpleNamespace(terrain=terrain),
                                                  _ex41_terrain={"policy": "performance", "level_cap": 5}),
                              level_cap=5, effective={"terrain": {"level_cap": 5}}, policy_std_cap=0.0,
                              runner=SimpleNamespace(alg=SimpleNamespace(policy=policy)),
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


def test_slow_progress_can_be_adjusted_inside_approved_fence(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_progress": 0.0})
    record = ctl.on_update_start(2)
    assert record["after"]["rewards"]["slow_progress"] == 0.0
    assert runtime.env.reward_manager.get_term_cfg("ex42_slow_progress").weight == 0.0
    outside = tmp_path / "outside"
    outside.mkdir()
    changed, runtime2, _ = _setup(outside, rewards={"slow_progress": 0.2})
    assert changed.on_update_start(2)["after"]["rewards"]["slow_progress"] == 0.2
    assert runtime2.env.reward_manager.get_term_cfg("ex42_slow_progress").weight == 0.2


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


@pytest.mark.parametrize('adjusted_first', [False, True])
def test_within_limit_unchanged_reward_without_receipt_stops_before_rollout(tmp_path, adjusted_first):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    if adjusted_first:
        ctl.on_update_start(2)
    runtime.env.reward_manager.get_term_cfg("ex41_zero_yaw").weight = -1.5
    with pytest.raises(RuntimeError, match="without a receipt"):
        ctl.on_update_start(3 if adjusted_first else 1)


def test_unchanged_cell_outside_limit_stops_before_next_rollout(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    ctl.on_update_start(2)
    runtime.env.reward_manager.get_term_cfg("ex42_slow_progress").weight = .35
    with pytest.raises(RuntimeError, match="slow_progress.*outside approved limit"):
        ctl.on_update_start(3)


def test_resume_rejects_out_of_limit_receipt_before_applying_it(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    ctl.on_update_start(2)
    path = tmp_path / "ex42_update_adjust_m2.json"
    receipt = json.loads(path.read_text())
    receipt["after"]["rewards"]["slow_progress"] = .35
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


# ---- v28 run-time cells: policy std cap (off by default) and the terrain level cap (held by the plan) -----------------
def _std(runtime):
    return float(runtime.runner.alg.policy.std.max())


def _second_change(file, iteration, entry):
    doc = json.loads(file.read_text())
    doc["changes"][str(iteration)] = entry
    file.write_text(json.dumps(doc))


def _entry(**cells):
    return {"decided_by": "lead", "decided_at": "2026-11-14T13:30+09:00", "evidence": "probe row", **cells}


def test_runtime_cells_are_registered_off_in_the_real_plan_and_both_copies_agree():
    import hashlib as _h
    import yaml
    from pathlib import Path
    from foothold_s2.commands.ex42_segment_adjust import REWARD_LIMITS, reward_limits
    plan = yaml.safe_load((Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml").read_text(encoding="utf-8"))
    row = next(r for r in plan["stages"] if r["id"] == "E1")
    live, cap = row["live_adjustment"], row["terrain"]["continuous_level_cap"]
    assert live["runtime_start"] == {"policy_std_cap": 0.0}                     # off at the start
    assert {k: tuple(map(float, v)) for k, v in live["runtime_limits"].items()} == reward_limits()["runtime_cells"]
    assert live["segment_reward_limits_sha256"] == _h.sha256(REWARD_LIMITS.read_bytes()).hexdigest()
    assert cap["start"] == cap["end"] == 5                                      # the plan holds the first segment's cap
    assert live["runtime_limits"]["terrain_level_cap"][0] == cap["start"]       # and the cell starts where the plan holds it
    from foothold_s2.ex42_live_adjust import limits_from_plan
    assert set(limits_from_plan(live)["runtime"]) == {"policy_std_cap", "terrain_level_cap"}


def test_plan_and_limits_file_that_disagree_on_a_runtime_cell_are_refused(tmp_path):
    from foothold_s2.ex42_live_adjust import limits_from_plan
    from foothold_s2.commands.ex42_segment_adjust import REWARD_LIMITS
    live = {"segment_reward_limits_sha256": hashlib.sha256(REWARD_LIMITS.read_bytes()).hexdigest(),
            "extra_reward_limits": {"zero_yaw": [-2, -.5], "feet_air_time_threshold": [.04, .5], "slow_track": [0, .3],
                                    "slow_track_sigma": [.5, .5], "slow_track_speed_min": [.1, .1], "slow_track_speed_max": [.3, .3]},
            "command_limits": {"low_forward_fraction": [.2, .5]},
            "runtime_limits": {"policy_std_cap": [0, 2], "terrain_level_cap": [5, 12]}}
    with pytest.raises(ValueError, match="terrain_level_cap differs from segment fence"):
        limits_from_plan(live)
    del live["runtime_limits"]
    with pytest.raises(ValueError, match="run-time cells must be in both"):
        limits_from_plan(live)


def test_nothing_is_capped_while_the_cells_are_off(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    runtime.runner.alg.policy.std.data.fill_(1.5)
    assert ctl.on_update_start(1) is None
    assert _std(runtime) == 1.5 and runtime.policy_std_cap == 0.0 and runtime.level_cap == 5


def test_std_cap_applies_clamps_every_update_and_turns_off(tmp_path):
    ctl, runtime, file = _setup(tmp_path, runtime={"policy_std_cap": .9})
    record = ctl.on_update_start(2)
    assert record["before"]["runtime"]["policy_std_cap"] == 0.0 and record["after"]["runtime"]["policy_std_cap"] == .9
    assert _std(runtime) == pytest.approx(.9)                                    # the first rollout already runs at the cap
    runtime.runner.alg.policy.std.data.fill_(1.0)                                # learning pushed it up again
    assert ctl.on_update_start(3) is None
    assert _std(runtime) == pytest.approx(.9)
    _second_change(file, 4, _entry(runtime={"policy_std_cap": 0.0}))             # the lead turns it off
    assert ctl.on_update_start(4)["after"]["runtime"]["policy_std_cap"] == 0.0
    runtime.runner.alg.policy.std.data.fill_(1.0)
    ctl.on_update_start(5)
    assert _std(runtime) == 1.0


def test_std_cap_below_point_eight_of_the_current_std_is_rejected(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, runtime={"policy_std_cap": .79})          # largest current std 1.0
    result = ctl.on_update_start(2)
    assert result["kind"] == "rejected" and "0.8 x the current std" in result["reason"]
    assert runtime.policy_std_cap == 0.0 and _std(runtime) == 1.0
    ctl2, runtime2, _ = _setup(tmp_path / "edge", runtime={"policy_std_cap": .8})      # exactly 0.8 x is allowed
    assert ctl2.on_update_start(2)["after"]["runtime"]["policy_std_cap"] == .8


def test_std_cap_outside_the_fence_is_rejected(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, runtime={"policy_std_cap": 2.5})
    assert ctl.on_update_start(2)["kind"] == "rejected" and runtime.policy_std_cap == 0.0


def test_terrain_cap_is_raised_live_in_every_place_that_reads_it(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, runtime={"terrain_level_cap": 6})
    record = ctl.on_update_start(2)
    assert record["before"]["runtime"]["terrain_level_cap"] == 5 and record["after"]["runtime"]["terrain_level_cap"] == 6
    terrain = runtime.env.scene.terrain
    assert runtime.level_cap == 6 and runtime.effective["terrain"]["level_cap"] == 6
    assert runtime.env._ex41_terrain["level_cap"] == 6                           # the promotion rule's cap
    assert terrain.exposure_level_caps.tolist() == [6, 6, 0]                     # the placement cap; the closed column stays 0


def test_terrain_cap_is_refused_below_the_fence_above_it_noninteger_and_below_the_cap_in_force(tmp_path):
    for value in (4, 10, 6.5):
        ctl, runtime, _ = _setup(tmp_path / f"v{value}", runtime={"terrain_level_cap": value})
        assert ctl.on_update_start(2)["kind"] == "rejected" and runtime.level_cap == 5
    ctl, runtime, file = _setup(tmp_path / "lower", runtime={"terrain_level_cap": 7})
    assert ctl.on_update_start(2)["after"]["runtime"]["terrain_level_cap"] == 7
    _second_change(file, 3, _entry(runtime={"terrain_level_cap": 6}))
    result = ctl.on_update_start(3)
    assert result["kind"] == "rejected" and "below the cap in force" in result["reason"] and runtime.level_cap == 7


def test_resume_restores_the_raised_cap_and_std_cap_from_the_receipt(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, runtime={"terrain_level_cap": 7, "policy_std_cap": .9})
    ctl.on_update_start(2)
    ctl2, runtime2, _ = _setup(tmp_path, runtime={"terrain_level_cap": 7, "policy_std_cap": .9})        # a new process, same folder
    assert runtime2.level_cap == 7 and runtime2.env._ex41_terrain["level_cap"] == 7
    assert runtime2.env.scene.terrain.exposure_level_caps.tolist() == [7, 7, 0] and runtime2.policy_std_cap == .9


def test_a_runtime_cell_changed_without_a_receipt_stops_the_run(tmp_path):
    ctl, runtime, _ = _setup(tmp_path, rewards={"slow_track": .2})
    runtime.policy_std_cap = .5
    with pytest.raises(RuntimeError, match="without a receipt"):
        ctl.on_update_start(1)
    ctl, runtime, _ = _setup(tmp_path / "terrain", rewards={"slow_track": .2})
    runtime.level_cap = 6
    with pytest.raises(RuntimeError, match="without a receipt"):
        ctl.on_update_start(1)


def test_a_plan_that_starts_the_std_cap_on_or_a_runtime_that_does_is_refused(tmp_path):
    ctl, runtime, _ = _setup(tmp_path)
    config = {**{k: v for k, v in {"x": 1}.items()}}
    from foothold_s2.ex42_live_adjust import LiveAdjustment
    base = dict(segment_reward_limits_sha256=ctl.limits["segment_limits_sha256"])
    runtime.policy_std_cap = .9
    cfg = {"segment_reward_limits_sha256": ctl.limits["segment_limits_sha256"],
           "extra_reward_limits": {"zero_yaw": [-2, -.5], "feet_air_time_threshold": [.04, .5], "slow_track": [0, .3],
                                   "slow_track_sigma": [.5, .5], "slow_track_speed_min": [.1, .1], "slow_track_speed_max": [.3, .3]},
           "command_limits": {"low_forward_fraction": [.2, .5]},
           "runtime_limits": {"policy_std_cap": [0, 2], "terrain_level_cap": [5, 9]},
           "runtime_start": {"policy_std_cap": 0.0}}
    segment = tmp_path / "segment.yaml"
    with pytest.raises(ValueError, match="must start off"):
        LiveAdjustment(runtime, cfg, plan_sha256="a" * 64, path=None, log_dir=tmp_path / "fresh", segment_limits_path=segment)


def test_raise_open_cap_on_the_terrain_apply_exposure_leaves_behind():
    import types as _t
    import torch
    from foothold_s2.terrains import ex42_exposure as ex

    rows, cols, envs = 10, 4, 8
    terrain = _t.SimpleNamespace(terrain_origins=torch.zeros(rows, cols, 3), terrain_levels=torch.zeros(envs, dtype=torch.long),
                                 terrain_types=torch.zeros(envs, dtype=torch.long), env_origins=torch.zeros(envs, 3))

    def update(env_ids, move_up, move_down):
        terrain.terrain_levels[env_ids] += move_up.long() * 3 - move_down.long()
    terrain.update_env_origins = update
    ex.apply_exposure(terrain, [1.0, 1.0, 0.0, 0.0], [5, 5, 0, 0])
    ids = torch.arange(envs)
    terrain.update_env_origins(ids, torch.ones(envs, dtype=torch.bool), torch.zeros(envs, dtype=torch.bool))
    terrain.update_env_origins(ids, torch.ones(envs, dtype=torch.bool), torch.zeros(envs, dtype=torch.bool))
    assert int(terrain.terrain_levels.max()) == 5                                # six levels asked, cut at the cap 5
    ex.raise_open_cap(terrain, 5, 7)
    terrain.update_env_origins(ids, torch.ones(envs, dtype=torch.bool), torch.zeros(envs, dtype=torch.bool))
    assert int(terrain.terrain_levels.max()) == 7                                # the wrapped update now cuts at 7
    with pytest.raises(ValueError, match="raised only"):
        ex.raise_open_cap(terrain, 7, 6)
    terrain.exposure_level_caps[1] = 6
    with pytest.raises(ValueError, match="one cap"):
        ex.raise_open_cap(terrain, 7, 8)
    ex.raise_open_cap(terrain, 7, 99) if False else None
