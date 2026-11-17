"""속도 가지 + 실제 StartRunner (가짜 env): 얼림 · 켜짐 · 옛 저장본 읽기 · 저장 왕복 (DESIGN-SLOW-WALK 7 절 1 단계 진입점)."""
import copy

import torch

from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


def _runner(monkeypatch, mode, freeze="0", seed=0):
    monkeypatch.setenv("EX42_VEL_BRANCH", mode)
    monkeypatch.setenv("EX42_VEL_BRANCH_FREEZE", freeze)
    torch.manual_seed(seed)
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), train_cfg(24, {"microbatch_envs": 4, "replay_impl": "loop"}), log_dir=None, device="cpu")


def _snap(module):
    return {k: v.detach().clone() for k, v in module.state_dict().items()}


def test_frozen_shadow_changes_only_the_branch(monkeypatch):
    r = _runner(monkeypatch, "shadow", "1")
    pol0, per0 = _snap(r.alg.policy), _snap(r.perception)
    r.learn(2)
    assert all(torch.equal(pol0[k], v) for k, v in r.alg.policy.state_dict().items())          # 정책 얼림
    changed = [k for k, v in r.perception.state_dict().items() if not torch.equal(per0[k], v)]
    assert changed and all(k.startswith("vbranch.") for k in changed), changed                  # 몸통 얼림 · 가지만 움직임
    losses = r.last_perception_losses
    assert "vb" in losses and "vslope_slow_branch" in losses or "vslope_slow_n" in losses


def test_unfrozen_replace_trains_and_actor_gets_branch_v(monkeypatch):
    r = _runner(monkeypatch, "replace", "0")
    r.learn(2)
    assert "vb" in r.last_perception_losses
    assert r.perception.cfg.vel_branch == "replace"


def test_old_checkpoint_into_frozen_branch_runner_and_roundtrip(monkeypatch, tmp_path):
    old = _runner(monkeypatch, "off")
    old.learn(2)
    p_old = str(tmp_path / "old.pt")
    old.save(p_old)
    new = _runner(monkeypatch, "shadow", "1", seed=3)
    fresh = {k: v.clone() for k, v in new.perception.state_dict().items() if k.startswith("vbranch.")}
    new.load(p_old)                                                   # 가지 열쇠가 없는 옛 저장본: 가지는 새로 만든 그대로 · 지각 optimizer 는 안 읽음
    for k, v in old.perception.state_dict().items():
        assert torch.equal(new.perception.state_dict()[k], v), k
    assert all(torch.equal(new.perception.state_dict()[k], v) for k, v in fresh.items())
    new.learn(2)
    p_new = str(tmp_path / "new.pt")
    new.save(p_new)
    again = _runner(monkeypatch, "shadow", "1", seed=4)
    again.load(p_new)                                                 # 가지가 든 저장본 왕복
    for k, v in new.perception.state_dict().items():
        assert torch.allclose(again.perception.state_dict()[k], v, atol=1e-6), k
