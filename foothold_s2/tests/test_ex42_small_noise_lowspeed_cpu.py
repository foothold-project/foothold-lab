"""v28m: an env whose command speed (vx vy norm) is below SMALL_NOISE_LOWSPEED_CMD acts with the small noise for that step,
the other envs keep the fixed-share spread. The scale of every step is stored so the update re-evaluates each row with the
std it really sampled from (ratio 1). CPU only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from foothold_s2.ex42_live_metrics import LiveMetrics
from foothold_s2.runners import ex41_critic_mirror as mirror
from foothold_s2.runners.ex41_critic_mirror import small_noise_mask, small_noise_scale
from foothold_s2.tests.test_ex42_small_noise_cpu import N, _alg, _obs

SIGMA = mirror.SMALL_NOISE_SIGMA_SCALE


@pytest.fixture(autouse=True)
def _rule_on_and_no_mean_envs(monkeypatch):
    """v28p ships the low-speed rule OFF (threshold 0) and 12 % mean-action envs; these tests are about the rule, so they switch it on."""
    monkeypatch.setattr(mirror, "SMALL_NOISE_LOWSPEED_CMD", 0.3)
    monkeypatch.setattr(mirror, "MEAN_ACTION_PERCEPTION_SHARE", 0.0)


def test_constants_and_the_threshold_rule():
    assert mirror.SMALL_NOISE_LOWSPEED_CMD == 0.3 and mirror.SMALL_NOISE_REST_SHARE == 0.25 and mirror.SMALL_NOISE_ENV_SHARE == 0.25
    assert mirror.small_noise_static_share() == 0.25                                  # rule on: the rest share
    cmd = torch.tensor([[0.0, 0.0], [0.29, 0.0], [0.3, 0.0], [0.2, 0.2], [0.0, -0.25], [0.25, 0.25], [1.0, 0.0]])
    assert mirror.lowspeed_noise_mask(cmd, 0.3).tolist() == [True, True, False, True, True, False, False]   # norm, strict, standing counts
    assert not mirror.lowspeed_noise_mask(cmd, 0.0).any()                              # threshold 0 selects none


def test_one_constant_turns_it_off_and_the_v28l_share_comes_back(monkeypatch):
    monkeypatch.setattr(mirror, "SMALL_NOISE_LOWSPEED_CMD", 0.0)
    assert mirror.small_noise_static_share() == mirror.SMALL_NOISE_ENV_SHARE


def _runner(alg, n=N):
    from foothold_s2.runners import start_runner
    runner = object.__new__(start_runner.StartRunner)
    runner.ex41_pose_commands, runner.ex41_critic_mirror, runner.ex41_mirror_approval = True, True, None
    runner.alg, runner.device, runner.env = alg, "cpu", SimpleNamespace(num_envs=n)
    runner.disable_logs = True
    return runner


def _o(speeds):
    o = torch.zeros(len(speeds), 12)
    o[:, 6] = torch.tensor(speeds)
    return o


def test_runner_marks_low_speed_envs_on_top_of_the_static_share_and_counts_them():
    alg, _ = _alg(None, steps=3)
    runner = _runner(alg)
    runner._apply_small_noise()
    static = small_noise_mask(N, 0.25)
    assert torch.equal(alg.storage.noise_scale_env.flatten() < 1, static) and alg.storage.noise_scale_steps.shape == (3, N, 1)
    speeds = [0.1 if i % 2 == 0 else 0.8 for i in range(N)]
    runner._step_small_noise(_o(speeds))
    low = torch.tensor([s < 0.3 for s in speeds])
    scale = alg.storage.noise_scale_env
    assert torch.equal(scale.flatten() < 1, static | low) and alg.policy.noise_scale is scale
    assert torch.allclose(scale[scale < 1], torch.tensor(SIGMA))
    runner._step_small_noise(_o([0.8] * N))                                     # decided again at every step
    assert torch.equal(alg.storage.noise_scale_env.flatten() < 1, static)
    row = runner._small_noise_finish(7)
    assert row["lowspeed_envs"] == pytest.approx(N / 4) and row["small_noise_envs"] == pytest.approx((int((static | low).sum()) + int(static.sum())) / 2)
    assert runner._small_noise_finish(8) == {}                                  # counts were reset


def test_off_constant_leaves_the_v28l_path_untouched(monkeypatch):
    monkeypatch.setattr(mirror, "SMALL_NOISE_LOWSPEED_CMD", 0.0)
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner._apply_small_noise()
    assert alg.storage.noise_scale_steps is None
    before = alg.storage.noise_scale_env
    runner._step_small_noise(_o([0.0] * N))
    assert alg.storage.noise_scale_env is before and torch.equal(before.flatten() < 1, small_noise_mask(N, mirror.SMALL_NOISE_ENV_SHARE))


def test_live_metrics_hear_the_mask_of_each_step(tmp_path):
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner.continuous_curriculum = SimpleNamespace(live_metrics=LiveMetrics(tmp_path / "live", noise_envs=small_noise_mask(N, 0.25),
                                                                            noise_sigma_scale=SIGMA))
    runner._apply_small_noise()
    runner._step_small_noise(_o([0.0] * N))
    assert runner.continuous_curriculum.live_metrics.noise_envs.all()


def test_rollout_with_per_step_scales_updates_with_ratio_one_and_the_wrong_env_scale_would_not():
    alg, obs = _alg(None, steps=2)
    runner = _runner(alg)
    runner._apply_small_noise()
    torch.manual_seed(7)
    scales = []
    for speeds in ([0.1] * N, [0.8] * N):                                        # step 0 all low speed, step 1 only the static share
        runner._step_small_noise(_o(speeds))
        scales.append(alg.storage.noise_scale_env.clone())
        with torch.inference_mode():
            alg.act(obs)
            alg.process_env_step(obs, torch.zeros(N), torch.zeros(N), {"ex41_ppo_valid": torch.ones(N, dtype=torch.bool)})
    alg.compute_returns(obs)
    st = alg.storage
    assert torch.equal(st.noise_scale_steps[0], scales[0]) and torch.equal(st.noise_scale_steps[1], scales[1])
    assert torch.allclose(st.sigma[0], (alg.policy.std * SIGMA).expand(N, 12)) and not torch.allclose(st.sigma[1][0], st.sigma[0][0])
    advantage = st.advantages.flatten(0, 1).flatten().clone()
    alg.normalize_advantage_per_mini_batch = False
    losses = alg.update()
    assert losses["surrogate"] == pytest.approx(-float(advantage.mean()), abs=1e-5)         # ratio exactly 1 on every row of both steps
    assert losses["small_noise_env_share"] == pytest.approx(float(torch.stack(scales).lt(1).float().mean()))
    assert losses["small_noise_env_share"] != pytest.approx(float((scales[1] < 1).float().mean()))   # not just the last step's scale
    # what the old per-env scale (last step only) would have done to the rows of step 0:
    alg2, obs2 = _alg(None, steps=2)
    alg2.storage.noise_scale_env = scales[1]
    alg2.policy.noise_scale = scales[1]
    row = st.mu[0]
    alg2.policy.act(obs)
    wrong = alg2.policy.get_actions_log_prob(st.actions[0])
    assert (wrong - st.actions_log_prob[0].flatten()).abs().max() > 1.0
