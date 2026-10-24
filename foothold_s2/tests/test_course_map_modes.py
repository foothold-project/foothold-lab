"""SONNET-X25 T4 일부: 평가 지도 모드(eval_gt · eval_pred · probe_prop_only). CPU 만.

GT 와 PRED 를 서로 다른 정수 상수로 넣어 «정책(IE)에 실제로 들어간 지도» 가 모드대로인지 본다.
"""

import pytest
import torch

from foothold_s2.eval.adapters import S2Policy
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

GT_CONST, PRED_CONST = 7.0, 3.0


def _runner(force_gt=True, map_input="reconstruction"):
    env = FakeStartEnv(num_envs=8, seed=1)
    cfg = train_cfg(4, {"microbatch_envs": 4, "map_input": map_input, "force_gt": force_gt, "critic_mode": "clean52"})
    r = StartRunner(env, cfg, log_dir=None, device="cpu")
    r.alg.policy.eval()
    r.perception.eval()
    if r.perception.trnet is not None:
        r.perception.trnet.decode = lambda h: (torch.full((h.shape[0], 32, 16), PRED_CONST), torch.full((h.shape[0], 32, 16), PRED_CONST))      # 복원 지도 = 상수 3
    seen = []
    real = r.perception.ie.estimate
    r.perception.ie.estimate = lambda z, hmap: (seen.append(None if hmap is None else hmap.detach().clone()), real(z, hmap))[1]

    return r, env, seen


def _obs(env, gt_const=GT_CONST):
    raw = env.get_observations()
    raw["gt_map"] = torch.full_like(raw["gt_map"], gt_const)

    return raw


def _values(hmap):
    return set(hmap.unique().tolist())


@pytest.mark.parametrize("force_gt", [True, False])
def test_eval_pred_never_feeds_gt_even_when_the_checkpoint_says_force_gt(force_gt):
    r, env, seen = _runner(force_gt)
    pol = S2Policy(r, 8, map_mode="eval_pred")

    assert not bool(pol.pstate.use_gt.any())
    pol(_obs(env))

    assert _values(seen[-1]) == {PRED_CONST}                                    # 정책 입력 지도에 GT 상수(7) 가 한 칸도 없다
    pol.reset(torch.ones(8))                                                    # 모든 env reset 뒤에도
    pol(_obs(env))

    assert _values(seen[-1]) == {PRED_CONST} and not bool(pol.pstate.use_gt.any())


def test_eval_gt_feeds_gt_for_all_envs_before_and_after_reset():
    r, env, seen = _runner(force_gt=False)                                       # 체크포인트가 False 여도 GT 를 요청하면 GT
    pol = S2Policy(r, 8, map_mode="eval_gt")
    pol(_obs(env))

    assert _values(seen[-1]) == {GT_CONST}
    pol.reset(torch.ones(8))
    pol(_obs(env))

    assert _values(seen[-1]) == {GT_CONST} and bool(pol.pstate.use_gt.all())


def test_default_keeps_the_old_behavior_follow_the_checkpoint_force_gt():
    for force_gt, expect in ((True, GT_CONST), (False, PRED_CONST)):
        r, env, seen = _runner(force_gt)
        S2Policy(r, 8)(_obs(env))

        assert _values(seen[-1]) == {expect}


def test_mixed_per_env_selection_is_exact():
    r, env, seen = _runner(True)
    pol = S2Policy(r, 8, map_mode="eval_gt")
    pol.pstate.use_gt[:3] = False
    pol(_obs(env))
    h = seen[-1]

    assert _values(h[:3]) == {PRED_CONST} and _values(h[3:]) == {GT_CONST}


def test_probe_prop_only_ignores_the_map_without_replacing_it():
    r, env, seen = _runner(True)
    pol = S2Policy(r, 8, map_mode="probe_prop_only")
    pol(_obs(env, 7.0))
    est_a = pol.last_est.clone()
    h = seen[-1]

    assert r.perception.ie.mask_map_tokens is True
    assert h is not None and h.shape[1:] == (32, 16)                              # 0 높이 지도로 대체하지 않았다: 지도는 그대로 IE 에 들어가되 attention 이 보지 않는다
    r2, env2, seen2 = _runner(True)
    pol2 = S2Policy(r2, 8, map_mode="probe_prop_only")
    r2.perception.load_state_dict(r.perception.state_dict())
    r2.alg.policy.load_state_dict(r.alg.policy.state_dict())
    pol2(_obs(env2, -4.0))                                                        # 전혀 다른 GT 상수

    assert torch.equal(pol2.last_est, est_a)                                      # 지도 값이 달라도 est 가 비트 단위로 같다


def test_probe_prop_only_equals_attention_over_the_prop_token_alone():
    """마스크는 «지도 토큰이 없는 시퀀스» 와 같은 수학이다(같은 가중치 · 같은 prop 토큰)."""
    r, _env, _seen = _runner(True)
    ie = r.perception.ie
    z = torch.randn(8, 128, generator=torch.Generator().manual_seed(2))
    ie.mask_map_tokens = True
    with torch.no_grad():
        masked = ie.estimate(z, torch.randn(8, 32, 16, generator=torch.Generator().manual_seed(3)))
        tok = ie.prop_token(z).unsqueeze(1)
        alone = ie.heads(ie.attn(tok)[:, 0])
        mu, logvar = alone[:, :masked["mu"].shape[1]], alone[:, masked["mu"].shape[1]:2 * masked["mu"].shape[1]]

    assert torch.allclose(masked["mu"], mu, atol=1e-5) and torch.allclose(masked["logvar"], logvar, atol=1e-5)


def test_without_the_probe_mask_the_map_does_change_est():
    """대조: 마스크가 없으면 지도 값이 est 를 바꾼다(위 불변 시험이 공허하지 않다는 증거)."""
    r, env, _ = _runner(True)
    a = S2Policy(r, 8, map_mode="eval_gt")
    a(_obs(env, 7.0))
    est_a = a.last_est.clone()
    r2, env2, _ = _runner(True)
    r2.perception.load_state_dict(r.perception.state_dict())
    r2.alg.policy.load_state_dict(r.alg.policy.state_dict())
    b = S2Policy(r2, 8, map_mode="eval_gt")
    b(_obs(env2, -4.0))

    assert not torch.equal(b.last_est, est_a)


def test_invalid_mode_and_probe_without_map_are_refused():
    r, _env, _ = _runner(True)

    with pytest.raises(ValueError, match="map_mode"):
        S2Policy(r, 8, map_mode="gt")

    r0, _e, _ = _runner(False, "none")

    with pytest.raises(ValueError, match="지도 토큰"):
        S2Policy(r0, 8, map_mode="probe_prop_only")


def test_env_var_selects_the_mode(monkeypatch):
    monkeypatch.setenv("S2_MAP_MODE", "eval_pred")
    r, env, seen = _runner(True)
    S2Policy(r, 8)(_obs(env))

    assert _values(seen[-1]) == {PRED_CONST}


def test_mask_is_cleared_when_the_same_runner_is_reused_for_another_mode():
    r, env, seen = _runner(True)
    S2Policy(r, 8, map_mode="probe_prop_only")

    assert r.perception.ie.mask_map_tokens is True
    for mode in ("eval_gt", "eval_pred", None):
        S2Policy(r, 8, map_mode=mode)

        assert r.perception.ie.mask_map_tokens is False, mode
