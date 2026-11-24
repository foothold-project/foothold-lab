"""Known timelines for the opt-in map-outage path, without Isaac or GPU."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import pytest
import torch

from foothold_s2.models.start_perception import PerceptionCfg, StartPerception
from foothold_s2.runners.ex42_map_transition import Config, MapTransition, read_config
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.eval.ex42_map_transition_compare import compare
from foothold_s2.eval.adapters import S2Policy
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


def test_missing_key_is_off_and_config_rejects_bad_ranges():
    assert read_config({}) is None
    raw = {"wait_s": [0.04, 0.04], "off_s": [0.1, 0.1],
           "restore_depth_ticks": [2, 2], "seed": 9}
    assert read_config({"EX42_MAP_TRANSITION_JSON": json.dumps(raw)}) == Config(
        (0.04, 0.04), (0.1, 0.1), (2, 2), 9)
    raw["off_s"] = [0.02, 3.0]
    with pytest.raises(ValueError):
        read_config({"EX42_MAP_TRANSITION_JSON": json.dumps(raw)})


def test_known_outage_and_delayed_depth_restore_keep_untouched_rows():
    cfg = Config((0.04, 0.04), (0.1, 0.1), (2, 2), 42)
    trans = MapTransition(cfg, 3, "cpu", dt=0.02, depth_tick=2)
    trans.reset(torch.ones(3, dtype=torch.bool), torch.tensor([False, True, False]),
                torch.tensor([True, True, False]))
    off, hold = [], []
    for step in range(10):
        o, h = trans.step(torch.tensor([step % 2 == 0] * 3))
        off.append(o.tolist())
        hold.append(h.tolist())
    assert [r[0] for r in off[:8]] == [False, True, True, True, True, True, False, False]
    assert [r[0] for r in hold[:10]] == [False, False, False, False, False, False,
                                        True, False, True, False]
    assert all(r[1] and not r[2] for r in off)
    assert all(not r[1] and not r[2] for r in hold)
    assert trans.take_counts() == {"off_starts": 1, "on_restores": 1, "held_depth_ticks": 2}


def test_restore_keeps_gru_and_history_and_replay_tick_agrees():
    net = StartPerception(PerceptionCfg(depth_tick=2))
    state = net.init_state(1, "cpu")
    state.h_terr.fill_(3.0)
    state.h_prop.fill_(4.0)
    state.hist.fill_(7.0)
    state.steps_since_reset.fill_(2)
    state.frames.fill_(5.0)
    old_terr, old_prop, old_hist = state.h_terr.clone(), state.h_prop.clone(), state.hist.clone()
    inp = net.ingest(state, torch.ones(1, 45), torch.ones(1, 60, 60) * 9,
                     depth_hold=torch.tensor([True]))
    assert inp["tick"].tolist() == [False]
    assert torch.equal(inp["depth2"], torch.ones_like(inp["depth2"]) * 5)
    assert torch.equal(state.h_terr, old_terr) and torch.equal(state.h_prop, old_prop)
    assert not torch.equal(state.hist, old_hist)  # proprioceptive history keeps moving
    with pytest.raises(ValueError):
        net.ingest(state, torch.ones(1, 45), torch.ones(1, 60, 60), depth_hold=torch.ones(2, dtype=torch.bool))


def test_real_policy_adapter_changes_map_attention_without_resetting_hidden_state():
    env = FakeStartEnv(num_envs=2)
    runner = StartRunner(env, train_cfg(2, perception={"microbatch_envs": 2, "map_input": "reconstruction"}), device="cpu")
    policy = S2Policy(runner, 2, z_mode="mean", act_mode="mean", map_mode="eval_pred")
    policy.map_transition = MapTransition(Config((.02, .02), (.1, .1), (1, 1), 42), 2, "cpu", .02,
                                          runner.perception.cfg.depth_tick)
    policy.map_transition.reset(torch.ones(2, dtype=torch.bool), policy.base_map_off)
    with torch.inference_mode():
        action = policy(env.get_observations())
        hidden = policy.pstate.h_prop.clone()
        assert policy.pstate.map_off.tolist() == [True, True]
        assert action.shape == (2, 12) and torch.isfinite(action).all()
        for _ in range(5):
            policy(env.get_observations())
        assert policy.pstate.map_off.tolist() == [False, False]
        assert policy.pstate.steps_since_reset.tolist() == [6, 6]
        assert torch.isfinite(policy.pstate.h_prop).all() and torch.isfinite(hidden).all()


def test_transition_rng_receipt_and_resume_guard():
    cfg = Config((0.04, 0.06), (0.1, 0.2), (0, 2), 42)
    a = MapTransition(cfg, 2, "cpu", 0.02, 2)
    a.reset(torch.ones(2, dtype=torch.bool), torch.zeros(2, dtype=torch.bool))
    saved = a.state_dict()
    b = MapTransition(cfg, 2, "cpu", 0.02, 2)
    b.load_state_dict(saved)
    assert torch.equal(a.gen.get_state(), b.gen.get_state())
    runner = StartRunner.__new__(StartRunner)
    runner.map_transition = b
    runner.load_map_transition_state(saved)
    runner.map_transition = None
    with pytest.raises(ValueError):
        runner.load_map_transition_state(saved)
    with pytest.raises(ValueError):
        b.load_state_dict({"config": {**cfg.receipt(), "seed": 43}, "generator_state": saved["generator_state"]})


def test_reset_after_outage_returns_to_the_episode_baseline():
    runner = StartRunner.__new__(StartRunner)
    runner.device = "cpu"
    runner.p_map_off = 0.0
    runner.map_transition = object()
    runner.map_switch_gen = None
    assert torch.equal(runner._next_reset_map_off(2, torch.tensor([True, False])), torch.zeros(2, dtype=torch.bool))
    runner.map_transition = None
    assert runner._next_reset_map_off(2, torch.tensor([True, False])) is None


def _write_evidence(folder: Path, *, transition: bool, bad_spawn: bool = False):
    folder.mkdir(exist_ok=True)
    status = "on" if transition else "baseline"
    doc = {"run_identity": {"checkpoint_sha256": "a" * 64, "eval_seed": 42},
           "terrain_tiles": [{"kind": "flat", "level": 0}] * 2,
           "map_transition_evidence": {"schema": "ex42-map-transition-evidence/1",
                                       "config": {"wait_s": [.04, .04], "off_s": [.1, .1],
                                                  "restore_depth_ticks": [1, 1], "seed": 42} if transition else None},
           "modes": {"eval_pred": {"fwd1.0": {"map_transition": {
               "state": status, "counts": {"off_starts": 1 if transition else 0,
                                            "on_restores": 1 if transition else 0,
                                            "held_depth_ticks": 1 if transition else 0}}}}}}
    (folder / "map_modes.json").write_text(json.dumps(doc), encoding="utf-8")
    alive = np.ones((5, 2), dtype=bool)
    fall = np.zeros_like(alive)
    if transition:
        fall[-1, 0] = True
        alive[-1, 0] = False
    np.savez(folder / "env_arrays_eval_pred_fwd1.0.npz", alive=alive,
             transition_tilt_rad=np.full((5, 2), .2 if transition else .1),
             transition_foot_contact=np.ones((5, 2, 4), dtype=bool),
             transition_map_off=np.full((5, 2), transition),
             transition_depth_hold=np.full((5, 2), transition),
             transition_fall=fall, transition_timeout=np.zeros_like(alive),
             terrain_col=np.zeros(2, dtype=int), terrain_level=np.zeros(2, dtype=int),
             start_xy=np.array([[1., 1.], [2., 2. if not bad_spawn else 3.]]),
             dt=np.array(.02), assignment_sha256=np.array("tile-sha"))


def test_pair_comparison_uses_raw_tilt_footing_and_real_fall_reason(tmp_path: Path):
    baseline, transition = tmp_path / "baseline", tmp_path / "transition"
    _write_evidence(baseline, transition=False)
    _write_evidence(transition, transition=True)
    result = compare(baseline, transition)
    assert result["delta_transition_minus_baseline"]["tilt_mean_rad"] == pytest.approx(.1)
    assert result["delta_transition_minus_baseline"]["fall_envs"] == 1
    assert result["transition"]["timeout_envs"] == 0
    assert result["transition_counts"]["off_starts"] == 1


def test_pair_comparison_refuses_different_spawn_or_no_outage(tmp_path: Path):
    baseline, transition = tmp_path / "baseline", tmp_path / "transition"
    _write_evidence(baseline, transition=False)
    _write_evidence(transition, transition=True, bad_spawn=True)
    with pytest.raises(ValueError, match="initial condition"):
        compare(baseline, transition)
    _write_evidence(transition, transition=True)
    path = transition / "map_modes.json"
    doc = json.loads(path.read_text())
    doc["modes"]["eval_pred"]["fwd1.0"]["map_transition"]["counts"]["off_starts"] = 0
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="no completed outage"):
        compare(baseline, transition)
