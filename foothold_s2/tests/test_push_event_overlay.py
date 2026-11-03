"""G18 known-input overlay contract without Kit or video encoding."""

import json
import hashlib
from pathlib import Path

import numpy as np
import pytest
import cv2

from foothold_s2.eval.video25.push_event_overlay import (
    active_push_event, box_arrow_points, draw_push_overlay, draw_push_scene_arrow,
    load_overlay, push_arrow_geometry,
)
from foothold_s2.eval.video25 import compose_25e_v2style10 as composer
from foothold_s2.eval.video25 import push_event_overlay as push_overlay_module
from foothold_s2.eval.video25.record_c_layer import follow_camera_pose
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, composer_version, require_video_rule


def fixture(tmp_path):
    path = tmp_path / "push.json"
    path.write_text(json.dumps({
        "capture_receipt_sha256": "a" * 64,
        "dr": {"readback": {"forward": {
            "push_events": [{"t_s": 2.0, "env_ids": [0, 7],
                             "dv_xyz_w_mps": [[.1, 0, 0], [0, 2, 0]]}],
            "recovery": {"recovery_time_s_median": 1.5},
        }}}}), encoding="utf-8")
    return path


def legend_geometry():
    start, tip = box_arrow_points(composer.LEGEND_RECT, (2, -1))
    return {"box_start": start, "box_tip": tip}


def test_world_xy_direction_magnitude_and_time(tmp_path):
    event = load_overlay(fixture(tmp_path), "a" * 64, "forward", 7)
    assert event["events"] == [{"t_s": 2.0, "dx": 0.0, "dy": 2.0,
                                 "magnitude_mps": 2.0}]
    before = np.zeros((720, 1280, 3), np.uint8)
    bounds = {"legend_rect": composer.LEGEND_RECT}
    assert np.array_equal(draw_push_overlay(before.copy(), event, 1.99, **bounds), before)
    during = draw_push_overlay(before.copy(), event, 2.5, **bounds,
                               geometry=legend_geometry())
    x0, y0, width, height = composer.LEGEND_RECT
    assert during[y0:y0 + height, x0:x0 + width].sum() > 0
    after = draw_push_overlay(before.copy(), event, 4.0, **bounds)
    assert np.array_equal(after, before)
    assert active_push_event(event, 3.5) is not None
    assert active_push_event(event, 3.51) is None


def test_missing_recovery_uses_one_point_five_seconds(tmp_path):
    path = fixture(tmp_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    del doc["dr"]["readback"]["forward"]["recovery"]
    path.write_text(json.dumps(doc), encoding="utf-8")
    event = load_overlay(path, "a" * 64, "forward", 7)
    assert active_push_event(event, 3.5) is not None
    assert active_push_event(event, 3.51) is None


def test_push_box_pixel_edges_equal_terrain_speed_panel_and_mutation_is_caught(tmp_path, monkeypatch):
    event = load_overlay(fixture(tmp_path), "a" * 64, "forward", 7)
    blank = np.zeros((720, 1280, 3), np.uint8)
    speed_panel = composer.speed_tag(blank.copy(), "1x", "seq")
    speed_pixels = np.flatnonzero(speed_panel[700].any(axis=1))
    expected_edges = (int(speed_pixels.min()), int(speed_pixels.max()) + 1)
    assert expected_edges == (composer.GAUGE_X0, composer.GAUGE_X1)

    def check_rect(rect):
        frame = draw_push_overlay(blank.copy(), event, 2.5, legend_rect=rect,
                                  geometry=legend_geometry())
        x0, y0, width, height = rect
        pixels = np.argwhere(frame.any(axis=2))
        assert (int(pixels[:, 1].min()), int(pixels[:, 0].min()),
                int(pixels[:, 1].max()) + 1, int(pixels[:, 0].max()) + 1) == (
                    expected_edges[0], composer.LEGEND_RECT[1],
                    expected_edges[1], composer.GAUGE_Y0 - 8)
        return frame

    legend = composer.scene_legend(blank.copy(), {"overlay_25e": {}})
    lx, ly, lw, lh = composer.LEGEND_RECT
    legend_pixels = np.argwhere(legend.any(axis=2))
    assert (int(legend_pixels[:, 1].min()), int(legend_pixels[:, 0].min()),
            int(legend_pixels[:, 1].max()) + 1, int(legend_pixels[:, 0].max()) + 1) == (
                lx, ly, lx + lw, ly + lh)
    assert (lx, lx + lw) == expected_edges
    assert ly + lh + 8 == composer.GAUGE_Y0
    frame = check_rect(composer.LEGEND_RECT)
    start, tip = box_arrow_points(composer.LEGEND_RECT, (2, -1))
    assert ((start[0] + tip[0]) / 2, (start[1] + tip[1]) / 2) == (
        lx + lw // 2, ly + lh // 2)
    arrow = np.argwhere((frame[:, :, 0] < 100) & (frame[:, :, 1] > 150) & (frame[:, :, 2] > 180))
    white = (frame[:, :, 0] > 180) & (frame[:, :, 1] > 180) & (frame[:, :, 2] > 180)
    upper = np.argwhere(white[:ly + 50])
    lower = np.argwhere(white[ly + 110:ly + lh])
    assert len(arrow) and len(upper) and len(lower)
    arrow_y = (int(arrow[:, 0].min()), int(arrow[:, 0].max()) + 1)
    upper_y = (int(upper[:, 0].min()), int(upper[:, 0].max()) + 1)
    lower_y = (int(lower[:, 0].min()) + ly + 110, int(lower[:, 0].max()) + ly + 111)
    def separated(arrow_bounds):
        return upper_y[1] <= arrow_bounds[0] and arrow_bounds[1] <= lower_y[0]

    assert separated(arrow_y)

    with pytest.raises(AssertionError):
        check_rect((lx - 5, ly, lw + 5, lh))
    original_arrow = cv2.arrowedLine

    def arrow_into_footer(image, start, tip, color, thickness, line_type, *, tipLength):
        return original_arrow(image, start, (tip[0], lower_y[0] + 8),
                              color, thickness, line_type, tipLength=tipLength)

    monkeypatch.setattr(push_overlay_module.cv2, "arrowedLine", arrow_into_footer)
    mutated = draw_push_overlay(blank.copy(), event, 2.5, legend_rect=composer.LEGEND_RECT,
                                geometry=legend_geometry())
    mutated_arrow = np.argwhere((mutated[:, :, 0] < 100) & (mutated[:, :, 1] > 150)
                                & (mutated[:, :, 2] > 180))
    assert not separated((int(mutated_arrow[:, 0].min()), int(mutated_arrow[:, 0].max()) + 1))


@pytest.mark.parametrize("mode,scan_visible", [("eval_gt", True), ("eval_pred", False),
                                               ("probe_prop_only", False)])
def test_legend_fixed_bounds_in_all_map_modes(mode, scan_visible):
    blank = np.zeros((720, 1280, 3), np.uint8)
    before = list(composer.OVERFLOW)
    image = composer.scene_legend(blank, {"map_modes": {"map_mode": {"requested": mode}},
                                           "overlay_25e": {"scene_foot_scan_visible": scan_visible}})
    x0, y0, width, height = composer.LEGEND_RECT
    assert image[y0:y0 + height, x0:x0 + width].any()
    assert not image[y0:y0 + height, :x0].any()
    assert not image[y0:y0 + height, x0 + width:].any()
    assert before == composer.OVERFLOW


def test_v34_receipt_accepts_current_composer_and_rejects_old_rule():
    source = Path(composer.__file__)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert composer_version(source) == VIDEO_RULE_VERSION == "v3.4-D168"
    require_video_rule({"video_rule_version": VIDEO_RULE_VERSION,
                        "composer_sha256": digest}, composer_sha256=digest)
    with pytest.raises(ValueError, match="video_rule_hold"):
        require_video_rule({"video_rule_version": "v3.3-D167",
                            "composer_sha256": digest}, composer_sha256=digest)


def test_world_push_arrow_uses_recorded_camera_only_inside_recovery(tmp_path):
    event = load_overlay(fixture(tmp_path), "a" * 64, "forward", 7)
    root = np.array([-37.975643, -86.700874, 0.579598])
    eye, target = follow_camera_pose(root, push_video=True)
    camera = {"camera_eye_w": eye, "camera_target_w": target,
              "focal_length_mm": 18.147562, "horizontal_aperture_mm": 20.955}
    blank = np.zeros((720, 1280, 3), np.uint8)
    geometry = push_arrow_geometry(event["events"][0], root, [1, 0, 0, 0], camera,
                                   scene_width=1280, scene_height=720,
                                   legend_rect=composer.LEGEND_RECT)
    assert geometry["length_m"] == .5
    assert geometry["angle_diff_deg"] < 10
    assert geometry["body_start_ok"]
    assert geometry["screen_width_fraction"] <= .15
    during = draw_push_scene_arrow(blank.copy(), geometry, flash=True)
    red = (during[:, :, 2] > 190) & (during[:, :, 1] < 110) & (during[:, :, 0] < 110)
    assert red.sum() > 50
    sx, sy = geometry["scene_start"]
    assert red[max(0, sy-12):sy+13, max(0, sx-12):sx+13].sum() > 0
    with pytest.raises(ValueError, match="camera pose"):
        push_arrow_geometry(event["events"][0], root, [1, 0, 0, 0], None,
                            scene_width=1280, scene_height=720,
                            legend_rect=composer.LEGEND_RECT)


def test_arrow_wrong_direction_and_oversize_fail_closed(monkeypatch):
    root = np.array([-37.975643, -86.700874, 0.579598])
    eye, target = follow_camera_pose(root, push_video=True)
    camera = {"camera_eye_w": eye, "camera_target_w": target,
              "focal_length_mm": 18.147562, "horizontal_aperture_mm": 20.955}
    event = {"t_s": 2.0, "dx": 2.0, "dy": 0.0}
    original = push_overlay_module.box_arrow_points
    def reversed_box(rect, delta):
        start, tip = original(rect, delta)
        return tip, start
    monkeypatch.setattr(push_overlay_module, "box_arrow_points", reversed_box)
    with pytest.raises(ValueError, match="geometry FAIL"):
        push_arrow_geometry(event, root, [1, 0, 0, 0], camera,
                            scene_width=1280, scene_height=720,
                            legend_rect=composer.LEGEND_RECT)
    monkeypatch.setattr(push_overlay_module, "box_arrow_points", original)
    old_eye, old_target = follow_camera_pose(root, push_video=False)
    camera["camera_eye_w"], camera["camera_target_w"] = old_eye, old_target
    with pytest.raises(ValueError, match="geometry FAIL"):
        push_arrow_geometry(event, root, [1, 0, 0, 0], camera,
                            scene_width=1280, scene_height=720,
                            legend_rect=composer.LEGEND_RECT)


@pytest.mark.parametrize("sha,key,env", [("b" * 64, "forward", 7),
                                        ("a" * 64, "missing", 7),
                                        ("a" * 64, "forward", 8)])
def test_reject_unbound_event(tmp_path, sha, key, env):
    with pytest.raises(ValueError):
        load_overlay(fixture(tmp_path), sha, key, env)


def test_missing_recovery_does_not_claim_recovered(tmp_path):
    path = fixture(tmp_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    del doc["dr"]["readback"]["forward"]["recovery"]
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load_overlay(path, "a" * 64, "forward", 7)["recovery_time_s_median"] is None
