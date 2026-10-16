"""ASTRA 17v P1 known answers and counterexamples, CPU only."""
from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace

import torch

from s2_env_adapter_17v import AdapterFault, expected_world_xy, training_map, yaw_from_quat_wxyz
from s2_packet_17v import AtomicPacket, raw_sha
from s2_ppo_17v import PPOConfig
from s2_runner_17v import S2Runner, S2RunnerError, timeout_corrected_reward
from s2_terrain_overlay_17v import EncounterLog, TerrainOverlayError


def check(label, good):
    print(("PASS" if good else "FAIL") + " " + label, flush=True)
    if not good:
        raise AssertionError(label)


def cfg():
    return SimpleNamespace(ray_alignment="yaw", offset=SimpleNamespace(pos=(0., 0., 20.)),
        pattern_cfg=SimpleNamespace(ordering="xy", size=(1.6, 1.0), resolution=.1, direction=(0., 0., -1.)))


def packet(step: int, generation: int, height: float, episodes):
    pos = torch.tensor([[0., 0., .5], [1., 0., .5]])
    quat = torch.tensor([[1., 0., 0., 0.], [1., 0., 0., 0.]])
    xy = expected_world_xy(pos, torch.zeros(2))
    hits = torch.cat((xy, torch.full((2, 187, 1), height)), dim=-1)
    sensor = SimpleNamespace(cfg=cfg(), data=SimpleNamespace(pos_w=pos, ray_hits_w=hits))
    digest = raw_sha(pos, hits)
    receipt = {"generation": generation, "step": step, "raw_sha256": digest,
               "generation_by_env":[generation,generation],
               "sensor_timestamp_by_env":[float(step),float(step)],
               "hook_source_sha256":"fixture-hook"}
    obs = {"policy": torch.full((2, 2), float(step)), "single_obs": torch.ones(2, 1),
           "critic": torch.zeros(2, 2)}
    return AtomicPacket(obs, sensor, pos, quat, torch.tensor(episodes), step, step, generation,
                        digest, f"packet-{step}", receipt, (0.,0.,0.))


def event_fields(**changes):
    data = {"kind": "gap", "env_id": 0, "episode_id": 3, "terrain_instance": "tile-2",
            "terrain_seed": 11, "difficulty": 2, "obstacle_id": "gap-1", "command_bin": "forward",
            "update": 10, "crossed_approach_line": False, "crossed_finish_line": False,
            "obstacle_contact": False, "after_obstacle": False}
    data.update(changes)
    return data


def test_all():
    torch.set_num_threads(2)
    reward, value = torch.tensor([1., 1., 1.]), torch.tensor([2., 2., 2.])
    done, timeout = torch.tensor([True, True, False]), torch.tensor([True, False, False])
    corrected = timeout_corrected_reward(reward, done, timeout, value, .99)
    returns = corrected + .99*value*(~done)
    check("timeout_parent_2_98_terminal_1_nonterminal_2_98", torch.allclose(returns, torch.tensor([2.98, 1., 2.98])))
    try:
        timeout_corrected_reward(reward, done, torch.tensor([False, False, True]), value, .99)
    except S2RunnerError:
        check("timeout_not_done_rejected", True)
    else:
        check("timeout_not_done_rejected", False)
    p0 = packet(0, 10, 0., [0, 0])
    p1 = packet(1, 11, .2, [1, 0])
    p0.validate(previous=None, previous_done=None)
    p1.validate(previous=p0, previous_done=torch.tensor([True, False]))
    mapped, faults = training_map(p1.sensor, mode="B", yaw_w=p1.validate(previous=p0,
                                   previous_done=torch.tensor([True, False])), geometry_tolerance_m=.002)
    check("same_xy_new_height_reset_packet", faults.total == 0 and abs(float(mapped[0, 0])+.2) < 1e-6)
    stale = packet(1, 11, 0., [1, 0])
    class Env:
        def capture_packet_after_sensor_update(self): return stale
        def read_sensor_source_receipt(self): return p1.source_receipt
    runner = S2Runner.__new__(S2Runner)
    runner.env = Env(); runner.mode = "B"; runner.geometry_tolerance_m = .002
    runner._last_packet = p0; runner._last_done = torch.tensor([True, False])
    runner.algo = SimpleNamespace(config=SimpleNamespace(num_envs=2), policy=SimpleNamespace(get_critic_obs=lambda obs: obs["critic"]))
    from s2_map_obs import RunValidityGate
    try:
        runner._frame(stale.obs, RunValidityGate())
    except S2RunnerError as exc:
        check("old_raw_new_numbers_rejected_by_independent_source", "source receipt" in str(exc))
    else:
        check("old_raw_new_numbers_rejected_by_independent_source", False)
    moved = packet(2, 12, .2, [1, 0])
    moved.sensor.data.pos_w[0, 0] += .1
    digest = raw_sha(moved.sensor.data.pos_w, moved.sensor.data.ray_hits_w)
    moved = replace(moved, sensor_raw_sha256=digest,
                    source_receipt={**moved.source_receipt,"raw_sha256": digest})
    try:
        yaw = moved.validate(previous=p1, previous_done=torch.tensor([False, False]))
        training_map(moved.sensor, mode="B", yaw_w=yaw, geometry_tolerance_m=.002)
    except AdapterFault:
        check("same_yaw_movement_old_hit_rejected", True)
    else:
        check("same_yaw_movement_old_hit_rejected", False)
    mixed = packet(2, 12, .3, [1, 0])
    mixed.validate(previous=p1, previous_done=torch.tensor([False, False]))
    check("partial_env_reset_episode_contract", True)
    for bad in (torch.tensor([math.nan, 0.]), torch.tensor([math.inf, 0.])):
        try:
            expected_world_xy(torch.zeros(2, 3), bad)
        except AdapterFault:
            check("nonfinite_yaw_rejected", True)
        else:
            check("nonfinite_yaw_rejected", False)
    for bad_quat in (torch.tensor([[math.nan, 0., 0., 0.]]), torch.tensor([[2., 0., 0., 0.]])):
        try:
            yaw_from_quat_wxyz(bad_quat)
        except AdapterFault:
            check("nonfinite_or_unnormalized_quaternion_rejected", True)
        else:
            check("nonfinite_or_unnormalized_quaternion_rejected", False)
    encounters = EncounterLog()
    encounters.record(event="assigned", **event_fields())
    encounters.record(event="approach", **event_fields(crossed_approach_line=True))
    encounters.record(event="pass", **event_fields(crossed_finish_line=True))
    for label, ev in (("duplicate_pass", "pass"), ("conflicting_fall", "fall")):
        try:
            encounters.record(event=ev, **event_fields(crossed_finish_line=True))
        except TerrainOverlayError:
            check(label+"_rejected", True)
        else:
            check(label+"_rejected", False)
    encounters.record(event="post_pass_fall", **event_fields(after_obstacle=True))
    counts = encounters.report()
    check("post_pass_fall_distinct", counts["gap_pass"] == 1 and counts["gap_fall"] == 0 and counts["gap_post_pass_fall"] == 1)
    try:
        PPOConfig(3, 2, 2, 4, .2, .99, .95, 1., .01, 1., .01, "adaptive", True)
    except ValueError as exc:
        check("minibatch_divisibility", "divide evenly" in str(exc))
    else:
        check("minibatch_divisibility", False)
    held = S2Runner.__new__(S2Runner)
    held._held_reason = "synthetic invalid collection"; held.mode = "A"
    held.algo = SimpleNamespace(ctl=SimpleNamespace(next_update_index=0))
    check("invalid_collect_persistent_hold", held.update_once()["status"] == "held_collect" and held.update_once()["status"] == "held_collect")
    try:
        held.load("unused")
    except S2RunnerError as exc:
        check("environment_resume_unsupported", "unsupported" in str(exc))
    else:
        check("environment_resume_unsupported", False)


if __name__ == "__main__":
    test_all()
