"""ex42_slow_overspeed: the one-sided overspeed penalty of the slow band (candidate C, lead 2026-11-19 23:03), registered at weight 0. CPU only."""
from __future__ import annotations

import hashlib
import types
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.rewards import ex42_slow_overspeed as so

ROOT = Path(__file__).resolve().parents[2]
K = {"speed_min": 0.1, "speed_max": 0.3}


def value(velocity, command, turn=0.0, **extra):
    return float(so.slow_overspeed_value(torch.tensor([velocity]), torch.tensor([command]), torch.tensor([turn]), **{**K, **extra})[0])


def test_no_overspeed_is_zero_and_an_overshoot_of_the_command_is_minus_one():
    assert value([0.0, 0.0], [0.2, 0.0]) == 0.0                       # standing: slow_progress charges that, not this
    assert value([0.1, 0.0], [0.2, 0.0]) == 0.0                       # too slow
    assert value([0.2, 0.0], [0.2, 0.0]) == pytest.approx(0.0, abs=1e-6)                       # exactly the command
    assert value([0.227, 0.0], [0.2, 0.0]) == pytest.approx(-0.135)   # m1100: 0.027 over a 0.2 command
    assert value([0.4, 0.0], [0.2, 0.0]) == pytest.approx(-1.0)       # overshoot |c|
    assert value([0.9, 0.0], [0.2, 0.0]) == pytest.approx(-1.0)       # clipped
    assert value([-0.3, 0.0], [0.2, 0.0]) == 0.0                      # backwards is not overspeed


def test_the_direction_is_the_commanded_one_and_the_mirror_of_slow_progress():
    assert value([0.0, 0.4], [0.0, 0.2]) == pytest.approx(-1.0)       # a side command is measured along itself
    assert value([0.4, 0.0], [0.0, 0.2]) == 0.0                       # fast across the command: no overspeed along it
    from foothold_s2.rewards import ex42_slow_progress as sp
    for v in (0.0, 0.1, 0.2):
        p = float(sp.slow_progress_value(torch.tensor([[v, 0.0]]), torch.tensor([[0.2, 0.0]]), torch.tensor([0.0]), **K)[0])
        assert p == pytest.approx(v / 0.2) and value([v, 0.0], [0.2, 0.0]) == pytest.approx(0.0, abs=1e-6)      # below the command only slow_progress pays


@pytest.mark.parametrize("command", [[0.05, 0.0], [0.3, 0.0], [0.8, 0.0]])
def test_outside_the_band_the_term_is_off(command):
    assert value([2.0, 0.0], command) == 0.0


def test_excluded_envs_and_turn_commands_give_zero_and_heading_envs_count():
    v, c = torch.tensor([[0.4, 0.0]] * 3), torch.tensor([[0.2, 0.0]] * 3)
    ex = torch.tensor([False, True, False])
    out = so.slow_overspeed_value(v, c, torch.tensor([0.0, 0.0, 0.5]), excluded=ex, **K)
    assert out.tolist() == pytest.approx([-1.0, 0.0, 0.0])             # excluded env 0, a free env with a turn command 0
    heading = torch.tensor([False, False, True])
    out = so.slow_overspeed_value(v, c, torch.tensor([0.0, 0.0, 0.5]), excluded=ex, turn_exempt=heading, **K)
    assert out.tolist() == pytest.approx([-1.0, 0.0, -1.0])
    with pytest.raises(ValueError, match="nonfinite"):
        so.slow_overspeed_value(torch.tensor([[float("nan"), 0.0]]), torch.tensor([[0.2, 0.0]]), torch.tensor([0.0]), **K)


class _Term:
    heading = torch.tensor([False, False, False, False, False])
    is_flag_env = torch.tensor([False, False, False, False, True])


class _Scene:
    def __init__(self, types_, robot):
        self.terrain, self._robot = types.SimpleNamespace(terrain_types=torch.tensor(types_)), robot

    def __getitem__(self, key):
        return self._robot


def _fake_env(types_, table=True):
    n = len(types_)
    robot = types.SimpleNamespace(data=types.SimpleNamespace(root_lin_vel_b=torch.tensor([[0.4, 0.0, 0.0]] * n)))
    env = types.SimpleNamespace(
        command_manager=types.SimpleNamespace(get_command=lambda name: torch.tensor([[0.2, 0.0, 0.0]] * n), get_term=lambda name: _Term),
        scene=_Scene(types_, robot))
    if table:
        env._ex42_column_table = [{"family": "A", "kind": "pyramid_stairs"}, {"family": "A", "kind": "gaps"}, {"family": "A", "kind": "flat"},
                                  {"family": "B", "kind": "gap"}, {"family": "C", "kind": "gap"}, {"family": "B", "kind": "rough"}]
    return env


def test_gap_sparse_and_flag_envs_are_left_out_through_the_term_function():
    env = _fake_env([0, 1, 2, 3, 0])                     # stairs, A gaps, flat, B gap, stairs (env 4 is the flag env)
    out = so.slow_overspeed_term(env, "base_velocity", **K).tolist()
    assert out == pytest.approx([-1.0, 0.0, -1.0, 0.0, 0.0])     # continuous columns pay, the gap / sparse columns and the flag env do not
    assert so.slow_overspeed_term(_fake_env([5, 4, 5, 0, 0]), "base_velocity", **K).tolist() == pytest.approx([0.0, 0.0, 0.0, -1.0, 0.0])   # B/rough is B family: sparse by the project rule
    with pytest.raises(ValueError, match="column table"):
        so.slow_overspeed_term(_fake_env([0, 0, 0, 0, 0], table=False), "base_velocity", **K)


class _Cfg:
    def __init__(self, func=None, weight=0.0, params=None):
        self.func, self.weight, self.params = func, weight, dict(params or {})


def _env_cfg():
    return types.SimpleNamespace(rewards=types.SimpleNamespace(track_lin_vel=_Cfg(weight=2.0, params={"std": 0.5}),
                                                               track_ang_vel=_Cfg(weight=1.0, params={"std": 0.5}),
                                                               ex41_feet_air_time=_Cfg(params={"name": "feet_air_time"})))


def _opened_limits(tmp_path, pair="[-1.0, 0.0]"):
    text = adj.REWARD_LIMITS.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines()]
    at = max(i for i, ln in enumerate(lines) if ln.strip().startswith("slow_progress:"))
    lines.insert(at + 1, f"  slow_overspeed: {pair}")
    path = tmp_path / "limits.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_registered_at_weight_zero_and_it_turns_on_through_the_segment_entry_seam(tmp_path):
    """The seam train_start calls (apply_reward_params): the term is added at weight 0, follows the slow_track band, and an entry that
    asks for -0.3 under an opened fence puts -0.3 on the live term. Without an opened fence the same ask is refused."""
    plan = EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    row = adj.stage_rewards(plan, "E1")
    assert row["slow_overspeed"] == 0.0                          # a plan row without the cell means off
    env_cfg = _env_cfg()
    out = adj.apply_reward_params(env_cfg, {"rewards": {"values": row}}, _Cfg)
    term = env_cfg.rewards.ex42_slow_overspeed
    assert term.weight == 0.0 and term.func is so.slow_overspeed_term and out["slow_overspeed"] == {"before": 0.0, "after": 0.0}
    assert term.params == {"command_name": "base_velocity", "speed_min": 0.1, "speed_max": 0.3, "include_heading": True}
    assert so.register(env_cfg, _Cfg) is False
    with pytest.raises(ValueError, match="slow_overspeed"):
        adj._rewards({**row, "slow_overspeed": -0.3}, adj.reward_limits(), "closed")          # the shipped fence is closed at 0
    opened = adj.reward_limits(_opened_limits(tmp_path))
    ask = adj._rewards({**row, "slow_overspeed": -0.3}, opened, "opened")
    assert ask["slow_overspeed"] == -0.3
    with pytest.raises(ValueError, match="slow_overspeed"):
        adj._rewards({**row, "slow_overspeed": 0.1}, opened, "opened")                         # a bonus is not a penalty
    with pytest.raises(ValueError, match="slow_overspeed"):
        adj._rewards({**row, "slow_overspeed": -1.5}, opened, "opened")
    env_cfg = _env_cfg()
    assert adj.apply_reward_params(env_cfg, {"rewards": {"values": ask}}, _Cfg)["slow_overspeed"] == {"before": 0.0, "after": -0.3}
    assert env_cfg.rewards.ex42_slow_overspeed.weight == -0.3


def test_a_manager_without_the_term_reads_as_off_and_a_weight_asked_of_it_fails_the_readback():
    plan = EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    row = adj.stage_rewards(plan, "E1")
    live = {"track_lin_vel": _Cfg(weight=2.0, params={"std": row["track_lin_vel_std"]}),
            "track_ang_vel": _Cfg(weight=1.0, params={"std": row["track_ang_vel_std"]}),
            "ex41_feet_air_time": _Cfg(weight=row["feet_air_time"], params={"threshold": row["feet_air_time_threshold"]}),
            "ex41_foot_slip": _Cfg(weight=row["foot_slip"]), "ex41_zero_yaw": _Cfg(weight=row["zero_yaw"]),
            "ex42_slow_track": _Cfg(weight=row["slow_track"], params={"sigma": row["slow_track_sigma"], "speed_min": 0.1, "speed_max": 0.3}),
            "ex42_slow_progress": _Cfg(weight=row["slow_progress"])}
    env = types.SimpleNamespace(reward_manager=types.SimpleNamespace(get_term_cfg=lambda name: live[name]))
    assert adj.reward_readback(env, {"rewards": {"values": row}})["live"]["slow_overspeed"] == 0.0
    with pytest.raises(ValueError, match="the live reward manager carries"):
        adj.reward_readback(env, {"rewards": {"values": {**row, "slow_overspeed": -0.2}}})


def _live(tmp_path, change, fence):
    """The real LiveAdjustment over a fake runtime whose manager carries the term (what apply_reward_params registers)."""
    import json
    from foothold_s2.ex42_live_adjust import LiveAdjustment
    from foothold_s2.tests.test_ex42_live_adjust_cpu import _setup
    ctl, runtime, file = _setup(tmp_path, iteration=2, rewards={"slow_track": 0.2})
    seg = tmp_path / "segment.yaml"
    extra = {"zero_yaw": [-2, -.5], "feet_air_time_threshold": [.04, .5], "slow_track": [0, .3], "slow_track_sigma": [.5, .5],
             "slow_track_speed_min": [.1, .1], "slow_track_speed_max": [.3, .3]}
    if fence is not None:
        extra["slow_overspeed"] = fence
    cfg = {"segment_reward_limits_sha256": hashlib.sha256(seg.read_bytes()).hexdigest(), "extra_reward_limits": extra,
           "command_limits": {"low_forward_fraction": [.2, .5]}, "runtime_limits": {"policy_std_cap": [0, 2], "terrain_level_cap": [5, 9]},
           "runtime_start": {"policy_std_cap": 0.0}}
    doc = json.loads(file.read_text())
    doc["changes"]["2"] = {"decided_by": "lead", "decided_at": "2026-11-19T23:30+09:00", "evidence": "m1100 overspeed", "rewards": {"slow_overspeed": change}}
    file.write_text(json.dumps(doc))
    return LiveAdjustment(runtime, cfg, plan_sha256="a" * 64, path=file, log_dir=tmp_path / "log", segment_limits_path=seg), runtime


def test_the_live_adjustment_takes_a_negative_weight_inside_the_row_fence_and_refuses_the_rest(tmp_path):
    ctl, runtime = _live(tmp_path / "ok", -0.3, [-1.0, 0.0])
    out = ctl.on_update_start(2)
    assert out["after"]["rewards"]["slow_overspeed"] == -0.3
    assert runtime.env.reward_manager.get_term_cfg("ex42_slow_overspeed").weight == -0.3        # on from the next rollout
    for name, change, fence in (("closed", -0.3, None), ("bonus", 0.1, [-1.0, 0.0]), ("too_big", -1.5, [-1.0, 0.0])):
        ctl, runtime = _live(tmp_path / name, change, fence)
        out = ctl.on_update_start(2)
        assert out["kind"] == "rejected" and "slow_overspeed" in out["reason"], name
        assert runtime.env.reward_manager.get_term_cfg("ex42_slow_overspeed").weight == 0.0
