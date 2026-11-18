"""EX-42 합친 메시의 발 가장자리 마스크 (CPU · Isaac 없음). 실제 합친 메시 npz 를 쓴다 (없으면 건너뜀)."""
import json
import os
import types
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.terrains import ex42_edge_masks as em

REAL = Path(os.environ.get("EX42_EDGE_TEST_MESH", "/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2/terrain_mesh.npz"))
needs_mesh = pytest.mark.skipif(not REAL.is_file(), reason="real combined mesh npz not on this machine")


@pytest.fixture(scope="module")
def real():
    d = np.load(REAL, allow_pickle=False)
    arrays = {k: d[k] for k in d.files}
    built = em.build_edge_masks(arrays["vertices"], arrays["faces"], arrays["origins"], [str(v) for v in arrays["column_family"]])
    return arrays, built


def _tables(built, total=76):
    packed = em.pack_masks(built)
    loaded = {"inner": built["inner"], "outer": built["outer"], "columns": built["columns"], "meta": json.loads(str(packed["edge_meta"]))}
    return em.EdgeTables(loaded, total, "cpu")


def _world(tbl, r, col, ci, cj):
    rows, fam = tbl.inner.shape[0], int(round(tbl.shift[1].item() * 2 / tbl.tile[1]))
    return (-tbl.tile[0] * rows / 2 + tbl.tile[0] * r + (ci + 0.5) * tbl.res, -tbl.tile[1] * fam / 2 + tbl.tile[1] * col + (cj + 0.5) * tbl.res)


@needs_mesh
def test_stone_edge_cell_reads_nonzero_and_stone_top_reads_zero(real):
    import torch
    _, built = real
    tbl = _tables(built)
    r, k = 3, 0
    col = int(built["columns"][k])
    inner, outer = built["inner"][r, k], built["outer"][r, k]
    ci, cj = [int(v) for v in np.argwhere(inner)[len(np.argwhere(inner)) // 2]]
    flat = np.argwhere(~inner & ~outer)
    far = [int(v) for v in flat[len(flat) // 3]]
    on_edge, on_top = _world(tbl, r, col, ci, cj), _world(tbl, r, col, *far)
    feet = torch.tensor([[on_edge, on_top]], dtype=torch.float32)
    contact = torch.ones(1, 2, dtype=torch.bool)
    both = tbl.penalty(feet, contact, torch.tensor([r]), torch.tensor([col]))
    assert float(both[0]) == pytest.approx(em_omega(0))                 # only the edge foot counts (inner weight 1.0)
    swing = tbl.penalty(feet, torch.zeros(1, 2, dtype=torch.bool), torch.tensor([r]), torch.tensor([col]))
    assert float(swing[0]) == 0.0                                       # a foot in the air pays nothing


def em_omega(i):
    from foothold_s2.rewards import core
    return core.EDGE_OMEGA[i]


@needs_mesh
def test_continuous_columns_and_flat_column_read_zero(real):
    import torch
    arrays, built = real
    tbl = _tables(built)
    # stairs (col 2) and boxes (col 11) have real height steps but are not edge kinds: no masks, the term is 0
    for col in (2, 11, 48):
        assert int(tbl.col_to_k[col]) == -1
        r = 4
        xs = torch.tensor([[[-40.0 + 8 * r + 1.0 + 0.3 * i, -200.0 + 8 * col + 4.0] for i in range(6)]], dtype=torch.float32)
        v = tbl.penalty(xs, torch.ones(1, 6, dtype=torch.bool), torch.tensor([r]), torch.tensor([col]))
        assert float(v[0]) == 0.0


@needs_mesh
def test_mask_cells_sit_on_real_height_drops_of_the_mesh(real):
    """Geometry check independent of the rasteriser: ray-cast the mesh on both sides of sampled inner cells; a drop of 0.2 m or more must be within 5 cm."""
    from foothold_s2.terrains.ex42_mesh_mount import MeshHeights
    arrays, built = real
    tbl = _tables(built)
    heights = MeshHeights(arrays["vertices"], arrays["faces"])
    rng = np.random.default_rng(0)
    r, k = 5, 2
    col = int(built["columns"][k])
    cells = np.argwhere(built["inner"][r, k])
    pick = cells[rng.choice(len(cells), 12, replace=False)]
    ok = 0
    for ci, cj in pick:
        x, y = _world(tbl, r, col, int(ci), int(cj))
        pts = np.array([[x + dx, y + dy] for dx in (-0.05, 0.0, 0.05) for dy in (-0.05, 0.0, 0.05)])
        z = heights.at(pts, radius=0.5)
        ok += int(np.nanmax(z) - np.nanmin(z) >= 0.2 - 1e-6)
    assert ok == len(pick)


@needs_mesh
def test_self_check_passes_and_catches_a_shifted_table(real):
    import torch
    _, built = real
    tbl = _tables(built)
    assert tbl.self_check()["value_on_inner"] > 0
    tbl.shift = tbl.shift + 5.0                                          # a wrong world-to-tile shift reads 0 on the checked cell: raise, do not train silently
    with pytest.raises(RuntimeError):
        tbl.self_check()


def test_pack_roundtrip_and_old_mesh_has_no_masks(tmp_path):
    inner = np.zeros((2, 1, 320, 320), bool); inner[1, 0, 10:12, 5:9] = True
    outer = np.zeros_like(inner); outer[1, 0, 12, 5:9] = True
    meta = {"tile": [8.0, 8.0], "resolution_m": 0.025, "rows": 2, "family_columns": 50}
    built = {"inner": inner, "outer": outer, "columns": np.array([23]), "meta": meta}
    np.savez(tmp_path / "m.npz", vertices=np.zeros((3, 3)), **em.pack_masks(built))
    got = em.load_edge_masks(tmp_path / "m.npz")
    assert np.array_equal(got["inner"], inner) and np.array_equal(got["outer"], outer) and got["columns"].tolist() == [23]
    np.savez(tmp_path / "old.npz", vertices=np.zeros((3, 3)))
    assert em.load_edge_masks(tmp_path / "old.npz") is None
    np.savez(tmp_path / "half.npz", edge_columns=np.array([1]))
    with pytest.raises(ValueError):
        em.load_edge_masks(tmp_path / "half.npz")


def test_rasterize_top_two_boxes_and_edge_masks():
    # one 1x1 m box at z 0.3 on a z 0 floor: a vertical step of 0.3 m on its four sides
    v = np.array([[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0], [0.5, 0.5, 0.3], [1.5, 0.5, 0.3], [1.5, 1.5, 0.3], [0.5, 1.5, 0.3]], float)
    f = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
    g = em.rasterize_top(v, f, 0.0, 0.0, 80, 80, 0.025)
    assert g[40, 40] == pytest.approx(0.3) and g[5, 5] == pytest.approx(0.0) and (g > em.FLOOR).all()
    from foothold_s2.terrains import sparse_terrains as st
    inner, outer = st.edge_masks(g)
    assert inner[19, 40] and inner[20, 40] and outer[18, 40] and not inner[40, 40] and not inner[5, 5]


def test_foot_edge_weight_needs_masks_and_a_fenced_value():
    from foothold_s2.scripts.ex42_training_entry import _foot_edge_weight
    assert _foot_edge_weight({}, None) == 0.0 and _foot_edge_weight({"foot_edge_weight": 0}, None) == 0.0
    with pytest.raises(ValueError):
        _foot_edge_weight({"foot_edge_weight": -1.0}, None)             # a weight on a mesh without masks: the term would read 0
    edge = {"columns": [1]}
    assert _foot_edge_weight({"foot_edge_weight": -1.0}, edge) == -1.0
    for bad in (0.5, -2.0, float("nan"), "x", True):
        with pytest.raises(ValueError):
            _foot_edge_weight({"foot_edge_weight": bad}, edge)


def test_attach_refuses_a_live_weight_without_tables_or_a_different_weight():
    from foothold_s2.scripts.ex42_training_entry import attach_edge_tables
    def raw(weight):
        def get_term_cfg(name):
            if weight == 0:
                raise ValueError("no such term")                          # Isaac Lab skips weight-0 terms
            return types.SimpleNamespace(weight=weight)
        return types.SimpleNamespace(device="cpu", reward_manager=types.SimpleNamespace(get_term_cfg=get_term_cfg))
    assert attach_edge_tables(raw(0), {"column_table": [0] * 76}) is None
    with pytest.raises(RuntimeError):
        attach_edge_tables(raw(-1.0), {"column_table": [0] * 76, "foot_edge_weight": -1.0})      # weight on, no tables
    with pytest.raises(RuntimeError):
        attach_edge_tables(raw(-0.5), {"column_table": [0] * 76})                                  # live weight differs from the contract (0)
