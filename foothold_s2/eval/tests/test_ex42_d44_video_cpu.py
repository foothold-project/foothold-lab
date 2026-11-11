from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.eval import ex42_d44_video as video


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"


def test_d44_video_case_order_matches_eval_tasks():
    assert video.command_order("turn_left") == ("turn_left_6s",)
    assert video.command_order("turn_right") == ("turn_right_6s",)
    assert video.command_order("stop_restart") == (
        "approach_to_stop_band", "stop_band_hold_2s", "restart_to_top")
    with pytest.raises(ValueError, match="unknown D44 task"):
        video.command_order("invented")


def test_capture_env_requests_rgb_array_and_fixed_viewport_resolution():
    class Gym:
        def __init__(self):
            self.call = None

        def make(self, task_id, **kwargs):
            self.call = (task_id, kwargs)
            return object()

    class Cfg:
        class Viewer:
            resolution = None
        viewer = Viewer()

    gym, cfg = Gym(), Cfg()
    video.make_capture_env(gym, "task-id", cfg)
    assert gym.call == ("task-id", {"cfg": cfg, "render_mode": "rgb_array"})
    assert cfg.viewer.resolution == (video.WIDTH, video.HEIGHT)


def test_render_product_is_created_by_warmup_before_mask_attachment():
    class RawEnv:
        def __init__(self):
            self.calls = 0
            self._render_product = None

        def render(self):
            self.calls += 1
            if self.calls == video.RENDER_WARMUP_FRAMES:
                self._render_product = "ready-product"

    raw = RawEnv()
    assert video.prepare_render_product(raw) == "ready-product"
    assert raw.calls == video.RENDER_WARMUP_FRAMES


def test_d44_video_commands_follow_eval_timing_and_latched_band_entry():
    common = {"settle": 0, "approach": 200, "stop": 100, "turn_rate": 1.2,
              "approach_speed": 1., "restart_speed": 1., "stop_band": (1., 2.)}
    def at(task, tick, x=0., entered=False):
        return video.command_for_tick(task=task, tick=tick, local_x=x,
                                      entered=entered, **common)
    assert at("turn_left", 0) == ("landing_turn", (0., 0., 1.2), False)
    assert at("turn_right", 0) == ("landing_turn", (0., 0., -1.2), False)
    assert at("stop_restart", 198)[0:2] == ("approach", (1., 0., 0.))
    assert at("stop_restart", 199, x=1.5) == ("approach", (0., 0., 0.), True)
    assert at("stop_restart", 199, x=2.5, entered=True) == ("approach", (0., 0., 0.), True)
    assert at("stop_restart", 200)[0:2] == ("stop_band_hold", (0., 0., 0.))
    assert at("stop_restart", 300)[0:2] == ("restart_to_top", (1., 0., 0.))


def test_plan_uses_gt_and_pred_cases_with_pinned_source(monkeypatch, tmp_path):
    checkpoint = tmp_path / "model_1000.pt"
    checkpoint.write_bytes(b"answer-known-checkpoint")
    mesh = tmp_path / "mesh"
    mesh.mkdir()
    mesh_sha = "b" * 64
    document = yaml.safe_load(PLAN.read_text(encoding="utf-8-sig"))
    document["evaluation"]["paper_cells"]["stairs_landing"]["source_mesh_dir"] = str(mesh)
    document["evaluation"]["paper_cells"]["stairs_landing"]["source_mesh_sha256"] = mesh_sha
    plan = tmp_path / "plan.yaml"
    plan.write_text(yaml.safe_dump(document), encoding="utf-8")
    monkeypatch.setattr("foothold_s2.eval.ex42_eval_tile_mesh.source_tile",
                        lambda _mesh: ({"mesh_sha256": mesh_sha}, {}))
    result = video.build_plan(checkpoint=checkpoint, plan_path=plan, output_dir=tmp_path / "out",
                              mesh_dir=mesh, expected_checkpoint_sha256=hashlib.sha256(
                                  checkpoint.read_bytes()).hexdigest())
    assert result["envs"] == 1 and result["map_modes"] == ["eval_gt", "eval_pred"]
    assert result["cases"] == list(video.VIDEO_CASES)
    assert result["durations_s"] == {
        "turn_left_eval_gt": 6.0, "turn_left_eval_pred": 6.0,
        "turn_right_eval_gt": 6.0, "turn_right_eval_pred": 6.0,
        "stop_restart_eval_gt": 12.0, "stop_restart_eval_pred": 12.0,
    }
    assert result["command_order"]["stop_restart_eval_gt"] == list(video.command_order("stop_restart"))
    assert result["durations_s"]["stop_restart_eval_gt"] == 12.0
    assert result["durations_s"]["turn_left_eval_gt"] == 6.0
    with pytest.raises(ValueError, match="SHA differs"):
        video.build_plan(checkpoint=checkpoint, plan_path=plan, output_dir=tmp_path / "out",
                         mesh_dir=mesh, expected_checkpoint_sha256="0" * 64)


def test_plan_rejects_non_m1000_checkpoint(monkeypatch, tmp_path):
    checkpoint = tmp_path / "model_999.pt"
    checkpoint.write_bytes(b"wrong-checkpoint")
    with pytest.raises(ValueError, match="m1000 checkpoint"):
        video.build_plan(checkpoint=checkpoint, plan_path=PLAN,
                         output_dir=tmp_path / "out", mesh_dir=tmp_path)


def test_one_env_judgment_records_actual_failure_reasons():
    n = 4
    anchors = {"approach": [0.0, 0.0, 0.0], "landing_center": [1.0, 0.0, 0.5],
               "stop_band_x": [0.4, 0.6], "landing_bounds_xy": [0.8, 1.2, -0.4, 0.4]}
    settings = {"turn_seconds": 6.0, "turn_rate_radps": 1.2, "turn_success_fraction": .8,
                "timing": {"stop_speed_mps": .05, "stop_hold_s": 1., "top_hold_s": .5,
                           "foot_below_top_m": .08}}
    data = {"root": np.tile([0., 0., .5], (n, 1)), "quat": np.tile([1., 0., 0., 0.], (n, 1)),
            "feet": np.zeros((n, 4, 3)), "contact": np.zeros((n, 4), dtype=bool),
            "vel": np.zeros((n, 3)), "alive": np.ones(n, dtype=bool),
            "phase": np.array(["approach", "stop_band_hold", "restart_to_top", "restart_to_top"])}
    result = video.judge_one(data, task="stop_restart", anchors=anchors,
                             settings=settings, dt=.02, tile_origin=[0., 0., 0.])
    assert result["success"] is False
    assert set(result["failure_reasons"]) == {
        "approach_timeout", "stop_band_hold_not_met", "landing_hold_not_met"}


def test_command_summary_pairs_requested_and_actual_values():
    rows = video.summarize_commands({
        "phase": ["approach", "approach", "restart_to_top"],
        "command": [[1., 0., 0.], [1., 0., 0.], [1., 0., 0.]],
        "vel": [[.8, 0., 0.], [.9, 0., 0.], [.7, 0., 0.]],
        "wz": [0.1, 0.0, -0.1],
    })
    assert [row["phase"] for row in rows] == ["approach", "restart_to_top"]
    assert rows[0]["requested_vx_mps"] == 1.0
    assert rows[0]["actual_vx_mean_mps"] == pytest.approx(.85)
    assert rows[1]["actual_wz_mean_radps"] == pytest.approx(-.1)


def test_stop_restart_hud_exposes_stop_band_motion_and_contact_readback():
    assert video.stop_restart_hud(task="stop_restart", local_x=1.5, stop_band=(1., 2.),
        foot_contacts=4, speed_xy=.01, stop_speed=.05) == (
            "stop-band=in | stopped=yes | feet contact=4/4 | speed_xy=0.010 m/s")
    assert video.stop_restart_hud(task="stop_restart", local_x=2.5, stop_band=(1., 2.),
        foot_contacts=2, speed_xy=.2, stop_speed=.05) == (
            "stop-band=out | stopped=no | feet contact=2/4 | speed_xy=0.200 m/s")
