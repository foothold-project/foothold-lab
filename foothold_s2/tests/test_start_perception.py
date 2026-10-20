"""12 §9 · 13 §7 L0 CPU 시험: 모양 · 손실 기대값 · AdaSmpl · gradient 경계 · 재생 = 수집 · terminal 마스크 · 10 Hz 마스크."""

import math

import pytest
import torch

from foothold_s2.models.start_perception import (
    AdaSmpl,
    DepthCNN,
    IEEstimator,
    PerceptionCfg,
    StartPerception,
    TRNet,
    loss_tr,
)
from foothold_s2.runners.perception_replay import PerceptionReplay


def test_shapes():
    torch.manual_seed(0)
    assert DepthCNN()(torch.randn(2, 2, 60, 60)).shape == (2, 1024)
    tr = TRNet()
    h = tr.step(torch.randn(2, 2, 60, 60), torch.randn(2, 128), torch.zeros(2, 128))
    rough, refined = tr.decode(h)
    assert rough.shape == (2, 32, 16) and refined.shape == (2, 32, 16)
    ie = IEEstimator(PerceptionCfg())
    m = ie.map_cnn(torch.randn(2, 1, 32, 16))
    assert m.flatten(2).transpose(1, 2).shape == (2, 128, 64)  # 토큰 128 x 64
    out = ie.estimate(torch.randn(2, 128), torch.randn(2, 32, 16))
    assert [out[k].shape[-1] for k in ("mu", "v", "zb", "zf")] == [16, 3, 16, 16]
    assert ie.last_num_map_tokens == 128


def test_negative_61():
    with pytest.raises(ValueError):
        DepthCNN()(torch.randn(2, 2, 61, 61))


def test_g0_has_no_map_tokens():
    p = StartPerception(PerceptionCfg(map_input="none"))
    assert p.trnet is None
    p.ie.estimate(torch.randn(3, 128), None)
    assert p.ie.last_num_map_tokens == 0
    assert not any("map_cnn" in n for n, _ in p.named_parameters())


def test_loss_tr_expected():
    hb = torch.randn(1, 32, 16)
    assert float(loss_tr(hb.clone(), hb.clone(), hb)) == 0.0
    off = hb.clone()
    off[0, 3, 4] += 0.1
    assert math.isclose(float(loss_tr(off, off, hb)), 0.01 / 512 + 0.1 / 512, rel_tol=1e-4)


def test_adasmpl_expected():
    a = AdaSmpl(p_init=0.5)
    a.add(torch.tensor([1.0, 1.0, 1.0]))
    assert a.update() == 0.0
    a.add(torch.tensor([0.0, 2.0]))
    assert math.isclose(a.update(), math.tanh(1.0), rel_tol=1e-5)  # 0.7616 (분모 eps 1e-6 만큼 차이)
    assert math.isclose(math.tanh(1.0), 0.7616, abs_tol=1e-4)
    # 끝난 에피소드가 2 개 미만이면 그대로
    a.add(torch.tensor([5.0]))
    assert math.isclose(a.update(), math.tanh(1.0), rel_tol=1e-5)
    assert AdaSmpl(force_gt=True).sample(5, "cpu").all()


def _rollout(p: StartPerception, n=6, T=24, done_at=None, seed=0):
    """step() 으로 수집하며 재생 버퍼를 채운다. 수집 때 추정값도 돌려준다."""
    g = torch.Generator().manual_seed(seed)
    st = p.init_state(n, "cpu")
    st.use_gt = torch.tensor([True, False] * (n // 2))
    rb = PerceptionReplay(n, T, "cpu", torch.float32)
    rb.start(st.h_prop, st.h_terr)
    ests, terr = [], []
    for t in range(T):
        o = torch.randn(n, 45, generator=g)
        d = torch.rand(n, 60, 60, generator=g)
        gm = torch.randn(n, 32, 16, generator=g) * 0.1
        inp = p.ingest(st, o, d)
        est = p.step(st, inp, gm, deterministic=True)
        ests.append(est)
        terr.append(st.h_terr.clone())
        rb.add_pre(inp, o, gm, torch.randn(n, 100, generator=g), torch.randn(n, 3, generator=g), st.use_gt)
        done = torch.zeros(n, dtype=torch.bool)
        if done_at is not None and t == done_at:
            done[0] = True
        rb.add_post(torch.randn(n, 45, generator=g), done)
        p.reset_envs(st, done, torch.zeros(n, dtype=torch.bool))
    return rb, ests, terr


def test_terrain_gru_advances_only_on_ticks():
    torch.manual_seed(0)
    p = StartPerception()
    _, _, terr = _rollout(p, T=24)
    changes = sum(int(not torch.equal(terr[t][1], terr[t - 1][1])) for t in range(1, 24)) + 1  # t=0 은 0 에서 진행
    assert changes == 5  # 틱 0 · 5 · 10 · 15 · 20
    # done 을 12 에 두면 env 0 은 13 에서 다시 0 부터 센다: 틱 0 · 5 · 10 · 13 · 18 · 23 = 6
    _, _, terr2 = _rollout(StartPerception(), T=24, done_at=12)
    ch0 = [t for t in range(1, 24) if not torch.equal(terr2[t][0], terr2[t - 1][0])]
    assert ch0 == [5, 10, 13, 18, 23]


def test_replay_equals_collection():
    """재생(gradient 켬) 이 수집 때와 같은 추정을 낸다 = 시간축 · 시작 상태 · 마스크를 같게 다룬다."""
    torch.manual_seed(1)
    p = StartPerception()
    rb, ests, _ = _rollout(p, T=24, done_at=12)
    b = rb.gather(torch.arange(6))
    h_prop, h_terr = b["h_prop0"], b["h_terr0"]
    for t in range(24):
        h_prop, h_terr, out = p._advance(h_prop, h_terr, b["hist"][t], b["depth2"][t], b["tick"][t], b["first"][t],
                                         b["use_gt"][t], b["gt_map"][t])
        est = torch.cat([out["mu"], out["v"], out["zf"], out["zb"]], -1)
        assert torch.allclose(est, ests[t], atol=1e-5), t


def test_terminal_mask_excludes_done_transition():
    torch.manual_seed(2)
    p = StartPerception()
    rb, _, _ = _rollout(p, T=24, done_at=12)
    b = rb.gather(torch.arange(6))
    torch.manual_seed(7)
    base = float(p.sequence_loss(b)["o_next"])
    b["next_obs"][12, 0] += 1e3  # done 인 전이의 「다음 관측」 은 새 에피소드 첫 관측: 손실에 들어가면 안 된다
    torch.manual_seed(7)
    assert math.isclose(float(p.sequence_loss(b)["o_next"]), base, rel_tol=1e-6)
    b["next_obs"][11, 0] += 1e3  # negative control: done 이 아닌 전이는 들어가야 한다
    torch.manual_seed(7)
    assert float(p.sequence_loss(b)["o_next"]) > base * 10


def test_gradient_boundaries_inside_perception():
    torch.manual_seed(3)
    p = StartPerception()
    rb, _, _ = _rollout(p, T=6)
    b = rb.gather(torch.arange(6))
    res = p.sequence_loss(b)
    res["l_tr"].backward(retain_graph=True)
    assert all(q.grad is None for q in p.ie.parameters()), "L_TR 이 I-E 로 흘렀다"
    assert any(q.grad is not None for q in p.trnet.parameters())
    p.zero_grad(set_to_none=True)
    res["l_ie"].backward()
    assert all(q.grad is None for q in p.trnet.parameters()), "L_IE 가 TR-Net 으로 흘렀다"
    assert any(q.grad is not None for q in p.ie.parameters())


def test_replay_depth_float16_bytes():
    rb = PerceptionReplay(3072, 24, "meta")
    assert rb.data["depth2"].dtype == torch.float16
    assert rb.data["depth2"].numel() * 2 == 3072 * 24 * 2 * 60 * 60 * 2  # 0.989 GiB (12 §6.1)
    assert math.isclose(rb.data["depth2"].numel() * 2 / 2**30, 0.989, abs_tol=1e-3)


def test_each_detach_layer_alone():
    """detach 는 두 겹(_advance 의 refined.detach · estimate 의 hmap.detach)이다. 하나만 빠져도 잡히게 겹마다 따로 본다."""
    torch.manual_seed(4)
    p = StartPerception()
    # 겹 1: estimate 는 gradient 가 붙은 지도를 받아도 지도 쪽으로 흘리지 않는다
    hmap = torch.randn(3, 32, 16, requires_grad=True)
    out = p.ie.estimate(torch.randn(3, 128), hmap)
    sum(v.sum() for v in out.values()).backward()
    assert hmap.grad is None, "estimate 가 지도로 gradient 를 흘렸다"
    # 겹 2: _advance 가 I-E 에 넘기는 지도는 이미 gradient 가 끊겨 있다
    seen = {}
    orig = p.ie.estimate

    def spy(z_prop, m):
        seen["requires_grad"] = m.requires_grad
        return orig(z_prop, m)

    p.ie.estimate = spy
    n = 4
    p._advance(torch.zeros(n, 128), torch.zeros(n, 128), torch.randn(n, 10, 45), torch.rand(n, 2, 60, 60),
               torch.ones(n, dtype=torch.bool), torch.ones(n, dtype=torch.bool), torch.zeros(n, dtype=torch.bool),
               torch.randn(n, 32, 16))
    assert seen["requires_grad"] is False, "_advance 가 gradient 붙은 재구성 지도를 I-E 에 넘겼다"
