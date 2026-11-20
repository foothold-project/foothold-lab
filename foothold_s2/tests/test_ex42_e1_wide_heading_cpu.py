"""Known-answer checks for the E1 wide fixed cells: start yaw +x and forward-3.5-m success (팀장 11/15 21:49 ⑤). CPU only."""
import ast
import math
import textwrap
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2.ex42_e1_wide import (CONTINUOUS, FORWARD_SUCCESS_M, _fixed_forward,
                                      forward_reach, kit_commands)

ROOT = Path(__file__).resolve().parents[2]
STEPS, ENVS, DT = 475, 64, .02


def _rows(stop=300):
    return {(kind, 3): {"steps": stop, "dt": DT, "hold_s": .5,
                        "anchors": {"exit_x": 7.5, "exit_bounds_y": [0., 8.]},
                        "origin_m": [4., 4., 0.]} for kind in CONTINUOUS}


def _write(tmp_path, vx, x, y, alive, *, override=None, integral=None):
    kinds = [CONTINUOUS[i % len(CONTINUOUS)] for i in range(ENVS)]
    path = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    np.savez(path, root_x_local_m=x.astype(np.float32), root_y_local_m=y.astype(np.float32),
             alive=alive, vx=vx.astype(np.float32), kind=np.array(kinds),
             terrain_level=np.full(ENVS, 3), terrain_col=np.arange(ENVS) % 23,
             assignment_sha256="known-assignment", dt=DT, alive_end=alive[-1],
             alive_steps=alive.sum(0),
             body_vx_integral_m=(((vx * alive).sum(0) * DT) if integral is None else integral).astype(np.float32))
    doc = {"env_arrays": {"eval_gt/fwd1.0": path.name},
           "fixed_terrain": {"assignment_sha256": "known-assignment"},
           "terrain_tiles": [{"env": i, "kind": kind, "level": 3, "column": i % 23}
                             for i, kind in enumerate(kinds)]}
    if override is not None:
        doc["start_yaw_override"] = override
    return doc


def _eight_way_walk(distance_m=6., speed=1.):
    """Eight start headings, eight envs each, every robot walks straight along its own heading (known answer)."""
    heading = np.repeat(np.arange(8) * math.pi / 4, 8)
    walk = int(round(distance_m / (speed * DT)))
    vx = np.zeros((STEPS, ENVS))
    vx[:walk] = speed
    along = np.cumsum(vx, axis=0) * DT
    return vx, along * np.cos(heading), along * np.sin(heading), np.ones((STEPS, ENVS), dtype=bool)


def test_eight_start_directions_all_pass_the_new_rule_and_only_plus_x_pass_the_old_rule(tmp_path):
    vx, x, y, alive = _eight_way_walk()
    doc = _write(tmp_path, vx, x, y, alive)
    old = _fixed_forward(tmp_path, doc, "eval_gt", 3, _rows())
    # old rule: exit line 3.5 m along +x inside the 8 m wide tile; headings 0 and +-45 deg reach it, the other five never do
    assert old["success_count"] == 24 and "success_rule" not in old
    assert "forward_m" not in old["per_env"][0]
    new = _fixed_forward(tmp_path, doc, "eval_gt", 3, _rows(), rule="heading_forward")
    assert new["success_count"] == 64 and new["survival_count"] == 64
    assert new["success_rule"] == f"heading_forward_{FORWARD_SUCCESS_M}m"
    assert all(abs(r["forward_m"] - 6.) < 1e-3 for r in new["per_env"])
    # the evaluation that set start yaw to +x declares it, and then the new rule is the default
    declared = _fixed_forward(tmp_path, _write(tmp_path, vx, x, y, alive, override=0.0), "eval_gt", 3, _rows())
    assert declared["success_count"] == 64 and declared["success_rule"] == new["success_rule"]


def test_boundary_exactly_3p5_m_passes_and_just_below_fails(tmp_path):
    for walk_steps, expected in ((175, 64), (174, 0)):
        vx = np.zeros((STEPS, ENVS))
        vx[:walk_steps] = 1.0
        x = np.cumsum(vx, axis=0) * DT
        doc = _write(tmp_path, vx, x, np.zeros_like(x), np.ones((STEPS, ENVS), dtype=bool))
        row = _fixed_forward(tmp_path, doc, "eval_gt", 3, _rows(stop=475), rule="heading_forward")
        assert row["success_count"] == expected, walk_steps


def test_falling_inside_the_hold_window_is_not_a_success_and_dead_steps_do_not_count(tmp_path):
    vx = np.ones((STEPS, ENVS))
    x = np.cumsum(vx, axis=0) * DT
    alive = np.ones((STEPS, ENVS), dtype=bool)
    alive[200:, 0] = False          # 3.5 m is reached at step 174; falls at 200 (hold ends at 199)
    alive[180:, 1] = False          # falls 6 steps after reaching: inside the 25-step hold
    alive[100:, 2] = False          # dead before 3.5 m (2.0 m): vx while dead must not count
    doc = _write(tmp_path, vx, x, np.zeros_like(x), alive)
    row = _fixed_forward(tmp_path, doc, "eval_gt", 3, _rows(stop=475), rule="heading_forward")
    got = [r["success"] for r in row["per_env"][:3]]
    assert got == [True, False, False]
    assert abs(row["per_env"][2]["forward_m"] - 2.0) < 1e-6


def test_forward_evidence_must_match_the_recorded_integral(tmp_path):
    vx, x, y, alive = _eight_way_walk()
    doc = _write(tmp_path, vx, x, y, alive, integral=np.full(ENVS, 5.0))
    with pytest.raises(ValueError, match="forward evidence differs"):
        _fixed_forward(tmp_path, doc, "eval_gt", 3, _rows(), rule="heading_forward")


def test_forward_reach_uses_the_same_hold_and_window_as_the_old_rule():
    vx = np.ones((475, 1))
    alive = np.ones((475, 1), dtype=bool)
    assert forward_reach(vx, alive, DT, 200, 25)[0][:2] == (174, True)
    assert forward_reach(vx, alive, DT, 199, 25)[0][1] is False       # 174 + 25 is not < 199


def test_only_the_fixed_bundle_gets_the_yaw_flag_and_the_parser_knows_it(tmp_path):
    from foothold_s2.tests.test_ex42_e1_wide_cpu import _plan
    rows = kit_commands(tmp_path / "model_250.pt", tmp_path / "out", "cuda:1", task="T",
                        plan_path=tmp_path / "plan.yaml", plan=_plan(), mesh_dir=tmp_path / "mesh", seed=42)
    for name, argv in rows:
        assert ("--start-yaw-zero" in argv) == (name != "wide_endpoints"), name
    source = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text()
    assert 'parser.add_argument("--start-yaw-zero", action="store_true"' in source
    assert 'args.start_yaw_zero and ((args.command_suite != "e1_wide_fixed" and not kind_cell)' in source


def test_start_yaw_block_of_the_real_eval_script_sets_yaw_zero_and_keeps_position():
    """Run the real block text from eval_map_modes.py against a stand-in robot with random start yaws."""
    torch = pytest.importorskip("torch")
    text = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text()
    lines = text.splitlines()
    first = next(i for i, line in enumerate(lines) if line.strip().startswith("if args.start_yaw_zero:"))
    last = next(i for i in range(first, len(lines)) if lines[i].strip().startswith("offset = "))
    block = textwrap.dedent("\n".join(lines[first:last]))
    ast.parse(block)

    class Robot:
        def __init__(self, n):
            yaw = torch.rand(n) * 6.2 - 3.1
            quat = torch.stack([torch.cos(yaw / 2), torch.zeros(n), torch.zeros(n), torch.sin(yaw / 2)], 1)
            self.state = torch.cat([torch.rand(n, 3) * 4, quat, torch.rand(n, 6)], 1)

        def write_root_pose_to_sim(self, pose):
            self.state[:, :7] = pose

        def write_root_velocity_to_sim(self, vel):
            self.state[:, 7:] = vel

    robot = Robot(ENVS)
    before = robot.state[:, :3].clone()
    start = robot.state[:, 3:7].clone()
    assert (start[:, 3].abs() > .1).any()

    class Data:
        root_state_w = robot.state

        @property
        def root_quat_w(self):
            return robot.state[:, 3:7]

    robot.data = Data()
    res = {}
    exec(block, {"args": SimpleNamespace(start_yaw_zero=True), "torch": torch, "robot": robot,
                 "dev": "cpu", "res": res})
    assert torch.equal(robot.state[:, :3], before)
    assert torch.allclose(robot.state[:, 3:7], torch.tensor([1., 0., 0., 0.]).repeat(ENVS, 1))
    assert float(robot.state[:, 7:].abs().max()) == 0.0
    assert res["start_yaw_override"] == 0.0
    off = {}
    exec(block, {"args": SimpleNamespace(start_yaw_zero=False), "torch": torch, "robot": robot,
                 "dev": "cpu", "res": off})
    assert off == {}
