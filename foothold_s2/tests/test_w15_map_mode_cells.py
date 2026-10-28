"""W15 CPU contract: command cells, 64-env terrain receipts and shell wiring."""

from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import map_mode_cells as cells


ROOT = Path(__file__).resolve().parents[2]


def test_extended_command_cells_are_literal_and_core_is_unchanged():
    core = cells.commands("core")
    extended = cells.commands("extended")
    assert len(core) == 4 and len(extended) == 13
    assert all(extended[k] == v for k, v in core.items())
    assert extended["back0.5"] == (-0.5, 0.0, 0.0)
    assert extended["back1.0"] == (-1.0, 0.0, 0.0)
    assert extended["side+0.5"] == (0.0, 0.5, 0.0)
    assert extended["side-0.5"] == (0.0, -0.5, 0.0)
    assert extended["stop"] == (0.0, 0.0, 0.0)
    assert sum(k.startswith("diag-") for k in extended) == 4
    assert cells.SEQUENCES["spin_left_to_right"] == ((0, 0, 1.2), (0, 0, -1.2))
    assert cells.SEQUENCES["spin_right_to_left"] == ((0, 0, -1.2), (0, 0, 1.2))
    assert cells.SEQUENCES["stop_and_restart"] == ((0, 0, 0), (0.5, 0, 0), (0, 0, 0), (0.5, 0, 0))
    assert cells.phase_steps(300, 4) == [75, 75, 75, 75]
    with pytest.raises(ValueError):
        cells.commands("invented")


def test_reverse_and_side_projection_use_command_direction():
    tiles = cells.terrain_rows([0, 0], [0, 1], ["gap", "stones"])
    alive = np.ones((3, 2), dtype=bool)
    vx = np.array([[-0.5, 0], [-0.5, 0], [-0.5, 0]])
    vy = np.array([[0, -0.5], [0, -0.5], [0, -0.5]])
    wz = np.zeros((3, 2))
    reverse = cells.summarize((-0.5, 0, 0), tiles, vx, vy, wz, alive, [True, True], 0.02)
    side = cells.summarize((0, -0.5, 0), tiles, vx, vy, wz, alive, [True, True], 0.02)
    assert reverse["per_env"][0]["command_xy_projection_integral_m"] == pytest.approx(0.03)
    assert side["per_env"][1]["command_xy_projection_integral_m"] == pytest.approx(0.03)
    assert reverse["by_kind"]["gap"]["env_count"] == 1
    assert reverse["per_env"][0]["vx_abs_error_mean_alive_mps"] == 0
    assert side["per_env"][1]["vy_abs_error_mean_alive_mps"] == 0
    stop = cells.summarize((0, 0, 0), tiles, vx, vy, wz, alive, [True, True], 0.02)
    assert stop["per_env"][0]["command_xy_projection_integral_m"] is None


def test_64_env_by_kind_and_terminal_survival_are_not_aliased():
    tiles = cells.terrain_rows(np.arange(64) % 3, np.arange(64) % 2, ["gap", "stones"])
    alive_samples = np.ones((2, 64), dtype=bool)
    final = np.ones(64, dtype=bool)
    final[9] = False
    data = cells.summarize((0.5, 0, 0), tiles, np.ones((2, 64)),
                           np.zeros((2, 64)), np.zeros((2, 64)), alive_samples, final, 0.02)
    assert data["env_count"] == len(data["per_env"]) == 64
    assert sum(x["env_count"] for x in data["by_kind"].values()) == 64
    assert sum(x["env_count"] for x in data["by_kind_level"].values()) == 64
    assert data["per_env"][9]["samples_alive"] == 2
    assert data["per_env"][9]["alive_at_end"] is False
    assert sum(x["alive_at_end"] for x in data["by_kind"].values()) == 63
    with pytest.raises(ValueError):
        cells.summarize((0.5, 0, 0), tiles[:-1], np.ones((2, 64)),
                        np.zeros((2, 64)), np.zeros((2, 64)), alive_samples, final, 0.02)


def test_spin_drift_and_restart_response_are_descriptive_not_gates():
    tiles = cells.terrain_rows([0], [0], ["gap"])
    samples = np.ones((3, 1), dtype=bool)
    spin = cells.summarize((0, 0, -1.2), tiles, np.zeros((3, 1)), np.zeros((3, 1)),
                           np.array([[0], [-0.5], [-1.0]]), samples, [True], 0.02,
                           [[0, 0]], [[0.03, 0.04]], [[[0.01, 0]], [[0.03, 0]], [[0.03, 0.04]]])
    assert spin["per_env"][0]["world_xy_displacement_m"] == pytest.approx(0.05)
    assert spin["per_env"][0]["world_xy_path_m"] == pytest.approx(0.07)
    assert cells.response_times((0, 0, -1.2), np.zeros((3, 1)), np.zeros((3, 1)),
                                np.array([[0], [-0.5], [-1.0]]), samples, 0.02)[0]["yaw_sign_response_s"] == 0.02
    restart = cells.response_times((0.5, 0, 0), np.array([[0], [0.1], [0.3]]),
                                   np.zeros((3, 1)), np.zeros((3, 1)), samples, 0.02)
    assert restart[0]["half_speed_response_s"] == 0.04
    assert cells.response_times((0, 0, 0), np.zeros((3, 1)), np.zeros((3, 1)),
                                np.zeros((3, 1)), samples, 0.02)[0]["half_speed_response_s"] is None


def test_kit_entry_and_chain_are_wired_without_running_kit():
    eval_src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    chain = (ROOT / "foothold_s2/eval/run_sb_eval.sh").read_text(encoding="utf-8")
    for token in ('--command-suite', 'map_mode_cells.commands(args.command_suite)',
                  'map_mode_cells.terrain_rows(', 'map_mode_cells.summarize(',
                  '"terrain_tiles"', '"terrain_columns"', 'VY[k]'):
        assert token in eval_src
    assert 'map_mode_cells.SEQUENCES.items()' in eval_src
    assert '"sequences"' in eval_src
    assert 'eval_gt probe_prop_only eval_pred' in chain
    assert '--command-suite "$COMMAND_SUITE"' in chain
    assert '--envs 64 --steps 300' in chain
