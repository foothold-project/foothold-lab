"""v28u: the averaged perception weights (candidate C). With PERCEPTION_EMA_DECAY > 0 the rollout asks an averaged copy of the perception
module for est; the perception loss updates the online weights; model_N.pt carries perception_ema; an evaluation reads it when it is there.
Off (0) builds nothing. CPU only: the real StartRunner on the fake env, the real eval loader, the real WeightEma."""
from __future__ import annotations

import json

import pytest
import torch

from foothold_s2.eval.adapters import load_s2_runner
from foothold_s2.models.start_perception import StartPerception
from foothold_s2.runners import perception_ema as pema, start_runner
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.runners.weight_ema import WeightEma
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

N = 8
DECAY = 0.98


def _runner(seed=3, decay=DECAY, monkeypatch=None, env=None):
    torch.manual_seed(seed)
    if monkeypatch is not None:
        monkeypatch.setattr(start_runner, "PERCEPTION_EMA_DECAY", decay)
    return StartRunner(env or FakeStartEnv(num_envs=N, seed=seed), train_cfg(24, {"microbatch_envs": 4, "map_input": "reconstruction"}), log_dir=None, device="cpu")


def _params(module):
    return {k: p.detach().clone() for k, p in module.named_parameters()}


def _prepare(r):
    """what learn() does before the loop, without the loop: a state and the average."""
    r.pstate = r.perception.init_state(N, "cpu")
    r._perception_ema_init()


def _learn(r, k=1, seed=9):
    torch.manual_seed(seed)
    r.learn(k)


def test_the_constant_is_off_by_default_and_the_helper_validates_the_decay():
    assert start_runner.PERCEPTION_EMA_DECAY == 0.0
    assert pema.usable_decay(0.98) and not pema.usable_decay(0.0) and not pema.usable_decay(1.0) and not pema.usable_decay(True) and not pema.usable_decay(None)


def _count_steps(monkeypatch):
    calls: dict[int, int] = {}
    orig = StartPerception.step

    def spy(self, *a, **k):
        calls[id(self)] = calls.get(id(self), 0) + 1
        return orig(self, *a, **k)
    monkeypatch.setattr(StartPerception, "step", spy)
    return calls


def test_off_builds_nothing_saves_no_key_prints_no_line_and_rolls_out_with_the_online_module(capsys, monkeypatch):
    r = _runner(decay=0.0, monkeypatch=monkeypatch)
    calls = _count_steps(monkeypatch)
    _learn(r, 1)
    assert r.perception_wema is None and r.perception_ema is None and r.pstate_ema is None
    assert "perception_ema" not in r.state_dict()
    assert calls == {id(r.perception): r.num_steps_per_env}
    assert "EX42_PERCEPTION_EMA" not in capsys.readouterr().out and r.last_perception_ema is None


def test_on_the_rollout_asks_the_averaged_copy_and_never_the_online_module(capsys, monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    calls = _count_steps(monkeypatch)
    _learn(r, 1)
    assert "EX42_PERCEPTION_EMA where=start decay=0.98 status=start_from_loaded_weights (checkpoint has no policy_ema)" in capsys.readouterr().out
    assert calls == {id(r.perception_ema): r.num_steps_per_env}                 # the online module was never asked in the rollout
    assert float(r.pstate.h_prop.abs().sum()) == 0.0                           # so its GRU state never moved
    assert float(r.pstate_ema.h_prop.abs().sum()) > 0.0                        # the averaged copy runs its own state


def test_the_averaged_copy_is_the_shadow_and_the_online_weights_are_what_the_perception_loss_updates(monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    before = _params(r.perception)
    _learn(r, 1)
    after = _params(r.perception)
    assert any(not torch.equal(before[k], after[k]) for k in before)           # the perception loss moved the online weights
    ema = _params(r.perception_ema)
    for k, w0 in before.items():
        # one average step from the weights the run started with: shadow = w0 + (1 - decay) * (online_after - w0)
        assert torch.allclose(ema[k], w0 + (1 - DECAY) * (after[k] - w0), atol=1e-7), k
        assert r.perception_wema.shadow["perception"][k].equal(ema[k])
    assert r.perception_wema.updates == 1
    assert all(not p.requires_grad for p in r.perception_ema.parameters()) and not r.perception_ema.training


def test_the_average_formula_over_several_steps_and_a_non_finite_weight_skips_the_step(monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    _prepare(r)
    w0 = _params(r.perception)
    shadow = {k: v.clone() for k, v in w0.items()}
    for step in range(3):
        with torch.no_grad():
            for p in r.perception.parameters():
                p.add_(0.1)
        cur = _params(r.perception)
        shadow = {k: shadow[k] + (1 - DECAY) * (cur[k] - shadow[k]) for k in shadow}
        r._perception_ema_step()
    for k, v in _params(r.perception_ema).items():
        assert torch.allclose(v, shadow[k], atol=1e-6), k
    good = _params(r.perception_ema)
    with torch.no_grad():
        next(r.perception.parameters()).fill_(float("nan"))
    r._perception_ema_step()
    assert r.perception_wema.skipped == 1 and r.perception_wema.updates == 3
    for k, v in _params(r.perception_ema).items():
        assert torch.equal(v, good[k]), k


def test_a_finished_episode_resets_the_averaged_hidden_state_too(monkeypatch):
    class OneEnvEnds(FakeStartEnv):
        def step(self, actions):
            obs, rew, dones, extras = super().step(actions)
            dones = torch.zeros_like(dones)
            if self.t % 24 == 0:
                dones[0] = 1                                                      # env 0 ends at the last rollout step
            return obs, rew, dones, extras

    r = _runner(monkeypatch=monkeypatch, env=OneEnvEnds(num_envs=N, seed=3, episode_len=10_000))
    _learn(r, 1)
    assert float(r.pstate_ema.h_prop[0].abs().sum()) == 0.0 and float(r.pstate_ema.h_terr[0].abs().sum()) == 0.0
    assert float(r.pstate_ema.h_prop[1:].abs().sum(-1).min()) > 0.0


def test_the_replay_starts_from_the_averaged_hidden_state(monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    seen = {}
    start = r.replay.start
    r.replay.start = lambda h_prop, h_terr: (seen.update(h=h_prop.clone()), start(h_prop, h_terr))[1]
    _learn(r, 2)
    assert float(seen["h"].abs().sum()) > 0.0                                   # iteration 2 starts from the hidden state of the averaged run, not the (zero) online one


def test_the_line_and_the_train_extra_record_of_the_gap_between_the_online_and_the_averaged_est(capsys, tmp_path, monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    r.log_dir = str(tmp_path)
    _learn(r, 2)
    lines = [l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_PERCEPTION_EMA it=")]
    assert len(lines) == 2
    fields = dict(kv.split("=") for kv in lines[-1].split()[1:])
    assert set(fields) == {"it", "decay", "updates", "est_diff_mean", "v_diff_mean", "v_online_minus_ema"}
    assert float(fields["decay"]) == DECAY and int(fields["updates"]) == 1       # it 2 is probed before its own average step: one step so far
    assert float(fields["est_diff_mean"]) > 0.0 and float(fields["v_diff_mean"]) > 0.0
    extra = [json.loads(l) for l in (tmp_path / "train_extra.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(extra) == 2 and set(extra[-1]["perception_ema"]) == {"est_diff_mean", "v_diff_mean", "v_online_minus_ema", "updates", "decay"}


def test_the_probe_does_not_touch_the_weights_or_the_rng_state(monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    _learn(r, 1)
    w = _params(r.perception)
    e = _params(r.perception_ema)
    rng = torch.get_rng_state()
    r._perception_ema_probe(5)
    assert torch.equal(rng, torch.get_rng_state())
    for k, v in _params(r.perception).items():
        assert torch.equal(v, w[k])
    for k, v in _params(r.perception_ema).items():
        assert torch.equal(v, e[k])


def _kl_runner(decay, monkeypatch, tmp_path):
    monkeypatch.setattr(start_runner, "PERCEPTION_EMA_DECAY", decay)
    torch.manual_seed(3)
    r = StartRunner(FakeStartEnv(num_envs=N, seed=3), train_cfg(24, {"microbatch_envs": 4, "log_kl": True, "kl_probe_envs": 4}), log_dir=None, device="cpu")
    r.log_dir = str(tmp_path)
    return r


def test_the_phi_ema_kl_is_recorded_next_to_the_online_one_when_the_kl_probe_is_on(monkeypatch, tmp_path):
    r = _kl_runner(DECAY, monkeypatch, tmp_path)
    _learn(r, 1)
    kl = json.loads((tmp_path / "train_extra.jsonl").read_text(encoding="utf-8").splitlines()[-1])["kl_probe"]
    assert {"ppo", "phi", "phi_ema"} <= set(kl)
    assert 0.0 < kl["phi_ema"]["all"]["mean"] < kl["phi"]["all"]["mean"]        # the average moved by (1 - decay) of what the online weights moved
    off_dir = tmp_path / "off"
    off_dir.mkdir()
    off = _kl_runner(0.0, monkeypatch, off_dir)
    _learn(off, 1)
    assert set(json.loads((off_dir / "train_extra.jsonl").read_text(encoding="utf-8").splitlines()[-1])["kl_probe"]) == {"ppo", "phi"}


def test_the_checkpoint_carries_the_shadow_and_a_resume_continues_it(tmp_path, capsys, monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    _learn(r, 2)
    path = tmp_path / "model_2.pt"
    r.save(str(path))
    saved = torch.load(path, map_location="cpu", weights_only=False)
    assert saved["perception_ema"]["decay"] == DECAY and saved["perception_ema"]["updates"] == 2
    assert set(saved["perception_ema"]["shadow"]["perception"]) == {k for k, _ in r.perception.named_parameters()}
    assert "perception_state_dict" in saved                                         # the online weights are still what a resume loads
    new = _runner(seed=5, monkeypatch=monkeypatch)
    new.load(str(path), map_location="cpu")
    for k, v in new.perception.state_dict().items():
        assert torch.equal(v, saved["perception_state_dict"][k]), k               # the resume loaded the ONLINE weights
    capsys.readouterr()
    _prepare(new)
    assert "EX42_PERCEPTION_EMA where=start decay=0.98 status=continued (updates 2)" in capsys.readouterr().out
    for k, v in new.perception_wema.shadow["perception"].items():
        assert torch.equal(v, saved["perception_ema"]["shadow"]["perception"][k]), k
        assert torch.equal(_params(new.perception_ema)[k], v), k                   # and the copy the rollout uses is that shadow


def test_a_checkpoint_without_the_key_or_with_another_decay_starts_the_average_from_the_loaded_weights(tmp_path, capsys, monkeypatch):
    plain = _runner(decay=0.0, monkeypatch=monkeypatch)
    _learn(plain, 1)
    path = tmp_path / "model_1.pt"
    plain.save(str(path))
    assert "perception_ema" not in torch.load(path, map_location="cpu", weights_only=False)
    new = _runner(seed=5, monkeypatch=monkeypatch)
    new.load(str(path), map_location="cpu")
    capsys.readouterr()
    _prepare(new)
    assert "status=start_from_loaded_weights (checkpoint has no policy_ema)" in capsys.readouterr().out
    for k, v in new.perception_wema.shadow["perception"].items():
        assert torch.equal(v, _params(new.perception)[k]), k
    other = _runner(decay=0.9, monkeypatch=monkeypatch)
    _learn(other, 1)
    path2 = tmp_path / "model_2.pt"
    other.save(str(path2))
    again = _runner(seed=5, monkeypatch=monkeypatch)
    again.load(str(path2), map_location="cpu")
    capsys.readouterr()
    _prepare(again)
    assert "saved decay 0.9 != 0.98" in capsys.readouterr().out


def test_the_checkpoint_stays_loadable_by_a_runner_that_has_the_average_off(tmp_path, monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    _learn(r, 1)
    path = tmp_path / "model_1.pt"
    r.save(str(path))
    off = _runner(seed=5, decay=0.0, monkeypatch=monkeypatch)
    off.load(str(path), map_location="cpu")                                        # the extra key is ignored
    assert off.perception_wema is None


def test_the_evaluation_reads_the_average_when_it_is_there_and_says_so(tmp_path, capsys, monkeypatch):
    r = _runner(monkeypatch=monkeypatch)
    _learn(r, 2)
    path = tmp_path / "model_2.pt"
    r.save(str(path))
    saved = torch.load(path, map_location="cpu", weights_only=False)
    capsys.readouterr()
    runner, _ = load_s2_runner(FakeStartEnv(num_envs=2), train_cfg(24), str(path), "cpu")
    assert "EVAL_PERCEPTION_SOURCE=ema" in capsys.readouterr().out
    for k, v in saved["perception_ema"]["shadow"]["perception"].items():
        assert torch.equal(dict(runner.perception.named_parameters())[k].detach(), v), k
    online = saved["perception_state_dict"]
    assert any(not torch.equal(runner.perception.state_dict()[k], online[k]) for k in saved["perception_ema"]["shadow"]["perception"])   # it is not the online weights


def test_the_evaluation_falls_back_to_the_online_weights_and_names_the_reason(tmp_path, capsys, monkeypatch):
    plain = _runner(decay=0.0, monkeypatch=monkeypatch)
    _learn(plain, 1)
    path = tmp_path / "model_1.pt"
    plain.save(str(path))
    capsys.readouterr()
    load_s2_runner(FakeStartEnv(num_envs=2), train_cfg(24), str(path), "cpu")
    assert "EVAL_PERCEPTION_SOURCE=online\n" in capsys.readouterr().out
    r = _runner(monkeypatch=monkeypatch)
    _learn(r, 1)
    sd = torch.load(_save(r, tmp_path / "model_3.pt"), map_location="cpu", weights_only=False)
    key = next(iter(sd["perception_ema"]["shadow"]["perception"]))
    sd["perception_ema"]["shadow"]["perception"][key] = torch.zeros(1)             # a shape that does not fit
    capsys.readouterr()
    runner, _ = load_s2_runner(FakeStartEnv(num_envs=2), train_cfg(24), "unused", "cpu", checkpoint_state=sd)
    out = capsys.readouterr().out
    assert "EVAL_PERCEPTION_SOURCE=online (" in out and "does not match" in out
    for k, v in sd["perception_state_dict"].items():
        assert torch.equal(runner.perception.state_dict()[k], v), k                 # the online weights were loaded


def _save(r, path):
    r.save(str(path))
    return str(path)


def test_ema_state_dict_helper_edges():
    online = {"a": torch.ones(2), "b": torch.zeros(3), "buf": torch.tensor(5.0)}
    saved = {"decay": 0.98, "shadow": {"perception": {"a": torch.full((2,), 7.0)}}}
    state, why = pema.ema_state_dict(online, saved)
    assert why == "" and torch.equal(state["a"], torch.full((2,), 7.0)) and torch.equal(state["b"], online["b"]) and torch.equal(state["buf"], online["buf"])
    assert torch.equal(online["a"], torch.ones(2))                                  # the online dict is not changed
    assert pema.ema_state_dict(online, None)[0] is None and pema.ema_state_dict(online, {})[0] is None
    assert pema.ema_state_dict(online, {"shadow": {}})[0] is None
    assert pema.ema_state_dict(online, {"shadow": {"perception": {"zz": torch.ones(2)}}})[0] is None       # a parameter the model does not have
    assert pema.ema_state_dict(online, {"shadow": {"perception": {"a": torch.ones(3)}}})[0] is None        # another shape
    assert pema.ema_state_dict(online, {"shadow": {"perception": {"a": torch.full((2,), float("inf"))}}})[0] is None
    assert pema.decay_of(saved) == 0.98 and pema.decay_of(None) is None


def test_two_ranks_with_the_same_online_weights_hold_the_same_average(monkeypatch):
    """the perception gradients are summed over the ranks and both start from the same weights, so the online weights are equal after every update;
    the average is a deterministic function of them (here: two runners fed the same data stand for the two ranks)."""
    a, b = _runner(seed=4, monkeypatch=monkeypatch), _runner(seed=4, monkeypatch=monkeypatch)
    _learn(a, 2, seed=11)
    _learn(b, 2, seed=11)
    for k, v in a.perception_wema.save_state()["shadow"]["perception"].items():
        assert torch.equal(v, b.perception_wema.save_state()["shadow"]["perception"][k]), k
    assert a.perception_wema.updates == b.perception_wema.updates == 2


def test_not_a_fast_gt_only_run_and_a_bad_decay_is_refused(monkeypatch):
    r = _runner(decay=0.0, monkeypatch=monkeypatch)
    monkeypatch.setattr(start_runner, "PERCEPTION_EMA_DECAY", 1.5)
    r.pstate = r.perception.init_state(N, "cpu")
    with pytest.raises(ValueError, match="PERCEPTION_EMA_DECAY"):
        r._perception_ema_init()
    monkeypatch.setattr(start_runner, "PERCEPTION_EMA_DECAY", DECAY)
    r.pcfg["fast_gt_only"] = True
    with pytest.raises(ValueError, match="fast_gt_only"):
        r._perception_ema_init()


def test_the_phi_ema_before_snapshot_comes_from_the_averaged_weights(monkeypatch, tmp_path):
    r = _kl_runner(DECAY, monkeypatch, tmp_path)
    _learn(r, 1)
    with torch.no_grad():
        for p in r.perception_ema.parameters():
            p.add_(0.5 * torch.randn_like(p))                                      # the average now differs from the online weights
    snap = r._kl_phi_before(3)
    mu_e, _ = r._phi_dist(snap, r.perception_ema)
    assert torch.equal(snap["mu_ema"], mu_e)
    assert not torch.equal(snap["mu_ema"], snap["mu"])
