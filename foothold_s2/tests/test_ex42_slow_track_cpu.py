"""EX-42 slow-command relative tracking term and its reward cells (decisions.tsv 2026-11-13 15:30). CPU only."""
from __future__ import annotations

import json
import math
import types
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.rewards import ex42_slow_track as st
from foothold_s2.scripts import ex42_training_entry as te

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
K = dict(st.DEFAULTS)


def value(vel, cmd, wz=0.0, **k):
    return float(st.slow_track_value(torch.tensor([vel], dtype=torch.float32), torch.tensor([cmd], dtype=torch.float32),
                                     torch.tensor([wz], dtype=torch.float32), **{**K, **k})[0])


def test_walking_as_told_is_one_and_standing_is_the_same_small_value_at_every_slow_speed():
    stand = math.exp(-1.0 / 0.25)                                              # relative error 1, sigma 0.5
    for speed in (0.1, 0.15, 0.2, 0.29):                                       # the lower edge is inside the band
        assert value([speed, 0.0], [speed, 0.0]) == pytest.approx(1.0)
        assert value([0.0, 0.0], [speed, 0.0]) == pytest.approx(stand, rel=1e-5)
    assert stand == pytest.approx(0.0183, abs=1e-4)
    assert value([0.1, 0.0], [0.2, 0.0]) == pytest.approx(math.exp(-0.25 / 0.25), rel=1e-5)      # half the speed


def test_slow_side_back_and_diagonal_commands_count_as_well():
    assert value([0.0, 0.2], [0.0, 0.2]) == pytest.approx(1.0)
    assert value([-0.2, 0.0], [-0.2, 0.0]) == pytest.approx(1.0)                # backwards
    assert value([0.0, 0.1], [0.0, 0.1]) == pytest.approx(1.0) and value([-0.1, 0.0], [-0.1, 0.0]) == pytest.approx(1.0)
    assert value([0.0, -0.15], [0.0, -0.15]) == pytest.approx(1.0)
    assert value([0.0, 0.0], [0.0, 0.2]) == pytest.approx(math.exp(-4.0), rel=1e-5)
    assert value([0.14, 0.14], [0.14, 0.14]) == pytest.approx(1.0)              # |c| = 0.198


@pytest.mark.parametrize("cmd, wz", [
    ([0.0, 0.0], 0.0),            # stand
    ([0.0999, 0.0], 0.0),         # just below the lower edge
    ([0.05, 0.0], 0.0),
    ([0.3, 0.0], 0.0),            # at the upper edge: the ordinary tracking term takes over
    ([0.8, 0.0], 0.0),
    ([0.2, 0.0], 0.3),            # a turn command: off, like zero_yaw
    ([0.2, 0.0], -0.01),
])
def test_outside_the_slow_band_or_with_a_turn_command_the_term_is_zero(cmd, wz):
    assert value(cmd, cmd, wz) == 0.0 and value([0.0, 0.0], cmd, wz) == 0.0


def test_no_nan_for_a_zero_command_and_bad_inputs_are_refused():
    out = st.slow_track_value(torch.zeros(3, 2), torch.zeros(3, 2), torch.zeros(3), **K)
    assert torch.isfinite(out).all() and float(out.abs().sum()) == 0.0
    inactive_nan = st.slow_track_value(torch.tensor([[float("nan"), 0.0]]), torch.tensor([[0.8, 0.0]]), torch.zeros(1), **K)
    assert float(inactive_nan[0]) == 0.0                                        # an inactive row is not read
    with pytest.raises(ValueError, match="nonfinite active velocity"):
        st.slow_track_value(torch.tensor([[float("nan"), 0.0]]), torch.tensor([[0.2, 0.0]]), torch.zeros(1), **K)
    with pytest.raises(ValueError, match="nonfinite command"):
        st.slow_track_value(torch.zeros(1, 2), torch.tensor([[float("inf"), 0.0]]), torch.zeros(1), **K)
    for bad in (dict(speed_min=0.3, speed_max=0.3), dict(speed_min=0.0), dict(sigma=0.0)):
        with pytest.raises(ValueError, match="slow track needs"):
            value([0.0, 0.0], [0.2, 0.0], **bad)


def test_the_constants_are_cells(tmp_path):
    assert value([0.0, 0.0], [0.2, 0.0], sigma=1.0) == pytest.approx(math.exp(-1.0), rel=1e-5)
    assert value([0.35, 0.0], [0.35, 0.0], speed_max=0.4) == pytest.approx(1.0) and value([0.35, 0.0], [0.35, 0.0]) == 0.0
    assert value([0.08, 0.0], [0.08, 0.0], speed_min=0.05) == pytest.approx(1.0) and value([0.08, 0.0], [0.08, 0.0]) == 0.0


def _env(command, velocity, heading, flag):
    term = types.SimpleNamespace(heading=heading, is_flag_env=flag)
    manager = types.SimpleNamespace(get_command=lambda name: {"base_velocity": command}[name],
                                    get_term=lambda name: {"base_velocity": term}[name])
    return types.SimpleNamespace(command_manager=manager,
                                 scene={"robot": types.SimpleNamespace(data=types.SimpleNamespace(root_lin_vel_b=velocity))})


def test_the_term_reads_the_body_frame_planar_velocity_and_the_command():
    command = torch.tensor([[0.2, 0.0, 0.0], [0.0, 0.2, 0.0], [0.2, 0.0, 0.5]])
    velocity = torch.tensor([[0.2, 0.0, 9.0], [0.0, 0.0, 9.0], [0.2, 0.0, 9.0]])           # the third column is vz: unread
    off = torch.zeros(3, dtype=torch.bool)
    out = st.slow_track_term(_env(command, velocity, off, off), "base_velocity", **K)
    assert out.tolist() == pytest.approx([1.0, math.exp(-4.0), 0.0], rel=1e-5)


def test_heading_envs_and_flag_envs_are_left_out_whatever_their_command_is():
    """Contract (lead 2026-11-13 15:41). Four envs walk a slow forward command exactly, with a zero turn command:
    a free one, a heading env whose controller happens to ask for no turn, a flag env, and one that is both."""
    command = torch.tensor([[0.2, 0.0, 0.0]] * 4)
    velocity = torch.tensor([[0.2, 0.0, 0.0]] * 4)
    heading = torch.tensor([False, True, False, True])
    flag = torch.tensor([False, False, True, True])
    assert st.slow_track_term(_env(command, velocity, heading, flag), "base_velocity", **K).tolist() == [1.0, 0.0, 0.0, 0.0]
    for broken in (types.SimpleNamespace(heading=heading), types.SimpleNamespace(is_flag_env=flag)):
        manager = types.SimpleNamespace(get_command=lambda name: command, get_term=lambda name, broken=broken: broken)
        env = types.SimpleNamespace(command_manager=manager, scene={"robot": types.SimpleNamespace(
            data=types.SimpleNamespace(root_lin_vel_b=velocity))})
        with pytest.raises(ValueError, match="needs the command term's heading and is_flag_env masks"):
            st.slow_track_term(env, "base_velocity", **K)


class _Cfg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_registration_adds_the_term_once_at_weight_zero_and_never_contains_the_tracking_name():
    env_cfg = types.SimpleNamespace(rewards=types.SimpleNamespace())
    assert st.register(env_cfg, _Cfg) is True and st.register(env_cfg, _Cfg) is False
    term = env_cfg.rewards.ex42_slow_track
    assert term.weight == 0.0 and term.func is st.slow_track_term
    assert term.params == {"command_name": "base_velocity", "speed_min": 0.1, "speed_max": 0.3, "sigma": 0.5}
    # start_runner picks the tracking columns by the substring "track_lin_vel" and needs exactly one of each
    assert "track_lin_vel" not in st.TERM and "track_ang_vel" not in st.TERM


def test_the_reward_manager_skips_a_term_of_weight_zero():
    """With weight 0 the total reward cannot change: Isaac Lab's reward manager does not call the term and adds 0.
    The installed source is read when it is on this machine; the arithmetic below is the same statement in numbers."""
    source = Path("/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py")
    if source.is_file():
        text = source.read_text(encoding="utf-8")
        skip = text.index("if term_cfg.weight == 0.0:")
        assert "continue" in text[skip:skip + 160] and text.index("term_cfg.func(self._env") > skip
    values = {"track_lin_vel": 0.8, "ex41_zero_yaw": 0.1, "ex42_slow_track": 0.9}
    weights = {"track_lin_vel": 2.0, "ex41_zero_yaw": -1.0, "ex42_slow_track": 0.0}
    with_term = sum(values[k] * weights[k] for k in values)
    without = sum(values[k] * weights[k] for k in values if k != "ex42_slow_track")
    assert with_term == without


# ---- the cells in the plan row, the limits file and the segment adjustment ----

@pytest.fixture(scope="module")
def plan():
    return EX42Plan.load(PLAN)


def view(plan):
    source = te.load_ex42_stage_zero_source(plan)
    return te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1")


def open_limits(tmp_path, **fences):
    """A copy of the shipped limits file with some of the closed slow-forward fences opened (as an approval would)."""
    text = adj.REWARD_LIMITS.read_text(encoding="utf-8")
    for name, fence in fences.items():
        closed = next(line for line in text.splitlines() if line.strip().startswith(name + ":"))
        text = text.replace(closed, f"  {name}: [{fence[0]}, {fence[1]}]")
    path = tmp_path / "limits_open.yaml"
    path.write_text(text, encoding="utf-8")
    return path


class _Term:
    def __init__(self, weight=0.0, **params):
        self.weight, self.params = weight, dict(params)


def terms():
    return {"track_lin_vel": _Term(2.0, std=0.5, command_name="base_velocity"),
            "track_ang_vel": _Term(1.0, std=0.5, command_name="base_velocity"),
            "ex41_feet_air_time": _Term(0.0, name="feet_air_time"), "ex41_foot_slip": _Term(-0.15),
            "ex41_zero_yaw": _Term(-1.0)}


def test_the_shipped_row_starts_with_the_term_off_and_the_fences_closed(plan, tmp_path):
    row = adj.stage_rewards(plan, "E1")
    assert (row["slow_track"], row["feet_air_time_threshold"], row["feet_air_time"]) == (0.0, 0.5, 0.0)
    assert (row["slow_track_sigma"], row["slow_track_speed_min"], row["slow_track_speed_max"]) == (0.5, 0.1, 0.3)
    limits = adj.reward_limits()["cells"]
    assert all(limits[name] == (row[name], row[name]) for name in
               ("slow_track", "feet_air_time_threshold", "slow_track_sigma", "slow_track_speed_min", "slow_track_speed_max"))
    for change in ({"slow_track": 0.1}, {"feet_air_time_threshold": 0.3}, {"slow_track_sigma": 0.4}):
        doc = {"schema": adj.SCHEMA, "stage_id": "E1", "plan_sha256": plan.sha256,
               "segments": {"1": {"decided_at": "t", "reason": "r", "evidence": "e", "rewards": {**row, **change}}}}
        path = tmp_path / "adjust.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError, match="leaves the approved limits"):
            adj.start_segment(view(plan), plan, "E1", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=False)


def test_the_first_segment_registers_the_term_and_changes_nothing_else(plan, tmp_path):
    live = terms()
    env_cfg = types.SimpleNamespace(rewards=types.SimpleNamespace(**{k: live[k] for k in
                                                                    ("track_lin_vel", "track_ang_vel", "ex41_feet_air_time")}))
    record = adj.start_segment(view(plan), plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path), write=True)
    out = adj.apply_reward_params(env_cfg, record, _Cfg)
    assert env_cfg.rewards.ex42_slow_track.weight == 0.0 and env_cfg.rewards.ex42_slow_track.func is st.slow_track_term
    assert out["slow_track"] == {"before": 0.0, "after": 0.0} and out["feet_air_time_threshold"] == {"before": 0.5, "after": 0.5}
    assert out["track_lin_vel_std"] == {"before": 0.5, "after": 0.35}                   # the one reward change of the start
    live["ex42_slow_track"] = env_cfg.rewards.ex42_slow_track
    manager = types.SimpleNamespace(get_term_cfg=lambda name: live[name])
    body = adj.reward_readback(types.SimpleNamespace(reward_manager=manager), record)
    assert body["live"] == record["rewards"]["values"] and body["live"]["slow_track"] == 0.0


def test_an_opened_fence_lets_a_boundary_switch_the_term_on_and_the_read_back_checks_it(plan, tmp_path):
    row = adj.stage_rewards(plan, "E1")
    asked = {**row, "slow_track": 0.5, "slow_track_sigma": 0.4, "feet_air_time_threshold": 0.25, "feet_air_time": 0.1}
    doc = {"schema": adj.SCHEMA, "stage_id": "E1", "plan_sha256": plan.sha256,
           "segments": {"1": {"decided_at": "t", "reason": "r", "evidence": "e", "rewards": asked}}}
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    limits = open_limits(tmp_path, slow_track=(0.0, 1.0), slow_track_sigma=(0.25, 0.5), feet_air_time_threshold=(0.2, 0.5))
    record = adj.start_segment(view(plan), plan, "E1", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=True,
                               limits_path=limits)
    live = terms()
    env_cfg = types.SimpleNamespace(rewards=types.SimpleNamespace(**{k: live[k] for k in
                                                                    ("track_lin_vel", "track_ang_vel", "ex41_feet_air_time")}))
    out = adj.apply_reward_params(env_cfg, record, _Cfg)
    term = env_cfg.rewards.ex42_slow_track
    assert term.weight == 0.5 and term.params["sigma"] == 0.4 and term.params["speed_max"] == 0.3
    assert live["ex41_feet_air_time"].params["threshold"] == 0.25
    assert out["slow_track"] == {"before": 0.0, "after": 0.5} and out["feet_air_time_threshold"] == {"before": 0.5, "after": 0.25}
    live["ex42_slow_track"] = term
    live["ex41_feet_air_time"].weight = 0.1                                             # the stage table carries that weight
    manager = types.SimpleNamespace(get_term_cfg=lambda name: live[name])
    assert adj.reward_readback(types.SimpleNamespace(reward_manager=manager), record)["live"] == asked
    for name, wrong in (("weight", 0.0), ("sigma", 0.5)):
        broken = dict(live)
        broken["ex42_slow_track"] = _Term(term.weight if name != "weight" else wrong,
                                          **{**term.params, **({"sigma": wrong} if name == "sigma" else {})})
        manager = types.SimpleNamespace(get_term_cfg=lambda key, broken=broken: broken[key])
        with pytest.raises(ValueError, match="the live reward manager carries"):
            adj.reward_readback(types.SimpleNamespace(reward_manager=manager), record)
    stale = dict(live)
    stale["ex41_feet_air_time"] = _Term(0.1, name="feet_air_time")                      # the threshold did not reach the env
    manager = types.SimpleNamespace(get_term_cfg=lambda key: stale[key])
    with pytest.raises(ValueError, match="the live reward manager carries"):
        adj.reward_readback(types.SimpleNamespace(reward_manager=manager), record)


def test_constants_that_do_not_make_a_band_are_refused_even_inside_opened_fences(plan, tmp_path):
    row = adj.stage_rewards(plan, "E1")
    limits = open_limits(tmp_path, slow_track_speed_min=(0.05, 0.4), slow_track_speed_max=(0.1, 0.4))
    doc = {"schema": adj.SCHEMA, "stage_id": "E1", "plan_sha256": plan.sha256,
           "segments": {"1": {"decided_at": "t", "reason": "r", "evidence": "e",
                              "rewards": {**row, "slow_track_speed_min": 0.3, "slow_track_speed_max": 0.3}}}}
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="slow_track needs 0 < speed_min < speed_max"):
        adj.start_segment(view(plan), plan, "E1", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=False,
                          limits_path=limits)
