"""Known-answer CPU checks for EX-42 boundary rule ordering and source identity."""
import json

import numpy as np

import pytest

from foothold_s2.tools import ex42_boundary_autojudge as judge


def profile(side=0.09, lin_std=0.5, overlay=0.25):
    return {"commands": {"shares": {"forward": round(0.37 - 2 * side, 6),
                                    "side_left": side, "side_right": side, "other": 0.63},
                         "ranges": {"side_vy_abs": [0.1, 0.8], "walk_vx": [0.3, 1.2]},
                         "turn_overlay": {"fraction": overlay, "wz_abs": [0.2, 0.6]}},
            "rewards": {**judge.DEFAULT_REWARDS, "track_lin_vel_std": lin_std}}


def test_two_declines_large_drop_and_repeat_width_are_separate_flags():
    earlier = {"S_side_progress": 0.9, "H_zero_yaw_error": 0.1}
    previous = {"S_side_progress": 0.85, "H_zero_yaw_error": 0.12}
    current = {"S_side_progress": 0.77, "H_zero_yaw_error": 0.18}
    result = judge.alarms(current, previous, earlier, {"S_side_progress": 0.09},
                          {"S_side_progress": 0.03})
    assert {row["metric"] for row in result["two_consecutive_declines"]} == set(current)
    assert {row["metric"] for row in result["one_boundary_large_declines"]} == set(current)
    assert result["repeat_width_spikes"] == [{"metric": "S_side_progress",
                                               "previous": 0.03, "current": 0.09}]
    assert judge.alarms(current, previous, earlier)["repeat_width_spikes"] is None


def test_prior_side_share_change_and_worse_side_progress_is_a_side_effect():
    result = judge.side_effects({"S_side_progress": 0.7}, {"S_side_progress": 0.8},
                                profile(side=0.105), profile(side=0.09))
    assert result == [{"prior_change": "side_share_up", "metric": "S_side_progress", "delta_bad": 0.1}]
    assert judge.side_effects({"S_side_progress": 0.9}, {"S_side_progress": 0.8},
                              profile(side=0.105), profile(side=0.09)) == []


def test_command_share_rule_keeps_missing_three_seed_safety_visible():
    baseline = {"T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    now = {"R_maintenance": "PASS", "S_side_progress": 0.7, "V_fast_side_3seed": None,
           "H_zero_yaw_error": 0.1, "T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    result = judge.propose(250, now, baseline, None, profile(), None)["command"]
    assert result["state"] == "PARTIAL" and result["share_rule"] == "S1"
    assert result["widen_rule"] is None and result["missing"] == ["V_3seed"]
    assert result["proposed_commands"]["shares"] == {
        "forward": 0.16, "side_left": 0.105, "side_right": 0.105, "other": 0.63}


def test_from_boundary_500_the_forward_share_is_not_reduced():
    """Rule table amendment of 2026-11-13: S1 moves the shares at boundary 250 only; at 500 the low side progress is
    recorded (S1b) and the proposed profile keeps the shares it runs with."""
    baseline = {"T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    now = {"R_maintenance": "PASS", "S_side_progress": 0.7, "V_fast_side_3seed": None,
           "H_zero_yaw_error": 0.1, "T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    running = profile()
    result = judge.propose(500, now, baseline, None, running, None)
    assert result["command"]["share_rule"] == "S1b"
    assert result["command"]["proposed_commands"]["shares"] == running["commands"]["shares"]
    assert result["command_rule_amendment_commit"] == judge.COMMAND_RULE_AMENDMENT
    assert judge.propose(250, now, baseline, None, profile(), None)["command"]["proposed_commands"]["shares"][
        "forward"] == 0.16


def test_safety_overrides_widening_and_reverts_prior_overlay():
    baseline = {"T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    now = {"R_maintenance": "PASS", "S_side_progress": 0.9, "V_fast_side_3seed": 190,
           "H_zero_yaw_error": 0.1, "T/L5/ref_walk0.5_wz0.5/wz": 0.9}
    result = judge.propose(500, now, baseline, None, profile(overlay=0.3),
                           profile(overlay=0.25))["command"]
    assert result["safety_rules"] == ["A2"] and result["widen_rule"] is None
    assert result["proposed_commands"]["turn_overlay"]["fraction"] == 0.25


def test_reward_reversion_takes_priority_even_if_terrain_curve_is_missing():
    now = {"R_maintenance": "PASS", "F1_slow_forward": 0.1, "P1_slow_spin": 0.7,
           "n_fwd_vx": 0.8, "A_min_survival": 64, "Z_terrain_level": None}
    prev = {**now, "n_fwd_vx": 0.9}
    result = judge.propose(1000, now, {}, prev, profile(lin_std=0.4),
                           profile(lin_std=0.5))["reward"]
    assert result["rule"] == "X1" and result["values"]["track_lin_vel_std"] == 0.5
    now["n_fwd_vx"] = 0.9
    result = judge.propose(1000, now, {}, prev, profile(lin_std=0.4),
                           profile(lin_std=0.5))["reward"]
    assert result["state"] == "HOLD_MISSING_SAFETY" and result["values"] is None


def test_first_reward_step_is_draft_and_needs_live_readback():
    now = {"R_maintenance": "PASS", "F1_slow_forward": 0.05,
           "P1_slow_spin": 0.7, "Z_terrain_level": None}
    result = judge.propose(750, now, {}, None, profile(), profile())["reward"]
    assert result["rule"] == "L1" and result["values"]["track_lin_vel_std"] == 0.4
    assert result["rule_status"] == "draft" and result["requires_live_readback"]
    assert judge.propose(750, {**now, "R_maintenance": "HOLD"}, {}, None,
                         profile(), profile())["reward"]["rule"] == "R0"


def test_brief_recounts_raw_and_rejects_wrong_checkpoint(tmp_path):
    g1b = tmp_path / "hipan_g1b_L0"
    g1 = tmp_path / "hipan_g1_L0"
    g1b.mkdir(); g1.mkdir()
    raw = {"eval_seed": 42, "checkpoint_sha256": "a" * 64, "checkpoint_iter": 250,
           "envs": 64, "commands": {"fwd0.1": [0.1, 0, 0]},
           "modes": {"eval_gt": {"fwd0.1": {"env_count": 64, "alive_envs_at_end": 64,
                       "per_env": [{"vx_abs_error_mean_alive_mps": 0.05,
                                    "vy_abs_error_mean_alive_mps": 0.02,
                                    "wz_abs_error_mean_alive_radps": 0.01}] * 64}}}}
    for folder in (g1b, g1):
        (folder / "map_modes.json").write_text(json.dumps(raw), encoding="utf-8")
    recounted = judge._source(g1b / "map_modes.json", "a" * 64, iteration=250)
    brief = {"format": "foothold-ex42-boundary-brief/1", "label": "m250", "at": 250,
             "g1b": {key: recounted[key] for key in ("source", "rows")}, "g1": "없음"}
    path = tmp_path / "m250_L0.json"
    path.write_text(json.dumps(brief), encoding="utf-8")
    result = judge.load_level(path, iteration=250, checkpoint_sha="a" * 64)
    assert result["blocks"]["g1"]["source"]["provenance"] == "same_checkpoint_sibling"
    raw["checkpoint_sha256"] = "b" * 64
    (g1 / "map_modes.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint"):
        judge.load_level(path, iteration=250, checkpoint_sha="a" * 64)


def test_width_receipt_checks_its_raw_source_hashes(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    body = {"format": "foothold-ex42-boundary-widths/1", "iteration": 250,
            "checkpoint_sha256": "a" * 64, "widths": {"S_side_progress": 0.07},
            "sources": [{"path": str(tmp_path / name), "sha256": judge.sha(tmp_path / name)}
                        for name in ("a", "b")]}
    (tmp_path / "m250.json").write_text(json.dumps(body), encoding="utf-8")
    assert judge._widths(tmp_path, 250, "a" * 64)[0] == {"S_side_progress": 0.07}
    (tmp_path / "b").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA"):
        judge._widths(tmp_path, 250, "a" * 64)


def test_reward_profile_uses_two_live_ranks_and_rejects_mismatch(tmp_path):
    receipt = {"format": "ex42-segment-commands/1", "stage_id": "E1",
               "boundary_index": 3, "plan_sha256": "a" * 64,
               "commands": profile()["commands"], "rewards": {"values": None}}
    for rank in (0, 1):
        path = tmp_path / f"segment_rewards_b3_rank{rank}.json"
        path.write_text(json.dumps({"format": "ex42-segment-rewards/1", "stage_id": "E1",
                                    "boundary_index": 3, "plan_sha256": "a" * 64,
                                    "live": judge.DEFAULT_REWARDS}), encoding="utf-8")
    result, sources = judge._profile(receipt, tmp_path)
    assert result["rewards"] == judge.DEFAULT_REWARDS and len(sources) == 2
    assert all(judge.sha(tmp_path / f"segment_rewards_b3_rank{i}.json") == row["sha256"]
               for i, row in enumerate(sources))
    wrong = json.loads((tmp_path / "segment_rewards_b3_rank1.json").read_text())
    wrong["live"]["track_lin_vel_std"] = 0.4
    (tmp_path / "segment_rewards_b3_rank1.json").write_text(json.dumps(wrong), encoding="utf-8")
    with pytest.raises(ValueError, match="ranks or requested"):
        judge._profile(receipt, tmp_path)


def test_s1_threshold_is_085_not_080():
    base = {"T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    now = {"R_maintenance": "PASS", "S_side_progress": 0.82,
           "V_fast_side_3seed": 190, "H_zero_yaw_error": 0.1,
           "T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    assert judge.propose(250, now, base, None, profile(), None)["command"]["share_rule"] == "S1"
    now["S_side_progress"] = 0.85
    assert judge.propose(250, now, base, None, profile(), None)["command"]["share_rule"] == "S2"
    assert judge.propose(500, now, base, None, profile(), None)["command"]["share_rule"] == "S2"


def test_a1_threshold_is_171_not_161():
    base = {"T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    now = {"R_maintenance": "PASS", "S_side_progress": 0.9,
           "V_fast_side_3seed": 165, "H_zero_yaw_error": 0.1,
           "T/L5/ref_walk0.5_wz0.5/wz": 1.0}
    assert "A1" in judge.propose(500, now, base, None, profile(), None)["command"]["safety_rules"]
    now["V_fast_side_3seed"] = 171
    assert "A1" not in judge.propose(500, now, base, None, profile(), None)["command"]["safety_rules"]


def test_command_adjustment_stops_after_m500():
    now = {"R_maintenance": "PASS", "S_side_progress": 0.5,
           "V_fast_side_3seed": 150, "H_zero_yaw_error": 0.2}
    result = judge.propose(750, now, {}, None, profile(), profile())["command"]
    assert result["state"] == "FROZEN"
    assert "proposed_commands" not in result


def test_l1_floor_is_03_not_02():
    now = {"R_maintenance": "PASS", "F1_slow_forward": 0.1,
           "P1_slow_spin": 1.0, "Z_terrain_level": 0.0}
    result = judge.propose(750, now, {}, None, profile(lin_std=0.3), profile(lin_std=0.3))["reward"]
    assert result["rule"] is None and result["values"] is None
    result = judge.propose(750, now, {}, None, profile(lin_std=0.4), profile(lin_std=0.4))["reward"]
    assert result["rule"] == "L1" and result["values"]["track_lin_vel_std"] == 0.3


def test_maintenance_fail_suppresses_both_adjustments():
    now = {"R_maintenance": "FAIL", "S_side_progress": 0.5,
           "V_fast_side_3seed": 150, "F1_slow_forward": 0.0, "P1_slow_spin": 0.0}
    for iteration in (500, 750):
        result = judge.propose(iteration, now, {}, None, profile(), None)
        assert result["command"]["state"] == "HOLD"
        assert result["reward"]["state"] == "HOLD"
        assert "proposed_commands" not in result["command"]
        assert result["reward"].get("values") is None


def test_body_forward_ratio_keeps_sign_and_excludes_initial_world_position(tmp_path):
    levels = {}
    for level in judge.LEVELS:
        source = tmp_path / level / "map_modes.json"
        source.parent.mkdir()
        source.write_text(json.dumps({"commands": {"fwd0.1": [0.1, 0, 0],
                                                   "fwd0.2": [0.2, 0, 0]},
                                      "env_arrays": {f"eval_gt/{case}": f"{case}.npz"
                                                     for case in ("fwd0.1", "fwd0.2")}}), encoding="utf-8")
        levels[level] = {"blocks": {"g1b": {"source": {"path": str(source)}}}}
        for case in ("fwd0.1", "fwd0.2"):
            vx = np.zeros((3, 64), dtype=np.float32)
            vx[:, :33] = -float(case.removeprefix("fwd"))
            alive = np.ones_like(vx, dtype=bool)
            np.savez(source.with_name(f"{case}.npz"), vx=vx, alive=alive, dt=0.02,
                     alive_steps=np.full(64, 3), body_vx_integral_m=vx.sum(axis=0) * 0.02,
                     run_identity=json.dumps({"checkpoint_sha256": "a" * 64, "eval_seed": 42}),
                     start_xy=np.tile([0.5, 0.0], (64, 1)))
    values, sources = judge.body_forward_ratios(levels, "a" * 64)
    assert len(sources) == 4
    assert all(np.isclose(values[f"body_forward_ratio/{lev}/{case}"], -1.0, rtol=0, atol=1e-6)
               for lev in judge.LEVELS for case in ("fwd0.1", "fwd0.2"))
