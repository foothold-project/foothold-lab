"""SOL-23f 후속: scalar SHA, 재개 원점, 분리된 영수증의 정답 입력."""

import hashlib
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.runners.manifest import state_sha
from foothold_s2.runners.sol23f_runner import BRunner
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg
from foothold_s2.eval.adapters import load_s2_runner


def test_state_sha_scalar_and_legacy_vector_bytes():
    scalar = {"step": torch.tensor(1.)}
    assert len(state_sha(scalar)) == 64
    assert state_sha({"step": torch.tensor(2.)}) != state_sha(scalar)
    vector = torch.tensor([1., 2., 3.])
    old = hashlib.sha256()
    old.update(b"/weight" + str(vector.dtype).encode() + str(tuple(vector.shape)).encode()
               + vector.contiguous().view(torch.uint8).numpy().tobytes())
    assert state_sha({"weight": vector}) == old.hexdigest()


def test_restored_levels_types_rebuild_origin_used_by_reset():
    terrain_origins = torch.tensor([[[4., 4., 0.], [4., 12., 0.]],
                                    [[12., 4., 0.], [12., 12., 0.]]])
    terrain = SimpleNamespace(terrain_origins=terrain_origins,
                              terrain_levels=torch.tensor([0]), terrain_types=torch.tensor([0]),
                              env_origins=terrain_origins[0, 0].reshape(1, 3).clone())
    scene = SimpleNamespace(terrain=terrain, env_origins=terrain.env_origins)
    env = SimpleNamespace(scene=scene, common_step_counter=0, command_manager=None)
    runner = object.__new__(StartRunner)
    runner.env = SimpleNamespace(unwrapped=env)
    # Saved level 1 means the next physical reset must spawn at x=12, not x=4.
    runner._load_env_state({"terrain_levels": torch.tensor([1]), "terrain_types": torch.tensor([0])})
    assert terrain.env_origins.tolist() == [[12., 4., 0.]]
    assert scene.env_origins.data_ptr() == terrain.env_origins.data_ptr()
    assert scene.env_origins.tolist() == [[12., 4., 0.]]
    # A scene that is not linked to terrain origins cannot be claimed restored.
    scene.env_origins = torch.zeros_like(terrain.env_origins)
    with pytest.raises(RuntimeError, match="origins differ"):
        runner._load_env_state({"terrain_levels": torch.tensor([1]), "terrain_types": torch.tensor([0])})


def test_b_two_cpu_updates_use_inherited_learning_path():
    assert BRunner.learn is StartRunner.learn
    assert BRunner.update_perception is StartRunner.update_perception
    torch.manual_seed(91)
    runner = BRunner(FakeStartEnv(num_envs=8, seed=91), train_cfg(24, {"microbatch_envs": 4}),
                     log_dir=None, device="cpu")
    runner.learn(2)
    assert runner.current_learning_iteration == 1
    assert len(runner.iter_log) == 2
    assert all(torch.isfinite(value).all() for value in runner.alg.policy.state_dict().values())


def test_resume_segment_physically_resets_at_restored_origin_once():
    origins = torch.tensor([[[4., 4., 0.]], [[12., 4., 0.]]])
    terrain = SimpleNamespace(terrain_origins=origins, terrain_levels=torch.tensor([1]),
                              terrain_types=torch.tensor([0]), env_origins=origins[1, 0].reshape(1, 3).clone())
    class Curriculum:
        def __init__(self):
            self.calls = 0
        def compute(self, **kwargs):
            self.calls += 1
            terrain.terrain_levels[:] = 0
    curriculum = Curriculum()
    scene = SimpleNamespace(terrain=terrain, env_origins=terrain.env_origins)
    class Wrapped:
        def __init__(self):
            self.unwrapped = SimpleNamespace(scene=scene, curriculum_manager=curriculum)
            self.physical_root = None
        def reset(self):
            curriculum.compute(env_ids=torch.tensor([0]))
            self.physical_root = scene.env_origins.clone()
    wrapped = Wrapped()
    runner = object.__new__(BRunner)
    runner.env = wrapped
    row = runner.reset_segment_physics()
    assert row["performed"] and not row["physical_resume_identical"]
    assert curriculum.calls == 0 and terrain.terrain_levels.tolist() == [1]
    assert wrapped.physical_root.tolist() == [[12., 4., 0.]]
    assert getattr(curriculum.compute, "__self__", None) is curriculum


def test_topdown_depth_delay_checkpoint_controls_eval_loader(tmp_path):
    source = StartRunner(FakeStartEnv(num_envs=2), train_cfg(24, {"microbatch_envs": 2,
                         "map_input": "reconstruction", "depth_delay_ticks": 0}), log_dir=None, device="cpu")
    path = tmp_path / "model.pt"
    saved = {"perception_cfg": dict(source.pcfg),
             "model_state_dict": source.alg.policy.state_dict(),
             "perception_state_dict": source.perception.state_dict(),
             "sol23f": {"variant": "START_TopDown", "depth_delay_ticks": 0}}
    torch.save(saved, path)
    runner, _ = load_s2_runner(FakeStartEnv(num_envs=2), train_cfg(24), path, "cpu")
    assert runner.perception.cfg.depth_delay_ticks == 0
    assert runner.perception.init_state(2, "cpu").frames.shape[1] == 2
    saved["perception_cfg"].pop("depth_delay_ticks")
    torch.save(saved, path)
    with pytest.raises(ValueError, match="TopDown checkpoint missing"):
        load_s2_runner(FakeStartEnv(num_envs=2), train_cfg(24), path, "cpu")
