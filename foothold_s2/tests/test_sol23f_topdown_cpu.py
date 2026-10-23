"""SOL-23f TopDown의 논문 축과 작업가정 분리 CPU 정답/변이."""

import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType

import numpy as np
import pytest
import torch

from foothold_s2.rewards import core
from foothold_s2.tasks.s2_23f_camera import camera_intrinsic_fx, quat_apply, randomize_topdown_camera
from foothold_s2.tasks.s2_23f_spawn import DEPARTURE, EDGE_MARGIN_M, correct_topdown_spawn, supported_departure_xy
from foothold_s2.tasks.s2_23f_termination import below_plane, world_support_plane
from foothold_s2.terrains import columns, sol23f_topdown, progression
from foothold_s2.terrains.s2_layout import Layout


ROOT = Path(__file__).resolve().parents[2]


def _assert_topdown_mix(proportions):
    assert sum(proportions.values()) == pytest.approx(1.0)
    assert proportions["gaps"] == pytest.approx(0.10)
    assert proportions["stepping_stones_low"] == proportions["flat"]
    assert len({proportions[n] for n in ("stepping_stones_high", "balance_beams", "stepping_beams")}) == 1
    assert columns.column_assignment(proportions, 30) == {
        "stepping_stones_low": 5, "flat": 4, "stepping_stones_high": 6,
        "balance_beams": 6, "stepping_beams": 6, "gaps": 3,
    }


def test_sparse_only_mix_and_mutation():
    proportions = sol23f_topdown.PROPORTIONS
    _assert_topdown_mix(proportions)
    mutant = dict(proportions, gaps=0.0)
    with pytest.raises(AssertionError):
        _assert_topdown_mix(mutant)
    layout = Layout(proportions, sol23f_topdown.NUM_COLS)
    assert len(layout.easy_cols) == 9 and len(layout.hard_cols) == 18
    assert (layout.group_by_col == "gap").sum() == 3
    assert (layout.group_by_col == "continuous").sum() == 0


def test_topdown_side_table_binds_all_300_cells_including_flat():
    table = sol23f_topdown.TopDownSideTable()
    names = Layout(sol23f_topdown.PROPORTIONS, 30).names
    for kind in names:
        for row in range(10):
            difficulty = (row + 0.5) / 10
            # A small synthetic tile proves the binder handles names excluded by old KINDS.
            tile = sol23f_topdown.sparse_terrains.TileData(
                kind, "gap" if kind == "gaps" else "sparse", row,
                np.array([[0., 8., 0., 4., -0.2, 0.]]), np.array([0.5, 2., 0.]),
                np.zeros((4, 2)), np.zeros((1, 1), bool), np.zeros((1, 1), bool))
            table.record(kind, difficulty, tile)
    table.bind_all(names, 10)
    assert len(table.by_cell) == 300
    assert any(row["kind"] == "flat" for row in table.by_cell.values())
    assert np.allclose(table.by_cell[(0, 0)]["origin_world"], [0.5 - 40.0, 2.0 - 60.0])
    assert np.allclose(table.by_cell[(0, 0)]["flags_world"][0], [0.0 - 40.0, 0.0 - 60.0])
    table.calls.pop()
    with pytest.raises(RuntimeError, match="missing TopDown tile"):
        sol23f_topdown.TopDownSideTable.bind_all(table, names, 10)


@pytest.mark.parametrize("kind", list(sol23f_topdown.PROPORTIONS))
def test_true_8_by_4_geometry_and_masks(kind):
    tile = sol23f_topdown.make_tile(kind, 0.95)
    assert tile.level == 9
    assert tile.inner.shape == tile.outer.shape == (320, 160)
    assert np.all(tile.boxes[:, 0] >= 0) and np.all(tile.boxes[:, 1] <= 8)
    assert np.all(tile.boxes[:, 2] >= 0) and np.all(tile.boxes[:, 3] <= 4)
    assert tile.flags.shape == (4, 2)
    assert tile.group == ("gap" if kind == "gaps" else "sparse")
    assert np.all(tile.outer[tile.inner])


def test_start_progression_keeps_gap_and_uses_both_easy_hard():
    layout = Layout(sol23f_topdown.PROPORTIONS, 30)
    gap = int(np.flatnonzero(layout.group_by_col == "gap")[0])
    types = np.array([gap, int(layout.easy_cols[0]), int(layout.hard_cols[0])])
    groups = layout.group_by_col[types]
    low = progression.reassign_columns(np.random.default_rng(1), groups, layout.easy_cols, layout.hard_cols,
                                       1000, p_max=0.9, T_start=1000, T_end=8000)
    high = progression.reassign_columns(np.random.default_rng(1), groups, layout.easy_cols, layout.hard_cols,
                                        8000, p_max=0.9, T_start=1000, T_end=8000)
    assert low[0] == high[0] == -1
    assert all(x in layout.easy_cols for x in low[1:])
    assert all(x in np.r_[layout.easy_cols, layout.hard_cols] for x in high[1:])
    assert progression.p_advance(8000) == pytest.approx(0.9)
    assert progression.p_advance(1000) == 0.0
    assert progression.p_advance(4500) == pytest.approx(0.45)


def test_camera_fov_and_position_known_input():
    fx = camera_intrinsic_fx(torch.tensor([87.0]))
    assert 55.0 < fx.item() < 57.0
    q = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    v = torch.tensor([[0.25, 0.0, 0.12]])
    assert torch.allclose(quat_apply(q, v), v)


def test_camera_event_changes_only_selected_sensor_rows():
    class Camera:
        def __init__(self):
            self._data = SimpleNamespace(intrinsic_matrices=torch.eye(3).repeat(2, 1, 1))
            self._offset_pos = torch.zeros(2, 3)
            self._offset_quat = torch.tensor([[1., 0., 0., 0.]] * 2)
            self.resets = []
            self.outdated = False
            self.ray_fx = torch.ones(2)
            self.rendered_fx = []
        @property
        def data(self):
            if self.outdated:
                self.rendered_fx.append(self.ray_fx.clone())
                self.outdated = False
            return self._data
        def reset(self, ids):
            self.resets.append(ids.clone())
            self.outdated = True
        def set_intrinsic_matrices(self, matrices, env_ids):
            self._data.intrinsic_matrices[env_ids] = matrices
            self.ray_fx[env_ids] = matrices[:, 0, 0]
    camera = Camera()
    robot = SimpleNamespace(data=SimpleNamespace(root_pos_w=torch.zeros(2, 3),
                                                   root_quat_w=torch.tensor([[1., 0., 0., 0.]] * 2)))
    class Scene:
        sensors = {"depth_cam": camera}
        def __getitem__(self, name):
            return robot
    env = SimpleNamespace(device="cpu", scene=Scene())
    torch.manual_seed(7)
    randomize_topdown_camera(env, torch.tensor([1]))
    assert camera.resets[0].tolist() == [1]
    assert camera.rendered_fx == [] and camera.outdated
    first_frame_fx = camera.data.intrinsic_matrices[1, 0, 0]
    assert camera.rendered_fx[0][1] == first_frame_fx
    assert not camera.outdated
    assert torch.allclose(camera._offset_pos[0], torch.zeros(3))
    assert camera._offset_pos[1].shape == (3,)
    assert 0.24 <= camera._offset_pos[1, 0].item() <= 0.26
    assert torch.allclose(camera.data.intrinsic_matrices[0], torch.eye(3))
    assert 53.0 < camera.data.intrinsic_matrices[1, 0, 0].item() < 59.0


def test_randomized_joint_departure_spawns_keep_four_feet_supported():
    from foothold_s2.robots import go2_kinematics as fk

    for kind in sol23f_topdown.PROPORTIONS:
        for row in range(10):
            box = sol23f_topdown.make_tile(kind, (row + 0.5) / 10).boxes[0]
            assert box[0] <= DEPARTURE[0] and box[1] >= DEPARTURE[1]
            assert box[2] <= DEPARTURE[2] and box[3] >= DEPARTURE[3]
    default = np.asarray(fk.DEFAULT_JOINT_POS)
    q = default.copy()
    chosen = supported_departure_xy(q, np.array([0.85, 2.0]), 0.0)
    assert chosen[0] <= 0.85
    rng = np.random.default_rng(17)
    for _ in range(1000):
        sampled = default * rng.uniform(0.5, 1.5, (4, 3))
        proposed = np.array([rng.uniform(0., 1.), rng.uniform(1.5, 2.5)])
        yaw = rng.uniform(-3.14, 3.14)
        xy = supported_departure_xy(sampled, proposed, yaw)
        feet = fk.foot_centers(sampled)[:, :2]
        c, s = np.cos(yaw), np.sin(yaw)
        foot_xy = feet @ np.array([[c, s], [-s, c]]) + xy
        assert np.all(foot_xy >= np.array([DEPARTURE[0], DEPARTURE[2]]) + EDGE_MARGIN_M - 1e-6)
        assert np.all(foot_xy <= np.array([DEPARTURE[1], DEPARTURE[3]]) - EDGE_MARGIN_M + 1e-6)


def test_spawn_reset_writes_root_after_randomized_joints_without_changing_joints():
    from foothold_s2.robots import go2_kinematics as fk

    joints = torch.tensor(np.asarray(fk.DEFAULT_JOINT_POS).reshape(1, 12), dtype=torch.float32)
    root = torch.tensor([[0.85, 2.0, 0.4, 1.0, 0.0, 0.0, 0.0]])
    class Robot:
        joint_names = list(fk.JOINT_NAMES)
        def __init__(self):
            self.data = SimpleNamespace(default_joint_pos=joints.clone(), joint_pos=joints.clone(),
                                        root_link_pose_w=root.clone())
        def write_root_pose_to_sim(self, value, env_ids):
            self.data.root_link_pose_w[env_ids] = value
    robot = Robot()
    terrain = SimpleNamespace(env_origins=torch.tensor([[0.5, 2.0, 0.0]]))
    class Scene:
        def __init__(self):
            self.terrain = terrain
        def __getitem__(self, name):
            assert name == "robot"
            return robot
    correct_topdown_spawn(SimpleNamespace(scene=Scene()), torch.tensor([0]))
    assert robot.data.root_link_pose_w[0, 0] < 0.85
    assert torch.equal(robot.data.joint_pos, joints)
    cfg = (ROOT / "foothold_s2/tasks/s2_23f_topdown_cfg.py").read_text(encoding="utf-8")
    assert cfg.index('self.events.reset_robot_joints.params["position_range"]') < cfg.index("self.events.supported_spawn")


def test_topdown_cfg_and_agent_do_not_select_gt_or_added_terrain():
    cfg = (ROOT / "foothold_s2/tasks/s2_23f_topdown_cfg.py").read_text(encoding="utf-8")
    agent = (ROOT / "foothold_s2/tasks/agents/s2_23f_topdown_ppo_cfg.py").read_text(encoding="utf-8")
    common = (ROOT / "foothold_s2/scripts/train_sol23f_common.py").read_text(encoding="utf-8")
    tree = ast.parse(agent)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    attrs = {node.targets[0].id: node.value for node in cls.body if isinstance(node, ast.Assign)}
    attrs.update({node.target.id: node.value for node in cls.body if isinstance(node, ast.AnnAssign)})
    assert ast.literal_eval(attrs["max_iterations"]) == 20000
    perception_values = {ast.literal_eval(k): ast.literal_eval(v)
                         for k, v in zip(attrs["perception"].keys, attrs["perception"].values) if k is not None}
    assert perception_values["force_gt"] is False and perception_values["depth_delay_ticks"] == 0
    assert 'self.rewards.foot_edge.weight = core.WEIGHTS["foot_edge"]' in cfg
    assert 'track_lin_form: str = "A"' in cfg
    assert 'self.events.topdown_camera = EventTerm' in cfg
    assert 'AUG.enabled = False' in common and '"depth_delay_ticks": 0' in agent
    mutant = agent.replace('"force_gt": False', '"force_gt": True')
    mutant_cls = next(node for node in ast.parse(mutant).body if isinstance(node, ast.ClassDef))
    mutant_attrs = {node.target.id: node.value for node in mutant_cls.body if isinstance(node, ast.AnnAssign)}
    mutant_values = {ast.literal_eval(k): ast.literal_eval(v)
                     for k, v in zip(mutant_attrs["perception"].keys, mutant_attrs["perception"].values) if k is not None}
    assert mutant_values["force_gt"] is True


def test_edge_lookup_uses_8_by_4_cell():
    inner = torch.zeros(1, 1, 320, 160, dtype=torch.bool)
    outer = torch.zeros_like(inner)
    inner[0, 0, 40, 40] = True
    outer[0, 0, 40, 40] = True
    feet = torch.tensor([[[1.01, 1.01], [1.01, 5.01]]])
    contact = torch.tensor([[True, True]])
    value = core.foot_edge_penalty_tiles(feet, contact, inner, outer,
                                         torch.tensor([0]), torch.tensor([0]),
                                         size=(8.0, 4.0), resolution=0.025)
    assert value.item() == pytest.approx(1.5)
    centered = feet - torch.as_tensor(sol23f_topdown.WORLD_CENTER_SHIFT)
    centered_value = core.foot_edge_penalty_tiles(
        centered + torch.as_tensor(sol23f_topdown.WORLD_CENTER_SHIFT),
        contact, inner, outer, torch.tensor([0]), torch.tensor([0]),
        size=(8.0, 4.0), resolution=0.025)
    assert centered_value.item() == pytest.approx(1.5)


def test_support_plane_nonzero_transform_and_reset_margin():
    # Local spawn elevation and support surface are distinct.
    plane = world_support_plane(torch.tensor([1.2, 3.2]), 0.4, 0.1)
    assert torch.allclose(plane, torch.tensor([0.9, 2.9]))
    assert below_plane(torch.tensor([[0.60, 0.65], [2.65, 2.64]]), plane, 0.25).tolist() == [True, True]
    assert below_plane(torch.tensor([[0.651, 0.66], [2.651, 2.66]]), plane, 0.25).tolist() == [False, False]
    # Uniform tile z translation preserves the decision; -0.3 vs pit floor -0.5 fires.
    assert below_plane(torch.tensor([[-0.30, 0.2]]), torch.tensor([0.0]), 0.25).item()
    assert below_plane(torch.tensor([[-0.30 + 7, 0.2 + 7]]), torch.tensor([7.0]), 0.25).item()


def test_topdown_motor_scales_pd_before_dc_clip(monkeypatch):
    fake = ModuleType("isaaclab.actuators")
    fake.DCMotor = type("DCMotor", (), {})
    monkeypatch.setitem(sys.modules, "isaaclab.actuators", fake)
    path = ROOT / "foothold_s2/tasks/s2_23f_motor.py"
    spec = importlib.util.spec_from_file_location("test_topdown_motor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    motor = object.__new__(module.TopDownDCMotor)
    motor.stiffness = torch.tensor([[10.]])
    motor.damping = torch.tensor([[1.]])
    motor.strength_scale = torch.tensor([[0.9]])
    motor._joint_vel = torch.zeros(1, 1)
    motor._clip_effort = lambda effort: effort.clamp(-8, 8)
    action = SimpleNamespace(joint_positions=torch.tensor([[0.5]]),
                             joint_velocities=torch.tensor([[0.0]]), joint_efforts=torch.tensor([[0.0]]))
    module.TopDownDCMotor.compute(motor, action, torch.zeros(1, 1), torch.zeros(1, 1))
    assert motor.computed_effort.item() == pytest.approx(5.0)
    assert action.joint_efforts.item() == pytest.approx(4.5)
    assert action.joint_positions is None and action.joint_velocities is None
    # At saturation, scaling before clipping is observably distinct from scaling the limits.
    assert module.scale_before_clip(torch.tensor([[10.]]), torch.tensor([[1.1]]), motor._clip_effort).item() == 8.0
