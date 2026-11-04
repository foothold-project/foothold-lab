"""Known pixel identities distinguish robot geometry from white obstacles."""
from __future__ import annotations

import numpy as np
import pytest

from foothold_s2.eval.c_layer_segmentation import (
    ensure_only_selected_visible, packet_diagnostic, robot_pixel_evidence,
    require_single_visible_robot,
)


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


def test_failed_gpu_packet_diagnostic_distinguishes_missing_label_from_missing_pixels():
    with_label = packet(0)
    row = packet_diagnostic(with_label, selected_env=0)
    assert row["selected_label_count"] == 1 and row["mask_unique_ids"] == 1
    no_label = {"data": with_label["data"], "info": {"idToLabels": {
        "99": "/World/ground/terrain/mesh"}}}
    row = packet_diagnostic(no_label, selected_env=0)
    assert row["selected_label_count"] == 0 and row["robot_label_count"] == 0


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
    assert evidence["selected_robot_bbox_xyxy"] == [0, 0, 10, 9]


class FakePrim:
    def __init__(self, visibility="invisible", valid=True):
        self.visibility = visibility
        self.valid = valid

    def IsValid(self):
        return self.valid


class FakeStage:
    def __init__(self, prims):
        self.prims = prims

    def GetPrimAtPath(self, path):
        return self.prims.get(path, FakePrim(valid=False))


class FakeImageable:
    def __init__(self, prim):
        self.prim = prim

    def ComputeVisibility(self):
        return self.prim.visibility

    def MakeVisible(self):
        self.prim.visibility = "inherited"


def test_nonzero_selected_robot_is_restored_while_other_clones_stay_hidden():
    roots = {f"/World/envs/env_{env}/Robot": FakePrim() for env in range(64)}
    stage = FakeStage(roots)
    selected = "/World/envs/env_12/Robot"
    hidden = [path for path in roots if path != selected]
    result = ensure_only_selected_visible(stage, selected, hidden, FakeImageable)
    assert result["selected_visibility_before"] == "invisible"
    assert result["selected_visibility_after"] == "inherited"
    assert result["hidden_robot_count"] == 63
    assert all(roots[path].visibility == "invisible" for path in hidden)


def test_visibility_contract_rejects_missing_subject_or_visible_sibling():
    selected = "/World/envs/env_12/Robot"
    other = "/World/envs/env_13/Robot"
    with pytest.raises(ValueError, match="selected robot prim is missing"):
        ensure_only_selected_visible(FakeStage({other: FakePrim()}), selected, [other], FakeImageable)
    with pytest.raises(ValueError, match="another robot became visible"):
        ensure_only_selected_visible(FakeStage({selected: FakePrim(), other: FakePrim("inherited")}),
                                     selected, [other], FakeImageable)
