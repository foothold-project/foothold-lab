"""ex42_slow_progress: one-sided progress along a slow command, registered at weight 0 (decisions.tsv 2026-11-14 01:21,
ledger commit 06d4a1ae). CPU only."""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.rewards import ex42_slow_progress as sp
from foothold_s2.rewards import ex42_slow_track as st

ROOT = Path(__file__).resolve().parents[2]
K = {"speed_min": 0.1, "speed_max": 0.3}


def value(velocity, command, turn=0.0, **extra):
    return float(sp.slow_progress_value(torch.tensor([velocity]), torch.tensor([command]), torch.tensor([turn]),
                                        **{**K, **extra})[0])


def test_standing_pays_nothing_and_walking_as_told_or_faster_pays_one():
    assert value([0.0, 0.0], [0.1, 0.0]) == 0.0                                   # standing still
    assert value([0.1, 0.0], [0.1, 0.0]) == pytest.approx(1.0)                    # as told
    assert value([0.2, 0.0], [0.1, 0.0]) == pytest.approx(1.0)                    # the slowest gait the policy has: still 1
    assert value([0.05, 0.0], [0.1, 0.0]) == pytest.approx(0.5)                   # half way
    assert value([-0.2, 0.0], [0.1, 0.0]) == pytest.approx(-1.0)                  # backwards: charged, clipped at -1
    assert value([-0.05, 0.0], [0.1, 0.0]) == pytest.approx(-0.5)
    rock = [value([v, 0.0], [0.1, 0.0]) for v in (0.3, -0.3, 0.3, -0.3)]          # rocking back and forth is not paid
    assert sum(rock) == pytest.approx(0.0)
    # the reason for the term: slow_track cannot tell 0.2 m/s from standing under a 0.1 m/s command, this term can
    track = lambda v: float(st.slow_track_value(torch.tensor([v]), torch.tensor([[0.1, 0.0]]), torch.zeros(1),      # noqa: E731
                                                speed_min=0.1, speed_max=0.3, sigma=0.5)[0])
    assert track([0.2, 0.0]) == pytest.approx(track([0.0, 0.0]))
    assert value([0.2, 0.0], [0.1, 0.0]) - value([0.0, 0.0], [0.1, 0.0]) == pytest.approx(1.0)


def test_the_direction_is_the_commanded_one():
    assert value([0.0, 0.2], [0.0, 0.2]) == pytest.approx(1.0)                    # a slow side command, walking sideways
    assert value([0.0, -0.2], [0.0, -0.2]) == pytest.approx(1.0)
    assert value([0.2, 0.0], [0.0, 0.2]) == 0.0                                   # walking forward under a side command
    assert value([0.0, -0.2], [0.0, 0.2]) == pytest.approx(-1.0)                  # the wrong side (body frame: +y is left)
    assert value([0.0, 0.2], [0.0, -0.2]) == pytest.approx(-1.0)
    assert value([-0.2, 0.0], [-0.25, 0.0]) == pytest.approx(0.8)                 # a slow reverse command
    diagonal = value([0.1, 0.1], [0.14, 0.14])                                    # |c| 0.198: the projection is 0.1414
    assert diagonal == pytest.approx(0.1414 / 0.198, rel=1e-2)


@pytest.mark.parametrize("command", [[0.3, 0.0], [0.5, 0.0], [0.0999, 0.0], [0.0, 0.0]])
def test_outside_the_band_the_term_is_off(command):
    assert value(command, command) == 0.0


def test_the_band_edges_are_the_slow_track_ones():
    assert value([0.1, 0.0], [0.1, 0.0]) > 0.0 and value([0.2999, 0.0], [0.2999, 0.0]) > 0.0


def test_the_upper_edge_tapers_to_zero_instead_of_jumping():
    full = lambda c, **extra: value([c, 0.0], [c, 0.0], **extra)      # noqa: E731  walking exactly as told
    assert full(0.25, taper_from=0.25) == pytest.approx(1.0) and full(0.2, taper_from=0.25) == pytest.approx(1.0)
    assert full(0.275, taper_from=0.25) == pytest.approx(0.5, abs=1e-4)
    assert full(0.2999, taper_from=0.25) == pytest.approx(0.002, abs=1e-3) and full(0.3, taper_from=0.25) == 0.0
    assert full(0.2999) == pytest.approx(1.0)                         # without a taper the edge jumps (the old shape)
    with pytest.raises(ValueError, match='speed_min <= taper_from <= speed_max'):
        full(0.2, taper_from=0.35)


def test_a_free_env_with_a_turn_command_is_off_and_bad_inputs_are_refused():
    assert value([0.2, 0.0], [0.2, 0.0], turn=0.3) == 0.0
    with pytest.raises(ValueError, match="nonfinite command"):
        sp.slow_progress_value(torch.zeros(1, 2), torch.tensor([[float("nan"), 0.0]]), torch.zeros(1), **K)
    with pytest.raises(ValueError, match="nonfinite active velocity"):
        sp.slow_progress_value(torch.tensor([[float("nan"), 0.0]]), torch.tensor([[0.2, 0.0]]), torch.zeros(1), **K)
    for bad in ({"speed_min": 0.0}, {"speed_min": 0.3, "speed_max": 0.3}):
        with pytest.raises(ValueError, match="0 < speed_min < speed_max"):
            value([0.0, 0.0], [0.2, 0.0], **bad)
    # an inactive env may carry a nonfinite velocity: it is not read
    out = sp.slow_progress_value(torch.tensor([[float("nan"), 0.0]]), torch.tensor([[0.5, 0.0]]), torch.zeros(1), **K)
    assert float(out[0]) == 0.0


def _env(command, velocity, heading, flag):
    term = types.SimpleNamespace(heading=heading, is_flag_env=flag)
    manager = types.SimpleNamespace(get_command=lambda name: command, get_term=lambda name: term)
    robot = types.SimpleNamespace(data=types.SimpleNamespace(root_lin_vel_b=velocity))
    return types.SimpleNamespace(command_manager=manager, scene={"robot": robot})


def test_heading_envs_count_and_flag_envs_do_not():
    """A heading env's turn command comes from its controller; a flag env is left out whatever its command is."""
    command = torch.tensor([[0.2, 0.0, 0.4], [0.2, 0.0, 0.4], [0.2, 0.0, 0.0], [0.2, 0.0, 0.0]])
    velocity = torch.tensor([[0.2, 0.0, 9.0]] * 4)                               # the third column is vz: unread
    heading = torch.tensor([True, False, False, True])
    flag = torch.tensor([False, False, False, True])
    env = _env(command, velocity, heading, flag)
    assert sp.slow_progress_term(env, "base_velocity", **K).tolist() == [1.0, 0.0, 1.0, 0.0]
    assert sp.slow_progress_term(env, "base_velocity", include_heading=False, **K).tolist() == [0.0, 0.0, 1.0, 0.0]
    with pytest.raises(ValueError, match="needs the command term's heading and is_flag_env masks"):
        broken = _env(command, velocity, heading, flag)
        broken.command_manager.get_term = lambda name: types.SimpleNamespace(heading=heading)
        sp.slow_progress_term(broken, "base_velocity", **K)


class _Cfg:
    def __init__(self, func=None, weight=0.0, params=None):
        self.func, self.weight, self.params = func, weight, dict(params or {})


def test_the_term_is_registered_at_the_plan_weight_and_follows_the_slow_track_band():
    rewards = types.SimpleNamespace(track_lin_vel=_Cfg(weight=2.0, params={"std": 0.5}),
                                    track_ang_vel=_Cfg(weight=1.0, params={"std": 0.5}),
                                    ex41_feet_air_time=_Cfg(params={"name": "feet_air_time"}))
    env_cfg = types.SimpleNamespace(rewards=rewards)
    plan = EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    row = adj.stage_rewards(plan, "E1")
    assert row["slow_progress"] == 0.2 and adj.reward_limits()["cells"]["slow_progress"] == (0.0, 0.3)   # v28, ledger b6024dd2
    out = adj.apply_reward_params(env_cfg, {"rewards": {"values": row}}, _Cfg)
    term = env_cfg.rewards.ex42_slow_progress
    assert term.weight == 0.2 and term.func is sp.slow_progress_term and out["slow_progress"] == {"before": 0.0, "after": 0.2}
    assert term.params == {"command_name": "base_velocity", "speed_min": 0.1, "speed_max": 0.3, "taper_from": 0.25,
                           "include_heading": True}
    assert adj.apply_reward_params(env_cfg, {"rewards": {"values": row}}, _Cfg)["slow_progress"]["after"] == 0.2    # again: no second term
    assert sp.register(env_cfg, _Cfg) is False


def test_the_fence_refuses_a_weight_above_its_upper_limit_until_it_is_opened(tmp_path):
    plan = EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    row = adj.stage_rewards(plan, "E1")
    with pytest.raises(ValueError, match="rewards.slow_progress leaves the approved limits"):
        adj._rewards({**row, "slow_progress": 0.35}, adj.reward_limits(), "test")
    text = adj.REWARD_LIMITS.read_text(encoding="utf-8").replace("slow_progress: [0.0, 0.3]", "slow_progress: [0.0, 0.5]")
    opened = tmp_path / "limits.yaml"
    opened.write_text(text, encoding="utf-8")
    assert adj._rewards({**row, "slow_progress": 0.35}, adj.reward_limits(opened), "test")["slow_progress"] == 0.35


def test_documents_older_than_the_cell_stay_readable_with_the_term_off(tmp_path):
    """A ten-cell row, entry, limits file or readback means slow_progress 0."""
    plan = EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    row = adj.stage_rewards(plan, "E1")
    ten = {name: value for name, value in row.items() if name != "slow_progress"}
    off = {**row, "slow_progress": 0.0}                     # a row without the cell means the term off, not the plan value
    assert adj._rewards(ten, adj.reward_limits(), "old row") == off
    old_limits = tmp_path / "old_limits.yaml"
    lines = [line for line in adj.REWARD_LIMITS.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("slow_progress:")]
    old_limits.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert adj.reward_limits(old_limits)["cells"]["slow_progress"] == (0.0, 0.0)
    assert adj.complete_cells(None) is None and adj.complete_cells(ten) == off
    # a live manager without the term reads as weight 0; asking for more than 0 then fails the readback
    live = {"track_lin_vel": _Cfg(weight=2.0, params={"std": row["track_lin_vel_std"]}),
            "track_ang_vel": _Cfg(weight=1.0, params={"std": row["track_ang_vel_std"]}),
            "ex41_feet_air_time": _Cfg(weight=row["feet_air_time"], params={"threshold": row["feet_air_time_threshold"]}),
            "ex41_foot_slip": _Cfg(weight=row["foot_slip"]), "ex41_zero_yaw": _Cfg(weight=row["zero_yaw"]),
            "ex42_slow_track": _Cfg(weight=row["slow_track"], params={"sigma": 0.5, "speed_min": 0.1, "speed_max": 0.3})}
    manager = types.SimpleNamespace(get_term_cfg=lambda name: live[name])
    env = types.SimpleNamespace(reward_manager=manager)
    assert adj.reward_readback(env, {"rewards": {"values": ten}})["live"]["slow_progress"] == 0.0
    with pytest.raises(ValueError, match="the live reward manager carries"):
        adj.reward_readback(env, {"rewards": {"values": {**row, "slow_progress": 0.1}}})
    assert json.dumps(adj.reward_readback(env, {"rewards": {"values": off}})["live"], sort_keys=True)
