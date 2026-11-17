"""복원 지도 손실의 모서리 · 구멍 칸 가중 (설계 DESIGN-MAP-EDGE-1117 7 절 1). 기본 가중 1.0 = 꺼짐.
칸 정의는 축 도구 (foothold_s2/eval/ex42_axes.py · HOLE_DEFINITION v2) 와 같다: 모서리 = 위아래 · 좌우 네 이웃 중 하나와 높이 차가 5 cm 이상,
구멍 = 같은 줄 또는 같은 열에서 양쪽 모두 10 칸 안에 10 cm 이상 높은 칸이 있음. 이쪽은 torch (학습 손실용 · 정답 지도 한 장 (B, R, C) 단위), 축 도구는 numpy (평가용).
두 구현이 같은 칸을 고르는지는 tests/test_map_weights_cpu.py 가 실제 메시 타일로 대조한다."""
from __future__ import annotations

import torch

EDGE_STEP_M = 0.05
HOLE_DROP_M = 0.10
HOLE_REACH_CELLS = 10


def edge_mask_t(m: torch.Tensor, step: float = EDGE_STEP_M) -> torch.Tensor:
    a = m.double()
    big = torch.zeros_like(a, dtype=torch.bool)
    for axis in (-2, -1):
        n = a.shape[axis]
        if n < 2:
            continue
        head = a.narrow(axis, 0, n - 1)
        tail = a.narrow(axis, 1, n - 1)
        jump = (tail - head).abs() >= step                    # 비유한이면 False
        # head 쪽 칸 [0, n-1) 과 tail 쪽 칸 [1, n) 에 각각 반영
        ph = torch.zeros_like(big)
        pt = torch.zeros_like(big)
        ph.narrow(axis, 0, n - 1).copy_(jump)
        pt.narrow(axis, 1, n - 1).copy_(jump)
        big |= ph | pt
    return big


def hole_mask_t(m: torch.Tensor, drop: float = HOLE_DROP_M, reach: int = HOLE_REACH_CELLS) -> torch.Tensor:
    a = m.double()
    finite = torch.isfinite(a)
    a = torch.where(finite, a, torch.full_like(a, float("-inf")))
    out = torch.zeros_like(a, dtype=torch.bool)
    for axis in (-2, -1):
        size = a.shape[axis]
        lo = torch.full_like(a, float("-inf"))
        hi = torch.full_like(a, float("-inf"))
        for d in range(1, reach + 1):
            if d >= size:
                break
            lo.narrow(axis, d, size - d).copy_(torch.maximum(lo.narrow(axis, d, size - d), a.narrow(axis, 0, size - d)))
            hi.narrow(axis, 0, size - d).copy_(torch.maximum(hi.narrow(axis, 0, size - d), a.narrow(axis, d, size - d)))
        out |= ((lo - a) >= drop) & ((hi - a) >= drop)
    return out & finite


def weight_map(gt: torch.Tensor, w_edge: float = 1.0, w_hole: float = 1.0) -> torch.Tensor | None:
    """정답 지도 gt (..., R, C) -> 같은 모양 float 가중. 둘 다 1.0 이면 None (손실이 옛 식을 그대로 부른다). 모서리이면서 구멍이면 둘 중 큰 값."""
    if w_edge == 1.0 and w_hole == 1.0:
        return None
    w = torch.ones_like(gt, dtype=torch.float32)
    if w_edge != 1.0:
        w = torch.where(edge_mask_t(gt), torch.full_like(w, float(w_edge)), w)
    if w_hole != 1.0:
        w = torch.where(hole_mask_t(gt), torch.maximum(w, torch.full_like(w, float(w_hole))), w)
    return w
