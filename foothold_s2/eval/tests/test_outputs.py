"""산출물 점검 · 옛 값 대조 · CSV 규칙 시험 (Kit 없음)."""

import pytest

from foothold_s2.eval import compare, manifest


def _make_run(tmp_path, rows=3, log="ok\n", with_manifest=True):
    manifest.write_csv(str(tmp_path / "axis1_raw.csv"), [{"a": i, "b": None} for i in range(rows)])
    (tmp_path / "run.log").write_text(log, encoding="utf-8")

    if with_manifest:
        manifest.write_json(str(tmp_path / "run_manifest.json"), {"x": 1})

    return str(tmp_path)


def test_check_run_dir_passes_a_good_run(tmp_path):
    ok, problems = manifest.check_run_dir(_make_run(tmp_path), 3, "axis1_raw.csv")
    assert ok and not problems


def test_check_run_dir_catches_traceback_even_with_all_files(tmp_path):
    d = _make_run(tmp_path, log="Traceback (most recent call last):\n  boom\n")
    ok, problems = manifest.check_run_dir(d, 3, "axis1_raw.csv")
    assert not ok and any("Traceback" in p for p in problems)


def test_check_run_dir_catches_short_csv_and_missing_manifest(tmp_path):
    d = _make_run(tmp_path, rows=2, with_manifest=False)
    ok, problems = manifest.check_run_dir(d, 3, "axis1_raw.csv")
    assert not ok and len(problems) == 2


def test_check_run_dir_empty_dir_fails(tmp_path):
    ok, problems = manifest.check_run_dir(str(tmp_path), 3, "axis1_raw.csv")
    assert not ok and len(problems) == 3


def test_write_csv_blank_for_none_and_rejects_ragged_rows(tmp_path):
    p = str(tmp_path / "t.csv")
    manifest.write_csv(p, [{"a": 1, "b": None}])
    assert manifest.read_csv(p) == [{"a": "1", "b": ""}]

    with pytest.raises(ValueError):
        manifest.write_csv(p, [{"a": 1}, {"a": 1, "b": 2}])

    with pytest.raises(ValueError):
        manifest.write_csv(p, [])


def test_diff_table_flags_cells_outside_tolerance():
    new = {("rough6", "boxes", 0.5): 0.79, ("rough6", "random_rough", 0.5): 0.60, ("a", "only_new", 1.0): 1.0}
    old = {("rough6", "boxes", 0.5): 0.80, ("rough6", "random_rough", 0.5): 0.65}
    rows, summary = compare.diff_table(new, old)
    assert summary["cells_compared"] == 2
    assert summary["cells_outside_tolerance"] == 1
    assert summary["max_abs_delta"] == pytest.approx(0.05)
    assert summary["missing_in_old"] == 1


def test_cell_means_split_in_range():
    vals = {("s", "t", 0.5): 1.0, ("s", "t", 1.0): 0.5, ("s", "t", 1.5): 0.0}
    out = compare.cell_means(vals)
    assert out["mean_all"] == pytest.approx(0.5)
    assert out["n_in_range"] == 2 and out["mean_in_range"] == pytest.approx(0.75)


def test_episode_level_match_detects_a_flipped_episode(tmp_path):
    base = [{"terrain": "t", "env_id": str(i), "episode": "1", "overall_success": "True"} for i in range(3)]
    flipped = [dict(r) for r in base]
    flipped[1]["overall_success"] = "False"
    manifest.write_csv(str(tmp_path / "n.csv"), flipped)
    manifest.write_csv(str(tmp_path / "o.csv"), base)
    out = compare.episode_level_match(str(tmp_path / "n.csv"), str(tmp_path / "o.csv"))
    assert out["joined"] == 3 and out["same_overall"] == 2 and out["differ"] == [("t", "1", "1")]


def test_axis2_seed_table_counts_failed_seeds(tmp_path):
    def write(sub, vals):
        d = tmp_path / sub
        d.mkdir()
        manifest.write_csv(str(d / "axis2_cells.csv"), [
            {"cell": "hold/joint_target_delta_tail", "threshold": "<= 0.01", "value": v, "passed": v <= 0.01}
            for v in vals])
    write("axis2", [0.002])
    write("axis2_s43", [0.011])
    write("axis2_s44", [0.004])
    rows = compare.axis2_seed_table(str(tmp_path))
    assert rows[0]["passed"] == "True" and rows[0]["value"] == "0.002"
    assert rows[0]["seeds_measured"] == 3 and rows[0]["seeds_failed"] == 1
    assert rows[0]["value_s43"] == "0.011"


def test_axis2_seed_table_missing_seeds_are_not_counted(tmp_path):
    d = tmp_path / "axis2"
    d.mkdir()
    manifest.write_csv(str(d / "axis2_cells.csv"),
                       [{"cell": "c", "threshold": "<= 1", "value": 2.0, "passed": False}])
    rows = compare.axis2_seed_table(str(tmp_path))
    assert rows[0]["seeds_measured"] == 1 and rows[0]["seeds_failed"] == 1
    assert rows[0]["value_s43"] == ""
