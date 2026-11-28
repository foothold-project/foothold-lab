"""Continuous r_x bins for the gaze-window tools (REQ210; design docs/stage1_logs/req206/design_next_v3.md sections 2 and 3).

280 bins of the normalized gaze x (r_x in [0, 1], 1 = front):
  [0, 0.9) in steps of 0.01 (bins 0-89), [0.9, 0.99) in steps of 0.001 (bins 90-179), [0.99, 1] in steps of 0.0001 (bins 180-279).
Every bin is [a, b) except the last one, [0.9999, 1]. The edges come from integer grids (k/100, k/1000, k/10000), so no edge is
the sum of rounded steps; most decimal edges are still not exact binary numbers. A stored gaze value (float32 from the model) is
promoted to float64 as it is and compared with the float64 edges: the promotion keeps its float32 rounding (float32 0.9 is
0.8999999761581421 and falls into [0.89, 0.9); float32 0.99 is 0.9900000095367432 and is above the 0.99 edge). Nothing is
rounded to make a value fit a bin. A value outside [0, 1] or not a number is an error.
Direct counts: r_x > 0.95, 0.99, 0.999, 0.9999 on the same promoted values (a value exactly on a threshold is in the bin that
starts there but not in the "above" count).
Quantiles from a histogram are only located to a bin: hist_quantile_bin() returns the bin index and its edges, never a point."""

import torch

NB = 280
THRESHOLDS = (0.95, 0.99, 0.999, 0.9999)


def edges() -> torch.Tensor:
    e = [k / 100 for k in range(0, 91)] + [k / 1000 for k in range(901, 991)] + [k / 10000 for k in range(9901, 10001)]
    t = torch.tensor(e, dtype=torch.float64)
    assert t.numel() == NB + 1 and bool((t[1:] > t[:-1]).all()) and float(t[0]) == 0.0 and float(t[-1]) == 1.0
    return t


EDGES = edges()


def rx_bin(r: torch.Tensor, e: torch.Tensor | None = None) -> torch.Tensor:
    """Bin index (0-279) of every value of r (any float dtype, promoted to float64 as stored). Raises on NaN / outside [0, 1]."""
    e = EDGES.to(r.device) if e is None else e
    x = r.to(torch.float64)
    bad = ~torch.isfinite(x) | (x < 0.0) | (x > 1.0)
    if bool(bad.any()):
        raise ValueError(f"r_x outside [0, 1] or not finite: {int(bad.sum())} values, e.g. {x[bad].flatten()[:3].tolist()}")
    # right=True: e[i-1] <= x < e[i] gives i, so the bin is i - 1; x == 1 gives NB + 1 and goes to the last bin [0.9999, 1]
    return (torch.bucketize(x, e, right=True) - 1).clamp_(max=NB - 1)


def above(r: torch.Tensor) -> torch.Tensor:
    """(..., 4) booleans: r_x > 0.95, 0.99, 0.999, 0.9999, compared in float64 on the promoted stored value."""
    x = r.to(torch.float64)
    return torch.stack([x > t for t in THRESHOLDS], dim=-1)


def first_bin_at_or_above(t: float) -> int:
    """Index of the bin whose lower edge equals t (t must be an edge)."""
    i = int(torch.nonzero(EDGES == t).flatten()[0]) if bool((EDGES == t).any()) else -1
    assert 0 <= i < NB, f"{t} is not a lower bin edge"
    return i


def hist_quantile_bin(h: torch.Tensor, q: float):
    """The bin that holds the q-quantile of a 280-bin histogram (smallest bin whose cumulative share reaches q).
    Returns (index, lower edge, upper edge), or None if the histogram is empty."""
    h = h.to(torch.float64).flatten()
    assert h.numel() == NB and bool((h >= 0).all()) and bool(torch.isfinite(h).all())
    n = float(h.sum())
    if n <= 0:
        return None
    c = torch.cumsum(h, 0) / n
    i = int(torch.searchsorted(c, torch.tensor(q, dtype=torch.float64)))
    i = min(i, NB - 1)
    return i, float(EDGES[i]), float(EDGES[i + 1])
