"""G18 known-input overlay contract without Kit or video encoding."""

import json

import numpy as np
import pytest

from foothold_s2.eval.video25.push_event_overlay import draw_push_overlay, load_overlay
from foothold_s2.eval.video25 import compose_25e_v2style10 as composer


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


def test_world_xy_direction_magnitude_and_time(tmp_path):
    event = load_overlay(fixture(tmp_path), "a" * 64, "forward", 7)
    assert event["events"] == [{"t_s": 2.0, "dx": 0.0, "dy": 2.0,
                                 "magnitude_mps": 2.0}]
    before = np.zeros((720, 1280, 3), np.uint8)
    bounds = {"panel_x0": composer.GAUGE_X0, "panel_x1": composer.GAUGE_X1}
    assert np.array_equal(draw_push_overlay(before.copy(), event, 1.99, **bounds), before)
    during = draw_push_overlay(before.copy(), event, 2.5, **bounds)
    assert during[45:191, composer.GAUGE_X0:composer.GAUGE_X1].sum() > 0
    after = draw_push_overlay(before.copy(), event, 4.0, **bounds)
    assert not np.array_equal(after, during)


def test_push_box_pixel_edges_equal_terrain_speed_panel_and_mutation_is_caught(tmp_path):
    event = load_overlay(fixture(tmp_path), "a" * 64, "forward", 7)
    blank = np.zeros((720, 1280, 3), np.uint8)
    speed_panel = composer.speed_tag(blank.copy(), "1x", "seq")
    speed_pixels = np.flatnonzero(speed_panel[700].any(axis=1))
    expected_edges = (int(speed_pixels.min()), int(speed_pixels.max()) + 1)
    assert expected_edges == (composer.GAUGE_X0, composer.GAUGE_X1)

    def check_edges(left, right):
        frame = draw_push_overlay(blank.copy(), event, 2.5, panel_x0=left, panel_x1=right)
        pixels = np.flatnonzero(frame[50].any(axis=1))
        assert (int(pixels.min()), int(pixels.max()) + 1) == expected_edges
        assert not frame[45:191, :composer.GAUGE_X0].any()
        assert not frame[45:191, composer.GAUGE_X1:].any()

    check_edges(composer.GAUGE_X0, composer.GAUGE_X1)
    with pytest.raises(AssertionError):
        check_edges(composer.GAUGE_X0 - 5, composer.GAUGE_X1)


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
