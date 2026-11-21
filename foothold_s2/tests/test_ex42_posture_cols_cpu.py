"""EX-42 rx2ps2 posture input columns (ex42_posture_cols · lead 2026-11-22 07:41 ledger 8ee347dad · planner 07:41). The real StartActorCritic
(actor 98 · critic 666 inputs, pose_command_dim 2) and a real torch Adam with the PPO learning rate. CPU only.
  - off (both switches unset): attach() gives None (no hook, nothing changes)
  - init: the two columns get 1/4 of the median norm of the other columns; with posture input 0 the actor output is the same as before
  - LR x20: after one optimizer step the posture columns moved 20 x what plain Adam moved them, every other column exactly as plain Adam
  - the start line and the 50-update check line (column norms, action change for height -0.2 / roll 0.5)."""
from __future__ import annotations

import copy
import json

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import CRITIC_IN, OBS_GROUPS, StartActorCritic
from foothold_s2.models.start_perception import ACTOR_IN
from foothold_s2.runners import ex42_posture_cols as pc


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in (pc.LR_SWITCH, pc.INIT_SWITCH):
        monkeypatch.delenv(k, raising=False)


def _policy(seed=0):
    torch.manual_seed(seed)
    obs = TensorDict({"actor_in": torch.zeros(4, ACTOR_IN + 2), "critic_in": torch.zeros(4, CRITIC_IN + 2)}, batch_size=[4])
    pol = StartActorCritic(obs, OBS_GROUPS, 12, pose_command_dim=2)
    with torch.no_grad():                                         # the parent: posture columns start at 0
        pol.actor[0].weight[:, list(pc.ACTOR_COLS)] = 0.0
        pol.critic[0].weight[:, list(pc.CRITIC_COLS)] = 0.0
    return pol


class _Alg:
    def __init__(self, pol):
        self.optimizer = torch.optim.Adam(pol.parameters(), lr=1e-3)


def test_off_attaches_nothing():
    pol = _policy()
    assert pc.attach(_Alg(pol), pol) is None


def test_init_sets_quarter_median_norm_and_keeps_actions_without_posture_input(monkeypatch, capsys):
    monkeypatch.setenv(pc.INIT_SWITCH, "1")
    pol = _policy()
    x = torch.randn(64, ACTOR_IN + 2); x[:, list(pc.ACTOR_COLS)] = 0.0
    before = pol.actor(x).detach().clone()
    cols = pc.attach(_Alg(pol), pol)
    cols.maybe_init(True, 42)
    w = pol.actor[0].weight
    med = pc.other_median(w, pc.ACTOR_COLS)
    for c in pc.ACTOR_COLS:
        assert float(w[:, c].norm()) == pytest.approx(0.25 * med, rel=1e-5)
    for c in pc.CRITIC_COLS:
        assert float(pol.critic[0].weight[:, c].norm()) == pytest.approx(0.25 * pc.other_median(pol.critic[0].weight, pc.CRITIC_COLS), rel=1e-5)
    assert torch.equal(pol.actor(x), before)                     # posture input 0 -> the same action
    line = json.loads([l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_POSTURE_COLS where=start")][0].split(" ", 2)[2])
    assert line["init_done"] and line["init"]["actor"]["before"] == [0.0, 0.0] and line["lr_mult"] is None
    other = _policy(); o2 = pc.attach(_Alg(other), other); o2.maybe_init(True, 42)
    assert torch.equal(other.actor[0].weight, w)                 # same seed -> both ranks draw the same columns
    third = _policy(); o3 = pc.attach(_Alg(third), third); o3.maybe_init(False, 42)
    assert float(third.actor[0].weight[:, list(pc.ACTOR_COLS)].abs().sum()) == 0.0   # a resume (not fresh from the parent) is left alone


def test_lr_mask_scales_only_the_two_columns(monkeypatch):
    monkeypatch.setenv(pc.LR_SWITCH, "20")
    a, b = _policy(1), _policy(1)
    with torch.no_grad():                                         # non-zero posture columns so their gradient is not trivially zero
        for p in (a, b):
            p.actor[0].weight[:, list(pc.ACTOR_COLS)] = 0.01
    alg_a, alg_b = _Alg(a), _Alg(b)
    cols = pc.attach(alg_a, a)                                    # a: masked · b: plain Adam
    x = torch.randn(32, ACTOR_IN + 2)
    w0 = a.actor[0].weight.detach().clone()
    for p, alg in ((a, alg_a), (b, alg_b)):
        alg.optimizer.zero_grad(); p.actor(x).pow(2).mean().backward(); alg.optimizer.step()
    da, db = a.actor[0].weight.detach() - w0, b.actor[0].weight.detach() - w0
    keep = [c for c in range(w0.shape[1]) if c not in pc.ACTOR_COLS]
    assert torch.equal(da[:, keep], db[:, keep])                 # every other column: plain Adam exactly
    assert torch.allclose(da[:, list(pc.ACTOR_COLS)], 20 * db[:, list(pc.ACTOR_COLS)], rtol=1e-4, atol=1e-9)
    assert float(db[:, list(pc.ACTOR_COLS)].abs().sum()) > 0
    for la, lb in list(zip(a.actor, b.actor))[1:]:
        for pa, pb in zip(la.parameters(), lb.parameters()):
            assert torch.equal(pa, pb)                           # other layers: plain Adam exactly
    cols.lr.remove()


def test_check_line_reports_norms_and_action_change(monkeypatch, capsys):
    monkeypatch.setenv(pc.INIT_SWITCH, "1"); monkeypatch.setenv(pc.LR_SWITCH, "20")
    pol = _policy()
    cols = pc.attach(_Alg(pol), pol)
    cols.maybe_init(True, 42)
    pol.actor(torch.randn(16, ACTOR_IN + 2))                     # a rollout batch passes the actor
    cols.after_update(48); assert "EX42_POSTURE_COLS_CHECK" not in capsys.readouterr().out
    cols.after_update(49)
    line = json.loads([l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_POSTURE_COLS_CHECK")][0].split(" ", 1)[1])
    assert line["it"] == 50 and line["mean_abs_action_change"] > 0 and len(line["actor_norms"]) == 2


@pytest.mark.parametrize("bad", ["0.5", "abc", "500"])
def test_bad_lr_values_refuse(monkeypatch, bad):
    monkeypatch.setenv(pc.LR_SWITCH, bad)
    with pytest.raises(ValueError):
        pc.settings()


def test_the_real_runner_calls_it():
    from pathlib import Path
    from foothold_s2.runners import start_runner
    src = Path(start_runner.__file__).read_text()
    assert "ex42_posture_cols.attach(alg, policy)" in src and "self._ex42_posture_cols.maybe_init(" in src and "self._ex42_posture_cols.after_update(it)" in src
