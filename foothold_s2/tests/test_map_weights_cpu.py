"""복원 지도 설계 7 절 8 (시험): 기본값이면 옛 것과 비트 같음 · 가중 마스크가 정답 지도의 모서리 칸 수와 맞음 (축 도구 numpy 판과 같은 칸) · TRNet 폭 기본값 불변."""
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn.functional as F

from foothold_s2.eval import ex42_axes as ax
from foothold_s2.models import map_weights as mw
from foothold_s2.models import start_perception as sp

TILES = Path(__file__).resolve().parent / "data" / "ex42_axes_real_tiles.npz"


def _tiles():
    d = np.load(TILES)
    return [np.asarray(d[k], dtype=np.float64) for k in d.files if np.asarray(d[k]).ndim == 2]


def test_torch_masks_pick_the_same_cells_as_the_numpy_axes_tool_on_real_tiles():
    tiles = _tiles()
    assert tiles
    total_h = total_e = 0
    for t in tiles:
        g = torch.as_tensor(t)
        assert (mw.hole_mask_t(g).numpy() == ax.hole_mask(t)).all()
        assert (mw.edge_mask_t(g).numpy() == ax.edge_mask(t)).all()
        total_h += int(ax.hole_mask(t).sum()); total_e += int(ax.edge_mask(t).sum())
    assert total_h > 0 and total_e > 0            # 시험이 빈 마스크끼리 맞는 것이 아니다


def test_weight_map_counts_match_the_masks_and_off_returns_none():
    t = _tiles()[0]
    g = torch.as_tensor(t)[None].float()
    assert mw.weight_map(g, 1.0, 1.0) is None
    w = mw.weight_map(g, 4.0, 1.0)
    assert int((w == 4.0).sum()) == int(ax.edge_mask(g[0].numpy().astype(np.float64)).sum()) and int((w == 1.0).sum()) + int((w == 4.0).sum()) == w.numel()
    both = mw.weight_map(g, 3.0, 5.0)
    assert float(both.max()) == 5.0 and set(both.unique().tolist()) <= {1.0, 3.0, 5.0}


def test_loss_tr_default_is_the_old_formula_bit_for_bit_and_unit_weights_match():
    g = torch.Generator().manual_seed(0)
    rough, refined, hb = (torch.randn(6, sp.MAP_X, sp.MAP_Y, generator=g) for _ in range(3))
    old = F.mse_loss(rough, hb) + F.l1_loss(refined, hb)
    assert torch.equal(sp.loss_tr(rough, refined, hb), old)
    assert torch.allclose(sp.loss_tr(rough, refined, hb, torch.ones_like(hb)), old, atol=1e-6)
    w = torch.full_like(hb, 4.0)
    assert float(sp.loss_tr(rough, refined, hb, w)) == pytest.approx(4.0 * float(old), rel=1e-5)     # 평균 축은 가중으로 나누지 않음


def test_trnet_default_width_keeps_shapes_and_seeded_init_and_wide_width_changes_only_gru_and_rough():
    torch.manual_seed(7); a = sp.TRNet()
    torch.manual_seed(7); b = sp.TRNet(width=128)
    assert all(torch.equal(x, y) for x, y in zip(a.state_dict().values(), b.state_dict().values()))
    assert a.gru.hidden_size == 128 and a.rough[0].in_features == 128 and a.rough[0].out_features == 128 and a.rough[2].out_features == 256
    w = sp.TRNet(width=512)
    assert w.gru.hidden_size == 512 and w.rough[0].in_features == 512 and w.rough[2].out_features == 1024
    diff = {k for k in a.state_dict() if a.state_dict()[k].shape != w.state_dict()[k].shape}
    assert diff and all(k.startswith(("gru.", "rough.")) for k in diff)                       # CNN · U-Net · prop_mlp 은 같은 모양 (이어받기 가능)
    h = torch.zeros(2, 512)
    r, f = w.decode(w.step(torch.zeros(2, 2, 60, 60), torch.zeros(2, 128), h))
    assert r.shape == f.shape == (2, sp.MAP_X, sp.MAP_Y)
