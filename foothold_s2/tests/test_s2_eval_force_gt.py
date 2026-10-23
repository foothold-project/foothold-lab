"""Checkpoint map selection at the CPU evaluation boundary."""

import pytest
import torch
from types import SimpleNamespace

from foothold_s2.eval.adapters import S2Adapter, S2Policy, load_s2_runner
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


def _checkpoint(tmp_path, map_input, force_gt, *, omit_flag=False):
    source = StartRunner(
        FakeStartEnv(num_envs=2),
        train_cfg(24, {"microbatch_envs": 2, "map_input": map_input, "force_gt": force_gt}),
        log_dir=None,
        device="cpu",
    )
    saved_cfg = dict(source.pcfg)
    if omit_flag:
        saved_cfg.pop("force_gt")
    path = tmp_path / "model.pt"
    torch.save(
        {
            "perception_cfg": saved_cfg,
            "model_state_dict": source.alg.policy.state_dict(),
            "perception_state_dict": source.perception.state_dict(),
        },
        path,
    )
    return path


@pytest.mark.parametrize(
    ("map_input", "saved_force_gt", "omit_flag", "agent_force_gt", "want_gt"),
    [
        ("reconstruction", True, False, False, True),
        ("reconstruction", False, False, True, False),
        ("none", False, False, True, False),
        ("none", False, True, True, False),
    ],
)
def test_checkpoint_controls_map_at_first_step_and_after_reset(
    tmp_path, map_input, saved_force_gt, omit_flag, agent_force_gt, want_gt
):
    checkpoint = _checkpoint(tmp_path, map_input, saved_force_gt, omit_flag=omit_flag)
    env = FakeStartEnv(num_envs=2)
    cfg = train_cfg(24, {"microbatch_envs": 2, "map_input": "reconstruction", "force_gt": agent_force_gt})
    runner, _ = load_s2_runner(env, cfg, checkpoint, "cpu")
    policy = S2Policy(runner, 2, z_mode="mean", act_mode="mean")
    assert runner.perception.cfg.force_gt is want_gt
    assert policy.pstate.use_gt.tolist() == [want_gt, want_gt]

    seen_maps = []
    original = runner.perception.ie.estimate

    def capture(h_prop, hmap):
        seen_maps.append(None if hmap is None else hmap.detach().clone())
        return original(h_prop, hmap)

    runner.perception.ie.estimate = capture
    obs = env.get_observations()
    policy(obs)
    expected_map = obs["gt_map"].reshape(2, 32, 16)
    if map_input == "none":
        assert seen_maps[-1] is None
    elif want_gt:
        assert torch.equal(seen_maps[-1], expected_map)
    else:
        assert not torch.equal(seen_maps[-1], expected_map)

    policy.reset(torch.tensor([1, 0]))
    assert policy.pstate.use_gt.tolist() == [want_gt, want_gt]
    policy(obs)
    if want_gt:
        assert torch.equal(seen_maps[-1], expected_map)


def test_adapter_reports_restored_force_gt(tmp_path):
    checkpoint = _checkpoint(tmp_path, "reconstruction", True)
    cfg = train_cfg(24, {"microbatch_envs": 2, "map_input": "none", "force_gt": False})
    adapter = SimpleNamespace(checks={})
    built = {"env": FakeStartEnv(num_envs=2), "agent_cfg": SimpleNamespace(to_dict=lambda: cfg, device="cpu")}
    _, policy, _, _ = S2Adapter.load_policy(adapter, built, checkpoint)
    assert adapter.checks["restored_modes"]["force_gt"] is True
    assert policy.pstate.use_gt.tolist() == [True, True]


def test_non_boolean_checkpoint_flag_is_rejected(tmp_path):
    checkpoint = _checkpoint(tmp_path, "none", False)
    saved = torch.load(checkpoint, weights_only=False, map_location="cpu")
    saved["perception_cfg"]["force_gt"] = "False"
    torch.save(saved, checkpoint)
    with pytest.raises(ValueError, match="force_gt 는 bool"):
        load_s2_runner(FakeStartEnv(num_envs=2), train_cfg(), checkpoint, "cpu")
