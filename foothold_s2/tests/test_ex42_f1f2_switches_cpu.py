"""F1 / F2 switches (lead 2026-11-25 20:23): stand tilt, stand load balance, front-load DR and actor mirror augmentation.
Real command runtime (stop bundle fixture), real START runner and update loop on CPU; known-answer values by hand."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
import torch

from foothold_s2.curriculum import ex42_front_load_dr as fl
from foothold_s2.rewards import ex42_stand_tilt_load as st
from foothold_s2.rewards.ex42_stop_bundle import stop_mask
from foothold_s2.tests.test_ex42_stop_bundle_cpu import N, SENSOR, _draw, _env


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    st._SUMS.clear()
    st._FIRST.clear()
    for name in (st.TILT, st.LOAD, st.TILT + "_W", st.LOAD + "_W", st.DELAY_ENV, fl.ENV_SWITCH, fl.PARAMS_ENV,
                 "EX42_ACTOR_MIRROR_AUG", "EX42_ACTOR_MIRROR_W", "EX42_STOP_BUNDLE", "EX42_STOP_BUNDLE_PARAMS"):
        monkeypatch.delenv(name, raising=False)


def _stand_env(monkeypatch):
    command, raw, data = _env(monkeypatch)
    _draw(command)
    data.projected_gravity_b = torch.tensor([0.06, -0.08, -0.994]).repeat(N, 1)   # 0.0036 + 0.0064 = 0.01
    raw._ex40_total_mass_kg = torch.full((N,), 15.0)
    raw.scene.sensors["contact_forces"].data.net_forces_w[:, :, 2] = torch.tensor([40.0, 30.0, 50.0, 20.0])
    return command, raw, data


# -- gates -------------------------------------------------------------------------------------------------------------

def test_off_registers_nothing_and_bad_values_refuse(monkeypatch):
    cfg = NS(rewards=NS(), events=NS(ex40_base_com=None))
    assert st.register(cfg, term_cfg_class=dict, entity_cfg_class=lambda *a, **k: NS(a=a, k=k)) == []
    assert fl.register(cfg, term_cfg_class=dict, entity_cfg_class=lambda *a, **k: None) is False
    assert vars(cfg.rewards) == {} and vars(cfg.events) == {"ex40_base_com": None}
    assert st.summary() is None
    for switch, raw in ((st.TILT, "2"), (st.LOAD, "yes"), (fl.ENV_SWITCH, "on"), ("EX42_ACTOR_MIRROR_AUG", "2")):
        monkeypatch.setenv(switch, raw)
        with pytest.raises(ValueError, match=switch):
            (fl.enabled() if switch == fl.ENV_SWITCH else st.enabled(switch) if switch != "EX42_ACTOR_MIRROR_AUG"
             else __import__("foothold_s2.runners.ex42_actor_mirror", fromlist=["x"]).aug_from_env())
        monkeypatch.delenv(switch)
    monkeypatch.setenv(st.TILT + "_W", "-1")
    with pytest.raises(ValueError, match="is not 1"):
        st.enabled(st.TILT)
    monkeypatch.setenv(st.TILT, "1")
    for bad in ("0", "0.5", "nan", "x"):
        monkeypatch.setenv(st.TILT + "_W", bad)
        with pytest.raises(ValueError, match="EX42_STAND_TILT_W"):
            st.weight(st.TILT)
    monkeypatch.setenv(fl.ENV_SWITCH, "1")
    for bad in ("mass_lo=0.5,mass_hi=0.4", "x=0", "q=1", "x=abc", "z=0.5"):
        monkeypatch.setenv(fl.PARAMS_ENV, bad)
        with pytest.raises(ValueError, match=fl.PARAMS_ENV):
            fl.params()


# -- F1 stand terms ----------------------------------------------------------------------------------------------------

def test_tilt_and_load_known_answers_only_on_stand_after_delay(monkeypatch, capsys):
    monkeypatch.setenv(st.TILT, "1")
    monkeypatch.setenv(st.LOAD, "1")
    command, raw, data = _stand_env(monkeypatch)
    stand = stop_mask(raw, "base_velocity")
    assert 50 < int(stand.sum()) < N // 2                     # real draw: stand slot on the continuous column only
    command.stop_elapsed_s[:] = 0.5                           # inside the 1 s delay: both 0
    assert bool((st.ex42_stand_tilt(raw, "base_velocity", NS(name="robot"), 1.0) == 0).all())
    assert bool((st.ex42_load_balance(raw, "base_velocity", SENSOR, 1.0) == 0).all())
    command.stop_elapsed_s[:] = 1.0
    tilt = st.ex42_stand_tilt(raw, "base_velocity", NS(name="robot"), 1.0)
    load = st.ex42_load_balance(raw, "base_velocity", SENSOR, 1.0)
    # |40 - 30| + |50 - 20| = 40 N over 15 kg x 9.81
    assert torch.allclose(tilt[stand], torch.full_like(tilt[stand], 0.01), atol=1e-6)
    assert torch.allclose(load[stand], torch.full_like(load[stand], 40.0 / (15.0 * 9.81)), atol=1e-6)
    assert bool((tilt[~stand] == 0).all()) and bool((load[~stand] == 0).all())
    walking_or_sparse = ~stand
    assert int(walking_or_sparse.sum()) > N // 2
    out = capsys.readouterr().out
    assert "EX42_STAND_TILT first_active envs=%d" % int(stand.sum()) in out
    assert "EX42_LOAD_BALANCE first_active" in out
    row = st.summary()
    assert row["tilt_active_env_steps"] == int(stand.sum()) and row["tilt_value_mean"] == pytest.approx(0.01, abs=1e-6)
    assert row["load_value_mean"] == pytest.approx(40.0 / 147.15, abs=1e-6)


def test_load_is_left_right_per_pair_not_front_rear(monkeypatch):
    fz = torch.tensor([[50.0, 50.0, 25.0, 25.0], [50.0, 25.0, 25.0, 50.0], [-5.0, 0.0, 0.0, 0.0]])
    value = st.load_value(fz, torch.full((3,), 10.0))
    assert value.tolist() == pytest.approx([0.0, 50.0 / 98.1, 0.0])   # front-heavy stance is free; negative force clipped


def test_register_adds_two_terms_with_weights_and_start_lines(monkeypatch, capsys):
    monkeypatch.setenv(st.TILT, "1")
    monkeypatch.setenv(st.LOAD, "1")
    monkeypatch.setenv(st.LOAD + "_W", "-0.25")
    cfg = NS(rewards=NS())
    made = st.register(cfg, term_cfg_class=lambda **k: NS(**k), entity_cfg_class=lambda *a, **k: NS(name=a[0], **k))
    assert made == [st.TILT, st.LOAD]
    assert cfg.rewards.ex42_stand_tilt.weight == -1.0 and cfg.rewards.ex42_stand_tilt.func is st.ex42_stand_tilt
    assert cfg.rewards.ex42_load_balance.weight == -0.25
    assert cfg.rewards.ex42_load_balance.params["sensor_cfg"].body_names == list(st.FEET)
    out = capsys.readouterr().out
    assert "EX42_STAND_TILT where=start term=ex42_stand_tilt w=-1 delay_s=1" in out
    assert "EX42_LOAD_BALANCE where=start term=ex42_load_balance w=-0.25" in out
    with pytest.raises(ValueError, match="twice"):
        st.register(cfg, term_cfg_class=lambda **k: NS(**k), entity_cfg_class=lambda *a, **k: NS(name=a[0], **k))


def test_mutation_mask_inverted_or_weight_ignored_fails(monkeypatch):
    """The known-answer test above must catch an inverted mask or a dropped mass divisor."""
    monkeypatch.setenv(st.TILT, "1")
    command, raw, data = _stand_env(monkeypatch)
    command.stop_elapsed_s[:] = 1.0
    stand = stop_mask(raw, "base_velocity")
    good = st.ex42_stand_tilt(raw, "base_velocity", NS(name="robot"), 1.0)
    inverted = torch.where(~stand, st.tilt_value(data.projected_gravity_b), torch.zeros(N))
    assert not torch.equal(good, inverted)
    assert not torch.allclose(st.load_value(torch.tensor([[40.0, 30, 50, 20]]), torch.tensor([15.0])),
                              torch.tensor([40.0]))


# -- F1 front-load DR --------------------------------------------------------------------------------------------------

class _View:
    def __init__(self, n):
        self.m = torch.tensor([[6.9, 1.0]]).repeat(n, 1)
        self.i = torch.tensor([[0.1] * 9, [0.01] * 9]).repeat(n, 1, 1)
        self.c = torch.zeros(n, 2, 7)
        self.c[:, 0, 0] = 0.02
        self.c[:, :, 6] = 1.0
        self.com_sets = 0

    def get_masses(self): return self.m.clone()
    def set_masses(self, m, ids): self.m[ids] = m[ids]
    def get_inertias(self): return self.i.clone()
    def set_inertias(self, i, ids): self.i[ids] = i[ids]
    def get_coms(self): return self.c.clone()

    def set_coms(self, c, ids):
        self.com_sets += 1
        self.c[ids] = c[ids]


class _Scene(dict):
    num_envs = 64


def _env_for(view, n=64):
    scene = _Scene(robot=NS(root_physx_view=view))
    scene.num_envs = n
    env = NS(scene=scene, cfg=NS(seed=3))
    return env


def test_front_load_known_answer_and_reset_keeps_the_shift(monkeypatch, capsys):
    monkeypatch.setenv(fl.ENV_SWITCH, "1")
    reset_calls = []

    def ex40_reset(env, env_ids, asset_cfg, target_range):    # restores the baseline CoM like reset_base_com does
        coms = env.scene["robot"].root_physx_view.get_coms().clone()
        coms[env_ids, 0, :3] = torch.tensor([0.02, 0.0, 0.0])
        env.scene["robot"].root_physx_view.set_coms(coms, env_ids)
        reset_calls.append(len(env_ids))

    cfg = NS(events=NS(ex40_base_com=NS(func=ex40_reset, params={"asset_cfg": NS(name="robot"), "target_range": {}})))
    assert fl.register(cfg, term_cfg_class=lambda **k: NS(**k), entity_cfg_class=lambda *a, **k: NS(name=a[0], body_ids=[0]))
    assert "EX42_FRONT_LOAD_DR where=start mass_kg=[0.3,0.4] x_m=0.25 z_m=0 com_path=after_ex40_base_com_reset" in capsys.readouterr().out
    view = _View(64)
    env = _env_for(view)
    cfg.events.ex42_front_load_reset_owned.func(env, None)    # startup order: marker first
    term = cfg.events.ex42_front_load
    term.func(env, None, **term.params)
    load = view.m[:, 0] - 6.9
    assert float(load.min()) >= 0.3 - 1e-6 and float(load.max()) <= 0.4 + 1e-6 and float(load.std()) > 0.01
    assert view.com_sets == 0                                   # the reset wrapper owns the CoM
    assert torch.allclose(view.i[:, 0, 0], 0.1 * (6.9 + load) / 6.9)
    expected_dx = load * (0.25 - 0.02) / (6.9 + load)           # 0.35 kg -> 0.01113 m
    rows = torch.arange(64)
    cfg.events.ex40_base_com.func(env, rows, **cfg.events.ex40_base_com.params)
    assert torch.allclose(view.c[:, 0, 0], 0.02 + expected_dx, atol=1e-7) and reset_calls == [64]
    cfg.events.ex40_base_com.func(env, rows[:5], **cfg.events.ex40_base_com.params)   # second reset: no double shift
    assert torch.allclose(view.c[:, 0, 0], 0.02 + expected_dx, atol=1e-7)
    assert "EX42_FRONT_LOAD_DR applied envs=64" in capsys.readouterr().out
    rng = torch.get_rng_state()
    term.func(_env_for(_View(64)), None, **term.params)
    assert torch.equal(rng, torch.get_rng_state())             # own generator: the global stream is untouched


def test_front_load_without_reset_event_writes_the_com_once(monkeypatch):
    monkeypatch.setenv(fl.ENV_SWITCH, "1")
    cfg = NS(events=NS())
    fl.register(cfg, term_cfg_class=lambda **k: NS(**k), entity_cfg_class=lambda *a, **k: NS(name=a[0], body_ids=[0]))
    assert not hasattr(cfg.events, "ex42_front_load_reset_owned")
    view = _View(8)
    term = cfg.events.ex42_front_load
    term.func(_env_for(view, 8), None, **term.params)
    load = view.m[:, 0] - 6.9
    assert view.com_sets == 1
    assert torch.allclose(view.c[:, 0, 0], 0.02 + load * 0.23 / (6.9 + load), atol=1e-7)


# -- F2 actor mirror augmentation ----------------------------------------------------------------------------------------

def _aug_runner(monkeypatch, tmp_path, flat=True):
    from foothold_s2.runners.start_runner import StartRunner
    from foothold_s2.tests.ex41_authorization_fixture import real_authorization
    from foothold_s2.tests.start_fake_env import train_cfg
    from foothold_s2.tests.test_ex41_b345 import PoseEnv

    class FlatPoseEnv(PoseEnv):
        def _make(self):
            raw = super()._make()
            if flat:
                raw["gt_map"].zero_()
            return raw

    cfg = train_cfg(2, {"microbatch_envs": 2})
    cfg["ex41_pose_commands"] = True
    cfg["ex41_critic_mirror"] = True
    cfg["ex41_mirror_approval"] = real_authorization(tmp_path / "w72_aug")
    return StartRunner(FlatPoseEnv(num_envs=4), cfg, log_dir=None, device="cpu")


def test_aug_on_real_runner_prints_start_and_first_update_lines(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EX42_ACTOR_MIRROR_AUG", "1")
    runner = _aug_runner(monkeypatch, tmp_path)
    assert runner.alg.actor_mirror_aug is True and runner.alg.actor_mirror_weight == 0.0
    assert "EX42_ACTOR_MIRROR_AUG where=start mask=gt_map_range_lt_0.02m" in capsys.readouterr().out
    runner.learn(1)
    out = capsys.readouterr().out
    assert "EX42_ACTOR_MIRROR_AUG on update=1 rows=" in out and "fraction=1 " in out
    assert "Mean actor_mirror loss" not in out


def test_aug_and_loss_together_refuse(monkeypatch, tmp_path):
    monkeypatch.setenv("EX42_ACTOR_MIRROR_AUG", "1")
    monkeypatch.setenv("EX42_ACTOR_MIRROR_W", "0.1")
    with pytest.raises(ValueError, match="separate branches"):
        _aug_runner(monkeypatch, tmp_path)


def test_mirrored_surrogate_known_answer_on_a_symmetric_sample():
    """A sample whose mirror is itself (zero obs, zero action) gives the same per-row surrogate as the original."""
    from foothold_s2.runners.ex42_actor_mirror import mirror_action, mirrored_surrogate_rows

    class Policy:
        def act(self, obs):
            self.mean = obs["actor_in"][:, :12] * 0.5

        def get_actions_log_prob(self, a):
            return torch.distributions.Normal(self.mean, 1.0).log_prob(a).sum(-1)

    from tensordict import TensorDict
    x = torch.randn(6, 98)
    obs = TensorDict({"actor_in": x}, batch_size=[6])
    actions = torch.randn(6, 12)
    p = Policy()
    p.act(obs)
    old = p.get_actions_log_prob(actions).detach()
    adv = torch.randn(6)
    rows, ratio = mirrored_surrogate_rows(p, obs, actions, old, adv, 0.2)
    from foothold_s2.runners.ex42_actor_mirror import mirror_actor_observation
    mean_m = mirror_actor_observation(x)[:, :12] * 0.5
    logp_m = torch.distributions.Normal(mean_m, 1.0).log_prob(mirror_action(actions)).sum(-1)
    r = torch.exp(logp_m - old)
    assert torch.allclose(ratio, r) and torch.allclose(rows, torch.maximum(-adv * r, -adv * r.clamp(0.8, 1.2)))
    # mutation: using the unmirrored action gives a different value on a general sample
    assert not torch.allclose(rows, torch.maximum(-adv * torch.exp(
        torch.distributions.Normal(mean_m, 1.0).log_prob(actions).sum(-1) - old), -adv))
