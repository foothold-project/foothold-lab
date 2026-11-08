from __future__ import annotations

import numpy as np
import pytest

from foothold_s2.eval.c_layer_outcome import classify_arrays, foot_contact_and_force
from foothold_s2.eval.video_style import check_video_name, video_name


def _trajectory(local_x: list[float], level: int = 2) -> np.ndarray:
    world = np.zeros((len(local_x), 3), dtype=np.float32)
    world[:, 0] = np.asarray(local_x) + level * 8 - 40
    return world


@pytest.mark.parametrize(
    ("path", "done", "expected"),
    [([0.0, 6.9, 7.0, 7.2], [0, 0, 0, 0], "cross"),
     ([0.0, 5.0, 6.99, 6.8], [0, 0, 0, 0], "survive"),
     ([0.0, 7.1, 7.2, 7.3], [0, 0, 1, 0], "fall"),
     ([0.0, 2.0, 7.3, 7.5], [0, 1, 0, 0], "fall")],
)
def test_three_outcomes_first_episode_and_termination(path, done, expected):
    result = classify_arrays(_trajectory(path), np.asarray(done, bool),
                             np.zeros(len(done), bool), level=2)
    assert result["outcome"] == expected
    assert result["reached_first_tile_x7"] == (max(path[:done.index(1) + 1] if 1 in done else path) >= 7)


def test_timeout_cannot_be_called_a_fall():
    with pytest.raises(ValueError, match="timeout reset"):
        classify_arrays(_trajectory([0, 8]), np.array([0, 1], bool),
                        np.array([0, 1], bool), level=2)


def test_foot_force_preserves_vector_and_contact_threshold():
    force = np.array([[1.0, 0, 0], [1.0, 1.0, 0], [0, 0, -2.0], [0, 0, 0]], np.float32)
    stored, contact = foot_contact_and_force(force)
    np.testing.assert_array_equal(stored, force)
    np.testing.assert_array_equal(contact, [False, True, True, False])
    force[1] = 0
    assert stored[1, 0] == 1.0
    with pytest.raises(ValueError, match="four finite"):
        foot_contact_and_force(np.full((4, 3), np.nan))


@pytest.mark.parametrize("result", ["cross", "survive", "fall"])
def test_new_video_suffix_and_old_suffix_remain_valid(result):
    name = video_name("EX41", "gaps", 0, 6000, result, segment="eval_gt")
    assert name.endswith("-" + result)
    assert check_video_name(name) == name
    assert check_video_name("EX41-gaps_L0-m6000-eval_gt-1x-success")
