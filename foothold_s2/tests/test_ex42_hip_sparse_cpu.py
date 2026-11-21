"""EX-42 hip L1 lower on sparse-column envs only (ex42_hip_sparse · EX42_HIP_SPARSE · lead 2026-11-21 21:35). CPU only."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.rewards import ex42_hip_sparse as hs

ROOT = Path(__file__).resolve().parents[2]
TABLE = [{"family": "A", "kind": "boxes"}, {"family": "A", "kind": "flat"}, {"family": "A", "kind": "balance_beams"},
         {"family": "B", "kind": "beam"}, {"family": "A", "kind": "gaps"}]


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv(hs.ENV_SWITCH, raising=False)
    monkeypatch.delenv(hs.WEIGHT_ENV, raising=False)


def _term(env, **params):
    return torch.full((env.num_envs,), 2.0)


def _env(types, weight=-0.05):
    cfg = SimpleNamespace(weight=weight)
    return SimpleNamespace(num_envs=len(types), device="cpu", _ex42_column_table=TABLE,
                           scene=SimpleNamespace(terrain=SimpleNamespace(terrain_types=torch.tensor(types))),
                           reward_manager=SimpleNamespace(get_term_cfg=lambda name: cfg))


def _cfg(weight=-0.05):
    return SimpleNamespace(rewards=SimpleNamespace(basic_hip_pos_penalty_l1=SimpleNamespace(func=_term, weight=weight, params={})))


def test_off_changes_nothing():
    cfg = _cfg()
    assert hs.register(cfg) is False and cfg.rewards.basic_hip_pos_penalty_l1.func is _term


def test_weight_without_switch_is_a_mistake(monkeypatch):
    monkeypatch.setenv(hs.WEIGHT_ENV, "0")
    with pytest.raises(ValueError, match="is not 1"):
        hs.enabled()


@pytest.mark.parametrize("w,expect_sparse", [("0", 0.0), ("-0.01", 2.0 * 0.2)])
def test_sparse_envs_get_the_lower_weight_and_continuous_keep_the_term(monkeypatch, capsys, w, expect_sparse):
    monkeypatch.setenv(hs.ENV_SWITCH, "1"); monkeypatch.setenv(hs.WEIGHT_ENV, w)
    cfg = _cfg()
    assert hs.register(cfg)
    assert "EX42_HIP_SPARSE where=start" in capsys.readouterr().out
    env = _env([0, 1, 2, 3, 4])
    v = cfg.rewards.basic_hip_pos_penalty_l1.func(env)
    # A/boxes and A/flat keep the value (weight -0.05); A/balance_beams, B/beam, A/gaps are sparse: value x w / -0.05
    assert torch.allclose(v, torch.tensor([2.0, 2.0, expect_sparse, expect_sparse, expect_sparse]))
    assert hs.register(cfg) is False                                   # not wrapped twice


def test_a_stage_table_weight_change_keeps_the_sparse_weight_exact(monkeypatch):
    monkeypatch.setenv(hs.ENV_SWITCH, "1"); monkeypatch.setenv(hs.WEIGHT_ENV, "-0.01")
    cfg = _cfg()
    hs.register(cfg)
    v = cfg.rewards.basic_hip_pos_penalty_l1.func(_env([3], weight=-0.1))
    assert float(v[0]) * -0.1 == pytest.approx(2.0 * -0.01)            # effective sparse weight stays -0.01


@pytest.mark.parametrize("w", ["0.01", "-0.2", "x"])
def test_bad_weights_refuse(monkeypatch, w):
    monkeypatch.setenv(hs.ENV_SWITCH, "1"); monkeypatch.setenv(hs.WEIGHT_ENV, w)
    with pytest.raises(ValueError):
        hs.register(_cfg())


def test_missing_term_or_table_refuses(monkeypatch):
    monkeypatch.setenv(hs.ENV_SWITCH, "1")
    with pytest.raises(ValueError, match="no basic_hip_pos_penalty_l1"):
        hs.register(SimpleNamespace(rewards=SimpleNamespace()))
    cfg = _cfg(); hs.register(cfg)
    env = _env([0]); del env._ex42_column_table
    with pytest.raises(ValueError, match="column table"):
        cfg.rewards.basic_hip_pos_penalty_l1.func(env)


def test_the_real_wiring_point_calls_the_module():
    seg = (ROOT / "foothold_s2/commands/ex42_segment_adjust.py").read_text(encoding="utf-8")
    i = seg.index("def apply_reward_params")
    assert "ex42_hip_sparse.register(env_cfg)" in seg[i:i + 1500]


def test_isaac_lab_term_check_sees_the_original_signature(monkeypatch):
    """ManagerBase._resolve_common_term_cfg (manager_base.py:363) checks inspect.signature(func) against the params: the wrapper must show the
    hip term's own parameters (inspect follows __wrapped__)."""
    import inspect
    from foothold_s2.rewards.basic_gait_bundle import hip_pos_penalty_l1
    monkeypatch.setenv(hs.ENV_SWITCH, "1")
    cfg = SimpleNamespace(rewards=SimpleNamespace(basic_hip_pos_penalty_l1=SimpleNamespace(func=hip_pos_penalty_l1, weight=-0.05, params={})))
    hs.register(cfg)
    assert list(inspect.signature(cfg.rewards.basic_hip_pos_penalty_l1.func).parameters) == list(inspect.signature(hip_pos_penalty_l1).parameters)
