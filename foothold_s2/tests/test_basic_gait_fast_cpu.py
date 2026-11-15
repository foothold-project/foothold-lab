"""Known-input checks for the opt-in basic-gait GT-only segment."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import types

import pytest
import torch

from foothold_s2.basic_gait_extend_launch import prepare
from foothold_s2.models.start_perception import PerceptionCfg, StartPerception
from foothold_s2.rewards.basic_gait_bundle import (
    BASELINE,
    E1_CANDIDATE,
    WEIGHT_NAMES,
    apply_settings,
    hip_pos_penalty_l1,
    scheduled_lin_vel_z_weight,
    set_lin_vel_z_weight,
    validate_settings,
)
from foothold_s2.sensors.fast_gt_cfg import disable_depth_camera_for_gt, zero_depth_obs
from foothold_s2.tests.test_basic_gait_extend_cpu import END, parent_fixture


def test_fast_gt_keeps_network_weights_and_actor_input_values():
    torch.manual_seed(31)
    normal = StartPerception(PerceptionCfg(force_gt=True))
    fast = StartPerception(PerceptionCfg(force_gt=True, fast_gt_only=True))
    assert {k: v.shape for k, v in normal.state_dict().items()} == {
        k: v.shape for k, v in fast.state_dict().items()}
    fast.load_state_dict(normal.state_dict())
    normal_optimizer = torch.optim.Adam(normal.parameters(), lr=5e-4)
    next(normal.parameters()).flatten()[0].backward()
    normal_optimizer.step()
    fast_optimizer = torch.optim.Adam(fast.parameters(), lr=5e-4)
    fast_optimizer.load_state_dict(normal_optimizer.state_dict())
    assert len(fast_optimizer.param_groups[0]["params"]) == len(normal_optimizer.param_groups[0]["params"])
    assert len(fast_optimizer.state) == len(normal_optimizer.state) == 1
    fast.trnet.step = lambda *_a: (_ for _ in ()).throw(AssertionError("TR-Net called"))
    n = 2
    hprop = torch.zeros(n, 128)
    hterr = torch.zeros(n, 128)
    hist = torch.randn(n, 10, 45)
    depth = torch.randn(n, 2, 60, 60)
    gt = torch.randn(n, 32, 16)
    flags = torch.ones(n, dtype=torch.bool)
    map_off = torch.tensor([False, True])
    with torch.no_grad():
        _a, _b, ref = normal._advance(hprop, hterr, hist, depth, flags, flags, flags, gt, map_off)
        _a, _b, got = fast._advance(hprop, hterr, hist, depth, flags, flags, flags, gt, map_off)
    for key in ("mu", "logvar", "v", "zf", "zb"):
        torch.testing.assert_close(got[key], ref[key], rtol=0, atol=0)
    assert "refined" not in got
    with pytest.raises(ValueError, match="GT map"):
        fast._advance(hprop, hterr, hist, depth, flags, flags,
                      torch.tensor([True, False]), gt, map_off)


def test_zero_depth_contract_and_camera_removal():
    original = object()
    term = SimpleNamespace(func=original, params={"sensor_cfg": "camera"})
    cfg = SimpleNamespace(scene=SimpleNamespace(depth_cam=object()),
                          observations=SimpleNamespace(depth=SimpleNamespace(depth=term)))
    disable_depth_camera_for_gt(cfg)
    assert cfg.scene.depth_cam is None and term.func is zero_depth_obs and term.params == {}
    result = term.func(SimpleNamespace(num_envs=3, device="cpu"))
    assert result.shape == (3, 3600) and torch.count_nonzero(result) == 0
    with pytest.raises(ValueError, match="original START depth"):
        disable_depth_camera_for_gt(cfg)


def test_reward_defaults_selected_weights_and_reserved_ground_adapter():
    empty = validate_settings({name: None for name in WEIGHT_NAMES}, False, None)
    terms = {name: SimpleNamespace(weight=value) for name, value in BASELINE.items()}
    terms["lin_vel_z"] = SimpleNamespace(weight=-2.0)
    cfg = SimpleNamespace(rewards=SimpleNamespace(**terms))
    apply_settings(cfg, empty)
    assert {name: getattr(cfg.rewards, name).weight for name in BASELINE} == BASELINE
    selected = validate_settings({**E1_CANDIDATE}, True, None)
    assert selected["lin_vel_z_schedule"]
    apply_settings(cfg, {"weights": {k: v for k, v in selected["weights"].items() if k != "hip_pos_penalty"}})
    assert {name: getattr(cfg.rewards, name).weight for name in BASELINE} == {
        k: E1_CANDIDATE[k] for k in BASELINE}
    with pytest.raises(ValueError, match="ground adapter"):
        validate_settings({name: None for name in WEIGHT_NAMES}, False, -0.05)
    with pytest.raises(ValueError, match="invalid basic reward"):
        validate_settings({**{name: None for name in WEIGHT_NAMES}, "track_ang_vel": float("nan")}, False, None)


def test_e1_absolute_update_schedule_and_reward_manager_binding():
    assert [scheduled_lin_vel_z_weight(i) for i in (0, 750, 1500, 3000)] == [-2.0, -1.0, 0.0, 0.0]

    class Manager:
        def __init__(self):
            self.term = SimpleNamespace(weight=-2.0)
            self.calls = []

        def get_term_cfg(self, name):
            assert name == "lin_vel_z"
            return self.term

        def set_term_cfg(self, name, term):
            self.calls.append((name, term.weight))

    mgr = Manager()
    env = SimpleNamespace(unwrapped=SimpleNamespace(reward_manager=mgr))
    assert set_lin_vel_z_weight(env, 1501) == 0.0
    assert mgr.calls == [("lin_vel_z", 0.0)]


def test_hip_l1_binding_matches_installed_go2_parameters(monkeypatch):
    isaac_managers = types.ModuleType("isaaclab.managers")
    isaac_managers.RewardTermCfg = lambda **kw: SimpleNamespace(**kw)
    isaac_managers.SceneEntityCfg = lambda name, **kw: SimpleNamespace(name=name, **kw)
    monkeypatch.setitem(sys.modules, "isaaclab.managers", isaac_managers)
    cfg = SimpleNamespace(rewards=SimpleNamespace())
    settings = validate_settings({"track_ang_vel": None, "track_lin_vel": None,
                                  "joint_acc": None, "hip_pos_penalty": -0.05}, False, None)
    apply_settings(cfg, settings)
    term = cfg.rewards.basic_hip_pos_penalty_l1
    assert term.weight == -0.05 and term.func is hip_pos_penalty_l1
    assert term.params["asset_cfg"].joint_names == ".*_hip_joint"
    assert term.params["command_name"] == "base_velocity"
    assert term.params["stand_still_scale"] == 1.0 and term.params["command_threshold"] == 0.1


def test_hip_l1_matches_e1_formula_known_commands_and_joint_indices():
    asset = SimpleNamespace(data=SimpleNamespace(
        joint_pos=torch.tensor([[0.4, 8.0, -0.2], [0.1, 7.0, 0.3]]),
        default_joint_pos=torch.tensor([[0.0, 8.0, 0.0], [0.0, 7.0, 0.0]])))
    commands = torch.tensor([[1.0, 0.2, 0.0], [1.0, 0.0, 0.0]])
    env = SimpleNamespace(
        scene={"robot": asset},
        command_manager=SimpleNamespace(get_command=lambda name: commands))
    cfg = SimpleNamespace(name="robot", joint_ids=[0, 2])
    got = hip_pos_penalty_l1(env, "base_velocity", cfg, 0.5, 0.1)
    torch.testing.assert_close(got, torch.tensor([0.6, 0.2]), rtol=0, atol=1e-6)


def test_training_reward_bundle_call_uses_local_hip_function(monkeypatch):
    isaac_managers = types.ModuleType("isaaclab.managers")
    isaac_managers.RewardTermCfg = lambda **kw: SimpleNamespace(**kw)
    isaac_managers.SceneEntityCfg = lambda name, **kw: SimpleNamespace(name=name, **kw)
    monkeypatch.setitem(sys.modules, "isaaclab.managers", isaac_managers)
    cfg = SimpleNamespace(rewards=SimpleNamespace(**{
        name: SimpleNamespace(weight=value) for name, value in BASELINE.items()}))
    args = SimpleNamespace(basic_track_ang_weight=1.0, basic_track_lin_weight=2.0,
                           basic_joint_acc_weight=-1e-7, basic_hip_pos_weight=-0.05,
                           basic_lin_vel_z_schedule=True, basic_feet_regulation_weight=None)
    source = Path(__file__).resolve().parents[1] / "scripts" / "train_sol23f_common.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "basic_reward_bundle" for t in node.targets)]
    assert len(matches) == 1
    expression = compile(ast.Expression(matches[0].value), str(source), "eval")
    bundle = eval(expression, {"apply_settings": apply_settings, "validate_settings": validate_settings,
                               "env_cfg": cfg, "args_cli": args})
    assert bundle["weights"] == E1_CANDIDATE
    assert cfg.rewards.basic_hip_pos_penalty_l1.func is hip_pos_penalty_l1


def test_isaac311_imports_new_cpu_modules_without_extra_sys_path():
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    modules = (
        "foothold_s2.rewards.basic_gait_bundle",
        "foothold_s2.commands.basic_levels",
        "foothold_s2.basic_gait_run",
        "foothold_s2.basic_gait_launch",
        "foothold_s2.sol23f_contract",
        "foothold_s2.runners.start_runner",
        "foothold_s2.sensors.fast_gt_cfg",
        "foothold_s2.basic_gait_extend_launch",
    )
    code = "\n".join(f"import {name}" for name in modules)
    code += (
        "\nimport ast, importlib.util\nfrom pathlib import Path\n"
        "assert importlib.util.find_spec('robot_lab') is None\n"
        "tree = ast.parse(Path('foothold_s2/scripts/train_sol23f_common.py').read_text(encoding='utf-8'))\n"
        "found = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) "
        "and node.module == 'foothold_s2.rewards.basic_gait_bundle']\n"
        "assert len(found) == 1\n"
        "exec(compile(ast.Module(body=found, type_ignores=[]), '<training-reward-import>', 'exec'))\n"
        "assert callable(apply_settings) and callable(validate_settings)\n"
    )
    python = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
    result = subprocess.run([str(python), "-c", code], cwd=root, env=env,
                            text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stderr


def test_fast_launch_receipt_and_forbidden_adapter(tmp_path):
    checkpoint, digest, _ = parent_fixture(tmp_path, "B")
    args, receipt = prepare("B", "cuda:1", str(checkpoint), digest, 500, END,
                            str(tmp_path / "extend"), fast_gt_only=True,
                            reward_weights={"track_ang_vel": 1.0, "track_lin_vel": 2.0,
                                            "joint_acc": -1e-7, "hip_pos_penalty": None},
                            lin_vel_z_schedule=True)
    assert "--fast-gt-only" in args and "--basic-lin-vel-z-schedule" in args
    assert args[args.index("--basic-track-ang-weight") + 1] == "1.0"
    assert receipt["perception_network_shape_changed"] is False
    assert receipt["training_started"] is False
    assert receipt["reward_bundle"]["weights"]["track_lin_vel"] == 2.0
    with pytest.raises(ValueError, match="ground adapter"):
        prepare("B", "cuda:1", str(checkpoint), digest, 500, END,
                str(tmp_path / "extend"), feet_regulation_weight=-0.05)


def test_fast_shell_dry_keeps_training_off_and_receipt_explicit(tmp_path):
    shell = Path("C:/Program Files/Git/bin/bash.exe")
    if not shell.is_file():
        pytest.skip("Git Bash unavailable")
    checkpoint, digest, _ = parent_fixture(tmp_path, "B")
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.update(END_BY=END, BASIC_LOG_ROOT=str(tmp_path / "extend"), LIVE="0",
               CUDA_VISIBLE_DEVICES="", FAST_GT_ONLY="1", BASIC_TRACK_ANG_WEIGHT="1.0",
               BASIC_LIN_VEL_Z_SCHEDULE="1")
    child = subprocess.run([str(shell), str(root / "foothold_s2/run_basic_gait_extend.sh"),
                            "B", "cuda:1", str(checkpoint), digest, "1"],
                           cwd=root, env=env, capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr
    assert "DRY: training not started" in child.stdout
    receipts = list((tmp_path / "extend" / "receipts" / "extend").glob("*/launch_receipt.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["fast_gt_only"] and not receipt["depth_camera_enabled"]
    assert not receipt["perception_training_enabled"] and not receipt["training_started"]
    assert receipt["reward_bundle"]["weights"]["track_ang_vel"] == 1.0
    assert receipt["reward_bundle"]["lin_vel_z_schedule"]
    assert not (tmp_path / "extend" / "main").exists()
