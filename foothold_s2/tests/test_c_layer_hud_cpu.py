"""Known-input C76 HUD measurements and map-off visual contract."""

import math

import numpy as np

from foothold_s2.eval.video25 import compose_25e_v2style10 as hud


def _quat(yaw):
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


def test_heading_lateral_drift_uses_current_episode_start():
    yaw = math.pi / 2
    rows = {
        "root_quat_w": np.asarray([_quat(yaw), _quat(yaw + math.pi / 6),
                                     _quat(0), _quat(-math.pi / 3)]),
        "root_pos_w": np.asarray([[0, 0, 0], [1, 0, 0],
                                   [10, 10, 0], [10, 11, 0]], dtype=float),
        "done": np.asarray([False, True, False, False]),
        "time_out": np.asarray([False, False, False, False]),
    }
    h1, d1 = hud.heading_lateral_at(rows, 1)
    h3, d3 = hud.heading_lateral_at(rows, 3)
    assert math.isclose(h1, 30.0, abs_tol=1e-6)
    assert math.isclose(d1, -1.0, abs_tol=1e-6)
    assert math.isclose(h3, -60.0, abs_tol=1e-6)
    assert math.isclose(d3, 1.0, abs_tol=1e-6)


def test_unused_map_tile_is_grey_but_used_map_keeps_colour():
    grid = np.linspace(-1, 1, 512, dtype=np.float32).reshape(32, 16)
    active = hud.map_tile(grid, True, cell=2)
    unused = hud.map_tile(grid, False, cell=2)
    assert np.any(active[:, :, 0] != active[:, :, 1])
    assert np.array_equal(unused[:, :, 0], unused[:, :, 1])
    assert np.array_equal(unused[:, :, 1], unused[:, :, 2])


def test_eval_gt_panel_really_greys_unused_reconstruction():
    grid = np.linspace(-1, 1, 512, dtype=np.float32).reshape(32, 16)
    z = {
        "gt_map": np.stack([grid, grid]), "refined_map": np.stack([grid, grid]),
        "map_use_gt": np.asarray([True, True]), "t": np.asarray([0.0, 0.02]),
        "root_pos_w": np.zeros((2, 3), dtype=np.float32),
        "root_quat_w": np.asarray([_quat(0), _quat(0)]),
        "foot_pos_w": np.full((2, 4, 3), 100.0, dtype=np.float32),
        "foot_contact": np.zeros((2, 4), dtype=bool),
    }
    meta = {"map_modes": {"map_mode": {"requested": "eval_gt"}}}
    panel = hud.draw_map_panel(z, meta, 0, None, np.asarray([0.0, 0.0]))
    gt = panel[120, 50]
    unused = panel[120, 250]
    assert not (gt[0] == gt[1] == gt[2])
    assert unused[0] == unused[1] == unused[2]
