"""GVD 위 등급 비용 A* (PLAN-HIPAN-V2 §5.3 · M5 · 22-NAV-ENV §3 · §6.4). numpy · scipy 만.

통과 불가 (BLOCKED) 셀을 장애물로 두고 거리 변환 (`distance_transform_edt`, 가장 가까운 장애물 번호 함께) 을 구한다.
이웃 셀의 가장 가까운 장애물이 서로 다른 셀이 GVD. 노드 = GVD 셀 + 듬성한 통과 가능 · 머리 위 통과 셀 + 그 둘레 `ramp_m` 안의 통과 가능 셀
(띠가 좁아 GVD 가 띠에 닿지 않을 수 있어서 · 계획 §5.3 가정). 8 방향, 비용 = 이동 거리 x 두 셀 비용 평균. 시작 · 목표는 가장 가까운 노드에 붙인다.
자세 스위치 (낮은 통로) 는 등급 지도가 이미 반영한다 (grade_map.make_grade_map(pose_active)).
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from foothold_s2.nav import grade_map as gm

RAMP_M = 1.5
_NB = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


@dataclass
class Path:
    found: bool
    points: np.ndarray      # (K, 2) m, 시작 · 목표 포함. 못 찾으면 (0, 2)
    length_m: float
    cost: float


def gvd_mask(grade: np.ndarray, sep_cells: int = 3) -> np.ndarray:
    """이웃한 두 통과 가능 셀의 가장 가까운 장애물 셀이 sep_cells 칸 넘게 떨어져 있으면 둘 다 GVD (같은 덩어리 벽의 서로 다른 면도 가름)."""
    free = grade != gm.BLOCKED
    if free.all():
        return np.zeros_like(free)
    _, idx = ndimage.distance_transform_edt(free, return_indices=True)
    ix, iy = idx
    gvd = np.zeros_like(free)
    h, w = free.shape
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        x0, x1 = 0, h - dx
        y0, y1 = (0, w - dy) if dy >= 0 else (-dy, w)
        sl_a = (slice(x0, x1), slice(y0, y1))
        sl_b = (slice(x0 + dx, x1 + dx), slice(y0 + dy, y1 + dy))
        far = np.maximum(np.abs(ix[sl_a] - ix[sl_b]), np.abs(iy[sl_a] - iy[sl_b])) > sep_cells
        diff = far & free[sl_a] & free[sl_b]
        gvd[sl_a] |= diff
        gvd[sl_b] |= diff
    return gvd & free


def node_mask(g: gm.GradeMap, ramp_m: float = RAMP_M, region: np.ndarray | None = None) -> np.ndarray:
    special = np.isin(g.grade, (gm.SPARSE, gm.OVERHEAD))
    nodes = gvd_mask(g.grade) | special
    if special.any():
        d = ndimage.distance_transform_edt(~special) * g.res
        nodes |= (d <= ramp_m) & (g.grade != gm.BLOCKED)
    nodes &= g.grade != gm.BLOCKED
    if region is not None:
        nodes &= region
    lab, n = ndimage.label(nodes, structure=np.ones((3, 3)))     # 가장 큰 덩어리만 (GVD 조각이 고립돼 시작 · 목표가 거기 붙는 일을 막음)
    return lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1) if n else nodes


def _cell(g, xy):
    c = (np.asarray(xy, float) / g.res).astype(int)
    if not (0 <= c[0] < g.grade.shape[0] and 0 <= c[1] < g.grade.shape[1]):
        raise ValueError("point outside the room")
    return int(c[0]), int(c[1])


def find_path(g: gm.GradeMap, start_xy, goal_xy, ramp_m: float = RAMP_M) -> Path:
    s, t = _cell(g, start_xy), _cell(g, goal_xy)
    if g.grade[s] == gm.BLOCKED or g.grade[t] == gm.BLOCKED:
        raise ValueError("start and goal must be on passable cells")
    reg, _ = ndimage.label(g.grade != gm.BLOCKED, structure=np.ones((3, 3)))   # 통과 가능 덩어리
    if reg[s] != reg[t]:
        return Path(False, np.zeros((0, 2)), 0.0, np.inf)                      # 서로 다른 덩어리 = 경로 없음
    nodes = node_mask(g, ramp_m, reg == reg[s])
    if not nodes.any():
        return Path(False, np.zeros((0, 2)), 0.0, np.inf)
    _, idx = ndimage.distance_transform_edt(~nodes, return_indices=True)
    s2, t2 = (int(idx[0][s]), int(idx[1][s])), (int(idx[0][t]), int(idx[1][t]))
    cost = g.cost
    h, w = cost.shape
    dist = {s2: 0.0}
    prev = {}
    pq = [(0.0, s2)]
    best = np.inf
    while pq:
        f, u = heapq.heappop(pq)
        if u == t2:
            best = dist[u]
            break
        du = dist[u]
        if f > du + np.hypot(u[0] - t2[0], u[1] - t2[1]) * g.res + 1e-9:
            continue                                    # 낡은 큐 항목
        for dx, dy in _NB:
            v = (u[0] + dx, u[1] + dy)
            if not (0 <= v[0] < h and 0 <= v[1] < w) or not nodes[v]:
                continue
            step = np.hypot(dx, dy) * g.res * 0.5 * (cost[u] + cost[v])
            nd = du + step
            if nd < dist.get(v, np.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd + np.hypot(v[0] - t2[0], v[1] - t2[1]) * g.res, v))
    if not np.isfinite(best):
        return Path(False, np.zeros((0, 2)), 0.0, np.inf)
    cells = [t2]
    while cells[-1] != s2:
        cells.append(prev[cells[-1]])
    pts = (np.array(cells[::-1], float) + 0.5) * g.res
    pts = np.vstack([np.asarray(start_xy, float), pts, np.asarray(goal_xy, float)])
    length = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    stub_s = float(np.linalg.norm(pts[1] - pts[0])) * float(cost[s])          # 시작 -> 첫 노드 · 마지막 노드 -> 목표 직선도 비용에 넣음
    stub_t = float(np.linalg.norm(pts[-1] - pts[-2])) * float(cost[t])
    return Path(True, pts, length, float(best) + stub_s + stub_t)
