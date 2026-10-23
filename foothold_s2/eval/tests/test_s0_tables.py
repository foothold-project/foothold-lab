"""S0 표 만들기 시험: 가짜 원자료로 풀링 · 범위 밖 · 열 합집합을 확인한다 (Kit 없음)."""

import os

from foothold_s2.eval import manifest, s0_chain, s0_tables


def _write_axis3(root, policy, group, direction, cmd, rows):
    tag = "%s_%s_%s" % (group, direction, s0_chain._cmd_text(cmd).replace(",", "_"))
    d = os.path.join(root, policy, "axis3", tag)
    os.makedirs(d, exist_ok=True)
    manifest.write_csv(os.path.join(d, "axis3_raw.csv"), rows)


def _row(terrain, r, s, dev=False):
    return {"terrain": terrain, "R_body": r, "S": s, "J_body": bool(r and s), "yaw_dev_flag": dev,
            "cmd_progress_ratio": 1.0, "cmd_progress_ratio_capped": 1.0, "velocity_mae_mps": 0.1,
            "yaw_follow_ratio": None, "yaw_dev_deg": 5.0, "heading_err_deg": 1.0,
            "lateral_dev_m": 0.1, "gate_lateral_dev_m": 0.1}


def test_spin_pools_both_signs_and_out_of_range_has_no_values(tmp_path):
    root = str(tmp_path)
    _write_axis3(root, "e1", "continuous", "spin", (0.0, 0.0, 1.0), [
        dict(_row("wave", None, True), R_body=None, J_body=None, yaw_dev_flag=None)] * 3)
    _write_axis3(root, "e1", "continuous", "spin", (0.0, 0.0, -1.0), [
        dict(_row("wave", None, False), R_body=None, J_body=None, yaw_dev_flag=None)] * 1)
    pooled, by_terrain = s0_tables.axis3_tables(root, ["e1"])
    spin = [r for r in pooled if r["group"] == "continuous" and r["direction"] == "spin"][0]
    assert spin["episodes"] == 4 and spin["S_rate"] == 0.75 and spin["S_n"] == 4
    assert spin["R_body_n"] == 0
    diag = [r for r in pooled if r["group"] == "sparse" and r["direction"] == "diag"][0]
    assert diag["status"] == "out_of_range" and diag.get("S_rate") is None
    assert len(pooled) == 23


def test_not_run_cells_are_marked_not_zero(tmp_path):
    pooled, _ = s0_tables.axis3_tables(str(tmp_path), ["v2"])
    measured = [r for r in pooled if r["status"] == "not_run"]
    assert len(measured) == 20 and all(r.get("S_rate") is None for r in measured)


def test_uniform_fills_union_of_columns():
    rows = s0_tables._uniform([{"a": 1}, {"b": 2}])
    assert rows == [{"a": 1, "b": None}, {"a": None, "b": 2}]


def test_read_rows_converts_booleans_and_numbers(tmp_path):
    manifest.write_csv(str(tmp_path / "r.csv"), [{"R_body": True, "S": False, "yaw_dev_deg": 12.5,
                                                  "yaw_dev_flag": None}])
    row = s0_tables.read_rows(str(tmp_path / "r.csv"))[0]
    assert row["R_body"] is True and row["S"] is False and row["yaw_dev_deg"] == 12.5
    assert row["yaw_dev_flag"] is None


def test_compare_policies_carries_yaw_deviation_rate_for_every_policy():
    axis3 = [
        {"policy": "e1", "group": "continuous", "direction": "front", "status": "measure",
         "J_body_rate": 1.0, "S_rate": 1.0, "yaw_dev_rate": 0.27, "mean_cmd_progress_ratio_capped": 1.0},
        {"policy": "v2", "group": "continuous", "direction": "front", "status": "measure",
         "J_body_rate": 0.9, "S_rate": 1.0, "yaw_dev_rate": 0.05, "mean_cmd_progress_ratio_capped": 0.97},
    ]
    rows = s0_tables.compare_policies([], axis3)
    dev = [r for r in rows if r["extra"] == "yaw_dev_rate"]
    assert len(dev) == 1 and dev[0]["e1"] == 0.27 and dev[0]["v2"] == 0.05
