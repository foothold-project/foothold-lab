"""GVD 위 등급 비용 A* (PLAN-HIPAN-V2 §5.3 · M5 · 22-NAV-ENV §3 · §6.4). numpy · scipy 만.

통과 불가 (BLOCKED) 셀을 장애물로 두고 거리 변환 (`distance_transform_edt`, 가장 가까운 장애물 번호 함께) 을 구한다.
이웃 셀의 가장 가까운 장애물이 서로 다른 셀이 GVD. 노드 = GVD 셀 + 듬성한 통과 가능 · 머리 위 통과 셀 + 그 둘레 `ramp_m` 안의 통과 가능 셀
(띠가 좁아 GVD 가 띠에 닿지 않을 수 있어서 · 계획 §5.3 가정). 8 방향, 비용 = 이동 거리 x 두 셀 비용 평균. 시작 · 목표는 가장 가까운 노드에 붙인다.
건너뛰기 간선 (리뷰 #730): 같은 지형 패치 (징검돌 · 평균대 · 디딤 보) 안에서 듬성한 (SPARSE) 두 셀 사이가 막힌 (BLOCKED) 칸뿐이고 틈이 `g.stride_m`
(하위가 한 걸음에 건너는 틈 · 등급표 max_stride_m) 이하면 두 셀을 잇는다. 돌 사이를 SPARSE 로 칠해 잇지 않는다 (실제 디딤 위치를 잃는다).
자세 스위치 (낮은 통로) 는 등급 지도가 이미 반영한다 (grade_map.make_grade_map(pose_active)).
"""
from __future__ import annotations

import heapq
import math
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


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def jump_edges(g: gm.GradeMap, stride_m: float | None = None) -> np.ndarray:
    """(K, 5) int: 한 패치 안의 두 셀 (적어도 하나는 듬성한 SPARSE, 다른 쪽은 평지 · 듬성한 셀) (ax, ay, bx, by) 과 센터 거리 (셀 수 x 1000). 사이 셀은 전부 막힘이고 틈 = 센터 거리 - 한 칸 <= stride."""
    stride = g.stride_m if stride_m is None else stride_m
    none = np.zeros((0, 5), np.int64)
    if stride <= 0 or g.patch is None:
        return none
    sparse = g.grade == gm.SPARSE
    blocked = g.grade == gm.BLOCKED
    walk = np.isin(g.grade, (gm.FREE, gm.CONNECTED_ROUGH, gm.SPARSE))      # 패치 가장자리 평지에서 첫 돌로 들어가고 마지막 돌에서 나오는 간선도
    comp, _ = ndimage.label(g.grade != gm.BLOCKED, structure=np.ones((3, 3)))   # 이어진 셀로 갈 수 있는 쪽은 간선이 필요 없다 (평균대 옆 평지에서 비스듬히 뛰어드는 길을 막는다)
    h, w = g.grade.shape
    reach = int(np.ceil(stride / g.res)) + 1
    out = []
    for dx in range(0, reach + 1):
        for dy in range(-reach, reach + 1):
            if dx == 0 and dy <= 0:
                continue
            n = max(abs(dx), abs(dy))
            if n < 2:
                continue                                          # 이웃 칸은 보통 간선이 이미 있다
            dist = np.hypot(dx, dy) * g.res
            if dist - g.res > stride + 1e-9:
                continue
            xa0, xa1, ya0, ya1 = max(0, -dx), h - max(0, dx), max(0, -dy), w - max(0, dy)
            if xa1 <= xa0 or ya1 <= ya0:
                continue
            region = (slice(xa0, xa1), slice(ya0, ya1))
            b_sl = (slice(xa0 + dx, xa1 + dx), slice(ya0 + dy, ya1 + dy))
            ok = (sparse[region] & walk[b_sl]) | (walk[region] & sparse[b_sl])
            ok &= g.patch[region] == g.patch[b_sl]
            ok &= g.patch[region] >= 0
            ok &= comp[region] != comp[b_sl]
            for m in range(1, n):
                sx, sy = int(round(m * dx / n)), int(round(m * dy / n))
                ok &= blocked[xa0 + sx:xa1 + sx, ya0 + sy:ya1 + sy]   # 사이가 전부 막힌 칸일 때만 (그 밖은 보통 간선이 이미 있다)
            ax, ay = np.nonzero(ok)
            if len(ax):
                out.append(np.stack([ax + xa0, ay + ya0, ax + xa0 + dx, ay + ya0 + dy,
                                     np.full(len(ax), int(round(dist / g.res * 1000)))], axis=1))
    return np.concatenate(out).astype(np.int64) if out else none


def node_mask(g: gm.GradeMap, ramp_m: float = RAMP_M, region: np.ndarray | None = None,
              jumps: np.ndarray | None = None) -> np.ndarray:
    special = np.isin(g.grade, (gm.SPARSE, gm.OVERHEAD))
    nodes = gvd_mask(g.grade) | special
    if special.any():
        d = ndimage.distance_transform_edt(~special) * g.res
        nodes |= (d <= ramp_m) & (g.grade != gm.BLOCKED)
    nodes &= g.grade != gm.BLOCKED
    if region is not None:
        nodes &= region
    lab, n = ndimage.label(nodes, structure=np.ones((3, 3)))     # 가장 큰 덩어리만 (GVD 조각이 고립돼 시작 · 목표가 거기 붙는 일을 막음)
    if not n:
        return nodes
    uf = _UF()
    for e in (jumps if jumps is not None else ()):               # 건너뛰기 간선으로 이어진 덩어리는 한 덩어리
        la, lb = int(lab[e[0], e[1]]), int(lab[e[2], e[3]])
        if la and lb:
            uf.union(la, lb)
    size: dict = {}
    for k, cnt in enumerate(np.bincount(lab.ravel())[1:], start=1):
        size[uf.find(k)] = size.get(uf.find(k), 0) + int(cnt)
    best = max(size, key=size.get)
    keep = np.array([0] + [int(uf.find(k) == best) for k in range(1, n + 1)], bool)
    return keep[lab]


def _cell(g, xy):
    c = (np.asarray(xy, float) / g.res).astype(int)
    if not (0 <= c[0] < g.grade.shape[0] and 0 <= c[1] < g.grade.shape[1]):
        raise ValueError("point outside the room")
    return int(c[0]), int(c[1])


_CACHE = True      # 시험이 끌 수 있다 (캐시 없는 옛 계산과 같은 길이 나오는지 대조)


def _static(g: gm.GradeMap, ramp_m: float, stride_m: float | None) -> dict:
    """방 (GradeMap) 마다 한 번만 만드는 값: 통과 가능 덩어리 · 건너뛰기 간선 · 덩어리 합치기. 시작 · 목표와 무관해서 find_path 가 부를 때마다 다시 만들 까닭이 없다
    (G3 Pod 실측: 새 과제 하나에 find_path 약 8 번 · 한 번 0.1 초 안팎 중 대부분이 이 계산이었다). 격자 · 비용 · 간격이 바뀌면 (지문이 달라지면) 다시 만든다."""
    fp = (hash(g.grade.tobytes()), hash(np.asarray(g.cost).tobytes()), float(g.res), float(g.stride_m if stride_m is None else stride_m), float(ramp_m),
          None if g.patch is None else hash(np.asarray(g.patch).tobytes()))
    c = getattr(g, "_gvd_static", None) if _CACHE else None
    if c is not None and c["fp"] == fp:
        return c
    reg, _ = ndimage.label(g.grade != gm.BLOCKED, structure=np.ones((3, 3)))   # 통과 가능 덩어리
    jumps = jump_edges(g, stride_m)
    uf = _UF()
    for e in jumps:                                                            # 건너뛰기로 이어지는 덩어리끼리 합침
        uf.union(int(reg[e[0], e[1]]), int(reg[e[2], e[3]]))
    c = {"fp": fp, "reg": reg, "jumps": jumps, "uf": uf, "groups": {}, "clear": None}
    if _CACHE:
        g._gvd_static = c
    return c


def _group(g: gm.GradeMap, st: dict, group: int, ramp_m: float):
    """한 덩어리의 (노드 마스크 · 가장 가까운 노드 색인 · 건너뛰기 연결). 없으면 (None, None, None)."""
    got = st["groups"].get(group)
    if got is not None:
        return got
    reg, jumps, uf = st["reg"], st["jumps"], st["uf"]
    member = np.array([uf.find(int(k)) == group for k in range(int(reg.max()) + 1)], bool)
    member[0] = False
    nodes = node_mask(g, ramp_m, member[reg], jumps)
    if not nodes.any():
        got = (None, None, None)
    else:
        _, idx = ndimage.distance_transform_edt(~nodes, return_indices=True)
        cost = g.cost
        link: dict = {}
        for ax, ay, bx, by, d in jumps:
            u, v = (int(ax), int(ay)), (int(bx), int(by))
            if nodes[u] and nodes[v]:
                step = d / 1000.0 * g.res * 0.5 * (cost[u] + cost[v])
                link.setdefault(u, []).append((v, step))
                link.setdefault(v, []).append((u, step))
        got = (nodes, idx, link)
    if _CACHE:
        st["groups"][group] = got
    return got


def _lists(st: dict, nodes, cost):
    st["lists"] = (nodes, nodes.tolist(), np.asarray(cost, np.float64).tolist())
    return st["lists"]


def find_path(g: gm.GradeMap, start_xy, goal_xy, ramp_m: float = RAMP_M, stride_m: float | None = None, straighten: bool = False) -> Path:
    s, t = _cell(g, start_xy), _cell(g, goal_xy)
    if g.grade[s] == gm.BLOCKED or g.grade[t] == gm.BLOCKED:
        raise ValueError("start and goal must be on passable cells")
    st = _static(g, ramp_m, stride_m)
    reg, uf = st["reg"], st["uf"]
    if uf.find(int(reg[s])) != uf.find(int(reg[t])):
        return Path(False, np.zeros((0, 2)), 0.0, np.inf)                      # 서로 다른 덩어리 = 경로 없음
    nodes, idx, link = _group(g, st, uf.find(int(reg[s])), ramp_m)
    if nodes is None:
        return Path(False, np.zeros((0, 2)), 0.0, np.inf)
    s2, t2 = (int(idx[0][s]), int(idx[1][s])), (int(idx[0][t]), int(idx[1][t]))
    cost = g.cost
    h, w = cost.shape
    ls = st.get("lists")
    if ls is None or ls[0] is not nodes:
        ls = _lists(st, nodes, cost)
    nodes_l, cost_l = ls[1], ls[2]
    res = g.res
    nb = [(dx, dy, math.hypot(dx, dy) * res * 0.5, math.hypot(dx, dy) * res) for dx, dy in _NB]
    hyp = math.hypot
    dist = {s2: 0.0}
    prev = {}
    pq = [(0.0, s2)]
    best = np.inf
    t0, t1 = t2
    while pq:
        f, u = heapq.heappop(pq)
        if u == t2:
            best = dist[u]
            break
        du = dist[u]
        u0, u1 = u
        if f > du + hyp(u0 - t0, u1 - t1) * res + 1e-9:
            continue                                    # 낡은 큐 항목
        cu = cost_l[u0][u1]
        around = []
        for dx, dy, half, _full in nb:                  # 순수 파이썬 (numpy 스칼라 접근이 느렸다: G3 Pod 실측)
            x, y = u0 + dx, u1 + dy
            if 0 <= x < h and 0 <= y < w and nodes_l[x][y]:
                around.append(((x, y), half * (cu + cost_l[x][y])))
        for v, step in around + link.get(u, []):
            nd = du + step
            if nd < dist.get(v, np.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd + hyp(v[0] - t0, v[1] - t1) * res, v))
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
    if straighten:
        pts = straighten_path(g, pts)
        length = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    return Path(True, pts, length, float(best) + stub_s + stub_t)


MIN_CLEAR_M = 0.3                 # 곧게 편 뒤에도 장애물 (막힌 칸) 과의 여유가 이 아래로 내려가지 않는다 (원래 길이 더 좁게 지나면 그 값까지만)
STRAIGHT_STEP_M = 0.05


def straighten_path(g: gm.GradeMap, points: np.ndarray, min_clear_m: float = MIN_CLEAR_M) -> np.ndarray:
    """경로 곧게 펴기 (DESIGN-HIPAN-ROOMS-1117 3.3 · 4: 보로노이 뼈대가 빈 곳에서 도는 것을 줄임. 논문에 없는 덧붙임).
    앞에서부터 보이는 (직선이 평지 FREE 셀만 지나고 막힌 칸과의 여유가 need 이상인) 가장 먼 점으로 잇는다. need = min(min_clear_m, 원래 길의 최소 여유):
    원래 길이 좁은 문을 지났으면 그 문까지는 허용하되 더 좁은 곳으로는 안 깎는다. 계단 · 머리 위 · 듬성한 셀을 지나는 구간은 원래 점을 그대로 둔다."""
    pts = np.asarray(points, float)
    if len(pts) <= 2:
        return pts
    st = _static(g, RAMP_M, None)
    if st["clear"] is None or not _CACHE:
        st["clear"] = (ndimage.distance_transform_edt(g.grade != gm.BLOCKED) * g.res, g.grade == gm.FREE)
    dist, free_grade = st["clear"]
    h, w = dist.shape
    hw = np.array([h - 1, w - 1])

    def at(xy):
        c = np.clip((np.asarray(xy) / g.res).astype(int), 0, hw)
        return int(c[0]), int(c[1])

    need = min(min_clear_m, float(min(dist[at(q)] for q in pts)))

    def visible(a, b):
        n = max(int(np.ceil(np.linalg.norm(b - a) / STRAIGHT_STEP_M)), 1)
        c = np.clip(((a + (b - a) * (np.arange(n + 1) / n)[:, None]) / g.res).astype(int), 0, hw)      # 선 위 모든 점을 한 번에 (옛 꼴은 점마다 파이썬 반복)
        return bool(free_grade[c[:, 0], c[:, 1]].all() and (dist[c[:, 0], c[:, 1]] >= need - 1e-9).all())

    out, i = [pts[0]], 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not visible(pts[i], pts[j]):
            j -= 1
        out.append(pts[j])
        i = j
    return np.array(out)
