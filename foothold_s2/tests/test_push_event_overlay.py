"""G18 known-input overlay contract without Kit or video encoding."""

import json

import numpy as np
import pytest

from foothold_s2.eval.video25.push_event_overlay import draw_push_overlay, load_overlay


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
    assert np.array_equal(draw_push_overlay(before.copy(), event, 1.99), before)
    during = draw_push_overlay(before.copy(), event, 2.5)
    assert during[42:193, 1010:1275].sum() > 0
    after = draw_push_overlay(before.copy(), event, 4.0)
    assert not np.array_equal(after, during)


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
