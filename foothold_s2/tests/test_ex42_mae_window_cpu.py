"""Known-answer tests for the 0.5 s window MAE (team lead 2026-11-15 21:11, ledger 9cf03f93). CPU only."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2 import ex42_e1_v2
from foothold_s2.ex42_e1_v2 import _map_cell, judge_cells, measure_cells, window_mae_per_env

ROOT = Path(__file__).resolve().parents[2]
PLAN = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text())
DT = 0.02


def _reference(vx, alive, command, dt, window_s):
    """Plain loops, written independently of the vectorised code."""
    steps = int(round(window_s / dt))
    out, counts = [], []
    for env in range(vx.shape[1]):
        errors = []
        for start in range(0, vx.shape[0] - steps + 1, steps):
            if all(alive[start:start + steps, env]):
                errors.append(abs(sum(vx[start:start + steps, env]) / steps - command))
        out.append(sum(errors) / len(errors) if errors else 0.0)
        counts.append(len(errors))
    return np.array(out), np.array(counts)


def test_gait_wobble_is_invisible_to_the_window_but_not_to_the_step_mean():
    k = np.arange(300)[:, None]
    for amplitude, step_mae in ((0.03, 0.03 * 2 / np.pi), (0.0377, 0.0377 * 2 / np.pi)):
        vx = np.repeat(0.1 + amplitude * np.sin(2 * np.pi * k / 5), 64, axis=1)   # 0.1 s gait, 5 steps
        alive = np.ones((300, 64), bool)
        step = np.abs(vx - 0.1).mean(0)
        window, windows = window_mae_per_env(vx, alive, 0.1, DT, 0.5)
        assert np.allclose(step, step_mae, atol=1e-3)         # 0.019 (+-0.03) and 0.024 (+-0.0377)
        assert window.max() < 1e-6 and (windows == 12).all()  # the wobble averages out in 25 steps
    assert abs(step_mae - 0.024) < 1e-3                         # the lead's 0.024 case, over the 0.020 limit


def test_window_keeps_a_real_bias():
    vx = np.full((300, 4), 0.08)
    window, _ = window_mae_per_env(vx, np.ones((300, 4), bool), 0.1, DT, 0.5)
    assert np.allclose(window, 0.02, atol=1e-7)                 # a 20 % slow robot is still 0.02 off


def test_window_length_follows_dt_and_matches_the_reference_on_random_data():
    rng = np.random.default_rng(3)
    for dt, window_s in ((0.02, 0.5), (0.05, 0.5), (0.02, 0.52), (0.04, 0.48)):
        vx = rng.normal(0.1, 0.05, (300, 16))
        alive = np.arange(300)[:, None] < rng.integers(0, 301, 16)[None, :]    # alive is a prefix
        got, windows = window_mae_per_env(vx, alive, 0.1, dt, window_s)
        want, count = _reference(vx, alive, 0.1, dt, window_s)
        assert np.allclose(got, want, atol=1e-12) and (windows == count).all()


def test_tail_and_dead_windows_are_dropped():
    vx = np.full((300, 3), 0.1)
    vx[-4:, 0] = 100.0                   # 0.52 s windows (26 steps): 11 fit, the last 4 steps are the tail
    alive = np.ones((300, 3), bool)
    alive[130:, 1] = False               # env 1 dies at step 130: windows 0..4 (25 steps) are fully alive
    vx[130:, 1] = 100.0                  # the dead steps carry garbage and must not count
    vx[125:130, 1] = 0.1
    window, windows = window_mae_per_env(vx, alive, 0.1, DT, 0.52)
    assert window[0] < 1e-12 and windows[0] == 11
    window25, windows25 = window_mae_per_env(vx, alive, 0.1, DT, 0.5)
    assert windows25.tolist() == [12, 5, 12] and window25[1] < 1e-12
    alive[:10, 2] = False                # a window that is not entirely alive is skipped, not averaged
    _, windows3 = window_mae_per_env(vx, alive, 0.1, DT, 0.5)
    assert windows3[2] == 11


def test_window_must_be_a_whole_number_of_steps():
    ones = np.ones((300, 2))
    for bad in (0.51, 0.0, -0.5):
        with pytest.raises(ValueError):
            window_mae_per_env(ones, ones.astype(bool), 0.1, DT, bad)
    with pytest.raises(ValueError):
        window_mae_per_env(ones[:20], ones[:20].astype(bool), 0.1, DT, 0.5)


def _synthetic_cell(tmp_path, vx, alive, command=0.1, mode="eval_gt", case="fwd0.1"):
    """A map_modes.json + env_arrays npz that _map_cell accepts, with the official per-step MAE."""
    sha, seed, steps, envs = "a" * 64, 42, vx.shape[0], vx.shape[1]
    identity = {"checkpoint_sha256": sha, "eval_seed": seed}
    alive_steps = alive.sum(0)
    np.savez(tmp_path / f"env_arrays_{mode}_{case}.npz", vx=vx.astype(np.float32), alive=alive, dt=np.float64(DT),
             alive_steps=alive_steps, alive_end=alive[-1], assignment_sha256=np.str_("b" * 64),
             run_identity=np.str_(json.dumps(identity)))
    vx32 = vx.astype(np.float32).astype(np.float64)
    step = (np.abs(vx32 - command) * alive).sum(0) / np.maximum(alive_steps, 1)
    per_env = [{"env": i, "samples_alive": int(alive_steps[i]), "vx_abs_error_mean_alive_mps": float(step[i]),
                "vy_abs_error_mean_alive_mps": 0.0,
                "command_xy_projection_integral_m": float((vx32[:, i] * alive[:, i]).sum() * DT)}
               for i in range(envs)]
    doc = {"commands": {case: [command, 0.0, 0.0]}, "env_arrays": {f"{mode}/{case}": f"env_arrays_{mode}_{case}.npz"},
           "modes": {mode: {case: {"per_env": per_env, "command": [command, 0.0, 0.0], "env_count": envs,
                                   "alive_envs_at_end": int(alive[-1].sum())}}},
           "run_identity": identity, "checkpoint_sha256": sha, "eval_seed": seed,
           "fixed_terrain": {"assignment_sha256": "b" * 64}}
    return tmp_path / "map_modes.json", doc, step


def test_map_cell_default_is_unchanged_and_window_replaces_only_the_mae(tmp_path):
    k = np.arange(300)[:, None]
    vx = np.repeat(0.1 + 0.0377 * np.sin(2 * np.pi * k / 5), 64, axis=1)
    vx[:, 5] = 0.08                       # one env with a real 0.02 bias
    alive = np.ones((300, 64), bool)
    alive[10:, 7] = False                 # env 7 never completes a window
    path, doc, step = _synthetic_cell(tmp_path, vx, alive)
    legacy = _map_cell(path, doc, "eval_gt", "fwd0.1")
    assert "mae_window_s" not in legacy and abs(legacy["mae_mps"] - np.median(step)) < 1e-12
    windowed = _map_cell(path, doc, "eval_gt", "fwd0.1", mae_window_s=0.5)
    errors = np.array(windowed["per_env_mae_mps"])
    assert windowed["mae_window_s"] == 0.5 and windowed["mae_mps"] < 1e-3          # median env is wobble only
    assert abs(errors[5] - 0.02) < 1e-6                                              # a bias is kept
    assert abs(errors[7] - step[7]) < 1e-12 and windowed["per_env_mae_windows"][7] == 0   # per-step fallback
    assert windowed["per_env_mae_step_mps"] == legacy["per_env_mae_mps"]
    for key in ("R", "survival", "per_env_R", "per_env_alive_end", "command_mps"):
        assert windowed[key] == legacy[key]


def test_module_default_is_off_and_the_constant_switches_measure_cells(tmp_path, monkeypatch):
    assert ex42_e1_v2.MAE_WINDOW_S is None
    seen = []
    monkeypatch.setattr(ex42_e1_v2, "_map_cell", lambda *a, mae_window_s=None, **k: seen.append(mae_window_s) or {})
    folder = tmp_path / "e1_v2" / "L0"
    folder.mkdir(parents=True)
    (folder / "map_modes.json").write_text("{}")
    monkeypatch.setattr(ex42_e1_v2, "_source", lambda *a, **k: {"command_suite": "e1_v2", "commands": dict.fromkeys(ex42_e1_v2.LOW_CASES)})
    measure_cells(tmp_path, "a" * 64, 42)
    monkeypatch.setattr(ex42_e1_v2, "MAE_WINDOW_S", 0.5)
    measure_cells(tmp_path, "a" * 64, 42)
    measure_cells(tmp_path, "a" * 64, 42, mae_window_s=0.25)
    assert set(seen[:18]) == {None} and set(seen[18:36]) == {0.5} and set(seen[36:]) == {0.25}


def test_window_mae_moves_a_cell_across_the_limit_without_touching_the_other_bounds():
    base = {"R": 1.0, "survival": 64, "envs": 64, "command_mps": 0.1,
            "per_env_R": [1.0] * 64, "per_env_alive_end": [True] * 64}

    def cells(mae):
        row = {**base, "mae_mps": mae, "per_env_mae_mps": [mae] * 64}
        yaw = {"median_abs_rad": .04, "p90_abs_rad": .08, "survival": 64, "envs": 64}
        modes = ("eval_gt", "eval_pred", "probe_prop_only")
        return {"low": {f"L{lv}": {m: {c: {**row} for c in ex42_e1_v2.LOW_CASES} for m in modes} for lv in (0, 5)},
                "side05": {m: {c: {**row, "command_mps": .5} for c in ("side+0.5", "side-0.5")} for m in modes},
                "yaw": {m: {c: yaw.copy() for c in ("fwd0.5", "fwd1.0")} for m in modes}}
    # 0.1 command: limit 0.020; the step MAE 0.024 fails every cell, the window MAE 0 passes
    for cell in (cells(0.024),):
        for lv in ("L0", "L5"):
            for mode in ("eval_gt", "eval_pred"):
                cell["low"][lv][mode]["fwd0.2"].update({"command_mps": .2, "mae_mps": 0.0, "per_env_mae_mps": [0.0] * 64})
                for case in ("side+0.2", "side-0.2", "side+0.4", "side-0.4"):
                    cell["low"][lv][mode][case].update({"command_mps": float(case[4:]), "mae_mps": 0.0,
                                                        "per_env_mae_mps": [0.0] * 64})
        for mode in ("eval_gt", "eval_pred"):
            for case in ("side+0.5", "side-0.5"):
                cell["side05"][mode][case].update({"mae_mps": 0.0, "per_env_mae_mps": [0.0] * 64})
        failed = judge_cells(cell, PLAN)
        assert failed["items"]["low/L0/eval_gt/fwd0.1"]["judgement"] == "FAIL"
        cell["low"]["L0"]["eval_gt"]["fwd0.1"].update({"mae_mps": 0.0, "per_env_mae_mps": [0.0] * 64})
        fixed = judge_cells(cell, PLAN)
        assert fixed["items"]["low/L0/eval_gt/fwd0.1"]["judgement"] == "PASS"
        assert fixed["items"]["low/L0/eval_gt/fwd0.1"]["success"] == 64


M500 = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261115_135412/main/EX-42-B-E1-v29c_20261115_135412/eval/scores/m500")


@pytest.mark.skipif(not M500.is_dir(), reason="read-only v29c m500 score absent on this machine")
def test_real_m500_step_mae_reproduces_the_official_value_and_the_window_is_new():
    score = json.loads((M500 / "ex42_score.json").read_text())
    legacy = measure_cells(M500, score["checkpoint_sha256"], 42)
    assert abs(legacy["low"]["L0"]["eval_gt"]["fwd0.1"]["mae_mps"] - 0.0338387) < 1e-6      # the official 0.0338
    assert ex42_e1_v2.canonical_evidence(legacy) == ex42_e1_v2.canonical_evidence(score["e1_v2_cells"])
    window = measure_cells(M500, score["checkpoint_sha256"], 42, mae_window_s=0.5)
    cell = window["low"]["L0"]["eval_gt"]["fwd0.1"]
    assert cell["per_env_mae_step_mps"] == legacy["low"]["L0"]["eval_gt"]["fwd0.1"]["per_env_mae_mps"]
    assert cell["mae_mps"] < cell["mae_step_mps"]
    side = window["low"]["L0"]["eval_gt"]["side+0.2"]                  # vy cells are not windowed
    assert side == legacy["low"]["L0"]["eval_gt"]["side+0.2"]
