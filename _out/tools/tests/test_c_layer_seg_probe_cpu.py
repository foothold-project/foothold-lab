"""Known-input checks for bounded segmentation diagnosis without Kit."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import c_layer_seg_probe as probe  # noqa: E402
import prepare_c_layer_seg_probe as prepare  # noqa: E402


def _recognize(packet):
    ids = packet["info"]["idToLabels"]
    if not any("/env_5/Robot" in str(value) for value in ids.values()):
        raise ValueError("C76 selected robot instance IDs missing")
    return {"selected_robot_pixels": 100}


def test_render_only_retry_recovers_and_preserves_state():
    packets = iter([{"info": {"idToLabels": {"1": "/World/envs/env_0/Robot"}}},
                    {"info": {"idToLabels": {"5": "/World/envs/env_5/Robot"}}}])
    renders = []
    def render():
        renders.append(True)
        return np.full((4, 4, 3), 42, dtype=np.uint8)
    row, frame, checks, failed, reason = probe.recognize_after_render(
        lambda: next(packets), _recognize, render, lambda: {"step": 0},
        np.zeros((4, 4, 3), dtype=np.uint8), max_retries=2)
    assert row["selected_robot_pixels"] == 100 and frame.mean() == 42
    assert len(renders) == len(checks) == 1 and checks[0]["state_unchanged"]
    assert failed is None and reason is None


def test_retry_fails_if_physics_changes():
    state = iter([{"step": 0}, {"step": 1}])
    packet = {"info": {"idToLabels": {"1": "/World/envs/env_0/Robot"}}}
    with pytest.raises(RuntimeError, match="changed simulation state"):
        probe.recognize_after_render(lambda: packet, _recognize,
                                    lambda: np.zeros((2, 2, 3), dtype=np.uint8),
                                    lambda: next(state), np.zeros((2, 2, 3), dtype=np.uint8))


def test_exhausted_retry_writes_visible_label_and_rgb(tmp_path):
    packet = {"info": {"idToLabels": {"1": "/World/envs/env_0/Robot",
                                      "5": "/World/envs/env_5/Robot"}},
              "data": np.array([[1, 1], [1, 1]], dtype=np.uint32)}
    def missing(_packet):
        raise ValueError("C76 selected robot instance IDs missing")
    row, frame, checks, failed, reason = probe.recognize_after_render(
        lambda: packet, missing, lambda: np.full((2, 2, 3), 42, dtype=np.uint8),
        lambda: {"step": 0}, np.zeros((2, 2, 3), dtype=np.uint8), max_retries=1)
    assert row is None and len(checks) == 1
    target = probe.write_failure(tmp_path, packet=failed, frame=frame, selected_env=5,
                                 selected_root="/World/envs/env_5/Robot", root_visibility="inherited",
                                 camera={"root_in_frame": True}, checks=checks, reason=reason)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["selected_labels"] == {"5": "/World/envs/env_5/Robot"}
    assert data["robot_labels_with_pixels"] == {"1": "/World/envs/env_0/Robot"}
    assert data["rgb_mean"] == 42 and (tmp_path / "segmentation_failure_rgb.png").is_file()


def test_diagnostic_plan_preserves_frozen_source_and_queue(tmp_path):
    frozen = Path("D:/mai-wt/foothold-lab/c-layer-run-5027e4ad")
    base = Path("D:/mai-tmp/c_layer_m6000_phase1_shards_hold3/phase1_gpu1.json")
    result = prepare.build(frozen, base, tmp_path / "source", tmp_path / "out",
                           "pyramid_stairs_inv_L0_eval_gt")
    plan = json.loads(Path(result["plan"]).read_text(encoding="utf-8"))
    assert plan["queue_sha256"] == json.loads(base.read_text())["queue_sha256"]
    assert plan["checkpoint_sha256"] == json.loads(base.read_text())["checkpoint_sha256"]
    assert plan["recorder_sha256"] == prepare.digest(Path(result["recorder"]))
    spec = importlib.util.spec_from_file_location("frozen_queue", plan["queue"])
    queue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(queue)
    assert queue.validate_plan(plan)["ready"] == 216
