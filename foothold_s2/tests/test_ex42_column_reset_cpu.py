"""Per-column reset ranges: table building, zero ranges are exactly zero, default kept elsewhere."""
from __future__ import annotations

import math
import types

import pytest
import torch

from foothold_s2.terrains import ex42_column_reset as cr

FAMILIES = ["C"] * 7 + ["E"] * 4
ZERO = {"x": (0.0, 0.0), "y": (0.0, 0.0), "yaw": (0.0, 0.0)}


def _table():
    return cr.build_column_table(FAMILIES, {"C": {"gap": ZERO}})


def test_default_is_the_ex41_range_when_nothing_is_declared():
    rows = cr.build_column_table(FAMILIES, {})
    assert all(r["ranges"] == cr.DEFAULT_RANGES and not r["from_declaration"] for r in rows)
    assert cr.DEFAULT_RANGES == {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)}


def test_declared_kind_overrides_only_its_own_column(monkeypatch):
    monkeypatch.setattr(cr, "family_column_kinds", lambda f, n: ["gap", "flat", "box"] + [None] * (n - 3) if f == "C" else [None] * n)
    rows = cr.build_column_table(FAMILIES, {"C": {"gap": ZERO, "box": {"yaw": (0.0, 0.0)}}})
    assert rows[0]["ranges"] == {**cr.DEFAULT_RANGES, **ZERO} and rows[0]["from_declaration"]
    assert rows[1]["ranges"] == cr.DEFAULT_RANGES
    assert rows[2]["ranges"]["yaw"] == (0.0, 0.0) and rows[2]["ranges"]["x"] == (-0.5, 0.5)
    assert all(r["ranges"] == cr.DEFAULT_RANGES for r in rows[3:])


def test_bad_declarations_and_noncontiguous_columns_are_rejected():
    with pytest.raises(ValueError):
        cr._clean({"x": (1.0, 0.0)})
    with pytest.raises(ValueError):
        cr._clean({"q": (0.0, 0.0)})
    with pytest.raises(ValueError):
        cr._clean({"x": (0.0, float("nan"))})
    with pytest.raises(ValueError):
        cr.build_column_table(["C", "E", "C"], {})


class FakeAsset:
    device = "cpu"

    def __init__(self, n):
        root = torch.zeros(n, 13)
        root[:, 2] = 0.4
        root[:, 3] = 1.0
        self.data = types.SimpleNamespace(default_root_state=root)
        self.pose = self.vel = None

    def write_root_pose_to_sim(self, pose, env_ids):
        self.pose = pose

    def write_root_velocity_to_sim(self, vel, env_ids):
        self.vel = vel


def _env(columns):
    n = len(columns)
    asset = FakeAsset(n)
    class Scene:
        terrain = types.SimpleNamespace(terrain_types=torch.tensor(columns))
        env_origins = torch.tensor([[10.0 * i, 0.0, 0.0] for i in range(n)])

        def __getitem__(self, key):
            return asset

    scene = Scene()
    return types.SimpleNamespace(scene=scene), asset


def test_zero_columns_start_exactly_on_the_origin_and_others_jitter():
    table = [{"ranges": {**cr.DEFAULT_RANGES, **ZERO}}, {"ranges": dict(cr.DEFAULT_RANGES)}]
    lo, hi = cr.table_tensors(table)
    columns = [0] * 50 + [1] * 50
    env, asset = _env(columns)
    cr.reset_root_state_by_column(env, torch.arange(100), lo, hi, {})
    pos, quat = asset.pose[:, :3], asset.pose[:, 3:]
    base = env.scene.env_origins + torch.tensor([0.0, 0.0, 0.4])
    assert torch.equal(pos[:50], base[:50])                              # no xy jitter at all
    assert torch.allclose(quat[:50], torch.tensor([1.0, 0, 0, 0]).expand(50, 4))   # no yaw
    off = (pos[50:] - base[50:])
    assert off[:, :2].abs().max() <= 0.5 and off[:, :2].abs().max() > 0.1
    yaw = 2 * torch.atan2(quat[50:, 3], quat[50:, 0])
    assert yaw.abs().max() > 0.5 and torch.allclose(quat.norm(dim=1), torch.ones(100), atol=1e-5)
    assert torch.equal(pos[:, 2], base[:, 2])                            # z is never jittered


def test_yaw_quaternion_matches_the_closed_form():
    q = cr._quat_from_euler_wxyz(torch.zeros(1), torch.zeros(1), torch.tensor([1.0]))
    assert torch.allclose(q, torch.tensor([[math.cos(0.5), 0.0, 0.0, math.sin(0.5)]]), atol=1e-6)


# ---- push gate ----
def _kinds_table():
    return [{"family": "A", "kind": "random_rough"}, {"family": "A", "kind": "stones"},
            {"family": "C", "kind": "gap"}, {"family": "C", "kind": "flat"}, {"family": "E", "kind": None}]


def test_push_gate_mask_follows_the_table_and_rejects_unknown_kinds():
    mask = cr.push_gate_mask(_kinds_table(), {"A": ["stones"], "C": {"gap"}})
    assert mask == [False, True, True, False, False]
    assert cr.push_gate_mask(_kinds_table(), {}) == [False] * 5            # no table -> push stays everywhere
    with pytest.raises(ValueError):
        cr.push_gate_mask(_kinds_table(), {"C": ["gapp"]})                 # typo must not silently keep the push
    report = cr.push_gate_report(_kinds_table(), mask)
    assert report["push_off_kinds"] == ["A/stones", "C/gap"] and report["columns_with_unknown_kind_push_kept"] == [4]


def _gate_env(columns):
    class Scene:
        terrain = types.SimpleNamespace(terrain_types=torch.tensor(columns))
        num_envs = len(columns)
    return types.SimpleNamespace(scene=Scene())


def test_gate_calls_the_push_only_for_envs_on_allowed_columns():
    seen = []
    inner = lambda env, rows, tag: seen.append((rows.tolist(), tag))
    push_off = torch.tensor([False, True, True, False])
    env = _gate_env([0, 1, 2, 3, 1, 0])
    cr.push_gated_by_column(env, None, inner, push_off, tag="t")
    assert seen == [([0, 3, 5], "t")]
    seen.clear()
    cr.push_gated_by_column(env, torch.tensor([1, 2, 4]), inner, push_off, tag="t")      # all push-off
    assert seen == []


def test_apply_gate_wraps_the_term_keeps_params_and_fails_without_a_term():
    func = lambda env, rows, asset_cfg, target_range: None
    cfg = types.SimpleNamespace(events=types.SimpleNamespace(
        ex40_push=types.SimpleNamespace(func=func, params={"asset_cfg": "robot", "target_range": {"x": (0, 1)}})))
    assert cr.apply_column_push_gate(cfg, [False, True]) == ["ex40_push"]
    term = cfg.events.ex40_push
    assert term.func is cr.push_gated_by_column and term.params["inner"] is func
    assert term.params["target_range"] == {"x": (0, 1)} and term.params["push_off"].tolist() == [False, True]
    with pytest.raises(ValueError):
        cr.apply_column_push_gate(types.SimpleNamespace(events=types.SimpleNamespace()), [False])
