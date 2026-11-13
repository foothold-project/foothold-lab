"""Known E1 start cells and the heading exception, without Isaac or GPU."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan, _read_yaml
from foothold_s2.rewards.ex42_slow_track import configure_from_plan, slow_track_value
from foothold_s2.scripts.ex42_training_entry import (EX42StageZeroRuntime, load_ex42_stage_zero_source,
                                                     make_ex42_stage_zero_plan_view)


PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def test_approved_slow_start_is_applied_before_env_construction():
    row = next(row for row in EX42Plan.load(PLAN).document["stages"] if row["id"] == "E1")

    class Term:
        def __init__(self, *, func, weight, params):
            self.func, self.weight, self.params = func, weight, params

    env_cfg = SimpleNamespace(rewards=SimpleNamespace())
    receipt = configure_from_plan(env_cfg, row, Term)
    assert receipt == {"weight": .2, "include_heading": True}
    assert env_cfg.rewards.ex42_slow_track.params["include_heading"] is True

    plan = EX42Plan.load(PLAN)
    source, stage = load_ex42_stage_zero_source(plan)
    view = make_ex42_stage_zero_plan_view(source, stage, {"parent_sha256": "a" * 64},
                                           ex42_plan=plan, stage_id="E1")
    assert view.stages[0].low_forward_fraction == .5


@pytest.mark.parametrize("key, duplicate_value", [
    ("low_forward_fraction", "0.4"),
    ("slow_track_heading", "false"),
])
def test_ex42_plan_loader_rejects_duplicate_e1_keys(tmp_path, key, duplicate_value):
    source = PLAN.read_text(encoding="utf-8-sig")
    row = next(row for row in EX42Plan.load(PLAN).document["stages"] if row["id"] == "E1")
    assert row["low_forward_fraction"] == .5
    assert row["slow_track_heading"] is True
    duplicate = source.replace(
        "  slow_track_heading: true\n  command_adjust_limits:",
        f"  slow_track_heading: true\n  {key}: {duplicate_value}\n  command_adjust_limits:",
        1,
    )
    assert duplicate != source
    path = tmp_path / "duplicate-ex42-prep.yaml"
    path.write_text(duplicate, encoding="utf-8")
    with pytest.raises(ValueError, match=f"duplicate YAML key.*{key}"):
        _read_yaml(path)


def test_heading_exception_keeps_flag_and_free_turn_out():
    vel = torch.tensor([[.2, 0], [.2, 0], [.2, 0]])
    cmd = vel.clone()
    wz = torch.tensor([1., 1., 1.])
    value = slow_track_value(vel, cmd, wz, speed_min=.1, speed_max=.3, sigma=.5,
                             excluded=torch.tensor([False, True, False]),
                             turn_exempt=torch.tensor([True, True, False]))
    assert value.tolist() == [1., 0., 0.]
    old = slow_track_value(vel[:1], cmd[:1], wz[:1], speed_min=.1, speed_max=.3, sigma=.5,
                           excluded=torch.tensor([True]))
    assert old.item() == 0.


def test_start_rejects_missing_approval_cell():
    class Term:
        def __init__(self, *, func, weight, params):
            self.weight, self.params = weight, params

    env_cfg = SimpleNamespace(rewards=SimpleNamespace())
    with pytest.raises(ValueError, match="approved weight"):
        configure_from_plan(env_cfg, {"live_monitor": {"enabled": True}, "slow_track_heading": True}, Term)


def test_post_step_uses_raw_timeout_when_wrapper_extras_omit_it():
    runtime = EX42StageZeroRuntime(
        stage_zero_plan=SimpleNamespace(stages=[SimpleNamespace(id="T0_prime")]),
        plan_sha256="a" * 64, approval_sha256="b" * 64,
        parent_sha256="c" * 64, push_vmax_mps=2.)
    runtime.env = SimpleNamespace(num_envs=1, reset_time_outs=torch.tensor([True]),
                                  scene={"robot": SimpleNamespace(data=SimpleNamespace(
                                      root_lin_vel_b=torch.zeros(1, 3)))})
    runtime._step_pending = True
    runtime._live_pre = tuple(torch.zeros(1, 3) if i == 0 else torch.zeros(1) if i == 7
                              else torch.zeros(1, dtype=torch.bool) for i in range(9))
    calls = []
    runtime.live_metrics = SimpleNamespace(add=lambda *args, **kwargs: calls.append(kwargs))
    runtime.record_post_step(torch.tensor([True]))
    assert calls[0]["time_out"].tolist() == [True]
    assert calls[0]["pre_speed"].tolist() == [0.]
    assert calls[0]["reset"].tolist() == [False]


def test_live_start_reads_pre_step_stillness_and_reset_before_physics():
    class Scene:
        terrain = SimpleNamespace(terrain_types=torch.tensor([0]))
        robot = SimpleNamespace(data=SimpleNamespace(root_lin_vel_b=torch.tensor([[.03, .0, .0]])))
        def __getitem__(self, name):
            assert name == "robot"
            return self.robot

    term = SimpleNamespace(slot_current=torch.tensor([0]), heading=torch.tensor([False]),
                           is_flag_env=torch.tensor([False]))
    runtime = EX42StageZeroRuntime(
        stage_zero_plan=SimpleNamespace(stages=[SimpleNamespace(id="T0_prime")]),
        plan_sha256="a" * 64, approval_sha256="b" * 64,
        parent_sha256="c" * 64, push_vmax_mps=2.)
    runtime.env = SimpleNamespace(num_envs=1, scene=Scene(), episode_length_buf=torch.tensor([0]),
                                  reset_time_outs=torch.tensor([False]),
                                  command_manager=SimpleNamespace(get_term=lambda _: term))
    runtime.runner = SimpleNamespace(pstate=SimpleNamespace(use_gt=torch.tensor([True]),
                                                              map_off=torch.tensor([False])),
                                     _consumed_command=lambda _: torch.tensor([[.12, .0, .0]]))
    runtime._live_sparse_by_col = torch.tensor([False])
    runtime.iteration = 1
    calls = []
    runtime.live_metrics = SimpleNamespace(add=lambda *args, **kwargs: calls.append((args, kwargs)))
    runtime.record_pre_step()
    runtime.env.scene.robot.data.root_lin_vel_b[0, 0] = .08
    runtime.env.episode_length_buf[0] = 1
    runtime.record_post_step(torch.tensor([False]))
    args, kwargs = calls[0]
    assert kwargs["pre_speed"].tolist() == pytest.approx([.03])
    assert kwargs["reset"].tolist() == [True]
    assert args[1][0, 0].item() == pytest.approx(.08)
