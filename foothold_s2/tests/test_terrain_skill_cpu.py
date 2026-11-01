"""W78 terrain skill suite: CPU checks of the pure helpers (Kit is not imported)."""
import numpy as np
import pytest

pytest.importorskip("torch")
from foothold_s2.eval import terrain_skill_run as ts


def test_case_steps_and_cases_cover_requested_skills():
    assert ts.case_steps([((0.5, 0, 0), 4.0), ((0, 0, 1.2), 2.6)], 0.02) == [200, 130]
    with pytest.raises(ValueError):
        ts.case_steps([((0, 0, 0), 0.001)], 0.02)
    assert {"stairs_side_left", "stairs_side_right", "stairs_back", "stairs_fwd_turn_return",
            "stairs_fwd_back_return", "slope_fwd1.0"} <= set(ts.CASES)


def test_env_rows_phase_height_and_fall():
    steps = [2, 2]
    z0 = np.array([0.3, 0.3])
    z = np.array([[0.4, 0.3], [0.5, 0.2], [0.45, 0.1], [0.3, 0.1]])
    xy = np.zeros((4, 2, 2)); xy[:, 0, 0] = [1, 2, 2.5, 1]
    valid = np.array([[1, 1], [1, 1], [1, 0], [1, 0]], dtype=bool)        # env 1 falls after step 1
    rows = ts.env_rows([{"kind": "a"}, {"kind": "b"}], z0, z, xy, valid, steps)
    assert rows[0]["alive_end"] and abs(rows[0]["phases"][0]["dz_m"] - 0.2) < 1e-9
    assert abs(rows[0]["phases"][1]["dz_m"] - 0.0) < 1e-9 and rows[0]["phases"][1]["radius_m"] == 1
    assert not rows[1]["alive_end"] and rows[1]["phases"][1]["alive"] is False
    assert abs(rows[1]["phases"][1]["dz_m"] - (-0.1)) < 1e-9                   # last valid sample, not post-reset
