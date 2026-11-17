"""속도 가지 (DESIGN-SLOW-WALK 7 절 ㄱ-2) 시험: 꺼짐 = 옛것과 같은 모양 · 켜짐이어도 z zf zb 는 비트 같음 · 명령 칸만 바꾸면 가지 출력이 정확히 같음 · 리셋 · 재생 = 수집 · 옛 저장본 읽기."""
import pytest
import torch

from foothold_s2.models.start_perception import (
    VEL_BRANCH_CMD_COLS, PerceptionCfg, StartPerception, Z_DIM, slow_window_sums, window_fit)
from foothold_s2.runners.perception_replay import PerceptionReplay
from foothold_s2.runners import start_runner as sr

N, T = 6, 12


def _make(mode, seed=0, base=None):
    torch.manual_seed(seed)
    p = StartPerception(PerceptionCfg(vel_branch=mode))
    if base is not None:
        res = p.load_state_dict(base.state_dict(), strict=False)
        assert all(k.startswith("vbranch.") for k in res.missing_keys) and not res.unexpected_keys
    return p


def _inputs(seed=3):
    g = torch.Generator().manual_seed(seed)
    return [(torch.randn(N, 45, generator=g), torch.rand(N, 60, 60, generator=g), torch.randn(N, 32, 16, generator=g) * 0.1) for _ in range(T)]


def _run(p, inputs, hist_edit=None):
    st = p.init_state(N, "cpu")
    st.use_gt = torch.tensor([True, False] * (N // 2))
    outs = []
    for o, d, gm in inputs:
        inp = p.ingest(st, o, d)
        if hist_edit is not None:
            inp = dict(inp, hist=hist_edit(inp["hist"]))
        outs.append(p.step(st, inp, gm, deterministic=True))
    return torch.stack(outs), st


def test_off_has_no_branch_and_old_shapes():
    p = _make("off")
    assert p.vbranch is None and p.hp_dim == 128
    assert not any(k.startswith("vbranch") for k in p.state_dict())
    assert p.init_state(3, "cpu").h_prop.shape == (3, 128)


def test_bad_mode_rejected():
    with pytest.raises(ValueError):
        StartPerception(PerceptionCfg(vel_branch="maybe"))


def test_shadow_and_replace_keep_z_zf_zb_bitwise_and_v_follows_mode():
    base = _make("off")
    inputs = _inputs()
    e_off, _ = _run(base, inputs)
    e_sh, _ = _run(_make("shadow", base=base), inputs)
    e_rp, _ = _run(_make("replace", base=base), inputs)
    zs, vs, rest = slice(0, Z_DIM), slice(Z_DIM, Z_DIM + 3), slice(Z_DIM + 3, 51)
    for e in (e_sh, e_rp):
        assert torch.equal(e[..., zs], e_off[..., zs]) and torch.equal(e[..., rest], e_off[..., rest])
    assert torch.equal(e_sh[..., vs], e_off[..., vs])           # shadow: 정책이 받는 속도는 옛 머리 값 그대로
    assert not torch.equal(e_rp[..., vs], e_off[..., vs])        # replace: 가지 출력


def test_command_columns_cannot_move_branch_output_but_move_old_head():
    base = _make("off")
    rp = _make("replace", base=base)
    inputs = _inputs()

    def edit(h):
        h = h.clone()
        h[..., list(VEL_BRANCH_CMD_COLS)] += 0.1
        return h
    a, _ = _run(rp, inputs)
    b, _ = _run(rp, inputs, hist_edit=edit)
    v = slice(Z_DIM, Z_DIM + 3)
    assert torch.equal(a[..., v], b[..., v])                     # 개입 비 정확히 0
    sh = _make("shadow", base=base)
    c, _ = _run(sh, inputs)
    d, _ = _run(sh, inputs, hist_edit=edit)
    assert not torch.equal(c[..., v], d[..., v])                 # 옛 머리는 명령을 따라간다 (시험이 개입을 실제로 넣었다는 확인)


def test_reset_clears_branch_state():
    rp = _make("replace")
    inputs = _inputs()
    st = rp.init_state(N, "cpu")
    for o, d, gm in inputs[:5]:
        rp.step(st, rp.ingest(st, o, d), gm, deterministic=True)
    assert float(st.h_prop[:, 128:].abs().sum()) > 0
    rp.reset_envs(st, torch.ones(N, dtype=torch.bool), torch.ones(N, dtype=torch.bool))
    assert float(st.h_prop.abs().sum()) == 0
    o, d, gm = inputs[5]
    fresh = rp.init_state(N, "cpu")
    fresh.use_gt = st.use_gt.clone()
    e1 = rp.step(st, rp.ingest(st, o, d), gm, deterministic=True)
    e2 = rp.step(fresh, rp.ingest(fresh, o, d), gm, deterministic=True)
    assert torch.equal(e1, e2)


def test_replay_equals_collection_and_loss_graph_is_separate():
    p = _make("replace", seed=1)
    g = torch.Generator().manual_seed(5)
    st = p.init_state(N, "cpu")
    st.use_gt = torch.tensor([True, False] * (N // 2))
    rb = PerceptionReplay(N, T, "cpu", torch.float32, h_prop_dim=p.hp_dim)
    rb.start(st.h_prop, st.h_terr)
    ests = []
    for t in range(T):
        o = torch.randn(N, 45, generator=g)
        inp = p.ingest(st, o, torch.rand(N, 60, 60, generator=g))
        gm = torch.randn(N, 32, 16, generator=g) * 0.1
        ests.append(p.step(st, inp, gm, deterministic=True))
        rb.add_pre(inp, o, gm, torch.randn(N, 100, generator=g), torch.randn(N, 3, generator=g), st.use_gt)
        rb.add_post(torch.randn(N, 45, generator=g), torch.zeros(N, dtype=torch.bool))
    b = rb.gather(torch.arange(N))
    h_prop, h_terr = b["h_prop0"], b["h_terr0"]
    for t in range(T):
        h_prop, h_terr, out = p._advance(h_prop, h_terr, b["hist"][t], b["depth2"][t], b["tick"][t], b["first"][t], b["use_gt"][t], b["gt_map"][t])
        est = torch.cat([out["mu"], p._v_out(out), out["zf"], out["zb"]], -1)
        assert torch.allclose(est, ests[t], atol=1e-5), t
    res = p.sequence_loss(b)
    assert "vb" in res and res["_vb_slope"].shape == (2, 7)
    p.zero_grad()
    res["vb"].backward(retain_graph=True)
    assert all(q.grad is None or float(q.grad.abs().sum()) == 0 for n_, q in p.named_parameters() if not n_.startswith("vbranch."))
    assert any(q.grad is not None and float(q.grad.abs().sum()) > 0 for n_, q in p.named_parameters() if n_.startswith("vbranch."))


def test_fast_replay_impl_refused_with_branch():
    p = _make("shadow")
    g = torch.Generator().manual_seed(0)
    st = p.init_state(N, "cpu")
    rb = PerceptionReplay(N, 2, "cpu", torch.float32, h_prop_dim=p.hp_dim)
    rb.start(st.h_prop, st.h_terr)
    for _ in range(2):
        o = torch.randn(N, 45, generator=g)
        inp = p.ingest(st, o, torch.rand(N, 60, 60, generator=g))
        rb.add_pre(inp, o, torch.zeros(N, 32, 16), torch.zeros(N, 100), torch.zeros(N, 3), st.use_gt)
        rb.add_post(torch.zeros(N, 45), torch.zeros(N, dtype=torch.bool))
    with pytest.raises(NotImplementedError):
        p.sequence_loss(rb.gather(torch.arange(N)), impl="a1")


def test_old_checkpoint_loads_with_fresh_branch_and_other_missing_is_an_error():
    old = _make("off")
    new = _make("shadow", seed=9)
    fresh = {k: v.clone() for k, v in new.state_dict().items() if k.startswith("vbranch.")}
    assert sr.load_perception_state(new, old.state_dict(), strict=True) is True
    assert all(torch.equal(new.state_dict()[k], v) for k, v in fresh.items())          # 가지는 새로 만든 그대로
    broken = {k: v for k, v in old.state_dict().items() if not k.startswith("ie.heads")}
    with pytest.raises(RuntimeError):
        sr.load_perception_state(new, broken, strict=True)
    assert sr.load_perception_state(_make("off"), old.state_dict()) is False


def _windows(slope, intercept, T=50, B=40, noise=0.0, seed=0):
    g = torch.Generator().manual_seed(seed)
    x = torch.linspace(0.0, 0.14, B)[None, :].expand(T, B)                                   # 환경마다 실제가 0 ~ 0.14 로 퍼진다
    jitter = noise * torch.randn(T, B, generator=g)
    est = slope * x + intercept + jitter
    return est[None], x, torch.zeros(T, B, dtype=torch.bool)


def test_window_fit_recovers_slope_and_intercept_not_the_through_origin_ratio():
    est, gt, first = _windows(0.3, 0.05)
    fit = window_fit(slow_window_sums(est, gt, first)[0])
    assert fit["slope"] == pytest.approx(0.3, abs=1e-6) and fit["intercept"] == pytest.approx(0.05, abs=1e-6)
    assert fit["zero"] == pytest.approx(0.05, abs=0.01)                                       # 실제 0 근처 칸에서의 추정 = 영점
    origin_ratio = float((est[0] * gt).sum() / (gt * gt).sum())                                # 옛 식: 영점이 섞여 기울기가 부푼다
    assert origin_ratio > 0.6


def test_window_mean_averages_step_noise_and_reset_windows_are_dropped():
    est, gt, first = _windows(0.3, 0.0, noise=0.05)
    fit = window_fit(slow_window_sums(est, gt, first)[0])
    assert fit["n"] == 2 * 40 and abs(fit["slope"] - 0.3) < 0.1                                # 25 step 창 2 개 x 40 env
    first2 = first.clone()
    first2[10, :20] = True                                                                     # 첫 창 안에서 20 env 가 리셋됨
    assert window_fit(slow_window_sums(est, gt, first2)[0])["n"] == 2 * 40 - 20


def test_window_fit_none_when_too_few_or_flat():
    assert window_fit(torch.zeros(7, dtype=torch.float64))["slope"] is None
    est, gt, first = _windows(0.3, 0.0)
    assert window_fit(slow_window_sums(est, torch.full_like(gt, 0.1), first)[0])["slope"] is None


def test_env_switches(monkeypatch):
    monkeypatch.delenv("EX42_VEL_BRANCH", raising=False)
    monkeypatch.delenv("EX42_VEL_BRANCH_FREEZE", raising=False)
    assert sr.vel_branch_mode() == "off" and sr.vel_branch_freeze() is False
    assert sr.vx_corr_params()[0] is True
    monkeypatch.setenv("EX42_VEL_BRANCH", "replace")
    assert sr.vx_corr_params()[0] is False                         # 가지가 정책에 들어가면 보정 b 는 꺼진다
    monkeypatch.setenv("EX42_VEL_BRANCH", "shadow")
    assert sr.vx_corr_params()[0] is True
    monkeypatch.setenv("EX42_VEL_BRANCH_FREEZE", "1")
    assert sr.vel_branch_freeze() is True
    monkeypatch.setenv("EX42_VEL_BRANCH", "off")
    with pytest.raises(ValueError):
        sr.vel_branch_freeze()
    monkeypatch.setenv("EX42_VEL_BRANCH", "bogus")
    with pytest.raises(ValueError):
        sr.vel_branch_mode()


def test_mask_config_hides_action_columns_too_and_default_is_cmd_only():
    from foothold_s2.models.start_perception import VEL_BRANCH_ACTION_COLS
    base = _make("off")
    inputs = _inputs()
    p_cmd = StartPerception(PerceptionCfg(vel_branch="replace"))
    p_act = StartPerception(PerceptionCfg(vel_branch="replace", vel_branch_mask="cmd_action"))
    assert float(p_cmd.vbranch.cmd_mask[list(VEL_BRANCH_ACTION_COLS)].min()) == 1.0           # 기본: 행동 칸은 보임
    assert float(p_act.vbranch.cmd_mask[list(VEL_BRANCH_ACTION_COLS)].max()) == 0.0
    assert float(p_act.vbranch.cmd_mask[list(VEL_BRANCH_CMD_COLS)].max()) == 0.0
    for p in (p_cmd, p_act):
        p.load_state_dict(base.state_dict(), strict=False)

    def edit(h):
        h = h.clone(); h[..., list(VEL_BRANCH_ACTION_COLS)] += 0.3
        return h
    v = slice(Z_DIM, Z_DIM + 3)
    a, _ = _run(p_act, inputs); b, _ = _run(p_act, inputs, hist_edit=edit)
    assert torch.equal(a[..., v], b[..., v])                                                  # 행동 칸까지 가리면 행동을 바꿔도 같다
    c, _ = _run(p_cmd, inputs); d, _ = _run(p_cmd, inputs, hist_edit=edit)
    assert not torch.equal(c[..., v], d[..., v])                                              # 기본 가림에서는 행동 칸이 간접 길
    with pytest.raises(ValueError):
        StartPerception(PerceptionCfg(vel_branch="shadow", vel_branch_mask="bogus"))


def test_input_log_replays_branch_and_swaps_action_columns_from_a_donor_record():
    from foothold_s2.models.start_perception import VEL_BRANCH_ACTION_COLS
    rp = _make("replace", seed=2)
    inputs = _inputs(3)
    donor_inputs = _inputs(11)                                                                 # 다른 명령으로 걸은 기록 (같은 시각 · 같은 env 수)
    rp.record_inputs(True)
    est, _ = _run(rp, inputs)
    log = rp.input_log
    rp.record_inputs(True)
    _run(rp, donor_inputs)
    donor = rp.input_log
    assert len(log) == T and log[0]["hist"].shape == (N, 10, 45)
    again = rp.branch_from_log(log)
    assert torch.allclose(again, est[..., Z_DIM:Z_DIM + 3], atol=1e-6)                         # 기록으로 다시 돌린 가지 = 수집 때 값
    direct = rp.branch_from_log(log, VEL_BRANCH_CMD_COLS, donor)
    assert torch.equal(direct, again)                                                          # 직접 개입 (명령 칸 바꿔 끼움): 정확히 같음
    indirect = rp.branch_from_log(log, VEL_BRANCH_ACTION_COLS, donor)
    assert not torch.equal(indirect, again)                                                    # 간접 개입 (행동 칸 바꿔 끼움): 달라진다 = 잴 수 있다
    with pytest.raises(ValueError):
        rp.branch_from_log(log, VEL_BRANCH_ACTION_COLS, donor[:3])
    rp.record_inputs(False)
    assert rp.input_log is None


def test_window_fit_keeps_only_forward_slow_command_windows():
    est, gt, first = _windows(0.3, 0.05)
    T, B = gt.shape
    cmd = torch.zeros(T, B, 3); cmd[..., 0] = 0.1
    assert window_fit(slow_window_sums(est, gt, first, cmd)[0])["n"] == 2 * B                 # 전부 앞으로 느림
    stand = cmd.clone(); stand[:, :10, 0] = 0.0                                                # 서기 10 env
    side = cmd.clone(); side[:, 10:20, 1] = 0.2                                                # 옆걸음 10 env
    turn = cmd.clone(); turn[:, 20:25, 2] = 0.3                                                # 회전 5 env
    mixed = torch.where(torch.arange(B)[None, :, None] < 10, stand, torch.where(torch.arange(B)[None, :, None] < 20, side, torch.where(torch.arange(B)[None, :, None] < 25, turn, cmd)))
    assert window_fit(slow_window_sums(est, gt, first, mixed)[0])["n"] == 2 * (B - 25)
    half = cmd.clone(); half[30:, :, 0] = 0.0                                                  # 둘째 창은 서기로 바뀜
    assert window_fit(slow_window_sums(est, gt, first, half)[0])["n"] == B
