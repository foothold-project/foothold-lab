"""L0 CPU 시험. 답을 아는 입력과 negative control. Kit 없이 돈다."""

import math

import numpy as np
import pytest

from foothold_s2.eval import axis2_metrics, cells, judge, rsj, start_sheet
from foothold_s2.eval.stats import wilson

DT = 0.02


# ---------------------------------------------------------------- Wilson


def test_wilson_hand_computed_100_90():
    lo, hi = wilson(90, 100)
    assert round(lo, 3) == 0.826
    assert round(hi, 3) == 0.945


def test_wilson_edges():
    lo, hi = wilson(100, 100)
    assert round(lo, 3) == 0.963 and hi == 1.0
    lo, hi = wilson(0, 100)
    assert lo == pytest.approx(0.0, abs=1e-12) and round(hi, 3) == 0.037
    assert math.isnan(wilson(0, 0)[0])
    with pytest.raises(ValueError):
        wilson(5, 3)


# ---------------------------------------------------------------- 칸 목록


def test_axis1_cells_48_and_32():
    assert len(cells.axis1_cells()) == 48
    in_range = cells.axis1_in_range_cells()
    assert len(in_range) == 32
    assert {c[2] for c in in_range} == {0.5, 1.0}
    assert len({(c[1], c[2]) for c in cells.axis1_cells()}) == 48


def test_axis2_has_nine_cells():
    assert len(cells.AXIS2_CELLS) == 9


def test_axis3_table_marks_out_of_range_and_vy_obs():
    table = {(r["group"], r["direction"]): r for r in cells.axis3_table()
             if r.get("variant") != "observed"}
    assert table[("sparse", "diag")]["status"] == "out_of_range"
    assert table[("sparse", "left")]["commands"] == [(0.0, 0.2, 0.0)]
    assert table[("sparse", "right")]["commands"] == [(0.0, -0.2, 0.0)]
    assert table[("sparse", "left")]["basis"] == cells.VY_ASSUMED_LABEL
    assert table[("sparse", "back")]["commands"] == [(-0.3, 0.0, 0.0)]
    assert table[("sparse", "spin")]["commands"] == [(0.0, 0.0, 1.2), (0.0, 0.0, -1.2)]
    assert table[("continuous", "diag")]["commands"] == [(0.4, 0.4, 0.0)]
    with_vy = {(r["group"], r["direction"]): r for r in cells.axis3_table(vy_obs=0.3)}
    assert with_vy[("sparse", "left")]["commands"] == [(0.0, 0.3, 0.0)]
    assert with_vy[("sparse", "left")]["basis"] == "vy_obs"
    assert with_vy[("sparse", "right")]["commands"] == [(0.0, -0.3, 0.0)]
    assert sum(1 for r in table.values() if r["status"] == "out_of_range") == 1
    assert len(table) == 21
    assert len(cells.axis3_table()) == 23


def test_axis3_groups_are_disjoint_after_lead_decision():
    seen = {}
    for group, names in cells.TERRAIN_GROUPS.items():
        for n in names:
            assert n not in seen, (n, group, seen[n])
            seen[n] = group
    assert "pyramid_stairs" not in cells.TERRAIN_GROUPS["continuous"]
    assert len(cells.TERRAIN_GROUPS["continuous"]) == 6


def test_axis3_duration_rule():
    assert cells.axis3_duration_s((0.5, 0.0, 0.0)) == pytest.approx(12.0)
    assert cells.axis3_duration_s((0.0, 0.0, 1.0)) == 12.0
    assert cells.axis3_duration_s((0.4, 0.4, 0.0)) == pytest.approx(6.0 / math.hypot(0.4, 0.4))


# ---------------------------------------------------------------- 축 1 판정


def _straight(n, speed, fwd=(1.0, 0.0)):
    t = np.arange(n) * DT
    return np.stack([speed * t * fwd[0], speed * t * fwd[1]], axis=1)


def _axis1(pos, vel_err=None, timed_out=True, terminated=False, fwd=(1.0, 0.0)):
    if vel_err is None:
        vel_err = np.zeros(len(pos))
    return judge.judge_axis1(pos, vel_err, fwd, timed_out, terminated, DT,
                             min_progress_m=3.0, max_lateral_drift_m=0.75,
                             max_velocity_mae_mps=0.25)


def test_axis1_straight_walk_is_all_pass():
    pos = _straight(600, 0.5)
    row = _axis1(pos)
    assert row["overall_success"] and row["R_body"] and row["S"] and row["J_body"]
    assert row["forward_progress_m"] == pytest.approx(0.5 * 599 * DT)
    assert row["gate_lateral_drift_m"] == pytest.approx(0.0, abs=1e-9)


def test_axis1_sideways_drift_beyond_075_fails_direction():
    pos = _straight(600, 0.5)
    pos[:, 1] = np.linspace(0.0, 0.9 * 600 / 300, 600)  # 300 스텝(6 s)에 0.9 m
    row = _axis1(pos)
    assert row["gate_lateral_drift_m"] > 0.75
    assert not row["direction_success"] and not row["overall_success"]
    assert row["R_body"] and row["S"] and row["J_body"]


def test_axis1_lateral_just_inside_passes_and_078_fails():
    for lat, ok in ((0.70, True), (0.78, False)):
        pos = _straight(600, 0.5)
        pos[:, 1] = np.linspace(0.0, lat * 600 / 300, 600)
        assert _axis1(pos)["direction_success"] is ok


def test_axis1_fall_trajectory_fails_survival_and_J():
    pos = _straight(400, 0.5)
    row = _axis1(pos, timed_out=False, terminated=True)
    assert not row["S"] and not row["survival_success"]
    assert row["R_body"] and not row["J_body"]
    assert row["termination_reason"] == "base_contact"


def test_axis1_short_walk_never_reaches():
    pos = _straight(100, 0.5)
    row = _axis1(pos)
    assert not row["R_body"] and not row["J_body"] and row["S"]
    assert row["gate_lateral_drift_m"] is None and not row["direction_success"]


def test_axis1_tracking_failure_only_breaks_overall():
    pos = _straight(600, 0.5)
    row = _axis1(pos, vel_err=np.full(600, 0.4))
    assert not row["tracking_success"] and not row["overall_success"]
    assert row["J_body"]


def test_axis1_rotated_start_heading_uses_given_forward():
    th = math.radians(40)
    fwd = (math.cos(th), math.sin(th))
    pos = _straight(600, 0.5, fwd=fwd)
    row = _axis1(pos, fwd=fwd)
    assert row["overall_success"]
    assert row["gate_lateral_drift_m"] == pytest.approx(0.0, abs=1e-9)


def test_axis1_empty_rejected():
    with pytest.raises(ValueError):
        _axis1(np.zeros((0, 2)), vel_err=np.zeros(0))


# ---------------------------------------------------------------- 축 3 판정


def _cmd_episode(cmd, n, vel_b=None, wz=None, yaw=None, pos=None, active=None,
                 timed_out=True, terminated=False, ref=3.0):
    cmd_arr = np.tile(np.asarray(cmd, dtype=float), (n, 1))
    vel_b = np.tile([cmd[0], cmd[1]], (n, 1)) if vel_b is None else vel_b
    wz = np.full(n, cmd[2]) if wz is None else wz
    yaw = np.cumsum(wz) * DT if yaw is None else yaw

    if pos is None:
        th = np.concatenate([[0.0], np.cumsum(wz)[:-1] * DT])
        vx, vy = vel_b[:, 0], vel_b[:, 1]
        dx = (vx * np.cos(th) - vy * np.sin(th)) * DT
        dy = (vx * np.sin(th) + vy * np.cos(th)) * DT
        pos = np.stack([np.concatenate([[0.0], np.cumsum(dx)[:-1]]),
                        np.concatenate([[0.0], np.cumsum(dy)[:-1]])], axis=1)

    act = np.ones(n, dtype=bool) if active is None else active

    return judge.judge_command(pos, yaw, vel_b, wz, cmd_arr, act, timed_out, terminated,
                               DT, reference_m=ref)


def test_command_straight_front_zero_deviation():
    row = _cmd_episode((0.5, 0.0, 0.0), 600)
    assert row["R_body"] and row["S"] and row["J_body"]
    assert row["yaw_dev_deg"] == pytest.approx(0.0, abs=1e-6)
    assert row["yaw_dev_flag"] is False
    assert row["heading_err_deg"] == pytest.approx(0.0, abs=1e-6)
    assert row["lateral_dev_m"] == pytest.approx(0.0, abs=1e-6)
    assert row["cmd_progress_ratio"] == pytest.approx(0.5 * 599 * DT / 3.0)


def test_command_sideways_replaced_by_turning_is_a_deviation_failure():
    # 좌 0.5 명령인데 몸을 90 도 돌려 앞으로 걷는다
    n = 600
    wz = np.zeros(n)
    wz[:50] = math.pi / 2 / (50 * DT)
    yaw = np.cumsum(wz) * DT
    vel_b = np.zeros((n, 2))
    vel_b[50:, 0] = 0.5
    dx = (vel_b[:, 0] * np.cos(yaw)) * DT
    dy = (vel_b[:, 0] * np.sin(yaw)) * DT
    pos = np.stack([np.cumsum(dx), np.cumsum(dy)], axis=1)
    row = _cmd_episode((0.0, 0.5, 0.0), n, vel_b=vel_b, wz=wz, yaw=yaw, pos=pos)
    assert row["yaw_dev_flag"] is True and row["yaw_dev_deg"] > 80
    assert row["cmd_progress_ratio"] < 0.05
    assert not row["R_body"] and not row["J_body"]


def test_command_proper_left_strafe_passes():
    row = _cmd_episode((0.0, 0.5, 0.0), 600)
    assert row["R_body"] and row["J_body"] and row["yaw_dev_flag"] is False
    assert row["net_disp_y_m"] > 5.0


def test_command_lateral_push_is_recorded_not_hidden():
    n = 600
    pos = np.stack([np.arange(n) * 0.5 * DT, np.linspace(0.0, 0.75, n)], axis=1)
    vel_b = np.tile([0.5, 0.0], (n, 1))
    row = _cmd_episode((0.5, 0.0, 0.0), n, vel_b=vel_b, pos=pos, yaw=np.zeros(n))
    assert row["gate_lateral_dev_m"] > 0.3
    assert row["lateral_dev_m"] == pytest.approx(0.75, abs=0.05)
    assert row["heading_err_deg"] > 5


def test_command_fall_fails_S_and_J_but_keeps_R():
    row = _cmd_episode((0.5, 0.0, 0.0), 400, timed_out=False, terminated=True)
    assert row["R_body"] and not row["S"] and not row["J_body"]


def test_command_pure_spin_has_no_R_and_tracks_yaw():
    row = _cmd_episode((0.0, 0.0, 1.0), 600)
    assert row["R_body"] is None and row["J_body"] is None
    assert row["S"] is True
    assert row["yaw_follow_ratio"] == pytest.approx(1.0)
    assert row["yaw_dev_flag"] is None


def test_command_front_turn_arc_has_zero_yaw_deviation():
    row = _cmd_episode((0.5, 0.0, 0.5), 600)
    assert row["yaw_dev_deg"] == pytest.approx(0.0, abs=1e-6)
    assert row["R_body"] and row["heading_err_deg"] == pytest.approx(0.0, abs=2.0)


def test_command_stop_after_reach_does_not_drag_progress_down():
    n = 600
    act = np.arange(n) < 300
    vel_b = np.zeros((n, 2))
    vel_b[act, 0] = 0.5
    cmd = np.zeros((n, 3))
    cmd[act, 0] = 0.5
    pos = np.stack([np.cumsum(vel_b[:, 0]) * DT, np.zeros(n)], axis=1)
    row = judge.judge_command(pos, np.zeros(n), vel_b, np.zeros(n), cmd, act, True, False,
                              DT, reference_m=3.0)
    assert row["R_body"] and row["S"] and row["J_body"]
    assert row["cmd_progress_ratio"] == pytest.approx(1.0, abs=0.01)


def test_expected_displacement_arc_closes_a_circle():
    d = judge.expected_displacement((0.5, 0.0, 0.5), 2 * math.pi / 0.5)
    assert np.hypot(*d) < 0.02


# ---------------------------------------------------------------- R/S/J 집계


def test_rsj_invariants_and_negative_control():
    good = [{"R_body": True, "S": True, "J_body": True}, {"R_body": True, "S": False, "J_body": False},
            {"R_body": False, "S": True, "J_body": False}]
    out = rsj.summarize_rsj(good)
    assert out["J_body"]["k"] == 1 and out["R_body"]["k"] == 2 and out["S"]["k"] == 2

    with pytest.raises(rsj.RSJError):
        rsj.summarize_rsj([{"R_body": False, "S": True, "J_body": True}])
    with pytest.raises(rsj.RSJError):
        rsj.summarize_rsj([{"R_body": True, "S": False, "J_body": True}])
    with pytest.raises(rsj.RSJError):
        rsj.summarize_rsj([{"R_body": None, "S": True, "J_body": True}])


def test_rsj_from_real_judge_rows_never_violate():
    rng = np.random.default_rng(3)
    rows = []
    for _ in range(300):
        n = int(rng.integers(50, 700))
        speed = float(rng.uniform(0.1, 0.8))
        timed_out = bool(rng.random() < 0.6)
        pos = _straight(n, speed)
        pos[:, 1] = np.cumsum(rng.normal(0, 0.01, n))
        rows.append(_axis1(pos, timed_out=timed_out, terminated=not timed_out))
    out = rsj.summarize_rsj(rows)
    assert out["J_body"]["k"] <= min(out["R_body"]["k"], out["S"]["k"])


def test_degenerate_cell_flag():
    rows = [{"R_body": False, "S": False, "J_body": False}] * 5
    assert rsj.summarize_axis3_cell(rows)["degenerate"] is True
    rows = [{"R_body": True, "S": True, "J_body": True}] * 5
    assert rsj.summarize_axis3_cell(rows)["degenerate"] is True
    rows = [{"R_body": True, "S": True, "J_body": True}, {"R_body": False, "S": True, "J_body": False}]
    assert rsj.summarize_axis3_cell(rows)["degenerate"] is False


def test_axis3_cell_counts_deviation_rate():
    rows = [dict(R=True, S=True, J=True, yaw_dev_flag=f) for f in (True, False, False, False)]
    out = rsj.summarize_axis3_cell(rows)
    assert out["yaw_dev_rate"] == 0.25 and out["yaw_dev_n"] == 4


# ---------------------------------------------------------------- 축 2


def test_axis2_yaw_follow_and_hold():
    n = 900
    cmd = np.zeros((n, 3))
    cmd[:, 2] = np.where(np.arange(n) < 450, 1.0, -0.5)
    wz = cmd[:, 2] * 0.9
    jt = np.zeros((n, 12))
    m = axis2_metrics.env_metrics(np.zeros(n), np.zeros(n), wz, cmd, jt, DT, float("nan"))
    assert m["yaw_follow"]["+1.00"] == pytest.approx(0.9)
    assert m["yaw_follow"]["-0.50"] == pytest.approx(0.9)
    assert m["residual_speed_mps"] == 0.0 and m["joint_target_delta_tail"] == 0.0


def test_axis2_fell_ratio_counts_degenerate_envs():
    ok = axis2_metrics.env_metrics(np.zeros(50), np.zeros(50), np.zeros(50),
                                   np.zeros((50, 3)), np.zeros((50, 12)), DT, float("nan"))
    fell = axis2_metrics.env_metrics(np.zeros(1), np.zeros(1), np.zeros(1),
                                     np.zeros((1, 3)), np.zeros((1, 12)), DT, 0.02)
    assert fell["degenerate"] and fell["fell"]
    agg = axis2_metrics.aggregate_scenario([ok, ok, ok, fell])
    assert agg["fell_ratio"] == 0.25 and agg["envs_degenerate"] == 1


def test_axis2_judge_cells_missing_value_is_not_a_pass():
    summary = {"stop": {"fell_ratio": 0.0}}
    rows = {r["cell"]: r for r in axis2_metrics.judge_cells(summary)}
    assert rows["stop/fell_ratio"]["passed"] is True
    assert rows["hold/fell_ratio"]["value"] is None
    assert rows["hold/fell_ratio"]["passed"] is False
    assert len(rows) == 9


def test_axis2_judge_threshold_edges():
    summary = {
        "stop": {"fell_ratio": 0.03},
        "hold": {"fell_ratio": 0.0, "residual_speed_mps": 0.0051,
                 "joint_target_delta_tail": 0.01},
        "turn": {"fell_ratio": 0.109375,
                 "yaw_follow_ratio": {"-1.00": 0.4, "-0.50": 0.39, "+0.50": 0.9, "+1.00": 0.9}},
    }
    rows = {r["cell"]: r["passed"] for r in axis2_metrics.judge_cells(summary)}
    assert rows["stop/fell_ratio"] and rows["hold/joint_target_delta_tail"]
    assert not rows["hold/residual_speed_mps"] and not rows["turn/fell_ratio"]
    assert rows["turn/yaw_follow/-1.00"] and not rows["turn/yaw_follow/-0.50"]


# ---------------------------------------------------------------- START 시험지


def _geom(kind, level, seed=0):
    return start_sheet.generate(kind, level, np.random.default_rng(seed))


def test_start_stepping_stones_level9_dimensions():
    g = _geom("stepping_stones", 9)
    assert g.params["stone"] == pytest.approx(0.2)
    assert g.params["gap_x"] == pytest.approx(0.25)
    assert g.params["gap_y"] == pytest.approx(0.175)
    sp = start_sheet.sparsity(g)
    assert abs(sp - 0.763) < 0.02, sp


def test_start_stepping_stones_level0_stone_half_meter():
    g = _geom("stepping_stones", 0)
    assert g.params["stone"] == pytest.approx(0.5)
    assert g.params["jitter"] == 0.0


def test_start_level10_and_unknown_kind_rejected():
    with pytest.raises(ValueError):
        _geom("stepping_stones", 10)
    with pytest.raises(ValueError):
        _geom("stepping_stones", -1)
    with pytest.raises(ValueError):
        _geom("stepping_stones", 2.5)
    with pytest.raises(ValueError):
        _geom("moon", 3)


def test_start_beam_width_and_stepping_beams_sparsity():
    assert _geom("balance_beams", 9).params["beam_width"] == pytest.approx(0.175)
    g = _geom("stepping_beams", 9)
    assert g.params["beam"] == pytest.approx(0.15)
    assert g.params["gap"] == pytest.approx(0.275)
    assert abs(start_sheet.sparsity(g) - 0.647) < 0.02


def test_start_gaps_level9_width_07_and_depth_range():
    g = _geom("gaps", 9)
    assert g.params["gap_width"] == pytest.approx(0.7)
    assert _geom("gaps", 0).params["gap_width"] == pytest.approx(0.1)
    for seed in range(20):
        assert 0.2 <= _geom("gaps", 5, seed).depth <= 0.7


def test_start_height_jitter_within_5cm():
    g = _geom("stepping_stones", 9, seed=4)
    tops = g.boxes[3:, 5]
    assert np.all(np.abs(tops) <= 0.05 + 1e-9)


def test_start_mev_counts_edge_steps():
    g = _geom("balance_beams", 9)
    yc = start_sheet.SIZE[1] / 2.0
    center = [(3.0, yc), (4.0, yc), (5.0, yc)]
    edge = [(3.0, yc + 0.175 / 2 - 0.01)]
    assert start_sheet.mev(g, center) == 0.0
    assert start_sheet.mev(g, center + edge) == pytest.approx(0.25)
    assert start_sheet.mev(g, [(3.0, 0.2)]) is None
    assert start_sheet.crossing_ratio(3.25) == pytest.approx(0.5)
    assert start_sheet.crossing_ratio(99.0) == 1.0


# ---------------------------------------------------------------- 듬성한 행 뒤 · 옆 칸 규칙 (41 §4 결정 2)


def test_sparse_short_rule_known_answers():
    side = cells.axis3_rule("sparse", "left", (0.0, 0.2, 0.0))
    assert side["reference_m"] == pytest.approx(0.4)
    assert side["duration_s"] == 4.0 and side["command_s"] == 2.0

    back = cells.axis3_rule("sparse", "back", (-0.3, 0.0, 0.0))
    assert back["reference_m"] == pytest.approx(0.6) and back["duration_s"] == 4.0

    right = cells.axis3_rule("sparse", "right", (0.0, -0.25, 0.0))
    assert right["reference_m"] == pytest.approx(0.5)


def test_other_cells_keep_the_3m_rule():
    for group, direction, cmd in (("sparse", "front", (0.5, 0.0, 0.0)), ("sparse", "spin", (0.0, 0.0, 1.2)),
                                  ("sparse", "front_turn", (0.5, 0.0, 0.5)),
                                  ("continuous", "back", (-0.5, 0.0, 0.0)), ("stairs", "left", (0.0, 0.5, 0.0))):
        rule = cells.axis3_rule(group, direction, cmd)
        assert rule["reference_m"] == 3.0 and rule["command_s"] is None
        assert rule["duration_s"] == pytest.approx(cells.axis3_duration_s(cmd))


def test_sparse_short_cell_judges_with_the_new_distance():
    """명령 2 s (100 스텝) 뒤 정지, 총 4 s. 0.2 m/s 로 정확히 걸으면 기준 0.4 m 에 닿는다."""
    n = 200
    pos = np.zeros((n, 2))
    pos[:, 1] = np.minimum(np.arange(n), 100) * 0.2 * DT
    yaw = np.zeros(n)
    vel = np.zeros((n, 2))
    vel[:100, 1] = 0.2
    cmd = np.zeros((n, 3))
    cmd[:100, 1] = 0.2
    act = np.zeros(n, dtype=bool)
    act[:100] = True
    rule = cells.axis3_rule("sparse", "left", (0.0, 0.2, 0.0))
    row = judge.judge_command(pos, yaw, vel, np.zeros(n), cmd, act, True, False, DT,
                              reference_m=rule["reference_m"])
    assert row["R_body"] and row["S"] and row["J_body"]
    assert row["cmd_progress_ratio"] == pytest.approx(1.0)
    assert row["active_s"] == pytest.approx(2.0, abs=DT)
    assert row["duration_s"] == pytest.approx(4.0, abs=DT)

    # 같은 걸음을 옛 규칙(3 m)으로 보면 도달하지 못한다: 규칙이 실제로 판정을 바꾼다.
    old = judge.judge_command(pos, yaw, vel, np.zeros(n), cmd, act, True, False, DT, reference_m=3.0)
    assert not old["R_body"]
