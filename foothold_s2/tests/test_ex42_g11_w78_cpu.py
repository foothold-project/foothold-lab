from copy import deepcopy

from foothold_s2.eval.ex42_w78_gate import compare_split, unit_queue_admission


def receipt(value=1.0):
    return {"state": "done", "run_identity": {"code_head": "a" * 40},
            "source_sha256": {"terrain_skill_v2_run.py": "b" * 64},
            "checkpoint_sha256": "c" * 64, "checkpoint_iter": 750,
            "eval_seed": 42, "envs": 64, "levels": [2], "start_angles_deg": [0],
            "dt_s": 0.02, "dr_off": True, "curriculum_off": True,
            "mode_selection": ["eval_gt"], "case_selection": ["stairs_side_left"],
            "modes": {"eval_gt": {"L2_a000_stairs_side_left": {"distance": value}}}}


def test_g11_exact_same_code_unit():
    assert compare_split(receipt(), [receipt()])["state"] == "PASS"


def test_g11_different_code_or_unmeasured_difference_holds():
    full, unit = receipt(), receipt(1.1)
    assert compare_split(full, [unit])["reason"] == "repeat_width_missing"
    unit["run_identity"]["code_head"] = "d" * 40
    assert compare_split(full, [unit])["reason"] == "source_or_completion_differs"


def test_g11_repeat_width_is_measured_not_assumed():
    full, unit = receipt(), receipt(1.1)
    assert compare_split(full, [unit], repeats=[receipt(1.04), receipt(1.2)])["state"] == "PASS"
    assert compare_split(full, [unit], repeats=[receipt(1.01), receipt(1.02)])["reason"] == "beyond_repeat_width"


def test_g11_queue_yields_to_gpu1_p1():
    unit = {"id": 7, "gpu": 1, "priority": 2, "kind": "eval", "state": "대기"}
    p1 = {"id": 8, "gpu": 1, "priority": 1, "kind": "eval", "state": "실행"}
    assert unit_queue_admission({"items": [unit, p1]}, 7)["state"] == "yield_to_P1"
    assert unit_queue_admission({"items": [unit]}, 7)["state"] == "eligible"
