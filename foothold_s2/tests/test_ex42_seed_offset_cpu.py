"""EX42_SEED_OFFSET (lead 2026-11-22 08:35 ledger 30d8e881d): 0 / unset = no reseed (the same first command as before); 1 = a different first
command sample and different global draws. The real MixedVelocityCommand (e1f_term harness) and the real train_start / start_runner lines. CPU only."""
from __future__ import annotations

from pathlib import Path

import pytest
import torch

from foothold_s2.runners import ex42_seed_offset as so
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

N = 256


def _first_cmd(monkeypatch, offset):
    command, _, _ = e1f_term(monkeypatch, {}, n=N)
    command.gen.manual_seed(1234)                       # the restored state (same for every arm)
    torch.manual_seed(99)
    if offset:
        so.reseed(42 + offset, command)
    command.time_left[:] = 4.0
    command._resample_command(torch.arange(N))
    return command.vel_command_b.clone(), torch.rand(4)


def test_offset_zero_keeps_the_first_command_and_one_changes_it(monkeypatch):
    a0, r0 = _first_cmd(monkeypatch, 0)
    b0, s0 = _first_cmd(monkeypatch, 0)
    a1, r1 = _first_cmd(monkeypatch, 1)
    a2, _ = _first_cmd(monkeypatch, 2)
    assert torch.equal(a0, b0) and torch.equal(r0, s0)                 # offset 0: bit for bit
    assert not torch.equal(a0, a1) and not torch.equal(r0, r1)          # offset 1: other command samples and other global draws
    assert not torch.equal(a1, a2)


def test_parse(monkeypatch):
    monkeypatch.delenv(so.ENV, raising=False)
    assert so.offset() == 0
    monkeypatch.setenv(so.ENV, "1"); assert so.offset() == 1
    for bad in ("-1", "x", "1.5", "2000"):
        monkeypatch.setenv(so.ENV, bad)
        with pytest.raises(ValueError):
            so.offset()


def test_the_real_entry_and_runner_use_it():
    root = Path(so.__file__).resolve().parents[1]
    ts = (root / "scripts" / "train_start.py").read_text()
    assert ts.count("+ ex42_seed_offset.offset()") == 2               # both stage-start seed lines
    sr = (root / "runners" / "start_runner.py").read_text()
    assert "if ex42_seed_offset.offset():" in sr and "ex42_seed_offset.reseed(env_seed, self._command_term())" in sr
