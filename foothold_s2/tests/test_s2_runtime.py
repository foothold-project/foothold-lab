"""S2 지형 재배정 · 깃발 공급 L0 (15 §5 · §8.1 ① · ⑤). Isaac 없이 가짜 terrain 객체로 돈다."""

import numpy as np
import pytest
import torch

from foothold_s2.terrains import s2_layout, s2_runtime
from foothold_s2.terrains import sparse_terrains as st

ROWS = 10


def make_world():
    layout = s2_layout.Layout()
    table = st.SideTable()
    rng = np.random.default_rng(0)

    # Isaac 커리큘럼 순서(열 우선, 줄 순서)로 생성기 함수가 불리는 것을 흉내
    for col, name in enumerate(layout.names):
        for row in range(ROWS):
            if name in st.KINDS:
                d = (row + rng.uniform()) / ROWS
                table.record(name, d, st.build_tile(name, d))

    table.bind_all(layout.names, ROWS)
    tables = s2_runtime.S2Tables(table, layout, ROWS, "cpu")
    return layout, table, tables


def fake_terrain(layout, n, level, col_kind):
    cols = [i for i, g in enumerate(layout.group_by_col) if g == col_kind]
    types = torch.as_tensor(np.random.default_rng(1).choice(cols, n), dtype=torch.long)
    origins = torch.zeros(ROWS, layout.num_cols, 3)

    for r in range(ROWS):
        for c in range(layout.num_cols):
            origins[r, c] = torch.tensor([r * 8.0 + 0.5, c * 8.0 + 4.0, 0.0])

    terrain = type("T", (), {})()
    terrain.terrain_types = types
    terrain.terrain_levels = torch.full((n,), level, dtype=torch.long)
    terrain.terrain_origins = origins
    terrain.env_origins = origins[terrain.terrain_levels, terrain.terrain_types].clone()
    return terrain


def test_layout_counts_and_groups():
    layout = s2_layout.Layout()
    assert len(layout.easy_cols) == 7 + 2 and len(layout.hard_cols) == 5 + 5 + 5
    assert set(layout.group_by_col) == {"continuous", "sparse", "gap"}
    assert (layout.group_by_col == "gap").sum() == 3


def test_side_table_binds_every_sparse_cell_in_isaac_call_order():
    layout, table, _ = make_world()
    sparse_cols = [c for c, n in enumerate(layout.names) if n in st.KINDS]
    assert len(table.by_cell) == len(sparse_cols) * ROWS
    assert all(table.by_cell[(r, c)]["kind"] == layout.names[c] for r in range(ROWS) for c in sparse_cols)
    assert all(table.by_cell[(r, c)]["level"] == r for r in range(ROWS) for c in sparse_cols)


def test_bind_all_raises_when_call_order_assumption_breaks():
    layout = s2_layout.Layout()
    table = st.SideTable()

    for name in layout.names:
        if name in st.KINDS:
            for row in range(ROWS):
                d = (ROWS - 1 - row + 0.5) / ROWS           # 줄 순서가 거꾸로면 걸려야 한다
                table.record(name, d, st.build_tile(name, d))

    with pytest.raises(RuntimeError):
        table.bind_all(layout.names, ROWS)


@pytest.mark.parametrize("T,want", [(1000, 0.0), (8000, 0.9), (4500, 0.45)])
def test_sparse_envs_move_to_hard_columns_with_p_advance(T, want):
    layout, _, tables = make_world()
    n = 4000
    terrain = fake_terrain(layout, n, level=3, col_kind="sparse")
    rng = np.random.default_rng(5)
    s2_runtime.reassign(terrain, tables, torch.arange(n), T, rng)
    hard = np.isin(terrain.terrain_types.numpy(), layout.hard_cols).mean()
    assert abs(hard - want) < 0.03
    # 어려운 열에 있던 env 도 다시 뽑힌다: 두 번째 재배정에서 쉬운 열로 돌아오는 비율 ~ 1 - p
    s2_runtime.reassign(terrain, tables, torch.arange(n), T, rng)
    hard2 = np.isin(terrain.terrain_types.numpy(), layout.hard_cols).mean()
    assert abs(hard2 - want) < 0.03


def test_gap_and_continuous_envs_never_move_and_origin_follows_type():
    layout, _, tables = make_world()

    for kind in ("gap", "continuous"):
        terrain = fake_terrain(layout, 500, level=2, col_kind=kind)
        before = terrain.terrain_types.clone()
        s2_runtime.reassign(terrain, tables, torch.arange(500), 8000, np.random.default_rng(1))
        assert torch.equal(before, terrain.terrain_types)

    terrain = fake_terrain(layout, 300, level=4, col_kind="sparse")
    s2_runtime.reassign(terrain, tables, torch.arange(300), 8000, np.random.default_rng(2))
    expect = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    assert torch.equal(terrain.env_origins, expect)


def test_flags_follow_new_cell_and_lie_on_that_cells_world_frame():
    layout, table, tables = make_world()
    terrain = fake_terrain(layout, 50, level=5, col_kind="sparse")
    s2_runtime.reassign(terrain, tables, torch.arange(50), 8000, np.random.default_rng(3))
    flags = tables.flag_provider(terrain, torch.arange(50), 4)
    assert flags.shape == (50, 4, 2) and not torch.isnan(flags).any()

    for i in range(50):
        r, c = int(terrain.terrain_levels[i]), int(terrain.terrain_types[i])
        assert torch.allclose(flags[i], torch.as_tensor(table.by_cell[(r, c)]["flags_world"], dtype=torch.float32))
        # 깃발은 그 칸 안 (월드): x in [8r, 8r+8], y in [8c, 8c+8]
        assert (flags[i, :, 0] > 8 * r).all() and (flags[i, :, 0] < 8 * r + 8).all()
        assert (flags[i, :, 1] > 8 * c).all() and (flags[i, :, 1] < 8 * c + 8).all()


def test_continuous_cells_fall_back_to_the_straight_flag_line():
    layout, _, tables = make_world()
    terrain = fake_terrain(layout, 10, level=1, col_kind="continuous")
    flags = tables.flag_provider(terrain, torch.arange(10), 4)
    assert not torch.isnan(flags).any()
    assert torch.allclose(flags[:, 0, 0] - terrain.env_origins[:10, 0], 0.5 * torch.ones(10))
    assert float((flags[:, :, 0] - terrain.env_origins[:10, :1]).abs().max()) <= 3.5 + 1e-6   # 칸 경계(4 m) 안쪽


def test_force_flag_marks_sparse_and_gap_cells_but_not_continuous():
    layout, _, tables = make_world()

    for kind, want in (("sparse", True), ("gap", True), ("continuous", False)):
        terrain = fake_terrain(layout, 20, level=2, col_kind=kind)
        got = tables.force_flag(terrain, torch.arange(20))
        assert bool(got.all()) == want and bool(got.any()) == want
