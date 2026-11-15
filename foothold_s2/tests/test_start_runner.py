"""12 §9 · 13 §7 L0 CPU 시험 (runner): PPO 입력 고정 · PPO 와 지각의 gradient 경계 · 한 iteration 순서 · checkpoint 왕복.

가짜 env(start_fake_env) 로 runner 배선만 본다. 실제 Isaac 은 10/27 통합 관문(L1)에서.
"""

import os
import subprocess
import sys

import torch

from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _runner(seed=0, n=8, T=24, perception=None, map_input=None):
    torch.manual_seed(seed)
    p = dict(perception or {"microbatch_envs": 4})
    if map_input:
        p["map_input"] = map_input
    return StartRunner(FakeStartEnv(num_envs=n, seed=seed), train_cfg(T, p), log_dir=None, device="cpu")


def _collect_only(r: StartRunner):
    """learn() 의 ① 만 떼어 돌린다(PPO update 전 상태를 보려고)."""
    calls = {}
    orig_update = r.alg.update

    def stop_update():
        calls["storage_obs"] = r.alg.storage.observations.clone()
        calls["storage_logp"] = r.alg.storage.actions_log_prob.clone()
        calls["storage_actions"] = r.alg.storage.actions.clone()
        raise StopIteration

    r.alg.update = stop_update
    try:
        r.learn(1)
    except StopIteration:
        pass
    r.alg.update = orig_update
    return calls


def test_ppo_input_frozen_ratio_is_one():
    r = _runner()
    c = _collect_only(r)
    obs = c["storage_obs"].flatten(0, 1)
    r.alg.policy.act(obs)
    logp = r.alg.policy.get_actions_log_prob(c["storage_actions"].flatten(0, 1))
    ratio = torch.exp(logp - c["storage_logp"].flatten())
    assert torch.allclose(ratio, torch.ones_like(ratio), atol=1e-6)


def test_negative_recomputed_input_breaks_ratio():
    """지각을 먼저 갱신하고 actor 입력을 다시 만들면 ratio != 1 이어야 한다(그 경로를 막는 까닭)."""
    r = _runner()
    c = _collect_only(r)
    r.update_perception()  # 지각 한 번 갱신
    b = r.replay.gather(torch.arange(r.env.num_envs))
    h_prop, h_terr = b["h_prop0"], b["h_terr0"]
    new_inputs = []
    with torch.no_grad():
        for t in range(r.num_steps_per_env):
            h_prop, h_terr, out = r.perception._advance(h_prop, h_terr, b["hist"][t], b["depth2"][t].float(),
                                                        b["tick"][t], b["first"][t], b["use_gt"][t], b["gt_map"][t])
            est = torch.cat([out["mu"], out["v"], out["zf"], out["zb"]], -1)
            new_inputs.append(torch.cat([b["obs"][t], est], -1))
    obs = c["storage_obs"].clone()
    obs["actor_in"] = torch.stack(new_inputs)
    r.alg.policy.act(obs.flatten(0, 1))
    logp = r.alg.policy.get_actions_log_prob(c["storage_actions"].flatten(0, 1))
    ratio = torch.exp(logp - c["storage_logp"].flatten())
    assert (ratio - 1).abs().max() > 1e-3


def test_ppo_update_does_not_touch_perception_and_perception_update_does_not_touch_policy():
    r = _runner()
    _collect_only(r)
    p_before = {k: v.clone() for k, v in r.perception.state_dict().items()}
    a_before = {k: v.clone() for k, v in r.alg.policy.state_dict().items()}
    r.alg.compute_returns  # 이미 계산됨(learn 의 ① 끝)
    r.alg.update()
    assert all(torch.equal(p_before[k], v) for k, v in r.perception.state_dict().items()), "PPO 가 지각을 움직였다"
    assert all(q.grad is None for q in r.perception.parameters())
    a_mid = {k: v.clone() for k, v in r.alg.policy.state_dict().items()}
    assert not all(torch.equal(a_before[k], v) for k, v in a_mid.items())
    r.update_perception()
    assert all(torch.equal(a_mid[k], v) for k, v in r.alg.policy.state_dict().items()), "지각 갱신이 정책을 움직였다"
    assert not all(torch.equal(p_before[k], v) for k, v in r.perception.state_dict().items())


def test_one_full_iteration_and_adasmpl_log():
    r = _runner()
    r.learn(2)
    assert set(r.last_perception_losses) >= {"l_tr", "l_ie", "kl", "o_next"}
    assert 0.0 <= r.adasmpl.p <= 1.0
    assert r.current_learning_iteration == 1


def test_g0_runs():
    r = _runner(map_input="none")
    r.learn(1)
    assert r.perception.trnet is None
    assert r.last_perception_losses["l_tr"] == 0.0


def _same_outputs(r1: StartRunner, r2: StartRunner):
    g = torch.Generator().manual_seed(9)
    n = 4
    hist, d2 = torch.randn(n, 10, 45, generator=g), torch.rand(n, 2, 60, 60, generator=g)
    gm = torch.randn(n, 32, 16, generator=g)
    tick, first, use_gt = torch.ones(n, dtype=torch.bool), torch.ones(n, dtype=torch.bool), torch.tensor([1, 0, 1, 0]).bool()
    outs = []
    for r in (r1, r2):
        with torch.no_grad():
            _, _, o = r.perception._advance(torch.zeros(n, 128), torch.zeros(n, 128), hist, d2, tick, first, use_gt, gm)
            x = torch.randn(n, 96, generator=torch.Generator().manual_seed(3))
            outs.append((o["mu"], o["refined"], r.alg.policy.act_inference({"actor_in": x})))
    return all(torch.allclose(a, b, atol=1e-6) for a, b in zip(outs[0], outs[1]))


def test_checkpoint_roundtrip_new_process(tmp_path):
    r = _runner(seed=0)
    r.learn(2)
    path = str(tmp_path / "ck.pt")
    r.save(path)
    # 새 프로세스에서 복원해 같은 입력의 출력 · AdaSmpl · optimizer 상태를 비교한다
    script = tmp_path / "load.py"
    script.write_text(
        "import sys, torch\n"
        f"sys.path.insert(0, r'{REPO}')\n"
        "from foothold_s2.runners.start_runner import StartRunner\n"
        "from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg\n"
        "torch.manual_seed(123)\n"
        "r = StartRunner(FakeStartEnv(num_envs=8, seed=5), train_cfg(24, {'microbatch_envs': 4}), None, 'cpu')\n"
        f"r.load(r'{path}')\n"
        f"torch.save({{'p': r.perception.state_dict(), 'a': r.alg.policy.state_dict(), 'po': r.perception_optimizer.state_dict(),"
        f" 'ao': r.alg.optimizer.state_dict(), 'ada': r.adasmpl.state_dict(), 'iter': r.current_learning_iteration}}, r'{tmp_path / 'back.pt'}')\n",
        encoding="utf-8",
    )
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", KMP_DUPLICATE_LIB_OK="TRUE")
    subprocess.run([sys.executable, str(script)], check=True, env=env, cwd=REPO)
    back = torch.load(tmp_path / "back.pt", weights_only=False)
    for k, v in r.perception.state_dict().items():
        assert torch.allclose(v, back["p"][k], atol=1e-6)
    for k, v in r.alg.policy.state_dict().items():
        assert torch.allclose(v, back["a"][k], atol=1e-6)
    assert back["ada"] == r.adasmpl.state_dict()
    assert back["iter"] == r.current_learning_iteration
    po, bo = r.perception_optimizer.state_dict(), back["po"]
    for pid, s in po["state"].items():
        for kk, vv in s.items():
            assert torch.allclose(torch.as_tensor(vv), torch.as_tensor(bo["state"][pid][kk]), atol=1e-6)


def test_checkpoint_same_outputs_and_negative_without_perception_optimizer(tmp_path):
    r = _runner(seed=0)
    r.learn(2)
    path = str(tmp_path / "ck.pt")
    r.save(path)
    r2 = _runner(seed=77)
    r2.load(path)
    assert _same_outputs(r, r2)
    # 같은 재생 자료로 한 번 더 갱신했을 때 지각 가중치가 같아야 한다(optimizer 상태까지 복원됐다는 뜻)
    r2.replay.data = {k: v.clone() for k, v in r.replay.data.items()}
    r2.replay.h_prop0, r2.replay.h_terr0, r2.replay.step = r.replay.h_prop0.clone(), r.replay.h_terr0.clone(), r.replay.step
    r3 = _runner(seed=78)
    r3.load(path)
    r3.perception_optimizer = torch.optim.Adam(r3.perception.parameters(), lr=5e-4)  # negative control: 지각 optimizer 빼기
    r3.replay.data = {k: v.clone() for k, v in r.replay.data.items()}
    r3.replay.h_prop0, r3.replay.h_terr0, r3.replay.step = r.replay.h_prop0.clone(), r.replay.h_terr0.clone(), r.replay.step
    for rr in (r, r2, r3):
        torch.manual_seed(5)
        rr.update_perception()
    sd, sd2, sd3 = r.perception.state_dict(), r2.perception.state_dict(), r3.perception.state_dict()
    assert all(torch.allclose(sd[k], sd2[k], atol=1e-6) for k in sd)
    assert not all(torch.allclose(sd[k], sd3[k], atol=1e-6) for k in sd)
