"""Global faults must stop this rollout, not become valid zero-filled samples."""
import json
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.rewards import w86_runtime as wr
from foothold_s2.tests.test_w86_runtime_cpu import sample


def runner_at(tmp_path):
    env = SimpleNamespace(num_envs=3, device="cpu", step_dt=.02, common_step_counter=12)
    env._ex41_w86 = wr.W86Runtime(env, tmp_path, source=lambda: sample())
    env.scene = SimpleNamespace(write_data_to_sim=lambda: None)
    env.sim = SimpleNamespace(forward=lambda: None)
    env._reset_idx = lambda ids: None
    env.observation_manager = SimpleNamespace(compute=lambda update_history: {"policy": torch.ones(3, 4)})
    return SimpleNamespace(env=SimpleNamespace(unwrapped=env), alg=SimpleNamespace())


def fatal_receipt(path, reason):
    rows = [json.loads(x) for x in (path / "ex41_fatal.jsonl").read_text().splitlines()]
    row = rows[-1]
    assert row["reason"] == reason and row["stop_requested"] is True
    assert row["resumable_checkpoint_written"] is False
    assert row["event"] == "fatal_training_fault" and row["step"] == 12


def test_global_policy_nan_is_not_env_quarantine(tmp_path):
    runner = runner_at(tmp_path)
    runner.alg.policy = torch.nn.Linear(2, 2)
    runner.alg.policy.weight.data[0, 0] = float("nan")
    with pytest.raises(ValueError):
        wr.quarantine_actions(runner, torch.full((3, 12), float("nan")))
    fatal_receipt(tmp_path, "global_nonfinite_policy")
    assert not runner.env.unwrapped._ex41_w86.pending.any()


def test_all_bad_actions_stop_without_fake_zero_actions(tmp_path):
    runner = runner_at(tmp_path)
    with pytest.raises(ValueError):
        wr.quarantine_actions(runner, torch.full((3, 12), float("nan")))
    fatal_receipt(tmp_path, "all_env_actions_invalid")


@pytest.mark.parametrize("phase", ["reset", "forward", "compute", "still_nan"])
def test_failed_local_reset_is_fatal_and_preserves_pending(tmp_path, phase):
    runner = runner_at(tmp_path)
    env = runner.env.unwrapped
    def broken(*args, **kwargs):
        raise RuntimeError("known reset failure")
    if phase == "reset": env._reset_idx = broken
    if phase == "forward": env.sim.forward = broken
    if phase == "compute": env.observation_manager.compute = broken
    if phase == "still_nan":
        env.observation_manager.compute = lambda **kw: {"policy": torch.full((3, 4), float("nan"))}
    obs = {"policy": torch.ones(3, 4)}
    obs["policy"][1, 0] = float("nan")
    with pytest.raises(ValueError):
        wr.quarantine_step(runner, obs, torch.ones(3), torch.zeros(3, dtype=torch.bool), {})
    fatal_receipt(tmp_path, "post_reset_still_invalid" if phase == "still_nan" else "env_reset_failed")
    assert env._ex41_w86.pending[1]


def test_non_env_scalar_nan_is_not_silently_ignored(tmp_path):
    runner = runner_at(tmp_path)
    obs = {"policy": torch.ones(3, 4), "shared": torch.tensor(float("nan"))}
    with pytest.raises(ValueError):
        wr.quarantine_step(runner, obs, torch.ones(3), torch.zeros(3, dtype=torch.bool), {})
    fatal_receipt(tmp_path, "global_nonfinite_observation")
