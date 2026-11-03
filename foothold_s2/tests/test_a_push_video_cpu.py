from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import a_push_video as video
from foothold_s2.eval.video25 import compose_25e_v2style10 as composer
from foothold_s2.eval.video25 import record_c_layer as recorder


def args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(kind="pyramid_stairs", level=0, col=0, env_id=0,
                              seed=42, push_seed=42, iteration=10, cadence="stage_end",
                              python=Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"),
                              recorder=tmp_path / "record_c_layer.py", checkpoint=tmp_path / "model_10.pt",
                              composer=tmp_path / "compose.py", device="cuda:1")


def source(tmp_path: Path) -> dict:
    return {"source_root": str(tmp_path), "source_head": "a" * 40,
            "source_recorder_sha256": "b" * 64, "checkpoint_sha256": "c" * 64,
            "capture_recorder_sha256": "d" * 64, "composer_sha256": "e" * 64}


def test_a_push_heading_label_leaves_top_blue_arrow_visible(monkeypatch):
    monkeypatch.setattr(composer, "heading_lateral_at", lambda z, row: (0.0, 0.0))
    scene = np.full((720, 1280, 3), 120, dtype=np.uint8)
    scene[40:55, 350:400] = (240, 30, 20)  # blue velocity arrow in BGR
    z = {"command": np.array([[1.0, 0.0, 0.0]]), "t": np.array([0.0]),
         "vx": np.array([1.0]), "wz": np.array([0.0])}
    meta = {"label": "a push", "scene": "rough", "map_modes": {"map_mode": {"requested": "eval_pred"}}}
    push = composer.receipt_header(scene.copy(), meta, z, 0, push_video=True)
    regular = composer.receipt_header(scene.copy(), meta, z, 0, push_video=False)
    assert tuple(push[50, 380]) == (240, 30, 20)
    assert tuple(regular[50, 380]) == (20, 24, 29)


def test_three_modes_share_tile_seed_push_and_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(video.shared, "parent_sha", lambda root: "f" * 64)
    rows = {mode: video.policy_spec(args(tmp_path), mode, source(tmp_path)) for mode in video.MODES}
    assert {row["map_mode"] for row in rows.values()} == set(video.MODES)
    assert len({row["push_group_id"] for row in rows.values()}) == 1
    assert len({row["seed"] for row in rows.values()}) == 1
    assert len({row["push_seed"] for row in rows.values()}) == 1
    assert all(row["a_push_video_reference"] and row["dr_scale"] == 1.0 for row in rows.values())
    changed = args(tmp_path)
    changed.push_seed = 43
    assert video.policy_spec(changed, "eval_gt", source(tmp_path))["push_group_id"] != rows["eval_gt"]["push_group_id"]


def test_capture_parser_rejects_missing_mode_and_wrong_ex41_source(tmp_path, monkeypatch):
    monkeypatch.setattr(video.shared, "parent_sha", lambda root: "f" * 64)
    row = video.policy_spec(args(tmp_path), "eval_pred", source(tmp_path))
    monkeypatch.setattr(recorder, "_git_value", lambda *a: "a" * 40)
    monkeypatch.setattr(recorder, "_sha", lambda *a: "b" * 64)
    assert recorder.parse_spec(json.dumps(row))["map_mode"] == "eval_pred"
    row["map_mode"] = "missing"
    with pytest.raises(ValueError, match="map mode"):
        recorder.parse_spec(json.dumps(row))
    row["map_mode"] = "eval_gt"
    row["source_head"] = "0" * 40
    with pytest.raises(ValueError, match="source HEAD"):
        recorder.parse_spec(json.dumps(row))


def test_dr_on_preserves_startup_and_delay_vs_off():
    class Holder:
        pass
    def cfg():
        row = Holder()
        row.scene = Holder()
        row.scene.num_envs = 64
        row.scene.terrain = Holder()
        row.events = Holder()
        row.actions = Holder()
        row.actions.joint_pos = Holder()
        row.actions.joint_pos.max_delay_s = 0.015
        row.events.physics_material = object()
        row.events.add_base_mass = object()
        row.curriculum = Holder()
        row.curriculum.terrain_levels = object()
        row.curriculum.command_range = object()
        row.commands = Holder()
        row.commands.base_velocity = Holder()
        return row
    on, off = cfg(), cfg()
    recorder.configure_sparse_evaluation_config(on, None, preserve_dr=True)
    recorder.configure_sparse_evaluation_config(off, None)
    assert on.events.physics_material is not None and on.events.add_base_mass is not None
    assert on.actions.joint_pos.max_delay_s == 0.015
    assert off.events.physics_material is None and off.events.add_base_mass is None
    assert off.actions.joint_pos.max_delay_s == 0.0


def test_three_receipts_reject_changed_push_and_missing_video(tmp_path):
    for mode in video.MODES:
        path = tmp_path / f"{mode}.mp4"
        path.write_bytes(mode.encode())
        row = {"map_mode": mode, "video": str(path), "video_sha256": video.sha256(path),
               "group_id": "g", "source_head": "s", "checkpoint_sha256": "c", "iteration": 10,
               "kind": "pyramid_stairs", "level": 0, "col": 0, "env_id": 0,
               "seed": 42, "push_seed": 42,
               "push_signature": ["g", 42, 100, 999, [[0.3, 0.1, 0.0]] * 64]}
        (tmp_path / f"{mode}.json").write_text(json.dumps(row), encoding="utf-8")
    assert video.compare_mode_receipts(tmp_path)["state"] == "complete"
    changed = tmp_path / "eval_pred.json"
    row = json.loads(changed.read_text())
    row["push_signature"][4][0][0] = 0.4
    changed.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="actual push"):
        video.compare_mode_receipts(tmp_path)
    row["push_signature"][4][0][0] = 0.3
    changed.write_text(json.dumps(row), encoding="utf-8")
    row["push_signature"][4][0][0] = 0.3000002
    changed.write_text(json.dumps(row), encoding="utf-8")
    assert video.compare_mode_receipts(tmp_path)["state"] == "complete"
    row["push_signature"][4][0][0] = 0.3
    row["source_head"] = "wrong"
    changed.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="terrain, seed or checkpoint"):
        video.compare_mode_receipts(tmp_path)
    row["source_head"] = "s"
    changed.write_text(json.dumps(row), encoding="utf-8")
    (tmp_path / "eval_pred.mp4").unlink()
    with pytest.raises(FileNotFoundError):
        video.compare_mode_receipts(tmp_path)


def test_push_signature_needs_event_and_recovery():
    row = {"a_push_video": {"push_group_id": "g", "push_seed": 42,
                            "dr_recovery": {"defined": True},
                            "push_events": [{"step": 100, "seed": 999,
                                             "dv_xyz_w_mps": [[0.4, -0.1, 0.0]]}]}}
    assert video.push_signature(row)[2] == 100
    row["a_push_video"]["dr_recovery"] = {"defined": False}
    with pytest.raises(ValueError, match="recovery"):
        video.push_signature(row)


def test_direct_child_gets_pinned_package_path(tmp_path):
    env = video.source_child_env(Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"), tmp_path)
    assert env["PYTHONPATH"].split(";")[0] == str(tmp_path)
    assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    assert "CUDA_VISIBLE_DEVICES" not in env


def test_integer_done_mask_keeps_other_env_alive():
    import torch
    done, alive = recorder.dr_done_and_alive(torch.tensor([True, True, False]),
                                             torch.tensor([0, 1, 0], dtype=torch.int64))
    assert done.dtype is torch.bool
    assert done.tolist() == [False, True, False]
    assert alive.tolist() == [True, False, False]
