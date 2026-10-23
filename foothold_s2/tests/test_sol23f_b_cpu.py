"""SOL-23f B의 CPU 정답 입력과 변이. Kit과 CUDA는 사용하지 않는다."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.runners.sol23f_runner import BRunner, DeadlineReached, StepEvidence, contact_tangent_stats, material_summary, save_material_array, sha256
from foothold_s2.runners.start_runner import StartRunner


ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "foothold_s2/tasks/s2_23f_b_cfg.py"
AGENT = ROOT / "foothold_s2/tasks/agents/s2_23f_b_ppo_cfg.py"
EX23_AGENT = ROOT / "foothold_s2/tasks/agents/s2_x23_ppo_cfg.py"


def _cfg_from_source(source: str):
    """Kit import 없이 실제 새 cfg의 class body를 가짜 EX23 부모에 대해 실행한다."""
    class Ex23:
        def __post_init__(self):
            self.events = SimpleNamespace(physics_material=SimpleNamespace(mode="startup", params={"old": True}))
            self.other = {"mass": (-1.0, 3.0), "com": None, "delay": False, "reward": "EX23"}

    class Entity:
        def __init__(self, name, body_names):
            self.name, self.body_names = name, body_names

    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FootholdS223FBEnvCfg")
    code = compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(CFG), "exec")
    ns = {"FootholdS2X23EnvCfg": Ex23, "SceneEntityCfg": Entity, "configclass": lambda x: x}
    exec(code, ns)
    obj = ns["FootholdS223FBEnvCfg"]()
    obj.__post_init__()
    return obj


def _assert_b(cfg):
    p = cfg.events.physics_material.params
    assert cfg.events.physics_material.mode == "startup"
    assert (p["asset_cfg"].name, p["asset_cfg"].body_names) == ("robot", ".*")
    assert p["static_friction_range"] == p["dynamic_friction_range"] == (0.2, 1.2)
    assert p["restitution_range"] == (0.0, 0.0)
    assert p["num_buckets"] == 64 and p["make_consistent"] is True
    assert cfg.other == {"mass": (-1.0, 3.0), "com": None, "delay": False, "reward": "EX23"}


def test_b_only_changes_startup_robot_friction():
    source = CFG.read_text(encoding="utf-8")
    _assert_b(_cfg_from_source(source))
    cls = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))
    writes = [ast.unparse(node.targets[0]) for node in ast.walk(cls) if isinstance(node, ast.Assign)]
    assert writes == ["self.events.physics_material.params"]


def test_b_friction_mutation_is_caught():
    source = CFG.read_text(encoding="utf-8")
    mutant = source.replace('"dynamic_friction_range": (0.2, 1.2)', '"dynamic_friction_range": (0.8, 0.8)')
    assert mutant != source
    with pytest.raises(AssertionError):
        _assert_b(_cfg_from_source(mutant))


def test_b_agent_inherits_ex23_without_ppo_override():
    source = AGENT.read_text(encoding="utf-8")
    cls = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))
    assert ast.unparse(cls.bases[0]) == "S2X23PPORunnerCfg"
    assert [target.id for node in cls.body if isinstance(node, ast.Assign) for target in node.targets] == ["experiment_name"]
    ex23 = EX23_AGENT.read_text(encoding="utf-8")
    assert '"force_gt": True' in ex23 and '"map_input": "reconstruction"' in ex23


def test_foot_xy_known_input_and_no_contact():
    velocity = torch.tensor([[[3.0, 4.0, 2.0], [9.0, 0.0, 0.0]]])
    force = torch.tensor([[[0.0, 0.0, 2.0], [0.0, 0.0, 0.0]]])
    speed, count = contact_tangent_stats(velocity, force)
    assert (speed.item(), count.item()) == (5.0, 1)
    with pytest.raises(ValueError, match="shape"):
        contact_tangent_stats(velocity, force[..., :2])


def test_termination_receipt_pre_reset(tmp_path):
    names = ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
    robot = SimpleNamespace(body_names=["base", *names], data=SimpleNamespace(
        body_lin_vel_w=torch.tensor([[[0., 0., 0.], [3., 4., 0.], [0., 0., 0.], [0., 0., 0.], [0., 0., 0.]]]),
        joint_pos=torch.zeros(1, 12)))
    sensor = SimpleNamespace(body_names=names, data=SimpleNamespace(
        net_forces_w=torch.tensor([[[0., 0., 2.], [0., 0., 0.], [0., 0., 0.], [0., 0., 0.]]])))
    class Manager:
        active_terms = ["time_out", "foot_below_ground"]
        def compute(self):
            return torch.tensor([True])
        def get_term(self, name):
            return torch.tensor([name == "foot_below_ground"])
    env = SimpleNamespace(device="cpu", step_dt=0.02, termination_manager=Manager(), scene=SimpleNamespace(sensors={"contact_forces": sensor}))
    class Scene:
        sensors = {"contact_forces": sensor}
        def __getitem__(self, name):
            assert name == "robot"
            return robot
    env.scene = Scene()
    evidence = StepEvidence(env, str(tmp_path))
    assert env.termination_manager.compute().item() is True
    row = evidence.flush(0)
    assert row["termination_counts"] == {"time_out": 0, "foot_below_ground": 1}
    assert row["foot_xy_tangent_speed_mean_mps"] == 5.0
    assert row["contact_foot_xy_path_m"] == pytest.approx(0.1)
    assert row["contact_foot_duration_s"] == pytest.approx(0.02)
    assert evidence.flush(1)["termination_counts"]["foot_below_ground"] == 0


def test_contact_xy_integral_and_done_exclusion():
    velocities = torch.tensor([[[3., 4., 0.]], [[9., 0., 0.]]])
    forces = torch.tensor([[[0., 0., 2.]], [[0., 0., 2.]]])
    speed, count = contact_tangent_stats(velocities, forces, torch.tensor([True, False]))
    assert (speed.item(), count.item()) == (5.0, 1)
    dt = 0.02
    assert speed.item() * dt == 0.1
    assert count.item() * dt == 0.02


def test_realized_physx_material_summary_and_mutant():
    samples = torch.tensor([[[0.8, 0.6, 0.0]], [[0.2, 0.2, 0.0]]])
    row = material_summary(samples)
    assert row["envs"] == 2 and row["shapes_per_env"] == 1
    assert row["static_min"] == pytest.approx(0.2)
    assert row["dynamic_le_static_all"] is True
    samples[1, 0, 1] = 0.9
    assert material_summary(samples)["dynamic_le_static_all"] is False


def test_full_physx_material_file_retains_each_shape(tmp_path):
    import numpy as np

    samples = torch.tensor([[[0.8, 0.6, 0.0], [0.7, 0.5, 0.0]], [[0.2, 0.2, 0.0], [1.2, 1.0, 0.0]]])
    row = save_material_array(samples, tmp_path)
    path = tmp_path / row["array_file"]
    assert row["array_sha256"] == sha256(path)
    assert row["array_shape"] == [2, 2, 3]
    assert np.array_equal(np.load(path, allow_pickle=False), samples.numpy())
    # A range summary cannot reveal this changed interior cell; the array SHA does.
    changed = samples.clone()
    changed[0, 1, 0] = 0.65
    assert material_summary(changed)["static_min"] == material_summary(samples)["static_min"]
    assert save_material_array(changed, tmp_path)["array_sha256"] != row["array_sha256"]


def test_deadline_saves_completed_iteration_atomically(monkeypatch, tmp_path):
    monkeypatch.setattr(StartRunner, "log", lambda self, locs, width=80, pad=35: None)
    runner = object.__new__(BRunner)
    runner.log_dir = str(tmp_path)
    runner.env = SimpleNamespace(num_envs=3072)
    runner.evidence = None
    runner.deadline_epoch = 0
    runner.stop_file = None
    runner.state_dict = lambda infos=None: {"iter": 3}
    runner._manifest_checkpoint = lambda *args: None
    runner.save_latest = lambda: None
    with pytest.raises(DeadlineReached, match='"iter": 3'):
        runner.log({"it": 3})
    assert torch.load(tmp_path / "model_3.pt", weights_only=True) == {"iter": 3}
    assert not (tmp_path / "model_3.pt.tmp").exists()
