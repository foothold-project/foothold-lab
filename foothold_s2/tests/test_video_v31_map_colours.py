"""D139 keeps both comparison maps in v2 colour and mutes only policy input."""
from __future__ import annotations

import numpy as np

from foothold_s2.eval.video25 import compose_25e_v2style10 as compose


def test_gt_and_reconstruction_keep_colour_when_policy_uses_prediction():
    gt = np.linspace(-0.2, 0.2, 512, dtype=np.float32).reshape(1, 512)
    pred = gt + 0.03
    z = {
        "t": np.array([0.0], dtype=np.float32),
        "gt_map": gt,
        "refined_map": pred,
        "map_use_gt": np.array([False]),
        "root_pos_w": np.zeros((1, 3), dtype=np.float32),
        "root_quat_w": np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
        "foot_pos_w": np.full((1, 4, 3), 99.0, dtype=np.float32),
        "foot_contact": np.zeros((1, 4), dtype=bool),
    }
    panel = compose.draw_map_panel(
        z, {"map_modes": {"map_mode": {"requested": "eval_pred"}}},
        0, np.zeros(128, dtype=np.float32),
    )
    centre = float(np.median(gt))
    span = max(float(np.percentile(np.abs(gt - centre), 95)), compose.MAP_MIN_SPAN_M)
    x0, x1, x2 = (compose.map_tile_x(x, 11) for x in compose.MAP_TILE_XS)
    y = compose.MAP_TILE_Y
    assert np.array_equal(panel[y + 30, x0 + 30],
                          compose.map_tile(gt[0], True, 11, (centre, span))[30, 30])
    assert np.array_equal(panel[y + 30, x1 + 30],
                          compose.map_tile(pred[0], True, 11, (centre, span))[30, 30])
    muted = compose.map_tile(pred[0], False, 11, (centre, span))
    expected_policy = compose.attention_heatmap_tile(np.zeros(128), muted, 11)
    assert np.array_equal(panel[y + 30, x2 + 30], expected_policy[30, 30])
    assert compose.VIDEO_RULE_VERSION == "v3.1-D137"


def test_legacy_scene_keeps_foot_scan_legend_but_new_recording_does_not():
    scene = np.full((720, 1280, 3), 100, dtype=np.uint8)
    old = compose.scene_legend(scene.copy(), {"overlay_25e": {}})
    new = compose.scene_legend(
        scene.copy(), {"overlay_25e": {"scene_foot_scan_visible": False}}
    )
    assert np.any(old[180:185, 1020:1272] != new[180:185, 1020:1272])
