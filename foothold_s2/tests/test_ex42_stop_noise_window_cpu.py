"""S2a: the real E2 command term feeds the real runner noise step (CPU only)."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.runners import ex41_critic_mirror as mirror
from foothold_s2.tests.test_ex42_small_noise_lowspeed_cpu import N, _alg, _o, _runner
from foothold_s2.tests.test_ex42_stop_bundle_cpu import _env, _draw


@pytest.fixture(autouse=True)
def low_speed_rule(monkeypatch):
    monkeypatch.setattr(mirror, "SMALL_NOISE_LOWSPEED_CMD", 0.3)
    monkeypatch.setattr(mirror, "MEAN_ACTION_PERCEPTION_SHARE", 0.0)
    monkeypatch.delenv("EX42_STOP_NOISE_WINDOW_S", raising=False)


def _transition(monkeypatch):
    command, raw, _ = _env(monkeypatch, stage_id="E2")
    command.reset(torch.arange(N))
    assert not command.stop_from_move.any()  # reset resampling is not a moving-to-stand transition
    _draw(command, seed=7)
    before = command.stand.clone()
    command._resample_command(torch.arange(N))
    window = command.stop_from_move & command.stand & (raw.scene.terrain.terrain_types == 0)
    assert int(window.sum()) > 10 and int((~before & window).sum()) > 0
    assert int((command.stop_from_move & (raw.scene.terrain.terrain_types == 1)).sum()) > 0
    return command, raw, window


def _step(runner, command):
    obs = _o(command.command[:, 0].tolist())
    obs[:, 7] = command.command[:, 1]
    runner._step_small_noise(obs)
    return runner.alg.storage.noise_scale_env.clone()


def test_only_non_sparse_transition_window_restores_original_noise(monkeypatch, capsys):
    monkeypatch.setenv("EX42_STOP_NOISE_WINDOW_S", "0.1")
    command, raw, window = _transition(monkeypatch)
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner.env = raw
    runner.disable_logs = False
    runner._apply_small_noise()
    base = runner._noise_static.clone()
    scale = _step(runner, command)
    low = mirror.lowspeed_noise_mask(command.command[:, :2], mirror.SMALL_NOISE_LOWSPEED_CMD)
    expected = torch.where(low[:, None], torch.full_like(base, mirror.SMALL_NOISE_SIGMA_SCALE), base)
    expected[window] = 1.0
    assert torch.equal(scale, expected)
    assert bool((scale[window] == 1.0).all())
    sparse_transition = command.stop_from_move & (raw.scene.terrain.terrain_types == 1)
    assert torch.equal(scale[sparse_transition], expected[sparse_transition])

    command.stop_elapsed_s[window] = 0.1
    later = _step(runner, command)
    assert torch.equal(later, torch.where(low[:, None], torch.full_like(base, mirror.SMALL_NOISE_SIGMA_SCALE), base))
    assert bool((later[window] == mirror.SMALL_NOISE_SIGMA_SCALE).all())
    row = runner._small_noise_finish(11)
    assert row["stop_window_envs"] == pytest.approx(int(window.sum()) / 2)
    assert row["stop_window_noise_std_mean"] == pytest.approx(float(alg.policy.std.mean()), rel=1e-6)
    text = capsys.readouterr().out
    assert "EX42_STOP_NOISE_WINDOW where=start window_s=0.1" in text
    assert "EX42_STOP_NOISE_WINDOW it=11" in text


def test_off_is_identical_and_does_not_touch_command_rng(monkeypatch):
    command, raw, window = _transition(monkeypatch)
    state = command.gen.get_state().clone()
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner.env = raw
    runner._apply_small_noise()
    unset = _step(runner, command)
    monkeypatch.setenv("EX42_STOP_NOISE_WINDOW_S", "0")
    zero = _step(runner, command)
    assert torch.equal(unset, zero)
    assert torch.equal(command.gen.get_state(), state)
    assert "stop_window_envs" not in runner._small_noise_finish(1)


def test_enabled_window_refuses_missing_noise_install(monkeypatch):
    monkeypatch.setenv("EX42_STOP_NOISE_WINDOW_S", "1.0")
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner._lowspeed_noise = False
    with pytest.raises(ValueError, match="low-speed noise path is not installed"):
        runner._step_small_noise(_o([0.0] * N))


@pytest.mark.parametrize("value", ["bad", "-0.1", "nan", "inf"])
def test_bad_window_refused(monkeypatch, value):
    monkeypatch.setenv("EX42_STOP_NOISE_WINDOW_S", value)
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner._apply_small_noise()
    with pytest.raises(ValueError, match="finite nonnegative"):
        runner._step_small_noise(_o([0.0] * N))
