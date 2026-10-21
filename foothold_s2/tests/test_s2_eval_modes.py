"""평가 adapter 의 z · action 모드 분리 (SONNET-X11 1 단계). Kit 없이 가짜 env 의 StartRunner 로.

답을 아는 입력: 같은 관측에서 z=mean 이면 반복해도 같은 행동, z=sample 이면 매번 다르고, 표집 z 의 평균은 mu 로 수렴한다.
"""

import pytest
import torch

from foothold_s2.eval.adapters import S2Policy
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


def _runner(seed=0, n=8):
    torch.manual_seed(seed)
    env = FakeStartEnv(num_envs=n, seed=seed)

    return StartRunner(env, train_cfg(24, {"microbatch_envs": 4, "map_input": "none"}), log_dir=None, device="cpu"), env


def _act(runner, obs, z, act, seed):
    torch.manual_seed(seed)

    return S2Policy(runner, obs.batch_size[0], z_mode=z, act_mode=act)(obs)


def test_z_mean_is_repeatable_and_z_sample_is_not():
    r, env = _runner()
    obs = env.get_observations()
    a1, a2 = _act(r, obs, "mean", "mean", 1), _act(r, obs, "mean", "mean", 2)
    s1, s2 = _act(r, obs, "sample", "mean", 1), _act(r, obs, "sample", "mean", 2)

    assert torch.equal(a1, a2)                              # z 평균 + 행동 평균: 시드가 달라도 같다
    assert not torch.allclose(s1, s2)                       # z 표집: 시드가 다르면 다르다
    assert torch.equal(s1, _act(r, obs, "sample", "mean", 1))   # 같은 시드면 같은 표집


def test_act_sample_differs_but_z_mean_with_act_mean_matches_default():
    r, env = _runner()
    obs = env.get_observations()
    base = _act(r, obs, "mean", "mean", 1)

    assert not torch.allclose(_act(r, obs, "mean", "sample", 1), base)
    assert torch.equal(_act(r, obs, "mean", "mean", 5), base)


def test_four_combinations_are_four_distinct_modes():
    r, env = _runner()
    obs = env.get_observations()
    out = {(z, a): _act(r, obs, z, a, 3) for z in ("mean", "sample") for a in ("mean", "sample")}
    keys = list(out)

    for i in range(4):
        for j in range(i + 1, 4):
            assert not torch.allclose(out[keys[i]], out[keys[j]]), (keys[i], keys[j])


def test_sampled_z_mean_converges_to_mu():
    r, env = _runner(n=1)
    obs = env.get_observations()
    mu = None
    zs = []

    for k in range(400):
        pol = S2Policy(r, 1, z_mode="sample", act_mode="mean")
        torch.manual_seed(1000 + k)
        pol(obs)
        zs.append(pol.last_est[0, :r.perception.cfg.latent_dim].clone() if hasattr(r.perception.cfg, "latent_dim") else pol.last_est[0, :16].clone())

    pol = S2Policy(r, 1, z_mode="mean", act_mode="mean")
    pol(obs)
    mu = pol.last_est[0, :zs[0].numel()]
    Z = torch.stack(zs)
    std = Z.std(0)
    se = std / (len(zs) ** 0.5)

    assert float(std.mean()) > 1e-3                                # 표집이 실제로 퍼져 있다
    assert float(((Z.mean(0) - mu).abs() / (se + 1e-9)).max()) < 5.0   # 평균이 mu 로 수렴(표준오차의 5 배 안)


def test_bad_mode_is_rejected():
    r, _ = _runner()

    with pytest.raises(ValueError):
        S2Policy(r, 8, z_mode="bogus")
