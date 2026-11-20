"""v29-14c: the side cells are windowed like the forward ones when the raw has vy; the official path (no plan window) is byte identical."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2 import ex42_e1_v2
from foothold_s2.ex42_e1_v2 import _map_cell, mae_window_s_from_plan, measure_cells, window_mae_per_env
from foothold_s2.tests.test_ex42_mae_window_cpu import DT, _reference

ROOT = Path(__file__).resolve().parents[2]
PLAN = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text())


def _side_cell(tmp_path, vy, alive, command=0.2, with_vy=True, mode="eval_gt", case="side+0.2"):
    sha, seed, envs = "a" * 64, 42, vy.shape[1]
    identity = {"checkpoint_sha256": sha, "eval_seed": seed}
    alive_steps = alive.sum(0)
    raw = dict(vx=np.zeros_like(vy, dtype=np.float32), alive=alive, dt=np.float64(DT), alive_steps=alive_steps, alive_end=alive[-1],
               assignment_sha256=np.str_("b" * 64), run_identity=np.str_(json.dumps(identity)))
    if with_vy:
        raw.update(vy=vy.astype(np.float32), wz=np.zeros_like(vy, dtype=np.float32))
    np.savez(tmp_path / f"env_arrays_{mode}_{case}.npz", **raw)
    vy32 = vy.astype(np.float32).astype(np.float64)
    step = (np.abs(vy32 - command) * alive).sum(0) / np.maximum(alive_steps, 1)
    per_env = [{"env": i, "samples_alive": int(alive_steps[i]), "vx_abs_error_mean_alive_mps": 0.0,
                "vy_abs_error_mean_alive_mps": float(step[i]),
                "command_xy_projection_integral_m": float((vy32[:, i] * alive[:, i]).sum() * DT)} for i in range(envs)]
    doc = {"commands": {case: [0.0, command, 0.0]}, "env_arrays": {f"{mode}/{case}": f"env_arrays_{mode}_{case}.npz"},
           "modes": {mode: {case: {"per_env": per_env, "command": [0.0, command, 0.0], "env_count": envs,
                                   "alive_envs_at_end": int(alive[-1].sum())}}},
           "run_identity": identity, "checkpoint_sha256": sha, "eval_seed": seed, "fixed_terrain": {"assignment_sha256": "b" * 64}}
    return tmp_path / "map_modes.json", doc, step


def _wobble(amplitude, envs=64):
    k = np.arange(300)[:, None]
    return np.repeat(0.2 + amplitude * np.sin(2 * np.pi * k / 5), envs, axis=1), np.ones((300, envs), bool)


def test_a_constant_speed_wobble_is_about_zero_in_the_window_and_step_sized_in_the_step_mae(tmp_path):
    vy, alive = _wobble(0.0377)
    path, doc, step = _side_cell(tmp_path, vy, alive)
    official = _map_cell(path, doc, "eval_gt", "side+0.2")
    assert abs(official["mae_mps"] - 0.0377 * 2 / np.pi) < 1e-3 and 0.023 < official["mae_mps"] < 0.025     # the step value (0.024)
    windowed = _map_cell(path, doc, "eval_gt", "side+0.2", mae_window_s=0.5)
    assert windowed["mae_basis"] == "window" and windowed["mae_mps"] < 1e-3 and windowed["mae_window_mps"] == windowed["mae_mps"]
    assert abs(windowed["mae_step_mps"] - official["mae_mps"]) < 1e-12 and windowed["mae_window_s"] == 0.5
    vy, alive = _wobble(0.03)                                                  # +-0.03: step 0.019, window ~0
    path, doc, _ = _side_cell(tmp_path, vy, alive)
    assert abs(_map_cell(path, doc, "eval_gt", "side+0.2")["mae_mps"] - 0.03 * 2 / np.pi) < 1e-3
    assert _map_cell(path, doc, "eval_gt", "side+0.2", mae_window_s=0.5)["mae_mps"] < 1e-3


def test_the_negative_side_command_is_windowed_with_its_sign(tmp_path):
    vy = -np.repeat(0.4 + 0.03 * np.sin(2 * np.pi * np.arange(300)[:, None] / 5), 64, axis=1)
    path, doc, _ = _side_cell(tmp_path, vy, np.ones((300, 64), bool), command=-0.4, case="side-0.4")
    doc["commands"]["side-0.4"] = [0.0, -0.4, 0.0]
    cell = _map_cell(path, doc, "eval_gt", "side-0.4", mae_window_s=0.5)
    assert cell["mae_basis"] == "window" and cell["mae_mps"] < 1e-3


def test_an_old_raw_without_vy_keeps_the_step_mae_and_says_so(tmp_path):
    vy, alive = _wobble(0.0377)
    path, doc, step = _side_cell(tmp_path, vy, alive, with_vy=False)
    cell = _map_cell(path, doc, "eval_gt", "side+0.2", mae_window_s=0.5)
    assert cell["mae_basis"] == "step" and cell["mae_window_mps"] is None and cell["per_env_mae_windows"] is None
    assert abs(cell["mae_mps"] - np.median(step)) < 1e-12                          # not a HOLD, not an error: the official number
    assert cell["per_env_mae_mps"] == _map_cell(path, doc, "eval_gt", "side+0.2")["per_env_mae_mps"]


def test_record_window_adds_the_values_and_leaves_the_judged_mae_alone(tmp_path):
    vy, alive = _wobble(0.0377)
    path, doc, _ = _side_cell(tmp_path, vy, alive)
    official = _map_cell(path, doc, "eval_gt", "side+0.2")
    recorded = _map_cell(path, doc, "eval_gt", "side+0.2", record_window_s=0.5)
    assert recorded["mae_basis"] == "step" and recorded["mae_mps"] == official["mae_mps"]
    assert recorded["mae_window_mps"] < 1e-3 and recorded["per_env_mae_mps"] == official["per_env_mae_mps"]


def test_without_a_window_the_cell_has_exactly_the_old_keys(tmp_path):
    """canonical_evidence compares whole cells: an extra key in the official path would make every stored score 'differ'."""
    vy, alive = _wobble(0.03)
    path, doc, _ = _side_cell(tmp_path, vy, alive)
    assert set(_map_cell(path, doc, "eval_gt", "side+0.2")) == {"R", "mae_mps", "survival", "command_mps", "envs", "per_env_R",
                                                                  "per_env_mae_mps", "per_env_alive_end", "raw_file", "raw_sha256"}


def test_the_plan_gate(monkeypatch):
    assert mae_window_s_from_plan(PLAN) is None and mae_window_s_from_plan(None) is None      # every plan an official boundary runs today
    plan = {"evaluation": {"e1_widened": {"graduation": {"mae_window_s": 0.5}}}}
    assert mae_window_s_from_plan(plan) == 0.5
    for bad in (0, -1, "0.5", True):
        with pytest.raises(ValueError):
            mae_window_s_from_plan({"evaluation": {"e1_widened": {"graduation": {"mae_window_s": bad}}}})
    seen = []
    monkeypatch.setattr(ex42_e1_v2, "_map_cell", lambda *a, mae_window_s=None, record_window_s=None: seen.append((mae_window_s, record_window_s)) or {})
    monkeypatch.setattr(ex42_e1_v2, "_source", lambda *a, **k: {"command_suite": "e1_v2", "commands": dict.fromkeys(ex42_e1_v2.LOW_CASES)})
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        folder = Path(d) / "e1_v2" / "L0"
        folder.mkdir(parents=True)
        (folder / "map_modes.json").write_text("{}")
        measure_cells(Path(d), "a" * 64, 42)
        measure_cells(Path(d), "a" * 64, 42, plan=PLAN)
        measure_cells(Path(d), "a" * 64, 42, plan=plan)
        measure_cells(Path(d), "a" * 64, 42, record_window_s=0.5)
    assert len(seen) == 72                                         # four measure_cells calls x (3 modes x 6 low cases) at level 0
    groups = [set(seen[i * 18:(i + 1) * 18]) for i in range(4)]
    assert groups == [{(None, None)}, {(None, None)}, {(0.5, None)}, {(None, 0.5)}]


def test_the_npz_writer_saves_vy_and_wz_beside_vx():
    import ast
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_save_env_arrays")
    assert {"vy", "wz"} <= {a.arg for a in fn.args.args}
    text = ast.get_source_segment(src, fn)
    assert 'extra["vy"] = vy' in text and 'extra["wz"] = wz' in text and "np.savez" in text
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_save_env_arrays"]
    assert calls and all({"vy", "wz"} <= {k.arg for k in c.keywords} for c in calls)


M500 = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261115_135412/main/EX-42-B-E1-v29c_20261115_135412/eval/scores/m500")


@pytest.mark.skipif(not M500.is_dir(), reason="read-only v29c m500 score absent on this machine")
def test_window_value_on_real_m500_forward_cell_equals_an_independent_loop():
    score = json.loads((M500 / "ex42_score.json").read_text())
    cell = measure_cells(M500, score["checkpoint_sha256"], 42, mae_window_s=0.5)["low"]["L0"]["eval_gt"]["fwd0.1"]
    with np.load(M500 / "e1_v2" / "L0" / "env_arrays_eval_gt_fwd0.1.npz") as z:
        want, count = _reference(z["vx"].astype(np.float64), z["alive"].astype(bool), 0.1, 0.02, 0.5)
    step = np.array(cell["per_env_mae_step_mps"])
    want = np.where(count > 0, want, step)
    assert np.allclose(cell["per_env_mae_mps"], want, atol=1e-12) and cell["mae_basis"] == "window"
