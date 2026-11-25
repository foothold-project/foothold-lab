"""Gk4 (lead 2026-11-26 02:07 / 02:08): low-speed action noise split into rows with a command and zero-command rows."""
import pytest
import torch

from foothold_s2.runners import ex41_critic_mirror as mirror


def _cmd():
    # stand, slow forward, spin in place, fast forward
    return torch.tensor([[0.0, 0.0, 0.0], [0.2, 0.0, 0.0], [0.0, 0.0, 0.5], [0.6, 0.0, 0.0]])


def test_unset_keeps_the_single_scale_rule(monkeypatch):
    monkeypatch.delenv(mirror.LOWSPEED_SIGMA_ENV, raising=False)
    monkeypatch.delenv(mirror.STAND_SIGMA_ENV, raising=False)
    static = torch.tensor([[1.0], [1.0], [1.0], [0.2]])
    scale, low, stand = mirror.lowspeed_scale(_cmd(), 0.3, static)
    old = torch.where(mirror.lowspeed_noise_mask(_cmd()[:, :2], 0.3)[:, None], torch.full_like(static, 0.2), static)
    assert torch.equal(scale, old)
    assert low.tolist() == [True, True, True, False] and stand.tolist() == [True, False, False, False]


def test_move_rows_take_low_sigma_and_stand_rows_keep_static(monkeypatch):
    monkeypatch.setenv(mirror.LOWSPEED_SIGMA_ENV, "0.6")
    monkeypatch.delenv(mirror.STAND_SIGMA_ENV, raising=False)
    static = torch.ones(4, 12)
    scale, _, _ = mirror.lowspeed_scale(_cmd(), 0.3, static)
    assert scale[:, 0].tolist() == pytest.approx([0.2, 0.6, 0.6, 1.0])
    monkeypatch.setenv(mirror.STAND_SIGMA_ENV, "0.3")
    assert mirror.lowspeed_scale(_cmd(), 0.3, static)[0][:, 0].tolist() == pytest.approx([0.3, 0.6, 0.6, 1.0])


@pytest.mark.parametrize("bad", ["0", "1", "x", "nan"])
def test_stand_sigma_rejects_out_of_range(monkeypatch, bad):
    monkeypatch.setenv(mirror.STAND_SIGMA_ENV, bad)
    with pytest.raises(ValueError):
        mirror.stand_sigma_scale()
