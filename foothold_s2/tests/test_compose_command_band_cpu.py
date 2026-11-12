"""The composite's command strip is drawn from the recorded per-step command, never from the evaluation phase list."""
import hashlib

import numpy as np
import pytest

from foothold_s2.eval.video25 import compose_25e_v2style10 as c

BACKGROUND = (18, 22, 27)
STEPS, DT = 650, 0.02
PHASES = [{"name": "settle", "target": [0, 0, 0], "start_s": 0.0, "duration_s": 1.0},
          {"name": "approach", "target": [1, 0, 0], "start_s": 1.0, "duration_s": 4.0},
          {"name": "hold", "target": [0, 0, 0], "start_s": 5.0, "duration_s": 2.0},
          {"name": "restart", "target": [1, 0, 0], "start_s": 7.0, "duration_s": 6.0}]


def trace():
    cmd = np.zeros((STEPS, 3), np.float32)
    cmd[50:115, 0] = 1.0          # forward stops at 2.3 s although the approach phase runs to 5 s
    cmd[350:471, 0] = 1.0
    return cmd


def zdict(cmd):
    return {"command": cmd, "t": np.arange(STEPS) * DT, "seg": np.repeat(np.arange(4), [50, 200, 100, 300]).astype(np.int8),
            "foot_contact": np.ones((STEPS, 4), bool), "vx": cmd[:, 0], "wz": cmd[:, 2]}


def band(cmd, **kw):
    z = zdict(cmd)
    curves = {"vx_cmd": cmd[:, 0], "vx": cmd[:, 0], "wz_cmd": cmd[:, 2], "wz": cmd[:, 2]}
    return c.draw_bottom(z, 300, curves, STEPS * DT, PHASES, **kw)


def blocks(img):
    row = img[20]
    on = np.any(row != np.array(BACKGROUND, np.uint8), axis=1)
    edges = np.flatnonzero(np.diff(on.astype(np.int8)) == 1) + 1
    return [int(x) for x in edges if x >= c.BOTTOM_GRAPH_X - 2]


def test_strip_blocks_start_at_the_recorded_command_changes_not_at_phase_edges():
    cmd = trace()
    img = band(cmd)
    changes = [0, *(np.flatnonzero(np.any(cmd[1:] != cmd[:-1], axis=1)) + 1).tolist()]
    width = 1880 - c.BOTTOM_GRAPH_X
    expected = [c.BOTTOM_GRAPH_X + int(k * DT / (STEPS * DT) * width) for k in changes]
    assert len(changes) == 5 and blocks(img) == expected


def test_strip_colour_follows_the_command_value():
    img = band(trace())
    x_stop = c.BOTTOM_GRAPH_X + int(70 * DT / (STEPS * DT) * (1880 - c.BOTTOM_GRAPH_X))     # step 70: forward 1.0
    x_zero = c.BOTTOM_GRAPH_X + int(200 * DT / (STEPS * DT) * (1880 - c.BOTTOM_GRAPH_X))    # step 200: stopped
    assert tuple(img[20, x_stop]) == c.command_block_color([1, 0, 0], False)
    assert tuple(img[20, x_zero]) == c.command_block_color([0, 0, 0], True)      # row 300 lies in this run
    assert c.command_block_color([1, 0, 0], False) != c.command_block_color([0, 0, 0], False)


def test_runs_expand_back_to_the_trace_and_any_one_step_difference_fails():
    cmd = trace()
    runs = c.command_runs_from_trace(cmd, np.arange(STEPS) * DT)
    c.assert_runs_match_trace(runs, cmd)
    shifted = [dict(r) for r in runs]
    shifted[1]["rows"] = (shifted[1]["rows"][0], shifted[1]["rows"][1] + 1)       # one step too long, gap in tiling
    with pytest.raises(ValueError, match="tile"):
        c.assert_runs_match_trace(shifted, cmd)
    moved = [dict(r) for r in runs]
    moved[1]["rows"] = (moved[1]["rows"][0] + 1, moved[1]["rows"][1])
    moved[0]["rows"] = (0, moved[0]["rows"][1] + 1)                                # boundary moved by one step
    with pytest.raises(ValueError, match="differs"):
        c.assert_runs_match_trace(moved, cmd)
    blip = cmd.copy()
    blip[200, 0] = 0.5                                                             # a single-step command change
    blip_runs = c.command_runs_from_trace(blip, np.arange(STEPS) * DT)
    assert len(blip_runs) == len(runs) + 2
    c.assert_runs_match_trace(blip_runs, blip)
    with pytest.raises(ValueError, match="differs"):
        c.assert_runs_match_trace(runs, blip)


def test_phase_drawn_strip_is_caught_by_the_block_test():
    cmd = trace()
    phase_blocks = blocks(band(cmd, command_runs=False))
    changes = 1 + int(np.count_nonzero(np.any(cmd[1:] != cmd[:-1], axis=1)))
    assert len(phase_blocks) == 4 and len(phase_blocks) != changes                 # what the old phase strip looked like


def test_receipt_names_the_cmd_trace_sha256(tmp_path):
    cmd = trace()
    (tmp_path / "review_feet.npz").write_bytes(b"x")
    entry = c.command_band_receipt(tmp_path, zdict(cmd), True)
    assert entry["cmd_trace_sha256"] == hashlib.sha256(np.ascontiguousarray(cmd).tobytes()).hexdigest()
    assert entry["review_feet_sha256"] and len(entry["runs"]) == 5
    assert c.command_band_receipt(tmp_path, zdict(cmd), False) == {"source": "phase_blocks"}


def test_drawing_refuses_a_strip_that_was_built_from_phases(monkeypatch):
    def phase_runs(cmd, t):
        return [dict(p, rows=(int(p["start_s"] / DT), int((p["start_s"] + p["duration_s"]) / DT))) for p in PHASES]
    monkeypatch.setattr(c, "command_runs_from_trace", phase_runs)
    with pytest.raises(ValueError, match="differs"):
        band(trace())
