"""Actual CPU calls through the EX-39 command consumers; no Kit or GPU."""

from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.eval.map_mode_cells import summarize as eval_summarize
from foothold_s2.eval.training_trace_bridge import TrainingTraceBridge
from foothold_s2.rewards.basic_gait_bundle import four_foot_contact_at_stop, hip_pos_penalty_l1
from foothold_s2.rewards.mgdp_core import stand_still_penalty
from foothold_s2.runners.action_stats import ActionStats
from foothold_s2.runners.contracts import command_sample_bad
from foothold_s2.runners.kl_probe import command_branch, summarize as kl_summarize
from foothold_s2.runners.map_switch import MapSwitchRecorder


def commands_and_heading():
    # Thirteen sampled slots, plus the two consumed heading cases at their limits.
    rows = [
        [0.5, 0, 0], [0.5, 0, 0.3], [0.5, 0, -0.3], [0, 0, 1.5],
        [0, 0, -1.5], [0, 0, 0], [-1.0, 0, 0], [0, 0.6, 0],
        [0, -0.6, 0], [0.5, 0.4, 0], [0.5, -0.4, 0],
        [-0.5, 0.4, 0], [-0.5, -0.4, 0], [0.5, 0, 2.0], [0, 0, 0],
    ]
    heading = torch.tensor([False] * 13 + [True, True])
    return torch.tensor(rows, dtype=torch.float32), heading


def test_contract_new_task_exposure_and_kl_consume_every_ex39_case():
    cmd, heading = commands_and_heading()
    assert not command_sample_bad("basic_gait_ex39", cmd, heading).any()
    assert command_sample_bad("basic_gait_ex39", torch.tensor([[0, 0, 2.1]]), torch.tensor([True])).item()
    params = SimpleNamespace(basic_mode=True)
    marks = mc.new_task_mask(cmd, params)
    assert marks.tolist() == [False, True, True, False, False, True,
                              True, True, True, True, True, True, True, True, True]
    record = mc.ExposureLog()
    record.add(torch.zeros(len(cmd), dtype=torch.long), cmd, 0.02)
    exposure = record.snapshot()
    assert sum(exposure["direction_ratio"].values()) == pytest.approx(1.0)
    assert exposure["direction_ratio"]["back"] > 0
    branch = command_branch(cmd)
    assert branch[7:13].tolist() == [0] * 6  # Side and diagonal are locomotion.
    assert branch[3:5].tolist() == [1, 1]
    assert branch[5].item() == 2
    assert kl_summarize(torch.ones(len(cmd)), branch)["all"]["n"] == len(cmd)


def test_action_map_trace_and_eval_consumers_accept_ex39_commands():
    cmd, _ = commands_and_heading()
    n = len(cmd)
    actions = ActionStats(17, n)
    actions.add(torch.zeros(n, 12), torch.zeros(n, dtype=torch.bool))
    assert actions.summary()["raw_abs_max"] == 0
    maps = MapSwitchRecorder(n, "cpu")
    maps.add_step(torch.zeros(n, dtype=torch.bool), torch.ones(n),
                  torch.zeros(n, dtype=torch.bool), levels=torch.zeros(n),
                  track_lin=torch.ones(n), track_ang=torch.ones(n),
                  time_outs=torch.zeros(n, dtype=torch.bool), use_gt=torch.ones(n, dtype=torch.bool))
    assert maps.summary()["on"]["env_steps"] == n

    data = SimpleNamespace(root_pos_w=torch.zeros(n, 3), root_quat_w=torch.zeros(n, 4),
                           body_pos_w=torch.zeros(n, 4, 3), body_lin_vel_w=torch.zeros(n, 4, 3),
                           joint_pos=torch.zeros(n, 12), joint_vel=torch.zeros(n, 12))
    contact = SimpleNamespace(data=SimpleNamespace(net_forces_w=torch.zeros(n, 4, 3)))
    camera = SimpleNamespace(data=SimpleNamespace(output={"distance_to_image_plane": torch.zeros(n, 2, 2, 1)}))
    env = SimpleNamespace(scene=SimpleNamespace(sensors={"depth_cam": camera},
                                                terrain=SimpleNamespace(terrain_types=torch.zeros(n),
                                                                        terrain_levels=torch.zeros(n))),
                          command_manager=SimpleNamespace(get_command=lambda _: cmd))
    trace = TrainingTraceBridge.__new__(TrainingTraceBridge)
    trace.active, trace.robot, trace.contact, trace.feet, trace.sensor_feet = True, SimpleNamespace(data=data), contact, [0, 1, 2, 3], [0, 1, 2, 3]
    trace.env, trace.episode = env, torch.zeros(n, dtype=torch.long)
    trace.pre_step(torch.zeros(n, 12))
    cmd.zero_()
    assert trace.pending["command"][6, 0] == -1.0
    assert trace.pending["command"][7, 1] == 0.6

    for row in trace.pending["command"].numpy():
        result = eval_summarize(row, [{"env": 0, "kind": "flat", "level": 0}],
                                np.zeros((2, 1)), np.zeros((2, 1)), np.zeros((2, 1)),
                                np.ones((2, 1), dtype=bool), np.array([True]), 0.02)
        assert result["command"] == row.tolist()


def test_ex39_stop_contact_uses_current_command_not_old_six_group():
    cmd, _ = commands_and_heading()
    n = len(cmd)
    force = torch.zeros(n, 4, 3)
    force[:, :, 2] = 2
    term = SimpleNamespace(slot_current=torch.arange(n))
    env = SimpleNamespace(command_manager=SimpleNamespace(get_command=lambda _: cmd,
                                                            get_term=lambda _: term),
                          scene=SimpleNamespace(sensors={"contact": SimpleNamespace(
                              data=SimpleNamespace(net_forces_w=force))}))
    sensor = SimpleNamespace(name="contact", body_ids=[0, 1, 2, 3])
    reward = four_foot_contact_at_stop(env, "base_velocity", sensor)
    assert reward[5].item() == 1.0
    assert reward[6:14].sum().item() == 0.0
    assert stand_still_penalty(torch.ones(n, 2), cmd)[5].item() == 2.0
    assert stand_still_penalty(torch.ones(n, 2), cmd)[3].item() == 0.0
    joint = SimpleNamespace(data=SimpleNamespace(joint_pos=torch.ones(n, 2),
                                                 default_joint_pos=torch.zeros(n, 2)))
    # This E1-form hip term uses the same coefficient at stand and movement.
    env.scene = {"robot": joint}
    assert torch.equal(hip_pos_penalty_l1(env, "base_velocity", SimpleNamespace(name="robot", joint_ids=[0, 1]),
                                          stand_still_scale=1.0, command_threshold=0.1), torch.full((n,), 2.0))
