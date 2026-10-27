"""Known-input grouping and actual receipt checks for the map-error card."""

import numpy as np
import pytest

from lab_map_error import group_inrange, main_launch_evidence, render


def test_known_tiles_group_env_means_without_step_weighting():
    data = {"envs": 4, "fixed_terrain": {"tiles": [
        {"env": 0, "kind": "gaps"}, {"env": 1, "kind": "gaps"},
        {"env": 2, "kind": "beams"}, {"env": 3, "kind": "beams"},
    ]}}
    arrays = {
        "env": np.arange(4), "kind": np.array(["gaps", "gaps", "beams", "beams"]),
        "map_err_inrange_mean_cm": np.array([2.0, 4.0, 6.0, 10.0]),
        "map_err_inrange_steps": np.array([1, 300, 20, 100]),
    }
    assert group_inrange(data, arrays, require_tiles=True) == [("beams", 2, 8.0), ("gaps", 2, 3.0)]
    data["fixed_terrain"]["tiles"][0]["kind"] = "beams"
    with pytest.raises(ValueError, match="disagree"):
        group_inrange(data, arrays, require_tiles=True)


def test_real_receipts_are_labeled_smoke_and_not_judgement():
    card = render()
    assert card.count("<tr>") == 13  # header plus five sparse and seven default kinds
    assert "reviewer 막음 0(REVIEW-496e0cfe.md)" in card
    assert "verifier 막음 0(VERIFY-verifier-496e0cfe-map-error.md)" in card
    launched, first_npz = main_launch_evidence()
    assert launched == "12:46:30" and first_npz == "12:47:06"
    assert "본 측정 X27n GPU0 12:46:30 기동, 진행 중(첫 NPZ 12:47:06 생성)" in card
    assert "결과 수치는 진행 중이라 미기입" in card
    assert "옛 valid 지표" in card
    assert "map_err_x27m4\\smoke64_sparse50_pred" in card
    assert "map_err_x27m4\\smoke64_default_pred" in card
