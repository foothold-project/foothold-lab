"""3.0 은 env.reset() 때 curriculum · event · command · action 에 env_ids=slice(None) 을 그대로 넘긴다 (v3.0.0 manager_based_env.py reset 기본값).
2.3.2 에서는 전체 인덱스 텐서였다. 우리 쪽 env_ids 받는 함수가 slice 와 텐서 둘 다 같은 결과를 내는지 본다."""
from __future__ import annotations

import numpy as np
import pytest
import torch

from foothold_s2.lab_compat import env_ids_long
from foothold_s2.nav import rewards_hl
from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.tests.test_ex42_column_reset_cpu import ZERO, _env, _gate_env


class _Proxy:
    def __init__(self, t):
        self.torch = t


@pytest.mark.parametrize("ids", [None, slice(None), slice(1, 4), torch.tensor([0, 2], dtype=torch.int32), [3, 1], np.array([0, 4]), _Proxy(torch.tensor([1, 2]))])
def test_env_ids_long_accepts_every_form_the_managers_may_send(ids):
    out = env_ids_long(ids, 5, "cpu")
    assert out.dtype == torch.long and out.ndim == 1
    want = {"None": [0, 1, 2, 3, 4]}.get(str(ids), None)
    if ids is None or (isinstance(ids, slice) and ids == slice(None)):
        assert out.tolist() == [0, 1, 2, 3, 4]
    elif isinstance(ids, slice):
        assert out.tolist() == [1, 2, 3]


def test_visit_grid_reset_with_slice_and_array():
    g = rewards_hl.VisitGrid(4)
    g.counts[:] = 1
    g.reset(slice(None))
    assert g.counts.sum() == 0
    g.counts[:] = 1
    g.reset(torch.tensor([1, 2]).numpy())
    assert g.counts[1].sum() == 0 and g.counts[0].sum() > 0
    g.counts[:] = 1
    g.reset(None)
    assert g.counts.sum() == 0


def test_column_reset_gives_the_same_pose_for_slice_and_full_index():
    table = [{"ranges": {**cr.DEFAULT_RANGES, **ZERO}}, {"ranges": dict(cr.DEFAULT_RANGES)}]
    lo, hi = cr.table_tensors(table)
    cols = [0] * 5 + [1] * 5
    env_a, asset_a = _env(cols)
    env_b, asset_b = _env(cols)
    cr.reset_root_state_by_column(env_a, slice(None), lo, hi, {})
    cr.reset_root_state_by_column(env_b, torch.arange(10), lo, hi, {})
    assert asset_a.pose.shape == asset_b.pose.shape == (10, 7)
    assert torch.equal(asset_a.pose[:5], asset_b.pose[:5])                 # 0 범위 칸은 두 길이 같다


def test_push_gate_slice_equals_none_equals_full_index():
    seen = []
    inner = lambda env, rows, tag: seen.append(rows.tolist())
    push_off = torch.tensor([False, True, True, False])
    env = _gate_env([0, 1, 2, 3, 1, 0])
    cr.push_gated_by_column(env, slice(None), inner, push_off, tag="t")
    cr.push_gated_by_column(env, None, inner, push_off, tag="t")
    cr.push_gated_by_column(env, torch.arange(6), inner, push_off, tag="t")
    assert seen[0] == seen[1] == seen[2] == [0, 3, 5]
