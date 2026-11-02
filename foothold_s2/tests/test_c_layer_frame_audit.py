"""Known-frame counterexamples for C-layer full video inspection."""

import numpy as np

from foothold_s2.eval.c_layer_frame_audit import inspect_frames


def frame():
    rng = np.random.default_rng(13)
    image = rng.integers(55, 135, size=(72, 128, 3), dtype=np.uint8)
    image[23:50, 44:69] = (190, 190, 190)
    return image


def test_good_sequence_and_each_frame_problem():
    original = frame()
    good = [np.roll(original, index % 4, axis=1) for index in range(30)]
    assert inspect_frames(good, expected=30, width=128, height=72)["pass"]
    for bad in (np.zeros_like(original), np.full_like(original, 80),
                np.full_like(original, 90)):
        frames = list(good)
        frames[12] = bad
        assert not inspect_frames(frames, expected=30, width=128, height=72)["pass"]
    offscreen = list(good)
    offscreen[12] = original.copy()
    offscreen[12][23:50, 44:69] = (90, 90, 90)
    assert "robot_out_of_view_proxy" in str(inspect_frames(
        offscreen, expected=30, width=128, height=72)["issues"])


def test_wrong_shape_short_decode_and_frozen_frames():
    original = frame()
    assert not inspect_frames([original] * 30, expected=30, width=128, height=72)["pass"]
    assert not inspect_frames([original], expected=30, width=128, height=72)["pass"]
    assert not inspect_frames([original[:, :-1]], expected=1, width=128, height=72)["pass"]


def test_styled_dark_map_panel_is_rejected_even_with_visible_scene():
    image = np.tile(frame(), (15, 15, 1))
    image[30:710, 1280:1900] = 0
    report = inspect_frames([image], expected=1, width=1920, height=1080)
    assert "dark_map_panel" in str(report["issues"])
