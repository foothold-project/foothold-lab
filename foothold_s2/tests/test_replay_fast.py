"""RL-3: 빠른 재생 구현(a1 · a2 · a3)이 기준(loop)과 같은 입력 · 같은 잡음에서 같은 손실 · 지도 · gradient 를 내는지 (1e-4)."""

import pytest
import torch

from foothold_s2.models.replay_fast import scan_cudnn, scan_loop
from foothold_s2.models.start_perception import PerceptionCfg, StartPerception
from foothold_s2.tests.test_start_perception import _rollout

DEVICES = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])


@pytest.mark.parametrize("device", DEVICES)
def test_scan_cudnn_equals_loop(device, monkeypatch):
    # cuDNN RNN 은 cudnn.allow_tf32(기본 True) 이면 TF32 로 곱해 GRUCell 과 3e-4 쯤 달라진다(10/20 실측).
    # 알고리즘이 같은지를 보려고 여기서는 끈다. 학습 실행에서의 TF32 차이는 따로 기록한다.
    monkeypatch.setattr(torch.backends.cudnn, "allow_tf32", False)
    g = torch.Generator().manual_seed(0)
    T, B, D, H = 24, 7, 11, 9
    cell = torch.nn.GRUCell(D, H).to(device)
    x = torch.randn(T, B, D, generator=g).to(device)
    h0 = torch.randn(B, H, generator=g).to(device)
    reset = torch.rand(T, B, generator=g) < 0.08
    reset[0, 2] = True  # 첫 스텝 리셋
    reset[:, 3] = False
    advance = torch.rand(T, B, generator=g) < 0.4
    advance[:, 4] = False  # 한 번도 진행하지 않는 env
    reset, advance = reset.to(device), advance.to(device)
    a = scan_loop(cell, x, h0, advance, reset)
    b = scan_cudnn(cell, x, h0, advance, reset)
    assert (a - b).abs().max() <= 1e-5
    ga = torch.autograd.grad(a.square().sum(), list(cell.parameters()))
    gb = torch.autograd.grad(b.square().sum(), list(cell.parameters()))
    assert max(float((u - v).abs().max()) for u, v in zip(ga, gb)) <= 1e-4


def _batch(map_input="reconstruction", n=6, seed=2):
    torch.manual_seed(seed)
    p = StartPerception(PerceptionCfg(map_input=map_input))
    rb, _, _ = _rollout(p, n=n, T=24, done_at=12, seed=seed)
    return p, rb.gather(torch.arange(n))


@pytest.mark.parametrize("impl", ["a1", "a2", "a3"])
@pytest.mark.parametrize("map_input", ["reconstruction", "none"])
def test_fast_equals_loop(impl, map_input):
    p, b = _batch(map_input)
    eps = torch.randn(24, 6, 16, generator=torch.Generator().manual_seed(5))
    ref = p.sequence_loss(b, eps=eps, impl="loop")
    params = [q for q in p.parameters()]
    g_ref = torch.autograd.grad(ref["loss"], params, allow_unused=True)
    new = p.sequence_loss(b, eps=eps, impl=impl)
    for k in ("l_tr", "l_ie", "kl", "o_next", "v", "hf", "hb", "loss"):
        assert abs(float(ref[k]) - float(new[k])) <= 1e-4, (k, float(ref[k]), float(new[k]))
    g_new = torch.autograd.grad(new["loss"], params, allow_unused=True)
    worst = max(float((u - v).abs().max()) for u, v in zip(g_ref, g_new) if u is not None)
    assert worst <= 1e-4, worst
    assert all((u is None) == (v is None) for u, v in zip(g_ref, g_new))  # gradient 경계도 같다


def test_fast_refined_map_equals_loop():
    """지도(H_refined) 자체도 같은지: loop 의 스텝별 decode 와 a3 의 한 번 계산."""
    p, b = _batch()
    eps = torch.zeros(24, 6, 16)
    new = p.sequence_loss(b, eps=eps, impl="a3")
    h_prop, h_terr, maps = b["h_prop0"], b["h_terr0"], []
    with torch.no_grad():
        for t in range(24):
            h_prop, h_terr, out = p._advance(h_prop, h_terr, b["hist"][t], b["depth2"][t], b["tick"][t], b["first"][t],
                                             b["use_gt"][t], b["gt_map"][t])
            maps.append(out["refined"])
    assert (torch.cat(maps) - new["_refined"].detach()).abs().max() <= 1e-4


@pytest.mark.parametrize("impl", ["a1", "a2", "a3"])
def test_fast_passes_detached_map_to_ie(impl):
    """detach 두 겹 중 빠른 경로 쪽 겹을 따로 본다(estimate 의 겹이 남아 있어도 이쪽이 빠지면 잡히게)."""
    p, b = _batch()
    seen = []
    orig = p.ie.estimate

    def spy(z_prop, m):
        seen.append(m.requires_grad)
        return orig(z_prop, m)

    p.ie.estimate = spy
    p.sequence_loss(b, eps=torch.zeros(24, 6, 16), impl=impl)
    assert seen and not any(seen)
