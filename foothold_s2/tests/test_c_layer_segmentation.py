"""Known pixel identities distinguish robot geometry from white obstacles."""
from __future__ import annotations

import numpy as np
import pytest

from foothold_s2.eval.c_layer_segmentation import robot_pixel_evidence, require_single_visible_robot


def packet(subject_pixels: int, other_pixels: int = 0):
    mask = np.zeros((20, 30), dtype=np.int32)
    mask.flat[:subject_pixels] = 17
    mask.flat[subject_pixels:subject_pixels + other_pixels] = 23
    return {"data": mask, "info": {"idToLabels": {
        "17": "/World/envs/env_0/Robot/base",
        "23": "/World/envs/env_1/Robot/base",
        "99": "/World/white_obstruction"}}}


def test_white_obstruction_cannot_replace_robot_instance():
    evidence = robot_pixel_evidence(packet(0), selected_env=0, env_count=2,
                                    height=20, width=30)
    with pytest.raises(ValueError, match="missing subject"):
        require_single_visible_robot(evidence)


def test_other_robot_is_detected_and_subject_alone_passes():
    mixed = robot_pixel_evidence(packet(100, 90), selected_env=0, env_count=2,
                                 height=20, width=30)
    assert mixed["other_robot_pixels"] == 90
    with pytest.raises(ValueError, match="another robot"):
        require_single_visible_robot(mixed)
    single = robot_pixel_evidence(packet(100), selected_env=0, env_count=2,
                                  height=20, width=30)
    require_single_visible_robot(single)


def test_missing_identity_map_is_hold():
    with pytest.raises(ValueError, match="idToLabels"):
        robot_pixel_evidence({"data": np.ones((20, 30), dtype=np.int32), "info": {}},
                             selected_env=0, env_count=2, height=20, width=30)


def test_fixed64_counts_selected_and_hidden_ids_in_one_frame():
    labels = {str(env + 100): f"/World/envs/env_{env}/Robot/base" for env in range(64)}
    pixels = np.zeros((10, 10), dtype=np.int32)
    pixels.flat[:81] = 123
    pixels.flat[81] = 124
    evidence = robot_pixel_evidence(
        {"data": pixels, "info": {"idToLabels": labels}},
        selected_env=23, env_count=64, height=10, width=10,
    )
    assert evidence["selected_robot_pixels"] == 81
    assert evidence["other_robot_pixels"] == 1
