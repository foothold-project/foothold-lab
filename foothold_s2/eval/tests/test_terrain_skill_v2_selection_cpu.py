import pytest

from foothold_s2.eval import terrain_skill_v2_run as w78


def test_w78_defaults_to_complete_240_combinations():
    selected = w78.select_v2_cases("all")
    assert tuple(selected) == tuple(w78.V2_CASES)
    assert len(w78.expected_combinations(selected)) == 240


def test_w78_mode_case_work_unit_and_resume_contract(tmp_path):
    modes = w78.select_v2_modes("eval_pred")
    cases = w78.select_v2_cases("stairs_side_left")
    assert modes == ("eval_pred",)
    assert tuple(cases) == ("stairs_side_left",)
    assert len(w78.expected_combinations(cases, modes)) == 8
    partial = {
        "checkpoint_sha256": "a" * 64, "eval_seed": 42,
        "case_selection": ["stairs_side_left"], "mode_selection": ["eval_pred"],
        "modes": {"eval_pred": {"L2_a000_stairs_side_left": {
            "level": 2, "stair_start_angle_deg": 0, "case": "stairs_side_left",
            "terrain_assignment_sha256": "b" * 64}}},
    }
    path = tmp_path / "w78-unit-partial-fixture.json"
    path.write_text(__import__("json").dumps(partial), encoding="utf-8")
    try:
        _prior, completed, assignments = w78.read_resumable_partial(
            path, checkpoint_sha256="a" * 64, eval_seed=42,
            cases=("stairs_side_left",), modes=("eval_pred",))
        assert completed == {(2, 0, "eval_pred", "stairs_side_left")}
        assert assignments == {(2, 0): "b" * 64}
        import pytest
        with pytest.raises(ValueError, match="identity"):
            w78.read_resumable_partial(path, checkpoint_sha256="c" * 64, eval_seed=42,
                                       cases=("stairs_side_left",), modes=("eval_pred",))
    finally:
        path.unlink(missing_ok=True)


def test_w78_merge_requires_all_30_units_and_builds_canonical_240_grid(tmp_path):
    import hashlib
    import json
    from foothold_s2.eval.ex41_w78_merge import CASES, MODES, LEVELS, ANGLES, merge

    root = tmp_path / "parts"
    checkpoint = tmp_path / "model_6000.pt"
    checkpoint.write_bytes(b"known checkpoint")
    pinned = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    for mode in MODES:
        for case in CASES:
            part_dir = root / mode / case
            part_dir.mkdir(parents=True)
            rows = {}
            for level in LEVELS:
                for angle in ANGLES:
                    raw_name = f"row_{level}_{angle}_{mode}_{case}.npz"
                    (part_dir / raw_name).write_bytes(f"{level}-{angle}-{mode}-{case}".encode())
                    rows[f"L{level}_a{angle:03d}_{case}"] = {
                        "level": level, "stair_start_angle_deg": angle, "case": case,
                        "terrain_assignment_sha256": f"{level}{angle}".ljust(64, "0"),
                        "raw_file": raw_name,
                        "raw_sha256": hashlib.sha256((part_dir / raw_name).read_bytes()).hexdigest(),
                        "by_terrain_kind": {"pyramid_stairs": {"movement_ratio_median": 0.8},
                                            "pyramid_stairs_inv": {"movement_ratio_median": 0.7}},
                    }
            part = {"schema": "foothold-terrain-skill-v2/1", "state": "done",
                    "checkpoint_sha256": pinned, "checkpoint_iter": 6000, "eval_seed": 42,
                    "case_selection": [case], "mode_selection": [mode], "modes": {mode: rows},
                    "envs": 64, "levels": list(LEVELS), "start_angles_deg": list(ANGLES),
                    "dt_s": 0.02, "dr_off": {"enabled": False}, "curriculum_off": True}
            (part_dir / "terrain_skill_v2.json").write_text(json.dumps(part), encoding="utf-8")
    output = root / "terrain_skill_v2.json"
    merged = merge(root, checkpoint, output)
    assert merged["state"] == "done"
    assert len(merged["parts"]) == 30
    assert all(len(merged["modes"][mode]) == 80 for mode in MODES)
    assert len(merged["w78_min_lr_ratio"]) == 48
    assert merged["modes"]["eval_gt"]["L2_a000_stairs_fwd"]["raw_file"].startswith("eval_gt/stairs_fwd/")


def test_w78_approved_periodic_selector_is_exactly_48_combinations():
    selected = w78.select_v2_cases("stairs_side_left,stairs_side_right")
    assert tuple(selected) == w78.PERIODIC_SIDE_CASES
    expected = w78.expected_combinations(selected)
    assert len(expected) == 48
    assert {row[3] for row in expected} == set(w78.PERIODIC_SIDE_CASES)


@pytest.mark.parametrize("value", [
    "stairs_side_right,stairs_side_left",
    "stairs_side_left,stairs_side_left", "stairs_side_left,unknown", "",
])
def test_w78_selector_rejects_partial_ambiguous_or_invalid_coverage(value):
    if value == "":
        assert len(w78.select_v2_cases(value)) == len(w78.V2_CASES)
        return
    with pytest.raises(ValueError, match="case selector"):
        w78.select_v2_cases(value)


def test_w78_require_complete_rejects_one_missing_periodic_combination():
    cases = w78.select_v2_cases("stairs_side_left,stairs_side_right")
    complete = w78.expected_combinations(cases)
    w78.require_complete(complete, cases)
    complete.remove(next(iter(complete)))
    with pytest.raises(RuntimeError, match="47/48"):
        w78.require_complete(complete, cases)
