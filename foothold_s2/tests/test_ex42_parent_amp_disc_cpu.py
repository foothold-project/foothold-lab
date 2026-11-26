"""lead 11/26 12:11: EX42_PARENT_AMP_DISC=1 makes the new-stage parent load restore the parent checkpoint's amp_disc (discriminator
weights with its normalisation mean/std, Adam state, update count, per-condition policy centres) instead of a fresh discriminator.
Unset = the fresh discriminator as before (bit for bit). A parent of another input size (side=1: 61 wide vs 60) is refused.
The parent checkpoint goes through the real load_ex42_stage_zero_parent (the parent-policy-EMA test's loader)."""

from __future__ import annotations

import types

import numpy as np
import pytest
import torch

from foothold_s2.rewards import ex42_amp_style as st
from foothold_s2.rewards import ex42_hip_sparse
from foothold_s2.tests.test_ex42_amp_cpu import _fake_env, _fake_ref, _fake_ref_side_turn
from foothold_s2.tests.test_ex42_parent_policy_ema_cpu import _load, _trained

PARAMS = "batch=16,buffer=64,disc_every=2,disc_steps=1,ramp_steps=1200,band_max_level=1,flatlike_only=1,ref_probe=32"


def _amp_env(monkeypatch, tmp_path, params=PARAMS, side_ref=False):
    (_fake_ref_side_turn if side_ref else _fake_ref)(tmp_path / "ref.npz", np.random.default_rng(0))
    monkeypatch.setenv(st.ENV_SWITCH, "1"); monkeypatch.setenv(st.WEIGHT_ENV, "0.5"); monkeypatch.setenv(st.REF_ENV, str(tmp_path / "ref.npz"))
    monkeypatch.setenv(st.PARAMS_ENV, params)
    monkeypatch.setattr(ex42_hip_sparse, "sparse_envs", lambda env: torch.tensor([False, False, False, True, False, False, False, False]))


def _parent_amp(monkeypatch, tmp_path):
    """A trained discriminator state (the same calls as the AMP term test), as the parent checkpoint saves it."""
    _amp_env(monkeypatch, tmp_path)
    st._STATE.clear()
    env, _ = _fake_env()
    p = st.params()
    torch.manual_seed(5)
    with torch.inference_mode():
        for _ in range(13):
            st.ex42_amp_style(env, "base_velocity", types.SimpleNamespace(name="robot"), p)
    ck = st.checkpoint_entry()["amp_disc"]
    assert ck["updates"] > 0 and bool(ck["pol_center_init"].all())
    st._STATE.clear()
    return ck


def _build(tmp_path, seed=11):
    torch.manual_seed(seed)
    with torch.inference_mode(False):
        st.build("cpu", st.params(), dict(np.load(tmp_path / "ref.npz")))
    return st._STATE


def test_on_restores_the_parent_discriminator_and_unset_keeps_the_fresh_one(tmp_path, monkeypatch, capsys):
    parent = _trained(tmp_path)                                          # the policy parent first, without the AMP switches
    amp = _parent_amp(monkeypatch, tmp_path)
    checkpoint = {**parent, "amp_disc": amp}

    monkeypatch.delenv(st.PARENT_DISC_ENV, raising=False)               # unset: the old path, a fresh discriminator
    st._STATE.clear()
    _load(checkpoint, capsys)
    assert "pending" not in st._STATE
    fresh = {k: v.clone() for k, v in _build(tmp_path).items() if k in ("pol_center", "pol_center_init")}
    fresh_disc = {k: v.clone() for k, v in st._STATE["disc"].state_dict().items()}
    assert st._STATE["updates"] == 0 and not st._STATE["opt"].state_dict()["state"]
    assert "EX42_AMP_DISC_SOURCE=fresh dims=60" in capsys.readouterr().out
    st._STATE.clear()
    old = _build(tmp_path)                                               # the same seed without any parent load: bit for bit
    for k, v in old["disc"].state_dict().items():
        assert torch.equal(v, fresh_disc[k]), k
    assert torch.equal(old["pol_center"], fresh["pol_center"]) and not bool(old["pol_center_init"].any())
    assert torch.equal(fresh_disc["mean"], amp["disc"]["mean"])          # the same reference and params give the same normalisation,
    amp["disc"]["mean"] = amp["disc"]["mean"] + 0.01                     # so mark the parent's to see that it is the one restored
    amp["disc"]["std"] = amp["disc"]["std"] * 1.01
    assert not any(torch.equal(fresh_disc[k], amp["disc"][k]) for k in ("net.0.weight", "mean", "std"))

    monkeypatch.setenv(st.PARENT_DISC_ENV, "1")
    monkeypatch.setenv(st.PARAMS_ENV, PARAMS.replace("ramp_steps=1200", "ramp_steps=1200,lr=2e-4"))
    st._STATE.clear()
    _load(checkpoint, capsys)
    assert st._STATE["pending"]["source"] == "parent"
    s = _build(tmp_path)
    for k, v in s["disc"].state_dict().items():
        assert torch.equal(v, amp["disc"][k]), k                         # weights and the normalisation mean / std
    assert torch.equal(s["pol_center"], amp["pol_center"]) and torch.equal(s["pol_center_init"], amp["pol_center_init"])
    assert s["updates"] == amp["updates"]
    got, want = s["opt"].state_dict(), amp["opt"]
    assert got["state"].keys() == want["state"].keys()
    for i in want["state"]:
        for k in ("exp_avg", "exp_avg_sq", "step"):
            assert torch.equal(torch.as_tensor(got["state"][i][k]), torch.as_tensor(want["state"][i][k])), (i, k)
    assert [g["lr"] for g in s["opt"].param_groups] == [2e-4]              # this run's lr, not the parent's
    assert s["buf"].n == 0                                               # the policy sample buffer is not carried
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith("EX42_AMP_DISC_SOURCE="))
    assert line == "EX42_AMP_DISC_SOURCE=parent net0_sha=%s updates=%d dims=60 pol_center_init=2/2 lr=0.0002" % (
        st.hashlib.sha256(amp["disc"]["net.0.weight"].contiguous().numpy().tobytes()).hexdigest()[:12], amp["updates"])
    st._STATE.clear()


def test_on_refuses_another_input_size_a_missing_entry_another_value_and_amp_off(tmp_path, monkeypatch, capsys):
    amp = _parent_amp(monkeypatch, tmp_path)                             # parent: walk / still, 60 wide
    monkeypatch.setenv(st.PARENT_DISC_ENV, "1")
    side = tmp_path / "side"; side.mkdir()
    _amp_env(monkeypatch, side, PARAMS + ",side=1", side_ref=True)       # this run: + side condition, 61 wide
    st._STATE.clear()
    st.load_parent_entry(amp)
    with pytest.raises(ValueError, match="does not fit this run"):
        _build(side)
    st._STATE.clear()
    with pytest.raises(ValueError, match="has no amp_disc"):
        st.load_parent_entry(None)
    monkeypatch.setenv(st.PARENT_DISC_ENV, "2")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        st.load_parent_entry(amp)
    monkeypatch.setenv(st.PARENT_DISC_ENV, "1")
    for k in (st.ENV_SWITCH, st.WEIGHT_ENV, st.REF_ENV, st.PARAMS_ENV):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValueError, match="while EX42_AMP is off"):
        st.load_parent_entry(amp)
    st._STATE.clear()
