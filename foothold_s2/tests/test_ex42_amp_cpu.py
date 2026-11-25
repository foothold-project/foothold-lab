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


def _fake_env(n=8):
    import types
    from foothold_s2.rewards import ex42_amp_style as st
    names = list(st.JOINTS)[::-1]                                       # sim order differs: the term must index by name
    data = types.SimpleNamespace(joint_pos=torch.randn(n, 12), default_joint_pos=torch.zeros(n, 12), joint_vel=torch.randn(n, 12),
                                 root_ang_vel_b=torch.randn(n, 3), projected_gravity_b=torch.tensor([[0.1, 0.0, -1.0]]).repeat(n, 1))
    robot = types.SimpleNamespace(joint_names=names, data=data)
    terrain = types.SimpleNamespace(terrain_levels=torch.tensor([0, 1, 2, 0, 0, 0, 0, 0]),
                                    terrain_types=torch.tensor([0, 0, 0, 1, 0, 0, 0, 0]))
    cmd = torch.tensor([[0.3, 0, 0], [0.0, 0, 0], [0.3, 0, 0], [0.3, 0, 0], [0.0, 0, 0.5], [0.5, 0, 0], [-0.4, 0.05, 0.0], [0.0, 0, 0]])
    raw = types.SimpleNamespace(episode_length_buf=torch.tensor([5, 5, 5, 5, 5, 0, 5, 5]), common_step_counter=600, device="cpu",
                                _ex42_column_table=[{"family": "A", "kind": "flat"}, {"family": "B", "kind": "beam"}],
                                _ex42_hip_sparse_mask=torch.tensor([False, True]))
    scene = type("Scene", (), {"terrain": terrain, "__getitem__": lambda self, k: {"robot": robot}[k]})()
    env = types.SimpleNamespace(unwrapped=raw, scene=scene, device="cpu", command_manager=types.SimpleNamespace(get_command=lambda name: cmd))
    return env, raw


def _fake_ref(path, rng):
    s = rng.standard_normal((500, 30)).astype(np.float32)
    s[:, 27] += 0.5                                                    # a posture offset the centring must remove
    stick = np.zeros((500, 3), dtype=np.float32)
    stick[:100, 1] = 0.6                                               # seg 0 walk, forward stick only
    stick[100:200, 0] = 0.6                                            # seg 1 walk, lateral stick: not straight
    stick[200:300, 1] = 0.6; stick[200:300, 2] = 0.4                   # seg 2 walk, forward + yaw: not straight
    np.savez(path, s=s, seg=np.repeat(np.arange(5), 100), kind=np.repeat([0, 0, 0, 1, 2], 100), stick=stick)


def test_amp_term_mask_ramp_buffer_and_training_in_inference_mode(monkeypatch, tmp_path, capsys):
    import types
    from foothold_s2.rewards import ex42_amp_style as st
    from foothold_s2.rewards import ex42_hip_sparse
    _fake_ref(tmp_path / "ref.npz", np.random.default_rng(0))
    monkeypatch.setenv(st.ENV_SWITCH, "1"); monkeypatch.setenv(st.WEIGHT_ENV, "0.5"); monkeypatch.setenv(st.REF_ENV, str(tmp_path / "ref.npz"))
    monkeypatch.setenv(st.PARAMS_ENV, "batch=16,buffer=64,disc_every=2,disc_steps=1,ramp_steps=1200,band_max_level=1,flatlike_only=1,ref_probe=32")
    monkeypatch.setattr(ex42_hip_sparse, "sparse_envs", lambda env: torch.tensor([False, False, False, True, False, False, False, False]))
    st._STATE.clear()
    env, raw = _fake_env()
    p = st.params()
    with torch.inference_mode():
        r0 = st.ex42_amp_style(env, "base_velocity", types.SimpleNamespace(name="robot"), p)
        assert float(r0.abs().sum()) == 0.0                              # no previous state yet
        for _ in range(12):
            r = st.ex42_amp_style(env, "base_velocity", types.SimpleNamespace(name="robot"), p)
    # rows: 0 straight · 1 still · 2 level 2 · 3 sparse column · 4 spin (not straight) · 5 fresh episode · 6 straight back · 7 still
    assert (r[[2, 3, 4, 5]] == 0).all() and (r[[0, 1, 6, 7]] > 0).all()
    assert float(r.max()) <= 0.5 + 1e-6                                   # ramp 600 / 1200 times style <= 1
    assert st._STATE["updates"] > 0 and st._STATE["buf"].n == 48         # 4 rows x 12 calls
    assert st._STATE["buf"].x.shape[1] == 60                              # 29 x 2 + 2: grav_z dropped
    assert bool(st._STATE["pol_center_init"].all()) and abs(float(st._STATE["pol_center"][0, 27]) - 0.1) < 1e-6
    ck = st.checkpoint_entry()
    assert set(ck) == {"amp_disc"} and "net.0.weight" in ck["amp_disc"]["disc"] and "pol_center" in ck["amp_disc"]
    out = capsys.readouterr().out
    assert "EX42_AMP_MON calls=1 " in out and "dead_frac=" in out and "D_pol_std=" in out and "pol_grav_x_walk=0.1000" in out
    st._STATE.clear()
    st.load_checkpoint_entry(ck["amp_disc"])
    assert "pending" in st._STATE
    with torch.inference_mode(False):
        st.build("cpu", p, dict(np.load(tmp_path / "ref.npz")))
    assert torch.equal(st._STATE["pol_center"], ck["amp_disc"]["pol_center"])
    st._STATE.clear()


def test_reference_classes_straight_and_centring(tmp_path):
    from foothold_s2.rewards import ex42_amp_style as st
    _fake_ref(tmp_path / "ref.npz", np.random.default_rng(1))
    npz = dict(np.load(tmp_path / "ref.npz"))
    x, centers = st.reference_transitions(npz, st.params())
    assert x.shape == (99 + 198, 60)                                      # straight seg 0 (99) + stop seg 3 and stand seg 4 (99 + 99)
    walk = x[x[:, -2] == 1]
    assert len(walk) == 99
    cols = st.input_cols(st.params())
    gx = cols.index(27)
    assert abs(float(centers[0, 27]) - float(npz["s"][:100, 27].mean())) < 1e-5 and float(centers[0, 29]) == 0.0
    assert abs(float(walk[:, gx].mean())) < 0.05                          # posture offset 0.5 removed
    off = dict(st.DEFAULTS, center=0.0, straight_only=0.0)
    x0, c0 = st.reference_transitions(npz, off)
    assert x0.shape == (297 + 198, 62) and float(c0.abs().sum()) == 0.0   # old form: all walk, 30 columns, no centring


def test_relative_style_keeps_a_ranking_when_the_discriminator_wins():
    from foothold_s2.rewards import ex42_amp_style as st
    d = torch.tensor([-1.30, -1.10, -1.05, -1.00, -0.95])                 # all D <= -0.95: the clipped LSGAN form is ~0 everywhere
    assert float(amp.style_reward(d).max()) < 0.05 and int((amp.style_reward(d) == 0).sum()) >= 3
    r = st.relative_style(d, torch.tensor(0.9), 2.0)
    assert (r > 0).all() and (r <= 1).all() and torch.all(r[1:] > r[:-1])   # ordered, nobody dead
    assert int((st.relative_style(d, torch.tensor(0.9), 0.0) == 0).sum()) == 2   # floor at the mean (-1.08): the two rows below it die again
    assert float(st.relative_style(torch.tensor([0.5]), torch.tensor(0.9), 2.0)) == 0.0


def test_disc_reference_draw_matches_the_policy_condition_mix():
    from foothold_s2.rewards import ex42_amp_style as st
    ref = torch.zeros(400, 4); ref[100:, -1] = 1.0; ref[:100, -2] = 1.0     # 100 walk : 300 still
    s = {"ref": ref, "ref_idx": [torch.arange(100), torch.arange(100, 400)]}
    xp = torch.zeros(64, 4); xp[:48, -2] = 1.0; xp[48:, -1] = 1.0           # policy 48 walk : 16 still
    i = st.ref_like(s, xp)
    assert len(i) == 64 and int((ref[i, -1] == 0).sum()) == 48


def test_amp_classes_and_off_switch(monkeypatch):
    from foothold_s2.rewards import ex42_amp_style as st
    cmd = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, 0.3], [0.2, 0.0, 0.0], [0.5, 0.3, 0.0], [-0.4, 0.05, 0.08]])
    walk, still = st.classes(cmd, st.params())
    assert still.tolist() == [True, False, False, False, False] and walk.tolist() == [False, False, True, False, True]
    walk_all, _ = st.classes(cmd, dict(st.DEFAULTS, straight_only=0.0))
    assert walk_all.tolist() == [False, True, True, True, True]
    for k in (st.ENV_SWITCH, st.WEIGHT_ENV, st.REF_ENV, st.PARAMS_ENV):
        monkeypatch.delenv(k, raising=False)
    assert st.enabled() is False
    monkeypatch.setenv(st.WEIGHT_ENV, "0.5")
    import pytest
    with pytest.raises(ValueError):
        st.enabled()
    monkeypatch.setenv(st.ENV_SWITCH, "1")
    monkeypatch.setenv(st.PARAMS_ENV, "center=2")
    with pytest.raises(ValueError):
        st.params()


def test_signature_gate_accepts_amp_disc_key():
    from foothold_s2.tools import ex42_policy_signature_gate as gate
    base = {"model_state_dict": {"actor.0.weight": torch.zeros(4, 3), "std": torch.zeros(4)}, "normalization_state": {"a": True}}
    cand = dict(base, amp_disc={"disc": {"net.0.weight": torch.zeros(2, 2)}})
    rep = gate.compare(base, cand)
    assert rep["same"] and rep["extra_top_level_in_cand"] == ["amp_disc"]
