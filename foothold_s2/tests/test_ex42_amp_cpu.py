"""AMP reference cutting and discriminator (plan AMP-PLAN-1126 steps 1-2): known-answer cases, no Kit, no trace files."""
import numpy as np
import torch

from foothold_s2.runners import ex42_amp_disc as amp
from foothold_s2.tools import ex42_amp_reference as ref


def test_label_walk_stop_stand_and_segments():
    wall = np.arange(200) * 0.02
    stick = np.zeros((200, 3))
    stick[20:60, 1] = 0.5                                  # walk 0.8 s, then zero stick
    kind = ref.label(stick, wall)
    assert (kind[20:60] == 0).all()
    assert (kind[60:60 + 74] == 1).all() and kind[60 + 76] == 2   # stop for 1.5 s after the last moving row
    assert (kind[:20] == 2).all()
    wall2 = wall.copy()
    wall2[100:] += 1.0                                     # a time gap starts a new segment
    seg = ref.segments(wall2, kind)
    assert seg[19] != seg[20] and seg[99] != seg[100] and seg[100] == seg[101]


def test_grad_penalty_is_on_the_normalised_input():
    disc = amp.AmpDiscriminator(2, (8,), torch.zeros(2), torch.tensor([0.05, 1.0]))
    x = torch.randn(16, 2)
    xn = disc.normalize(x).requires_grad_(True)
    (g,) = torch.autograd.grad(disc.net(xn).sum(), xn)
    assert torch.allclose(amp.grad_penalty(disc, x), g.square().sum(-1).mean())


def test_discriminator_separates_reference_from_noise_and_reward_range():
    torch.manual_seed(0)
    n = 4000
    t = torch.rand(n, 1) * 6.28
    xr = torch.cat([torch.sin(t), torch.cos(t), torch.sin(t + 0.1), torch.cos(t + 0.1)], 1)   # a circle: correlated columns
    xp = torch.randn(n, 4) * xr.std(0) + xr.mean(0)                                         # same per-column moments, no structure
    disc = amp.AmpDiscriminator(4, (64, 64), xr.mean(0), xr.std(0))
    opt = torch.optim.Adam(disc.parameters(), lr=1e-3)
    for _ in range(300):
        i = torch.randint(n, (256,))
        amp.disc_step(disc, opt, xr[i], xp[i])
    with torch.no_grad():
        dr, dp = disc(xr), disc(xp)
    assert float(dr.mean()) > 0.5 and float(dp.mean()) < -0.3
    r = amp.style_reward(torch.linspace(-3, 3, 61))
    assert float(r.min()) == 0.0 and float(r.max()) == 1.0


def _fake_env(n=6):
    import types
    from foothold_s2.rewards import ex42_amp_style as st
    names = list(st.JOINTS)[::-1]                                       # sim order differs: the term must index by name
    data = types.SimpleNamespace(joint_pos=torch.randn(n, 12), default_joint_pos=torch.zeros(n, 12), joint_vel=torch.randn(n, 12),
                                 root_ang_vel_b=torch.randn(n, 3), projected_gravity_b=torch.tensor([[0.0, 0.0, -1.0]]).repeat(n, 1))
    robot = types.SimpleNamespace(joint_names=names, data=data)
    terrain = types.SimpleNamespace(terrain_levels=torch.tensor([0, 1, 2, 0, 0, 0]), terrain_types=torch.tensor([0, 0, 0, 1, 0, 0]))
    cmd = torch.tensor([[0.3, 0, 0], [0.0, 0, 0], [0.3, 0, 0], [0.3, 0, 0], [0.0, 0, 0.5], [0.5, 0, 0]])
    raw = types.SimpleNamespace(episode_length_buf=torch.tensor([5, 5, 5, 5, 5, 0]), common_step_counter=600, device="cpu",
                                _ex42_column_table=[{"family": "A", "kind": "flat"}, {"family": "B", "kind": "beam"}],
                                _ex42_hip_sparse_mask=torch.tensor([False, True]))
    scene = type("Scene", (), {"terrain": terrain, "__getitem__": lambda self, k: {"robot": robot}[k]})()
    env = types.SimpleNamespace(unwrapped=raw, scene=scene, device="cpu", command_manager=types.SimpleNamespace(get_command=lambda name: cmd))
    return env, raw


def test_amp_term_mask_ramp_buffer_and_training_in_inference_mode(monkeypatch, tmp_path, capsys):
    import types
    from foothold_s2.rewards import ex42_amp_style as st
    from foothold_s2.rewards import ex42_hip_sparse
    rng = np.random.default_rng(0)
    s = rng.standard_normal((400, 30)).astype(np.float32)
    np.savez(tmp_path / "ref.npz", s=s, seg=np.repeat(np.arange(4), 100), kind=np.repeat([0, 0, 1, 2], 100))
    monkeypatch.setenv(st.ENV_SWITCH, "1"); monkeypatch.setenv(st.WEIGHT_ENV, "0.5"); monkeypatch.setenv(st.REF_ENV, str(tmp_path / "ref.npz"))
    monkeypatch.setenv(st.PARAMS_ENV, "batch=16,buffer=64,disc_every=2,disc_steps=1,ramp_steps=1200,band_max_level=1,flatlike_only=1")
    monkeypatch.setattr(ex42_hip_sparse, "sparse_envs", lambda env: torch.tensor([False, False, False, True, False, False]))
    st._STATE.clear()
    env, raw = _fake_env()
    p = st.params()
    with torch.inference_mode():
        r0 = st.ex42_amp_style(env, "base_velocity", types.SimpleNamespace(name="robot"), p)
        assert float(r0.abs().sum()) == 0.0                              # no previous state yet
        for _ in range(12):
            r = st.ex42_amp_style(env, "base_velocity", types.SimpleNamespace(name="robot"), p)
    # rows: 0 ok · 1 ok (still) · 2 level 2 · 3 sparse column · 4 ok (spin) · 5 fresh episode
    assert (r[[2, 3, 5]] == 0).all() and (r[[0, 1, 4]] > 0).all()
    assert float(r.max()) <= 0.5 + 1e-6                                   # ramp 600 / 1200 times style <= 1
    assert st._STATE["updates"] > 0 and st._STATE["buf"].n == 36
    ck = st.checkpoint_entry()
    assert set(ck) == {"amp_disc"} and "net.0.weight" in ck["amp_disc"]["disc"]
    assert "EX42_AMP_MON calls=1 " in capsys.readouterr().out
    st._STATE.clear()
    st.load_checkpoint_entry(ck["amp_disc"])
    assert "pending" in st._STATE
    st._STATE.clear()


def test_amp_condition_and_off_switch(monkeypatch):
    from foothold_s2.rewards import ex42_amp_style as st
    c = st.condition(torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, 0.3], [0.2, 0.0, 0.0]]))
    assert c.tolist() == [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0]]
    for k in (st.ENV_SWITCH, st.WEIGHT_ENV, st.REF_ENV, st.PARAMS_ENV):
        monkeypatch.delenv(k, raising=False)
    assert st.enabled() is False
    monkeypatch.setenv(st.WEIGHT_ENV, "0.5")
    import pytest
    with pytest.raises(ValueError):
        st.enabled()


def test_signature_gate_accepts_amp_disc_key():
    from foothold_s2.tools import ex42_policy_signature_gate as gate
    base = {"model_state_dict": {"actor.0.weight": torch.zeros(4, 3), "std": torch.zeros(4)}, "normalization_state": {"a": True}}
    cand = dict(base, amp_disc={"disc": {"net.0.weight": torch.zeros(2, 2)}})
    rep = gate.compare(base, cand)
    assert rep["same"] and rep["extra_top_level_in_cand"] == ["amp_disc"]
