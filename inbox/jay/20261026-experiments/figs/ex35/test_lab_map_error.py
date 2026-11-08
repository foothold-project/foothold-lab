"""Known-input grouping and actual receipt checks for the map-error card."""

import numpy as np
import pytest

from lab_map_error import MAIN, group_inrange, main_launch_evidence, render, render_main, render_smoke


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
    card = render_smoke()
    assert card.count("<tr>") == 13  # header plus five sparse and seven default kinds
    assert "reviewer 막음 0(REVIEW-496e0cfe.md)" in card
    assert "verifier 막음 0(VERIFY-verifier-496e0cfe-map-error.md)" in card
    launched, first_npz = main_launch_evidence()
    assert launched == "12:46:30" and first_npz == "12:47:06"
    assert "옛 valid 지표" in card
    assert "map_err_x27m4\\smoke64_sparse50_pred" in card
    assert "map_err_x27m4\\smoke64_default_pred" in card


def test_completed_main_table_uses_raw_npz_and_keeps_smoke_below():
    table = render_main()
    assert table.count("<tr>") == 34  # header plus 7 kinds on four levels and five sparse kinds
    assert "13:09:01 MAIN DONE · 12단계 rc=0" in table
    assert "한 번 잰 값 · 흔들림 폭 미측 · 해석 미완" in table
    assert 'href="evidence/maperr_parent_vs_m2000.md"' in table
    parent = MAIN / "parent_m1500/map64_eval_pred/env_arrays_eval_pred_fwd1.0.npz"
    newer = MAIN / "ex35_m2000/map64_eval_pred/env_arrays_eval_pred_fwd1.0.npz"
    with np.load(parent, allow_pickle=False) as a, np.load(newer, allow_pickle=False) as b:
        selection = a["kind"] == "boxes"
        assert np.array_equal(a["kind"], b["kind"])
        expected = (
            f"<tr><td>L0~2</td><td>boxes</td><td>{int(selection.sum())}</td>"
            f"<td>{float(a['map_err_inrange_mean_cm'][selection].mean()):.2f}</td>"
            f"<td>{float(b['map_err_inrange_mean_cm'][selection].mean()):.2f}</td></tr>"
        )
    assert expected in table
    assert render().index("X27n 본 측정 완료") < render().index("앞선 예행 두 차례")
