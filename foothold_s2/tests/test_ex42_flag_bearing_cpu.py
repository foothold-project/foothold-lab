"""Known-input checks for the optional, nonjudged first-flag bearing axis."""
from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml

from foothold_s2.commands import mixed_core as mc
from foothold_s2.eval import ex42_flag_turn_first
from foothold_s2.eval.ex42_flag_bearing import bearing_degrees, rotate_flags, score_turn_before_walk


def test_actual_flag_step_turns_toward_90_degree_flag_and_off_is_unchanged():
    # The Isaac CommandTerm cannot import without Kit; assert the real source
    # still calls this exact flag_step on its installed flag_state.
    source = (Path(__file__).resolve().parents[1] / "commands/mixed_command.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "MixedVelocityCommand"
                  for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_update_command")
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name) and node.func.value.id == "mc"
               and node.func.attr == "flag_step" for node in ast.walk(method))

    start = torch.tensor([[10., 20.], [-3., 4.]])
    yaw = torch.tensor([0., math.pi / 2])
    flags = torch.tensor([[[13., 20.], [14., 21.]], [[-3., 7.], [-2., 8.]]])
    frozen = flags.clone()
    rotated = rotate_flags(flags, start, yaw, 90.0)
    torch.testing.assert_close(flags, frozen)  # optional mode does not mutate the old row
    torch.testing.assert_close(rotated[:, 0], torch.tensor([[10., 23.], [-6., 4.]]), atol=1e-5, rtol=0)
    torch.testing.assert_close(torch.linalg.norm(rotated[:, 1] - rotated[:, 0], dim=1),
                               torch.linalg.norm(flags[:, 1] - flags[:, 0], dim=1))
    state = mc.FlagState.new(rotated)
    state.v.fill_(0.8)
    plan = yaml.safe_load((Path(__file__).resolve().parents[1] / "curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    turn = ex42_flag_turn_first.resolve("plan", plan, "E2")
    assert turn == {"rad": 0.5, "scope": "first"}
    cmd = mc.flag_step(state, start, yaw, 0.02,
                       mc.CommandParams(flag_spin_threshold=0.0), turn["rad"], turn["scope"])
    assert torch.equal(cmd[:, :2], torch.zeros(2, 2))
    assert bool((cmd[:, 2] > 0).all())
    # A reversed bearing sign or rotation around world origin fails both
    # the known world target and the first positive yaw command.
    wrong_sign = rotate_flags(flags, start, yaw, -90.0)
    assert not torch.allclose(wrong_sign[:, 0], rotated[:, 0])
    wrong_center = rotate_flags(flags, torch.zeros_like(start), yaw, 90.0)
    assert not torch.allclose(wrong_center[:, 0], rotated[:, 0])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 181., -181.])
def test_bearing_rejects_invalid_degrees(bad):
    with pytest.raises(ValueError, match="first flag bearing"):
        bearing_degrees(bad)
    assert bearing_degrees(None) is None


def test_first_actual_forward_crossing_reads_heading_and_spawn_not_world_origin():
    steps, envs = 4, 64
    start = np.tile([10., 20.], (envs, 1))
    pos = np.zeros((steps, envs, 3))
    pos[:, :, :2] = start
    pos[2:, :, 1] += .05
    vel = np.zeros_like(pos)
    vel[2:, :, 1] = .25
    angle = np.pi / 2
    quat = np.zeros((steps, envs, 4))
    quat[..., 0], quat[..., 3] = np.cos(angle / 2), np.sin(angle / 2)
    trace = dict(root_pos_w=pos, root_vel_w=vel, root_quat_w=quat,
                 alive=np.ones((steps, envs), dtype=bool),
                 flags_w=np.tile([[[10., 23.]]], (envs, 1, 1)), start_pos_xy_w=start)
    result = score_turn_before_walk(trace)
    assert result["passed"] and result["forward_crossings"] == 64
    assert result["bearing_error_median_deg"] == pytest.approx(0.)
    assert result["start_displacement_max_m"] == pytest.approx(.05)
    assert all(row["first_forward_step"] == 2 for row in result["per_env"])
    # Facing away at the crossing must fail; no crossing is not a success.
    wrong = dict(trace, root_quat_w=quat.copy())
    wrong["root_quat_w"][..., 3] *= -1
    assert not score_turn_before_walk(wrong)["passed"]
    stopped = dict(trace, root_vel_w=np.zeros_like(vel))
    assert not score_turn_before_walk(stopped)["passed"]


def test_eval_cli_defaults_do_not_change_receipt_and_on_records_rotation():
    source = (Path(__file__).resolve().parents[1] / "eval/ex42_flag_eval.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(isinstance(node, ast.Constant) and node.value == "--first-flag-bearing-deg"
               for node in ast.walk(tree))
    assert 'if args.first_flag_bearing_deg is not None:' in source
    assert 'receipt["first_flag_bearing_deg"] = args.first_flag_bearing_deg' in source
    assert 'raw_row["first_flag_bearing"] = score_turn_before_walk(trace)' in source
    assert 'rows["root_quat_w"].append(robot.data.root_quat_w' in source
