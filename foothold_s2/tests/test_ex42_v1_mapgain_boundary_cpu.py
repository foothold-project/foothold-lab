"""CPU tests of the new E2 v1 boundary judge (numbers are the seed-mean cells of the 11/20 map-gain tables, 64 envs)."""
import json

import numpy as np

from foothold_s2.tools import ex42_v1_mapgain_boundary as J


def cell(gt, pred, flat, shift, off, gt_alive=40.0, off_alive=40.0):
    return {"gt": (gt, gt_alive), "pred": (pred, 0), "flat": (flat, 0), "shift": (shift, 0), "off": (off, off_alive)}


def test_canon3_a_gaps_is_one_cell_short():
    # design 4 section start values: 0.7 gain +4.7 (judgeable), 1.0 gain +14.3 -> one cell short of two
    v = J.judge_kind({"0.7": cell(29.7, 30.0, 25.0, 25.0, 25.0), "1.0": cell(57.7, 58.7, 43.3, 55.0, 55.0)})
    assert v["verdict"] == "not_yet" and v["first_window_pass"] is False and v["passing_speeds"] == ["1.0"] and v["need"] == 2


def test_old_e2_beams_graduate_through_a_ceiling_speed():
    # 0.7 passes (+15.7, 55.0); 1.0 is ceiling (flat 58.7 > 56) -> need 1
    v = J.judge_kind({"0.7": cell(55.0, 55.0, 39.3, 40.0, 40.0), "1.0": cell(62.4, 62.0, 58.7, 60.0, 60.0)})
    assert v["ceiling_speeds"] == ["1.0"] and v["need"] == 1 and v["verdict"] == "graduate" and v["raise_cap"] is True


def test_both_ceiling_raises_and_both_floor_is_undecidable():
    assert J.judge_kind({"0.7": cell(60, 60, 58, 58, 58), "1.0": cell(60, 60, 58, 58, 58)})["verdict"] == "ceiling"
    v = J.judge_kind({"0.7": cell(2, 2, 1, 1, 1), "1.0": cell(5, 5, 4, 4, 4)})
    assert v["verdict"] == "undecidable" and v["first_window_pass"] is False and v["floor_speeds"] == ["0.7", "1.0"]


def test_each_of_the_four_tests_can_fail_alone():
    ok = {"0.7": cell(50, 50, 30, 30, 30), "1.0": cell(52, 52, 30, 30, 30)}
    assert J.judge_kind(ok)["verdict"] == "graduate"
    low = {"0.7": cell(50, 50, 30, 30, 30), "1.0": cell(47, 47, 30, 30, 30)}                   # crossed < 48
    assert J.judge_kind(low)["verdict"] == "not_yet"
    weak_pred = {"0.7": cell(50, 39, 30, 30, 30), "1.0": cell(52, 52, 30, 30, 30)}             # pred 11 below
    assert J.judge_kind(weak_pred)["verdict"] == "not_yet"
    harm = {"0.7": cell(50, 50, 30, 30, 30, gt_alive=20, off_alive=31), "1.0": cell(52, 52, 30, 30, 30)}   # alive 11 below off
    assert J.judge_kind(harm)["verdict"] == "not_yet"
    small = {"0.7": cell(50, 50, 41, 41, 41), "1.0": cell(52, 52, 30, 30, 30)}                 # gain 9
    assert J.judge_kind(small)["verdict"] == "not_yet"


def test_missing_cell_is_incomplete_not_a_pass():
    v = J.judge_kind({"0.7": None, "1.0": cell(60, 60, 20, 20, 20)})
    assert v["verdict"] == "incomplete" and v["first_window_pass"] is False


def test_evidence_list_matches_raise_kind_caps(tmp_path):
    from foothold_s2.terrains.ex42_exposure import raise_kind_caps
    path = tmp_path / "ladder_outcomes_list.json"
    kinds = {"A/gaps": {"first_window_pass": True}, "A/balance_beams": {"first_window_pass": False}}
    J.write_evidence(path, 1, kinds)
    entries = json.loads(path.read_text())
    assert entries == [{"A/balance_beams": {"first_window_pass": False, "target_level_reached": False},
                        "A/gaps": {"first_window_pass": True, "target_level_reached": False}}]
    terrain = {"kind_level_cap": {"end": 5, "step_per_boundary": 1},
               "exposure_at_E2": {"positive": [{"family": "A", "kind": "gaps", "share": 0.14, "level_cap": 1},
                                               {"family": "A", "kind": "balance_beams", "share": 0.14, "level_cap": 1}]}}
    new, moves = raise_kind_caps(terrain, "E2", 1, entries)
    assert [(m["kind"], m["before"], m["after"]) for m in moves] == [("A/gaps", 1, 2)]
    assert J.write_evidence(path, 2, kinds, entries)[0] == entries[0] and len(json.loads(path.read_text())) == 2


def test_read_cell_counts_crossed_and_alive(tmp_path):
    for seed, xs in ((42, 3.0), (43, 1.0)):
        for inp, suffix in (("gt", "main"), ("pred", "main"), ("off", "main"), ("flat", "flat"), ("shift", "shift20")):
            d = tmp_path / f"A_gaps_L1_v1.0_s{seed}_{suffix}"
            d.mkdir(exist_ok=True)
            (d / "DONE").write_text("")
            x = np.zeros((300, 64)); x[:, :32] = xs
            alive = np.zeros(64, bool); alive[:48] = True
            np.savez(d / f"env_arrays_{J.MODE_OF[inp]}_x.npz", root_x_local_m=x, alive_end=alive)
    c = J.read_cell(tmp_path, "A_gaps_L1", "1.0", seeds=(42, 43), threshold=2.0)
    assert c["gt"] == (16.0, 48.0)                       # seed 42: 32 envs past 2.0 m, seed 43: 0 -> mean 16
    assert J.read_cell(tmp_path, "A_gaps_L1", "0.7", seeds=(42,)) is None
