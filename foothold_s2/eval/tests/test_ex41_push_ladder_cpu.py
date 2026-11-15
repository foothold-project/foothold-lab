from __future__ import annotations

import pytest

from foothold_s2.eval.ex41_push_ladder import (
    DIRECTIONS_DEG,
    MAGNITUDES_MPS,
    MAP_MODES,
    TERRAIN_CASES,
    build_case_grid,
    fixed_target_range,
    summarize_ladder,
)


def _rows():
    rows = []
    for magnitude in MAGNITUDES_MPS:
        for angle in DIRECTIONS_DEG:
            survivors = 64 if magnitude <= 1.5 else (58 if magnitude == 2.0 else 57)
            rows.append({
                "terrain": "flat",
                "map_mode": "eval_gt",
                "command": "walk_0.5",
                "magnitude_mps": magnitude,
                "direction_deg": angle,
                "envs": 64,
                "survivors_after_5s": survivors,
                "recovery_times_s": [0.4, 0.8],
                "max_tilt_rad": 0.7,
            })
    return rows


def test_grid_covers_every_requested_condition_once():
    cases = build_case_grid()
    assert len(cases) == 432
    assert len({(c["terrain"], c["map_mode"], c["magnitude_mps"], c["direction_deg"])
                for c in cases}) == 432
    assert len(TERRAIN_CASES) == 3
    assert len(MAP_MODES) == 3
    walk = build_case_grid(command="walk_0.5", directions=DIRECTIONS_DEG)
    assert len(walk) == 432 and {row["command"] for row in walk} == {"walk_0.5"}
    assert len(build_case_grid(command="walk_1.0")) == 432
    assert len(build_case_grid(command="walk_1.5")) == 432
    assert len(build_case_grid(command="stand_turn_1.2")) == 432
    stand = build_case_grid(terrain="flat", command="stand", directions=(0, 90, 180, 270))
    assert len(stand) == 72
    assert {row["direction_deg"] for row in stand} == {0, 90, 180, 270}


def test_fixed_push_sets_world_xy_velocity_at_exact_requested_direction():
    target = fixed_target_range(2.0, 90)
    assert target == {"x": (0.0, 0.0), "y": (2.0, 2.0), "z": (0.0, 0.0),
                      "roll": (0.0, 0.0), "pitch": (0.0, 0.0), "yaw": (0.0, 0.0)}


def test_tolerance_uses_pooled_64_envs_per_direction_and_90_percent_threshold():
    result = summarize_ladder(_rows(), terrain="flat", map_mode="eval_gt")
    assert result["magnitudes"]["2.0"]["survivors"] == 8 * 58
    assert result["magnitudes"]["2.0"]["survival_fraction"] == pytest.approx(58 / 64)
    assert result["maximum_tolerated_mps"] == 2.0
    assert result["magnitudes"]["2.0"]["worst_direction_survival_fraction"] == pytest.approx(58 / 64)
    assert result["maximum_tolerated_worst_direction_mps"] == 2.0
    assert result["threshold_fraction"] == 0.9


def test_recovery_median_ignores_null_envs_and_keeps_all_null_direction_empty():
    rows = _rows()
    rows[0] = {**rows[0], "recovery_times_s": [None, 0.5]}
    rows[1] = {**rows[1], "recovery_times_s": [None, None]}

    result = summarize_ladder(rows, terrain="flat", map_mode="eval_gt")
    directions = result["magnitudes"]["0.5"]["directions"]
    assert directions["0"]["recovery_time_s_median"] == pytest.approx(0.5)
    assert directions["45"]["recovery_time_s_median"] is None


def test_incomplete_or_duplicate_direction_is_rejected():
    rows = _rows()
    with pytest.raises(ValueError, match="48 unique cells"):
        summarize_ladder(rows[:-1], terrain="flat", map_mode="eval_gt")
    rows[-1] = dict(rows[0])
    with pytest.raises(ValueError, match="48 unique cells"):
        summarize_ladder(rows, terrain="flat", map_mode="eval_gt")


def test_invalid_sample_count_and_nonfinite_metrics_are_rejected():
    rows = _rows()
    rows[0] = {**rows[0], "envs": 63}
    with pytest.raises(ValueError, match="64 envs"):
        summarize_ladder(rows, terrain="flat", map_mode="eval_gt")
    rows = _rows()
    rows[0] = {**rows[0], "max_tilt_rad": float("nan")}
    with pytest.raises(ValueError, match="finite"):
        summarize_ladder(rows, terrain="flat", map_mode="eval_gt")


def test_command_identity_is_mandatory_and_mismatch_is_rejected():
    rows = _rows()
    rows[0] = {**rows[0], "command": "stand"}
    with pytest.raises(ValueError, match="command"):
        summarize_ladder(rows, terrain="flat", map_mode="eval_gt")
