"""Known trajectories for D44 scoring, with no Isaac or GPU imports."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from foothold_s2.eval.ex42_d44_cells import contract, summarize, read_evidence
from foothold_s2.ex42_eval_once import d44_kit_command


def _plan():
    specs = {f"{task}_{mode}": {"task": task, "map_mode": mode,
                                "role": "record_only" if mode == "probe_prop_only" else "judge"}
             for task in ("turn_left", "turn_right", "stop_restart")
             for mode in ("eval_gt", "eval_pred", "probe_prop_only")}
    return {"evaluation": {"paper_cells": {"stairs_landing": {
        "judge_cases": [key for key in specs if specs[key]["role"] == "judge"],
        "record_cases": [key for key in specs if specs[key]["role"] == "record_only"],
        "case_specs": specs,
        "timing": {"settle_s": 1., "approach_limit_s": 4., "stop_s": 2.,
                   "restart_limit_s": 6., "stop_hold_s": 1., "top_hold_s": .5,
                   "stop_speed_mps": .05, "foot_below_top_m": .08,
                   "foot_stop_z_tolerance_m": .08},
        "turn_rate_radps": 1.2, "turn_seconds": 6.,
        "success_turn_fraction": .8, "stop_surface_z_m": .48, "valid_min": 48,
        "approach_vx_mps": 1.0, "restart_vx_mps": 1.0,
        "source_mesh_dir": "/tmp/proposed-evaluation-mesh",
        "source_mesh_sha256": "a" * 64,
    }}}}


def _trace(task):
    n, steps = 64, 70
    root = np.zeros((steps, n, 3), dtype=np.float32)
    root[..., 0] = 4.0 if task.startswith("turn_") else 1.7
    root[..., 1] = 4.0
    root[..., 2] = 1.9 if task.startswith("turn_") else .75
    quat = np.zeros((steps, n, 4), dtype=np.float32)
    angle = np.linspace(0, 6.8, steps)
    if task == "turn_right":
        angle *= -1
    quat[..., 0] = np.cos(angle[:, None] / 2)
    quat[..., 3] = np.sin(angle[:, None] / 2)
    feet = np.zeros((steps, n, 4, 3), dtype=np.float32)
    feet[..., 2] = 1.44 if task.startswith("turn_") else .32
    phase = np.ones((steps, n), dtype=np.int16)
    if task == "stop_restart":
        phase[10:30] = 2
        phase[30:] = 3
        root[30:, :, 0] = 4.0
        root[30:, :, 2] = 1.9
        feet[30:, :, :, 2] = 1.44
    return {"root_pos_w": root, "root_quat_w": quat, "foot_pos_w": feet,
            "contact": np.ones((steps, n, 4), dtype=bool),
            "alive": np.ones((steps, n), dtype=bool),
            "body_vel_b": np.zeros((steps, n, 3), dtype=np.float32),
            "phase_id": phase, "tile_offset_w": np.zeros((n, 3), dtype=np.float32)}


ANCHORS = {"landing_center": [4., 4., 1.44], "landing_bounds_xy": [3.4, 4.6, 3.4, 4.6],
           "stop_band_x": [1.6, 1.9]}


def test_contract_reads_six_judge_and_three_record_cases_from_plan():
    settings = contract(_plan())
    assert len(settings["judge_cases"]) == 6
    assert len(settings["record_cases"]) == 3
    bad = _plan()
    bad["evaluation"]["paper_cells"]["stairs_landing"].pop("judge_cases")
    with pytest.raises(ValueError, match="case list"):
        contract(bad)


def test_approved_prep_contract_pins_six_judged_three_record_and_source_mesh():
    import yaml
    from foothold_s2.eval.ex42_eval_tile_mesh import source_tile

    prep = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
    plan = yaml.safe_load(prep.read_text(encoding="utf-8-sig"))
    settings = contract(plan)
    assert len(settings["judge_cases"]) == 6
    assert len(settings["record_cases"]) == 3
    assert set(settings["case_specs"]) == set(settings["judge_cases"] + settings["record_cases"])
    assert tuple(settings["timing"][key] for key in
                 ("settle_s", "approach_limit_s", "stop_s", "restart_limit_s")) == (1, 4, 2, 6)
    manifest, _ = source_tile(Path(settings["source_mesh_dir"]))
    assert manifest["mesh_sha256"] == settings["source_mesh_sha256"]


def test_turn_left_right_use_signed_unwrapped_angle_and_platform():
    settings = contract(_plan())
    for task in ("turn_left", "turn_right"):
        trace = _trace(task)
        row = summarize(trace, spec={"task": task}, anchors=ANCHORS, settings=settings, dt=.1)
        assert (row["valid_count"], row["survival_count"], row["success_count"]) == (64, 64, 64)
        reversed_turn = copy.deepcopy(trace)
        reversed_turn["root_quat_w"][..., 3] *= -1
        bad = summarize(reversed_turn, spec={"task": task}, anchors=ANCHORS, settings=settings, dt=.1)
        assert bad["success_count"] == 0
        trace["foot_pos_w"][..., 2] = 1.0
        assert summarize(trace, spec={"task": task}, anchors=ANCHORS,
                         settings=settings, dt=.1)["success_count"] == 0
        trace = _trace(task)
        trace["contact"][:] = False
        assert summarize(trace, spec={"task": task}, anchors=ANCHORS,
                         settings=settings, dt=.1)["success_count"] == 0


def test_stop_restart_timeout_is_unjudged_and_reach_requires_four_feet():
    settings = contract(_plan())
    trace = _trace("stop_restart")
    good = summarize(trace, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=settings, dt=.1)
    assert (good["valid_count"], good["success_count"]) == (64, 64)
    trace["approach_entered"] = np.ones(64, dtype=bool)
    trace["approach_entered"][0] = False
    trace["foot_pos_w"][30:, 1, 3, 2] = 1.1
    bad = summarize(trace, spec={"task": "stop_restart"}, anchors=ANCHORS,
                    settings=settings, dt=.1)
    assert (bad["valid_count"], bad["success_count"]) == (63, 62)
    assert bad["survival_count"] == 63
    assert bad["per_env"][0]["reason"] == "approach_timeout"


def test_stop_is_root_band_and_speed_only_with_foot_height_diagnostic():
    settings = contract(_plan())
    trace = _trace("stop_restart")
    # Feet span different treads. The approved stop does not require 0.48 m feet.
    good = summarize(trace, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=settings, dt=.1)
    assert good["success_count"] == 64
    assert good["per_env"][0]["stop_feet_height_ok"] is False
    moving = copy.deepcopy(trace)
    moving["body_vel_b"][10:30, :, 0] = .051
    assert summarize(moving, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=settings, dt=.1)["success_count"] == 0
    outside = copy.deepcopy(trace)
    outside["root_pos_w"][10:30, :, 0] = 1.91
    assert summarize(outside, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=settings, dt=.1)["success_count"] == 0


def test_read_evidence_binds_every_case_json_and_npz_sha(tmp_path, monkeypatch):
    from foothold_s2.eval import ex42_eval_tile_mesh

    monkeypatch.setattr(ex42_eval_tile_mesh, "source_tile", lambda _: (
        {"mesh_sha256": "a" * 64}, {"anchors_local_m": ANCHORS}))
    plan = _plan()
    settings = contract(plan)
    cases = {}
    for case_id, spec in settings["case_specs"].items():
        trace = tmp_path / f"{case_id}.npz"
        arrays = _trace(spec["task"])
        arrays["dt"] = np.asarray(.1)
        np.savez_compressed(trace, **arrays)
        summary = {"case_id": case_id, **spec,
                   **summarize(arrays, spec=spec, anchors=ANCHORS, settings=settings, dt=.1),
                   "trace_file": str(trace),
                   "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}
        source = tmp_path / f"{case_id}.json"
        source.write_text(json.dumps(summary), encoding="utf-8")
        cases[case_id] = {**summary, "raw_file": str(source),
                          "raw_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    receipt = {"format": "foothold-ex42-d44-eval/1", "state": "done", "plan_sha256": "a" * 64,
               "source_mesh_sha256": "a" * 64,
               "checkpoint_sha256": "b" * 64, "seed": 42, "envs": 64, "cases": cases}
    (tmp_path / "d44_cells.json").write_text(json.dumps(receipt), encoding="utf-8")
    checked = read_evidence(tmp_path, plan=plan, plan_sha256="a" * 64,
                            checkpoint_sha256="b" * 64, seed=42)
    assert set(checked) == set(settings["judge_cases"])
    trace = tmp_path / f"{settings['judge_cases'][0]}.npz"
    trace.write_bytes(trace.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA"):
        read_evidence(tmp_path, plan=plan, plan_sha256="a" * 64,
                      checkpoint_sha256="b" * 64, seed=42)


def test_d44_real_kit_parser_accepts_parent_argv_then_rejects_bad_env_count(tmp_path, monkeypatch):
    if importlib.util.find_spec("isaaclab") is None:
        pytest.skip("Isaac Lab parser is unavailable in this CPU interpreter")
    monkeypatch.setenv("FOOTHOLD_MACHINE_PROFILE", str(Path(__file__).resolve().parents[2] / "machines/AI-WS01-linux.yaml"))
    argv = d44_kit_command(Path(__file__), tmp_path, "cuda:1", task="FootholdS2-Go2-S2-SB-v0",
                           plan_path=tmp_path / "missing-plan.yaml", mesh_dir=tmp_path / "source",
                           replica_dir=tmp_path / "replica", replica_sha256="a" * 64, seed=42)
    argv[argv.index("--envs") + 1] = "63"
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ""
    process = subprocess.run(argv, cwd=Path(__file__).resolve().parents[2], env=env,
                             text=True, capture_output=True, timeout=30, check=False)
    assert process.returncode == 2
    assert "D44 requires a fresh output" in process.stderr
    assert "unrecognized arguments" not in process.stderr
    assert not (tmp_path / "d44").exists()
