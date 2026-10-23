"""Narrow CPU evidence for the three SOL-23g tail corrections."""

import ast
import copy
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.runners.sol23f_runner import Sol23FRunner
from foothold_s2.runners.start_runner import CKPT_FORMAT, StartRunner
from foothold_s2.sol23f_contract import resume_parent


ROOT = Path(__file__).resolve().parents[2]


def test_topdown_reset_yaw_is_zero_and_b_inherits_random_yaw():
    source = (ROOT / "foothold_s2/tasks/s2_23f_topdown_cfg.py").read_text(encoding="utf-8")
    assignments = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Assign)
                   and any(ast.unparse(target) in {"self.events.reset_base", "self.events.reset_base.params"}
                           for target in node.targets)]
    assert len(assignments) == 2
    base_params = {"pose_range": {"yaw": (-3.14, 3.14)}}
    base_event = SimpleNamespace(params=base_params)
    events = SimpleNamespace(reset_base=base_event)
    context = {"self": SimpleNamespace(events=events), "copy": copy}
    exec(compile(ast.Module(body=assignments, type_ignores=[]), "topdown_yaw", "exec"), context)
    assert events.reset_base.params["pose_range"]["yaw"] == (0.0, 0.0)
    assert base_event.params["pose_range"]["yaw"] == (-3.14, 3.14)
    assert base_params["pose_range"]["yaw"] == (-3.14, 3.14)
    base = (ROOT / "foothold_s2/tasks/s1_env_cfg.py").read_text(encoding="utf-8")
    b = (ROOT / "foothold_s2/tasks/s2_23f_b_cfg.py").read_text(encoding="utf-8")
    assert '"yaw": (-3.14, 3.14)' in base
    assert 'class FootholdS223FBEnvCfg(FootholdS2X23EnvCfg)' in b
    assert "reset_base" not in b


def test_topdown_curriculum_generator_next_draw_survives_env_checkpoint(monkeypatch):
    fake = ModuleType("isaaclab.envs")
    fake.ManagerBasedRLEnv = type("ManagerBasedRLEnv", (), {})
    monkeypatch.setitem(sys.modules, "isaaclab.envs", fake)
    module = importlib.import_module("foothold_s2.tasks.s2_23f_topdown_env")
    env = module.FootholdS223FTopDownEnv.__new__(module.FootholdS223FTopDownEnv)
    env._s2_rng = np.random.default_rng(42)
    env._s2_rng.integers(0, 100, 7)
    runner = SimpleNamespace(env=env, _command_term=lambda: None)
    saved = StartRunner._env_state(runner)
    assert "s2_rng_state" in saved["env_hook"]
    expected = env._s2_rng.integers(0, 1000, 10)
    env._s2_rng = np.random.default_rng(99)
    StartRunner._load_env_state(runner, saved)
    assert np.array_equal(env._s2_rng.integers(0, 1000, 10), expected)
    with pytest.raises(ValueError, match="curriculum RNG"):
        env.foothold_load_state_dict({})


def test_initial_snapshot_rejected_but_completed_checkpoint_accepted(tmp_path):
    state = {"format": CKPT_FORMAT, "sol23f": {"variant": "START_TopDown", "depth_delay_ticks": 0},
             "iter": 0, **{key: {} for key in ("model_state_dict", "optimizer_state_dict",
                                          "perception_state_dict", "perception_optimizer_state_dict",
                                          "adasmpl", "env_state", "rng")}}
    runner = SimpleNamespace(state_dict=lambda infos=None: state)
    initial = tmp_path / "model_initial.pt"
    Sol23FRunner.save_initial(runner, str(initial))
    assert torch.load(initial, weights_only=False)["sol23f"]["initial_snapshot"] is True
    with pytest.raises(ValueError, match="initial snapshot"):
        resume_parent(str(initial), "TopDown")
    renamed = tmp_path / "renamed.pt"
    renamed.write_bytes(initial.read_bytes())
    with pytest.raises(ValueError, match="initial snapshot"):
        resume_parent(str(renamed), "TopDown")
    completed = tmp_path / "model_0.pt"
    Sol23FRunner.save(runner, str(completed))
    assert resume_parent(str(completed), "TopDown")["completed_update"] == 0
    old_initial = tmp_path / "legacy" / "model_initial.pt"
    old_initial.parent.mkdir()
    old_initial.write_bytes(completed.read_bytes())
    with pytest.raises(ValueError, match="initial snapshot"):
        resume_parent(str(old_initial), "TopDown")
