"""D93 pose observation producer checks without Kit or CUDA."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch


def _producer():
    """Execute only the real producer nodes; Isaac manager imports need Kit."""
    source = Path(__file__).parents[1] / "sensors" / "start_obs.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {"zero_pose_command", "PoseCommandGroup", "apply_ex41_pose_observation"}
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert {node.name for node in nodes} == names

    class ObsGroup:
        pass

    def configclass(cls):
        cls.__init__ = lambda self: self.__post_init__()
        return cls

    namespace = {"torch": torch, "ObsGroup": ObsGroup,
                 "ObsTerm": lambda **kwargs: SimpleNamespace(**kwargs), "configclass": configclass}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def test_pose_producer_is_zero_two_columns_and_follows_env_device():
    zero_pose_command = _producer()["zero_pose_command"]
    env = SimpleNamespace(num_envs=7, device="cpu")
    result = zero_pose_command(env)
    assert result.shape == (7, 2)
    assert result.dtype == torch.float32
    assert result.device.type == "cpu"
    assert torch.count_nonzero(result) == 0
    assert torch.equal(result, torch.zeros_like(result))


def test_ex41_group_is_separate_and_noiseless():
    namespace = _producer()
    PoseCommandGroup = namespace["PoseCommandGroup"]
    apply_ex41_pose_observation = namespace["apply_ex41_pose_observation"]
    zero_pose_command = namespace["zero_pose_command"]
    policy = object()
    obs = SimpleNamespace(policy=policy, depth=object(), gt_map=object())
    cfg = SimpleNamespace(observations=obs)
    apply_ex41_pose_observation(cfg)
    assert obs.policy is policy
    assert isinstance(obs.pose_cmd, PoseCommandGroup)
    assert obs.pose_cmd.concatenate_terms is True
    assert obs.pose_cmd.enable_corruption is False
    assert obs.pose_cmd.pose_cmd.func is zero_pose_command
    with pytest.raises(ValueError, match="already exists"):
        apply_ex41_pose_observation(cfg)
