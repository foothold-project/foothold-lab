"""The run's vx correction is written into every checkpoint and the evaluation applies it (lead 2026-11-22 10:36). CPU only.

apply_checkpoint_vx_corr: a checkpoint entry sets the environment (correct_est_vx then uses it); an environment naming other values is refused;
a checkpoint without the entry needs the values named in the environment, else refused (no hidden default)."""
from __future__ import annotations

import pytest
import torch

from foothold_s2.runners import start_runner as sr

KEYS = (sr.VX_CORR_ENV, sr.VX_CORR_ENV_B)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def test_record_reads_the_environment(monkeypatch):
    monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.009")
    assert sr.vx_corr_record() == {"on": True, "b": 0.009, "band": sr.VX_CORR_BAND, "ramp": sr.VX_CORR_RAMP}


def test_checkpoint_entry_sets_the_correction():
    rec = sr.apply_checkpoint_vx_corr({"on": True, "b": 0.009, "band": 0.3, "ramp": 0.05})
    assert rec["b"] == 0.009 and sr.vx_corr_params() == (True, 0.009, 0.3)
    est = torch.zeros(3, 51); est[:, 16] = torch.tensor([0.1, 0.2, 0.5])
    out = sr.correct_est_vx(est)
    want = 0.1 - 0.009 * 1.0 * (1 - 0.1 / 0.3)
    assert abs(float(out[0, 16]) - want) < 1e-7 and float(out[2, 16]) == 0.5           # outside the band unchanged


def test_environment_with_other_values_is_refused(monkeypatch):
    monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.010")
    with pytest.raises(ValueError):
        sr.apply_checkpoint_vx_corr({"on": True, "b": 0.009, "band": 0.3, "ramp": 0.05})
    monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.009"); monkeypatch.setenv(sr.VX_CORR_ENV, "0")
    with pytest.raises(ValueError):
        sr.apply_checkpoint_vx_corr({"on": True, "b": 0.009, "band": 0.3, "ramp": 0.05})


def test_same_environment_is_accepted(monkeypatch):
    monkeypatch.setenv(sr.VX_CORR_ENV, "1"); monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.009")
    assert sr.apply_checkpoint_vx_corr({"on": True, "b": 0.009, "band": 0.3, "ramp": 0.05})["b"] == 0.009


def test_old_checkpoint_needs_explicit_values(monkeypatch):
    with pytest.raises(ValueError):
        sr.apply_checkpoint_vx_corr(None)
    monkeypatch.setenv(sr.VX_CORR_ENV, "1")
    with pytest.raises(ValueError):                                                        # b still missing
        sr.apply_checkpoint_vx_corr(None)
    monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.009")
    assert sr.apply_checkpoint_vx_corr(None)["b"] == 0.009


@pytest.mark.parametrize("bad", [{"on": True, "b": 0.009}, {"on": True, "b": 0.009, "band": 0.25, "ramp": 0.05},
                                 {"on": True, "b": 0.009, "band": 0.3, "ramp": 0.1}])
def test_malformed_or_foreign_entry_is_refused(bad):
    with pytest.raises(ValueError):
        sr.apply_checkpoint_vx_corr(bad)


def test_state_dict_carries_the_entry():
    src = open(sr.__file__, encoding="utf-8").read()
    i = src.index("    def state_dict(self")
    assert '"vx_corr": vx_corr_record(),' in src[i:i + 4000]


def test_resume_needs_the_same_correction(monkeypatch):
    saved = {"on": True, "b": 0.009, "band": 0.3, "ramp": 0.05}
    with pytest.raises(ValueError):                                           # B forgotten: the process would apply 0.010
        sr.check_resume_vx_corr(saved, "load")
    monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.009")
    assert sr.check_resume_vx_corr(saved, "load")["b"] == 0.009


def test_resume_of_an_old_checkpoint_needs_explicit_values(monkeypatch):
    with pytest.raises(ValueError):
        sr.check_resume_vx_corr(None, "load_ex42_stage_zero_parent")
    monkeypatch.setenv(sr.VX_CORR_ENV, "1"); monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.009")
    assert sr.check_resume_vx_corr(None, "load_ex42_stage_zero_parent")["b"] == 0.009


def test_both_loaders_call_the_check():
    src = open(sr.__file__, encoding="utf-8").read()
    assert 'check_resume_vx_corr(sd.get("vx_corr"), "load")' in src
    assert 'check_resume_vx_corr(checkpoint.get("vx_corr"), "load_ex42_stage_zero_parent")' in src
