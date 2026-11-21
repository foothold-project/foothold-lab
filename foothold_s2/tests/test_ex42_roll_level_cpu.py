"""EX-42 roll level reward (ex42_roll_level · EX42_ROLL_LEVEL · lead 2026-11-22 00:40). CPU only."""
from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.rewards import ex42_roll_level as rl

ROOT = Path(__file__).resolve().parents[2]


class _Cfg:
    def __init__(self, func=None, weight=0.0, params=None):
        self.func, self.weight, self.params = func, weight, dict(params or {})


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv(rl.ENV_SWITCH, raising=False)
    monkeypatch.delenv(rl.WEIGHT_ENV, raising=False)


def _env(rolls):
    q = torch.stack([torch.tensor([math.cos(r / 2), math.sin(r / 2), 0.0, 0.0]) for r in rolls])
    return SimpleNamespace(scene={"robot": SimpleNamespace(data=SimpleNamespace(root_quat_w=q))})


def test_off_adds_nothing():
    cfg = SimpleNamespace(rewards=SimpleNamespace())
    assert rl.register(cfg, _Cfg) is False and vars(cfg.rewards) == {}


def test_weight_without_switch_is_a_mistake(monkeypatch):
    monkeypatch.setenv(rl.WEIGHT_ENV, "0.2")
    with pytest.raises(ValueError, match="is not 1"):
        rl.enabled()


def test_on_registers_the_paper_weight_and_rewards_level_roll(monkeypatch, capsys):
    monkeypatch.setenv(rl.ENV_SWITCH, "1")
    cfg = SimpleNamespace(rewards=SimpleNamespace())
    assert rl.register(cfg, _Cfg) and cfg.rewards.ex42_roll_level.weight == pytest.approx(0.2)
    assert "EX42_ROLL_LEVEL where=start weight=0.2 sigma=0.05" in capsys.readouterr().out
    v = rl.roll_level(_env([0.0, 0.05, -0.05, 0.3]))
    assert torch.allclose(v, torch.tensor([1.0, math.exp(-1), math.exp(-1), math.exp(-6)]), atol=1e-5)
    pitch = torch.tensor([[math.cos(0.1), 0.0, math.sin(0.1), 0.0]])        # pitch only: no roll cost (flat_orientation keeps pitch)
    assert float(rl.roll_level(SimpleNamespace(scene={"robot": SimpleNamespace(data=SimpleNamespace(root_quat_w=pitch))}))[0]) == pytest.approx(1.0, abs=1e-5)
    assert rl.register(cfg, _Cfg) is False                                   # not twice


@pytest.mark.parametrize("w", ["-0.1", "nan", "x"])
def test_bad_weights_refuse(monkeypatch, w):
    monkeypatch.setenv(rl.ENV_SWITCH, "1"); monkeypatch.setenv(rl.WEIGHT_ENV, w)
    with pytest.raises(ValueError):
        rl.weight()


def test_the_real_wiring_point_calls_the_module():
    seg = (ROOT / "foothold_s2/commands/ex42_segment_adjust.py").read_text(encoding="utf-8")
    i = seg.index("def apply_reward_params")
    assert "ex42_roll_level.register(env_cfg, term_cfg_class)" in seg[i:i + 1500]
