"""Known trajectories for D44 scoring, with no Isaac or GPU imports."""
from __future__ import annotations

import copy
import pathlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from foothold_s2.eval.ex42_d44_cells import (TRACE_FORMAT, RECEIPT_FORMAT, contract, summarize,
                                             read_evidence, restart_command, top_latch_mask)
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
    n, steps = 64, 130 if task == "stop_restart" else 70
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
    phase[:10] = 0
    cmd = np.zeros((steps, n, 3), dtype=np.float32)
    latch = np.full(n, -1, dtype=np.int32)
    if task == "stop_restart":
        phase[50:70] = 2
        phase[70] = 3
        phase[71:] = 4
        cmd[70, :, 0] = 1.0
        latch[:] = 70
        root[70:, :, 0] = 4.0
        root[70:, :, 2] = 1.9
        feet[70:, :, :, 0] = 4.0
        feet[70:, :, :, 1] = 4.0
        feet[70:, :, :, 2] = 1.44
    return {"trace_format": np.asarray(TRACE_FORMAT), "top_latched_at": latch,
            "cmd_post": cmd, "root_pos_w": root, "root_quat_w": quat, "foot_pos_w": feet,
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


def test_stop_restart_timeout_is_unjudged_and_low_contact_foot_fails():
    settings = contract(_plan())
    trace = _trace("stop_restart")
    good = summarize(trace, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=settings, dt=.1)
    assert (good["valid_count"], good["success_count"]) == (64, 64)
    trace["approach_entered"] = np.ones(64, dtype=bool)
    trace["approach_entered"][0] = False
    trace["foot_pos_w"][70:, 1, 3, 2] = 1.1
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
    moving["body_vel_b"][50:70, :, 0] = .051
    assert summarize(moving, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=settings, dt=.1)["success_count"] == 0
    outside = copy.deepcopy(trace)
    outside["root_pos_w"][50:70, :, 0] = 1.91
    assert summarize(outside, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=settings, dt=.1)["success_count"] == 0


def test_top_latch_and_command_are_per_env_after_post_step_entry():
    root = np.array([[3.75, 4.0], [3.75, 4.0], [4.7, 4.0], [3.75, 4.61]])
    feet_x = np.array([[3.4, 3.5, 3.6, 3.7], [3.39, 3.5, 3.6, 3.7], [3.8]*4, [3.8]*4])
    feet = np.stack((feet_x, np.full_like(feet_x, 4.0)), axis=-1)             # every foot on the landing's centre line
    latch = top_latch_mask(root, feet, np.ones(4, bool), ANCHORS["landing_bounds_xy"])
    assert latch.tolist() == [True, False, False, False]
    with pytest.raises(ValueError, match="top latch geometry"):
        top_latch_mask(root, feet_x, np.ones(4, bool), ANCHORS["landing_bounds_xy"])      # the /2 call: x only
    phase, vx = restart_command(latch, 1.0)
    assert phase.tolist() == [4, 3, 3, 3]
    assert vx.tolist() == [0.0, 1.0, 1.0, 1.0]


def test_a_foot_beside_the_landing_does_not_latch_the_top():
    """decisions.tsv 2026-11-12 11:28: with four feet at x >= 3.4 the robot latched while a hind foot stood one step
    lower. On the concentric stairs that is a foot outside the landing in y (or past its far edge in x)."""
    xmin, xmax, ymin, ymax = ANCHORS["landing_bounds_xy"]
    assert (xmin, xmax, ymin, ymax) == (3.4, 4.6, 3.4, 4.6)
    on = np.array([[3.6, 3.8], [3.6, 4.2], [4.2, 3.8], [4.2, 4.2]])           # four feet on the landing
    cases = {"on": on}
    for name, foot, value in (("left", (0, 1), 3.39), ("right", (1, 1), 4.61), ("front", (0, 0), 3.39), ("far", (3, 0), 4.61)):
        feet = on.copy()
        feet[foot] = value
        cases[name] = feet
    edge = on.copy()
    edge[0], edge[3] = (3.4, 3.4), (4.6, 4.6)                                 # exactly on the edge counts as on it
    cases["edge"] = edge
    names = list(cases)
    root = np.tile([4.0, 4.0], (len(names), 1))
    latch = top_latch_mask(root, np.stack([cases[n] for n in names]), np.ones(len(names), bool), ANCHORS["landing_bounds_xy"])
    assert dict(zip(names, latch.tolist())) == {"on": True, "left": False, "right": False, "front": False, "far": False,
                                                 "edge": True}
    dead = np.ones(len(names), bool)
    dead[0] = False
    assert not top_latch_mask(root, np.stack([cases[n] for n in names]), dead, ANCHORS["landing_bounds_xy"])[0]
    assert TRACE_FORMAT.endswith("/3") and RECEIPT_FORMAT.endswith("/3")      # /2 results were judged on x only


def test_top_stand_six_known_inputs_and_old_trace_rejection():
    settings = contract(_plan())
    kwargs = dict(spec={"task": "stop_restart"}, anchors=ANCHORS, settings=settings, dt=.1)
    good = _trace("stop_restart")
    # A trot can keep diagonal contact without all four feet touching together.
    good["contact"][71::2, :, [1, 3]] = False
    good["contact"][72::2, :, [0, 2]] = False
    assert summarize(good, **kwargs)["success_count"] == 64
    low = copy.deepcopy(good)
    low["contact"][71:, 0, 0] = True
    low["foot_pos_w"][71:, 0, 0, 2] = 1.28
    result = summarize(low, **kwargs)
    assert result["success_count"] == 63
    assert result["per_env"][0]["reason"] == "foot_below_landing"
    moving = copy.deepcopy(good)
    moving["body_vel_b"][71:, :, 0] = .06
    assert summarize(moving, **kwargs)["success_count"] == 0
    assert summarize(moving, **kwargs)["per_env"][0]["reason"] == "not_still"
    no_latch = copy.deepcopy(good)
    no_latch["phase_id"][71:] = 3
    no_latch["cmd_post"][71:, :, 0] = 1.0
    no_latch["top_latched_at"][:] = -1
    no_latch["foot_pos_w"][70:, :, :, 0] = 3.2
    assert summarize(no_latch, **kwargs)["per_env"][0]["reason"] == "no_top_latch"
    beside = copy.deepcopy(no_latch)                    # feet past the front edge, one hind foot beside the landing
    beside["foot_pos_w"][70:, :, :, 0] = 4.0
    beside["foot_pos_w"][70:, :, 3, 1] = 3.3
    assert summarize(beside, **kwargs)["per_env"][0]["reason"] == "no_top_latch"      # /2 latched here on x alone
    claimed = copy.deepcopy(beside)                     # a trace that says it latched there is not this geometry
    claimed["phase_id"][71:] = 4
    claimed["cmd_post"][71:, :, 0] = 0.0
    claimed["top_latched_at"][:] = 70
    with pytest.raises(ValueError, match="top latch or phase 4 differs"):
        summarize(claimed, **kwargs)
    kit = (pathlib.Path(__file__).resolve().parents[1] / "eval" / "ex42_d44_eval.py").read_text(encoding="utf-8")
    assert "candidate = top_latch_mask(local_root[:, :2], local_feet[:, :, :2]," in kit      # the live latch sees y too
    no_stand = copy.deepcopy(good)
    no_stand["body_vel_b"][71:, :, 0] = .2
    assert summarize(no_stand, **kwargs)["success_count"] == 0
    old = copy.deepcopy(good)
    old.pop("trace_format")
    with pytest.raises(ValueError, match="old trace format"):
        summarize(old, **kwargs)
    forged = copy.deepcopy(good)
    forged["cmd_post"][71:, :, 0] = 1.0
    with pytest.raises(ValueError, match="recorded command"):
        summarize(forged, **kwargs)


def test_four_foot_xy_diagnostic_counts_longest_consecutive_run_only():
    trace = _trace("stop_restart")
    trace["foot_pos_w"][74, :, 0, 1] = 4.7
    trace["foot_pos_w"][78, :, 0, 1] = 4.7
    rows = summarize(trace, spec={"task": "stop_restart"}, anchors=ANCHORS,
                     settings=contract(_plan()), dt=.1)["per_env"]
    assert rows[0]["success"] is True
    assert rows[0]["four_foot_xy_inside_ticks"] == 51


def test_top_stand_needs_25_consecutive_ticks_at_actual_plan_dt():
    import yaml
    plan = yaml.safe_load((Path(__file__).resolve().parents[1] / "curriculum" /
                           "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    settings = contract(plan)
    assert settings["timing"]["top_hold_s"] == .5
    trace = _trace("stop_restart")
    trace = {key: np.repeat(value, 5, axis=0) if value.shape[:1] == (130,) else value.copy()
             for key, value in trace.items()}
    trace["phase_id"][351:] = 4
    trace["cmd_post"][351:] = 0
    trace["top_latched_at"][:] = 350
    trace["body_vel_b"][351:, :, 0] = .06
    trace["body_vel_b"][400:424, :, 0] = 0
    kwargs = dict(spec={"task": "stop_restart"}, anchors=ANCHORS, settings=settings, dt=.02)
    assert summarize(trace, **kwargs)["success_count"] == 0
    trace["body_vel_b"][424, :, 0] = 0
    assert summarize(trace, **kwargs)["success_count"] == 64


def test_post_step_reset_command_is_ignored_only_after_terminal_tick():
    trace = _trace("stop_restart")
    trace["alive"][90:, 0] = False
    trace["cmd_post"][90, 0, 0] = .968
    kwargs = dict(spec={"task": "stop_restart"}, anchors=ANCHORS,
                  settings=contract(_plan()), dt=.1)
    assert summarize(trace, **kwargs)["per_env"][0]["survival"] is False
    trace["cmd_post"][89, 0, 0] = .968
    with pytest.raises(ValueError, match="recorded command"):
        summarize(trace, **kwargs)


def test_real_m1000_trace_replays_terminal_reset_without_waiving_live_command():
    path = os.environ.get("EX42_D44_M1000_REAL_TRACE")
    if not path:
        pytest.skip("set EX42_D44_M1000_REAL_TRACE to replay the preserved Kit trace")
    import yaml
    from foothold_s2.eval.ex42_eval_tile_mesh import source_tile

    with np.load(path) as saved:
        trace = {key: saved[key] for key in saved.files}
    plan = yaml.safe_load((Path(__file__).resolve().parents[1] / "curriculum" /
                           "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    settings = contract(plan)
    _, tile = source_tile(Path(settings["source_mesh_dir"]))
    kwargs = dict(spec={"task": "stop_restart"}, anchors=tile["anchors_local_m"],
                  settings=settings, dt=float(trace["dt"]))
    assert bool(trace["alive"][495, 38]) is True
    assert bool(trace["alive"][496, 38]) is False
    assert trace["phase_id"][496, 38] == 3
    assert trace["cmd_post"][496, 38, 0] == pytest.approx(.968481779, abs=1e-6)
    result = summarize(trace, **kwargs)
    assert (result["valid_count"], result["survival_count"], result["success_count"]) == (64, 63, 36)
    forged = copy.deepcopy(trace)
    forged["cmd_post"][495, 38, 0] = .968
    with pytest.raises(ValueError, match="recorded command"):
        summarize(forged, **kwargs)


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
    receipt = {"format": RECEIPT_FORMAT, "state": "done", "plan_sha256": "a" * 64,
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
